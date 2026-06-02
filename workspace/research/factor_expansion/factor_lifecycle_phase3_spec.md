# Factor-lifecycle Phase 3 — `get_factors()` + staged catalog→registry cutover (DESIGN, pre-build)

Status: **DESIGN v2 — conditional-GO review integrated; ready for confirm before build.** Round-1 design
review (architecture-enforcement lens) returned a conditional GO with 4 required changes — all integrated:
(1) required `stage=` arg refusing formal stages; (2) drift default `skip` (was `code_warn`); (3) base-only
compute-ready `get_factors` + a richer `FactorSelection`/`get_factor_records` for composites+metadata;
(4) no auto-sync, empty registry RAISES. The 7 open questions are resolved below. Phases 1 (5 enforcement
gates) and 2 (evidence schema) are MERGED to `wave1-field-promotion`. This is the read-path layer. Plan: §4 Phase 3 of
[factor_lifecycle_formalization_plan.md](factor_lifecycle_formalization_plan.md) — "`get_factors()` +
`sync_catalog_to_registry()` (staged cutover; static catalog kept for seeds/tests)". Spec sibling:
[factor_lifecycle_phase2_spec.md](factor_lifecycle_phase2_spec.md).

## Goal
Give research/sandbox a **status-aware** way to select factors from the registry — `get_factors(status_in,
prioritize)` — and a maintenance entry `sync_catalog_to_registry()` that keeps the registry in step with the
code catalog. The static `get_factor_catalog()` (and `get_composite_defs` / `get_industry_relative_defs`)
remain the **authoritative, computable definition source** (seeds, tests, every formal expression). Phase 3
is **purely additive** read convenience — it changes NO existing call site and weakens NO Phase-1/2 gate.

## The single most important rule (carried from plan §2.6 / §6 + P1.2)
`get_factors()` is **convenience for research/sandbox only** (plan line 127-128: "it does NOT carry the
formal gate — the resolver + writer do"). It MUST NOT become a back-door that lets a non-`approved` factor
enter a FORMAL path. Formal validation continues to resolve through the registry **resolver allow-set**
(`handle_validation_object_resolver`, P1.2) + the **definition-binding gate** (`_assert_no_definition_drift`,
P1.3) + the field gate. The Phase-3 risk is exactly the Phase-1 reader-gate risk one level up: a convenience
read that silently substitutes for the gated read. The boundary-enforcement mechanism (below) is the crux of
this review.

## Current state (grounding)
- `get_factor_catalog(include_new_data=False, include_hypothesis_factors=None)` → `OrderedDict{factor_id:
  qlib_expression_string}` (147 base; PIT-safe `Ref(...,1)`). Composites via `get_composite_defs()` (20),
  industry-relative via `get_industry_relative_defs()` (4). Total runtime universe = 171.
- **42 call sites across 18 files** consume `get_factor_catalog(` today (screening entry points, theme
  components, `validation_steps`, tests). This is the cutover blast radius — Phase 3 leaves all 42 untouched.
- `FactorRegistryStore.sync_catalog()` already mirrors the code catalog into the registry (new factor →
  `draft` row; definition change → new version). `export_current(status=...)` returns master rows.
- `get_factors()` does **not** exist yet.

## Boundary / non-goals (Phase 3)
NO consumer migration (all 42 `get_factor_catalog` call sites stay); NO status changes / promotion (Phase 6);
NO `factor_lifecycle/` modules (Phase 4); NO orchestrator profile (Phase 5); NO `FrozenSelectionSet`→seal
wiring; NO formal-gate change. Definition source stays **code** (registry pseudo-expressions like
`COMPOSITE(...)` / `INDUSTRY_REL[...](...)` are NOT computable and are never returned for computation).

## P3.1 — `get_factors()` contract (REVISED per design review)
Module-level, in [src/alpha_research/factor_library/catalog.py](src/alpha_research/factor_library/catalog.py)
(next to `get_factor_catalog`), re-exported from `factor_library/__init__.py`. Returns **BASE expressions
only** — a genuinely compute-ready drop-in for `compute_factors`; composites/industry-relative come from the
richer selection API (P3.1b), never as fake Qlib strings in this dict.

```python
SANDBOX_STAGES = ("sandbox_screening", "vectorized_screening")
FORMAL_STAGES  = ("formal_validation", "oos_test", "registry_publish")

def get_factors(
    *,
    stage,                          # REQUIRED: must be in SANDBOX_STAGES; a FORMAL stage RAISES
    status_in,                      # REQUIRED, explicit set/seq of {"draft","candidate","approved","deprecated"}
    prioritize=None,                # optional ordering key; None -> catalog order
    include_new_data=False,         # passed through to the code catalog (definition source)
    registry_dir=None,              # default data/factor_registry (config-derived)
    on_drift="skip",                # default "skip"; "code_warn" | "raise" are explicit opt-ins
) -> "OrderedDict[str, str]":       # {base_factor_id: qlib_expression_string} — compute-ready, base only
```

Semantics (fail-closed):
1. **Required `stage=`; formal stages refused at runtime (review req #1).** `stage not in SANDBOX_STAGES`
   raises `FormalStageNotAllowedError` (in particular every `FORMAL_STAGES` value). The architecture test
   (below) is defense-in-depth; this makes misuse loud at the call site, since Python can hide an import via
   alias / module-import / `getattr`.
2. **Registry = status FILTER only; code = definition SOURCE.** Load registry current rows, keep those whose
   `status ∈ status_in`, and for each kept BASE `factor_id` return the **code** expression
   (`get_factor_catalog(...)[factor_id]`). The registry NEVER supplies the computed expression — preserves
   computability + keeps the static catalog authoritative (plan: "static catalog kept for seeds/tests").
3. **`status_in` REQUIRED + explicit** — no default (review Q1). All 171 rows are `draft` today, so every
   implicit default is a trap. Unknown status token in `status_in` → raise.
4. **Definition drift default = `skip` (review req #2 / Q3).** A `factor_id` whose registry `definition_hash`
   ≠ the current code hash (`current_catalog_definition_hashes()`) is SKIPPED + warned by default — applying
   an old `candidate`/`approved` status to a changed code definition is misleading even in sandbox.
   `on_drift="code_warn"` (return code def + warn) and `"raise"` are explicit opt-ins for debug/triage.
5. **Empty registry RAISES, never returns `{}` (review req #4).** Zero current rows → `RegistryNotSyncedError`
   ("run sync_catalog_to_registry() first") so an unsynced registry can't masquerade as a valid empty filter.
   A non-empty registry with no rows matching `status_in` returns `{}` (a real, legitimate filter result).
6. **`prioritize`** (optional): order the returned dict by a registry metric — `"long_only_viable_provisional"`
   (viable→review_only→non_viable), `"latest_oos_rank_icir"` desc, `"signal_role_suggested"`. Pure ordering,
   never filters. Meaningful only once Phase-2 evidence is populated.
7. **Registry/catalog name mismatch:** a registry name absent from code is dropped + warned (can't compute);
   a code name absent from the registry is NOT auto-included (Phase 3 never silently widens the set — sync
   first). No auto-sync (review req #4 / Q5): reads stay reads.

## P3.1b — `get_factor_selection()` + `FactorSelection` (richer API, review req #3 / Q2,Q6)
Because composite + industry-relative factors are NOT computable Qlib strings — they flow through
`add_composites()` / `add_industry_relative_composites()` over a base `factors_df` — the status-aware
selection that includes them is a structured object, never a `{name: pseudo_expression}` dict:

```python
@dataclass(frozen=True)
class FactorSelection:
    base_expressions: "OrderedDict[str, str]"   # compute-ready; == get_factors(...) PLUS bases required by
                                                #   any selected composite/industry-rel (union, for compute-readiness)
    composite_defs: list                        # get_composite_defs() filtered to selected composite NAMES
    industry_relative_defs: list                # get_industry_relative_defs() filtered to selected names
    records: list                               # per-factor FactorRecord (see fields below)
    def get_factor_records(self) -> list: ...   # the `records` list (status/role/viability triage)

def get_factor_selection(*, stage, status_in, prioritize=None, include_new_data=False,
                         registry_dir=None, on_drift="skip") -> FactorSelection: ...
```
Each `FactorRecord` carries: `factor_id`, `kind` (base/composite/industry_relative), `status`,
`approval_validity`, `signal_role`(+`_suggested`), `long_only_viable_provisional`, `latest_oos_rank_icir`,
`definition_hash`, `drift_state`, and — first-class, per review discipline — **`selected: bool`** +
**`selection_role ∈ {"selected", "dependency"}`** + **`dependency_included: bool`** so a status-`draft` base
pulled in only to make a selected composite computable can NEVER be confused with a status-matched selection.
- Same `stage=` refusal, `status_in`-required, `skip`-default-drift, empty-registry-raises rules as P3.1.
- **Compute-readiness for composites (decision A, review-confirmed).** When a composite/industry-relative
  factor is selected, its base DEPENDENCIES are unioned into `base_expressions` even if those bases are at a
  different status — matching the repo compute path (`add_composites` / `add_industry_relative_composites`
  expect the base columns to already exist, else they skip). Each such base is `selection_role="dependency"`
  / `dependency_included=True` / `selected=False` in `records`.
- `get_factors(...)` is exactly the STRICT base-status filter (dependency-only bases EXCLUDED), so the plain
  API never surprises a caller with off-status factors; `FactorSelection.base_expressions` is that set PLUS
  the dependency bases (compute-ready).
- **Explicit test (review):** select a composite whose base deps are `draft`/off-status while requesting
  `status_in={"candidate"}` → `FactorSelection.base_expressions` INCLUDES the deps (computable) and tags them
  dependency-only in `records`; `get_factors(status_in={"candidate"})` does NOT include them.

## P3.2 — `sync_catalog_to_registry()` (staged cutover)
Thin module-level wrapper over `FactorRegistryStore.sync_catalog()` + a **parity report**:

```python
def sync_catalog_to_registry(*, registry_dir=None, record_run=True, dry_run=False) -> dict:
    # returns {synced, new_drafts, new_versions, catalog_only, registry_only, parity_ok}
```
- Idempotent; new factor → `draft`, definition change → new version (existing `sync_catalog` behavior, never
  writes `approved` — Phase-1 writer gate stands).
- Emits a **parity diff** (`catalog_only` / `registry_only`) so a cutover operator sees exactly what the sync
  changed. `dry_run=True` reports without writing. This is the "staged" control surface.
- Wired into a maintenance path only (NOT auto-run inside `get_factors`, per Q5 default).

## Staged cutover + back-compat + rollback
- **Additive.** `get_factor_catalog` unchanged; all 42 call sites keep working. `get_factors` is opt-in for
  NEW sandbox/discovery code.
- **Staged.** Catalog stays authoritative for definitions; registry is kept in sync; any future consumer
  migration is per-call-site and out of Phase-3 scope.
- **Rollback.** Because nothing is migrated, rollback = "don't call `get_factors`". No data migration, no
  schema change, no irreversible step. The registry itself is unchanged by reads.

## Safety boundary — preventing a formal-gate bypass (review crux; BOTH layers required)
Defense-in-depth, both layers (review req #1 / Q4 — neither alone is enough):
1. **Runtime `stage=` refusal (primary).** `get_factors` / `get_factor_selection` require `stage` and raise
   on any `FORMAL_STAGES` value. Loud at the call site; immune to import aliasing.
2. **AST-usage architecture test (secondary).** Mirrors [tests/architecture/test_dormant_module_boundaries.py](tests/architecture/test_dormant_module_boundaries.py)
   but scans **AST usage of the `get_factors` / `get_factor_selection` NAMES** (call/attribute), NOT just
   `import` statements — because formal-path modules (`release_gate`, `validation_steps`, `event_driven/`,
   `sealed_backtest_runner`, `resolver`) **legitimately** import `get_factor_catalog` from the same package,
   so an import-only scan both misses aliased usage and can't distinguish the allowed sibling. The test fails
   if any formal-path module references `get_factors`/`get_factor_selection`.
3. **Docstring contract:** both functions state "sandbox/discovery only; not a formal gate; formal factor
   resolution goes through the resolver allow-set (P1.2) + definition-binding (P1.3)".
- **Other bypass vector flagged in review:** a sandbox script could `get_factors(...)`, persist the names,
  and later feed them to a formal run. That residual path is OUT of `get_factors`'s control — it is closed
  where it must be: the formal resolver still status-gates every name and P1.3 still definition-binds, so a
  laundered name buys nothing. `get_factors` is not, and cannot be, the formal authority.

## Risks (plan §6) + the tests that close them (incl. review's extra tests)
- **Migration regression / name-resolution** → `test_get_factors_name_parity`: over a freshly-synced
  registry, `get_factors(stage="sandbox_screening", status_in={all-non-deprecated})` returns exactly the
  catalog BASE names with expressions identical to `get_factor_catalog` (no silent drop/rename); round-trips
  for `include_new_data` True/False; `get_factor_selection(...)` returns composite/industry-relative defs
  SEPARATELY (filtered to selected names), never as base names or fake expressions.
- **Compute-readiness** → `test_get_factors_base_dict_is_compute_ready`: the base dict feeds `compute_factors`
  unchanged; `test_get_factor_selection_composites_compute`: `base_expressions` + filtered `composite_defs`
  feed `compute_factors` → `add_composites` end-to-end (dependency bases auto-included).
- **Formal-gate bypass** → `test_get_factors_refuses_formal_stage` (every `FORMAL_STAGES` value raises) AND
  the AST-usage architecture test (no formal-path module references `get_factors`/`get_factor_selection`).
- **Drift handling** → `test_get_factors_drift_modes`: drifted factor SKIPPED by default; `code_warn` returns
  code def + warns; `raise` raises.
- **Status filter correctness** → after `set_status` to `candidate`/`deprecated`, inclusion/exclusion is
  exact; `deprecated` returned ONLY when explicitly in `status_in`.
- **Sync / empty** → `test_get_factors_empty_registry_raises` (`RegistryNotSyncedError`, NOT `{}`);
  `test_sync_catalog_to_registry_parity` (`dry_run` reports `catalog_only`/`registry_only` without writing;
  real run creates `draft`s/new versions, never `approved`); unknown `status_in` token → raise.
- **Name-mismatch** → registry-only name dropped + warned; catalog-only name NOT auto-included (sync-first).

## Open questions — RESOLVED (design review, conditional GO)
1. **`status_in` default** → REQUIRED-explicit, no default (all 171 are `draft`, every default is a trap). ✓
2. **Return shape** → BOTH: plain `{name: expression}` base drop-in (`get_factors`) + a richer
   `FactorSelection` / `get_factor_records` (status, role, viability, hashes, drift, composite defs). ✓ (P3.1b)
3. **Drift policy default** → `skip` (don't apply an old registry status to a changed code definition);
   `code_warn` / `raise` are explicit opt-ins. ✓ (req #2)
4. **Bypass prevention** → BOTH a required `stage=` refusal AND an AST-USAGE architecture test (not import-
   only — formal modules legitimately import the sibling `get_factor_catalog`). ✓ (req #1)
5. **Auto-sync** → NO. Reads stay reads; explicit `sync_catalog_to_registry(dry_run=...)` with a parity diff;
   `get_factors` reports stale/missing names but never mutates; empty registry RAISES. ✓ (req #4)
6. **Composite / industry-relative** → return names/defs in `FactorSelection`, never expanded base names and
   never fake Qlib strings; matches the two-stage `add_composites` compute model. ✓ (req #3)
7. **Scope** → ZERO consumer migration in Phase 3. Do NOT move a live discovery entry point; instead prove
   `get_factors` output feeds the existing compute path for base factors AND that composite defs are filtered
   separately (tests above). ✓

## Build order (review-confirmed) — safety tests land WITH their slice, not only at the end
1. **P3.1** — `get_factors` + required `stage=` (formal refusal) + drift-`skip` + empty-registry-raise, **WITH**
   `test_get_factors_refuses_formal_stage` + the AST-usage boundary test + name-parity + drift-modes.
2. **P3.1b** — `FactorSelection` / `get_factor_records` + composite/industry-relative dependency handling
   (decision A), **WITH** the compute-readiness + off-status-dependency tests.
3. **P3.2** — `sync_catalog_to_registry(dry_run=…)` + parity report, **WITH** the sync-parity test.
4. Final sweep — full offline suite + CLAUDE.md/AGENTS.md/project_state.

## Acceptance
`get_factors` (base-only, compute-ready, `stage=`-gated) + `get_factor_selection`/`FactorSelection` +
`sync_catalog_to_registry` added (additive; 0 of the 42 existing call sites changed); the full test set above
green (name-parity, compute-readiness, formal-stage refusal, AST-usage boundary, drift-skip-default, empty-
registry-raises, status-filter, sync parity); `get_factor_catalog` + all 42 consumers unchanged; CLAUDE.md §3
+ AGENTS.md §2a Phase-3 entry added (same pass, §11.2); full offline suite green. Then Phase 4
(`factor_lifecycle/` modules) begins.

## Post-implementation review (PR #32) — 2 fixes, then GO
GPT reviewed the implemented P3.1-P3.2 (ran the 19-test suite) and returned NO-GO with 2 small fixes, both
on the safety surface; both integrated → GO:
1. **`parity_ok` ignored `registry_only`.** `sync_catalog_to_registry`'s `parity_ok` was
   `not catalog_only and not drifted` — so an ORPHAN current registry row (a factor removed from code but
   still `is_current`) falsely reported parity. Now also requires `not registry_only`. Regression test
   `test_sync_parity_ok_false_when_registry_only_orphan_present` (fails on the pre-fix formula).
2. **AST boundary list missed `prescription_runtime`.** That module is the hypothesis_validation Gate-C
   universe-materialization step on the formal compute path (imported by `validation_steps`), so it was
   added to `FORMAL_PATHS` in the AST-usage boundary test. Suite: 21 passed.
