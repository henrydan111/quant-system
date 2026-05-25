# P1 — Sealed-OOS Replication of G5_A2: Design Doc

*Companion to [../research_plan_2026-05-19_next_3_to_6_months.md](../research_plan_2026-05-19_next_3_to_6_months.md).*

*Status: DRAFT. Hypothesis JSON in [p1_hypothesis_g5a2_v0.json](p1_hypothesis_g5a2_v0.json) is NOT yet registered. Registration command at the bottom of this doc — review before running.*

---

## Goal

Measure how much of JoinQuant G5_A2's reported +234,625% / Sharpe 2.995 / MDD -41% survives:
- Realistic event-driven execution (multi-tier limits + T+1 + 25% volume cap + 10bps slippage)
- 4-fold walk-forward training inside IS (2014-2023)
- Sealed OOS holdout (2024-01-01 → 2026-02-27)
- Hash-pinned reproducibility via `hypothesis_validation` profile

---

## Mapping decisions (JoinQuant → local engine)

### Universe: 中小综 (399101.XSHE) → small_cap theme, sc_u4 candidate

**Correction from initial draft (2026-05-19):** Initially planned to use sc_u3, but inspection of [src/alpha_research/theme_strategy/registry.py](../../src/alpha_research/theme_strategy/registry.py) shows the current 6 small_cap universe candidates are:

| candidate | membership | cap floor | cap cap | listing min | comment |
|---|---|---|---|---|---|
| sc_u1 | csi1000 | ¥10亿 | ¥100亿 | 375d | mid-small, csi1000 only |
| sc_u2 | csi1000 | ¥10亿 | ¥200亿 | 375d | mid, csi1000 only |
| sc_u3 | csi1000 | ¥10亿 | ¥200亿 | 375d | duplicate of sc_u2 spec-wise |
| **sc_u4** | **all_market** | **¥10亿** | **¥100亿** | **375d** | **best G5_A2 match** |
| sc_u5 | all_market | ¥10亿 | ¥200亿 | 375d | broader |
| sc_u6 | all_market | ¥10亿 | ¥300亿 | 120d | broadest, looser listing filter |

**sc_u4 is the correct match** because:
- `membership_source = all_market` (G5_A2 is not csi1000-only — 中小综 includes names that are not in CSI1000)
- `market_cap_max = ¥100亿` (G5_A2 picks bottom 12; even with a 100亿 cap, the selected stocks will be the smallest dozen)
- `min_listing_days = 375` (exact match for G5_A2's `filter_new_stock(context, initial_list, days=375)`)
- `board_policy = mainboard` (G5_A2 excludes 创业板/科创板/北交所 via `filter_kcbj_stock`)
- `st_mode = exclude` (G5_A2 has `filter_st_stock`)
- `liquidity_floor = ¥20M` (reasonable; G5_A2 has no explicit liquidity floor but `filter_paused_stock` removes zero-volume names)

| Aspect | JoinQuant G5_A2 | Local engine sc_u4 | Fidelity |
|---|---|---|---|
| Index | `get_index_stocks('399101.XSHE')` (中小综 frozen 2021-04) | `theme:small_cap/sc_u4` (all_market + ¥10-100亿 cap) | Different membership rule, similar size band |
| Filter logic | All 中小综 → take 12 smallest by market_cap | sc_u4 → take 12 smallest by size_ln_mcap | Match in concept |
| ST exclusion | filter_st_stock | st_mode=exclude | Match |
| New stock (<375d) | filter_new_stock(375) | min_listing_days=375 | **Exact match** |
| Board exclusion | filter_kcbj_stock (excludes 科创/北交所; KEEPS 创业板) | board_policy=mainboard (excludes ALL of 创业板/科创/北交所) | **Slight mismatch** — sc_u4 is tighter |
| Liquidity floor | None (only paused exclusion) | ¥20M/day | sc_u4 is slightly stricter |

**Remaining fidelity caveats:**
1. **创业板 (300xxx) handling.** G5_A2 keeps 创业板 names; sc_u4 excludes them via mainboard policy. This is a real difference. 创业板 contains some microcap names that G5_A2 would pick but sc_u4 won't see. Sensitivity test: if P1 results are weaker than expected, register a v2 hypothesis with a custom `kind="broad"` universe that explicitly keeps 创业板.
2. **中小综 membership vs all_market filter.** 中小综 was the 原中小板 + 后中小板 names. After 2021-04 merger, the membership is frozen. sc_u4 uses dynamic all_market with size filter. Over 12 years, the populations are similar in spirit but not identical in roster.

### Selection logic: `valuation.market_cap.asc()` → `size_ln_mcap` component

JoinQuant: `query(valuation.code).filter(...).order_by(valuation.market_cap.asc()).limit(g.stock_num * 2)`

Local engine: single component in `PrescribedRecipe.components`:
```json
{"factor_name": "size_ln_mcap", "weight": 1.0, "kind": "raw", "direction": "lower_is_better"}
```

`size_ln_mcap` definition (from [data/factor_registry/factor_master.csv](../../data/factor_registry/factor_master.csv) line 187):
```
Log(Ref($total_mv, 1) * 10000)
```

- PIT-safe (`Ref($total_mv, 1)` wraps the field — passes factor_library PIT-safety enforcement)
- Currently graded **C** (rank_icir_5d = -0.188 on 5-day forward returns) — consistent with the briefing's claim that size is the dominant alpha but doesn't appear as a "strong factor" in single-factor IC tests because the alpha is concentrated at the extreme tails, not in monotonic ranking across the universe
- `direction = "lower_is_better"` because smaller market cap → higher expected return in G5_A2's frame

### Schedule: weekly Tuesday 10:30 → rebalance_days=5

JoinQuant: `run_weekly(weekly_adjustment, 2, '10:30')`

Local engine: `rebalance_days = 5`. **Loses Tuesday specificity.** The EventDrivenBacktester uses cron-style daily rebalance with a configurable cadence; trading day-of-week isn't part of the prescription schema. This is unlikely to materially affect results — the day-of-week effect is small relative to the 5-day rebalance frequency.

### TopK: 12 stocks (G5_A2)

`topk = 12`. Straightforward.

### Cost model

JoinQuant: `FixedSlippage(3/10000)` + `OrderCost(close_tax=0.001, open_commission=2.5/10000, close_commission=2.5/10000, min_commission=5)`

Local engine `CostModel`:
```json
{
  "slippage_bps": 10.0,
  "stamp_tax": true,
  "half_spread_bps": 0.0,
  "use_exchange_defaults": false
}
```

**The 10bps slippage is INTENTIONALLY HIGHER than JoinQuant's 3bps.** JoinQuant's 3bps is "unrealistically optimistic for microcap" (briefing's own §1.4). 10bps matches the local engine default and is closer to realistic microcap execution. This is one of the mechanisms by which OOS Sharpe will likely be lower than IS.

If you want to validate the JoinQuant claim apples-to-apples, register a second hypothesis variant with `slippage_bps=3.0` after P1 baseline completes.

### Portfolio construction

JoinQuant: `value = context.portfolio.cash / (target_num - position_count)` — equal-weight by allocating cash evenly across NEW positions.

Local engine:
```json
{
  "weighting_rule": "equal",
  "side": "long_only",
  "target_gross_exposure": 1.0,
  "max_position_weight": 0.084,
  "score_to_weight": "topk_equal"
}
```

`max_position_weight = 1/12 = 0.0833...` — equal-weight 12 names. Set to 0.084 to allow small numerical headroom.

---

## What's OUT OF SCOPE for P1 (deferred to follow-up plans)

The `PrescribedRecipe` schema in [src/research_orchestrator/hypothesis.py](../../src/research_orchestrator/hypothesis.py) **does not natively support**:

1. **Calendar blackout (`pass_months=[1,4]`)** — G5_A2's most load-bearing alpha mechanism (briefing's most cross-validated finding). Schema has no `blackout_months` field; would need extension.
2. **Individual stoploss (-12% from cost)** — risk overlay, not in prescription.
3. **Market trend stoploss (3-day mean close/open <= 0.94 on 中小综)** — risk overlay, not in prescription.
4. **14:30 limit-up open sell** — intraday execution rule, not in prescription.

### Why this is methodologically GOOD, not a flaw

The JoinQuant G5_A2 backtest combines:
- (a) Raw size sort alpha
- (b) Calendar blackout protection
- (c) Stoploss protection
- (d) Intraday execution rules

The +234,625% number is the joint product. We don't know how much each piece contributes — the ablations only test (b) and (c) in isolation, not their joint behavior with realistic execution.

**P1 explicitly measures (a) in isolation.** Then planned follow-ups measure each overlay's marginal contribution:

| Follow-up | Adds | Measures |
|---|---|---|
| P1.1 (after P1) | Calendar blackout via custom DAG step | Marginal value of 1+4月空仓 OOS |
| P1.2 (after P1.1) | Stoploss rules via custom DAG step | Marginal value of dual stoploss OOS |
| P1.3 (after P1.2) | Schema extension to `PrescribedRecipe` | Native support so future strategies inherit |

This is a more rigorous research design than "run the whole strategy and hope it works." It gives you per-component OOS evidence that you can publish.

---

## Walk-forward design

| Window | Period | Purpose |
|---|---|---|
| Pre-buffer | 2012-01-01 → 2013-12-31 | Factor warmup (size_ln_mcap is point-in-time; only needs 1-day prior data, but 2y is the default pre-buffer) |
| IS Fold 1 | train 2014-2018, val 2019-2020, test 2021 | First test fold |
| IS Fold 2 | train 2015-2019, val 2020-2021, test 2022 | Step forward 1y |
| IS Fold 3 | train 2016-2020, val 2021-2022, test 2023 | Step forward 1y |
| IS Fold 4 | train 2017-2021, val 2022-2023, test (none — overlap with OOS) | Validation only |
| Sealed OOS | 2024-01-01 → 2026-02-27 | One-shot; seal burned if results inspected before retune |

**Pre-registered minimum:** ≥ 3 of the 3 test folds (2021, 2022, 2023) must beat the benchmark on a stitched basis. If only 2/3 pass, P2/P3/P4 should proceed with caution.

**Sealed OOS includes** 2024Q1 微盘 雪崩 (the regime acid test — does G5_A2 actually catch the reversal?), 2025 calm, and 2026 YTD drawdown. Three distinct regimes in 26 months.

---

## Success criteria (pre-registered)

| Metric | Profile floor | This hypothesis | Rationale |
|---|---|---|---|
| `min_rank_icir` | 0.025 | 0.030 | size_ln_mcap currently has -0.188 absolute → easily clears |
| `min_deflated_sharpe` | 0.6 | **1.0** | Stricter — if Sharpe is <1 after deflation, strategy is not deployable |
| `min_cost_adjusted_sharpe` | 0.4 | **0.7** | Tighter to enforce honesty about cost drag |
| `max_drawdown` | 0.35 | **0.50** | **RELAXED** — JoinQuant IS MDD was -41%, OOS likely worse. Force-relaxed flag required. |
| `max_annual_turnover` | 4.0 | **12.0** | **RELAXED** — G5_A2 turnover is 11.6× in JoinQuant. Force-relaxed flag required. |
| `min_monotonicity_pvalue` | 0.10 | 0.10 | Match profile floor |
| `max_correlation_to_approved` | 0.80 | 0.80 | Match profile floor (no approved strategies yet) |
| `min_regime_pass_count` | 3 | 3 | Out of 3 IS test folds, must pass ≥ 3 (i.e., 100%) |

Registration command must include:
```
--force-relaxed-criteria --override-reason "G5_A2 baseline replication; pre-registered relaxed max_drawdown and max_annual_turnover to honestly measure strategy survival without bias"
```

---

## Pre-registered concerns (Bayesian honesty)

These are the 4 fields in `pre_registered_concerns` (filled in [p1_hypothesis_g5a2_v0.json](p1_hypothesis_g5a2_v0.json)):

1. **`most_likely_failure_mode`**: "OOS Sharpe drops below 1.0 due to (a) 2014-2015 windfall absence from sealed OOS, (b) realistic 10bps slippage drag, (c) shell-value decay post 国九条 enforcement (Liu/Stambaugh/Yuan 2019)."

2. **`weakest_assumption`**: "The mapping from 中小综 (frozen 2021-04, ~800 names) to small_cap theme sc_u3 (~460 names) is approximate. sc_u3 is a smaller, possibly tighter universe — picking 12 smallest from it concentrates more aggressively than G5_A2 did historically."

3. **`what_would_falsify_this`**: "Stitched OOS Sharpe < 1.0 OR max_drawdown > -55% OR any single IS test fold underperforms benchmark by > -10% AND no fold delivers > +20% excess. Any of these falsifies 'the size sort delivers deployable alpha out of sample.'"

4. **`priors_on_cost_sensitivity`**: "G5_A2 turnover is ~11.6×/year per JoinQuant. At 10bps slippage + stamp tax, cost drag is ~30bps/rebalance × 52 rebalances ≈ 16% annual drag. Cost-adjusted Sharpe will be ~60-70% of gross."

---

## Run plan once registered

```bash
# 1. Register (review JSON first, then run)
"E:/量化系统/venv/Scripts/python.exe" "E:/量化系统/workspace/scripts/hypothesis_cli.py" register \
  --file "E:/量化系统/Knowledge/temp_plan/p1_hypothesis_g5a2_v0.json" \
  --registered-by "henry" \
  --profile-id hypothesis_validation \
  --force-relaxed-criteria \
  --override-reason "G5_A2 baseline replication; relaxed max_drawdown 0.50 and max_annual_turnover 12.0 to measure strategy survival honestly without floor-rail bias"

# 2. Verify seal is fresh (must return exit 0 with --expect-claims 0)
"E:/量化系统/venv/Scripts/python.exe" "E:/量化系统/workspace/scripts/hypothesis_cli.py" verify-seal \
  --hypothesis-id hyp_20260519_001 \
  --expect-claims 0

# 3. Build orchestrator request for hypothesis_validation profile
# (TODO: write request_file template; see hypothesis_pead.json template for pattern)

# 4. Execute DAG
"E:/量化系统/venv/Scripts/python.exe" "E:/量化系统/workspace/scripts/research_orchestrator_cli.py" run \
  --request-file "E:/量化系统/Knowledge/temp_plan/p1_orch_request.json"

# 5. At gate_concern_scoring pause, run score-concerns
"E:/量化系统/venv/Scripts/python.exe" "E:/量化系统/workspace/scripts/hypothesis_cli.py" score-concerns \
  --run-dir <run_dir>

# 6. At gate_review pause, approve or reject
"E:/量化系统/venv/Scripts/python.exe" "E:/量化系统/workspace/scripts/hypothesis_cli.py" approve \
  --run-dir <run_dir> --gate-step validation_gate_review_is

# 7. After OOS completes, verify seal was claimed exactly once
"E:/量化系统/venv/Scripts/python.exe" "E:/量化系统/workspace/scripts/hypothesis_cli.py" verify-seal \
  --hypothesis-id hyp_20260519_001 \
  --expect-claims 1
```

---

## Open items before registration

- [x] Confirm theme universe candidate exists. Verified `sc_u4` is registered in [src/alpha_research/theme_strategy/registry.py](../../src/alpha_research/theme_strategy/registry.py) THEME_SPECS['small_cap'].universe_candidates. ✓
- [x] Confirm `size_ln_mcap` is in the current factor registry as `is_current=True`. Verified ✓ at line 187 of factor_master.csv (status=draft, grade=C, but draft is fine for hypothesis_validation since `allow_candidate_components=false` only blocks candidate-registry factors, not draft formal-registry factors).
- [x] Run a dry validation: `Hypothesis.from_dict()` loads cleanly. ✓
- [x] Verify floor-rail behavior: without `--force-relaxed-criteria` the schema correctly rejects on `max_drawdown=0.50 > 0.35` and `max_annual_turnover=12.0 > 4.0`. With override, passes. ✓
- [x] **Final design_hash with sc_u4 universe locked**: `d90e204202321012a75a4f47b1e75ec0839c2552a9fb081c6315d27245c2f8da`. Any further edit to the hypothesis JSON will change this hash and require registration with a new hypothesis_id.
- [ ] Build the orchestrator request JSON (`p1_orch_request.json`) — mirror the pattern at `workspace/research/alpha_mining/hyp_growth_garp_3leg_run_20260429/run_metadata.json` (the only completed `hypothesis_validation` example).
- [ ] **YOU (the user) must approve registration command** — this writes to `data/hypothesis_registry/hypothesis_events.parquet`. Per CLAUDE.md §13, registry mutations need explicit OK.

## Next concrete step after this design is approved

Run the dry validation one more time with the sc_u4 universe fix, lock the design_hash, then I draft the orchestrator request JSON (`p1_orch_request.json`) which is the actual input to `research_orchestrator_cli.py run`. The request JSON references the registered hypothesis by ID, so the steps are: (1) approve THIS design doc, (2) approve registration, (3) approve orchestrator launch.

---

## Run history & infrastructure learnings (2026-05-19, live)

### v0 → hyp_20260519_001 — FAILED at validation_dataset_build

- **Recipe**: `kind="theme"`, theme_id=small_cap, theme_universe_candidate_id=sc_u4
- **Failure**: `ValueError: materialize_universe(kind='theme') requires a theme_resolver callable (theme_id, candidate_id) -> UniverseCandidate`
- **Root cause**: `validation_steps.py:298` calls `materialize_universe(...)` without passing `theme_resolver`. The `hypothesis_validation` profile v1 only supports `kind="broad"`.
- **Lesson**: Even though `UniverseSpec` schema accepts `kind="theme"`, the validation profile cannot consume it. This is an infrastructure gap to flag for a follow-up plan.

### v1 → hyp_20260519_002 — FAILED at orchestrator entry validation

- **Recipe**: switched to `kind="broad"` with broad_filters mirroring sc_u4 spec. success_criteria kept at relaxed values (max_drawdown=0.50, max_annual_turnover=12.0) with intent to use `--force-relaxed-criteria` at registration.
- **Failure**: `LaxCriteriaError` at `engine.py:_validate_request_against_profile`. The orchestrator re-validates floor rails at RUN TIME without honoring registration-time override.
- **Root cause**: `--force-relaxed-criteria` is a registration-time flag only. The runtime `validate_success_criteria_floor_rails` call at engine.py:268 always uses `allow_override=False`.
- **Lesson**: success_criteria in the hypothesis MUST satisfy profile floors. The override only relaxes registration, not execution. To run G5_A2 honestly: declare criteria AT THE FLOORS (max_drawdown=0.35, max_annual_turnover=4.0). If actuals exceed those, the gate verdict will be `is_quarantined` — which is correct behavior: we measured the strategy honestly, didn't promote it.

### v2 → hyp_20260519_003 — LAUNCHED 2026-05-19 ~17:55

- **Recipe**: `kind="broad"` + sc_u4-mirroring filters + success_criteria at profile floors (max_drawdown=0.35, max_annual_turnover=4.0).
- **Expected verdict**: `is_quarantined` at IS gate. G5_A2's claimed MDD is -41% IS (>0.35 floor) and turnover is 11.6× (>4.0 floor). The gate will reject. But all measured metrics will be produced — that's the data we want.
- **Design hash**: `fb6c54c37a3a916103e21dfe099f20bacdbf0785c5aacbdfb1154ef4a7dd73b5` (locked).
- **Run dir**: `workspace/research/alpha_mining/hyp_20260519_003_g5a2_replication/`.

### Infrastructure gaps surfaced (for future plans)

1. **Theme universe support in `hypothesis_validation` profile.** `validation_dataset_build` needs to receive a `theme_resolver` from the orchestrator context. Engineering: ~2-4 hours. Until then, all hypothesis_validation runs must use `kind="broad"`.
2. **No runtime override for floor rails.** This is by design (prevents lax criteria from sneaking past gate). The honest workaround is "declare at floor, accept is_quarantined verdict for measurement-only runs." Could be enhanced with a `measurement_only` mode that publishes diagnostics without applying gates — but that's a deeper schema change.

### Implication for the broader plan

Because of these gaps, all four projects (P1-P4) in the master plan will need similar handling:
- P2 (long-short): also requires schema extension (`side="long_short"` per project_state.md 2026-04-28). Engineering blocker confirmed.
- P3 (regime allocator): outside hypothesis_validation entirely — needs custom DAG step or runs in `theme_strategy` profile.
- P4 (capacity sweep): same recipe as P1 with different cost_model.slippage_bps → reuses P1's broad-universe pattern.
