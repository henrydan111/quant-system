# Backtest Engine Rules

These rules apply to everything under `src/backtest_engine/`.

## 1. Engine Roles

- `VectorizedBacktester` is for fast screening and signal comparison.
- `EventDrivenBacktester` is for realistic execution modeling, JoinQuant parity work, and corporate-action-aware validation.
- Keep the distinction clear in both code and documentation.

## 2. Signal Pipeline Discipline

- Preserve the four-layer pipeline: factor computation -> universe selection -> signal construction -> execution.
- Universe membership and screening must be handled with masks, not row drops.
- Do not encode tradability rules directly into factor values or final signals.
- Keep ranking logic separate from execution constraints.

## 3. Vectorized Research Defaults

Even though some current code defaults are convenience-oriented, research code should set execution parameters explicitly and prefer:

- `deal_price='open'`
- `only_tradable=False`
- `forbid_all_trade_at_limit=True`

Also keep `limit_threshold` aligned with the actual segment mix being tested and use underscore benchmark codes such as `000300_SH`.

## 4. Event-Driven Realism

- Preserve PIT access through `QlibDataFeeder`.
- Keep T+1 behavior, board-specific limits, dual-price infrastructure, and date-aware taxes/corporate actions intact.
- Prefer `preload_features()` when repeated field access would otherwise trigger expensive repeated Qlib calls.

## 4a. JoinQuant Deployment Parity (added 2026-05-22)

JoinQuant is the production deployment medium. The event-driven engine defaults are JoinQuant-aligned so a local backtest with default settings predicts a JoinQuant backtest:

- **Slippage**: `Exchange()` defaults to `JOINQUANT_DEFAULT_SLIPPAGE` = `FixedSlippage(0.0003)` (≈ 0.3 bps on a ¥10 stock — matches JoinQuant's standard `FixedSlippage(3/10000)`). For the prior 10-bps conservative default, pass `slippage_model=CONSERVATIVE_SLIPPAGE_10BPS` explicitly. **Never inline `PctSlippage(0.0003)` thinking it matches JoinQuant — it differs by ~10×**; use the named constants.
- **Costs**: `CostConfig()` defaults to the JoinQuant `OrderCost` equivalent (close_tax 0.1% constant, no 2023-08-28 cut, no transfer fee). For the actual Chinese exchange rules use `CostConfig.realistic_china()` explicitly.
- **Fill model**: `EventDrivenBacktester.run(fill_mode=...)` accepts:
  - `'open_close'` (default) — before_market_open → OPEN, on_bar → CLOSE; closest to live execution.
  - `'jq_daily_avg'` — both phases fill at `(open + close) / 2`; matches JoinQuant's daily-backtest fill model (API doc line 1252).
- **NaN-safe sizing**: when strategy code estimates post-sell cash for the no-trim sizing pattern, use `Portfolio.available_cash_after_sells(sold_codes, prices)` — it falls back to `avg_cost` for NaN/missing/non-positive prices. The same NaN-safe contract holds for `Portfolio.safe_total_value(prices)` (alias of `total_value`, which is already NaN-robust via `market_value`'s fallback). This pattern prevents the v18 stuck-in-cash bug (a suspended position's NaN prev-close poisoning a naive sum).
- **Regression tests**: `tests/backtest_engine/test_joinquant_parity.py` locks the contract.

## 5. Analysis Boundary

Performance summaries, trading statistics, and report generation belong in `src/result_analysis/`. Do not duplicate that logic inside the backtest engines.
