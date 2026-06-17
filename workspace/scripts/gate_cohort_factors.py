# SCRIPT_STATUS: ACTIVE — adjudicate + persist CICC-cohort factors through the P-GATE ceiling
"""Take a list of registered CICC-cohort factors through the P-GATE ceiling adjudication:
for each, ensure a univ_all FactorDomainClaim exists, run the SAME `_cohort_ceiling` the live
publish gate uses (manifest tier + oos_eligibility / 7-domain matrix coverage + freshness /
claim / certified operators), and persist its ReplicationGovernanceRecord. Evidence-only —
it does NOT promote anything to candidate (that is the human-gated orchestrator step). This
is the generalized form of canary_cicc_profit.py for a batch (e.g. the D4a difference factors).

Two-phase + fail-closed for --live (GPT E1a-gate review, finding 3): PHASE 1 RESOLVES every
requested factor read-only (registry row present + exactly one cohort-manifest match via
`_cohort_ceiling`); if ANY requested factor is unresolved, --live REFUSES before any write (no
silent 5-of-6 partial write). PHASE 2 registers the missing claims; PHASE 3 adjudicates (now
claims present) + persists governance/stamp/linkage. Dry-run prints each resolved ceiling.

`--hypothesis-id` is REQUIRED and stamped on every claim, and `--governance-notes` on every
governance record (GPT finding 1): the cohort-wave identity must be explicit per run — NEVER
reuse another wave's id (an earlier hard-coded `cicc_d4a` default would have polluted E1a's
domain-claim history).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from src.alpha_research.factor_registry import FactorRegistryStore  # noqa: E402
from src.alpha_research.factor_registry.domain_claims import DomainClaimStore  # noqa: E402
from src.alpha_research.factor_library.operator_certification import OperatorCertStore  # noqa: E402
from src.alpha_research.factor_registry.replication_governance import (  # noqa: E402
    CohortFactorLinkageStore,
    ReplicationGovernanceStore,
)
from src.research_orchestrator.factor_lifecycle_steps import (  # noqa: E402
    _cohort_ceiling,
    _load_cohort_manifests,
    _oos_trade_calendar,
)

UNIVERSE = "univ_all"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--factors", required=True, help="comma-separated catalog factor ids")
    ap.add_argument("--live", action="store_true", help="register claims + persist records")
    ap.add_argument("--hypothesis-id", required=True,
                    help="domain-claim hypothesis_id for THIS cohort wave (e.g. "
                         "cicc_e1a_momentum_reversal). REQUIRED — never reuse another wave's id.")
    ap.add_argument("--governance-notes", default="",
                    help="note stamped on each governance record; default derived from --hypothesis-id")
    ap.add_argument("--registry-dir", default="",
                    help="registry dir to operate on (default: live data/factor_registry; point at a "
                         "temp copy to dry-/live-exercise the fail-closed flow without touching production)")
    args = ap.parse_args()
    factors = [f.strip() for f in args.factors.split(",") if f.strip()]
    gov_notes = args.governance_notes or f"{args.hypothesis_id} P-GATE ceiling adjudication via gate_cohort_factors"

    reg = Path(args.registry_dir) if args.registry_dir else PROJECT_ROOT / "data" / "factor_registry"
    store = FactorRegistryStore(reg)
    claims = DomainClaimStore(reg)
    manifests = _load_cohort_manifests()
    certified_ops = OperatorCertStore(reg).certified_operators()
    gov = ReplicationGovernanceStore(reg)
    linkage = CohortFactorLinkageStore(reg)
    oos_cal = _oos_trade_calendar() or None   # exact OOS quarantine (R1 F9)
    cur = store.factor_master[store.factor_master["is_current"].fillna(False)]  # noqa: E712
    # F3: factors carrying a ledger link or a factor_master stamp "claim CICC" → fail closed on
    # a dropped manifest link.
    _active = linkage.active_links()
    linked_ids = set(_active["factor_id"].astype(str).tolist()) if len(_active) else set()
    linked_hashes = ({str(r["factor_id"]): str(r.get("definition_hash") or "")
                      for _, r in _active.iterrows()} if len(_active) else {})
    if len(cur) and "replication_cohort_id" in cur.columns:
        st = cur[cur["replication_cohort_id"].notna()]
        if len(st):
            st = st[st["replication_cohort_id"].astype("string").str.strip() != ""]
            linked_ids |= set(st["factor_id"].astype(str).tolist())

    def _adjudicate(fid: str):
        """Read-only: resolve fid through _cohort_ceiling. Returns (info|None, def_hash, reason)."""
        row = cur[cur["factor_id"] == fid]
        if not len(row):
            return None, "", "not_in_registry"
        def_hash = str(row.iloc[0]["definition_hash"])
        try:
            info = _cohort_ceiling(fid, UNIVERSE, manifests=manifests, evidence_df=store.factor_evidence,
                                   claim_store=claims, current_definition_hash=def_hash,
                                   certified_operators=certified_ops, trade_calendar=oos_cal,
                                   is_cohort_linked=(fid in linked_ids),
                                   linked_definition_hash=linked_hashes.get(fid, ""))
        except Exception as e:   # F1: any adjudication error on a cohort factor = fail closed
            return None, def_hash, f"adjudication_error:{type(e).__name__}:{e}"
        if info is None:
            return None, def_hash, "not_a_cohort_factor_manifest_link_missing"
        return info, def_hash, ""

    # ── PHASE 1: resolve every requested factor read-only (fail-closed for --live) ──
    resolved: dict[str, str] = {}   # fid -> def_hash
    unresolved: list = []
    for fid in factors:
        info, def_hash, reason = _adjudicate(fid)
        if reason:
            unresolved.append((fid, reason))
        else:
            resolved[fid] = def_hash
    print(f"resolve: {len(resolved)}/{len(factors)} requested factors resolved to exactly one cohort row")
    for fid, reason in unresolved:
        print(f"  UNRESOLVED {fid:22} {reason}")
    if unresolved and args.live:
        raise SystemExit(f"REFUSING --live: {len(unresolved)}/{len(factors)} requested factors unresolved "
                         "— a partial write would leave the cohort half-adjudicated (fail-closed, GPT "
                         "finding 3). Fix the factor ids / manifest links and re-run.")

    # ── PHASE 2 (--live): register the missing univ_all claims for the resolved factors ──
    if args.live:
        for fid in resolved:
            existing = claims.claims()
            have = (len(existing[(existing["factor_id"] == fid) & (existing["universe_id"] == UNIVERSE)
                                 & (existing["status"] != "rejected_claim")]) if len(existing) else 0)
            if not have:
                claims.register_claim(factor_id=fid, universe_id=UNIVERSE,
                                      hypothesis_id=args.hypothesis_id, declared_domain_count=1)

    # ── PHASE 3: adjudicate (claims now present) + persist governance / stamp / linkage ──
    written = 0
    for fid in resolved:
        info, def_hash, reason = _adjudicate(fid)
        if reason or info is None:   # a claim-registration regression would surface here
            raise SystemExit(f"{fid}: resolved in phase 1 but re-adjudication failed ({reason}) — aborting "
                             "before further writes (fail-closed).")
        dec = info["decision"]
        print(f"{fid:22} ceiling={dec.status_ceiling:18} blocking={','.join(dec.blocking_reasons)}")
        if args.live:
            gov.upsert(
                cohort_id=info["cohort_id"], factor_id=fid,
                factor_domain_claim_id=info["claim_id"] or f"{fid}:{UNIVERSE}",
                replication_tier=info["row"].replication_tier_planned,
                active_cap_reasons=dec.active_cap_reasons, oos_eligible_gates_met=dec.oos_eligible_gates_met,
                cohort_denominator_membership=["formalization_candidate"],
                truth_label_end=info["row"].truth_table_label_end,
                oos_quarantine_start=info.get("oos_quarantine_start", ""),
                oos_quarantine_approximate=bool(info.get("oos_quarantine_approximate", False)),
                notes=gov_notes,
            )
            # F3 + F11: stamp the reverse link (idempotent) + append a `linked` ledger event only
            # for a NEW link (drift on an existing link already raised in _cohort_ceiling; no churn).
            hb = str(getattr(info["row"], "handbook_id", "") or "")
            store.set_replication_link(factor_id=fid, cohort_id=info["cohort_id"], handbook_id=hb)
            if fid not in linked_ids:
                linkage.record_linkage(
                    cohort_id=info["cohort_id"], factor_id=fid, handbook_id=hb,
                    definition_hash=def_hash, event="linked", notes="gate_cohort_factors")
            written += 1

    if args.live:
        store.save()   # persist the factor_master replication_cohort_id stamps
        # GPT finding 3 checklist: exactly all requested factors written, none dropped.
        if written != len(factors):
            raise SystemExit(f"POST-WRITE MISMATCH: wrote {written} governance records but {len(factors)} "
                             "factors were requested — investigate (some write silently skipped).")
        print(f"claims + governance records + linkage stamps persisted: written={written} "
              f"requested={len(factors)} hypothesis_id={args.hypothesis_id}")
    else:
        print("dry-run — re-run with --live to register claims + persist records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
