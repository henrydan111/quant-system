"""CICC handbook replication governance (roadmap Rev5 §9 / §12, GPT 3-round APPROVE).

This is the *governance skeleton* the remaining-CICC roadmap is built on. It provides
three things, all per the cross-reviewed plan:

1. **CohortManifest** (§9.1) — the FROZEN declaration of a CICC handbook's factor
   inventory, locked BEFORE any batch registration so the cohort denominators,
   replication tiers, exclusion reasons, truth-table label windows and OOS
   eligibility cannot be chosen *after* seeing results (§9.2 anti-p-hacking). The
   manifest lives as committed governance YAML under ``config/replication/`` (never
   ``data/`` — CLAUDE.md §3.4); ``manifest_sha`` pins its content so any edit is
   detectable.

2. **ReplicationGovernanceRecord** (§12.3) — the ONE per-(cohort, factor, domain-claim)
   record that replaces the six separate ledgers. It carries the replication tier,
   the source truth tables + ``truth_label_end`` + derived ``oos_quarantine_start``
   (§9.3), the operator / data-provider / availability cert ids, the cohort-denominator
   membership, and the resolved status ceiling + reason codes.

3. **resolve_status_ceiling** (§12.4) — the DETERMINISTIC lattice. ``status_ceiling`` is
   NOT assembled ad-hoc from five cert completion states; it is one deterministic walk
   from strictest to loosest that materialises a SINGLE ceiling plus reason codes, so
   "why is this claim stuck" is machine-explainable. Two hard rules from the review:
     * ``orientation_undetermined`` does NOT lower the ceiling — a weak signal is not
       disqualified (§11.1b); it is recorded in ``uncomputable_metrics`` only. The
       resolver fails closed if it is passed as a cap reason, forcing callers to route
       it correctly.
     * the five denominators (§9.2) MUST be pre-frozen; any "CICC replication pass-rate"
       statement must report ``formalization_candidate / exact_oos_eligible /
       sealed_attempt`` together — :func:`cohort_pass_rate` refuses to emit one without
       all three.

The OOS-quarantine helper encodes §9.3: doing parity against a handbook truth table
*observes* its label window, so a CICC-replicated factor's sealed OOS may not start
before ``max(system_oos_start, truth_label_end + horizon + embargo)``.

Stores follow the registry pattern: parquet + ``file_lock`` around read-check-write.
This module is pure governance bookkeeping — it adjudicates nothing on its own (the
human gate + the IS/OOS validators remain the deciders) and reads no market data
(the trading calendar, when needed, is injected).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from src.research_orchestrator.file_lock import file_lock

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_GOV_DIR = _PROJECT_ROOT / "data" / "factor_registry"
DEFAULT_MANIFEST_DIR = _PROJECT_ROOT / "config" / "replication"

# ---- replication tiers (§7 / §9.1): only ``exact_certified`` counts as faithful ----
REPLICATION_TIERS = (
    "exact_certified",
    "formula_equivalent_pending",
    "proxy_approx",
    "derived_methodology_proxy",
    "not_replicable",
)

# ---- the five pre-frozen cohort denominators (§9.2) ----
COHORT_DENOMINATORS = (
    "source",                  # the handbook's full factor list (incl HF / non-replicable / dup) — scope honesty
    "daily_replicability",     # daily-frequency theoretically constructible — coverage
    "formalization_candidate", # the ~183 (frozen before registration) — engineering completeness
    "exact_oos_eligible",      # exact_certified AND still meets the power floor after OOS quarantine
    "sealed_attempt",          # attempts that actually spent sealed OOS (incl fail/withdraw) — kill-rate
)
# the first three are FROZEN in the manifest; the last two are tracked as work proceeds.
_FROZEN_DENOMINATORS = ("source", "daily_replicability", "formalization_candidate")

# ---- status-ceiling lattice, STRICT -> LOOSE (§12.4) ----
STATUS_CEILINGS = (
    "blocked",
    "dev_evidence_only",
    "evidence_only",
    "candidate_ceiling",
    "eligible_for_oos",
    "eligible_for_approved",
)

# reason codes that CAP a claim AT a ceiling (a cap must be REMOVED to advance).
CEILING_CAP_REASONS = {
    "blocked": (
        "non_pit_data_provider", "uncertified_operator",
        "missing_required_field", "failed_truth_table_qa",
    ),
    "dev_evidence_only": (
        "operator_experimental", "data_pit_cert_pending", "truth_table_unreviewed",
    ),
    "evidence_only": (
        "availability_floor_fail", "non_approved_universe",
        "structural_break_unresolved", "insufficient_cross_sections",
    ),
    "candidate_ceiling": (
        "proxy_approx", "derived_methodology_proxy",
        "oos_already_spent_same_family", "short_oos_power_floor_fail",
    ),
}
_ALL_CAP_REASONS = frozenset(r for rs in CEILING_CAP_REASONS.values() for r in rs)

# positive GATES that must be ACQUIRED to advance (not caps to remove).
OOS_ELIGIBLE_GATES = (
    "clean_or_calibrated_claim", "certified_operator", "coverage_pass", "denominator_frozen",
)
APPROVED_GATES = ("sealed_oos_pass", "power_floor_pass")

# §11.1b: weak-signal / uncomputable flags that are RECORDED but DO NOT lower the
# ceiling (a weak signal is not a disqualified factor). Passing one as a cap reason
# is a programming error — the resolver fails closed so callers route it to
# ``uncomputable_metrics`` instead.
NON_CEILING_FLAGS = ("orientation_undetermined",)

OOS_ELIGIBILITY = ("eligible", "spent_same_family", "institutional_break", "short_window", "pending")


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ceiling_rank(ceiling: str) -> int:
    return STATUS_CEILINGS.index(ceiling)


# --------------------------------------------------------------------------- #
# 1. the deterministic lattice resolver (§12.4)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class StatusCeilingDecision:
    status_ceiling: str
    blocking_reasons: tuple          # cap reason codes at the resolved level — must be REMOVED
    nonblocking_missing_certs: tuple # positive gates still to ACQUIRE to advance one level
    next_actions: tuple              # human-readable, ordered


def resolve_status_ceiling(
    active_cap_reasons,
    *,
    oos_eligible_gates_met=(),
    approved_gates_met=(),
) -> StatusCeilingDecision:
    """Deterministic walk strict→loose; materialise a SINGLE ceiling + reasons (§12.4).

    ``active_cap_reasons`` = the cap reason codes currently TRUE for this claim (must be
    a subset of :data:`_ALL_CAP_REASONS`). The STRICTEST applicable cap wins. If no cap
    applies, the claim advances as far as its positive gates allow.

    Fails closed (``ValueError``) on an unknown reason code, and specifically on any
    :data:`NON_CEILING_FLAGS` value (e.g. ``orientation_undetermined``) — those are
    recorded in ``uncomputable_metrics``, never treated as a ceiling cap (§11.1b).
    """
    active = set(active_cap_reasons)
    bad = active - _ALL_CAP_REASONS
    if bad:
        nonc = bad & set(NON_CEILING_FLAGS)
        if nonc:
            raise ValueError(
                f"{sorted(nonc)} are NON_CEILING_FLAGS (§11.1b): record them in "
                "uncomputable_metrics, do NOT pass as a status-ceiling cap")
        raise ValueError(f"unknown cap reason code(s): {sorted(bad)}")

    # strictest applicable cap wins (iterate strict -> loose over the capped levels)
    for level in ("blocked", "dev_evidence_only", "evidence_only", "candidate_ceiling"):
        hits = tuple(r for r in CEILING_CAP_REASONS[level] if r in active)
        if hits:
            return StatusCeilingDecision(
                level, hits, (),
                tuple(f"resolve cap: {r}" for r in hits))

    # no caps → how far do the positive gates carry it?
    oos_met, app_met = set(oos_eligible_gates_met), set(approved_gates_met)
    oos_missing = tuple(g for g in OOS_ELIGIBLE_GATES if g not in oos_met)
    if oos_missing:
        # not OOS-eligible yet, but nothing hard-caps it → sits at candidate_ceiling,
        # blocked only by gates to acquire (not caps to remove).
        return StatusCeilingDecision(
            "candidate_ceiling", (), oos_missing,
            tuple(f"acquire gate: {g}" for g in oos_missing))
    app_missing = tuple(g for g in APPROVED_GATES if g not in app_met)
    if app_missing:
        return StatusCeilingDecision(
            "eligible_for_oos", (), app_missing,
            tuple(f"acquire gate: {g}" for g in app_missing))
    return StatusCeilingDecision("eligible_for_approved", (), (), ())


# --------------------------------------------------------------------------- #
# 1b. the P-GATE adjudicator — compose existing governance inputs into a ceiling
# --------------------------------------------------------------------------- #
# These map the THREE standing evidence sources a (factor, universe) already has —
# the cohort manifest (replication_tier + oos_eligibility), the 7-domain matrix
# evidence (coverage_tier + effective_ic_days), and the FactorDomainClaim (claim_class)
# — into the cap reasons + positive gates that :func:`resolve_status_ceiling` consumes.
# This is the gate "brain": the orchestrator gate (P-GATE/F3, next increment) will call
# :func:`resolve_replication_ceiling`; here it can already run over the existing matrix so
# the ceilings are computed + persisted ("gate-readable", Rev5 §item-2) without recomputing.

# §3.9 depth floor: a status-bearing claim needs ~36 months (~756 trading days) of
# effective IC observations spanning ≥2 style regimes.
MIN_EFFECTIVE_IC_DAYS = 756


def tier_cap_reasons(replication_tier: str) -> list:
    """replication_tier → ceiling caps (§7). exact/formula_equivalent carry no tier cap;
    proxy/derived cap at candidate (§9.4); not_replicable is hard-blocked."""
    return {
        "proxy_approx": ["proxy_approx"],
        "derived_methodology_proxy": ["derived_methodology_proxy"],
        "not_replicable": ["missing_required_field"],
    }.get(replication_tier, [])


def availability_cap_reasons(*, coverage_tier: str = "", effective_ic_days=None,
                             cross_section_below_min: bool = False,
                             min_effective_ic_days: int = MIN_EFFECTIVE_IC_DAYS) -> list:
    """§11.1 coverage gate + §3.9 depth floor (both an availability concern). A 'sub'
    coverage tier (<50% cross-sectional) or too few effective IC days fails the floor →
    the domain can only be evidence-only; too-thin per-date cross-sections →
    insufficient_cross_sections."""
    reasons = []
    if coverage_tier == "sub":
        reasons.append("availability_floor_fail")
    if effective_ic_days is not None and float(effective_ic_days) < min_effective_ic_days:
        reasons.append("availability_floor_fail")   # temporal-depth floor (§3.9)
    if cross_section_below_min:
        reasons.append("insufficient_cross_sections")
    # de-dup, preserve order
    return list(dict.fromkeys(reasons))


def oos_eligibility_cap_reasons(oos_eligibility: str) -> list:
    """manifest oos_eligibility → caps (§9.3/§9.4). short_window (truth-table observed →
    post-quarantine OOS too short) and spent_same_family cap at candidate;
    institutional_break is a structural break (evidence-only)."""
    return {
        "short_window": ["short_oos_power_floor_fail"],
        "spent_same_family": ["oos_already_spent_same_family"],
        "institutional_break": ["structural_break_unresolved"],
    }.get(oos_eligibility, [])


def claim_cap_reasons(claim_class: str) -> list:
    """FactorDomainClaim class → caps. An evidence_only claim cannot be status-bearing in
    that domain (§3.5 three-field semantics)."""
    if claim_class == "evidence_only_not_status_bearing":
        return ["non_approved_universe"]
    return []


@dataclass(frozen=True)
class ReplicationCeilingDecision:
    status_ceiling: str
    blocking_reasons: tuple
    nonblocking_missing_certs: tuple
    next_actions: tuple
    active_cap_reasons: tuple        # the full set fed to the lattice (audit)
    oos_eligible_gates_met: tuple


def resolve_replication_ceiling(
    *,
    replication_tier: str,
    claim_class: str = "",
    coverage_tier: str = "",
    effective_ic_days=None,
    oos_eligibility: str = "pending",
    cross_section_below_min: bool = False,
    has_uncertified_operator: bool = False,
    max_stat_calibrated: bool = False,
    denominator_frozen: bool = True,
    sealed_oos_pass: bool = False,
    power_floor_pass: bool = False,
    min_effective_ic_days: int = MIN_EFFECTIVE_IC_DAYS,
) -> ReplicationCeilingDecision:
    """Compose all governance inputs for one (factor, universe) into a status ceiling.

    Conservative-by-construction (the GPT-review spirit): a ``tainted_post_hoc_max_stat``
    claim is NOT ``clean_or_calibrated`` until the P-CAL max-stat engine is available
    (``max_stat_calibrated``), so it cannot reach OOS-eligible on its own — it sits at
    candidate until calibrated or reviewer-overridden (Rev5: "tainted claim 用保守上界或
    reviewer-block,不退回旧 univ_all 原 bar"). An uncertified operator hard-blocks
    (P-OP not done). The result is the SINGLE ceiling + reason codes (§12.4)."""
    if replication_tier not in REPLICATION_TIERS:
        raise ValueError(f"unknown replication_tier {replication_tier!r}")
    caps: list = []
    caps += tier_cap_reasons(replication_tier)
    caps += availability_cap_reasons(
        coverage_tier=coverage_tier, effective_ic_days=effective_ic_days,
        cross_section_below_min=cross_section_below_min,
        min_effective_ic_days=min_effective_ic_days)
    caps += oos_eligibility_cap_reasons(oos_eligibility)
    caps += claim_cap_reasons(claim_class)
    if has_uncertified_operator:
        caps.append("uncertified_operator")
    caps = list(dict.fromkeys(caps))   # de-dup, stable order

    oos_gates: list = []
    if denominator_frozen:
        oos_gates.append("denominator_frozen")
    if claim_class in ("clean_singleton_primary", "predeclared_multi_domain") or (
            claim_class == "tainted_post_hoc_max_stat" and max_stat_calibrated):
        oos_gates.append("clean_or_calibrated_claim")
    if not has_uncertified_operator:
        oos_gates.append("certified_operator")
    if "availability_floor_fail" not in caps and "insufficient_cross_sections" not in caps:
        oos_gates.append("coverage_pass")
    app_gates = [g for g, ok in (("sealed_oos_pass", sealed_oos_pass),
                                 ("power_floor_pass", power_floor_pass)) if ok]

    d = resolve_status_ceiling(caps, oos_eligible_gates_met=oos_gates, approved_gates_met=app_gates)
    return ReplicationCeilingDecision(
        status_ceiling=d.status_ceiling, blocking_reasons=d.blocking_reasons,
        nonblocking_missing_certs=d.nonblocking_missing_certs, next_actions=d.next_actions,
        active_cap_reasons=tuple(caps), oos_eligible_gates_met=tuple(oos_gates))


# --------------------------------------------------------------------------- #
# 2. OOS quarantine from truth-table observation (§9.3)
# --------------------------------------------------------------------------- #
def compute_oos_quarantine_start(
    truth_label_end: str,
    system_oos_start: str,
    *,
    horizon_trading_days: int = 20,
    embargo_trading_days: int = 5,
    trade_calendar=None,
) -> tuple[str, bool]:
    """``max(system_oos_start, truth_label_end + horizon + embargo)`` (§9.3).

    Doing parity against a truth table observes its label window, so a replicated
    factor's sealed OOS cannot start before the label end plus one realisation horizon
    plus an embargo. ``trade_calendar`` (a sorted iterable of ``YYYY-MM-DD`` trading
    days — INJECTED, the module reads no data) advances exactly ``horizon+embargo``
    trading days; without it a conservative calendar-day fallback is used and the
    second return value is ``True`` (=approximate, must be tightened before it gates a
    real OOS spend). If ``truth_label_end`` is blank (not transcribed yet, §12.2), the
    quarantine is just ``system_oos_start`` and ``approximate=False``.
    """
    if not truth_label_end:
        return system_oos_start, False
    if trade_calendar is not None:
        cal = [d for d in trade_calendar if d > truth_label_end]
        steps = horizon_trading_days + embargo_trading_days
        post = cal[steps - 1] if len(cal) >= steps else (cal[-1] if cal else truth_label_end)
        approximate = len(cal) < steps
    else:
        # conservative calendar-day fallback: ~1.6 calendar days per trading day.
        days = int(round((horizon_trading_days + embargo_trading_days) * 1.6))
        end = datetime.strptime(truth_label_end, "%Y-%m-%d") + timedelta(days=days)
        post = end.strftime("%Y-%m-%d")
        approximate = True
    return (max(system_oos_start, post), approximate)


# --------------------------------------------------------------------------- #
# 3. cohort manifest (§9.1) — frozen committed governance YAML
# --------------------------------------------------------------------------- #
@dataclass
class CohortFactorRow:
    factor_name_original: str
    handbook_id: str = ""
    chart_id: str = ""
    formula_source: str = ""
    replication_tier_planned: str = "formula_equivalent_pending"
    exclusion_reason: str = ""
    required_fields: tuple = ()
    required_operators: tuple = ()
    truth_table_domains_available: tuple = ()
    truth_table_label_end: str = ""        # "" = not transcribed yet (lazy §12.2) — explicit, never silent
    primary_claim_universe: str = "univ_all"
    catalog_factor_id: str = ""            # our registry id once registered (may be "")
    oos_eligibility: str = "pending"

    def __post_init__(self):
        if self.replication_tier_planned not in REPLICATION_TIERS:
            raise ValueError(f"unknown replication_tier_planned {self.replication_tier_planned!r}")
        if self.oos_eligibility not in OOS_ELIGIBILITY:
            raise ValueError(f"unknown oos_eligibility {self.oos_eligibility!r}")


@dataclass
class CohortManifest:
    source_cohort_id: str
    handbook_label_window_end: str
    denominators: dict                      # {name: int} — must cover the 3 frozen layers
    factor_rows: list
    manifest_sha: str = ""

    def __post_init__(self):
        missing = [d for d in _FROZEN_DENOMINATORS if d not in self.denominators]
        if missing:
            raise ValueError(f"manifest must freeze denominators {missing} before registration (§9.2)")
        self.factor_rows = [
            r if isinstance(r, CohortFactorRow) else CohortFactorRow(**r) for r in self.factor_rows
        ]
        # manifest_sha is computed from CONTENT (excludes the sha field itself) so any
        # edit to the frozen declaration is detectable.
        self.manifest_sha = self._compute_sha()

    def _compute_sha(self) -> str:
        payload = {
            "source_cohort_id": self.source_cohort_id,
            "handbook_label_window_end": self.handbook_label_window_end,
            "denominators": {k: self.denominators[k] for k in sorted(self.denominators)},
            "factor_rows": [
                {k: (list(v) if isinstance(v, tuple) else v) for k, v in asdict(r).items()}
                for r in self.factor_rows
            ],
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]

    def row_for(self, *, catalog_factor_id: str = "", factor_name_original: str = "") -> CohortFactorRow | None:
        for r in self.factor_rows:
            if catalog_factor_id and r.catalog_factor_id == catalog_factor_id:
                return r
            if factor_name_original and r.factor_name_original == factor_name_original:
                return r
        return None


def load_cohort_manifest(path: str | Path) -> CohortManifest:
    """Load + freeze a cohort manifest from committed YAML (config/replication/)."""
    import yaml  # local import keeps the module importable without yaml for pure-resolver use
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    declared_sha = data.pop("manifest_sha", "")
    m = CohortManifest(
        source_cohort_id=data["source_cohort_id"],
        handbook_label_window_end=data.get("handbook_label_window_end", ""),
        denominators=data["denominators"],
        factor_rows=data.get("factor_rows", []),
    )
    if declared_sha and declared_sha != m.manifest_sha:
        raise ValueError(
            f"manifest_sha mismatch for {m.source_cohort_id}: file declares {declared_sha!r} "
            f"but content hashes to {m.manifest_sha!r} — the frozen manifest was edited")
    return m


def cohort_pass_rate(manifest: CohortManifest, *, n_exact_oos_eligible: int,
                     n_sealed_attempt: int, n_passed: int) -> dict:
    """Emit a cohort pass-rate ALWAYS with the three load-bearing denominators (§9.2).

    There is deliberately no single-number return: any "CICC replication pass-rate"
    must be read against ``formalization_candidate / exact_oos_eligible /
    sealed_attempt`` together, never a bare fraction.
    """
    fc = manifest.denominators.get("formalization_candidate")
    if fc is None:
        raise ValueError("manifest has no frozen formalization_candidate denominator")
    return {
        "source": manifest.denominators.get("source"),
        "daily_replicability": manifest.denominators.get("daily_replicability"),
        "formalization_candidate": fc,
        "exact_oos_eligible": int(n_exact_oos_eligible),
        "sealed_attempt": int(n_sealed_attempt),
        "passed": int(n_passed),
        "note": ("pass-rate is meaningful ONLY against formalization_candidate / "
                 "exact_oos_eligible / sealed_attempt jointly (§9.2); a bare fraction is invalid"),
    }


# --------------------------------------------------------------------------- #
# 4. ReplicationGovernanceRecord store (§12.3) — replaces six separate ledgers
# --------------------------------------------------------------------------- #
GOVERNANCE_COLUMNS = [
    "record_id", "cohort_id", "factor_id", "factor_domain_claim_id",
    "replication_tier", "source_truth_tables_json", "truth_label_end",
    "oos_quarantine_start", "oos_quarantine_approximate",
    "operator_cert_ids_json", "data_provider_cert_ids_json", "availability_audit_id",
    "cohort_denominator_membership_json", "status_ceiling", "blocking_reasons_json",
    "nonblocking_missing_certs_json", "uncomputable_metrics_json",
    "created_at", "updated_at", "notes",
]


@dataclass
class ReplicationGovernanceRecord:
    cohort_id: str
    factor_id: str
    factor_domain_claim_id: str
    replication_tier: str
    status_ceiling: str
    source_truth_tables: tuple = ()
    truth_label_end: str = ""
    oos_quarantine_start: str = ""
    oos_quarantine_approximate: bool = False
    operator_cert_ids: tuple = ()
    data_provider_cert_ids: tuple = ()
    availability_audit_id: str = ""
    cohort_denominator_membership: tuple = ()
    blocking_reasons: tuple = ()
    nonblocking_missing_certs: tuple = ()
    uncomputable_metrics: dict = field(default_factory=dict)
    notes: str = ""


class ReplicationGovernanceStore:
    """Parquet-backed ReplicationGovernanceRecord with locked read-check-write.

    One record per (cohort_id, factor_id, factor_domain_claim_id). The status ceiling
    is RESOLVED here via :func:`resolve_status_ceiling` (callers pass the active cap
    reasons + gate states; they cannot self-assign a ceiling), so the lattice is the
    single source of "why is this claim stuck".
    """

    def __init__(self, base_dir: str | Path | None = None):
        self.base_dir = Path(base_dir) if base_dir else DEFAULT_GOV_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.base_dir / "replication_governance.parquet"
        self._lock = self.base_dir / ".replication_governance.lock"

    def records(self) -> pd.DataFrame:
        if self.path.exists():
            return pd.read_parquet(self.path)
        return pd.DataFrame(columns=GOVERNANCE_COLUMNS)

    @staticmethod
    def _record_id(cohort_id: str, factor_id: str, claim_id: str) -> str:
        return f"{cohort_id}::{factor_id}::{claim_id}"

    def upsert(
        self,
        *,
        cohort_id: str,
        factor_id: str,
        factor_domain_claim_id: str,
        replication_tier: str,
        active_cap_reasons=(),
        oos_eligible_gates_met=(),
        approved_gates_met=(),
        source_truth_tables=(),
        truth_label_end: str = "",
        oos_quarantine_start: str = "",
        oos_quarantine_approximate: bool = False,
        operator_cert_ids=(),
        data_provider_cert_ids=(),
        availability_audit_id: str = "",
        cohort_denominator_membership=(),
        uncomputable_metrics: dict | None = None,
        notes: str = "",
    ) -> ReplicationGovernanceRecord:
        """Resolve the ceiling and idempotently write the record (replace on key)."""
        if replication_tier not in REPLICATION_TIERS:
            raise ValueError(f"unknown replication_tier {replication_tier!r}")
        bad_denoms = set(cohort_denominator_membership) - set(COHORT_DENOMINATORS)
        if bad_denoms:
            raise ValueError(f"unknown cohort denominator(s): {sorted(bad_denoms)}")
        decision = resolve_status_ceiling(
            active_cap_reasons,
            oos_eligible_gates_met=oos_eligible_gates_met,
            approved_gates_met=approved_gates_met,
        )
        rec = ReplicationGovernanceRecord(
            cohort_id=cohort_id, factor_id=factor_id,
            factor_domain_claim_id=factor_domain_claim_id,
            replication_tier=replication_tier,
            status_ceiling=decision.status_ceiling,
            source_truth_tables=tuple(source_truth_tables),
            truth_label_end=truth_label_end,
            oos_quarantine_start=oos_quarantine_start,
            oos_quarantine_approximate=bool(oos_quarantine_approximate),
            operator_cert_ids=tuple(operator_cert_ids),
            data_provider_cert_ids=tuple(data_provider_cert_ids),
            availability_audit_id=availability_audit_id,
            cohort_denominator_membership=tuple(cohort_denominator_membership),
            blocking_reasons=decision.blocking_reasons,
            nonblocking_missing_certs=decision.nonblocking_missing_certs,
            uncomputable_metrics=dict(uncomputable_metrics or {}),
            notes=notes,
        )
        now = _utcnow()
        rid = self._record_id(cohort_id, factor_id, factor_domain_claim_id)
        row = {
            "record_id": rid, "cohort_id": cohort_id, "factor_id": factor_id,
            "factor_domain_claim_id": factor_domain_claim_id,
            "replication_tier": rec.replication_tier,
            "source_truth_tables_json": json.dumps(list(rec.source_truth_tables), ensure_ascii=False),
            "truth_label_end": rec.truth_label_end,
            "oos_quarantine_start": rec.oos_quarantine_start,
            "oos_quarantine_approximate": rec.oos_quarantine_approximate,
            "operator_cert_ids_json": json.dumps(list(rec.operator_cert_ids), ensure_ascii=False),
            "data_provider_cert_ids_json": json.dumps(list(rec.data_provider_cert_ids), ensure_ascii=False),
            "availability_audit_id": rec.availability_audit_id,
            "cohort_denominator_membership_json": json.dumps(
                list(rec.cohort_denominator_membership), ensure_ascii=False),
            "status_ceiling": rec.status_ceiling,
            "blocking_reasons_json": json.dumps(list(rec.blocking_reasons), ensure_ascii=False),
            "nonblocking_missing_certs_json": json.dumps(list(rec.nonblocking_missing_certs), ensure_ascii=False),
            "uncomputable_metrics_json": json.dumps(rec.uncomputable_metrics, ensure_ascii=False),
            "updated_at": now, "notes": notes,
        }
        with file_lock(self._lock):
            df = self.records()
            keep = df[df["record_id"] != rid] if not df.empty else df
            created = now
            if not df.empty:
                prior = df[df["record_id"] == rid]
                if not prior.empty:
                    created = str(prior.iloc[-1]["created_at"])
            row["created_at"] = created
            out = pd.concat([keep, pd.DataFrame([row])], ignore_index=True)
            out = out[GOVERNANCE_COLUMNS]
            out.to_parquet(self.path, index=False)
        return rec
