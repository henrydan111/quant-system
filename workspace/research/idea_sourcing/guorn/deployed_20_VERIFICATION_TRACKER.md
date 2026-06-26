# 果仁 deployed-20 verification campaign — tracker

> **User directive (2026-06-24):** verify the 20 LIVE-DEPLOYED guorn strategies
> ([deployed_portfolio_20260624.json](deployed_portfolio_20260624.json), ~¥9.93M, ~5%/strategy) as the
> PRIORITY of the parity ladder. Each = a faithful reproduction validated vs its 果仁 xlsx ground-truth
> BEFORE formalizing (the #59 rung-6 methodology). 果仁 = trusted benchmark; the LOCAL layer is under test.
>
> Recipes: [deployed_20_recipes.md](deployed_20_recipes.md) (extracted from guorn_strategies_master.json).
> Factor mapping: [guorn_local_field_mapping.md](guorn_local_field_mapping.md) (rung 1-5 validated).
> Ground-truth: `Knowledge/果仁回测结果/NN_*.xlsx` (11 sheets incl. per-period holdings).

## Triage — by factor availability (rung 1-5 validated base)

🟢 = all factors in the validated base (statements/市值/价量/股息/forecast) → reproducible NOW
🟡 = 1 gap (light 中性化 / 1 rating / EBITDAQ-D&A) → reproducible with documented approximation OR 1 small unlock
🔴 = heavy irreducible (中性化-stack / 壳价值 / AH溢价) OR not-yet-materialized data (analyst CONSENSUS 预期*) OR different domain (funds)

| # | strategy | cat | xlsx | 果仁 年化/夏普 | triage | gating factor(s) | status |
|---|---|---|---|---|---|---|---|
| 1 | sm_01_成长动量 | sm | 01 | 57.2% / 1.68 | 🟢 | 市值+CoreProfitQGr+EpsExclXorQGr+ROETTMDiffPQ+mom | **✅ VERIFIED 2026-06-26** my **+49.09** vs 果仁 +57.2 (**−8.1pp**); overlap 40.8%/58.6%. +涨停不卖 +8.1pp + industry-fix +1.5pp. Residual = 果仁 microcap-fill optimism (rung-1). [verify01_FINDINGS.md](verify01_FINDINGS.md) |
| 2 | sm_01_成长_v1 | sm | 05 | 58.2% / 1.58 | 🟢 | 成长 (−mom +业绩快报) | **✅ VERIFIED 2026-06-26** my **+50.11** vs +58.2 (**−8.1pp**); overlap 47.9%/69.6%. Reuses #1 cache (6 shared factors); 业绩快报(express w=1) OMITTED (unmaterialized). |
| 6 | sm_01_成长高贝塔@TMT_v1 | sm | 06 | 60.3% / 1.44 | 🟢 | 成长+beta+TMT (−预期营收−快报) | **✅ VERIFIED 2026-06-26** my **+53.73** vs +60.3 (**−6.6pp**, smallest); vol 38.8≈39.2, MDD −51.5≈−51.9 (near-exact); overlap 45.9%/67.2%. beta(000001,250)+研发销售比率 computed; 预期营收(consensus)+快报 OMITTED. |
| 4 | sm_GARP_illiq | sm | 09 | 49.6% / 1.54 | 🟢 | SalesQGr+CoreProfit+ILLIQ (all rung-4/5) | pending |
| 5 | sm_双创研发强度_v1 | sm | 10 | 62.7% / 1.54 | 🟢 | 市值+ILLIQ+R&D (rung-5) | pending |
| 15 | 成长_双创_GARP@周期_v2 | 成长 | 44 | 43.4% / 1.13 | 🟢 | GARP (= #4 on 创业板) | pending |
| 7 | value_红利低波_v2 | value | 19 | 29.7% / 1.32 | 🟡 | 股息率✓ + 中性N日换手率 (1 light neutral) | pending |
| 8 | value_红利低波_央企_v1 | value | 20 | 32.1% / 1.27 | 🟡 | 股息率✓ + 预期股息率 (1 consensus) | pending |
| 9 | value_红利低波_重股息_v1 | value | 21 | 33.3% / 1.27 | 🟡 | 分红波动率 + 预期DivAGrPY% (1 consensus) | pending |
| 18 | ST_大市值_v3 | ST | 53 | 55.5% / 2.00 | 🟢 | 市值+CoreProfitQ+业绩预告✓ + **评级机构数(NEW=$report_rc__n_active_orgs)** | **✅ P5 PROOF 2026-06-27** my **+26.5** vs +55.5 (−29pp); overlap **34.5%/44.7%** (faithful, validated band) → **the published report_rc 评级机构数 field WORKS end-to-end**. Return gap = ST limit-up execution (2015 −84/2021 −190pp[果仁+242.7], rung-1 amplified) + omitted exits/退市风险 (2018), NOT a field/selection defect. ST = extreme RETURN-parity target; clean SELECTION proof. [guorn_verify_18_stbigcap.py](../../../scripts/guorn_verify_18_stbigcap.py) |
| 16 | 成长_隔夜动量@周期 | 成长 | 45 | 27.8% / 0.81 | 🟡 | 隔夜动量✓+业绩预告✓ + 评级机构数 | pending |
| 17 | 成长_高波@周期 | 成长 | 48 | 29.5% / 0.72 | 🟡 | 业绩预告✓ + 评级调高家数 | pending |
| 12 | value_创业板sm_v1 | value | 24 | 41.8% / 1.14 | 🟡 | GrossProfit✓ + EBITDAQ%EV + BP带壳01 + 1中性化 | pending |
| 11 | value_FCF_非企sm_v2 | value | 23 | 29.0% / 1.05 | 🔴 | 6× FCFQ_重算 (needs 处置FIOLTA[未物化]+D&A单季) | pending |
| 14 | 成长_净利润断层_v2 | 成长 | 43 | 48.4% / 1.62 | 🔴 | 业绩预告✓ − 预期净利润Q (consensus, 未物化) | pending |
| 13 | 成长_机构预期@周期_v1 | 成长 | 42 | 54.1% / 1.27 | 🔴 | 预期营收/盈利2年复合 (consensus-HEAVY) + HNeut | pending |
| 10 | value_AH_低溢价GARP_v1 | value | 22 | 30.4% / 1.06 | 🔴 | AH股溢价率 (w=4 dominant; needs H股价) | pending |
| 3 | sm_大制造GARP_v3 | sm | 07 | 62.0% / 1.71 | 🔴 | 8× 中性化-stack + BP带壳 + EBITDAQ | pending |
| 19 | MultiA_风险平价_v1 | MultiA | 31 | 13.8% / 0.60 | 🔴 | fund/ETF rotation (ATR/vol/涨幅/sortino) — 别域 | pending |
| 20 | MultiA_动量18 | MultiA | 29 | 32.6% / 1.14 | 🔴 | fund/ETF momentum (20日涨幅) — 别域 | pending |

## 成长 cluster — VERIFIED (2026-06-26): #1, #2, #6

All three reproduced faithfully through the daily model-II engine (0.2%/side, 涨停不卖, total return) vs their
果仁 xlsx ground-truth. Harnesses: [guorn_verify_01_growth.py](../../../scripts/guorn_verify_01_growth.py) /
`_02_` / `_06_`; selection check [_guorn_overlap.py](../../../scripts/_guorn_overlap.py); corrected-yearly
re-display [_guorn_redisplay.py](../../../scripts/_guorn_redisplay.py).

| # | LOCAL | 果仁 | gap | Sharpe L/果 | vol L/果 | MDD L/果 | overlap topN/2N |
|---|---|---|---|---|---|---|---|
| 1 | +49.09% | +57.21% | −8.1pp | 1.26/1.68 | 32.9/31.7 | −53.3/−47.9 | 40.8% / 58.6% |
| 2 | +50.11% | +58.20% | −8.1pp | 1.25/1.58 | 34.0/34.4 | −53.8/−50.0 | 47.9% / 69.6% |
| 6 | +53.73% | +60.32% | **−6.6pp** | 1.20/1.44 | **38.8/39.2** | **−51.5/−51.9** | 45.9% / 67.2% |

- **Construction is faithful** at the selection layer (40–48% top-N name overlap with 果仁, stable 2014–2026,
  above #59's 36%). The uniform **−6.6 to −8.1pp** return gap is NOT a defect: it is the **same quantified 果仁
  execution optimism** from rung-1 (`sm_纯市值01`) — 果仁 fills limit-up microcaps in explosive years (#2 2015
  −86pp; both 2023/2025 −41 to −47pp) that our realistic engine's fill-price-aware limit gate correctly refuses.
  #6's risk profile (vol/MDD) matches 果仁 almost exactly. **These are deployable reproductions; the gap is 果仁
  over-counting illiquid fills, and our engine being right to skip them.**
- **OMISSIONS (documented):** #2 omits 业绩快报归母净利QGr%PY (express, w=1 of 10 — unmaterialized §7); #6 omits
  预期营收2年复合增长 (analyst consensus, irreducible §5) + 业绩快报 (2 of 11). Immaterial to selection (overlap
  unaffected). #6's two NEW factors — 贝塔N日(000001,250) = rolling-250d Cov/Var on 上证综指, and 研发销售比率 =
  TTM(rd)/TTM(rev) — are computed locally.

### Two accuracy bugs found + fixed (the careful-verification mandate)
1. **`mktcap_ind` (w=2 一级行业内) was silently a SECOND GLOBAL rank.** `$sw2021_l1` is NOT a Qlib provider field
   (SW industry lives in `data/universe/industry_sw2021_members/`) → the read returned all-NaN → `astype("str")`
   → one `"nan"` group → `groupby` collapsed it to a global market-cap rank. Proven exactly: `corr(mktcap_ind,
   global)=1.0000` (broken) → `0.91` (fixed). Rebuilt the industry frame via the canonical PIT-safe resolver
   `provider_metadata.build_industry_series_asof` ([_fix_industry_cache.py](../../../scripts/_fix_industry_cache.py);
   31 SW L1 codes, coverage 52%→99% 2014→2025). **#1 +47.60% → +49.09% (+1.5pp).** ⚠ Confined to the parity
   harness — **formal code is CLEAN** (`catalog.py`/`operators.py` use the resolver, NOT `$sw2021_l1`; grep-verified).
2. **果仁 yearly decimal-parse.** 果仁 年度收益统计 stores DECIMALS (`3.4035` = +340%); the old `/100 if abs(v)>3`
   heuristic wrongly divided >300% years (only #2's 2015 mis-shown +3.4% → corrected +340%). Headline numbers were
   always correct (from the recipe stats + actual net). Fixed to `float(v)` in all 3 harnesses + `_guorn_redisplay.py`.

## Roadmap

1. **🟢 6 GREEN — 3 DONE (#1/#2/#6).** Remaining 🟢: #4 sm_GARP_illiq / #5 双创研发强度 / #15 GARP@周期 — but the
   FULL recipes show gaps the partial-read triage missed (#4 = 23 factors incl 3 中性化(irreducible §5) + 快报 +
   StdevQ(CoreProfit,12); #5 = 评级(consensus) + 10日融资偿还(quarantined repayment) + 壳价值 + 机构/管理层持股).
   Reproducible with documented omissions, but heavier than the 成长 cluster.
2. **🟡 7 YELLOW** — most are blocked only on **analyst CONSENSUS + rating aggregates** (预期净利润/营收/股息, 评级机构数/调高家数). Materializing report_rc consensus (Phase-2, was deferred) unlocks #8/#9/#14/#16/#17/#18 at once — the high-value data-infra task (like the stability factors unlocked #59). Light-neutral #7/#12 reproducible with documented approximation.
3. **🔴 7 RED** — out-of-scope or new-domain: AH溢价 (#10, H股 data), 中性化-stack (#3, irreducible regression), FCF (#11, 处置FIOLTA unmaterialized), consensus-heavy (#13), fund rotation (#19/#20, need fund/ETF price data).

## Execution spec (trade model — must reproduce per-strategy; [deployed_20_trade_models.md](deployed_20_trade_models.md))

| # | strategy | model | 调仓周期 | fill | 仓位范围 → ~holds | 备选 | 择时 | live holds |
|---|---|---|---|---|---|---|---|---|
| 1 | sm_01_成长动量 | II | **1 (daily)** | 09:35 | 7–13% → ~10 | 20 | 无 | 12 |
| 2 | sm_01_成长_v1 | II | 1 | 09:35 | 7–13% → ~10 | 20 | 无 | 11 |
| 6 | sm_01_成长高贝塔@TMT_v1 | II | 1 | 09:35 | 7.5–22.5% → ~7 | 20 | 无 | 8 |
| 4 | sm_GARP_illiq | II | 1 | **09:31** | 7–13% → ~10 | 5 | 无 | 11 |
| 5 | sm_双创研发强度_v1 | II | 1 | 09:35 | 14–26% → ~5 | 5 | 无 | 6 |
| 15 | 成长_双创_GARP@周期_v2 | II | 1 | **日均成交价** | 7–13% → ~10 | 5 | 无 | 11 |
| 7 | value_红利低波_v2 | **I** | **5** | 10:00 | (持仓数) ~10 | 10 | 无 | 10 |
| 8 | value_红利低波_央企_v1 | II | 1 | 09:35 | 14–26% → ~5 | 5 | 无 | 7 |
| 9 | value_红利低波_重股息_v1 | **I** | **5** | 09:35 | (持仓数) ~5-10 | 5 | 无 | 10 |
| 18 | ST_大市值_v3 | II | 1 | 09:35 | 14–26% → ~5 | 5 | 无 | 5 |
| 16 | 成长_隔夜动量@周期 | II | **20** | 09:35 | 5–15% → ~10 | 5 | 无 | 11 |
| 17 | 成长_高波@周期 | II | **5** | 09:35 | 5–15% → ~10 | 5 | 无 | 11 |
| 12 | value_创业板sm_v1 | II | 1 | 09:35 | 5–15% → ~10 | 5 | 无 | 11 |
| 11 | value_FCF_非企sm_v2 | II | 1 | 09:35 | 7–13% → ~10 | 5 | 无 | 10 |
| 14 | 成长_净利润断层_v2 | II | 1 | 09:35 | 10–30% → ~5 | 5 | 无 | 2 |
| 13 | 成长_机构预期@周期_v1 | II | **3** | 09:35 | 10–30% → ~5 | 5 | 无 | 5 |
| 10 | value_AH_低溢价GARP_v1 | II | 1 | **10:00** | 7–13% → ~10 | 5 | 无 | 11 |
| 3 | sm_大制造GARP_v3 | II | 1 | 09:35 | 7–13% → ~10 | 5 | 无 | 11 |
| 19 | MultiA_风险平价_v1 | II | 1 | **开盘价** | 23–43% → ~3 | — | 无 | 3 |
| 20 | MultiA_动量18 | II | 1 | **日均成交价** | 25–75% → ~2 | — | 无 | 2 |

- **All 20 market_timing = 无** (no 大盘择时 — fully invested, 1×).
- **⚠ Cost is NOT in the data** — the xlsx exports turnover/holds but not commission; the master json carries only the generic "单边千分之二或千分之五". Per-book cost = the user's platform setting. Working default = **千分之二 (0.2%/side)** (果仁 default, rung-1/2/6-validated); the return-match confirms it (at #1's 774%/yr turnover, 0.2% vs 0.5% ≈ 5%/yr CAGR gap — material, so confirm before trusting a return parity).
- Fill modes: 09:35/09:31/开盘价 → engine OPEN fill; **日均成交价 (#15/#20) → `jq_daily_avg` mode** (CLAUDE.md §3.3); 10:00 (#7/#10) → open-approx.
- Model I (#7/#9) = full rebalance to top-N each period; Model II (rest) = rank-band hold (rung-1/2 engine).

## Weight handling — CAMPAIGN INVARIANT (audited all 20; _audit_deployed_weights.py)
果仁 ranking = 综合排名分 = **Σ(排名分ᵢ × weightᵢ)** (果仁筛选与排名功能 §3.1.4), 排名分 = (N−排名+1)/N×100.
EVERY reproduction MUST read the per-factor weights from the recipe (never assume equal) — weights are
factor-specific + non-uniform: 总市值 2+3 (#1/2/6), 股息率TTM 3 / CoreProfitQGr 2 (#7), CoreProfitQGr 2 +
ROETTMDiffPQ 2 (#4/#15), RnDTTMGr 2 (#5), overnight-mom 3+2 (#16), cash-div-yield 3 (#9). Rules:
- duplicate indicators (e.g. 总市值 ×2) = SEPARATE weighted terms, summed (NOT merged).
- scope: 全部 = cross-sectional rank; 一级行业内 = rank within 申万L1 (different N/denominator).
- NaN factor → ranked LAST (worst 排名分), included in the sum (NOT skipped).
- audit confirmed: all 20 weights numeric, 0 extraction problems; #1 verified 市值 5 / others 1.

## Notes
- value_FCF_非企sm (#11 deployed) ↔ `23_value_FCF_非金sm_v2.xlsx` — 企/金 name variance, same book.
- All universes are A股 except #19/#20 (multi-asset fund rotation).
- Reproduce TOTAL-return via EventDriven (credits dividends; CLAUDE.md §3.3), 果仁 cost per-book from the xlsx 交易统计 sheet.
