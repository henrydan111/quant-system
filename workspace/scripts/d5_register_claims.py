# SCRIPT_STATUS: ACTIVE — D5: domain claims + taint entries for the CICC replication cohort
"""D5 step 2: create FactorDomainClaims for the 18 CICC-replication factors — the FIRST
cohort through the universe plan Draft-7 pipeline — with HONEST taint accounting.

Every factor's 2010-2022 IS performance on univ_all / univ_csi300 / univ_csi500 was
observed in the Phase-D truth-comparison batch (workspace/outputs/cicc_fundamental_batch/)
BEFORE registration. Per Draft-7 §3.3 the claims on those domains are therefore
``tainted_post_hoc_max_stat`` — recorded mechanically via exploratory_eval taint entries
predating the claims. The other 4 domains (csi1000/microcap/growth/liquid_top300) were
NOT evaluated in the batch → claims there stay clean until the F2 matrix runs.

component_selection_basis = external_prior (the published CICC handbook predates all of
our work and is domain/direction/horizon-specific) — but informed_by is non-empty (our
replication runs), so per R2-B2 the prior may EXPLAIN, never reset to clean. We do NOT
override; the post-hoc class stands.
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from src.alpha_research.factor_registry.domain_claims import DomainClaimStore  # noqa: E402

FACTORS = {
    # catalog id -> (CICC code, research family)
    "qual_cfoa_ttm": ("CFOA", "fam_cicc_profit_level"),
    "qual_roa_ttm": ("ROA_TTM", "fam_cicc_profit_level"),
    "qual_npm_ttm": ("NPM_TTM", "fam_cicc_profit_level"),
    "qual_at_ttm": ("AT", "fam_cicc_oper_turnover"),
    "qual_invt_ttm": ("INVT", "fam_cicc_oper_turnover"),
    "qual_rat_ttm": ("RAT", "fam_cicc_oper_turnover"),
    "qual_gpmd_ttm": ("GPMD", "fam_cicc_margin_delta"),
    "qual_csr": ("CSR", "fam_cicc_liquidity_safety"),
    "qual_ccr_ttm": ("CCR", "fam_cicc_liquidity_safety"),
    "grow_ni_attr_q_yoy": ("NP_Q_YOY", "fam_cicc_sq_growth"),
    "grow_ni_q_qoq": ("NP_QOQ", "fam_cicc_sq_growth"),
    "grow_op_q_yoy": ("OP_Q_YOY", "fam_cicc_sq_growth"),
    "grow_or_q_yoy": ("OR_Q_YOY", "fam_cicc_sq_growth"),
    "grow_total_assets_yoy": ("TA_YOY", "fam_cicc_sq_growth"),
    "val_ep_ttm_pit": ("EP_TTM", "fam_cicc_value_pit_ttm"),
    "val_ocfp_ttm_pit": ("OCFP_TTM", "fam_cicc_value_pit_ttm"),
    "val_fcfp_ttm": ("FCFP_TTM", "fam_cicc_value_pit_ttm"),
    "size_float_ratio": ("FC_MC", "fam_cicc_size_structure"),
}
OBSERVED_DOMAINS = ("univ_all", "univ_csi300", "univ_csi500")
BATCH_EVIDENCE = "workspace/outputs/cicc_fundamental_batch/batch_verdicts.json"


def main() -> int:
    store = DomainClaimStore()
    n_taints = n_claims = 0
    for fid, (cicc, family) in FACTORS.items():
        for univ in OBSERVED_DOMAINS:
            store.record_taint(
                source_type="exploratory_eval", factor_id=fid,
                research_family_id=family, universe_id=univ,
                source_id="cicc_fundamental_batch_20260611",
                evidence_ids=[f"{BATCH_EVIDENCE}#{cicc}@{univ}"],
                taint_effect="post_hoc_max_stat",
            )
            n_taints += 1
        cid = store.register_claim(
            factor_id=fid, universe_id="univ_all",
            research_family_id=family,
            hypothesis_id=f"cicc_replication_{cicc}",
            notes=(f"CICC {cicc} replication; truth-certified construction "
                   "(PHASE_D_ROUND1_REPORT). external_prior = published handbook, but "
                   "informed_by replication runs => post-hoc class stands (no override)."),
        )
        n_claims += 1
        cls = store.claims().set_index("claim_id").loc[cid, "claim_class"]
        print(f"{fid:24s} {cicc:10s} claim={cid} class={cls}")
    print(f"\n{n_claims} claims, {n_taints} taint entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
