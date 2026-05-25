# Provider Instruments

- `all.txt`: raw provider instrument coverage emitted by the Qlib dump step.
- `all_stocks.txt`: A-share stock universe with the repo's 90-day IPO lag preserved for research compatibility.
- `csi300.txt`, `csi500.txt`, `csi1000.txt`: monthly-snapshot PIT approximations derived from `index_weights`.
- `st_stocks.txt`: authoritative ST interval sidecar rebuilt from `stock_st_daily` plus the pre-2016 `namechange` fallback.
