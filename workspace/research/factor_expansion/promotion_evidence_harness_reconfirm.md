# DESIGN v2 RE-CONFIRM (for GPT) — promotion-evidence harness, 6 guards integrated

You Conditional-GO'd the harness with 6 must-fixes. All integrated below — concrete mechanism for
each. Tight re-confirm: verify the integrations are right and one consequence of #3 is acceptable,
before I build the leakage-critical harness.

## Your 6 must-fixes → how they're integrated
1. **Real seal claim.** The harness calls `HoldoutSealStore.claim_holdout_access(seal_key=<frozen-13
   hash>, design_hash=…, run_dir=…, step_id=…, stage="oos_test")` (the `SealedBacktestRunner` path)
   BEFORE the OOS compute — not a self-attested `holdout_seal_claimed=True`. This formalizes the seal
   PR #28 never recorded; the claim is the one sanctioned spend (re-claim refused unless same-run resume).
2. **Seal the full frozen 13.** `seal_key = FrozenSelectionSet.frozen_set_hash` built from the 13
   factors in `oos_frozen_topset.json` (+ selection-rule/protocol hashes) — NOT a 6-factor key. The 6
   are survivors; the budget was spent on the 13.
3. **Phase-4 belt on the OOS labels (no future-data leak).** The OOS reproduction REUSES
   `build_is_windowed_panel(factor_panel, adj_close, is_end=OOS_END=2026-02-27, horizon=h)`: factors
   computed `horizons=None` over `[2021-01-01, 2026-02-27]`, label = adj-close at the exact-calendar
   `r(t)=open_days[pos(t)+h]` capped at `OOS_END`, any `r(t) > OOS_END` dropped. PLUS assert the live
   provider calendar end == `2026-02-27`. Identical belt to the IS gate, applied to the OOS window.
4. **Exact-field statement parity.** The harness runs `verify_statement_provider_parity.py` logic for
   the EXACT fields in the 6 (`operate_profit_sq_q0/q4`, `n_income_attr_p_sq_q0/q4`,
   `total_revenue_sq_q0/q4`, `n_cashflow_act_sq_q0`, `oper_cost_sq_q0/q4`, `total_assets_q0/q4`,
   `total_cur_assets_q0/q4`, … + `close`/`adj_factor`/`turnover_rate_f`). `live_provider_parity="passed"`
   ONLY if every one of those fields passes; otherwise `"failed"`.
5. **Skipped ≠ passed.** Every check (parity, canaries, lint) asserts it actually RAN against a present
   provider; "provider absent / pytest-skipped / no rows" → recorded `"failed"`, never `"passed"`.
6. **Explicit definition binding.** The harness hashes each of the 6 catalog expressions and compares to
   the frozen-OOS-artifact expression hash; any mismatch → the harness REFUSES (approval fails) or the
   OOS must be re-run for the new definition. No approving a definition the OOS never validated.

## The one consequence of #3 I want you to explicitly bless
PR #28's OOS numbers were computed with Qlib `Ref(-h)` forward returns. The v2 reproduction uses the
**leak-free Phase-4 label** (exact-calendar `r(t)` capped at `OOS_END`) — which can differ slightly
from `Ref(-h)` near window-end / suspensions. So the reproduction is a **genuine re-test, not a
rubber-stamp**: its leak-free OOS ICIR / LS-Sharpe become the **authoritative** numbers; if any of the
6 fail the bar (sign-stable IS→OOS + OOS LS-Sharpe > 1.0) under the correct label, that factor is
**NOT approved** (the harness reflects the real result). I believe this is exactly right (the leak-free
number governs; a factor that only "passed" via a leaky label *should* fail). **Confirm** that the
reproduction's leak-free numbers — not PR #28's — are the ones that decide approval, and that a
divergence which drops a factor below the bar is a correct rejection, not a harness bug.

## Confirm
GO to build the harness as v2 (with any final tweak), or NO-GO with the remaining gap. Build arc:
`pit_canaries.py` (+ negative leak tests) → `promotion_evidence.py` (seal + belt + exact parity +
non-skip + definition-bind + self-verify) → review → C2 (catalog/sync/approve + audit +
expected_direction) → dry-run → temp validation → live `approved` write behind explicit approval on a
clean committed tree.
