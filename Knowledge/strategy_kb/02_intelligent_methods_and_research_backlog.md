# 02 — Intelligent Methods & Research Backlog

Distilled from Qbot `docs/03-智能策略/` (model_zoo, ML strategies) plus the platform's factor-generation
and evaluation tooling. The second half turns the gaps from [01](01_classic_strategies_catalog.md) into a
**prioritized research backlog mapped to our profiles**.

---

## A. ML / model methods Qbot foregrounds

Qbot's "quant.ai" is essentially **Microsoft Qlib's model zoo** — the same backend our system already
sits on. So "300+ models from 40+ papers" is *available to us too*; the question is which are worth
exercising, not whether we can.

| Family | Examples | Our status |
|---|---|---|
| GBDT | LightGBM, XGBoost, CatBoost | ✅ reachable via Qlib; `ml_signal_model_research` profile + `model_registry` |
| RNN / seq | LSTM, GRU, ALSTM, ADARNN | 🟡 reachable, not exercised |
| Attention | Transformer, TabNet, GATs, TFT, TRA, HIST | ⬜ not run |
| RL | DQN family, Q-learning (timing/execution) | ⬜ not run, no execution module |
| LLM | FinGPT, news/sentiment signals | ⬜ no news/NLP pipeline |

**Takeaway:** the model breadth is not a real gap (Qlib gives it to us). The *inputs* are the gap —
we feed the zoo a clean 171-factor panel; Qbot's edge claims come from **alt-data inputs (news/LLM) and
RL execution**, neither of which we have. Prioritize inputs over model architecture.

---

## B. Factor generation & evaluation tooling

| Qbot capability | What it is | Our equivalent / gap |
|---|---|---|
| **Alpha-101 / Alpha-191** | the published WorldQuant / GTJA formulaic alpha sets | 🟡 our catalog overlaps in spirit (price/volume `mom_* liq_* risk_*`); we have not systematically ported the 101/191 set as a labelled, PIT-wrapped batch — **concrete backlog item** |
| **DEAP / genetic auto factor generation** | evolve factor expressions against a fitness (IC) | ⬜ we hand-author factors; a genetic-search layer over our operator set + IC fitness is a real capability gap |
| **alphalens** | standardized factor tearsheets (IC, quantile spread, turnover) | ✅ we have richer: `factor_eval` toolkit + `result_analysis` canonical metrics. **We are ahead here.** |
| **quantstats** | portfolio tearsheet HTML | ✅ `BacktestReport` + per-registry `review.html` cover this |

**Two genuine tooling gaps worth importing the *idea* of:**
1. **Port Alpha-101/191 as a governed factor batch** — each formula wrapped to our PIT contract
   (every `$field` under `Ref(...)`, see CLAUDE.md §3 factor-library PIT-safety), run through the
   factor-lifecycle `draft→candidate` gate. High-yield, mechanical, well-defined.
2. **Genetic / search-based factor discovery** — a DEAP-style evolutionary loop over our
   `operators.py` primitives with rank-IC fitness, feeding survivors into `factor_screening`. This is
   the automated-discovery analog of what we now do by hand. Must run inside the IS window only
   (the search is itself a massive multiple-testing exposure → sealed-OOS confirmation is mandatory).

---

## C. Research backlog (prioritized, mapped to our machinery)

Ordered by **strategic value × feasibility**. Each item names the profile/engine that would run it.

### P0 — Market-neutral / hedge capability (regime diversification)
- **Why:** our entire catalogue is long-only trend-following, which the regime matrix
  ([00](00_strategy_taxonomy.md)) shows is *weak in bear & sideways*. A β≈0 capability is the single
  biggest portfolio-level gap (Card 5).
- **Minimum viable:** synthetic index-return short overlay on an existing long book; clearly labelled
  idealized (no futures basis/roll). Then evaluate via `result_analysis` with a market-neutral lens.
- **Blocker:** real version needs futures data + an `execution`/futures instrument (we have neither).
- **Profile:** custom overlay first; later `hypothesis_validation` once a hedge instrument exists.

### P0 — Promote `portfolio_risk` from dormant → real (unlocks index enhancement)
- **Why:** index enhancement (Card 4) and any TE-constrained or risk-parity construction need a real
  covariance/risk model. `MultiFactorRiskModel.fit()` is currently a no-op and `predict_portfolio_risk`
  returns hardcoded `0.05` (CLAUDE.md §3 dormant boundary).
- **Profile:** module work, then `strategy_improvement` to A/B the optimizer-constructed book vs top-k.

### P1 — Port Alpha-101/191 as a PIT-wrapped factor batch
- **Why:** large, well-defined, mechanical factor-coverage expansion; directly grows the catalog the
  whole system feeds on.
- **Profile:** `factor_screening` → factor-lifecycle `draft→candidate` gate. Each must pass the
  `test_factor_library_pit_safety` parser walk.

### P1 — RSRS timing overlay (drawdown control)
- **Why:** cheap to prototype (Card 6); addresses the trend-following drawdown weakness without a new
  asset class. Use as a regime switch on top of selection, not standalone.
- **Profile:** `event_driven_signal_research`.

### P2 — Genetic/auto factor search
- **Why:** automates discovery; high upside but high overfitting risk.
- **Guardrail:** IS-only search, sealed-OOS confirmation, treat the whole search as one multiple-testing
  family (the holdout-seal `seal_key` / FrozenSelectionSet machinery is designed for exactly this).
- **Profile:** new tooling feeding `factor_screening` + `hypothesis_validation`.

### P2 — ML signal models with current inputs (LightGBM/LSTM over the 171-factor panel)
- **Why:** the model zoo is free via Qlib; worth a baseline to see if non-linear blends beat the linear
  composites we publish.
- **Profile:** `ml_signal_model_research` → `model_registry`.

### P3 — Alt-data inputs (news/LLM sentiment)
- **Why:** Qbot's most differentiated input (FinGPT/news). Genuinely new alpha source for us.
- **Blocker:** no news/NLP ingestion pipeline; large build. Park until P0/P1 land.

### Parked (documented, low feasibility for us)
- **T+0 intraday, grid trading, limit-up board-opening** — blocked by daily granularity + A-share T+1
  (Cards 9, 12). Recorded so we don't re-litigate.
- **CTA/futures, macro multi-asset, fund 4433** — out of equity scope (the *momentum-rotation idea*
  from 4433 is the only transferable piece → multi-horizon `mom_*` filter, a cheap screening run).

---

## D. The honest framing (carry this into any "learn from Qbot" discussion)

Qbot teaches us **almost nothing about research correctness** (it has no PIT/seal/governance) and
**almost everything about strategy breadth + the productization last-mile** (live execution, monitoring,
alerting, dashboards, multi-asset). Our moat is exactly what Qbot lacks; Qbot's breadth is exactly where
our catalogue is thin. This KB imports the *breadth as a backlog* while keeping every item behind our
existing gates. The biggest strategic lesson is structural, not a single strategy: **we are 100%
long-only trend-following, and the regime matrix says that is fragile — build a market-neutral leg.**
