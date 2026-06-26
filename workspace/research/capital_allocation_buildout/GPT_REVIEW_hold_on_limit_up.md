# GPT cross-review packet — `hold_on_limit_up` engine fill-step (果仁 不卖条件 涨停不卖)

> **Gate:** CLAUDE.md §10 — a change to the shared EventDrivenBacktester engine must pass independent GPT
> 5.5 Pro review before it is committed as load-bearing / used in any formal path. Foreground the
> **quantitative-research principles (no-lookahead FIRST)**. Public repo: `https://github.com/henrydan111/quant-system`
> (branch `report-rc-registration`). **The embedded diff below is authoritative** (pushed at commit time;
> raw links valid post-push).

## R1 = REVISE → all 3 findings folded (this is the R2 re-review packet)
GPT R1: no-lookahead placement confirmed clean; **P1 formal-provenance gap = blocker**; 2× P2. Folded:
- **P1 (formal runs could silently enable a non-profiled rule):** `hold_on_limit_up` is now (a) recorded in
  `override_diff_record` → **provenance-stamped** (`manual_override`/`override_diff`), AND (b) gated by a
  **dedicated formal guard** that raises `OverrideRequiresReasonError` when `is_formal and hold_on_limit_up
  and not override_reason` — covering BOTH profile-formal AND run_mode-formal (the generic gate only fires
  with a profile). A formal run can enable it only WITH a documented `override_reason` (then stamped). Tests:
  `test_execution_profiles.py::test_formal_hold_on_limit_up_without_reason_raises` (+ `_with_reason_stamped`).
- **P2 (no-limit-day bypass):** the hold check now also requires `and not is_true_no_limit_day(code,date,row)`
  — mirrors the can_buy/can_sell rescue, so a no-limit IPO coverage-hole (is_limit_up spuriously True) is NOT
  held. Test: `test_hold_on_limit_up.py::test_no_limit_coverage_hole_does_not_hold`.
- **P2 (no tests):** new `tests/backtest_engine/test_hold_on_limit_up.py` (4: default-off sells / opt-in
  retains pos+cash / no-limit doesn't hold / jq_daily_avg all-day-lock) + 2 formal-guard tests. **47 targeted
  pass; full `tests/backtest_engine/` = 282 passed (no regression post-fold); #1 = +47.60% UNCHANGED**
  (folds non-behavioral for #1: no-limit-day doesn't touch its established names; #1 is non-formal so the
  formal guard doesn't fire — only the provenance stamp changes).

## R2 = APPROVE → 2 non-blocking findings folded (ready to commit)
GPT R2 verdict: **APPROVE** for the profiled/non-formal Guorn parity use — "behavioral issues are fixed
(hold check excludes true no-limit days), fill-time placement remains no-lookahead-clean". 2 non-blocking
findings, both folded:
- **P2 (run_mode-formal/no-profile override not provenance-stamped):** the override stamp (manual_override
  / override_reason / override_diff) MOVED OUTSIDE the `if profile_obj is not None` branch → now stamped for
  ANY run with overrides (profiled, run_mode-formal, or non-formal). `execution_profile_id` is Optional →
  schema-safe. Governance verified: `test_artifact_provenance` + `release_gate` + `pr8_runtime` = **38 passed**.
- **P3 (test didn't assert provenance):** `test_formal_hold_on_limit_up_with_reason_stamped` now asserts
  `result.config['artifact_provenance']` has `manual_override=True`, `override_diff['hold_on_limit_up']=True`,
  and the `override_reason` — not just the engine flag. `_run_with_mocks` returns the result for inspection.
- 47 targeted pass; **full `tests/backtest_engine/` post-all-folds = 282 passed** (0 regression); #1 +47.60% unchanged.

## What it is / why
果仁's 不卖条件 (don't-sell) "调仓日交易时涨停" = **hold a limit-up winner** (do not sell a name that is
limit-up at the rebalance trade). It is on **17 of the 20** user-deployed books. The reproduction harness
was selling those winners (model-II rank≥25), which systematically undershot 果仁 in momentum years
(#1 sm_01_成长动量: adding this lifted annual +39.5%→**+47.6%**, gap −17.4→−9.6pp, 2015 −72→+48pp).
The strategy runs `before_market_open` behind the §3.3 pre-open barrier, so it CANNOT see the same-day
limit state — the rule must live in the engine fill-step, which legitimately knows the fill-bar state
(exactly like the existing §3.3 `can_sell` limit gate). Implemented as an **opt-in, default-OFF** flag.

## Self-review (CLAUDE.md §10 prerequisite) — verdict: CLEAN FOR GPT
Checked against §3 invariants + quant principles:
- **§3.3 limit gate UNCHANGED**: adds a SEPARATE opt-in skip in `_execute_orders` BEFORE the `can_sell`
  gate; does NOT modify `can_buy`/`can_sell`/`is_limit_up`/limit-price resolution. `test_exchange_limits.py`
  + full `tests/backtest_engine/` [result pending below].
- **No-lookahead**: the skip reads `is_limit_up`/`is_all_day_limit_up` at the FILL (engine execution),
  same info the existing `can_sell` gate uses at the same point. The pre-open strategy never sees it; the
  §3.3 pre-open barrier (`test_pre_open_isolation.py`) is untouched.
- **Default-OFF / formal-safe**: `getattr(self,"_hold_on_limit_up",False)` → any engine/run not setting it
  is byte-identical; `run(... hold_on_limit_up=False)` default → wrapper unchanged unless explicitly set.
  Formal runs do not set it → unaffected.
- **limit_gate consistency**: mirrors `can_sell` — avg-fill (`limit_gate=='all_day_lock'`) → `is_all_day_limit_up`
  (一字; the synthetic avg is not a tradability state, §3.3); open/close fill → `is_limit_up(fill_price)`.
- **Semantics**: skips the SELL → position retained, cash NOT freed (no phantom cash); next bar re-evaluates.
- Minor: the log status reuses `'BLOCKED'` (a hold-choice, not a tradability block); the reason text clarifies.

## The diff (authoritative)

**`src/backtest_engine/event_driven/engine.py`** — in `_execute_orders`, the sell loop, immediately after
`row = day_indexed.loc[order.code]` and BEFORE the `can_sell` check:
```python
            # 果仁 不卖条件 "调仓日交易时涨停" (opt-in, default OFF; set via EventDrivenBacktester.run
            # hold_on_limit_up): HOLD a winner that is limit-up at the fill — skip the sell, retain the
            # position (its capital is not redeployed this bar). The engine knows the same-day limit state
            # at fill; the pre-open strategy cannot. Does NOT alter the §3.3 can_buy/can_sell gate below.
            # Limit-state mirrors the can_sell gate: daily-AVERAGE fill -> 一字 all-day lock (the synthetic
            # avg is not a tradability state); open/close fill -> is_limit_up at the actual fill column.
            if (getattr(self, "_hold_on_limit_up", False)
                    and (self.exchange.is_all_day_limit_up(row, order.code, date)
                         if limit_gate == 'all_day_lock'
                         else self.exchange.is_limit_up(row, order.code, date, price_field=fill_price))
                    and not self.exchange.is_true_no_limit_day(order.code, date, row)):   # R1 P2
                self._log_order(order, 'BLOCKED', '涨停不卖 (hold limit-up winner)')
                continue
```

**`src/backtest_engine/event_driven/__init__.py`** — `EventDrivenBacktester.run()` signature gains
`hold_on_limit_up: bool = False`. After the profile/no-profile block (R1 P1, track as override):
```python
        if hold_on_limit_up:
            override_diff_record["hold_on_limit_up"] = True
```
After `is_formal` is computed, BEFORE the generic override gate (R1 P1, formal guard covering run_mode-formal):
```python
        if is_formal and hold_on_limit_up and not override_reason:
            raise OverrideRequiresReasonError(
                "Formal run enabled hold_on_limit_up=True (果仁 涨停不卖 — a non-profiled execution rule that "
                "changes sell behavior) without override_reason. Pass override_reason='...' ...")
```
And immediately after `engine = BacktestEngine(...)`:
```python
        engine._hold_on_limit_up = bool(hold_on_limit_up)
```

## Contract sections it must honor
CLAUDE.md **§3.3** (execution/cost realism — esp. the fill-price-aware limit gate, the `is_limit_up`/`can_sell`
contract, the daily-avg `all_day_lock` rule, the pre-open no-lookahead barrier) and **§8.4** (no encoding
tradability inside the signal — here the rule is in the engine fill-step, not the strategy). It must NOT
change behavior for any run that does not set the flag.

## Review questions (please assess, no-lookahead FIRST)
1. **No-lookahead**: is applying `is_limit_up`/`is_all_day_limit_up` at the fill lookahead-free, given the
   pre-open barrier? Any path by which the same-day limit state could leak to the strategy?
2. **§3.3 gate intact**: confirm this does not alter `can_buy`/`can_sell`/`is_limit_up`/limit-price logic
   (it is a separate opt-in skip placed before `can_sell`).
3. **Formal safety**: confirm formal/existing runs (flag unset) are byte-identical (`getattr` default False +
   `run()` default False).
4. **Semantics + cash**: skipping the sell retains the position and does NOT free its cash — is that the
   correct faithful model of 果仁 涨停不卖 (hold the winner; capital stays in it; not redeployed this bar)?
5. **limit_gate-aware correctness**: avg-fill → `is_all_day_limit_up`, else `is_limit_up(fill_price)` —
   correct + consistent with `can_sell`/§3.3?
6. **Right layer**: is the engine fill-step the correct place (vs strategy), given the pre-open barrier?
7. **Edge cases**: T+1 (skip is before `portfolio.can_sell`), partial fills, suspended names, and a
   limit-up name that should still be force-sold by a 退市风险 sell-condition — any concern?
