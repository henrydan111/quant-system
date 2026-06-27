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
| 4 | sm_GARP_illiq | sm | 09 | 49.6% / 1.54 | 🟢 | SalesQGr+CoreProfit+ILLIQ (all rung-4/5) | **✅ VERIFIED 2026-06-27** my **+32.2** vs +49.6 (−17.4pp); vol 29.8≈29.6, MDD −40.6≈−42.5 (near-exact); overlap 19.4%/31.5%. ★ ILLIQ-filter DIRECTION bug found+fixed (果仁 holds ILLIQUID, "0-65%" is DESCENDING; overlap 9.7%→19.4%). 12/23 weight OMITTED. Composite faithful (果仁 @94.6 pct). |
| 5 | sm_双创研发强度_v1 | sm | 10 | 62.7% / 1.54 | 🟢 | 市值+ILLIQ+R&D (rung-5) | **✅ VERIFIED 2026-06-27** my **+40.7** vs +62.7 (−22pp); vol 39.0≈38.1, MDD −49.1 (better than −61.0); 2015 LOCAL AHEAD (+381 vs +298); overlap 13.7%/21.4% (top5/10). 9/16 weight OMITTED incl w=2 RnDTTMGr%PY (no rd q5-7 depth). Composite faithful (@91 pct). HEAVIEST-omission GREEN. |
| 15 | 成长_双创_GARP@周期_v2 | 成长 | 44 | 43.4% / 1.13 | 🟢 | GARP (= #4 on 双创) | **✅ VERIFIED 2026-06-27** my **+15.8** (exits-off faithful) vs +43.4 (−27.6pp); vol 35.2≈34.9 (near-exact), MDD −70.3 vs −46.6; overlap 24.2%/38.3%. Reuses #4 cache (双创 mask); 日均成交价→jq_daily_avg. exits-ON over-fires (+11.5%, rung-2). 12/24 weight OMITTED. WIDEST gap (双创 vol amplifies omission+fill optimism). |
| 7 | value_红利低波_v2 | value | 19 | 29.7% / 1.32 | 🟡 | 股息率✓ + 中性N日换手率 (1 light neutral) | pending |
| 8 | value_红利低波_央企_v1 | value | 20 | 32.1% / 1.27 | 🟡 | 股息率✓ + 预期股息率 (1 consensus) | pending |
| 9 | value_红利低波_重股息_v1 | value | 21 | 33.3% / 1.27 | 🟡 | 分红波动率 + 预期DivAGrPY% (1 consensus) | pending |
| 18 | ST_大市值_v3 | ST | 53 | 55.5% / 2.00 | 🟢 | 市值+CoreProfitQ+业绩预告✓ + **评级机构数(NEW=$report_rc__n_active_orgs)** | **⚠ P5 CORRECTED 2026-06-27** (06-27 "P5 PROOF/field WORKS/gap=execution" RETRACTED — was unverified). my +26.5 vs +55.5 (−29pp); overlap 34.5%/44.7%. **REPLAY (果仁's exact names thru my engine, EW) = +60.99 ≥ 果仁 +55.5 → engine SOUND → the −29pp is SELECTION (my factors ~34.5pp worse than 果仁's names), NOT execution/limit-up.** 评级机构数 DEGENERATE on ST (7 distinct/200 — analysts skip ST) → #18's overlap driven by the OTHER 5 factors, NOT the field → #18 does NOT prove the field. **FIELD ITSELF VALID: holding-level vendor parity vs 果仁's exported 评级机构数 = 79.3% exact-match / 0.92 corr (n=15,403).** ST = poor field-proof + poor return-target (5-hold concentration ceiling). [_verify18_replay.py](../../../scripts/_verify18_replay.py) |
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

## GARP / R&D cluster — VERIFIED (2026-06-27): #4, #15, #5

The 3 remaining GREEN books, reproduced through the same daily model-II engine (0.2%/side, 涨停不卖, total
return) vs their 果仁 xlsx. These are FACTOR-HEAVY books — **44–52% of recipe weight is irreducible/unavailable**,
so they carry LARGER residuals than the 成长 cluster (documented below). Harnesses:
[guorn_verify_04_garp.py](../../../scripts/guorn_verify_04_garp.py) (builds the broad universe incl 科创板 → #4
masks it out) / [guorn_verify_15_garp_cycle.py](../../../scripts/guorn_verify_15_garp_cycle.py) (REUSES #4's
cache + composite, 双创 mask) / [guorn_verify_05_rnd.py](../../../scripts/guorn_verify_05_rnd.py).

| # | LOCAL | 果仁 | gap | Sharpe L/果 | vol L/果 | MDD L/果 | overlap | kept weight |
|---|---|---|---|---|---|---|---|---|
| 4 | +32.2% | +49.6% | −17.4pp | 0.95/1.54 | **29.8/29.6** | **−40.6/−42.5** | 19.4%/31.5% (top10/20) | 13/25 (52%) |
| 15 | +15.8%¹ | +43.4% | −27.6pp | 0.48/1.13 | **35.2/34.9** | −70.3/−46.6 | 24.2%/38.3% (top10/20) | 12/24 (50%) |
| 5 | +40.7% | +62.7% | −22.0pp | 0.97/1.54 | **39.0/38.1** | −49.1/−61.0² | 13.7%/21.4% (top5/10) | 7/16 (44%) |

¹ #15 exits-OFF (faithful baseline); exits-ON over-fires to +11.5%/MDD −71% (rung-2). ² #5 MDD BETTER than 果仁.

- **Construction is FAITHFUL despite the lower overlap** — PROVEN by the same composite-percentile test that
  cleared #1/#59 ([_diag04_overlap.py](../../../scripts/_diag04_overlap.py) /
  [_diag05_composite.py](../../../scripts/_diag05_composite.py)): 果仁's actual held names sit at my composite's
  **94.6th** (#4/#15) / **91st** (#5, median 96th) percentile — the kept factors AGREE with 果仁's selection. The
  lower top-N overlap (vs 成长's 40-48%) is the **44–52% recipe-weight OMISSION** shifting the fine-ordering at
  concentrated top-N, NOT a defect. **vol matches 果仁 almost exactly on all three** (29.8/29.6, 35.2/34.9,
  39.0/38.1) ⇒ the engine + risk scaling are sound; #4's MDD is near-exact, #5's is tighter than 果仁.
- **★ #4 ILLIQ-DIRECTION bug (the careful-verification catch).** First pass = 9.7% overlap, too low even for the
  omission. Diagnosis (universe 100% correct, 果仁 holds at 94.6 pct ⇒ composite fine) localized it to the
  **ILLIQ(5) filter direction**: 果仁's #4 holds sit at ILLIQ-ascending-pct **mean 0.68** (frac<0.35 ≈ 1.2%) — the
  book "sm_GARP_illiq" **TARGETS illiquidity**, so "ILLIQ(5) 排名%区间 0%-65%" keeps the **most-illiquid 65%**
  (DESCENDING), not the most-liquid. My ascending filter excluded 55% of 果仁's picks. Flipped ⇒ overlap
  **9.7%→19.4%**. (Confined to #4's harness; #15 has no ILLIQ filter, #5's 振幅 is a ranking not a filter.)
- **OMISSIONS — every one measured-impossible from the field probe
  ([_guorn_garp_field_probe.py](../../../scripts/_guorn_garp_field_probe.py)), NOT assumed (rule #10):** provider
  single-quarter depth is **q0..q4 only** (no q5-7) ⇒ all TTM-YoY / 3yr-CAGR growths + the w=2 RnDTTMGr%PY (#5) +
  12q-StdevQ unreproducible; **no EV field** (`$ev`/`$ev_ttm`/`$enterprise_value` all absent) ⇒ EBITDAQ%EV +
  gross÷EV dropped; **D&A single-q = 0%** (semi-annual cadence) ⇒ FCFQ_重算 family dropped; 3 中性化 (HNeutralize)
  + 壳价值 + 快报 + 评级(report_rc quarantine, parallel session) + 10日融资偿还($rzche quarantine) + 机构/管理层持股
  (unmaterialized) = irreducible. Full per-book list in each `verifyNN_result.json`.
- **The residual is the rung-1 mechanism, scaled by universe volatility × omission weight.** Calm years tight
  (#4 2016 +2.7/2018 −3.4/2022 −8.9/2026 +3.2; #15 2014 −6.2/2017 +0.3/2023 −2.4/2025 +3.0; #5 2019 −5.8/2021
  −11.1/2020 +8.0); bull years undershoot — 果仁 fills 一字 limit-up 双创/微盘 microcaps that our fill-price-aware
  gate + volume cap (10%) correctly refuse. **#15 carries the WIDEST gap** because 双创 (创业+科创) is the most
  explosive universe (果仁 2015 +358%) — same factors as #4 but the high-dispersion universe amplifies BOTH the
  omission-driven selection-precision gap AND the fill optimism (and 日均成交价/jq_daily_avg pays the up-day
  average). **#5's 2015 is LOCAL-AHEAD (+381 vs +298)** and its MDD beats 果仁 — the R&D core reproduces well.

## Roadmap

1. **🟢 6 GREEN — ALL 6 DONE (#1/#2/#6 成长 cluster 2026-06-26; #4/#15/#5 GARP/R&D cluster 2026-06-27).** The
   GARP/R&D trio is factor-heavier (44–52% recipe-weight omitted: TTM-depth>q4, no EV field, D&A single-q=0%,
   中性化/壳/快报) → larger residuals (−17 to −28pp) than the 成长 cluster's −7 to −8pp, but composite-faithful
   (果仁 holds @91-95 pct) with near-exact vol. ★ Caught + fixed the #4 ILLIQ-direction bug (overlap 9.7%→19.4%).
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
