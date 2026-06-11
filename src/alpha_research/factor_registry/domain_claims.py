"""FactorDomainClaim + unified TaintLedger + claim-class resolver (universe plan Draft-7).

The domain-claim table is the SOURCE OF TRUTH for the universe lifecycle of a factor
("approved 的是 claim,不是 factor" — §3.0b): each row is one (factor, universe) claim
with its own status ladder. ``factor.status`` in the master registry remains the
denormalized view of the factor's PRIMARY claim (zero migration for the 42 catalog
call sites and the existing writer gates).

The TaintLedger is ONE state machine for all five contamination sources (§3.6b —
GPT R3-B3: do not build five independent trackers). Gate adjudication calls a single
function, :func:`resolve_claim_class`, whose output is one of FOUR classes:

    clean_singleton_primary        original IS-gate bar
    predeclared_multi_domain       bar adjusted for the declared k domains
    tainted_post_hoc_max_stat      permutation max-stat bar (§3.3 calibration contract)
    evidence_only_not_status_bearing   cannot carry a status-bearing claim at all

Hard rules encoded here (from the three GPT review rounds):
- an ``exploratory_eval`` / ``idea_family`` / ``lineage`` taint match downgrades the
  DEFAULT class (mechanical consequence, not disclosure) — overrides are explicit,
  reasoned, and audit-logged (R2 condition 1);
- thin-domain hard floors are admission rules, not diagnostics (R2 condition 5) —
  enforced at the gate layer which consults this resolver;
- taint NEVER decays with time; the only freshness recovery is a prospective
  fresh-window claim evaluated purely on post-taint labels (R3-B4).

Stores follow the registry pattern: parquet + file_lock around read-check-write.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.research_orchestrator.file_lock import file_lock

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CLAIMS_DIR = _PROJECT_ROOT / "data" / "factor_registry"

CLAIM_STATUSES = ("draft_claim", "candidate_claim", "approved_claim", "rejected_claim")
CLAIM_CLASSES = (
    "clean_singleton_primary",
    "predeclared_multi_domain",
    "tainted_post_hoc_max_stat",
    "evidence_only_not_status_bearing",
)
TAINT_SOURCE_TYPES = (
    "exploratory_eval",          # sanctioned-tool run without a claim context
    "lineage",                   # derived_from / clone ancestry
    "component_selection",       # composite built from matrix-selected components
    "idea_family",               # same research family observed the domain
    "non_primary_formal_evidence",  # all-domain gate run landed evidence here
    "manual_override",
)
TAINT_EFFECTS = ("none", "disclose", "post_hoc_max_stat", "block_status_claim")

CLAIM_COLUMNS = [
    "claim_id", "factor_id", "universe_id", "hypothesis_id", "research_family_id",
    "pre_registered_at", "status", "claim_class", "multiplicity_adjustment",
    "declared_domain_count", "lineage_taint_domains_json",
    "gate_evidence_id", "sealed_oos_id", "prospective_fresh_window_start",
    "created_at", "updated_at", "notes",
]
TAINT_COLUMNS = [
    "entry_id", "source_type", "source_id", "factor_id", "research_family_id",
    "universe_id", "observed_at", "evidence_ids_json", "taint_effect",
    "override_reason", "created_at",
]


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class ClaimClassDecision:
    claim_class: str
    reasons: tuple          # ordered, human-readable, audit-friendly
    taint_entry_ids: tuple  # the ledger rows that drove a downgrade
    override_applied: bool = False


class DomainClaimStore:
    """Parquet-backed FactorDomainClaim + TaintLedger with locked read-check-write."""

    def __init__(self, base_dir: str | Path | None = None):
        self.base_dir = Path(base_dir) if base_dir else DEFAULT_CLAIMS_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.claims_path = self.base_dir / "factor_domain_claims.parquet"
        self.taint_path = self.base_dir / "taint_ledger.parquet"
        self._lock = self.base_dir / ".domain_claims.lock"

    # ---------------- io ----------------
    def _read(self, path: Path, columns: list) -> pd.DataFrame:
        if path.exists():
            return pd.read_parquet(path)
        return pd.DataFrame(columns=columns)

    def claims(self) -> pd.DataFrame:
        return self._read(self.claims_path, CLAIM_COLUMNS)

    def taints(self) -> pd.DataFrame:
        return self._read(self.taint_path, TAINT_COLUMNS)

    # ---------------- taint ledger ----------------
    def record_taint(
        self,
        *,
        source_type: str,
        factor_id: str = "",
        research_family_id: str = "",
        universe_id: str,
        source_id: str = "",
        evidence_ids: list | None = None,
        taint_effect: str = "post_hoc_max_stat",
        override_reason: str = "",
    ) -> str:
        """Append one taint entry. ``factor_id`` or ``research_family_id`` must be set."""
        if source_type not in TAINT_SOURCE_TYPES:
            raise ValueError(f"unknown source_type {source_type!r}")
        if taint_effect not in TAINT_EFFECTS:
            raise ValueError(f"unknown taint_effect {taint_effect!r}")
        if not factor_id and not research_family_id:
            raise ValueError("taint entry needs factor_id or research_family_id")
        now = _utcnow()
        with file_lock(self._lock):
            df = self.taints()
            entry_id = f"taint_{len(df):06d}_{source_type}"
            row = {
                "entry_id": entry_id, "source_type": source_type, "source_id": source_id,
                "factor_id": factor_id, "research_family_id": research_family_id,
                "universe_id": universe_id, "observed_at": now,
                "evidence_ids_json": json.dumps(list(evidence_ids or []), ensure_ascii=False),
                "taint_effect": taint_effect, "override_reason": override_reason,
                "created_at": now,
            }
            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
            df.to_parquet(self.taint_path, index=False)
        return entry_id

    def taints_for(self, factor_id: str = "", research_family_id: str = "",
                   universe_id: str | None = None) -> pd.DataFrame:
        df = self.taints()
        if df.empty:
            return df
        sel = pd.Series(False, index=df.index)
        if factor_id:
            sel |= df["factor_id"] == factor_id
        if research_family_id:
            sel |= df["research_family_id"] == research_family_id
        out = df[sel]
        if universe_id is not None:
            out = out[out["universe_id"] == universe_id]
        return out

    # ---------------- claims ----------------
    def register_claim(
        self,
        *,
        factor_id: str,
        universe_id: str,
        hypothesis_id: str = "",
        research_family_id: str = "",
        declared_domain_count: int = 1,
        pre_registered_at: str | None = None,
        notes: str = "",
    ) -> str:
        """Create a draft_claim. The claim class is RESOLVED (not chosen) — taint
        ledger + declaration count decide it; callers cannot self-assign a class."""
        now = _utcnow()
        pre_at = pre_registered_at or now
        decision = self.resolve_claim_class(
            factor_id=factor_id, research_family_id=research_family_id,
            universe_id=universe_id, pre_registered_at=pre_at,
            declared_domain_count=declared_domain_count,
        )
        with file_lock(self._lock):
            df = self.claims()
            dup = df[(df["factor_id"] == factor_id) & (df["universe_id"] == universe_id)
                     & (df["status"] != "rejected_claim")]
            if not dup.empty:
                raise ValueError(
                    f"active claim already exists for ({factor_id}, {universe_id}): "
                    f"{dup.iloc[-1]['claim_id']}")
            claim_id = f"claim_{factor_id}_{universe_id}_{len(df):05d}"
            row = {
                "claim_id": claim_id, "factor_id": factor_id, "universe_id": universe_id,
                "hypothesis_id": hypothesis_id, "research_family_id": research_family_id,
                "pre_registered_at": pre_at, "status": "draft_claim",
                "claim_class": decision.claim_class,
                "multiplicity_adjustment": decision.claim_class,
                "declared_domain_count": int(declared_domain_count),
                "lineage_taint_domains_json": json.dumps(
                    sorted(set(self.taints_for(factor_id, research_family_id)["universe_id"]))
                    if not self.taints_for(factor_id, research_family_id).empty else []),
                "gate_evidence_id": "", "sealed_oos_id": "",
                "prospective_fresh_window_start": "",
                "created_at": now, "updated_at": now, "notes": notes,
            }
            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
            df.to_parquet(self.claims_path, index=False)
        return claim_id

    def set_claim_status(self, claim_id: str, status: str, *,
                         gate_evidence_id: str = "", sealed_oos_id: str = "") -> None:
        """Advance a claim. candidate/approved transitions are called by the HUMAN
        gates only (the same signing discipline as the factor-level writer gate —
        this store records, it does not adjudicate)."""
        if status not in CLAIM_STATUSES:
            raise ValueError(f"unknown claim status {status!r}")
        with file_lock(self._lock):
            df = self.claims()
            idx = df.index[df["claim_id"] == claim_id]
            if len(idx) != 1:
                raise KeyError(f"claim {claim_id!r} not found (or ambiguous)")
            i = idx[0]
            if df.at[i, "claim_class"] == "evidence_only_not_status_bearing" and \
                    status in ("candidate_claim", "approved_claim"):
                raise ValueError(
                    f"claim {claim_id} is evidence_only_not_status_bearing — it cannot "
                    "carry a status-bearing transition (thin-domain floor or block-level taint)")
            df.at[i, "status"] = status
            if gate_evidence_id:
                df.at[i, "gate_evidence_id"] = gate_evidence_id
            if sealed_oos_id:
                df.at[i, "sealed_oos_id"] = sealed_oos_id
            df.at[i, "updated_at"] = _utcnow()
            df.to_parquet(self.claims_path, index=False)

    def oos_validated_domains(self, factor_id: str) -> list:
        """§3.5 three-field semantics: the ONLY domains a production resolver may
        treat as approved scope = domains with an approved_claim."""
        df = self.claims()
        if df.empty:
            return []
        sel = df[(df["factor_id"] == factor_id) & (df["status"] == "approved_claim")]
        return sorted(sel["universe_id"].unique())

    # ---------------- the resolver (§3.6b) ----------------
    def resolve_claim_class(
        self,
        *,
        factor_id: str,
        universe_id: str,
        pre_registered_at: str,
        research_family_id: str = "",
        declared_domain_count: int = 1,
        override_reason: str = "",
    ) -> ClaimClassDecision:
        """ONE function decides the claim class from the unified ledger.

        Order of precedence (most severe wins):
        1. any ``block_status_claim`` taint on (factor|family, universe) → evidence_only
        2. any taint with effect ``post_hoc_max_stat`` observed BEFORE
           ``pre_registered_at`` → tainted_post_hoc_max_stat (the mechanical
           consequence; an explicit ``override_reason`` lifts it back to the
           declaration-based class and is itself recorded as a manual_override
           taint entry — audit event, R2 condition 1)
        3. ``declared_domain_count > 1`` → predeclared_multi_domain
        4. else → clean_singleton_primary
        Taints observed AFTER pre_registered_at do not downgrade the claim (the
        declaration predates the observation) — they matter for FUTURE claims.
        """
        taints = self.taints_for(factor_id, research_family_id, universe_id)
        reasons: list = []
        drove: list = []
        if not taints.empty:
            blockers = taints[taints["taint_effect"] == "block_status_claim"]
            if not blockers.empty:
                return ClaimClassDecision(
                    "evidence_only_not_status_bearing",
                    tuple([f"block-level taint: {t}" for t in blockers["entry_id"]]),
                    tuple(blockers["entry_id"]))
            prior = taints[(taints["taint_effect"] == "post_hoc_max_stat")
                           & (taints["observed_at"] <= pre_registered_at)]
            if not prior.empty:
                if override_reason:
                    self.record_taint(
                        source_type="manual_override", factor_id=factor_id,
                        research_family_id=research_family_id, universe_id=universe_id,
                        taint_effect="disclose", override_reason=override_reason)
                    reasons.append(f"taint overridden (audited): {override_reason}")
                else:
                    return ClaimClassDecision(
                        "tainted_post_hoc_max_stat",
                        tuple([f"prior taint: {t}" for t in prior["entry_id"]]),
                        tuple(prior["entry_id"]))
        if declared_domain_count > 1:
            reasons.append(f"declared {declared_domain_count} domains")
            return ClaimClassDecision("predeclared_multi_domain", tuple(reasons), tuple(drove),
                                      override_applied=bool(override_reason))
        reasons.append("singleton primary declaration, no prior taint")
        return ClaimClassDecision("clean_singleton_primary", tuple(reasons), tuple(drove),
                                  override_applied=bool(override_reason))
