---
trigger: model_decision
description: apply these rules when user's prompt involves signal construction, backtesting, strategy building, or portfolio execution
---

# Signal Construction and Backtesting

Rules for building quantitative signals and running backtests. Applies to factor-based, ML-based, event-driven, and hybrid strategies. Full reference with templates and corner cases lives in `workspace/research/signal_backtesting_guide.md`.

Use `VectorizedBacktester` for rapid signal screening and `EventDrivenBacktester` for realistic execution studies, JoinQuant parity work, and corporate-action-sensitive validation.

## 1. Pipeline Architecture

- Every backtest must follow a strict four-layer pipeline: factor computation -> universe selection -> signal construction -> execution.
- Keep concerns separated. Factor values belong in Layer 1, eligibility in Layer 2, desirability in Layer 3, and tradability in Layer 4.

## 2. Factor Computation (Layer 1)

- Compute factors on the full market before sub-universe filtering when lookbacks are involved.
- Use PIT-correct Qlib features for raw data access.
- Preserve awareness that `D.features()` returns `MultiIndex(instrument, datetime)`.
- Avoid chunking workflows that break cross-sectional ranks or time-series lookbacks unless the methodology explicitly supports it.

## 3. Universe Selection (Layer 2)

- Universe membership should be represented as boolean masks, not row drops.
- Layer screening conditions on top of membership instead of destroying rows.
- Do not filter on tradability at this stage; suspended names still need valid factor and ranking context.

## 4. Signal Construction (Layer 3)

- Rank within the intended sub-universe, not the full market.
- Forward-fill signals within membership where the methodology requires continuity.
- Export final signals in the index order expected by the consumer engine.
- Use signal values that are comparable across dates.

## 5. Execution (Layer 4)

- Never encode tradability logic directly in the signal.
- Set `VectorizedBacktester.run()` parameters explicitly on serious research runs.
- Preferred research settings are:
  - `deal_price='open'`
  - `only_tradable=False`
  - `forbid_all_trade_at_limit=True`
- Current vectorized code defaults are older convenience values (`deal_price='close'`, `forbid_all_trade_at_limit=False`). Do not rely on them.
- Keep `limit_threshold` aligned with the segment mix being tested.
- Use realistic transaction costs.

## 6. Rebalancing and Holding Period

- `hold_thresh` controls the minimum holding period; it is part of execution, not factor design.
- Even for weekly or monthly strategies, keep the signal pipeline daily so the engine can respond to suspensions, limits, and other intra-period events.

## 7. Banned Anti-Patterns

1. Filtering before factor computation
2. Dropping rows that should remain available for forward-fill
3. Encoding tradability inside the signal
4. Mixing ranking scope with execution filters
5. Omitting signal forward-fill when the methodology requires continuity

## 8. Validation Before Trust

- Check signal coverage.
- Verify there is no future-data leakage.
- Ensure costs are non-zero and execution assumptions are realistic.
- Match price-limit assumptions to the market segment.
- Cross-check against reference strategies when parity is the goal.
