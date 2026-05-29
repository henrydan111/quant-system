# Archived — PIT-lookahead legacy scripts (2026-05-29 sandbox loaders; 2026-05-30 JQ deploy mimics)

The **73** scripts listed below are the **INVALIDATED** research lineage
that produced the v31/v32/v33 + val_heavy "champions". They used a hand-rolled
`build_pit_pivot` loader that lexically compared dashed `effective_date`
("2018-10-30") against compact `trade_date` ("20180607"), injecting up to
~9 months of earnings lookahead. Full postmortem:
`workspace/research/jq_deployment/v33_PIT_lookahead_bug_report.md`.

**Status: FROZEN — DO NOT USE / DO NOT UN-ARCHIVE.** The corrected (PIT-safe)
performance of this lineage fails every gate (champion OOS 188.7%->2.0%;
val_heavy +81.9%->+9.6% with negative walk-forward). The sanctioned replacement
is `src/data_infra/pit_research_loader.py`; the migrated proof is
`workspace/scripts/val_heavy_loader_proof.py`.

## These scripts are intentionally NOT committed
They were never on public `main` (untracked local exploration). Committing
73 superseded buggy scripts would bloat the repo for no benefit. They
are kept locally (untracked) under this directory for recoverability. **This
README is the tracked manifest** — the version-controlled record of what was
archived, even though the dead code itself is not in git.

## Containment (committed enforcement)
The committed mechanism is: **tracked manifest (this file) + gitignored local
archive + root-specific lint skip + a live-reference architecture test** (NOT an
"exact-path allowlist" — the dead scripts are not committed, so there is nothing
to allowlist).
- `.gitignore` ignores `workspace/scripts/archive/pit_lookahead_legacy_2026_05/*.py`
  (this README stays tracked) so the dead lineage cannot be accidentally `git add`ed back.
- `scripts/lint_no_unsafe_pit_dates.py` skips the **sanctioned archive roots only**
  (`ARCHIVE_SKIP_ROOTS`, root-specific — a generic `archive/` dir elsewhere is still
  linted): these scripts still contain raw `pit_ledger` reads and would otherwise trip PIT002.
- `tests/architecture/test_dormant_module_boundaries.py::
  test_pit_lookahead_legacy_archive_not_referenced_by_live_code` enforces that no
  live `src/` or `workspace/` code imports `sandbox_v*` (incl. dotted/dynamic forms)
  or path-references this archive directory.

## Manifest (73 files)
- `sandbox_v10_breadth.py`
- `sandbox_v11_stock_ma.py`
- `sandbox_v12_voltarget.py`
- `sandbox_v13_fullmkt.py`
- `sandbox_v14_industry.py`
- `sandbox_v15_earnings_mom.py`
- `sandbox_v15aa_advanced_sizing.py`
- `sandbox_v15aa_diag.py`
- `sandbox_v15aa_diag2.py`
- `sandbox_v15aa_v10_deploy_val.py`
- `sandbox_v15aa_v11_expanded.py`
- `sandbox_v15aa_v12_trend_sector.py`
- `sandbox_v15aa_v13_alt_strategies.py`
- `sandbox_v15aa_v14_ey_roe.py`
- `sandbox_v15aa_v14b_3factor_val.py`
- `sandbox_v15aa_v15_k5_validation.py`
- `sandbox_v15aa_v16_4factor_val.py`
- `sandbox_v15aa_v17_5factor_ext.py`
- `sandbox_v15aa_v18_momentum_quality.py`
- `sandbox_v15aa_v19_5factor_rev_growth.py`
- `sandbox_v15aa_v20_6factor_exploration.py`
- `sandbox_v15aa_v21_rebal_derived.py`
- `sandbox_v15aa_v22_7f_reb15.py`
- `sandbox_v15aa_v23_oos_optimized_dir.py`
- `sandbox_v15aa_v24_dupont_factors.py`
- `sandbox_v15aa_v25_market_factors.py`
- `sandbox_v15aa_v26_pit_extensions.py`
- `sandbox_v15aa_v27_depth_exploration.py`
- `sandbox_v15aa_v28_qdtroe_exploration.py`
- `sandbox_v15aa_v29_portconstruct_roewaa.py`
- `sandbox_v15aa_v3.py`
- `sandbox_v15aa_v30_lgbm_and_dirichlet_validation.py`
- `sandbox_v15aa_v31_focuspct_confirmation.py`
- `sandbox_v15aa_v32_open_execution.py`
- `sandbox_v15aa_v33_event_driven.py`
- `sandbox_v15aa_v4.py`
- `sandbox_v15aa_v5.py`
- `sandbox_v15aa_v6_roa.py`
- `sandbox_v15aa_v7_combined.py`
- `sandbox_v15aa_v8_robust.py`
- `sandbox_v15aa_v9_final.py`
- `sandbox_v15b_earnings_timing.py`
- `sandbox_v15c_voltgt_finetune.py`
- `sandbox_v15d_nolev_verify.py`
- `sandbox_v15e_robustness.py`
- `sandbox_v15f_definitive.py`
- `sandbox_v15g_rebal_robustness.py`
- `sandbox_v15h2_weight_fine_grid.py`
- `sandbox_v15h_weight_robustness.py`
- `sandbox_v15i_universe_robustness.py`
- `sandbox_v15j_combined_defensive.py`
- `sandbox_v15k_deploy_readiness.py`
- `sandbox_v15l_factor_expansion.py`
- `sandbox_v15m_new_signal_robustness.py`
- `sandbox_v15n_dt_qoq_optimize.py`
- `sandbox_v15o_val_heavy_confirm.py`
- `sandbox_v15p_deep_validation.py`
- `sandbox_v15q_cost_regime.py`
- `sandbox_v15r_factor_expansion.py`
- `sandbox_v15s_sector_diversification.py`
- `sandbox_v15t_market_cap_segments.py`
- `sandbox_v15u_lgbm_signal.py`
- `sandbox_v15v_rebal_sizing.py`
- `sandbox_v15w_top2_focus_deep.py`
- `sandbox_v15x_momentum_overlay.py`
- `sandbox_v15y_regime_filter.py`
- `sandbox_v15z_alt_indicators.py`
- `sandbox_v7_ls.py`
- `sandbox_v7_refine.py`
- `sandbox_v8_lo.py`
- `sandbox_v8_lo_v2.py`
- `sandbox_v9_ml.py`
- `v33_factor_alignment_dump.py`

## JoinQuant deployment mimics (6 files, added 2026-05-30)

A distinct category from the 73 sandbox loaders above: these are JoinQuant
**deployment** scripts (`from jqdata import *`, `get_fundamentals`) — the
deploy-side end products of the same invalidated effort. They do **not** contain
raw `pit_ledger` reads (they consume JoinQuant's own PIT `get_fundamentals`), but
every performance figure in their headers was lifted from the contaminated
pre-2026-05-29 sandbox and is therefore **inflated by the lookahead bug**. None
were ever committed; they were loose in `workspace/scripts/` and archived here on
2026-05-30.

**Status: FROZEN — DO NOT DEPLOY.** Each is a near-deployment artifact of a
"champion" whose numbers do not survive PIT-correct measurement (claimed figures
are all from `sandbox simulation 2014-2026-02-27`):
- `jq_deploy_earnings_momentum_v1.py` — PIT Earnings Momentum, 3-factor baseline (claimed CAGR +65.6%, WF +68.7%)
- `jq_deploy_earnings_momentum_v2.py` — **val_heavy** 5-factor (claimed CAGR +81.9%, WF +82.4%; true PIT ≈ +9.6% with negative walk-forward — the exact strategy this prevention plan exists to catch)
- `jq_11f_roewaa_strategy.py` — 11-factor roe_waa value-growth (claimed IS 283.7%, OOS 192.7%)
- `jq_deploy_roa_quality_v3.py` — ROA-quality v15aa series (claimed BEST_B CAGR 133.6%, OOS 102.8%)
- `jq_deploy_roa_quality_v4.py` — 4-factor ROA+q_roe (claimed 4F_K5 CAGR 143.5%, OOS 120.0%)
- `jq_deploy_roa_quality_v5.py` — 6-factor ROA-quality (claimed CAGR 179.3%, OOS 137.1%)

Containment is identical to the sandbox section: `.gitignore` line 102 ignores
`*.py` here (this README stays tracked), the PIT lint skips this sanctioned root,
and `test_dormant_module_boundaries.py` forbids live code referencing the archive.
