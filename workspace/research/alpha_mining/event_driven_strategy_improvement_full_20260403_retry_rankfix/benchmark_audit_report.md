# Benchmark Audit Report

## Summary
- Benchmark: `000001.SH`
- Source file: `E:\量化系统\data\market\index\index_000001.SH.parquet`
- Audit time: `2026-04-03 20:26:19`
- Passed: `True`

## Coverage
- Row count: `4,410`
- Start date: `2008-01-02`
- End date: `2026-02-27`
- Duplicate trade_date rows: `0`
- Missing open trade dates vs calendar: `0`

## Null Checks
- null trade_date: `0`
- null open/high/low/close/pre_close: `0` / `0` / `0` / `0` / `0`

## Price Validity
- non-positive open/high/low/close/pre_close: `0` / `0` / `0` / `0` / `0`
- high < low rows: `0`
- close outside [low, high] rows: `0`

## pct_chg Consistency
- max abs diff between pct_chg and recalculated close/pre_close change: `0.000050`
- rows with abs diff > 0.01 pct points: `0`

## Verdict
- The benchmark is acceptable for formal strategy evaluation.
