# JoinQuant genuine-PIT eps_diffusion benchmark — results

**Purpose.** Independent genuine-PIT benchmark to discriminate between two competing attributions of
`earn_eps_diffusion_60/_120`'s pre-2022 strength: Tushare report_rc backfill vintage artifact vs
real economic signal (with post-2022 decay/regime change). The user requested this benchmark on
2026-06-15 explicitly to settle the artifact-vs-decay question (memory: `project_idea_sourcing_pipeline`).

**Method (notebook).** [jq_eps_diffusion_benchmark.py](jq_eps_diffusion_benchmark.py) — run in
JoinQuant 云端研究环境 (Python 3 kernel). Monthly as-of grid, survivorship-correct universes via
`get_all_securities(date=asof)`, validated PIT consensus FY1 EP series
`predicted_earnings_to_price_ratio` (`jqfactor.get_factor_values(..., end_date=asof, count=1)` is
genuine-PIT). Reconstruct consensus FY1 EPS = `EP × raw close` (raw cancels with the price JQ used
in the E/P ratio → recovered earnings; adjusted close would inject a split/dividend artifact). Take
2-month and 4-month EPS revision = `eps_t / eps_{t-N} − 1` as the breadth proxy. Score RankIC vs
5/10/20d adjusted forward returns. PRE window 2014-01-01..2021-12-31 (n=87 month-ends), POST window
2022-05-01..2026-02-27 (n=44 month-ends).

**Result.** 20d-horizon RankIC summary (full results in [jq_eps_diffusion_benchmark.csv](jq_eps_diffusion_benchmark.csv)):

| signal / window | mean_rank_ic | rank_icir | n_dates |
|---|---|---|---|
| PRE 2014–2021, 60d-EPrev proxy | **0.0238** | **0.339** | 87 |
| PRE 2014–2021, 120d-EPrev proxy | **0.0206** | **0.262** | 83 |
| POST 2022-05+, 60d-EPrev proxy | 0.0030 | 0.042 | 44 |
| POST 2022-05+, 120d-EPrev proxy | −0.0066 | −0.077 | 42 |

**Side-by-side with Tushare report_rc breadth (ICIR_20d):**
| factor / window | Tushare | JQ-PIT |
|---|---|---|
| `_60` PRE-2022 | 0.36 (deep 2021-01..2022-04) | **0.34** |
| `_120` PRE-2022 | 0.31 (deep) | **0.26** |
| `_60` POST 2022-05+ | 0.041 | **0.042** |
| `_120` POST 2022-05+ | −0.023 | **−0.077** |

Two independent PIT sources + two different signal constructions (Tushare per-analyst breadth vs JQ
consensus-EP revision proxy) agree on ICIR magnitudes in both windows to within ~0.05.

**Pre-registered interpretation status.** The notebook docstring pre-committed to "PRE mean_rank_ic
~0.03–0.06+ / ICIR ~0.3–0.4 ⇒ artifact verdict overturned." Observed: mean_rank_ic **0.024**
(below the stated 0.03 lower band), ICIR **0.339** (squarely in [0.3, 0.4]). **Marginal pass on
mean-IC, clean pass on ICIR.** Not a slam-dunk discriminator on the strictly pre-registered
criterion — supports artifact-vs-decay diagnosis, not automatic status restoration (GPT 5.5 Pro
cross-review Q4, 2026-06-15).

**Verdict (per GPT 5.5 Pro cross-review, 2026-06-15).** REJECT immediate re-approval. The
substantive attribution (real historical analyst-revision regime + no reliable current edge) is
supported. The procedural reversal of the 2026-06-14 revoke is NOT supported by this benchmark
alone: the 2026-06-09 approval was CANARY-OVERRIDDEN, the breadth-restatement canary later FIRED,
and reversal requires factor-level canary discharge (recompute eps_diffusion under SNAP1 vs SNAP2,
show rank_corr > 0.999 + decile overlap + IC unchanged within tolerance) OR an explicit formal
second governance override under a new audit record. Both factors **stay candidate** with a
diagnostic memo. See [eps_diffusion_reevaluation_2026_06_15.json](../idea_sourcing/eps_diffusion_reevaluation_2026_06_15.json)
for the full audit chain (verdict_INITIAL_SUPERSEDED → verdict_FINAL_SUPERSEDED_BY_GPT_REVIEW →
gpt_5_5_pro_cross_review_verdict_2026_06_15 → verdict_AFTER_GPT_REVIEW).

**Caveats (GPT cross-review Q2/Q3, must address before any procedural reversal):**
- *Price-basis sensitivity*: the EP × raw_close reconstruction recovers EPS only if JQ's E/P uses the
  same raw close. A divisor-adjusted price would still preserve directional IC if correlated with
  size/corporate actions. Required before reversal: rank_corr table across EP variants (raw / pre-adj
  / post-adj / EP-revision alone / direct JQ consensus EPS if available).
- *Proxy vs exact*: per-analyst breadth can diverge from consensus-level revision (many small
  revisions vs one large; coverage changes; broker stale forecasts; earnings-level revision without
  breadth change). The cross-source IC magnitude match supports the regime hypothesis but does NOT
  prove the EXACT Tushare breadth was PIT-clean. Required before reversal: a direct JQ PIT
  analyst-up/down-count factor OR a bridge test (Tushare breadth vs JQ revision monthly rank_corr +
  decile overlap + residualized IC on the overlap window).
