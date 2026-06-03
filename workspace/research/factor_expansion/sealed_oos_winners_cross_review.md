# DESIGN Cross-Review (for GPT) — onboard the 6 sealed-OOS winners into the formal registry

You are reviewing a **design** (no code/registry change yet) to bring 6 sealed-OOS-validated
factors into the formal factor registry, and the recommendation to promote them straight to
**`approved`**. No repo access — everything needed is embedded. Find any integrity/leakage hole,
any unsound step, any mis-stated gate behavior. A NO-GO with specifics beats a GO.

## 0. Context you need
- The system has a factor lifecycle: `draft → candidate → approved → deprecated`. `candidate` is
  produced by an **IS-only** walk-forward gate (Phases 5–7). `approved` is produced by a
  **promotion gate** that demands an *independent PIT-correct OOS reproduction*.
- The live registry has **87 `candidate` + 84 `draft` + 0 `approved`**. The 87 are
  `oos_informed_backfill`: IS-only verdicts whose *selection* used prior full-window knowledge, so
  2021–2026 is **burned** for them — that's exactly why they are NOT approved.
- **The 6 here are different.** In Round-6 (PR #28, 2026-05-31): an IS screen froze a 13-factor top
  set **before** the OOS run (rule pre-registered in `oos_topset_selection_rule.md`); the OOS window
  (2021-01-01 → 2026-02-27) was run **once**, through the sanctioned `compute_factors(oos_test)` →
  `qlib_windowed_features` path. 6 passed (sign-stable IS→OOS + OOS long-short Sharpe > 1.0). They
  are recorded ONLY in research artifacts — **not in the catalog, factor_registry, or
  candidate_registry.**

## 1. The 6 (all `Ref`-wrapped → PIT-safe; all use approved-dataset fields)

| factor | sign | OOS ICIR | OOS LS Sharpe | expression |
|---|---|---|---|---|
| `liq_zero_ret_days_10d` | − | +0.41 | +2.14 | `Sum(If(Abs(Ref(close*adj,1)/Ref(close*adj,2)-1)<1e-4,1,0),10)/10` |
| `rev_turnover_spike_5d` | + | +0.28 | +2.68 | `0-((Ref(close*adj,1)/Ref(close*adj,6)-1)*(Mean(Ref(turnover_rate_f,1),5)/Mean(Ref(turnover_rate_f,1),60)))` |
| `grow_total_revenue_yoy_accel_q` | + | +0.26 | +3.44 | `Delta(Ref(total_revenue_sq_q0,1)/Ref(total_revenue_sq_q4,1)-1,63)` |
| `grow_n_income_attr_p_yoy_accel_q` | + | +0.25 | +1.96 | `Delta(Ref(n_income_attr_p_sq_q0,1)/Ref(n_income_attr_p_sq_q4,1)-1,63)` |
| `grow_operate_profit_yoy_accel_q` | + | +0.20 | +1.49 | `Delta(Ref(operate_profit_sq_q0,1)/Ref(operate_profit_sq_q4,1)-1,63)` |
| `qual_piotroski_fscore_9pt` | + | +0.21 | +1.20 | 9-term `If(...)` sum of statement line-items (`_q0/_q4` PIT) |

Note: the 3 `grow_*_yoy_accel_q` are growth-**acceleration** (Δ of the YoY rate); the growth-**level**
`grow_*_yoy` factors were IS-overfit OOS-collapsers in Phase 6 — a *different* signal.

## 2. The promotion gate's ACTUAL requirements (verified in `release_gate.py`)
`evaluate_promotion_artifact` / `assert_promotion_artifact_eligible` requires ALL of:
- `reproduction_source ∈ {qlib_windowed_features, joinquant_native_pit, audited_pit_source}` — the
  sealed-OOS run used **`qlib_windowed_features`**, so this passes.
- `unsafe_pit_dates_lint == "passed"` (the 6 are `Ref`-wrapped, no raw `pit_ledger` reads; runs in `run_daily_qa`).
- `live_provider_parity == "passed"` (also in `run_daily_qa`; `not_required_for_label` is illegal here).
- clean working tree (`dirty_tree` must be explicitly `False`) + a `git_sha` matching the onboarding commit.
- a `reproduction_evidence` blob (the OOS metrics / run reference).
`set_status('approved')` ALSO requires a mandatory `current_git_sha`. All satisfiable.

## 3. The path (3 steps) and the fork
**A.** Add the 6 to `get_factor_catalog` (171→177), with PIT-safety (parser test) + field-registry
(`evaluate_field_dependencies` at `formal_validation`) + factor-library tests + a count-doc sweep.
**B.** `sync_catalog_to_registry` → 6 enter as `draft` (reversible).
**C.** Promote — the fork:
- **C1** `candidate` via the IS-only gate: redundant; it re-auditions IS-only and *ignores* the real OOS proof.
- **C2 (recommended)** straight to `approved` via the promotion gate using the sealed-OOS evidence:
  the gate is *designed* for exactly this; constructs `promotion_evidence` (source=`qlib_windowed_features`,
  the OOS metrics, the `screening_oos/` run_dir) + the lint/parity/clean-tree/git-sha.
- **C3** candidate-now, approved-after-strategy-validation.

**Core conceptual claim:** registry STATUS (a *factor* claim) ≠ deployment readiness (a *strategy*
claim). PR #28's "strategy-level validation NEXT" is the *deployment* gate; it does **not** block
*factor* registration. So C2 promotes the factors now; the strategy validation proceeds separately.

## 4. The questions I most want you to attack
1. **Is C2 (straight to `approved`) sound?** The OOS was a *single-shot, pre-registered* sealed test
   (top set frozen by a written rule BEFORE the one-time OOS run). I claim that is precisely the
   evidence `approved` should certify, and there is no double-dipping (selection used IS only; OOS
   spent once). Is there ANY leakage/overfitting path I'm missing — e.g., was the *13-set freeze*
   itself influenced by OOS, or the OOS run repeated/peeked? (Design assumes the PR #28 record is
   accurate: frozen-then-one-shot.) If you distrust the record, the safe fallback is C3.
2. **`promotion_evidence`: construct vs re-run.** The gate checks a *source label* + lint + parity +
   clean-tree + git-sha + a `reproduction_evidence` blob — it does **not** appear to re-validate the
   OOS numbers. So a constructed config with the right source label would pass. Is that **strong
   enough** for an `approved`-grade write, or should the design **re-run** the sealed OOS under a
   promotion-evidence-emitting harness (re-running the *same already-spent* window is fine — it was
   deliberately spent once; a faithful reproduction is not a new selection)? I lean re-run for a
   defensible artifact; your call.
3. **Is "registry status ≠ deployment readiness" the right framing**, i.e. is it legitimate to mark
   a factor `approved` while its *strategy* is unvalidated? Or should `approved` itself imply
   cost-adjusted tradability (making strategy-validation a prerequisite, i.e. forcing C3)?
4. **The 3 `grow_*_yoy_accel_q`** — distinct enough from the collapsed `grow_*_yoy` level factors to
   trust, or guilty-by-association enough to hold at `candidate`?
5. **Mechanics traps:** PIT-safety of `qual_piotroski_fscore_9pt` (long 9-term `If` expression);
   re-verifying the `_sq_q*` statement fields are `approved` today; the 171→177 count-doc sweep.

## 5. Verdict requested
For each: GO to build C2 (with any required changes — e.g. "re-run the OOS for the evidence" or
"C3 not C2"), or NO-GO with the specific integrity concern. The build would be dry-run →
temp-registry validation → live, with the live `approved` write behind explicit user approval.
