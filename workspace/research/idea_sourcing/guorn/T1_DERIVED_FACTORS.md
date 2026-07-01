# T1 derived factors — local reproductions built (2026-07-01), 果仁 verification PENDING (Chrome MCP down)

Tier-1 of the "cover the remaining 果仁 factors" plan: factors derivable from data already on disk (no new
ingestion). All local reproductions are BUILT + sanity-validated below. **Verification (果仁 web export → comparator
`--local-series`/`--local-expr` → top-K) is DEFERRED until the Claude-in-Chrome MCP reconnects.** NON-FORMAL.

Enabler added: `guorn_factor_parity.py --local-series <parquet>` (code+value) — feeds any pre-computed factor
through the existing coverage + pointwise + top-K machinery (commit c8fe2a9).

## Verification runbook (run each when Chrome is back)

Broad universe 排除ST排除科创, ONE rank condition = the 果仁 indicator, 选股日期 2025-12-31, export → rename
`果仁_20251231_排除ST排除科创_排名-<indicator>.xlsx`, then:

| # | 果仁 indicator | books | local reproduction (BUILT + sanity ✓) | verify command |
|---|---|---|---|---|
| 5 | **上市天数** | 7 | `guorn_days_listed.py --date 2025-12-31` → `days_listed_cal_20251231.parquet` (calendar-days; 000001=12691 ✓). **cal is the primary caliber** | `guorn_factor_parity.py --xlsx <exp> --date 2025-12-31 --local-series workspace/outputs/guorn_derived/days_listed_cal_20251231.parquet --guorn-col 上市天数` |
| 32 | **交易天数** | 1 | same helper → `days_listed_trd_20251231.parquet` (trading-days; ⚠ capped at 4376 for pre-2008 listings — provider cal starts 2008 → likely mismatches old names) | `… --local-series …/days_listed_trd_20251231.parquet --guorn-col 交易天数` |
| 23 | **贝塔N日(000001,250)** | 2 | `guorn_beta.py --date 2025-12-31 --n 250` → `beta_000001_sh_250_20251231.parquet` (Cov(r_stk,r_idx)/Var(r_idx), idx=上证指数; sample mean 1.11/median 1.09 ✓). Full-universe run may be slow → background | `… --local-series …/beta_000001_sh_250_20251231.parquet --guorn-col 贝塔N日(000001,250)` |
| 21 | **历史贝塔** | 2 | try the same `guorn_beta.py` output FIRST; if it diverges, 果仁's 历史贝塔 likely uses a different index (沪深300?) or window — re-run `--index 000300_sh --n <?>` | (as above, with the winning params) |
| 51 | **ATR%收盘价N日(20)** | 1 | qlib expr (lag-0), sanity median 1.56% ✓: `Mean(Greater(Greater($high-$low, Abs($high-Ref($close,1))), Abs($low-Ref($close,1))), 20)/$close` | `… --local-expr 'Mean(Greater(Greater($high-$low,Abs($high-Ref($close,1))),Abs($low-Ref($close,1))),20)/$close' --lag 0 --guorn-col ATR%收盘价N日(20)` |
| 47 | **EpsTTMGr%** | 1 | qlib expr (lag-1); ⚠ **unstable-denominator family** — VALUE reproduces (sanity ✓, BYD −34%/恒瑞 +35% match) but expect **top-K divergence** like RnDTTMGr%PY | `… --local-expr '(Ref($basic_eps_sq_q0,1)+Ref($basic_eps_sq_q1,1)+Ref($basic_eps_sq_q2,1)+Ref($basic_eps_sq_q3,1)-(Ref($basic_eps_sq_q4,1)+Ref($basic_eps_sq_q5,1)+Ref($basic_eps_sq_q6,1)+Ref($basic_eps_sq_q7,1)))/Abs(Ref($basic_eps_sq_q4,1)+Ref($basic_eps_sq_q5,1)+Ref($basic_eps_sq_q6,1)+Ref($basic_eps_sq_q7,1))' --lag 1 --guorn-col EpsTTMGr%` |

## Expected outcomes (pre-registered)
- **上市天数 / 交易天数 / beta / ATR** — DETERMINISTIC or stable-denominator → expect clean top-K (like 总市值 / 250日涨幅). The only open caliber question is per-factor (cal-vs-trd days; beta index/window; ATR raw-vs-复权 — used raw, matches 振幅 convention).
- **EpsTTMGr%** — unstable near-zero-base denominator → expect value-exact / top-K-diverged (the settled pattern; book-immaterial, 1 book). Document, don't chase.

## Scripts
- [guorn_days_listed.py](../../scripts/guorn_days_listed.py) — 上市天数 (cal) + 交易天数 (trd)
- [guorn_beta.py](../../scripts/guorn_beta.py) — 贝塔N日 / 历史贝塔
- ATR% + EpsTTMGr% are direct `--local-expr` (no helper)
