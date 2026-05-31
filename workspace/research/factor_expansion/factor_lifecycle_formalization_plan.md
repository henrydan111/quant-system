# Factor Lifecycle Formalization — Implementation Plan & Codex Cross-Review Handoff

**Date:** 2026-05-31. **Author:** Claude. **For:** Codex cross-review (design/architecture pass).
**Status:** PLAN ONLY — nothing in this document is implemented yet. This is the design to
review *before* building.

**Repository:** https://github.com/henrydan111/quant-system (public).
**Related in-repo context (read for grounding):**
- `CLAUDE.md` §3 (hard invariants), §7 (research integrity), §9 (orchestrator + 5 registries)
- `AGENTS.md` §2a (Codex mirror of the invariants)
- `workspace/research/factor_expansion/` — the workstream that motivated this (proposal, audit,
  OOS results, the predefined selection rule, the catalog re-validation)
- `src/alpha_research/factor_library/catalog.py` — `get_factor_catalog()` (static code dict)
- `src/alpha_research/factor_registry/store.py` — `FactorRegistryStore`, `VALID_STATUSES`
- `src/research_orchestrator/` — DAG engine, `factor_screening` profile, `factor_screening_steps.py`
- `config/field_registry/field_status.yaml` + `src/data_infra/field_registry.py` — the field gate
- `src/research_orchestrator/release_gate.py` — `assert_promotion_artifact_eligible` (the §3 promotion gate)
- `src/alpha_research/walk_forward.py` — `build_walk_forward_folds`, `TimeSplit`

---

## 0. Why this document exists

We just executed a full factor create→evaluate→select→register **workflow** end-to-end with
reproducible evidence (factor-expansion: 69 candidates → 50 IS-screened → 13 frozen → sealed
OOS → 6 validated; plus a walk-forward re-validation of the 147 base catalog factors). It was
rigorous **as a one-off**, but it was **not a formalized, enforced, reusable process** — it
ran on ad-hoc `workspace/scripts/` + markdown rules + manual git discipline. This plan turns
that proven workflow into a **codified pipeline with enforced gates**. Codex's job in this
round is to cross-review the architecture *before* implementation, with special attention to
anything that could (re)introduce PIT leakage, OOS contamination, or silent overfit at the
*process* level.

---

## 1. Current state — what is and isn't formalized (the audit)

| Lifecycle stage | Exists | Formalized? (codified + gated + contract) |
|---|---|---|
| **Creation** | `catalog.py::get_factor_catalog()` (static dict, 147 base + 20 composite + 4 industry-rel); `operators.py` Layer-1 expressions | Static gates (PIT parser, Count-ban lint, field-existence) are **CI-enforced**. Generation/definition is **code-only, no lifecycle hook**. |
| **Evaluation** | `factor_eval/` (IC/RankIC/ICIR/quantile/decay/monotonicity, `batch_screening`), `walk_forward.py` | Methods **codified + reused**. But this session orchestrated them via **ad-hoc direct-call workspace scripts** (`screen_*`, `run_sealed_oos`, `revalidate_*`), NOT the orchestrator. |
| **Selection** | `oos_topset_selection_rule.md` + `apply_oos_topset_rule.py` (predeclared, mechanical) | **One-off research artifacts.** Rule is a workspace markdown + a script, **not a governance contract**, not reusable. |
| **Registry** | `data/factor_registry/` (`FactorRegistryStore`, statuses `draft/candidate/approved/deprecated`, `status_history`, `import_screening`); 5 typed registries via orchestrator | **Field-level governance is fully formalized + tested** (`field_status.yaml`, approvals, drift checks, dependency gate). **Factor-level registration was NOT executed** — we annotated a CSV. The registry is **disconnected from the catalog** (see §2). |

**The five concrete gaps:**
1. **Catalog ≠ registry.** `get_factor_catalog()` is static code; research never reads registry
   status. There is no status-aware access. (Verified: `catalog.py` has zero `status`/registry refs.)
2. **Orchestrator bypassed.** The formal `factor_screening` DAG profile exists and writes to the
   registry, but we ran direct-call scripts (faster for research iteration, but not enforced/reusable).
3. **Rules are artifacts, not contracts.** Selection rule, status-assignment rule, IS/OOS/walk-forward
   protocol live in `workspace/` markdown + script headers — not CLAUDE.md, not tested.
4. **Registry-write deferred & manual.** No automated honest-status publish; `approved` correctly
   gated behind the promotion gate but the whole write path was skipped this session.
5. **No registry-level multiple-testing / OOS-budget accounting.** Each one-off run reasoned about it
   locally; nothing tracks "how many hypotheses have been tested against window W."

---

## 2. Target architecture — the formalized lifecycle

### 2.1 Registry as the single source of truth
The factor registry (`data/factor_registry/`) holds **every factor ever constructed** (171 catalog +
69 expansion + future), one row each, carrying: `definition_hash`, `expression`/`components`,
`status`, `status_history`, evidence (IS + walk-forward + sealed-OOS metrics), `field_eligibility`,
`provider_build_id` binding, and `last_revalidated_at`. Nothing is deleted; failures become
`deprecated` with reason (permanent negative knowledge → never blindly re-screened).

`catalog.py` is demoted from **source** to **seed**: a `sync_catalog_to_registry()` step writes the
code-defined expressions into the registry at `draft`. From then on the **registry's status governs
what research uses**, not the code dict.

### 2.2 Status lifecycle (evidence-driven, gated transitions)
```
            static gates           walk-forward            sealed-OOS + promotion gate
 (construct) ───────────► draft ───────────────► candidate ──────────────────────────► approved
                            │                        │                                      │
                            └─ field-ineligible      └─ collapse / sign-flip ──► deprecated ◄┘ (revoked on
                               (capped at draft)         (failed holdout)                       drift/expiry)
```
| Transition | Gate (mechanical unless noted) |
|---|---|
| → `draft` | passes PIT-safety + Count-ban + field-existence; computes non-degenerate |
| `draft` → `candidate` | walk-forward sign-stable (≥N-fold consistency) AND \|ICIR\| bar AND **field-eligible** (all fields `approved`) |
| `candidate` → `approved` | sealed-OOS pass on a *frozen predeclared set* AND **strategy-level promotion gate** (`assert_promotion_artifact_eligible`: independent PIT reproduction, clean tree, provider binding) — **human-authorized** |
| any → `deprecated` | OOS/holdout collapse or sign-flip; or superseded; or provider-drift invalidation |

**Hard rule:** `approved` is the only status requiring human authorization + the promotion gate; all
others are mechanical from evidence. **Field-eligibility is a hard cap:** a factor whose expression
touches a `quarantine`/`pending`/`unknown` field can never exceed `draft` for formal use, regardless
of performance (effective usability = `min(factor_status, field_status_gate)`).

### 2.3 Status-aware access API (replaces direct catalog reads)
```python
get_factors(status_in=("approved",), prioritize="approved", as_of=...) -> dict[name, expr]
```
- **Formal stages** (formal_validation / oos_test / registry_publish) default to `approved` (or
  `approved`+`candidate` with an explicit opt-in) — **fail-closed**, mirroring the field gate.
- **Sandbox/exploration** may request all statuses, but every returned factor carries its `status`
  so the researcher always sees the tier. "Access to all" is allowed; "build formal artifacts on
  unvalidated factors" is blocked at the formal gate.

### 2.4 Codified evaluation protocol (promote scripts → `src/` modules)
The ad-hoc scripts become tested reusable components under `src/alpha_research/factor_lifecycle/`:
`static_gates.py` (wraps the validator), `is_screen.py`, `walk_forward_eval.py`, `sealed_oos.py`
(one-shot guard), `selection_rule.py` (the predeclared rule as code), `status_assign.py`.

### 2.5 Orchestrator integration
A new profile `factor_lifecycle` (or extend `factor_screening`) compiles a DAG:
`sync_catalog → static_gate → is_screen → walk_forward → status_assign(candidate) →
[frozen_set freeze] → sealed_oos → promotion_gate → registry_publish`. This makes the lifecycle
**non-bypassable** for formal runs and produces the standard run artifacts + registry publish.

### 2.6 Governance & accounting
- Promote the IS/OOS/walk-forward protocol, the selection rule, and the status lifecycle into a
  CLAUDE.md/AGENTS.md contract section (so the next session is bound by it).
- **OOS-budget ledger:** track hypotheses tested per sealed window; raise the promotion bar as the
  count grows (registry-level multiple-testing control).
- **Re-validation cadence + provider-build binding:** `approved` carries `provider_build_id`; a
  provider rebuild flags stale approvals for re-validation (reuse the approval-evidence drift pattern).

---

## 3. Design decisions & tradeoffs (where I want Codex's view)

| # | Decision | My recommendation | Tradeoff / risk for Codex to weigh |
|---|---|---|---|
| D1 | Registry-as-source vs catalog-as-source | Registry source of truth; catalog = seed | Migration risk: 171 factors referenced by name across screening/backtest code; need a compat shim so `get_factor_catalog()` still works during migration |
| D2 | Which status transitions are mechanical vs human | Only `→approved` is human+promotion-gate; rest mechanical | Over-automation could promote to `candidate` on noise; mitigate with walk-forward + multiple-testing bar |
| D3 | Walk-forward vs single sealed-OOS for `candidate` | Walk-forward (reusable, no OOS spend) for `candidate`; reserve the one-shot sealed OOS for `→approved` | Walk-forward on a-priori factors ≈ per-fold IC stability (no fitting) — is that a strong enough bar? |
| D4 | Extend `factor_screening` profile vs new `factor_lifecycle` profile | New profile (cleaner DAG), keep `factor_screening` as legacy | Duplication vs clarity; Codex: is extending the existing DAG safer? |
| D5 | Field-eligibility × factor-status interaction | Hard cap (`min`) | Does the registry store the cap explicitly, or compute it at read time from the live field registry? (live is safer — fields can be demoted) |
| D6 | OOS-budget accounting granularity | Per (sealed-window) hypothesis counter in the registry | How to count an ensemble vs individual factors as "hypotheses"? |
| D7 | Status expiry | `approved` expires on provider-build change; re-validation required | Could mass-expire approvals on every rebuild → churn. Acceptable? |

---

## 4. Phased implementation plan (file-level, incremental, each phase shippable)

**Phase 0 — Inventory & freeze the de-facto process (docs only).**
Write the current process down (this doc + a `factor_lifecycle.md` under `src/alpha_research/`).
No code. Output: shared vocabulary.

**Phase 1 — Registry schema + status lifecycle (extend `FactorRegistryStore`).**
- Add evidence columns for walk-forward + sealed-OOS + `field_eligibility` + `provider_build_id` +
  `last_revalidated_at` to the master schema.
- Implement gated `set_status` transitions (mechanical gates inline; `→approved` calls
  `assert_promotion_artifact_eligible`, mirroring `strategy_registry.set_status`).
- Tests: transition gate matrix; field-cap; status_history append.

**Phase 2 — Status-aware access API + catalog→registry seed.**
- `sync_catalog_to_registry()` writes the 147+20+4 at `draft`.
- `get_factors(status_in, prioritize, as_of)` reads the registry; field-eligibility computed live.
- Compat shim: `get_factor_catalog()` delegates to `get_factors(status_in=all)` during migration.
- Tests: formal-stage fail-closed to approved; sandbox sees all-with-status.

**Phase 3 — Codify evaluation protocol (`src/alpha_research/factor_lifecycle/`).**
- Port the workspace scripts (`validate_factor_candidates`, `screen_*`, `run_sealed_oos`,
  `revalidate_catalog_walkforward`, `apply_oos_topset_rule`) into tested modules. Keep the one-shot
  OOS guard, the predeclared-rule-as-code, the multiple-testing-robust fold consistency.
- Tests: selection rule determinism; OOS one-shot guard; walk-forward fold math.

**Phase 4 — Orchestrator `factor_lifecycle` profile/DAG.**
- DAG per §2.5; `registry_publish` at honest statuses; `approved` guarded.
- Tests: DAG compiles; publish writes expected statuses; bypass is impossible at formal stage.

**Phase 5 — Governance contracts + accounting.**
- CLAUDE.md/AGENTS.md: lifecycle + protocol + selection rule as contract; OOS-budget ledger;
  re-validation cadence; provider-build binding for approvals.
- Tests: drift/expiry; budget-counter increments.

**Phase 6 — Backfill.**
- Seed the registry from the completed catalog re-validation (147 statuses) + the expansion OOS
  results (6 candidate / 2 defer / 5 deprecated). This is the first real population.

---

## 5. Invariants the formalization MUST preserve (non-negotiable)
- **PIT:** every `$field` `Ref(...,1)` except approved ADJ atoms/labels; the formal access path
  routes through `qlib_windowed_features` / `pit_research_loader` only.
- **OOS sanctity:** sealed OOS run once per frozen set; selection rule predeclared & immutable
  post-results; no post-OOS tuning. The lifecycle must make a second OOS read on the same window a
  hard error (cache-manifest + the one-shot guard).
- **Count banned;** field gate fail-closed; promotion gate guards `approved`.
- **No silent status inflation:** every transition writes `status_history` with evidence + commit.

## 6. Risks
- **Migration regression** (D1) — name-based catalog references break. Mitigation: compat shim + a
  test that every legacy name resolves.
- **"Access to all" leakage** (§2.3) — must be enforced fail-closed at formal stage, not advisory.
- **Walk-forward over-permissiveness** (D3) — fold stability on a-priori factors may pass weak signals;
  pair with an effect-size bar + multiple-testing control.
- **OOS-budget erosion** — the more the registry evaluates, the more the single sealed window is
  spent; the ledger must actually raise the bar, not just record.
- **Scope/churn** — this is a multi-week build touching `src/`, the orchestrator, governance docs.

## 7. Open questions for Codex
1. **D1 migration:** is a compat shim + name-resolution test sufficient, or do you want a hard cutover
   with all call sites migrated in one PR? Which is lower-risk given 171 name references?
2. **D3:** for a-priori (non-fitted) factors, is per-fold IC sign-consistency a defensible
   `candidate` bar, or should `candidate` also require a held-out block (mini-OOS) — and if so, how do
   we avoid spending the sealed window?
3. **D4:** extend `factor_screening` (which already publishes to the registry) vs a new
   `factor_lifecycle` profile? Which fits the existing DAG engine better?
4. **D5:** store field-eligibility in the registry row (fast, can go stale) vs compute live from the
   field registry at read time (correct, slower)? I lean live — confirm.
5. **OOS-budget (D6):** what's the right unit of "hypothesis" and the right bar-escalation function?
6. Any **process-level PIT/OOS/overfit hole** in §2 the per-factor gates wouldn't catch?
7. Is the **status taxonomy** (`draft/candidate/approved/deprecated`) sufficient, or do we need a
   `risk_sleeve` / `short_side` status for the high-|IC|-negative-LS factors (volatility cluster,
   accruals mismatch) that are signals but not long-only alpha?

## 8. What I want Codex to deliver
- Concur/refute the target architecture (§2) and each decision (§3).
- Flag migration/leakage/contamination risks I've underweighted.
- A recommended phase ordering (is Phase 1 registry-first right, or API-first?).
- Answers to §7, especially D1 (migration), D3 (candidate bar), D5 (eligibility freshness), and Q7
  (status taxonomy for short-side signals).
- Any reuse I'm missing (does the orchestrator already provide a component I'm proposing to build?).

---

*This plan is the design to review, not built code. The empirical inputs that will seed the registry
(147-factor catalog walk-forward re-validation + the expansion-set OOS verdicts) are produced by the
runs in `workspace/research/factor_expansion/`; this document is about the standing process that
should govern all future factors so none again go through bespoke scripts.*
