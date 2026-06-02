# Strategy Knowledge Base

**Created:** 2026-06-02
**Source seed:** distilled from the [UFund-Me/Qbot](https://github.com/UFund-Me/Qbot) `docs/` folder
(strategy taxonomy + classic/intelligent strategy write-ups), then **re-mapped onto this
system's primitives**. Qbot text is CC-BY-NC-SA; nothing here is copied — every strategy is
re-expressed as a structured card against *our* factor catalog, profiles, engines, and PIT/seal
governance. Attribution is retained per card.

---

## Why this exists

Qbot is broad (multi-asset, live trading, 40+ strategy write-ups) but has **no research-integrity
machinery**. Our system is the opposite: deep PIT-safety / sealed-OOS / governance, but a *narrow*
catalogue of strategy archetypes actually exercised in research. This KB imports Qbot's **strategy
breadth** as a research backlog without importing its (absent) methodology discipline.

The goal is operational: a future research session should be able to open one **strategy card**,
see exactly which of our factors / profiles / engines implement it, what the PIT traps are, and
whether it is already covered — then run it through the orchestrator. This is a *map from idea →
our machinery*, not a tutorial.

---

## How to use this KB (research protocol)

1. Start from [00_strategy_taxonomy.md](00_strategy_taxonomy.md) to place an idea in the
   three-category frame (trend-following / relative-value / event-driven) and check its **market-regime
   suitability** before spending compute.
2. Open the matching card in [01_classic_strategies_catalog.md](01_classic_strategies_catalog.md)
   or [02_intelligent_methods_and_research_backlog.md](02_intelligent_methods_and_research_backlog.md).
3. Read the card's **"Our-system path"** and **"PIT / leakage traps"** rows. The traps row is the
   load-bearing part — Qbot's versions have no PIT guard; ours must.
4. Implement through the named profile (never a bespoke `workspace/scripts/` loader — that is the
   exact lineage that produced the val_heavy lookahead, see [CLAUDE.md](../../CLAUDE.md) §3 and the
   `pit_lookahead_prevention_plan` under [../temp_plan/](../temp_plan/)).
5. Anything novel goes through the gated lifecycle: discovery profile → `hypothesis_validation` →
   sealed OOS → promotion gate. A strategy card is a *hypothesis source*, never a shortcut past the gates.

---

## Card schema (every strategy is written in this shape)

| Field | Meaning |
|---|---|
| **Category** | trend-following / relative-value / event-driven (taxonomy §) |
| **Core logic** | the one-paragraph mechanism |
| **Signal / factors** | mapped to our `factor_library` catalog names where they exist |
| **Universe / rebalance / hold** | concrete parameters |
| **Regime fit** | when it works / breaks (bull / bear / sideways) |
| **Our-system path** | profile + engine + factors that implement it here |
| **PIT / leakage traps** | the specific lookahead risks our discipline must close |
| **Coverage** | ✅ have · 🟡 partial · ⬜ gap (research backlog) |

---

## Index

- [00_strategy_taxonomy.md](00_strategy_taxonomy.md) — the three-category spine, secondary axes
  (index-exposure, frequency), CTA subtypes, and the regime-suitability matrix.
- [01_classic_strategies_catalog.md](01_classic_strategies_catalog.md) — strategy cards for the
  classic archetypes (multi-factor selection, small-cap, Fama-French, index enhancement, Alpha
  hedge, RSRS timing, Bollinger mean-reversion, dual-MA, grid, pairs trading, 4433 fund rotation,
  limit-up board-opening).
- [02_intelligent_methods_and_research_backlog.md](02_intelligent_methods_and_research_backlog.md) —
  ML/model-zoo, Alpha-101/191, automated factor generation (DEAP/genetic), RL timing, LLM signals,
  alphalens-style evaluation — and the **concrete research backlog** mapping each gap to one of our profiles.

---

## Maintenance

This is durable research guidance under `Knowledge/`, not a rule file. Update a card when:
- a strategy archetype gets a real run in our system (flip Coverage, link the run dir / registry rows),
- our factor catalog gains a factor that implements a card's signal,
- a new archetype worth tracking appears.

Keep the **PIT / leakage traps** row honest — it is the only part of this KB that protects research integrity.
