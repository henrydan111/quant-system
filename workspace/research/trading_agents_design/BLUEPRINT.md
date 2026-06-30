# Trading-Agents System Blueprint — 券商金股 Pool + 量化选股 + AI 主观增强

**Date:** 2026-06-28
**Status:** DESIGN (pending §10 GPT cross-review before any load-bearing build)
**Premise (validated):** 券商金股 is a **candidate pool**, not an alpha signal
([broker_recommend_alpha/FINDINGS.md](../broker_recommend_alpha/FINDINGS.md)). Alpha must come
from the quant + AI overlay ON the pool.

---

## 0. TL;DR — the one design decision the evidence forces

**The LLM is NOT the alpha engine. The quant factor model is.** Every published LLM-agent trading
system collapses 50–70% (or sign-flips) once the test period passes the model's training cutoff
(Profit Mirage, LiveTradeBench, +5 sources — see the deep-research report). A backtest of an LLM that
"rates" 贵州茅台 is contaminated by the model's *memory* of how 茅台 actually performed.

So the architecture inverts the naive "TradingAgents picks stocks" framing:

```
  券商金股 (candidate POOL)  →  QUANT factor model (the alpha, sealed-OOS validated)
                                        ↓ ranked candidates
        AI multi-analyst layer = a BOUNDED CONVICTION/RISK OVERLAY + EXPLAINER
        (never a return-timing oracle; only PIT-controlled inputs; veto-and-tilt, not pick)
                                        ↓
        Decision layer  →  EventDrivenBacktester  →  sealed-OOS governance  →  deploy
```

The LLM earns its place ONLY in roles where its training-cutoff memory cannot leak into the result:
**(1) structured extraction** from documents/analyst data, **(2) narrative/policy/macro dimensions the
quant model structurally cannot see**, **(3) explainable rationales** for human governance. It produces
a *bounded tilt and a veto flag*, not a price prediction.

---

## 1. What the evidence + your system FORCE (the binding constraints)

| Constraint | Source | Design consequence |
|---|---|---|
| LLM training cutoff = lookahead | Profit Mirage 2510.07920, LiveTradeBench 2511.03628, arXiv 2601.13770 | LLM never asked to "predict/rate" a named stock from memory. Inputs are PIT-controlled text/numbers only; the LLM *reasons over provided evidence*, not recalls outcomes. |
| LLM judgment can't be backtested cleanly | same | LLM-component validation = **live/forward** primary; historical backtest is a weak prior. Quant component uses normal sealed-OOS. |
| Stronger LLM ≠ better trading | LiveTradeBench (LMArena corr ≈ 0) | Don't over-invest in model size/reasoning for "picking". Invest in extraction quality + PIT plumbing. |
| 金股 = size proxy | our validation | Pool only. Size-neutralize. Quant overlay is mandatory. |
| **No raw news/text ingested** | codebase (only structured analyst/numeric data) | The "消息面 AI" layer's first fuel is **report_rc analyst revisions** (you HAVE it), NOT news scraping. News text is a later, separately-gated data-sourcing project. |
| A-share sentiment is manipulated (水军/黑嘴) + price-delayed | prior KOL deep-research (memory `research_kol_sentiment_altdata_verdict`) | Downgrade "social sentiment = alpha" → analyst-revision sentiment + dispersion; PIT-visible-time + anti-manipulation gates before any forum/news text. |
| Unlevered, sealed books, factor-validation-lab culture | CLAUDE.md §7.11, project governance | LLM signal enters the SAME draft→candidate→approved sealed-OOS ladder as any factor. No exceptions, no "the AI says so". |

---

## 2. The architecture — 4 layers + the agent roles (TradingAgents, adapted)

### Layer 1 — Universe / Pool (券商金股 as start point)
- Monthly 金股 dedup'd list = the candidate pool (PIT anchor: first trading day ≥ day-4 of month).
- Optionally union with a liquidity/size-banded broad universe so the pool isn't the only source
  (金股 alone is ~150–250 names/mo, size-tilted).
- Boolean membership mask (Layer-2 discipline), NOT a row filter.

### Layer 2 — Quant alpha (the engine, does the "fundamental/technical analyst" job rigorously)
- `get_factor_catalog()` + `compute_factors()` over the pool, **size-neutralized**.
- Selection by **marginal orthogonal contribution** (memory `reference_factor_selection_marginal_not_icir`),
  not standalone ICIR.
- This is the primary score. It is the part with demonstrated, sealed-OOS-validated edge.

### Layer 3 — AI multi-analyst overlay (the "主观增强" — bounded, PIT-firewalled)
Maps the user's vision (基本面/行业/宏观/地缘 analysts) onto TradingAgents' debate structure, but each
agent outputs a **structured opinion vector**, never a buy/sell or a price call:

| Agent (persona) | Input (PIT-controlled ONLY) | Output |
|---|---|---|
| **Analyst-revision analyst** | `report_rc` as-of (EPS revisions, rating changes, target-price drift), `forecast` 业绩预告 | revision-breadth score + direction (the endorsed 消息面 signal) |
| **Fundamental analyst** | the stock's PIT financials + the quant fundamental factors | concurs/dissents with quant fundamental score + 1-line reason |
| **Industry analyst** | sector aggregates, 金股 sector concentration, northbound sector flow | industry tailwind/headwind tilt |
| **Macro / Policy analyst** | as-of macro/policy context (the dimension quant can't see; A-share is policy-driven) | regime flag (risk-on/off), policy-beneficiary tilt |
| **Geopolitical analyst** | as-of curated events | tail-risk veto flag |
| **Bull vs Bear debate** | the above vectors per candidate | a **bounded net tilt ∈ [−1,+1]** + a **hard veto** (risk) |
| **Risk / Portfolio manager** | tilt + veto + quant score + position limits | final selection + (later) sizing — ties into the dormant `portfolio_risk` module |

Key rule: the overlay can **down-weight or veto** a quant pick (risk control, narrative red-flags) and
apply a **small bounded tilt** (capped, e.g. ±20% of rank) — it CANNOT manufacture a pick the quant
model didn't surface, and it cannot output a return forecast.

### Layer 4 — Decision + execution + governance
- Combine: `final_score = quant_score (rank) + clipped tilt`; veto removes a name.
- Backtest via `EventDrivenBacktester` (event-driven, total-return, T+1, realistic cost, 1× unlevered).
- The combined signal is registered and run through the **sealed-OOS ladder** (draft→candidate→approved).
- The LLM signal gets a **frozen prompt+model-version hash** (prompt/model drift = factor drift → re-seal).

---

## 3. How it maps onto YOUR system (concrete integration points)

*(Structural map from codebase exploration; exact signatures to be verified at build time.)*

| Need | Hook in your repo |
|---|---|
| Feed a monthly selection/score to the backtest | `Strategy` subclass (`src/backtest_engine/event_driven/strategy.py`: `initialize/before_market_open/on_bar`) → `EventDrivenBacktester.run(strategy, …)`. Precomputed `{date→[codes]}` / `{date,code→score}` drives `before_market_open`. (Same engine the guorn_verify_* scripts use.) |
| Quant factors over the pool | `get_factor_catalog()` + `compute_factors()` ([factor_library](../../../src/alpha_research/factor_library/)) |
| 消息面 fuel (NOW) | `report_rc` analyst forecasts (already PIT-materialized: `$report_rc__*`) + `forecast` 业绩预告 |
| Enter governance as a non-factor signal | `signal_registry` + `Hypothesis`/`PrescribedRecipe` (`src/research_orchestrator/hypothesis.py`), `hypothesis_validation` profile, sealed-OOS holdout store |
| New workflow | add a `ResearchProfile` (`src/research_orchestrator/profiles.py`) — e.g. `llm_overlay_research` — DAG: build pool → quant score → LLM overlay → backtest → correlation-gate → publish |
| Run logging | `ExperimentTracker` (`src/alpha_research/mlflow_tracker.py`) — log prompt hash, model id, metrics |
| LLM calls | greenfield — Anthropic SDK, `.env` present. No existing LLM code (clean slate). |
| Sizing / risk | the **dormant `portfolio_risk`** module is the natural home for the Risk-manager agent's output (a reason to revive it — memory `project_capital_allocation_buildout`) |

---

## 4. The PIT firewall (the hard problem — get this wrong and everything is fake)

This is where most LLM-trading projects silently fail. Three channels of leakage, each plugged:

1. **Parametric memory (training cutoff).** Never prompt "is 茅台 a good buy?". Prompt: "Given ONLY
   these as-of-date facts [analyst revisions, financials, sector flow], score the *evidence balance*."
   The model reasons over supplied evidence; it must not need to recall the ticker's future. For any
   *historical* evaluation of an LLM component, treat the result as a weak prior — the only clean test
   is **forward/paper-live** (LiveTradeBench philosophy).
2. **Point-in-time input alignment.** Every text/number fed to an agent is filtered to what was visible
   at the decision date (report_rc visibility anchor; 金股 day-4 anchor; news, if ever added, by
   published-time not event-time). Reuse the existing `pit_research_loader` / `qlib_windowed_features`
   doors — never hand-roll.
3. **Governance = same sealed-OOS gate.** The combined signal is a candidate factor. It spends a sealed
   OOS window once. The LLM prompt + model version are part of the definition hash (a prompt edit is a
   new factor, re-seal). No "trust the AI" bypass.

---

## 5. Staged build plan (each stage validated before the next; LLM enters late, on purpose)

**Phase 0 — Quant-only pool test (NO LLM). The foundation + the 金股 go/no-go.**
- 金股 pool ∩ size band → apply selected approved factors (size-neutralized, marginal-contribution) →
  monthly long-only top-K, event-driven, vs broad market AND vs 金股-EW.
- **Decision gate:** does quant-on-金股-pool beat (a) broad market and (b) raw 金股-EW? If broker
  pre-filtering adds nothing over quant-on-broad-universe → 金股 is dropped; if it adds → pool confirmed.
- *This is the sharpened-B test already proposed. It needs none of the AI machinery and de-risks everything.*

**Phase 1 — Analyst-revision layer (structured, PIT-clean, minimal/no LLM).**
- Build the report_rc-based analyst-revision-breadth + rating-drift signal over the pool (the 消息面
  signal the prior research endorsed). LLM optional here (only for parsing edge cases).
- Validate as a candidate factor; test marginal contribution over Phase-0 quant score.

**Phase 2 — LLM multi-analyst overlay (the "trading agents" proper).**
- Implement the Layer-3 agents (start with 3: analyst-revision, fundamental-concur, macro/policy-regime)
  producing bounded tilt + veto on PIT-controlled inputs. LangGraph-style orchestration or a simple
  sequential pipeline — start simple.
- Validate **forward/paper-live** + a cautious historical check; require it to add marginal value over
  Phase-1 net of cost. Frozen prompt+model hash. If it doesn't beat Phase-1 → it's an explainability tool,
  not an alpha source (still useful for governance/human review).

**Phase 3 — News/research text (separate, expensive, heavily-gated data project).**
- ONLY if Phases 0–2 justify it. Source news via Tushare `news`/`major_news`/`anns_d` (PIT-visible-time)
  with anti-manipulation gates (memory `research_kol_sentiment_altdata_verdict`). Highest cost/risk.

---

## 6. Honest expected value + the failure modes to pre-register

- **Most likely outcome (base rate):** the quant layer carries the edge; the LLM overlay adds modest
  risk-control + explainability but little independent alpha. That is still a *useful* system (better
  drawdowns, human-auditable rationales, policy-regime awareness) — just not the "AI picks winners" dream.
- **The trap to avoid:** a beautiful historical backtest of the LLM overlay that is pure training-cutoff
  leakage. Pre-registered falsification: LLM-overlay alpha must survive **forward/live** and a
  cutoff-aware split; if it only "works" in-sample it is rejected.
- **Capacity/cost:** monthly rebalance on a ~150-name pool is fine at <¥10M; LLM cost is per-decision,
  bounded by pool size × agents × rebalances (cheap monthly).
- **What would kill the project:** Phase-0 shows 金股 pool adds nothing over quant-on-broad → then the
  whole "金股 as start point" premise is moot and we'd pivot (Option B, or quant-on-broad + LLM risk overlay).

---

## 7. Immediate next step

**Run Phase 0 (quant-on-金股-pool vs broad + vs 金股-EW).** It is the foundation of every later layer,
needs zero AI infrastructure, reuses the factor library + event-driven engine you already trust, and
delivers the 金股 go/no-go. Everything in Phases 1–3 is contingent on Phase-0 confirming the pool has a
role.

**Before any of Phases 1–3 become load-bearing code: this blueprint goes through the §10 GPT cross-review.**
