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
