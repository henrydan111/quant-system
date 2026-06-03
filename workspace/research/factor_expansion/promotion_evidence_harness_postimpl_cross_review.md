# POST-IMPLEMENTATION Cross-Review (for GPT) — promotion-evidence harness + the first `approved`-tier promotion (PR #40)

You previously GO'd the **design** of this harness (Conditional GO + 6 guards + 3 tweaks, then re-confirm GO). This reviews the **implementation as built AND executed** — the 6 sealed-OOS winners are ALREADY `approved` on the live registry. Find any integrity hole that should **block the merge** or require a **follow-up fix**. No repo access — everything needed is embedded. A NO-GO with a specific mechanism beats a GO. Attack especially the reconciliation in §3 (a real bug I caught mid-build) and the soundness questions in §7.

## 0. What was built and executed (current state)

- The promotion gate (`release_gate.evaluate_promotion_artifact`) consumes a `promotion_evidence` artifact whose checks must all be `"passed"`, but **nothing produced it** (only test fixtures). This PR is the **producer**.
- Live registry is now **87 candidate + 84 draft + 6 `approved`** (177 current). The 6 (`liq_zero_ret_days_10d`, `rev_turnover_spike_5d`, `grow_total_revenue_yoy_accel_q`, `grow_n_income_attr_p_yoy_accel_q`, `grow_operate_profit_yoy_accel_q`, `qual_piotroski_fscore_9pt`) are the **first `approved`-tier factors**; all `approval_validity=valid`, `expected_direction=positive`, v1.
- The 87 lifecycle candidates remain blocked from `approved` (their selection used full-window OOS knowledge → 2021-2026 burned). The 6 are different: a 13-factor top set was **frozen pre-OOS** (committed `oos_frozen_topset.json`) and the OOS window (2021-01-01 → 2026-02-27) was run **once** in Round-6 (PR #28).

## 1. Harness architecture (2 modules + a driver)

- **`src/data_infra/pit_canaries.py`** — 6 PIT canaries (`synthetic_lookahead`, `restatement`, `q0_multiperiod`, `q0_stateful_restatement`, `q0_missing_field`, `availability_assertion`). Each runs a controlled synthetic-ledger fixture through already-tested kernel logic (`strictly_next_open_trade_day`, `derive_single_quarter_value`, the stateful-q0 `align_ledger_to_calendar`) and returns `"passed"`/`"failed"`; each also FAILS on an injected-leak fixture (fail-closed proof). Live correctness of the real pipeline is covered separately by `live_provider_parity`.
- **`src/research_orchestrator/promotion_evidence.py`** — `build_promotion_evidence` (pure assembler; missing canary → `"failed"`, missing dirty_tree → `True`), `produce_promotion_evidence` (gathers canaries + lint + parity + git, assembles, then **self-verifies via `evaluate_promotion_artifact`** and raises unless gate-eligible — so it can only ever emit a passing artifact on a clean committed tree), and `reproduce_sealed_oos` (§2).
- **Driver** `workspace/scripts/promote_sealed_oos_winners.py --mode dryrun|live`: builds the `FrozenSelectionSet` over the frozen 13, reproduces + self-verifies; `--mode live` aborts on a dirty tree BEFORE claiming the seal, then syncs the 6 to draft and `set_status('approved', …)` for the bar-passers.

## 2. The reproduction (`reproduce_sealed_oos`) — and the EXECUTED result

Re-runs the **screening's exact path** over the frozen window, claiming the holdout seal first:
- `compute_factors(catalog={6}, horizons=(5,10,20), stage="oos_test")` → factors + multi-horizon forward returns through the sanctioned `qlib_windowed_features` chokepoint (→ `source="qlib_windowed_features"`).
- `run_batch_screening(factors, fwd, horizons=(5,10,20), engine="batch")` — the **identical function + engine** `run_sealed_oos.py` used in Round-6 — and reads per-factor `rank_icir_20d` + `ls_sharpe`.
- Returns the `independent_reproduction` block (source, `provider_build_id`, `calendar_policy_id`, `frozen_set_hash`, per-factor metrics).

**Executed live result — reproduces the Round-6 report BIT-FOR-BIT:**

| factor | leak-free rank_icir | report icir | leak-free ls_sharpe | report ls | bar (LS>1.0, sign+) |
|---|---|---|---|---|---|
| liq_zero_ret_days_10d | 0.4109 | 0.4109 | 2.1431 | 2.143 | PASS |
| rev_turnover_spike_5d | 0.2759 | 0.2759 | 2.6818 | 2.682 | PASS |
| grow_total_revenue_yoy_accel_q | 0.2565 | 0.2565 | 3.4441 | 3.444 | PASS |
| grow_n_income_attr_p_yoy_accel_q | 0.2499 | 0.2499 | 1.9560 | 1.956 | PASS |
| grow_operate_profit_yoy_accel_q | 0.1966 | 0.1966 | 1.4924 | 1.492 | PASS |
| qual_piotroski_fscore_9pt | 0.2089 | 0.2089 | 1.2029 | 1.203 | PASS |

All 6 self-verified; gate artifact: all 6 canaries + `unsafe_pit_dates_lint` + `live_provider_parity` `"passed"`, `dirty_tree=false`, `git_sha=150c1ff…`.

## 3. The bug I caught mid-build (the reconciliation — attack this)

My FIRST `reproduce_sealed_oos` hand-rolled the LS Sharpe: `compute_quantile_returns(n=5,min_obs=…) → compute_long_short_returns → sqrt(252/horizon) × mean/std` at **horizon=20**. The dry-run then diverged from the report: `grow_total_revenue` 7.76 vs the report's 3.44 (2.26×), while `rev_turnover` matched (2.62 vs 2.68) — a **non-uniform** overshoot. I traced it empirically:
1. `rank_icir` matched the report **exactly** → factor + label data identical (RankIC is rank-based).
2. The `fwd_df` label vs my leak-free `build_is_windowed_panel` label gave **identical** ls_sharpe → not a label difference.
3. inf→NaN sanitization changed grow's number but did NOT reconcile (4.81 ≠ 3.44) → not (only) inf.
4. **Root cause:** `run_batch_screening`'s `ls_sharpe` is computed at `primary_h = horizons[0]`. Round-6 called it with `horizons=[5,10,20]` → the report's `ls_sharpe` is the **5-day** long-short Sharpe (with `sqrt(252)` annualization), NOT the 20-day. My hand-rolled 20-day metric was the wrong scale — and it **inflated the slow `grow_*` factors 2–4×**, which would have been a **false-positive promotion**.

Fix: drop the hand-rolled metric; reuse `run_batch_screening(engine="batch", horizons=(5,10,20))` verbatim → reproduces the report bit-for-bit (table in §2). inf in `grow_total_revenue` (829 `q0/q4`-near-zero cells) is a **red herring**: the screener's `qcut(duplicates="drop")` handles it identically to Round-6, and rank_icir is inf-robust.

**The decision I most want you to attack:** the registration bar `LS Sharpe > 1.0` was thus defined against a **5-day** primary-horizon LS Sharpe, while the IC criterion (`rank_icir_20d`) is 20-day — a **mixed-horizon** criterion that is an artifact of how the Round-6 screener emitted `ls_sharpe` (always `horizons[0]`). My position: a faithful reproduction must inherit the registration's exact metric (5d ls_sharpe), because the question being answered is "does the factor clear the *same bar it was selected against*, under the sanctioned formal path" — NOT "is 5d the ideal rebalance horizon." Promoting on the registration's own metric is faithful; re-judging with a different (20d) horizon would be a *new* selection. **Is that sound, or should `approved` require a horizon-consistent (e.g. 20d/20d) tradability metric — making this a candidate-only promotion until a 20d LS Sharpe is computed?** (For reference, my earlier 20d LS Sharpe: liq_zero 0.92, rev_turnover 0.59, grow_total_rev 1.74, grow_n_income 1.27, grow_op 0.83, piotroski 0.33 — i.e. on a 20d metric only 2 of 6 clear 1.0. The 5d metric — the registration's actual bar — clears all 6.)

## 4. The 6 guards, as IMPLEMENTED

1. **Real seal claim** — `HoldoutSealStore.claim_holdout_access(seal_key=frozen_set.frozen_set_hash, stage="oos_test", …)`; exactly **1 event** recorded for `frozen_set_hash=5a8d601a…`. Not a self-attested flag.
2. **Seal keyed to the full frozen 13** — `FrozenSelectionSet` over the 13 (not the 6 survivors); `expected_direction='long'` for all 13 = the **pre-OOS IS-frozen** sign (every frozen factor had positive IS RankICIR). `candidate_pool_hash`/`selection_rule_hash`/`eval_protocol_hash` derived from committed artifacts (the 50 formal-eligible IS-screen names; the `oos_topset_selection_rule.md` bytes; a protocol descriptor).
3. **Leak-free OOS** — guaranteed by asserting the **live provider `calendar_end == OOS_END (2026-02-27)`**: `Ref(-h)` forward returns are NaN past the data boundary for every horizon, so no future data can enter. `build_is_windowed_panel(is_end=OOS_END, horizon=max(5,10,20))` is RETAINED as a redundant explicit longest-horizon leak-guard (raises `IsEndLeakageError` if any label realizes past `is_end`), but its panel is NOT the scoring metric.
4. **Exact-field statement parity** — extended `verify_statement_provider_parity.py` to the 6's exact `_sq_q*`/`_q*` fields (§5); `live_provider_parity="passed"` only if every one passes.
5. **Skip-as-fail** — a check that didn't actually run against a present provider → `"failed"`, never `"passed"`.
6. **Definition-binding** — each of the 6 catalog expressions hashed (`sha256("base|{id}|{expr}")`) and compared to the frozen-artifact (CSV) expression hash; `bound=True` (the catalog strings are byte-identical to the validated CSV strings). Plus clean-tree + `git_sha` (the approval is bound to commit `150c1ff`; the live driver aborts on a dirty tree before the seal claim).

## 5. The parity-recompute fix (independence question — attack this)

Guard #4 required extending `verify_statement_provider_parity.py` to the 6's statement fields. Doing so surfaced a real recompute bug: the prior cumulative-diff recompute returned a STALE single-quarter value under a late single-quarter restatement (000001.SZ restated 2017-Q1 `operate_profit` to 8.242e9 in its 2018-Q1 filing in `income_quarterly`, while cumulative `income`'s 2017-Q1 row stayed 8.228e9; the provider correctly serves 8.242e9). Fix: reimplement the recompute to mirror the provider's `materialize_canonical_quarter_segments.canonical_state` — **DIRECT-QUARTER PRECEDENCE** (the `*_quarterly` reported single-quarter value when non-NaN, restatements included) with **CUMULATIVE FALLBACK** (`cur − prior_quarter_cumulative`, Q1 = cumulative). Result: 0 mismatches across 39,474 cells for the 9 statement fields the 6 use. **The independence question:** I re-implemented the provider's *spec* (reading the raw ledger families directly, NOT importing the provider's derivation functions). Is "re-implement the spec from the raw ledger, no provider-code import" still a legitimate INDEPENDENT parity check, or does mirroring the provider's algorithm make it tautological? (My view: it asserts an observable property — provider serving == independent raw-ledger recompute — and would catch a bug in the provider's *implementation* of the spec; it is not asserting "the code equals itself.")

## 6. Catalog / governance changes

- Catalog +6 via `catalog._add_sealed_oos_winners` (gated behind `include_new_data=True`; default `get_factor_catalog()` stays 111; `include_new_data=True` 147→**153**; surface 171→**177**). Expression strings are **byte-identical** to the validated CSV (so definition-binding holds). All `Ref(...)`-wrapped (PIT-safe parser passes); all field-eligible at `formal_validation` (market_daily / daily_basic / pit_fundamentals — all approved). Full count-doc sweep across code + CLAUDE.md/AGENTS.md/READMEs.
- Provenance: `sealed_oos_winners_promotion.json` (`evidence_class=single_shot_sealed_oos_leak_free_reproduction`) + a `testing_ledger` `registry_publish` event. `expected_direction='positive'` for all 6 (positive OOS ICIR).
- Tests: `test_pit_canaries.py` + `test_promotion_evidence.py` (21) green; architecture-boundary + registry + gate suites (68) green.

## 7. The questions I most want you to attack (block-the-merge or require-a-follow-up)

1. **The 5d-vs-20d horizon (§3).** Is promoting `approved` on the registration's 5-day `ls_sharpe` sound (faithful-to-registration), or does `approved` demand a horizon-consistent tradability metric — making this candidate-only until a 20d LS Sharpe is computed (on which only 2 of 6 clear 1.0)?
2. **Leak-freedom by calendar boundary (§4 guard 3).** Is "assert live `calendar_end == OOS_END` ⇒ `Ref(-h)` NaN past the boundary ⇒ no leak" a SOUND guarantee, or is there a leak path (e.g. a suspended stock whose `Ref(-h)` row-shift reaches a post-`OOS_END` price; provider calendar vs trade calendar mismatch)?
3. **Reproduction legitimacy.** Re-running the SAME already-spent 2021-2026 window (frozen set, no reselection, formal chokepoint) — legitimate `approved`-grade evidence, or circular? (Spent once in PR #28; this formalizes the seal PR #28 never recorded.)
4. **inf in `grow_total_revenue` (829 cells).** The approved factor's OOS metric matches the registration exactly, but the factor itself has inf from `q0/q4` (q4 near zero). Is that a factor-registration concern (should it be sanitized at the catalog level?), or purely a downstream deployment concern (`approved` ≠ tradable)?
5. **Parity independence (§5).** Sound, or tautological?
6. **`ebit` removal.** I removed `ebit` (a Wave-1 field, used by NONE of the 6) from the parity TARGETS because the recompute disagrees with the provider for banks (the provider's `canonicalize_report_variants` drops bank quarterly `ebit` rows the raw read keeps). Flagged as a follow-up chip. Acceptable to merge with that open, or must it be resolved first?
7. **git_sha binding.** The approval binds to `git_sha=150c1ff` (clean-tree commit, HEAD at evidence-production time). I then committed the provenance JSON + docs (HEAD moved). The recorded approval stands (the gate's git_sha check is at the transition, already passed). Any concern that later commits invalidate the bound evidence?
8. **Any path** by which the harness could emit a gate-passing artifact while the pipeline is actually unsafe, OR by which an inflated/wrong metric could have cleared the bar?

## 8. Verdict requested

**GO to merge PR #40 as-is**, **GO with a required follow-up** (specify), or **NO-GO** (specify the integrity mechanism + whether it should downgrade the 6 to `candidate`). The 6 are already `approved` on the live registry, so a NO-GO implies a rollback (`set_status` back to `candidate`/`draft`) — call that out explicitly if warranted.
