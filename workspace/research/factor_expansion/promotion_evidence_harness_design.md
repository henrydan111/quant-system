# Design: promotion-evidence reproduction harness + C2 onboarding of the 6 sealed-OOS winners

**Status:** DESIGN for review (no code/registry change). **Author:** Claude, 2026-06-02.
Supersedes [sealed_oos_winners_onboarding_design.md](sealed_oos_winners_onboarding_design.md)
§4 — incorporates GPT's Conditional-GO-for-C2 + the finding that **the gate's 7 canaries have no
producer** (only the gate consumer + test fixtures exist).

## 1. Goal + the structural gap

The promotion gate (`evaluate_promotion_artifact`, [release_gate.py](../../../src/research_orchestrator/release_gate.py))
is fully built and demands a `promotion_evidence` artifact with every check explicitly `"passed"`.
**Nothing produces it.** This design builds the **reusable producer** (a formal-promotion-evidence
harness), then uses it to promote the 6 sealed-OOS winners to `approved` (C2). The harness is the
real deliverable — it unblocks *every* future `approved` promotion, not just these 6.

## 2. Target artifact (exact, from the gate + its tests)
```python
{
  "independent_reproduction": {"source": "qlib_windowed_features"},  # the OOS re-run path
  "unsafe_pit_dates_lint": "passed",
  "synthetic_lookahead_canary": "passed",
  "restatement_canary": "passed",
  "q0_canary_multiperiod": "passed",
  "q0_canary_stateful_restatement": "passed",
  "q0_canary_missing_field": "passed",
  "availability_assertion": "passed",
  "live_provider_parity": "passed",
  "dirty_tree": False,
  "git_sha": "<HEAD sha, clean tree>",
  "promotion_status": "approved",
}
```
Every value must be a **genuine attestation produced by running the check**, never a hardcoded
string (that is precisely the "hand-built blob" GPT rejected).

## 3. Harness architecture (2 new modules)

### 3a. `src/data_infra/pit_canaries.py` — the 6 PIT canaries as standalone checks
Each canary runs the relevant PIT-correctness behavior on a **controlled synthetic fixture** and
returns `"passed"`/`"failed"` + detail. The LOGIC already exists and is tested in
[test_pit_backend.py](../../../tests/data_infra/test_pit_backend.py) /
[pit_alignment_core.py](../../../src/data_infra/pit_alignment_core.py) — the canary module *packages*
it as positive attestations (it does NOT re-implement correctness):

| canary | attests | reuses |
|---|---|---|
| `availability_assertion` | `effective_date > disclosure_date` STRICTLY | `strictly_next_open_trade_day` (test_pit_backend.py:368-408) |
| `restatement_canary` | a late prior-quarter restatement retroactively updates the derived value at its effective date, not before | `derive_single_quarter_value` / `test_flow_single_quarter_derivation_tracks_late_revision` |
| `q0_canary_multiperiod` | stateful-q0 Case-A multi-period uses best-known visible state | `pit_alignment_core` stateful-q0 / `test_metric_arrays_follow_yoy_and_qoq_from_visible_period_state` |
| `q0_canary_stateful_restatement` | stateful-q0 under restatement | same kernel, restatement fixture |
| `q0_canary_missing_field` | per-field fallback when a field is missing in the direct quarter | `canonicalize_report_variants` / `test_canonical_quarter_segments...fallback_per_field` |
| `synthetic_lookahead_canary` | a synthetic value disclosed at D is NOT visible until `effective_date > D` (inject-and-confirm-blocked) | `strictly_next_open_trade_day` + the visible-period-state walk |

Each is a pure function over a synthetic ledger fixture → no live data needed → deterministic and
fast. (A canary that FAILS means the PIT pipeline regressed — the harness then refuses to emit a
passing artifact, fail-closed.)

### 3b. `src/research_orchestrator/promotion_evidence.py` — the assembler/harness
`build_promotion_evidence(*, factors, frozen_set, oos_window, qlib_dir, ...) -> dict` that:
1. runs the 6 canaries (3a);
2. runs `unsafe_pit_dates_lint` (invoke `scripts/lint_no_unsafe_pit_dates.py` over `src`+`workspace`);
3. runs `live_provider_parity` (the lag-0/lag-1 `test_pit_loader_provider_parity` check, as `run_daily_qa` does);
4. **re-runs the sealed OOS** (§4) and records `independent_reproduction={"source":"qlib_windowed_features", ...metrics, run_dir}`;
5. captures git state — **refuses unless the tree is clean** (`dirty_tree=False`) — and stamps `git_sha`;
6. assembles the artifact and **self-verifies** via `evaluate_promotion_artifact(artifact, current_git_sha=HEAD)` — raising if not eligible (so the harness can only ever emit a gate-passing artifact on a clean tree).

## 4. The sealed-OOS reproduction (GPT must-fix #2 — not the old runner)
The old `run_sealed_oos.py` is `historical_investigation` / `formal_research_allowed:false` and
installs **no** `ResearchAccessContext`, so `qlib_windowed_features` did not enforce the seal/window.
The harness instead:
- loads the **frozen 13-factor set** verbatim from [oos_frozen_topset.json](oos_frozen_topset.json)
  (`73d556a`) — **no reselection** (the set is fixed; we only reproduce);
- installs a `ResearchAccessContext` (run_id, stage=`oos_test`, `allowed_start/end` = the OOS window
  2021-01-01…2026-02-27, provider_build_id, calendar_policy_id) so `qlib_windowed_features` enforces
  the window;
- computes the panel via `qlib_windowed_features` (the formal chokepoint → `source=qlib_windowed_features`);
- recomputes the OOS ICIR / LS-Sharpe / sign-retention for the 6 and records them as the
  reproduction evidence. This is a **faithful reproduction of an already-spent window** (deliberately
  spent once, pre-registered), not a new selection — so it does not "re-spend" OOS budget.

## 5. C2 onboarding (after the harness emits a passing artifact)
1. **Catalog** (`catalog.py`): add the 6 `Ref`-wrapped expressions. Count change is **147→153 base**
   (`get_factor_catalog(include_new_data=True)`) and **171→177 total surface** (153 + 20 composite +
   4 industry-relative); default `get_factor_catalog()` stays 111 (GPT must-fix #5 wording). PIT-safety
   parser + field-registry (`formal_validation`) + factor-library tests must pass (GPT confirmed all 6
   pass the field gate + PIT parser today; `qual_piotroski_fscore_9pt` is the full 916-char/9-`If` form).
2. **Sync** (`sync_catalog_to_registry`) → 6 enter as `draft`.
3. **Promote**: `set_status('approved', current_git_sha=HEAD, promotion_evidence=<harness artifact>)`
   for each of the 6, through the gate.
4. **Audit metadata (GPT must-fix #3):** write `sealed_oos_winners_promotion.json` + a testing-ledger
   event; pass `source_run_id` so status-history points back to the artifact.
5. **`expected_direction` (GPT must-fix #4):** call `set_expected_direction` from the **signed OOS
   ICIR**, NOT the CSV `direction` column (e.g. `liq_zero_ret_days_10d` is CSV `-` but has positive
   OOS ICIR — the CSV column is unreliable here).

## 6. Tests + gated arc
- Canary unit tests (each passes on a correct fixture, FAILS on an injected-leak fixture — the
  fail-closed proof, mirroring the Phase-7 leak test).
- Harness test: emits a `_FULL_OK`-shaped artifact that `assert_promotion_artifact_eligible` accepts;
  refuses on a dirty tree / a failing canary.
- Onboarding test: the 6 reach `approved` only with the harness artifact + a clean tree + git-sha;
  `expected_direction` persisted from signed ICIR.
- Arc: design → cross-review → build harness + tests → review → build C2 → review → dry-run →
  temp-registry validation → **live `approved` write behind explicit user approval on a clean
  committed tree** (§13).

## 7a. GPT cross-review integrated (design v2, 2026-06-02) — Conditional GO + 6 hard guards

GPT GO'd "build the reusable harness now" but flagged 6 fail-open risks. All integrated; these
turn the harness from "plausible" to "build-safe":

1. **Claim the holdout seal FOR REAL (not a self-attested flag).** The harness must call
   `HoldoutSealStore.claim_holdout_access(...)` (the same path `SealedBacktestRunner` uses) BEFORE
   the OOS compute — not merely set `ResearchAccessContext(holdout_seal_claimed=True)`. The claim
   formalizes the seal that PR #28's runner never recorded; it is the ONE sanctioned spend of this
   window (a later re-claim is refused unless same-run resume — correct).
2. **Seal the FULL frozen 13-set, not the 6.** OOS budget was spent on all 13 frozen factors (the 6
   are post-OOS survivors). The `seal_key` must represent the full frozen set + selection rule +
   protocol via `FrozenSelectionSet.frozen_set_hash` ([frozen_selection_set.py](../../../src/research_orchestrator/frozen_selection_set.py)),
   built from the 13 in `oos_frozen_topset.json` — not a 6-factor key.
3. **No future-provider-data leak into the OOS labels (the Phase-4 belt, again).**
   `compute_factors(horizons=[…])` builds `Ref(-h)` forward returns; `ResearchAccessContext` checks
   requested start/end but does NOT know `Ref(-20)` realizes 20 days AFTER the factor date — so if the
   provider calendar later advances past 2026-02-27, a naive re-run would pull new data into the
   labels. Fix: the OOS reproduction REUSES the Phase-4 leak-free machinery —
   `build_is_windowed_panel(..., is_end=OOS_END=2026-02-27)`: compute factors `horizons=None` over
   `[oos_start, oos_end]`, build the exact-calendar `r(t)` label capped at `oos_end`, drop any
   `r(t) > oos_end`. PLUS assert the provider calendar end == 2026-02-27 (pin it). Same belt as the IS
   gate, applied to the OOS window — calendar-advance-robust + deterministic.
4. **Exact-field statement parity, not the generic check.** `test_pit_loader_provider_parity` does
   NOT cover all the statement-derived `_sq_q*`/`_q4` fields the 6 use. The harness runs the
   independent statement parity logic in [verify_statement_provider_parity.py](../../../workspace/scripts/verify_statement_provider_parity.py)
   for the EXACT fields in the 6 expressions (`operate_profit_sq_q*`, `n_income_attr_p_sq_q*`,
   `total_revenue_sq_q*`, `n_cashflow_act_sq_q0`, `oper_cost_sq_q*`, `total_assets_q*`,
   `total_cur_assets_q*`, …) + the price/turnover fields. `live_provider_parity="passed"` only if the
   exact-field parity passes.
5. **Skipped ≠ passed (non-skip enforcement).** A pytest/QA check that exits cleanly when the provider
   is absent must be recorded as `"failed"`, never `"passed"`. The harness asserts the provider is
   present + the check actually ran (a skip/absent → `failed` → the gate refuses). No silent pass.
6. **Explicit definition binding.** The 6 catalog expressions MUST equal the exact expressions in the
   frozen OOS artifact (`factor_candidates_merged.csv` / the frozen run). The harness compares the
   catalog `definition_hash` against the frozen-artifact expression hash; a mismatch → **fail**
   (approval refused) or the OOS must be re-run for the new definition. No approving a definition the
   OOS never validated.

**GPT's residual confirmations:** synthetic canaries + live parity are sufficient ONLY after #4+#5;
reproducing the spent window is legitimate iff same-frozen-13 + no-reselection + sealed/provenanced
(#1+#2); kernel reuse in canaries is fine given observable-value asserts + negative (injected-leak)
tests; the four fail-open risks to kill are exactly #1 (seal), #5 (skip), #3 (future-label), #6
(definition drift). (GPT note: the Windows lock-concurrency suite errored on multiprocessing pipe
creation `WinError 5` — an environment issue, not lock logic; unrelated to this design.)

## 7. Open questions for review (now mostly resolved by §7a)
1. **Canary fidelity:** is "package the existing `test_pit_backend` correctness checks as synthetic-
   fixture canaries" a strong enough attestation for `approved`, or should each canary run against the
   **live provider** (not just synthetic fixtures)? (I lean: synthetic fixtures for the lookahead/
   restatement/q0 *logic* canaries — they prove the kernel is correct — PLUS the live-provider parity
   already covers the live path. But reviewer may want a live-data canary too.)
2. **Module homes:** `pit_canaries.py` under `data_infra` (it tests the PIT backend) vs
   `research_orchestrator` (it feeds the gate). I lean `data_infra` (the checks are about the PIT
   pipeline) with the assembler in `research_orchestrator`.
3. **Does the sealed re-run need MLflow / a run artifact dir**, or is an in-process compute +
   JSON artifact sufficient for the reproduction evidence?
4. **`promotion_status` vs `label`:** the 6 get registry status `approved` (not a deployment label
   like `champion`). Confirm the artifact should carry `promotion_status="approved"` and that no
   deployment LABEL is implied (the strategy-validation is separate, per the prior design).
5. **Scope check:** the harness is a net-new formal capability — is it in-scope to build now, or
   should it be its own milestone with the 6 held at `candidate` (C3) in the meantime?
