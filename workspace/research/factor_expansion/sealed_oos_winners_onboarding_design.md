# Design: onboard the 6 sealed-OOS expansion winners into the formal registry

**Status:** DESIGN for review (no code/registry change yet). **Author:** Claude, 2026-06-02.
**Decision owner:** user (+ optional GPT cross-review), mirroring every factor-lifecycle phase.

## 1. What these 6 are, and why they are special

Six factors were validated in the Round-6 sealed-OOS run (PR #28, 2026-05-31): the IS screen
froze a 13-factor top set *before* the OOS run; the OOS window (2021-01-01 → 2026-02-27) was run
**once**, through the sanctioned `compute_factors(oos_test)` → `qlib_windowed_features` path
(the formal data chokepoint). 6 passed (sign-stable IS→OOS + OOS long-short Sharpe > 1.0):

| factor | cat | sign | OOS ICIR | OOS LS Sharpe | retain | Qlib expression (all `Ref`-wrapped → PIT-safe) | fields |
|---|---|---|---|---|---|---|---|
| `liq_zero_ret_days_10d` | Liquidity | − | +0.41 | +2.14 | 139% | `Sum(If(Abs(Ref(close*adj,1)/Ref(close*adj,2)-1)<1e-4,1,0),10)/10` | close, adj_factor |
| `rev_turnover_spike_5d` | Reversal | + | +0.28 | +2.68 | 103% | `0-((Ref(close*adj,1)/Ref(close*adj,6)-1)*(Mean(Ref(turnover_rate_f,1),5)/Mean(Ref(turnover_rate_f,1),60)))` | close, adj_factor, turnover_rate_f |
| `grow_total_revenue_yoy_accel_q` | Growth | + | +0.26 | +3.44 | — | `Delta(Ref(total_revenue_sq_q0,1)/Ref(total_revenue_sq_q4,1)-1,63)` | total_revenue_sq_q0/q4 |
| `grow_n_income_attr_p_yoy_accel_q` | Growth | + | +0.25 | +1.96 | — | `Delta(Ref(n_income_attr_p_sq_q0,1)/Ref(n_income_attr_p_sq_q4,1)-1,63)` | n_income_attr_p_sq_q0/q4 |
| `grow_operate_profit_yoy_accel_q` | Growth | + | +0.20 | +1.49 | — | `Delta(Ref(operate_profit_sq_q0,1)/Ref(operate_profit_sq_q4,1)-1,63)` | operate_profit_sq_q0/q4 |
| `qual_piotroski_fscore_9pt` | Quality | + | +0.21 | +1.20 | — | 9-term `If(...)` sum of statement line-items | n_income_attr_p/n_cashflow_act/oper_cost/total_assets/total_cur_assets … (all `_q0/_q4` PIT) |

**They are the ONLY factors in the system with genuine, formal-path, single-shot sealed-OOS
evidence.** (The 87 lifecycle candidates are `oos_informed_backfill` — IS-only verdicts whose
*selection* used prior OOS knowledge; 2021–2026 is burned for them. The 6 are the opposite: their
2021–2026 OOS was a real sealed test.)

**Current state:** recorded ONLY in research artifacts (`oos_frozen_topset.json`,
`oos_results_and_registration.md`, `factor_candidates_merged.csv`). **Not in `get_factor_catalog`,
not in `factor_registry`, not in `candidate_registry`.** The registration was intentionally
conservative per the /goal irreversible-change caution.

## 2. The key distinction this design rests on

**Registry STATUS (a factor claim) ≠ deployment readiness (a strategy claim).**
- `candidate`/`approved` attest that *the factor* has predictive evidence at the stated level.
- PR #28's "NEXT: strategy-level validation" is about whether a *strategy built on these factors*
  is tradable and profitable after costs (cross-sectional LS Sharpe ≠ long-only net return).

These are **separable**. Onboarding the 6 as factors (with their factor-level sealed-OOS proof)
does **not** require the strategy validation first; the strategy validation is a downstream
deployment gate, not a factor-registration prerequisite. The design treats them separately.

## 3. The onboarding path (3 steps)

### Step A — add the 6 to the code catalog (`catalog.py`)
- Add the 6 `qlib_expression`s to `get_factor_catalog` (new rows in their categories: 3 Growth,
  1 Liquidity, 1 Reversal, 1 Quality). Catalog count **171 → 177** (153 base + 20 composite + 4
  industry-relative). Update the documented count everywhere (`grep -rn 171` sweep, per the PR-10
  precedent that fixed the 191→171 drift).
- **PIT-safety:** all 6 are already `Ref`-wrapped (verified above). The parser-based
  `tests/alpha_research/test_factor_library_pit_safety.py` must pass for the new rows (every
  `$field` inside a `Ref(...)` frame). Add per-operator expression-lock entries if the suite
  requires them.
- **Field-registry:** verify every field resolves to an `approved` dataset at `formal_validation`
  via `evaluate_field_dependencies`. Expected: `close`/`adj_factor` → market_daily (approved),
  `turnover_rate_f` → daily_basic (approved), the `_sq_q*`/`_q*` statement line-items →
  pit_fundamentals/statement families (approved). The merged CSV already stamped
  `formal_eligible=yes`, but re-verify at onboarding (fail-closed if any field is quarantine).
- Tests: the factor-library suite + a compute smoke (the 6 produce finite values over a window).

### Step B — sync into the registry as `draft`
- `sync_catalog_to_registry` → the 6 enter `factor_registry` as `draft` v1 (177 current rows),
  definition-bound (their `definition_hash` = the catalog hash). Non-privileged, reversible.

### Step C — promote (the fork — see §4)

## 4. The promotion fork (the decision for review)

There is **no "promote to candidate using OOS evidence" path** — the `candidate` tier is produced
by the IS-only `factor_lifecycle` gate; the `approved` tier by the promotion gate. So for the 6:

**Option C1 — `candidate` via the IS-only `factor_lifecycle` gate.**
Run them through the Phase-5/7 gate (IS-only 2014-2020 walk-forward). Pros: uniform with the 87;
simple; reversible-ish (candidate). Cons: **redundant + wasteful** — it re-auditions IS-only and
*ignores their real sealed-OOS proof*, under-selling them; and it would re-burn nothing (IS only).
The 6 would sit at `candidate` next to the `oos_informed_backfill` 87, indistinguishable despite
having *stronger* (real-OOS) evidence.

**Option C2 — `approved` via the promotion gate (recommended).**
The 6 are the one set whose evidence *qualifies* for `approved`: their sealed-OOS reproduction came
through `qlib_windowed_features` (the gate's required `source ∈ {qlib_windowed_features,
joinquant_native_pit, audited_pit_source}`). `set_status('approved')` requires, and we would supply:
- `current_git_sha` (the onboarding commit) + a clean working tree;
- `promotion_evidence` built from the sealed-OOS run: `source='qlib_windowed_features'`, the OOS
  window, the per-factor OOS ICIR / LS-Sharpe / retain, and the `screening_oos/` run_dir;
- `unsafe_pit_dates_lint=='passed'` (the 6 are `Ref`-wrapped, no raw `pit_ledger` reads) +
  `live_provider_parity` passed (both already enforced in `run_daily_qa`).
Cons: `approved` is irreversible-grade and the gate is strict — the `promotion_evidence` artifact
must be **constructed** from the sealed-OOS outputs (the run recorded candidate artifacts, not a
promotion_evidence blob), and verified against `assert_promotion_artifact_eligible` before the write.

**Option C3 — `candidate` first, `approved` later.**
C1 now (uniformity), then C2 after the strategy-level validation. Most conservative; but C1's
IS-only re-audition is still the redundant-evidence concern, and it muddies "why are real-OOS
factors sitting at candidate?".

**Recommendation: C2** — onboard the 6 and promote them straight to `approved` via the promotion
gate, because (a) they genuinely earned it (single-shot sealed OOS through the formal path), (b) it
is the gate *designed* for exactly this evidence, and (c) it keeps the registry honest: `approved`
should mean "real OOS proof," and only these 6 have it. The strategy-level validation proceeds
**in parallel** as the deployment gate, not as a blocker on the factor status.

## 5. Risks / open questions for the cross-review

1. **Is C2 (straight to `approved`) too aggressive**, or correct given the evidence is the strongest
   in the system? (My view: correct — this is what `approved` is *for*; the 87 stay candidate
   precisely because they *lack* this.)
2. **Constructing `promotion_evidence` from the sealed-OOS run** — is the `screening_oos/` artifact
   set sufficient to satisfy `assert_promotion_artifact_eligible`, or must the OOS be **re-run**
   under a promotion-evidence-emitting harness? (Need to inspect `release_gate.py`
   `assert_promotion_artifact_eligible` + the `screening_oos/` outputs. If a re-run is needed, note
   that re-running the *same* sealed window is fine here — it was already spent once, deliberately,
   and C2 is a faithful reproduction, not a new selection.)
3. **`qual_piotroski_fscore_9pt` truncation** — its expression is long (9 `If` terms); confirm the
   full expression (not the CSV-truncated form) is captured and PIT-safe.
4. **Field-registry re-verification** — confirm the `_sq_q*` statement-derived PIT fields are
   `approved` at `formal_validation` today (datasets/statuses can have shifted since the CSV stamp).
5. **Catalog-count doc sweep** — adding 6 base factors changes 171→177; the docstrings/README/
   tests that pin "171" must move in lockstep (there is a known invariant about this count).
6. **Should the 3 `grow_*_yoy_accel_q` be flagged** given the *level* `grow_*_yoy` factors were
   IS-overfit OOS-collapsers (Phase 6)? The acceleration variants are a *different* signal and
   passed sealed OOS — but worth an explicit note so they're not confused with the collapsers.

## 6. Scope if approved to build
- `catalog.py` (+6 rows) + count-doc sweep + PIT-safety/field-registry/test pass (Step A).
- `sync_catalog_to_registry` (Step B).
- Construct + verify `promotion_evidence`; `set_status('approved', current_git_sha=…,
  promotion_evidence=…)` for the 6 through the gate (Step C2) — dry-run → temp-registry validation
  → live, mirroring Phases 6–7, with the live write behind your explicit approval (§13).
- Provenance: a `sealed_oos_winners_promotion.json` artifact + a testing-ledger event.
- Strategy-level validation (PR #28's NEXT) tracked SEPARATELY as the deployment gate.
