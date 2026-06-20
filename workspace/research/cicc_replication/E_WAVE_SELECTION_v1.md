# E-wave family-aware selection v1 — protocol + chart-100 reference

> The mandated next step after the E-wave data-ready charts (E1a–E1h): collapse the 69 candidates → ~4-9
> frozen representatives by marginal-contribution, then (a SEPARATE deliberate step) one sealed OOS.
> Per GPT program-review (2026-06-20) + memory `project_e_wave_selection_mandate` +
> `reference_factor_selection_marginal_not_icir`. **No OOS / no 2021+ label is touched in the selection.**

## Chart-100 (价量复合, 图表100) — documented as REFERENCE, not registered

CICC's fixed-equal-weight composite recipe (z-score each component, then weight-combine). The handbook itself
calls it a "参照构造" (reference construction) for *our* Layer-2 composite — i.e. it is the same thing as this
selection, but with fixed equal weights instead of marginal-contribution selection. **It is NOT registered as
a factor** because (a) ~half its components are factors we deliberately DEFERRED, and (b) a marginal-
contribution selection is strictly better than fixed equal weights (the project's `marginal>ICIR` principle).

CICC's representative-factor map per family (the useful INPUT to our selection — what CICC considers
representative) and our buildability:

| family | CICC representatives | our status |
|---|---|---|
| 动量-隔夜 | mmt_overnight_A + mmt_report_overnight | partial (overnight built; report-overnight DEFERRED) |
| 动量-报告期 | mmt_report_jump_open + mmt_report_period | DEFERRED (report-period momentum not built) |
| 动量-年 | mmt_off_limit_A | buildable (off-limit momentum) |
| 反转 | mmt_intraday_M + mmt_range_M | partial (mmt_range DEFERRED) |
| 波动率 | 4× vol_*_std_6M (highlow/up/upshadow/w_downshadow) | ✅ have the family (E1b, 20/60/120d) |
| 流动性-换手 | liq_turn_std_6M | ✅ (E1c) |
| 流动性-弹性 | liq_shortcut_avg_1M + liq_vstd_1M | ✅ (E1c) |
| 资金流-大小单 | buy_shift_dist_l + act_buy_shift_dist_s | partial (buy family DEFERRED = affine alias; act_buy ✅ E1f) |
| 资金流-开盘 | inflow_*_open family | DEFERRED (no intraday split) |
| 北向-占比/变化 | north_hold_prefer/prop + lt/st_chg | DEFERRED (prefer rank-alias) / evidence-only |
| 量价相关 | corr_ret_turnd + corr_price_turn + corr_ret_turn_post | ✅ (E1d) |

**Takeaway:** CICC's composite leans heavily on vol / liquidity / correlation / active-flow — exactly the
families we DID promote to candidate. The deferred components (report momentum, open/close flow, prefer,
buy-alias) are either unbuildable or redundant. So our candidate pool already covers CICC's core composite
intent; the selection just needs to pick the marginal-contributing representatives.

## The candidate pool (frozen for selection)

69 E-wave candidates (E1a 3 + E1b 35 + E1c 19 + E1d 8 + E1f 3) + the pre-existing related candidates the
selection should consider for cross-redundancy (e.g. `rev_up_down_ratio_20d`, existing `liq_*`, `north_*`,
`margin_*`). Evidence-only drafts (E1g 4, E1h 5) are NOT in the selection pool (governance-capped). Deferred
rows are out of scope.

## Selection protocol (EWaveMarginalSelectionProtocol_v1)

```
inputs (IS-ONLY, 2010-2020 univ_all primary; NO 2021+):
  - corrected Layer-1 IS heldout RankICIR + sign-consistency (the matrix)
  - resid_ic_vs_style_controls_v1 (Layer-1 style residual = the SELECTION basis, reference-invariant)
  - factor-factor exposure correlation (Spearman) over the 2010-2020 IS panel
forbidden inputs: any 2021+ label; any post-2020 deployment backtest
rule:
  1. within each family, cluster by exposure corr (|ρ| > ~0.7) + payoff corr
  2. pick ONE representative per cluster by: stability (sign-consistency) + coverage + marginal
     style-residual IC, NOT top raw ICIR
  3. cross-family residualize (greedy: add the next factor with the highest residual IC vs the
     already-selected set; drop if marginal IC < a floor) — the marginal>ICIR principle
  4. family caps: vol ≤2, liquidity ≤2, pv-correlation ≤2, capital-flow ≤2, reversal/momentum ≤1
output:
  EWaveSelectedSet_v1: ~4-9 factor ids + expected directions + a deterministic ranking/weight rule
  + every rejected variant recorded with reason
then (SEPARATE deliberate step, not in this protocol):
  FrozenSelectionSet over the selected set → ONE 2021+ sealed OOS → deployment gate
```

## Next concrete step

Build the **family map + factor-factor exposure correlation** over the 2010-2020 IS panel (compute the 69
candidates, Spearman exposure corr, cluster within/across families), then run the greedy marginal-
style-residual-IC selection under the family caps → `EWaveSelectedSet_v1` (frozen, pre-OOS).

## RESULT: EWaveSelectedSet_v1 (2026-06-20) — 69 → 9 frozen representatives

Greedy marginal selection complete (IS-only, no 2021+). Family map: within-family redundancy high (vol mean
|corr| 0.75, liq 0.41, flow 0.50); cross-family low (all ≤0.26 → 5 orthogonal families). The 9 reps:

| family | factor | style_resid_ic | dir |
|---|---|---|---|
| corr | corr_ret_turnd_20d | −0.782 | inverse |
| vol | vol_highlow_std_20d | −0.570 | inverse |
| liq | liq_vstd_20d | −0.557 | inverse |
| liq | liq_shortcut_avg_20d | +0.528 | positive |
| corr | corr_price_turn_post_20d | −0.517 | inverse |
| vol | vol_up_std_20d | −0.498 | inverse |
| flow | flow_act_buy_shift_dist_xl_20d | −0.492 | inverse |
| mom | mmt_route_20d | −0.354 | inverse |
| flow | flow_act_buy_prop_l_20d | +0.226 | positive |

7 inverse (low-vol / illiquidity-turnover / 量价背离 / reversal / xl-distribution) + 2 positive (illiquidity-
shortcut premium, large-order accumulation). Provenance: `EWaveSelectedSet_v1.json`. **NEXT (separate
deliberate step — single sealed-OOS spend):** build the `FrozenSelectionSet` over these 9 → ONE 2021+ sealed
OOS → deployment gate. The OOS is single-shot/permanently-spent — do NOT run it without an explicit decision.
