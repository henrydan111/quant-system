# SCRIPT_STATUS: ACTIVE — adjudicate + persist CICC-cohort factors through the P-GATE ceiling
"""Take a list of registered CICC-cohort factors through the P-GATE ceiling adjudication:
for each, ensure a univ_all FactorDomainClaim exists, run the SAME `_cohort_ceiling` the live
publish gate uses (manifest tier + oos_eligibility / 7-domain matrix coverage + freshness /
claim / certified operators), and persist its ReplicationGovernanceRecord. Evidence-only —
it does NOT promote anything to candidate (that is the human-gated orchestrator step). This
is the generalized form of canary_cicc_profit.py for a batch (e.g. the D4a difference factors).

Dry-run prints each resolved ceiling; --live registers the claims + persists the records.
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
    args = ap.parse_args()
    factors = [f.strip() for f in args.factors.split(",") if f.strip()]

    reg = PROJECT_ROOT / "data" / "factor_registry"
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

    for fid in factors:
        row = cur[cur["factor_id"] == fid]
        if not len(row):
            print(f"{fid:14} NOT IN REGISTRY — skip"); continue
        def_hash = str(row.iloc[0]["definition_hash"])
        existing = claims.claims()
        have = (len(existing[(existing["factor_id"] == fid) & (existing["universe_id"] == UNIVERSE)
                             & (existing["status"] != "rejected_claim")]) if len(existing) else 0)
        if not have and args.live:
            claims.register_claim(factor_id=fid, universe_id=UNIVERSE,
                                  hypothesis_id="cicc_d4a", declared_domain_count=1)
        info = _cohort_ceiling(fid, UNIVERSE, manifests=manifests, evidence_df=store.factor_evidence,
                               claim_store=claims, current_definition_hash=def_hash,
                               certified_operators=certified_ops, trade_calendar=oos_cal,
                               is_cohort_linked=(fid in linked_ids),
                               linked_definition_hash=linked_hashes.get(fid, ""))
        if info is None:
            print(f"{fid:14} NOT a cohort factor (manifest link missing)"); continue
        dec = info["decision"]
        print(f"{fid:14} ceiling={dec.status_ceiling:18} blocking={','.join(dec.blocking_reasons)}")
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
                notes="D4a batch adjudication via gate_cohort_factors",
            )
            # F3 + F11: stamp the reverse link (idempotent) + append a `linked` ledger event only
            # for a NEW link (drift on an existing link already raised in _cohort_ceiling; no churn).
            hb = str(getattr(info["row"], "handbook_id", "") or "")
            store.set_replication_link(factor_id=fid, cohort_id=info["cohort_id"], handbook_id=hb)
            if fid not in linked_ids:
                linkage.record_linkage(
                    cohort_id=info["cohort_id"], factor_id=fid, handbook_id=hb,
                    definition_hash=def_hash, event="linked", notes="gate_cohort_factors")
    if args.live:
        store.save()   # persist the factor_master replication_cohort_id stamps
        print("claims + governance records + linkage stamps persisted")
    else:
        print("dry-run — re-run with --live to register claims + persist records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
