# 果仁 indicator → local field mapping + parity status (validated ledger)

> **Purpose.** The hard-won layer the raw-formula docs do NOT have: which LOCAL provider field/
> expression reproduces each 果仁 indicator, its **validated** parity status, the **corrections** to
> the auto-generated formula docs, and the reusable **conventions**. Built from the 果仁-parity ladder
> (rungs 1–4, 2026-06-22..23). Machine-readable sidecar: [guorn_local_field_mapping.json](guorn_local_field_mapping.json).
>
> **This file is CANONICAL; the JSON is a derived snapshot — keep them in sync.**
>
> **Raw 果仁 formulas (do NOT duplicate here):** [indicator_reference_auto.md](indicator_reference_auto.md)
> (99 custom + 14 builtin), [guorn_aichat_indicator_defs.md](guorn_aichat_indicator_defs.md) (builtins:
> ILLIQ / 中性化 / 朝阳永续 / 评级), [内联公式85条拆解.md](内联公式85条拆解.md) (85 inline).
>
> **Scope discipline (rule #10).** Only indicators ACTUALLY validated against 果仁 holdings get a
> `status` + parity. Mappable-but-unvalidated ones are listed separately and explicitly marked. The
> ~75 redundant/irreducible indicators are NOT mapped (see §5). NON-FORMAL parity diagnostics; not a
> formal artifact.

---

## 0. Reusable conventions (apply to EVERY indicator)

| convention | value | evidence |
|---|---|---|
| **Display lag** | 果仁 shows each factor as of the **SIGNAL date = T−1** (the trading day BEFORE the holding 开始日期), NOT the buy date. | 4-way: 总市值 lag1 0.52% vs lag0 0.98%; BP/乖离率/ILLIQ all prefer lag1 |
| **成交额 (亿元)** | `$amount` is in 千元 → 成交额(亿元) = `$amount / 1e5` | ILLIQ unit reconciliation |
| **总市值 unit** | `$total_mv` is in 万元; 果仁 `总市值(亿) × 1e4` = 万元 | 总市值 decomp 0.52% |
| **BP scale** | equity(元) / total_mv(万元) ⇒ ×1e4 to land on 果仁's displayed BP | scale-detect = 10000 |
| **后复权** | `adjc = $close × $adj_factor`. For a price **RATIO** (e.g. 250日涨幅) this is 复权-base-INVARIANT (后复权-present ≡ 前复权-as-of). raw close is wrong. | raw 26% vs adj 5.5% |
| **single-quarter** | `$<field>_sq_q0` = latest single quarter; `_sq_q1.._q4` = prior quarters; **TTM = Σ(_sq_q0.._q3)**, 去年同期 single quarter = `_sq_q4`. Provider-materialized bins, read via `D.features` (factor-library path), NOT raw `pit_ledger` columns. | rung-2/4 |
| **PIT gate timing** | gate the fundamental **as-of the rebalance day (lag-0)** — effective_date-safe because the provider anchors `effective_date > disclosure` STRICTLY (§3.2), matching 果仁's 公告日 selection. | rung-2 GPT R1 (0 flips) |

---

## 1. Validated mapping (penny-exact / structure-exact)

All parity = holding-level value vs 果仁's displayed factor across the 65 books, at the signal-date lag.

| 果仁 indicator | 果仁 formula | local expression | status (parity, n) | rung |
|---|---|---|---|---|
| **总市值** | 总市值 | `$total_mv` (万元) | ✅ display-precision (0.52% med, 97% w/5%, n=97k) | 1,4 |
| **流通市值** | 流通市值 | `$circ_mv` | ✅ (rung-1 portfolio reproduction) | 1 |
| **净利润(单季)** | 净利润(单季) | `$n_income_sq_q0` ÷1e4=万元 | ✅ **penny-exact** (96.1% w/0.1%, med 0.0000, n=14.7k) | 2 |
| **业绩预告净利润QGr%PYQ_v1** | mid=(预告净利min+max)/2; single_q_fc=mid−income_cum[FY,Q−1]; growth vs py_single | `$forecast__np_q_yoy` | ✅ (4.37e-05 med, 92.9% w/1%, 98.2% sign, n=38.4k) | 3 |
| **GrossProfit%AssetsQ** | (营收单季−营业成本单季)/资产总计单季 | `($revenue_sq_q0 − $oper_cost_sq_q0) / $total_assets_q0` | ✅ penny-exact (96.3% w/1%, 99.98% sign, n=262k) | 4 |
| **SalesQGr%PY** | (营收单季[0]−营收单季[4])/abs(营收单季[0]) | `($revenue_sq_q0 − $revenue_sq_q4) / abs($revenue_sq_q0)` | ✅ penny-exact (95.8% w/1%, 99.3% sign, n=124k) | 4 |
| **负债资产率** | 总负债/总资产 | `$total_liab_q0 / $total_assets_q0` | ✅ penny-exact (98.0% w/1%, 100% sign, n=48k) | 4 |
| **OPCFNPDiff%NP** | (经营现金流TTM−净利润TTM)/净利润TTM | `(Σ$n_cashflow_act_sq_q[0..3] − Σ$n_income_sq_q[0..3]) / Σ$n_income_sq_q[0..3]` | ✅ penny-exact (92.0% w/1%, 99.6% sign, n=63k) | 4 |
| **BP** | 归属母公司股东权益合计/总市值 | `$total_hldr_eqy_exc_min_int_q0 / $total_mv` (×1e4, lag T−1) | ✅ 0.66% med (66% w/1%, 96% w/5%, n=97k) — residual = 总市值 2-dec display-round + equity PIT-boundary | 4 |
| **市盈率** | 市盈率TTM | `$pe_ttm` (lag T−1) | ✅ 0.9% med (54% w/1%, 92% w/5%, n=19k) — residual = price signal-day | 4 |
| **ILLIQ(5)** | MA(股价振幅/成交额(亿元), 5) | `MA( ((high−low)/prev_close) / ($amount/1e5), 5 )` (lag T−1, avg-of-ratios) | ◑ structure-exact (12.5% w/0.1%); residual ~0.86× = undocumented platform sub-detail | 4 |

Legend: ✅ penny/structure-exact (residual = display/PIT-boundary) · ◑ structure confirmed, sub-detail residual.

---

## 2. Data-validated, residual = reconstruction convention (NOT a data error)

The underlying close/市值 data is penny-exact (via 总市值); the residual is 果仁's long-window
counting convention, proven NOT to be data / 复权 / corporate-action.

| 果仁 indicator | local expression | residual | proof it's not a data fault |
|---|---|---|---|
| **250日涨幅** | `adjc / adjc.shift(250) − 1` (lag 0) | ~5.5% med, signs 97% | window N=250 is a sharp confirmed min; ratio 复权-invariant; **no-corp-action subset EQUALLY off (5.45%)** → residual = N-day lookback window-MEMBERSHIP counting (果仁 suspension/calendar vs `.shift(250)`) |
| **N日乖离率(120)** | `(adjc − MA(adjc,120)) / MA(adjc,120)` (lag 1) | ~6.8% med, signs 95% | **no-corp-action subset EQUALLY off (8.2%, n=80k)** → same root cause (MA window-membership counting) |

---

## 3. Un-validatable from the holdings display

| 果仁 indicator | why | note |
|---|---|---|
| **股价振幅%当日成交额10日** | 果仁 **displays 0.00** for every holding (true value ~2e-6 rounds to zero at 2 decimals) | local formula `MA((high−low)/prev_close / $amount, 10)` is provably CORRECT (matches 果仁's published formula), but parity is meaningless at 2-dec display. ⚠ Earlier "2.4e-05 penny-exact" claim was WRONG (it was a degenerate near-zero match). |

---

## 4. Corrections to the auto-generated formula docs (errors that would mis-build a factor)

| doc | says | actually | impact if trusted |
|---|---|---|---|
| guorn_aichat_indicator_defs.md | ILLIQ = `Sum(\|1日涨幅\|/成交额(亿元),N)/N` | numerator is **股价振幅 (high−low)/prev_close**, NOT `\|1日涨幅\|` (the desc "每亿元成交额引起的股价振幅" is literal) | \|return\| gives gf/mine 1.85 (IQR 1.5–2.3); 振幅 gives 0.86 (IQR 0.81–0.94) + 12.5% within 0.1% |
| indicator_reference_auto.md (builtin BP) | `归属母公司股东权益合计/总市值` (correct) | the field is **exc_min_int** (parent-only), trivially mis-mapped to inc_min_int (total) | inc_min_int → 5.9% vs exc_min_int → 0.66% |
| (rung-2 finding) | plain `净利润(单季)` | = **TOTAL** single-quarter net profit (`$n_income_sq_q0`), NOT 归母 (`$n_income_attr_p_sq_q0`) | 归母 gave only 45.8% within 0.1% |

---

## 5. NOT mapped (by design) — redundant / irreducible / out-of-scope

- **Redundant** (reuse already-validated fields; path proven): CoreProfitQ & its `%PY`/`%PQ` growths,
  EPCoreProfitQ, EBITDAQ, all revenue/profit/asset growth-rate transforms, ROETTMDiffPQ, etc.
- **Irreducible** (cannot penny-match 果仁): 中性化 family (`HNeutralize`/`HNeutralizeMI` — 果仁's exact
  industry regression), 壳价值 (`SSlopeXY` AH-premium regression), 退市风险 screens (预期ST2021 / 风险预警25版
  / 重大违规 / 国九条 — no local data), 朝阳永续 预期 (预期净利润 / 评级机构数 — report_rc, validated vs
  **JoinQuant** not 果仁, different vendor), 大盘择时 (涨停/跌停家数比例 — market-aggregate), ETF selectors
  (`TICKER()=...`), 未来20日新增流通股 (PIT lockup schedule, no clean feed — realized shares = lookahead).

---

## 6. Coverage tracker (data paths)

| data path | status | via |
|---|---|---|
| 市值 (total/circ) | ✅ validated | 总市值/流通市值 |
| income statement (营收/营业成本/净利润 single-q + TTM) | ✅ penny-exact | rung-2/4 |
| balance sheet (总资产/总负债/归母权益) | ✅ penny-exact | rung-4 |
| cashflow (经营现金流净额) | ✅ penny-exact | OPCFNPDiff%NP |
| valuation (pe_ttm) | ✅ validated | 市盈率 |
| forecast 业绩预告 (event-PIT) | ✅ validated | rung-3 |
| price/volume (close/high/low/amount/adj) | ✅ validated | 总市值 + momentum |
| **分红 / 股息 (dividends)** | ⬜ OPEN | DivGrPY% / 股息率TTM / 近三年分红 |
| **股东数 (holder_number)** | ⬜ OPEN | 股东数下降率 [10]/[55] |
| **研发费用 ($rd_exp)** | ⬜ OPEN | RnD% factors |
| **总股本 (share count)** | ⬜ OPEN | SharesAvgGr%PY |
| **expense lines (管理/销售/财务费用)** | ⬜ OPEN | CoreProfitQ |
| **折旧摊销 (D&A)** | ⬜ OPEN | EBITDAQ / FCFQ_重算 |

The 6 OPEN paths are the only candidates for a future targeted "rung-5 field sweep" — everything else
is validated, redundant, or irreducible.

---

*Sources (all NON-FORMAL, workspace/scripts/): `_rung4_field_parity.py` (BP→exc_min_int),
`_rung4_reverse_engineer.py`, `_rung4_decompose.py`, `_rung4_illiq_bp_final.py`,
`_rung4_momentum_diag.py`; rung-2 `_validate_pit_netprofit_vs_guorn.py`; rung-3
`_provider_read_audit_forecast.py`. Full history: memory `project_guorn_parity` + project_state.md.*
