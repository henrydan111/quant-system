# Part-G implementation — self-review + GPT cross-review packet (after steps D1/D2/D5/D3, before D4 CLIs)

> **Purpose.** The Part-G build design (v2) was GPT-reviewed BEFORE coding. This packet asks for a
> cross-review of the CODE for the first three steps, BEFORE the D4 CLI integration layer is built on top
> (the CLI's `gate`/`characterize` wiring depends on resolving the open question #3 below). Repo is PUBLIC:
> `github.com/henrydan111/quant-system`, branch `report-rc-registration`. Commit-pinned raw permalinks let a
> web GPT read the files. Relevant commits: `1a5c4c5` (D1+D2), `c791d02` (D5), `a65a961` (D3), `4ddeb30`
> (self-review fixes). Design: `FACTOR_EVAL_PARTG_BUILD_DESIGN.md` (v2) + `FACTOR_EVAL_METHODOLOGY_v1.3.md`.

## 1. What was built (new package `src/alpha_research/factor_eval_skill/`, 50 tests green)

Thin contracts/orchestration layer; reuses the engines verbatim (catalog / PIT linters / unified-eval
matrix / lifecycle IS gate / `resolve_replication_ceiling` / `FrozenSelectionSet` / `HoldoutSealStore` /
`reproduce_sealed_oos` / `EventDrivenBacktester`).

| Module | Step | Contents |
|---|---|---|
| `_hashing.py` | D2 | `canonical_json` / `payload_hash` / `normalize_enum` / `normalize_mapping` — mirrors `FrozenSelectionSet`'s serialization byte-for-byte |
| `identity.py` | D2 | `TargetUniverseDeclaration`/`SelectedSet`/`FrozenSelectionEnvelope`/`DeploymentFrozenPlan` (frozen, typed-hash) + mandatory `assert_identity_chain` |
| `_store.py` | D1 | `AppendOnlyStore` base (string schema, file-locked atomic write — mirrors `HoldoutSealStore`) |
| `stores.py` | D1 | `FactorProvenanceStore` / `RoleDeclarationStore` / `Stage3QualityRecordStore` (3 scope-split) + `FilterCharacterizationStore` / `FilterDeploymentGateStore` + `FrozenSelectionEnvelopeStore` |
| `stage3_reader.py` | D5 | `stage3_caps(...)` → `Stage3QualityRecord`; `MatrixResults` loader |
| `marginal.py` | D3 | `select_marginal(...)` → `MarginalSelection` (greedy, extracted) |
| `sealed_oos.py` | D3 | `direction_aligned_pass` / `evaluate_sealed_oos_bar` (pure bar) + `run_sealed_oos` (wrapper) |
| `deployment.py` | D3 | `direction_aligned_composite` / `build_ranked_schedule` (pure) + `run_deployment` (wrapper) |

**Key behaviours demonstrated by tests:**
- Back-compat: an existing `FrozenSelectionSet`'s `frozen_set_hash` is unchanged; the envelope WRAPS it;
  `HoldoutSealStore` still seals on it (the spent E-wave seal stays valid). Legacy envelopes are auditable
  but refused a clean chain.
- D5 reused engines: `status_effect` = `resolve_replication_ceiling`; `target_universe_pass` =
  `assign_candidate_status`. The NEW cross-universe flags (`sign_flip_across_core_universes` / `liquid_fail`
  / `illiquidity_bound`) are diagnostic, not caps (v1.3 §5). **Real-data smoke**: `liq_vstd_20d` flips sign
  on `univ_liquid_top300` (−0.56 on univ_all → +0.18 on liquid); `liquid_fail` fires — the exact Stage-3
  catch that would have flagged the E-wave liquid weakness pre-OOS.
- D3 acceptance bar (GPT amendment): the E-wave case reproduces bit-for-bit — the library greedy on the
  cached corr + matrix reproduces the recorded `EWaveSelectedSet_v2` ordered selection; the bar replays the
  recorded OOS to 6/6. The three E-wave scripts now delegate their core to the library (thin callers).

## 2. Fidelity to the v2 design — deviations (all deliberate, flagged for review)

1. **D5 signature**: design wrote `stage3_caps(factor_id, definition_hash, layer1_methodology_hash, tud_hash, role)`.
   Implemented as `stage3_caps(matrix, *, factor_id, definition_hash, tud, role, replication_tier=…, claim_class=…, oos_eligibility=…, require_claim=False, ceiling_overrides=None)`. Two changes: (a) pass the
   `TargetUniverseDeclaration` object `tud` (carries both `target_universe_id` to pick the row AND `tud_hash`)
   rather than a bare `tud_hash`; (b) `layer1_methodology_hash` is DERIVED from the matrix row (authoritative,
   reference-invariant) instead of passed in. *Both seem strictly better — confirm.*
2. **`envelope_hash` determinism** (self-review fix, see §3.1): the design listed `created_at`/`created_by`
   as envelope fields; I EXCLUDED them from the hashed payload so `envelope_hash` is a deterministic function
   of the identity binding (survives re-creation). *Confirm this is the right call.*
3. **`run_sealed_oos` sides** (self-review fix, §3.2): derive held sides from the frozen set rather than a
   separate arg.
4. **Slow wrappers untested**: `run_sealed_oos` / `run_deployment` (which call `reproduce_sealed_oos` /
   `EventDrivenBacktester`) are NOT in the pytest suite — only their PURE inner logic (bar, composite,
   schedule, sides-derivation) is unit-tested, plus the E-wave bitwise regression on the deterministic core.
   Full backtest reproduction is a manual/one-time check. *Acceptable, or add a `@pytest.mark.slow` integration test?*

## 3. Self-review findings

### Fixed (committed `4ddeb30`)
- **3.1 `envelope_hash` was timestamp-dependent** → a `DeploymentFrozenPlan`'s `envelope_hash` reference
  would break whenever the envelope was rebuilt rather than reloaded. Now deterministic over the binding.
- **3.2 `run_sealed_oos` `sides`** could disagree with the sealed set → now derived from
  `FrozenSelectionSet.SelectedFactor.expected_direction` (an optional override remains).

### Open — judgment calls for GPT (NOT yet changed)
- **3.3 (PRIMARY) Stage-3 reader governance defaults are fail-OPEN.** `stage3_caps` defaults
  `replication_tier="exact_certified"`, `claim_class="clean_singleton_primary"`, `oos_eligibility="pending"`,
  `require_claim=False`. For a NATIVE catalog factor (e.g. D7's `mom_overnight_20d`) these are correct (no
  replication concern). For a CICC-COHORT factor they are the MOST PERMISSIVE inputs — if the caller forgets
  to resolve the real values from the cohort manifest + `FactorDomainClaim`, the reader silently UNDER-caps
  (e.g. misses a `proxy_approx` tier cap or a `missing_domain_claim`). The reused `resolve_replication_ceiling`
  is itself fail-closed; the risk is purely in the reader's permissive DEFAULTS. **Question: is "the D4 CLI
  MUST resolve governance inputs from the manifest for cohort factors" an acceptable contract, or should the
  reader be fail-closed — e.g. require an explicit `factor_class ∈ {native, cohort}` that flips the defaults
  (cohort ⇒ `require_claim=True` + no permissive tier default), or make the three governance inputs REQUIRED?**
- **3.4 Frozen dataclasses with `Mapping` fields are not Python-hashable.** `TargetUniverseDeclaration` /
  `DeploymentFrozenPlan` carry dict fields (`universe_definition_filters`, `construction`, `pre_declared_bar`),
  so `hash(instance)` raises (unlike `FrozenSelectionSet`, whose fields are tuples). Identity is taken via the
  `*_hash` property, never `hash()`, so it works — but it is a sharp edge. **Normalize dicts to an immutable
  form at construction (so instances are hashable), or leave as-is with a documented "use `.tud_hash`, not
  `hash()`" contract?**
- **3.5 `§0` Canonical Function Map does not yet list `factor_eval_skill`.** The package is now substantial
  and canonical-worthy, but §0 has no row for it (the exact drift the freshness-mechanism to-do targets). **Add
  the §0 rows now, or at D4 when the user-facing CLIs land (the most canonical-worthy entry points)?**
- **3.6 All-string store schema.** Like `HoldoutSealStore`, every sidecar column is `"string"` — numeric
  fields (`marginal_sharpe_delta`, deltas) are stored as their string form; structured fields as canonical
  JSON. **Acceptable per precedent, or type the numeric columns now (queryability vs dtype-stability)?**

## 4. Questions for the cross-review

1. **#3.3 is the load-bearing one** — fail-open Stage-3 defaults: acceptable CLI contract, or make the reader
   fail-closed (and how — `factor_class` discriminator vs required governance inputs)?
2. Deviations in §2 (D5 signature; deterministic `envelope_hash`; derive sides) — all endorsed?
3. The pure-logic-tested / slow-wrapper-untested split (§2.4) — sufficient, or add a marked slow integration test?
4. §3.4 hashability sharp edge — normalize-to-immutable, or documented contract?
5. §3.5 — §0 map drift: update now or at D4?
6. Any seam/correctness issue NOT caught here, especially in `assert_identity_chain`, the back-compat
   envelope wrapping, or the cross-universe flag definitions (`liquid_fail` = weak OR sign-flip vs primary;
   `illiquidity_bound` = strong-microcap AND weak-liquid)?
7. Green light to build D4 (the two CLIs) on this foundation, or fix #3.3 first?

## 5. Decision requested
"Foundation sound — proceed to D4" (optionally after fixing #3.3), or specific changes before the CLI layer.
