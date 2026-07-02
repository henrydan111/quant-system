# T1 derived factors — local reproductions built + 果仁 verification COMPLETE (2026-07-01)

Tier-1 of the "cover the remaining 果仁 factors" plan: factors derivable from data already on disk (no new
ingestion). All local reproductions are BUILT + sanity-validated below, and **果仁 web-export verification is now
COMPLETE (2026-07-01, Chrome MCP session)** — see the OUTCOMES table below and campaign rows #5/#32/#23/#21/#51/#47
in [guorn_web_validation_campaign.md](guorn_web_validation_campaign.md). NON-FORMAL.

## OUTCOMES (2026-07-01, broad 排除ST排除科创 4412 @2025-12-31)

| # | factor | verdict | key caliber finding |
|---|---|---|---|
| 5 | 上市天数 | ✅ VALUE-EXACT (EXACT 100%, ρ 1.000, top-K 100/100/100) | 果仁 = calendar days INCLUSIVE of listing day → patched `guorn_days_listed.py` cal branch `+1` (proven uniform +1) |
| 23 | 贝塔N日(000001,250) | ✅ penny-exact (medRelErr 0.20%, ρ 0.999, top-K 80/90/100) | caliber = **SIMPLE returns of 后复权 close, idx 上证指数** → fixed `guorn_beta.py` log-raw→simple-后复权 |
| 21 | 历史贝塔 | ✅ verified / ◑ structure-exact (medRelErr 1.13%, ρ 0.998, top-K 80/100/95) | **DISCOVERED: beta vs 沪深300 (000300), N=250, simple 后复权** (NOT 上证指数) |
| 51 | ATR%收盘价N日 | ◑ rank-faithful, precision-capped (within-0.01 99.9%, ρ 0.966) | 果仁 = custom ATRN = `ATR(N)/后复权收盘价`; 2dp export (12 buckets) blocks value/top-K; simple-MA not Wilder; verified N=50→transfers N=20 |
| 32 | 交易天数 | ✗ diverged (top-K 0/0/0, ρ 0.986) | 果仁 = **actual traded-bar count (suspension-EXCLUDED)**, proven 4/4; + 2008 data-start cap pins pre-2008 names → oldest top-K unrecoverable |
| 47 | EpsTTMGr% | ✗ composite NOT reproduced — but the FIELD ✅ (field-probe 2026-07-01) | **每股收益 = TTM basic EPS, reproduces** (`Σ$basic_eps_sq_q0..3`, ρ 0.9975, med 1.39%; 茅台 71.75 vs 果仁 71.89, 万科A −5.02 vs −4.99) → NOT a field-caliber gap. The COMPOSITE EpsTTMGr% is **degenerate on 果仁's side**: its published values don't follow from its own formula applied to the reproduced field — 万科A EPS collapsed (TTM −1.64→−5.02) yet 果仁 shows +8.4% "growth"; 茅台 −198% implies a nonsensical base. Cause = unstable near-zero denom (67% \|v\|>100%) + negative-base `abs()`. 1 book, don't chase |

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

## Expected outcomes (pre-registered) — vs ACTUAL (2026-07-01)
- **上市天数 / 交易天数 / beta / ATR** — pre-registered "DETERMINISTIC/stable → clean top-K". ACTUAL: **上市天数 ✅** (after +1 inclusive-day caliber); **beta ✅×2** (after fixing the return caliber to simple-后复权, and DISCOVERING 历史贝塔 = 沪深300 not 上证); **ATR ◑** (rank-faithful but value/top-K precision-capped by 果仁's 2-decimal export — NOT the raw-vs-复权 question the note anticipated; raw≈后复权 both fine, and 果仁 uses simple-MA not Wilder); **交易天数 ✗** (the open "cal-vs-trd" question resolved to a deeper caliber: 果仁 counts actual traded bars excl. suspension, and the 2008 provider-calendar start caps pre-2008 names — unrecoverable).
- **EpsTTMGr%** — pre-registered "value-exact / top-K-diverged". ACTUAL: **✗ worse than expected** — value does NOT reproduce even on stable-denom names (茅台 果仁 −1.98 vs mine +0.09); the "BYD −34/恒瑞 +35 match" in the runbook was measuring the LOCAL expr's own values, never a 果仁 comparison. **Field-probe (2026-07-01) then isolated it**: the 每股收益 FIELD is NOT opaque — 果仁 每股收益 = TTM basic EPS and it reproduces (`Σ$basic_eps_sq_q0..3`, ρ 0.9975; 茅台 71.75 vs 果仁 71.89). So the irreproducibility is NOT the field but a **degenerate 果仁-side composite formula** (万科A's EPS collapse −1.64→−5.02 shown by 果仁 as +8.4% "growth"; 茅台 −198% from a nonsensical base) amplified by the unstable near-zero denominator. Book-immaterial (1 book). Documented, not chased.

## Scripts
- [guorn_days_listed.py](../../scripts/guorn_days_listed.py) — 上市天数 (cal) + 交易天数 (trd)
- [guorn_beta.py](../../scripts/guorn_beta.py) — 贝塔N日 / 历史贝塔
- ATR% + EpsTTMGr% are direct `--local-expr` (no helper)
