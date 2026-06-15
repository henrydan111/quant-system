# eps_diffusion re-approval — GPT 5.5 Pro cross-review brief

**Verdict requested:** APPROVE the re-approval (reverse 2026-06-14 revoke) / CHANGES REQUIRED / REJECT.
**Reviewed commit:** `b5d70a0` on `report-rc-registration`. **Repo:** https://github.com/henrydan111/quant-system

⚠ This is a **load-bearing reversal of a recent revoke** based on my OWN admitted self-correction.
Please review skeptically — I am asking you to validate a decision I have a self-interested motive to
get right but also a self-interested motive to confirm. Discount accordingly; refute if the evidence
doesn't actually support reversal.

## Timeline (short)

- **2026-06-09** — both `earn_eps_diffusion_60/_120` approved via single-shot sealed OOS (canary OVERRIDDEN);
  per-factor metrics: `_60` RankICIR_20d **+0.131** / LS_5d **7.24**; `_120` **+0.070** / **2.59**. FrozenSelectionSet `c5335681…` SPENT.
- **2026-06-14** — breadth-restatement canary ran. The canary's "0 backfilled + 0 drift" literal bar failed
  (138 backfilled + 0 drift + 26 restatement). 138 backfilled are handled by the provider's create_time+2td
  anchor; 26 restatements include 0 material EPS changes (>1e-4) — i.e. breadth IS restatement-stable.
  Despite that, the revoke fired because of an unexplained "too-good LS Sharpe 7.24" residual concern.
  Both factors **revoked approved→candidate**.
- **2026-06-15** — re-evaluation per the user's directive ("try to reach approved again"). Three layers.

## The three diagnostic layers

**(1)** `eps_diffusion_lssharpe_decomposition.py` — splits the SPENT OOS at the 2022-05 data-trust boundary:
| factor | deep 2021-01..2022-04 (~16mo, backfilled) | full 2021-2026 | clean 2022-05+ (~44mo, real per-row) |
|---|---|---|---|
| `_60` ICIR_20d / LS_5d | **0.36 / 8.65** | 0.13 / 7.24 | **0.041 / 1.36** |
| `_120` ICIR_20d / LS_5d | **0.31 / 3.58** | 0.07 / 2.59 | **−0.023 / −0.51** |

**(2)** `eps_diffusion_pit_attribution.py` — extra-lag stress (k EXTRA td on every `Ref($report_rc__*, 1)`):
- Clean 2022-05+: `_60` ICIR 0.041@+0 → 0.033@+2 → 0.020@+5 → **0.005@+10td** (decays). `_120` ≤ 0 throughout.
- Deep 2021-01..2022-04: `_60` 0.36@+0 → **0.37@+5td**. `_120` 0.31 → 0.32.

**I initially read the deep window's lag-invariance as a Tushare backfill vintage artifact** (values not as-of)
and recommended both stay candidate. ⚠ This is the inference under review.

**(3)** `workspace/research/data_expansion/jq_eps_diffusion_benchmark.py` — the user requested an
independent JoinQuant **genuinely-PIT** benchmark to discriminate artifact vs decay. JQ 朝阳永续's
`predicted_earnings_to_price_ratio` is the VALIDATED PIT consensus FY1 EP series (`get_factor_values(end_date=asof)`
returns what was known AS OF that date). Methodology:
- Monthly as-of grid: PRE 2014–2021 (n=87 month-ends), POST 2022-05..2026-02 (n=44).
- Survivorship-correct universes via `get_all_securities(types=['stock'], date=asof)` (includes future-delisted).
- Reconstruct consensus FY1 EPS = `EP × RAW close` (RAW so the price JQ used in E/P cancels exactly; adj close would inject a split/div artifact).
- 2-month (~60d) / 4-month (~120d) consensus-EPS revision as the breadth proxy (`eps_t / eps_{t-N} − 1`).
- RankIC vs 5/10/20d adjusted forward returns; report mean_rank_ic, RankICIR.

**Result CSV:** [data/external/jq_eps_diffusion_benchmark.csv](https://github.com/henrydan111/quant-system/blob/b5d70a0/data/external/jq_eps_diffusion_benchmark.csv)

Side-by-side at the 20d horizon:
| signal / window | Tushare (per-analyst breadth) | **JQ-PIT (consensus-EP revision)** |
|---|---|---|
| `_60` PRE-2022 ICIR_20d | 0.36 (deep) | **0.34** |
| `_120` PRE-2022 ICIR_20d | 0.31 (deep) | **0.26** |
| `_60` POST 2022-05+ ICIR_20d | 0.041 | **0.042** |
| `_120` POST 2022-05+ ICIR_20d | −0.023 | **−0.077** |

## My corrected interpretation

Two **independent** PIT sources (Tushare report_rc per-analyst counts vs JQ 朝阳永续 consensus-EP level),
two **different** signal constructions (`#up − #down` vs consensus-revision), agreeing on IC magnitude
within ~0.05 ICIR in **both** windows. The probability of coincidental match is ~zero.

The pre-2022 strength is REAL economic signal (analyst-sentiment-shift regime 2018–2021); the post-2022
weakness is REAL decay/regime. My lag-invariance argument was wrong: a 60–120d rolling breadth on
slow-moving consensus is **inherently lag-insensitive at small +td shifts**, whether values are
first-state or end-state. The test cannot discriminate; JQ-PIT discriminates and says "real."

The original 2026-06-09 sealed-OOS pass was on REAL data: ~16mo strong (~0.34 PIT-confirmed) + ~44mo
decay (~0.04 PIT-confirmed) blended to 0.131/7.24. The 2026-06-14 revoke was based on my wrong
attribution. **Reversing it restores truth.**

## What I am recommending

`factor_registry.set_status('approved')` on both, with **decay context stamped into the approval reason**
(the factor is real-but-decaying alpha — common, valid, but the deployment side is uninvestable as a
standalone long-only top-K — separate gate, unchanged). Side effect: restores 9-approved → restores
the methodology hash the E1a matrix run was built under → unblocks task #34 (matrix drift auto-resolves).

## Verification points — please challenge each

**Q1 — JoinQuant predicted_earnings_to_price_ratio is genuinely PIT?**
Prior validation (REPORT_RC_PIT_ANCHOR_VALIDATION.md): level corr +0.997 / per-date Spearman +0.94 vs
the Tushare report_date+1 anchor over 2014–2021; documented as JQ 朝阳永续 PIT. Cross-section sizes
1800–2400/month (PRE) and 2500–3100/month (POST) (CELL 3 output). Is this sufficient for "genuinely PIT"?

**Q2 — EP × raw close → EPS reconstruction validity.**
JQ computes `predicted_earnings_to_price_ratio = consensus_FY1_EPS / price` using a specific price
basis (assumed raw close on the as-of date). My CELL 4 fetches `fq=None` close on the same as-of date.
If JQ uses a different price (e.g. divisor-adjusted), the EPS reconstruction carries a residual error.
Does the magnitude match (PRE ICIR 0.34 ≈ Tushare 0.36; POST 0.042 ≈ Tushare 0.041) rule out a material
price-basis mismatch? Or is there a price-basis check I should add?

**Q3 — Consensus-revision proxy vs per-analyst breadth.**
JQ exposes consensus level, not per-analyst breadth. My proxy is `eps_t / eps_{t-N} − 1` over 2/4 months.
The Tushare factor is `(#up − #down) / N_revisions` over 60/120 trading days. Same economic content
(direction of analyst sentiment shift) but different scales and noise structures. Is the cross-source
IC match a fair confirmation, or do you want a different decisive test before reversal?

**Q4 — Pre-registered interpretation honesty.**
The notebook docstring committed before running the JQ test states: "JQ-PIT pre-2022 RankIC strong
(~0.03-0.06 mean, ICIR ~0.3-0.4) ⇒ pre-2022 signal REAL → Tushare-artifact verdict OVERTURNED."
Observed: PRE mean_rank_ic 0.024 / ICIR 0.34. That is **at the lower edge** of the pre-registered
"strong" band on `mean_rank_ic` (0.024 < 0.03) but **squarely in the band** on ICIR (0.34 ∈ [0.3, 0.4]).
Is this a clean pre-registered pass, or marginal enough to demand a second test?

**Q5 — Lag-invariance failure mode (the technical point).**
My claim: at lag +5td on a 60d rolling sum of small daily revision flows, the displaced 5 days at each
end are small fractions of the window, AND the per-day flow distribution is statistically similar at
both ends of the window (slow-moving consensus drift) — so the rolling-sum is nearly invariant whether
values are first-state or end-state. Therefore lag-invariance ≠ vintage artifact for slow-moving
signals. Is this reasoning correct? Is there a sharper PIT discriminator I should have used in the
first place?

**Q6 — Decay-vs-artifact: is the post-2022 weakness genuine decay or noise?**
n=44 month-ends in POST. JQ shows _60 ICIR 0.042 (consistent with decay from 0.34); _120 −0.077
(sign-flipped). With t-stat ≈ ICIR × √n / √12 ≈ 0.042×√44/√12 ≈ 0.08 for _60 monthly, statistically
indistinguishable from zero, but the magnitudes match Tushare exactly. Is the conclusion "real decay
to near-zero" sound, or could POST be a small-sample artifact masking a residual real signal?

**Q7 — Should the registry mutation proceed at all?**
The factor was approved on a CANARY-OVERRIDDEN OOS spend (the 2026-06-15 breadth-restatement canary
was the contingency). The canary literally fired (`SNAP1→SNAP2` 138+26 restatements > "0"). The
revoke followed the contingency rule. Reversing it requires NOT just "the metrics are real" but also
"the canary contingency was wrongly worded." Is the reversal procedurally sound, or does the canary
contingency-rule force "stays candidate, document the decay, do NOT mutate the registry"?

**Q8 — Deployment caveat language for the approval reason.**
The deployment gate (`build/eval_eps_diffusion_deployment.py`) showed +4.5–9.8% net/liquid CAGR with
−62 to −65% MDD — uninvestable. Should the approval reason explicitly include the deployment caveat
(prevents future allocators extrapolating from the headline LS 7.24), or is "approved factor ≠
deployable strategy" already standing convention adequate?

## Requested verdict format

Per Q1–Q8: OK / CHANGES REQUIRED (+ exact fix). Overall: APPROVE re-approval / CHANGES REQUIRED /
REJECT (+ procedural alternative). If REJECT, please be explicit about what evidence WOULD justify
reversing the revoke given the OOS is permanently spent.
