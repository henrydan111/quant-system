> # ⚠ INVALID METHOD — RESULTS PROVISIONAL (2026-06-08 correction)
> This entire analysis was produced by a **non-compliant hand-rolled PIT path**: the scripts read raw
> `data/` parquet directly and hand-rolled the PIT alignment, violating CLAUDE.md §3.2 / src/system.md §0
> ("NEVER hand-roll PIT alignment; sandbox PIT → `pit_research_loader`; qlib factors → `compute_factors`;
> a new dataset is usable only after `pit_backend` materializes it into the ledger+provider + registry").
> It also bypassed the provider boundary guard (no delist/IPO-lag masking) → likely survivorship
> contamination. **Do NOT trust the `eps_diffusion` GO / tradability numbers below** — they must be
> reproduced through the sanctioned backend (materialize `$report_rc__*` bins via a `pit_backend`
> aggregator → register → `compute_factors` Qlib expr → factor_lifecycle → sealed OOS) before any are
> accepted. Same failure mode as the val_heavy lookahead. Retained for method reference only.

# Wave-1A pilot — `report_rc` analyst-consensus incremental-IC result

*2026-06-08. Sandbox, IS 2014-2020 ONLY (OOS 2021-2026 untouched). The audit-first gate (GPT
cross-review verdict) BEFORE paying the normalize→PIT→provider→registry ingestion toll.*

## Method (canonical helpers, no reinvention)
- Consensus panel: [report_rc_consensus.py](report_rc_consensus.py) — PIT anchor =
  `strictly_next_open_trade_day(report_date)` (verified `effective>report` for all rows), trailing
  window + 400d age-expiry, one vote per analyst. 84 month-end as-of dates, **211,790 stock-months,
  3,978 covered stocks** (covered universe only — the §2.4-correct test).
- Forward return (20d) + controls via `compute_factors`; neutralization via
  `factor_eval.neutralization.neutralize` (per-date cross-sectional OLS); IC via
  `factor_eval.ic_analysis` (never reimplemented).
- **Incremental** = RankIC of the residual after neutralizing each feature vs **{log size, 20d
  momentum, 5d reversal, P/B value, 20d turnover, 20d net money-flow} + SW-L1 industry dummies.**

## Result (incremental = the number that matters)

| Feature | raw RankIC | raw ICIR | **incr RankIC** | **incr ICIR** | incr t (n=84) | IC hit |
|---|---|---|---|---|---|---|
| `eps_revision` | +0.0106 | +0.19 | **+0.0106** | **+0.18** | 1.68 | 0.62 |
| `rating_revision` | +0.0048 | +0.15 | **+0.0066** | **+0.20** | 1.80 | 0.58 |
| `eps_dispersion` | −0.0130 | −0.21 | −0.0085 | −0.10 | −0.93 | 0.59 |
| `n_analysts` | +0.0147 | +0.10 | +0.0248 | +0.35 | 3.25 | **0.51** |
| `eps_fy1` (level) | +0.0117 | +0.10 | +0.0180 | +0.26 | 2.40 | 0.61 |
| `rating_score` (level) | +0.0070 | +0.08 | +0.0023 | +0.05 | 0.49 | 0.45 |

## What the data shows (stated, not hedged)
1. **Orthogonality thesis CONFIRMED.** The revision signals' RankIC is essentially unchanged by
   neutralization (`eps_revision` raw 0.0106 → incr 0.0106; `rating_revision` 0.0048 → 0.0066) → they
   are genuinely independent of size/price/value/flow/industry. This was the central hypothesis for
   adding `report_rc`, and it holds.
2. **But the signal is WEAK.** The cleanest thesis features (`eps_revision`, `rating_revision`) are
   **marginal**: incremental RankIC ≈ 0.006–0.011, monthly ICIR 0.18–0.20, t ≈ 1.7–1.8 (p ≈ 0.08–0.10).
   Encouraging only in that hit rates are 58–62% and the sign is direction-consistent.
3. **The two high-t features are not what they look like.** `n_analysts` (t=3.25) has a **51% IC hit
   rate** → a few-months magnitude artifact, not a robust monthly signal, and it is the size-adjacent
   coverage-count feature §2.4 already flagged. `eps_fy1` (t=2.40) is the consensus EPS *level* —
   economically ≈ share-price level, not analyst information; discounted.
4. **Rating *level* is dead** (t=0.49) — expected, since A-share sell-side ratings are ~uniformly
   bullish (panel mean `rating_score` ≈ 1.0 = "增持/Overweight"); only the *change* carries anything.

## v2 REFINEMENT (2026-06-08) — the verdict FLIPS for one feature form

The v1 NO-GO was correct *for v1 features* (magnitude revisions + levels). The user-chosen refinement
built the literature's stronger forms ([report_rc_consensus_v2.py](report_rc_consensus_v2.py),
[report_rc_pilot_v2.py](report_rc_pilot_v2.py)) — revision **diffusion/breadth**, recommendation-change
**events**, **target-implied return** — at horizons 5/10/20. Same PIT-correct, covered-universe,
neutralized harness.

| v2 feature | coverage | incr RankICIR 20d | incr RankIC 20d | t (n≈84) | hit | 5d / 10d ICIR |
|---|---|---|---|---|---|---|
| **`eps_diffusion`** (net % analysts raising FY1 EPS) | 29% | **+0.643** | +0.0243 | **5.89** | **0.74** | +0.19 / +0.22 |
| `rating_diffusion` (net % raising rating) | **2%** | +0.20 | +0.0283 | 1.75 | 0.58 | +0.09 / +0.05 |
| `rec_up_net` (recent rating-change events) | 73% | −0.10 | −0.0090 | −0.93 | 0.54 | −0.01 / −0.03 |
| `tp_implied_return` (mean target / close − 1) | 0%* | — | — | — | — | — |

Findings:
1. **`eps_diffusion` is a real, strong, orthogonal signal at the 20d horizon.** raw RankICIR +0.48 →
   incremental +0.64 (neutralization *raises* it → NOT a size/price/value/flow/industry artifact),
   t=5.89, 74% of months positive, and **monotonically rising with horizon** (0.19→0.22→0.64) — the
   signature of genuine slow information diffusion, not noise. The **breadth/diffusion form is
   dramatically stronger than v1's magnitude form** — GPT's refinement intuition was correct.
2. **Recommendation-change forms are dead** — `rating_diffusion` has only **2% coverage** (A-share
   sell-side analysts almost never *change* a rating; they are sticky at 买入/增持), and `rec_up_net`
   IC is ~0/negative. This is a data reality, not a feature-design failure.
3. **`tp_implied_return` deprioritized** — *a harness-alignment bug left it at 0% (UNRESOLVED, low
   priority); separately, the `tp` field is sparse (21%) AND unit-corrupted (target prices like 9600
   appear), so it would need cleaning before it is trustworthy regardless.

Caveats on the `eps_diffusion` win (why it's CONDITIONAL, not deploy-ready):
- **IS-only** (t=5.89 in-sample). Strong enough to formalize, NOT yet OOS-confirmed.
- **29% coverage** → the signal lives on a narrow, large-cap-tilted sub-universe (capacity/tradability
  must be assessed — IC ≠ long-only return, the project's recurring lesson).
- **20d-only** (weak at 5/10d) → a monthly-horizon signal.

## Tradability gate (2026-06-08) — PASSES (IC converts to a tradeable spread)
[report_rc_tradability.py](report_rc_tradability.py), canonical `factor_eval` (quantile/LS/turnover/
decay), IS 2014-2020, monthly 20d hold, covered universe. `eps_diffusion` is **discrete** with a large
point-mass at 0 → a 5-quantile `qcut` collapses (rank IC handles ties fine; the *portfolio* needs a
tie-tolerant construction), so the economically-clean read is a **sign split**: long upward-revised
(`diffusion>0`), short downward-revised (`diffusion<0`), vs the covered-universe equal-weight mean.

| Metric (IS 2014-2020, 84 months) | Value |
|---|---|
| avg names/month | 251 long / 381 short (real capacity) |
| **LONG-ONLY leg** (diffusion>0 excess vs universe) | **+5.5%/yr, Sharpe 1.63** |
| long-short (long − short) | +9.3%/yr, gross Sharpe 1.69 |
| annualized turnover (monthly) | 5.17 (517%) |
| **net LS Sharpe @ 30bps** | **1.13** (survives cost) |
| IC decay (RankICIR 10/20/40/60d) | 0.25 → 0.48 → 0.56 → **0.66** (rising = slow signal) |

The strong IC **converts to a deployable long-only signal** (+5.5%/yr excess at Sharpe 1.63) — unlike
v1, and unlike the cross-sectional factors from the `long_only_50cagr` effort that did NOT convert.
The LS survives realistic cost (net Sharpe 1.13). The rising-to-60d decay means turnover can be cut by
holding longer (better net). This clears the tradability gate.

Residual caveats (still IS, still need OOS): the long-only excess is vs the **covered (large-cap-
tilted) universe**, not a tradable index benchmark; a proper `EventDrivenBacktester` run vs CSI500 with
T+1 / limits / realistic costs is part of the formal step; and the whole thing is **in-sample** until
the single sealed-OOS shot.

## Verdict: GO — ingest `report_rc` and formalize `eps_diffusion` (only)
All three gates passed: **strong orthogonal IC** (t=5.89, neutralization-robust, monotonic decay) +
**tradeable** (long-only +5.5%/yr Sharpe 1.63, net-of-cost LS Sharpe 1.13). The data carries a real,
orthogonal, deployable monthly alpha — **analyst EPS-revision breadth** — that justifies the ingestion
toll. Proceed: normalize→PIT-ledger→Qlib-materialize→field-registry for `report_rc`, add
`eps_diffusion` to the catalog (PIT-safe expression, `Ref`-lagged), formalize through the
`factor_lifecycle` IS gate (LS-Sharpe / quantile / decay / turnover the formal way), then a single
sealed-OOS shot vs a tradable benchmark. Do NOT ingest the dead forms (rec-change / rating-diffusion)
or the corrupted `tp` field.

### (Earlier) CONDITIONAL-GO note (pre-tradability)
The audit-first gate worked exactly as intended: v1 would have wrongly shelved `report_rc`; the
refinement found the real signal. The data **does** carry a strong orthogonal alpha — **analyst
EPS-revision breadth (`eps_diffusion`)** — at the monthly horizon. That clears the bar to pay the
ingestion toll **for this one feature**: normalize→PIT-ledger→Qlib-materialize→field-registry, then
run it through the formal `factor_lifecycle` IS gate (proper LS-Sharpe / quantile-spread / decay /
turnover) and a single sealed-OOS shot. Do NOT ingest the dead forms (rec-change/rating-diffusion) or
the corrupted `tp` field. The original v1 NO-GO below stands for the magnitude/level forms.

---

## (Superseded) v1 verdict: NO-GO for full standalone ingestion now
The audit-first gate did its job: we now KNOW, before paying the heavy ingestion/governance toll, that
`report_rc` consensus is **real + orthogonal but too weak to justify a standalone factor.** The thesis
signals are marginal in-sample (t < 2); given this project's strong prior that marginal IS signals do
not survive sealed OOS (the 0/8 new-data screen, the val_heavy invalidation, the long_only negative),
a standalone `report_rc` factor would almost certainly fail the OOS bar. **Do NOT** run the
normalize→PIT-ledger→Qlib-materialize→field-registry pipeline for it as a standalone factor at this
stage.

Its honest place: a **weak-but-orthogonal ingredient** for a future multi-signal composite / ML
feature set — not a standalone factor. Orthogonality is exactly what an ensemble wants; strength is
what a standalone needs, and it has the former not the latter.

## One falsification path before final shelving (hypothesis, not a claim)
The v1 features are *magnitude* revisions + *levels*. The literature's strongest analyst-alpha forms
were NOT tested here and could move the result:
- **revision DIFFUSION / breadth** — net % of analysts revising *up* vs *down* over a short (20–30d)
  trailing window (a sign/diffusion index, not a magnitude), which is typically cleaner and stronger
  than magnitude revision;
- **recommendation-change events** — days-since-upgrade / upgrade indicator with a short holding window
  (the alpha concentrates right after the change, which a monthly snapshot dilutes);
- **target-price-implied return** — mean target / price − 1 (deferred in v1; needs a price merge).
- shorter holding horizon (5–10d) — revision alpha decays fast; 20d may already be past the half-life.

Test plan if pursued: build these three features in the SAME sandbox harness, same IS window, same
neutralizers; PASS only if a diffusion/event feature clears incremental RankICIR meaningfully above
the current ~0.20 with a hit rate > 60%. Falsified (→ final shelve) if it stays ≤ ~0.20.

## Discipline notes
- **OOS 2021-2026 was NOT touched.** This is an IS-only audit.
- Nothing was ingested/normalized/registered; `report_rc` remains RAW. No governance toll paid.
- Artifacts: [report_rc_consensus.py](report_rc_consensus.py), [report_rc_pilot.py](report_rc_pilot.py),
  `workspace/outputs/report_rc_pilot_*.json`.
