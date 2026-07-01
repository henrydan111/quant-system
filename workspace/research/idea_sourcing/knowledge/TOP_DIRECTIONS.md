# arXiv → A-share: Top Extracted Research Directions

*Curated 2026-06-10 by the analyst pass on top of the knowledge framework's value-ranked
shortlist (`ranked_papers.parquet`, 671-paper themed corpus). This is the human/LLM **precision
verdict** that sits on top of the deterministic triage prior — it maps the highest-value arXiv
papers onto our exact data inventory, assesses orthogonality vs the 182-factor book, and proposes
concrete, field-grounded factors with their validation path.*

> **⚡ D1-D4 FULLY ADJUDICATED 2026-06-10 — screens + lifecycle + sealed OOS all same day; full story
> in [D1_D4_SCREEN_RESULTS.md](D1_D4_SCREEN_RESULTS.md).** 5 factors → IS gate (all candidate,
> 0.34-0.60) → **single-shot sealed OOS: ONLY `earn_sue_ni_assets` approved** (+0.026/LS 1.06,
> scraped the bar). The D1 "winner" CGO **sign-flipped OOS** (−0.265, GP-style collapse — its +0.047
> increment was a 2018-20 quality-rally IS artifact); both D4 `north_*_cov` sign-flipped. **The
> 2021-2026 OOS is SPENT for all 5 — never re-test as fresh.** Sealed-OOS gate: 4/5 stopped.
> Verdicts: **D1 WINNER** (CGO marginal increment +0.047, the program's largest; build next),
> **D2 DROPPED** (informed-large-order hypothesis fails; retail-reversal side is `rev_return_5d`
> repackaged), **D3 = growth-family refinement** (corr 0.9 to `grow_netprofit_yoy`, not a new
> dimension), **D4 keep within-coverage forms** (`$ratio` is zero-densified for non-Connect names;
> masked `north_chg_20_cov` corr 0.556 / neut ICIR 0.47, increment just under bar). Errata found:
> the "unmined" claims below were wrong at the catalog level (Cat 11/12/15 already define
> moneyflow/northbound/chip factors — `alpha_chip_weight_avg_dev` IS the CGO formula), and
> hk_hold's served column is the bare **`$ratio`**, not `$hk_hold__ratio`.

> A paper is a **hypothesis source, never evidence.** Every factor below still runs the full
> IS-only → sealed-OOS lifecycle and must pass the size/industry-neutralized **marginal-contribution**
> test vs the catalog (marginal IC × low correlation, NOT standalone ICIR — the house rule).
> `approved` ≠ tradable-strategy validated (separate deployment gate). CLAUDE.md §3.5, §7.

The framework's saturation map drove this: **price/accounting is SATURATED** for our book (OSAP gave
12 ports → 1 candidate → 0 deployable). Every direction below is in a **FRONTIER_OPEN** dimension —
data we have approved but have **barely mined** — except the methodology and blocked sections.

---

## Tier 1 — build now (FRONTIER_OPEN, fields verified, orthogonal)

### D1. Capital Gains Overhang / disposition effect from chip-distribution (`cyq_perf`)  ⭐ top pick
- **Source:** [2] *Replication of Reference-Dependent Preferences and the Risk-Return Trade-Off in the
  Chinese Market* (arXiv:2505.20608, 2025) — **tested directly on A-shares, 1995-2024**; also the
  foundational Grinblatt-Han (2005) CGO / Wang et al. (2017).
- **Idea:** Investors are reluctant to realize losses (disposition effect). A stock where most holders
  sit on **unrealized gains** faces less overhang selling pressure → predictable continuation; the
  reference point is the aggregate cost basis. Capital Gains Overhang `CGO = (P − refPrice)/refPrice`.
- **A-share mapping (exact, verified fields):** `cyq_perf` (筹码分布) is approved and **entirely unmined**.
  - `behav_cgo_20 = (Ref($close,1) - Ref($cyq_perf__weight_avg,1)) / Ref($cyq_perf__weight_avg,1)`
    — Grinblatt-Han CGO using the volume-weighted average cost as the reference price.
  - `behav_winner_rate = Ref($cyq_perf__winner_rate,1)` — % of holders in profit (获利比例), a direct
    overhang proxy; and a cost-dispersion variant from `$cyq_perf__cost_85pct − $cyq_perf__cost_15pct`.
- **Novelty:** Orthogonal — our book has `risk_/mom_/rev_/qual_` but **no cost-basis / reference-price
  behavioral factor**, and `cyq_perf` is used by zero factors. New behavioral dimension.
- **Why it's the top pick:** the one paper that is (a) China-tested, (b) a frontier dimension, and
  (c) built on a dataset we approved but never touched. Highest P(new orthogonal factor).
- **Caveats:** `cyq_perf` coverage is 2018+ (shorter IS window — 2018-2021 IS, 2022-26 OOS); winner_rate
  is bounded [0,100] (rank-transform). The paper finds CGO **interacts** with risk (weaker for high-CGO)
  — test the base CGO→return first, the interaction second. Draft stub: `stubs/arxiv_2505_20608.json`.

### D2. Informed order-flow imbalance from `moneyflow` (large/extra-large net)
- **Source:** [3] *Information Propagation Across Investor Types: Transfer Entropy Networks* (Korea,
  arXiv:2603.20271, 2026); [35] *Residual Supply and the Price of Risk Absorption* (arXiv:2605.30672,
  2026) — both: heterogeneous investor-type flows carry cross-sectional information.
- **Idea:** Large/extra-large orders proxy **institutional/informed** flow; small orders proxy retail.
  Persistent net institutional buying predicts continuation; one-sided retail pressure predicts reversal.
- **A-share mapping (the field doc literally suggests the form):** `moneyflow` approved 2026-06-04,
  **zero factors built**. Use **component-derived** signals (the opaque `$net_mf_amount` does NOT
  reconcile — caveat in the registry):
  - `flow_lg_net_20 = Mean(Ref(($buy_lg_amount + $buy_elg_amount - $sell_lg_amount - $sell_elg_amount),1), 20) / Mean(Ref($amount,1),20)`
    — 20d-smoothed large-order net inflow scaled by turnover.
  - retail-pressure reversal variant from the `_sm_` (small-order) components.
- **Novelty:** Orthogonal — no flow/order-imbalance factor in the book. FRONTIER_OPEN, unmined.
- **Caveats:** same-day OUTCOME field → MUST wrap every field in `Ref(...,1)` (PIT-safety lint enforces).
  Daily flow is noisy → smooth (20d) and expect short decay → 5d rebalance. Coverage full from 2014.

### D3. Earnings surprise / PEAD (`forecast`/`express` + statements, w/ `report_rc` consensus)
- **Source:** [29] *Capturing PEAD via genetic-algorithm-optimised supervised learning* (arXiv:2009.03094,
  2020); [1] *Which Voices Move Markets?* (arXiv:2604.13260, 2026, the SUE-controlled drift).
- **Idea:** Prices under-react to earnings news; standardized unexpected earnings (SUE) predicts drift
  over 1-3 months (PEAD) — one of the most robust anomalies, **not yet in our book**.
- **A-share mapping:** we have quarterly statements + disclosure dates + `forecast`/`express`
  preannouncements. Two buildable forms:
  - **SUE (random-walk):** standardize the YoY change in single-quarter earnings (`$n_income_sq_q0`)
    by its trailing dispersion → drift factor, anchored on the disclosure date (PIT via the ledger).
  - **Surprise-vs-consensus:** actual EPS vs the `report_rc` analyst consensus level — **PARTIAL**: the
    4 approved `report_rc` fields are revision-*flow* primitives (up/dn/count/n_active), not the
    consensus EPS *level*; this variant needs one more `report_rc` field promoted (consensus eps).
- **Novelty:** Adjacent to `earn_eps_diffusion` (analyst-revision breadth) but a **different signal** —
  realized surprise + drift, not forecast revision. Builds on the report_rc dimension that already paid off.
- **Caveats:** PEAD is well-known → decay/crowding risk; the paper notes post-discovery decay for the
  customer-momentum cousin. Test the clean SUE first. Draft stub: `stubs/arxiv_2009_03094.json`.

### D4. Northbound / foreign-flow positioning (`hk_hold`)
- **Source:** [13] *Foreign Signal Radar* (arXiv:2504.07855, 2025); [3] (investor-type flows).
- **Idea:** Foreign (Stock-Connect) investors are a relatively informed clientele in A-shares; changes
  in northbound holdings and the **acceleration** of foreign accumulation predict the cross-section.
- **A-share mapping:** `hk_hold` approved, unmined. `north_hold_chg_20 = Ref($hk_hold__ratio,1) −
  Ref($hk_hold__ratio,21)` (20d change in northbound holding %), plus a level and an acceleration term.
- **Novelty:** Orthogonal — no foreign-flow factor in the book. FRONTIER_OPEN.
- **Caveats:** northbound coverage skews to larger/connect-eligible names (sub-universe; size-neutralize).
  Confirm the exact `hk_hold` served column before building.

---

## Tier 2 — methodology upgrades (METHOD; improve how we run the gates, not new factors)

These directly attack our **factor-zoo multiple-testing** problem — the exact risk that burned the
87 `oos_informed_backfill` candidates and that our marginal-contribution rule fights.

- **D5. Empirical-Bayes shrinkage for factor selection** — [26] *High-Throughput Asset Pricing*
  (arXiv:2311.10685, 2023): mine 136k strategies, EB shrinkage matches top-journal OOS performance
  while **eliminating look-ahead bias**, and standard multiple-testing methods *fail* to identify OOS
  performers. → Adopt EB-shrunk IC as a screening statistic in the sandbox layer; it is exactly our
  "screen hundreds of factors without overfitting" problem.
- **D6. FDR / dependent multiple testing** — [5] *Sequential Cauchy Combination Test* (arXiv:2303.13406);
  [36] *Controlling FDR under Cross-Sectional Correlations* (arXiv, 2021). → Strengthen the promotion
  gate's deflated-Sharpe / multiple-comparison control for correlated factor tests.
- **D7. Publication bias / forking paths** — [18] *Publication Bias in Asset Pricing Research* (2022);
  [42] *Forking paths in financial economics* (2023). → Reinforces pre-registration + sealed-OOS
  (we already do this); cite as the empirical justification in the lifecycle README.
- **D8. Conditional/ML factor models for combination** — [12] *Deep Learning for Conditional Asset
  Pricing*, [14] *Semiparametric Conditional Factor Models*, [25] *KAN Autoencoders*, [33] *Deep PLS*.
  → model_zoo targets for **combining** our existing factors (IPCA-style conditional loadings), not new
  raw signals.

---

## Tier 3 — blocked (great direction, needs data we lack → acquisition targets)

- **B1. Earnings-call / filing-text sentiment** — [1] *Which Voices Move Markets?* (FinBERT
  section-weighted earnings-call sentiment, OOS IC 0.142, monthly LS alpha 2.03% t=6.49). **BLOCKED:
  no transcript/filing text corpus.** Highest-value acquisition target → a Chinese earnings-call /
  公告 text pipeline + FinBERT-zh. The `text_nlp` dimension is the single biggest blocked frontier
  (it dominates the BLOCKED slice of the corpus).
- **B2. Customer / supply-chain momentum** — [8] *Customer Momentum* (arXiv:2301.11394): a firm's
  return predicted by its customers' past returns (Cohen-Frazzini lead-lag). **BLOCKED: no
  customer-supplier graph** (Tushare 产业链 not ingested). Partial proxy: SW-industry lead-lag momentum
  (buildable now, weaker). Note the paper documents post-discovery alpha decay.
- **B3. Fund-flow forced-sale pressure** — [35] *Residual Supply* needs mutual-fund holdings→flow.
  **BLOCKED: no fund-holdings dataset** (Tushare 基金持仓 not ingested). Northbound flow is a partial proxy (→D4).

---

## Tier 4 — buildable but low-priority

- **S1. China holiday / Spring-Festival seasonality** — [31] *Holiday Effect of China's Time-Honored
  Companies* (arXiv:2308.00702). Buildable from `trade_cal` (pre-holiday calendar dummy). Real but
  **low capacity / low breadth** (a calendar tilt, not a stock-selection factor). Park it.

---

## Recommended next action

Build **D1 (Capital Gains Overhang)** first — it is the highest-expected-value: China-tested in the
source paper, a genuinely new behavioral dimension orthogonal to the book, and built on `cyq_perf`
which we approved but never touched. Run it through the exact gauntlet that validated `eps_diffusion`:
sandbox screen (2018-2021 IS) → size/industry-neutralized **marginal-contribution** vs the catalog →
`factor_lifecycle` (draft→candidate) → single-shot sealed-OOS. Then D2 (informed flow) in parallel as
a second, uncorrelated frontier probe.

If D1 and D2 both survive the marginal test, we will have converted the arXiv frontier into **two new
orthogonal dimensions** (behavioral chip-distribution + informed flow) on top of the analyst dimension
that `eps_diffusion` opened — exactly the "new data dimension" the saturation finding said we needed.
