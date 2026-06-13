# SCRIPT_STATUS: ACTIVE — D-COMP/D4a canary: first CICC factor through the ceiling-wired gate
"""P-GATE first canary (roadmap Rev5 item 3): take the one cleanly-constructible CICC
fundamental composite — Profit (综合盈利 = CFOA + ROE + ROIC 等权, handbook §11) — through
the now-ceiling-wired factor_lifecycle governance:

  1. sync_catalog -> comp_cicc_profit registered as `draft`;
  2. register a univ_all FactorDomainClaim;
  3. adjudicate the replication status ceiling via the SAME `_cohort_ceiling` the live
     publish gate uses (manifest tier + oos_eligibility / matrix coverage / claim class);
  4. persist a ReplicationGovernanceRecord (evidence-only — gate-readable ceiling).

This validates the P-GATE governance pipeline end-to-end on a FRESH factor. It does NOT
promote anything to candidate — that is the human-gated orchestrator step. The expected,
honest result is candidate_ceiling (short_oos_power_floor_fail): Profit's members were
truth-observed across 2010-2022, so even a clean composite is not auto-approvable.

Dry-run by default (temp copy); --live commits the draft + claim + governance record.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from src.alpha_research.factor_registry import FactorRegistryStore  # noqa: E402
from src.alpha_research.factor_registry.domain_claims import DomainClaimStore  # noqa: E402
from src.alpha_research.factor_registry.replication_governance import (  # noqa: E402
    ReplicationGovernanceStore,
)
from src.research_orchestrator.factor_lifecycle_steps import (  # noqa: E402
    _cohort_ceiling,
    _load_cohort_manifests,
)

FACTOR_ID = "comp_cicc_profit"
UNIVERSE = "univ_all"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="commit to the REAL registry (default: dry-run copy)")
    args = ap.parse_args()

    if args.live:
        reg_dir = PROJECT_ROOT / "data" / "factor_registry"
    else:
        tmp = Path(tempfile.mkdtemp(prefix="canary_profit_"))
        shutil.copytree(PROJECT_ROOT / "data" / "factor_registry", tmp / "factor_registry")
        reg_dir = tmp / "factor_registry"
        print(f"dry-run registry copy: {reg_dir}")

    # 1. register the composite as draft (sync_catalog is idempotent)
    store = FactorRegistryStore(reg_dir)
    before = store.factor_master["factor_id"].nunique() if len(store.factor_master) else 0
    store.sync_catalog(record_run=bool(args.live))
    if args.live:
        store.save()
    cur = store.factor_master[store.factor_master["is_current"].fillna(False)]  # noqa: E712
    row = cur[cur["factor_id"] == FACTOR_ID]
    status = str(row.iloc[0]["status"]) if len(row) else "(NOT REGISTERED)"
    print(f"1. sync_catalog: {FACTOR_ID} status={status} "
          f"(unique factors {before} -> {store.factor_master['factor_id'].nunique()})")

    # 2. register a univ_all domain claim
    claims = DomainClaimStore(reg_dir)
    existing = claims.claims()
    have = len(existing[(existing["factor_id"] == FACTOR_ID) & (existing["universe_id"] == UNIVERSE)
                        & (existing["status"] != "rejected_claim")]) if len(existing) else 0
    if have:
        print(f"2. domain claim: already exists for ({FACTOR_ID}, {UNIVERSE})")
    elif args.live:
        cid = claims.register_claim(factor_id=FACTOR_ID, universe_id=UNIVERSE,
                                    hypothesis_id="cicc_profit_canary", declared_domain_count=1)
        print(f"2. domain claim: registered {cid}")
    else:
        print(f"2. domain claim: would register ({FACTOR_ID}, {UNIVERSE}) [dry-run]")

    # 3. adjudicate the ceiling via the SAME helper the wired publish gate uses
    manifests = _load_cohort_manifests()
    _cur = store.factor_master[store.factor_master["is_current"].fillna(False)]  # noqa: E712
    _dh = _cur[_cur["factor_id"] == FACTOR_ID]
    cur_def_hash = str(_dh.iloc[0]["definition_hash"]) if len(_dh) else ""
    info = _cohort_ceiling(FACTOR_ID, UNIVERSE, manifests=manifests,
                           evidence_df=store.factor_evidence, claim_store=claims,
                           current_definition_hash=cur_def_hash)
    if info is None:
        print("3. adjudication: NOT a cohort factor (manifest linkage missing) — check catalog_factor_id")
        return 1
    dec = info["decision"]
    print(f"3. adjudicated ceiling: {dec.status_ceiling}")
    print(f"   blocking_reasons: {dec.blocking_reasons}")
    print(f"   active_cap_reasons: {dec.active_cap_reasons}")
    print(f"   oos_eligible_gates_met: {dec.oos_eligible_gates_met}")
    print(f"   cohort: {info['cohort_id']} | tier: {info['row'].replication_tier_planned}")

    # 4. persist the ReplicationGovernanceRecord (evidence-only; gate-readable ceiling)
    if args.live:
        gov = ReplicationGovernanceStore(reg_dir)
        rec = gov.upsert(
            cohort_id=info["cohort_id"], factor_id=FACTOR_ID,
            factor_domain_claim_id=info["claim_id"] or f"{FACTOR_ID}:{UNIVERSE}",
            replication_tier=info["row"].replication_tier_planned,
            active_cap_reasons=dec.active_cap_reasons,
            oos_eligible_gates_met=dec.oos_eligible_gates_met,
            cohort_denominator_membership=["formalization_candidate"],
            truth_label_end=info["row"].truth_table_label_end,
            notes="D-COMP canary: comp_cicc_profit (CFOA+ROE+ROIC) first CICC composite",
        )
        print(f"4. governance record persisted: status_ceiling={rec.status_ceiling}")
    else:
        print("4. governance record: would persist [dry-run]")
        print("dry-run complete — real registry untouched. Re-run with --live to commit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
