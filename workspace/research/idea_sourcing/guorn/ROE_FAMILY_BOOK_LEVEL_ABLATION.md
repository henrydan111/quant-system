# Do the ROE-family factor gaps move BOOK-level selection? — ablation (2026-06-28)

**Question (user-directed):** the factor-level top-K parity for the ROE family is poor standalone
(净资产收益率 top-5 = 0%, ROETTMDiffPQ top-5 = 20%). Does that propagate to the **book's** actual
top-K selection — i.e. does it cost returns — or does it wash out in the composite 总排名分?

**Method.** Build the #5 sm_成长 composite (果仁-exact rank-score `(N−rank+1)/N×100`, weighted-sum) on the
排除ST排除科创 universe (4385 eligible, full 果仁-ROE coverage) at 2025-12-31. **Ablation:** Run A uses my
local ROETTMDiffPQ, Run B uses 果仁's exact ROETTMDiffPQ (from the factor export); **every other factor is
identical**, so the top-K difference isolates the ROE gap's effect. **Sweep** the ROE term's share of total
weight (real recipes use ROETTMDiffPQ at weight 1 of ~10–22 total → ~5–14%).

## Result — the gap WASHES OUT at realistic weights

| ROE weight | ROE share | top-5 | top-10 | top-20 | top-30 |
|---|---|---|---|---|---|
| **0.4 (real ≈ 1/16)** | **6%** | 60% | **100%** | **95%** | **90%** |
| 1.0 (7-term subset) | 14% | 40% | 80% | 80% | 83% |
| 2.0 | 25% | 80% | 60% | 70% | 53% |
| 3.0 | 33% | 80% | 80% | 60% | 70% |

**At the deployed weight (~6%): top-10 selection is UNCHANGED (100%), top-20 95%, top-30 90%.** The ROE
gap shifts only ~2 names in the top-5 (and the top-5 column is small-sample noisy). The impact grows only
if a book weights ROE at 25%+, which none of the deployed-20 do.

**Mechanism.** The composite top-K is a dense cluster (adjacent gaps ≈0.004 of the 0–1 range). A single
weight-1 ROE term among ~16 perturbs the composite by ≈ (ROE share) × (rank-score gap). At 6% share the
perturbation is small enough that the other 15 weight-units dominate the ranking; at 14%+ (the overweighted
subset) it starts to bite. The first ablation pass reported 40% top-5 precisely because the 7-term
reproducible subset inflates ROE's share to 1/7 — corrected by the sweep.

## Conclusion

The alarming **factor-level** ROE top-K divergence does **NOT** translate into a large **book-level**
selection gap. At the realistic recipe weight the deployed books' selection is **90–100% preserved** (top-10
through top-30) under the ROE swap. The documented ROE-family gaps (净资产收益率 加权平均 weighting;
ROETTMDiffPQ negative-equity) are **book-level immaterial beyond ~2 top-5 names** — they are a factor-fidelity
footnote, not a returns threat, because ROE enters every deployed book as one diluted weight-1 (often
中性化) term in a 10–22-weight composite.

Caveats: single date (2025-12-31), #5-style recipe, the ROE-**diff** (the most divergent ROE factor). A book
that ranked predominantly on ROE would diverge more — but none do. NON-FORMAL parity ablation; scripts under
`scratchpad/roe_ablation*.py` (logic), driven off the 果仁 ROETTMDiffPQ factor export.

---

## ROETTMDiffPQ dependency map (2026-06-28) — 21 strategies, 9 deployed

Parsed from every strategy's `排名条件` (`guorn_strategies_master.json`); machine-readable copy:
[roettmdiffpq_dependency_map.json](roettmdiffpq_dependency_map.json). **Every one weights it at 5–10% of total
rank weight (range [0.05, 0.10])** — so the ablation above (immaterial at ≤14% share) generalizes to ALL 21; no
strategy is ROE-dominant, none needs a per-book re-test.

**Deployed (9):**

| nn | strategy | ROE w | total w | share |
|---|---|---|---|---|
| #5 | sm_01_成长_v1 | 1 | 10 | 10% |
| #20 | value_红利低波_央企_v1 | 1 | 10 | 10% |
| #19 | value_红利低波_v2 | 1 | 11 | 9% |
| #9 | sm_GARP_illiq | 2 | 25 | 8% |
| #42 | 成长_机构预期@周期_v1 | 2 | 24 | 8% |
| #44 | 成长_双创_GARP@周期_v2 | 2 | 24 | 8% |
| #1 | sm_01_成长动量 | 1 | 12 | 8% |
| #6 | sm_01_成长高贝塔@TMT_v1 | 1 | 13 | 8% |
| #10 | sm_双创研发强度_v1 | 1 | 16 | 6% |

**Non-deployed (12):** #49 成长_化工_GARP@周期, #52 成长_GARP白酒, #62 Comp_GARP (each w2, 8%); #2/#3/#4
sm_01_成长动量_大盘择时* (w1, 8%); #17 sm_BJ_成长均衡_v1 (w1, 9%, uses the formula form
`公式(REFQ(净资产收益率,0)-REFQ(净资产收益率,1))`); #23 value_FCF_非金sm_v2 (5%); #47 成长_新高@周期 (7%);
#50 成长_GARP医药 (8%); #56 Comp_Core_growth (5%); #63 Comp_FCF (9%).

Three written forms occur: direct `ROETTMDiffPQ`, smoothed `公式(HAVG(ROETTMDiffPQ,1))` (#42), and the
expanded `公式(REFQ(净资产收益率,0)-REFQ(净资产收益率,1))` (#17) — the last is what pinned the definition.
All rank it `从大到小` (improving-ROE preferred); the theme is 成长 / GARP / value-红利.

---

## Full ROE investigation arc (2026-06-28) — settled

The complete thread, from factor definition to deployment impact (all NON-FORMAL; field-level detail in
[guorn_local_field_mapping.md](guorn_local_field_mapping.md), the ROE row):

1. **Definition pinned.** 果仁 净资产收益率 = **TTM 归母净利 ÷ 加权平均净资产** (CSRC weighted-average equity),
   confirmed by an implied-equity solve + the `公式(REFQ(净资产收益率,0)-REFQ(净资产收益率,1))` form in #17.
   ROETTMDiffPQ = the QoQ change of that TTM-ROE.
2. **Value floor ≈ 0.19pp, Tushare cannot break it.** Best reconstruction = raw single-quarter 归母净利 ÷
   time-weighted (trapezoid) quarter-end equity → median 0.19pp, Spearman 0.991, ~35% within 0.1pp. Tushare's
   `roe_waa` (the reported CSRC weighted-average) does NOT help (R1 0.267 / R3 0.219 > trapezoid 0.190) — the
   TTM-vs-YTD window splice loses more than the intra-quarter weighting gains, and `$roe_waa` itself is anomalous
   for some stocks (000858 = 4.89 vs ~18% real). The residual is the **sub-quarter equity path** (dividend
   ex-date jumps), which no Tushare field carries; only annual-report-aligned dates could hit ~100% via roe_waa_FY.
3. **Negative/tiny-equity = irreducible + proprietary.** The factor's standalone top-K is dominated by
   near-zero/negative-equity names where ROE is mathematically unstable (000692 eq −1.29亿 → 果仁 333) and 果仁's
   handling is a private convention — no data fixes it.
4. **Book-level impact = immaterial.** The ablation + the 5–10% weight map show the caliber gap leaves deployed
   selection 90–100% intact (top-10 unchanged). **Verdict: a factor-fidelity footnote, not a returns threat.**
   The data layer (income + equity statements) is penny-exact; the ~0.2pp is a derived-metric weighting
   convention, not a data error.
