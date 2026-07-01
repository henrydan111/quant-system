# 果仁-anchored StrategyCandidate harness — first object: #59 Comp_Core_Quality

> **Decision (user, 2026-06-24):** build the strategy/book layer **around 果仁** — the first formal
> `StrategyCandidate` is a *faithful reproduction* of a real deployed 果仁 book, validated against its
> xlsx backtest detail BEFORE it is formalized/sealed. Anchor book = **#59 Comp_Core_Quality**.
> **User constraint:** 果仁 data-parity is not 100% finished — *always check the locally-replicated
> strategy against 果仁's backtest result detail carefully to ensure accuracy* (verification-by-construction).
>
> This unifies the two threads: "continue to verify 果仁" (parity ladder) + "build the strategy workflow"
> (capital-allocation build plan [STRATEGY_LAYER_BUILD_PLAN_v1.md](STRATEGY_LAYER_BUILD_PLAN_v1.md)).
> The reproduction-and-validation IS the next parity rung; the formal object IS the harness every later
> PR (risk model, optimizer, capacity) plugs into.

## The book (verified verbatim from guorn_strategies_master.json, nn=59)

- **Category:** 策略组件 (component). **Benchmark:** 沪深300 (annual 6.25%). **Period:** 2014-01-02..2026-06-18.
- **★ Universe (CORRECTED):** `全部股票` (BROAD market) − ST − 科创板, suspended filtered, 申万2014 industry std.
  **NOT 沪深300-liquid** (the earlier memory note was wrong). 北证 inclusion = TBD, must be proven from the
  holdings sheet exactly like rung-1 (which found 果仁's "全部股票" = 沪深主板+创业板 only for sm_纯市值01).
- **Filter:** `扣非市盈率 ∈ (0, 60)` — *deducted-earnings* PE (扣非净利润), NOT plain `$pe_ttm`.
- **Rankings:** 12 slots, ALL equal weight (=1). `OPCFNPDiff%NP` appears twice → effective 2/12 on cashflow quality.
- **Trade model:** Model I, hold **20**, equal weight, rebalance **every 5 trading days at CLOSE**, 5 alternates,
  no idle-cash allocation, **no market timing**. (Close fill → engine gates on `raw_close`, legacy path.)
- **果仁 ground truth:** total 1160.44% / annual **22.56%** / Sharpe **0.69** / MDD **40.86%** / vol 26.71% /
  IR 0.92 / beta 0.94 / alpha 16.44% / excess 15.35%. Total-return basis (dividends reinvested → EventDriven).
  Cost = platform default (千分之二 or 千分之五 — confirm per-book from the 交易统计 sheet).

### Factor → local mapping (the parity sub-ledger for #59)

| # | 果仁 indicator | dir | local expression | parity status |
|---|---|---|---|---|
| 2,12 | OPCFNPDiff%NP (×2) | ↓big | (Σcashflow_act_sq[0..3]−Σn_income_sq[0..3])/Σn_income_sq[0..3] | ✅ penny-exact (rung-4) |
| 5 | GrossProfit%AssetsQ | ↓big | ($revenue_sq_q0−$oper_cost_sq_q0)/$total_assets_q0 | ✅ penny-exact (rung-4) |
| 3 | 销售毛利率Q − 销售毛利率 | ↓big | margin_single_q − margin_TTM | components ✅; **ratio TBV** |
| 4 | RoeCoreQ | ↓big | CoreProfitQ / $total_hldr_eqy_exc_min_int_q0 | components ✅ (rung-5); **ratio TBV** |
| 8 | STDEVQ(SalesQGr%PY,12) | ↑small | 12-quarter stdev of SalesQGr%PY | base ✅; **12q-series TBV** |
| 1 | RnDTTM%营业收入TTM | ↓big | TTM($rd_exp)/TTM($revenue) | base ✅ (rung-5); **ratio TBV** |
| 6 | RND%Assets | ↓big | TTM($rd_exp)/AvgQ($total_assets,4) | base ✅; **ratio TBV** |
| 7 | STDEVQ(RoeCoreQ,12) | ↑small | 12-quarter stdev of RoeCoreQ | **TBV** |
| 9 | HAVG(OPCFNPDiff%NP,1) | ↓big | historical-avg, window=1 | **HAVG semantics TBV** |
| 11 | 应收账款周转率 | ↓big | revenue / 应收账款 ($accounts_receiv?) | **field materialization TBV** |
| F | 扣非市盈率 | (0,60) | 总市值 / TTM(扣非净利润) [$profit_dedt?] | **field TBV** |
| 10 | 中性ROE (HAVG,1) | ↓big | 果仁 industry/size neutralization regression | ⛔ **irreducible** (ledger §5) |

TBV = to-be-validated at holding level vs 果仁 (rung-4/5 method). "11/12 reproducible, 1 irreducible" confirmed.

## Phased plan

- **A — Recipe + universe (verify): ✅ DONE.** Recipe extracted. **A3 PROVEN** from 交易段持仓详单 (606
  periods, 12,120 rows): universe = SH主板+SZ主板+中小板+创业板, **0 北证 / 0 科创板 / 0 B股** ever → allow-list
  `沪深 main+中小板+创业板`, exclude 科创板/北证/ST. Trade model confirmed empirically: exactly **20**
  holdings/period, **0.05=1/20** equal weight (drift 0.032–0.082), **5-day** cadence, 2014-01-02→2026-06-18.
  **中性ROE is near-inert** (displays 0.0000 for 98.5%, rest rounds to 0). **A4:** holdings cached to
  `workspace/outputs/guorn_parity/holdings_59.parquet`.
- **★ Phase-B feasibility (field/slot audit, DONE):** provider materializes **q0..q4 only** (revenue q0..q9)
  for statement single-quarter slots. → **9/12 slots + filter cleanly reproducible NOW** from approved fields
  (OPCFNPDiff%NP×2, GrossProfit%AssetsQ, RoeCoreQ, RnDTTM%营收, RND%Assets, 销售毛利率Q−销售毛利率,
  HAVG(OPCFNPDiff,1), 应收账款周转率, 扣非PE via approved `$dtprofit_to_profit`×NP). **slots 7,8 STDEVQ(…,12)
  need 12q depth** (not materialized) → omit-and-measure first; deeper-quarter materialization only if the
  measured residual warrants it (coordination-sensitive vs the in-flight rebuild). **slot 10 中性ROE**
  irreducible + inert → omit. So the meaningful omission is just the **2 stability factors**.
- **B — Factor parity (extend the ledger): ✅ DONE** ([_guorn59_factor_parity.py](../../scripts/_guorn59_factor_parity.py)
  + [_guorn59_refine.py](../../scripts/_guorn59_refine.py); ledger §1b updated). Holding-level vs 果仁's
  displayed values: **6 penny-exact** (OPCFNPDiff%NP, GrossProfit%AssetsQ, + 4 new: RnDTTM%营收, RND%Assets,
  销售毛利率Q−销售毛利率, 应收账款周转率[exact TTMrev/(avg4AR+avg4NR−avg4ADV)]); **2 rank-faithful sub-5%**
  (RoeCoreQ 3.9%/sign99.5% — q0-end equity best; 扣非PE 5.7% — fine for coarse filter); **HAVG(x,1) semantics
  RESOLVED = 申万L1 industry cross-sectional mean** (template `{0}<HAvg({0},{1})*{2}`, 范围=1=L1 industry);
  **3 omitted** (2× STDEVQ(,12) need 12q depth; 中性ROE irreducible + inert [0.0000 for 98.5%]).
  → 9/12 ranking slots + filter reproducible.
- **C — Reproduction + careful validation: IN PROGRESS** ([guorn_parity_rung6_quality59.py](../../scripts/guorn_parity_rung6_quality59.py),
  real `EventDrivenBacktester` + 果仁 0.2%/side; cache-iterate architecture: `--build`/`--select`/`--diag`/`--run`).
  **Result (9-factor, 2014..2026-02):** PROFILE match — LOCAL annual **+25.29%** / Sharpe **0.82** / MDD **−43.96%** /
  vol **27.06%** vs 果仁 +22.56% / 0.69 / −40.86% / **26.71%** (near-identical vol = same risk profile). But
  **year-by-year LOOSE** (±10–40%; 2015 −40.6, 2019 +30.4) and **holdings overlap only 22%**. **`--diag` verdict
  (decisive):** 果仁's held names sit at **median percentile 0.969 in MY ranking** (top ~3%) — the composite is
  SOUND; the 22% exact-top-20 overlap is selecting 20 from a clustered elite with 9 of 12 factors. `rank_eligible`
  (within-pool vs full) makes ~0 diff. **Leading-but-unproven cause:** the 2 omitted `STDEVQ` stability factors
  (my book is slightly higher-return/higher-vol = less stability-tilted; direction-consistent). **Confirm-the-cause
  test (user-chosen):** add the partially-computable `STDEVQ(SalesQGr%PY,6q)` (revenue_sq q0..q9, no provider
  change) → expect overlap↑ + vol→26.71 + return→22.56 if confirmed. Bug found+fixed en route: deeper-slot column
  misalignment (4817 vs 4826 → reindex to opcf.columns).
  **CHEAP-DIAGNOSIS CONCLUSION (exhausted, rule #10):** (1) the stability test is a DEAD END — f9 100% NaN because
  revenue q5..q9 are empty (provider q0..q4 depth holds for ALL statement single-q fields incl. revenue) → stability
  needs deeper materialization to test. (2) NaN-policy `worst` (missing→worst rank, more 果仁-faithful) lifts overlap
  21.6%→24.2% (MINOR). (3) `present_min` high → pool <20 names/period → 果仁 USES partial-coverage names (no full-
  coverage requirement). (4) size ~RULED OUT (backtest vol 27.06≈26.71). (5) rank-pool nil. **No cheaply-testable
  bug explains the 22% gap; composite 97th-pct sound + data penny-exact + real engine + profile-match.** Residual
  = stability factors (untestable w/o deeper materialization) + inherent top-20 sensitivity (20-from-clustered-elite).
  **STABILITY HYPOTHESIS CONFIRMED (2026-06-25) via SCOPED deep-slot materialization** (the user chose "finish
  the stability test, scoped correctly"). Built a slot_depth=16 staged provider for ONLY the 7 stability-input
  fields × the 4817 universe (`_build_deepslot_scoped.py`, Python API to bypass the ~48KB command-line limit;
  `--touched-symbols` avoids the full-tree copy, `field_filter` restricts to 7 fields → ~182GB transient, deleted
  after). `build_stability` computed the 2 real `STDEVQ(.,12)` factors (f9 RoeCoreQ-stab / f10 SalesGr-stab,
  ~72% coverage) → the faithful **11-factor composite**. **Ablation (decisive):** overlap **21.6% → 35.9%**
  (+14.3pp; `--drop-stab` reproduces 21.6% exactly) AND the backtest **converges**: annual +25.29%→**+21.42%**
  (vs 果仁 +22.56%), vol 27.06%→**25.72%** (vs 26.71%), Sharpe 0.82→**0.73** (vs 0.69) — the stability tilt makes
  the book more conservative, pulling it from overshoot to ~match. **The 2 STDEVQ stability factors were the
  dominant cause of the gap, proven.** Residual = inert 中性ROE (irreducible) + RoeCoreQ 3.9% + top-20 sensitivity
  (big-bull-year selection precision: 2015 −35, 2024 −20.8). ⚠ **DISK LESSON (memory `feedback_provider_build_disk_hazard`):**
  the FIRST (unscoped) attempt at this build hit 1TB and filled the disk — ALWAYS scope (`--touched-symbols` +
  `field_filter`) + estimate before a slot_depth build.
  → #59 now validated at BOTH levels (holdings 35.9% + returns within ~1%).
- **★ C-FINAL — stability factors NOW LIVE + REGISTERED (2026-06-25): ✅ DONE.** The 2 STDEVQ factors were
  materialized into a custom PIT provider materializer `_materialize_quality_stability` (reuses the proven
  single-quarter kernel; GPT R1 REVISE → R2 SHIP) and published **IN-PLACE** to the live provider
  (`_publish_stability_inplace.py` — user chose the surgical additive write over the heavy 327GB/20M-file
  staged-swap; purely additive, 2 new bins/dir, base build `phasec_profit_dedt_sq_20260624` NOT rotated).
  Verified **bit-faithful vs the rung-6 deepslot f9/f10** over the FULL universe (median rel-err **0.0**, n~2M;
  `_verify_stability_live.py`) → the 35.9% overlap reproduces by construction. Registered as the new
  `quality_stability` family (`$roe_core_stab_12q` / `$sales_gr_stab_12q`, status approved; field_status block +
  approval YAML `2026-06-25_quality_stability_to_approved.yaml` + log + provenance JSON). 88 governance tests
  pass; both fields resolve approved/allowed at all stages. **The FORMAL 11-factor #59 is now data-ready.**
- **D — Formalize (NOW UNBLOCKED):** wrap the validated **11-factor** recipe into a hash-bound `StrategyCandidate v0`
  via the `factor_eval_skill` seam (`DeploymentFrozenPlan`/`run_deployment`); publish into the empty
  `data/strategy_registry/`; seal (HoldoutSealStore on the strategy hash). Substantial → **independent GPT
  cross-review (§10) before it is treated as final**. Re-run the #59 overlap + event-driven backtest from the
  LIVE fields (accuracy-first mandate) as the formalization's validation leg. Capacity report = `pending_pr4`.
  ⚠ Note the #59 universe is BROAD (not liquid) — deployability is a separate PR4 gate, not assumed here.

## Coordination + caveats

- **In-flight provider publish (other session, 2026-06-24):** materializing 25 `q_*` indicators +
  `stk_holdertrade` 高管 signals → atomic provider swap + 33-field registration. #59 does NOT appear to need
  those fields (it builds single-quarter values from statement `_sq` bins, not the indicators `q_*` fields) →
  reproducible on the CURRENT provider (`20260623_004545`). But any **formal provider-stamped seal (Phase D)
  waits** until their publish settles (else artifact provenance binds a superseded build id).
- **NOT deployable as-is:** broad universe ≠ liquid; capacity/deployability is decided at PR4, not assumed.
  Unlevered throughout (§7.11). The `中性ROE` deviation is documented (like rung-1's 退市风险 proprietary screens).
- **GPT cross-review gate:** the harness design + the formal StrategyCandidate object are "substantial" →
  GPT 5.5 Pro cross-review before Phase D is treated as final (CLAUDE.md §10).
