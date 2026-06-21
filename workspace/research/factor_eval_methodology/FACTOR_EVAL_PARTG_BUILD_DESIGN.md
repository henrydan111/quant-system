# Factor-Eval Part-G build design **v2** — GPT design-review R1 folded — CODING-READY

> **GPT 5.5 Pro design-review verdict (R1): "revised design before coding."** Architecture confirmed sound
> — build a thin orchestration/contracts layer in `src/alpha_research/factor_eval_skill/` + 2 CLIs; reuse
> catalog / PIT linters / `FieldStatusRegistry` / unified-eval matrix / lifecycle IS gate /
> `FrozenSelectionSet` / `HoldoutSealStore` / `reproduce_sealed_oos` / event-driven backtester **verbatim**.
> Three real seam risks required amendment before coding: **(1)** D1 over-packed per-factor provenance with
> per-factor×target×methodology records; **(2)** D2 back-compat needs an *immutable envelope*, not an
> *optional* checker; **(3)** D6 disclosure-only is too weak as a standing OOS-multiplicity policy. All 8
> amendments + the over-engineering compromise + 5 seam traps are folded below. **This v2 is the coding
> spec.** v1 (pre-review) is preserved in git history.

## What changed from v1 (the 8 amendments)

| # | Area | v1 | v2 (folded) |
|---|---|---|---|
| 1 | **D1** storage | one `factor_provenance.parquet` | **three scope-split stores** (per-factor / per-role-context / per-factor×target×methodology) |
| 2 | **D2** identity | non-payload `tud_hash` + *optional* checker | **immutable `FrozenSelectionEnvelope`** + **mandatory** `assert_identity_chain` in select/seal/deploy |
| 3 | **D3** extraction | "becomes thin callers" | + **E-wave bitwise/tolerance regression bar** (selected set + frozen_set_hash + OOS/deploy metrics) |
| 4 | **D4** CLIs | own mode/equality/tier | + **forbidden-verb invariants** (`factor-eval` can't `deploy`; `strategy-build` can't `seal`); deploy requires the 3 hashes |
| 5 | **D5** Stage-3 reader | `stage3_caps(factor_id)` | `stage3_caps(factor_id, definition_hash, layer1_methodology_hash, tud_hash, role)` + **role-split outputs** |
| 6 | **D6** OOS-FDR | disclosure-only | **seal-layer counts + report/approval-layer guard** (disclose → acknowledge → adjusted-context/override by threshold) |
| 7 | **D7** acceptance | "an OSAP/arXiv draft" | **`mom_overnight_20d`** + strengthened criterion (identity-chain dry-run, temp registry, **no live OOS spend**) |
| — | **Sequencing** | D1→D5 late | **Stage0/Stage3 contracts move before CLI wiring** |
| — | **Over-eng.** | 8 contract objects | **4 identity-critical = typed-hash dataclasses**; 6 others = validated YAML → normalized-payload records |

## Scope: build vs reuse-untouched (confirmed)

**Reuse verbatim (do NOT modify):** catalog/`sync_catalog_to_registry`, PIT linters, `FieldStatusRegistry`,
`unified_eval_universe_matrix`, `replication_governance.resolve_replication_ceiling`,
`assign_candidate_status`/`run_is_walk_forward`, `FrozenSelectionSet`/`HoldoutSealStore`,
`reproduce_sealed_oos`/`produce_promotion_evidence`/`set_status`, `EventDrivenBacktester`,
`compute_factors`→`qlib_windowed_features`, `provider_manifest`.

**Build (this design):** new package `src/alpha_research/factor_eval_skill/` + 2 CLIs. New stores are
**sidecars** (append-only parquet/JSONL, file-locked) — never new `factor_master` columns.

---

## D1 — Storage model: **three** scope-split sidecar stores (was one)

> GPT: "`quality_flags`, `universe_profile`, and `target_universe_declaration_hash` are not stable per-factor
> attributes; they are per factor × target-universe × matrix-methodology records. A factor can be
> research-valid on `univ_all`, target-eligible on microcap, and target-failing on `liquid_top300`. One
> `factor_id`+version row cannot represent that without overwriting scope."

Split the single sidecar by **lifetime/scope** into three append-only stores:

```
FactorProvenanceStore            # lifetime: per factor identity (stable)
  key:   factor_id + definition_hash            (definition_hash = the catalog hash, §3.5)
  fields:
    evidence_tier                ∈ {theory_a_priori, a_priori_is_informed, oos_informed}
    direction_source             # where expected_direction came from (theory | is_observed | literature)
    may_cite_is_as_confirmation  # FALSE for a_priori_is_informed (IS-spent rule)
    fresh_oos_eligible
    multiplicity_scope_id
    prior_contradicted_by_is     # IS flipped the a-priori sign → flag, do not silently overwrite
    rationale
    committed_at, committed_by

RoleDeclarationStore             # lifetime: per (factor, role-context) declaration
  key:   factor_id + definition_hash + role_context_hash
  fields:
    role                         ∈ {ranking, filter, both}
    filter_role_subtype          # risk_exclusion | quality_floor | liquidity_floor | ...
    threshold, direction         # references expected_direction — NOT a new direction field (seam #2)
    declared_before_stage        # pre-registration order proof (no post-OOS role selection)

Stage3QualityRecordStore         # lifetime: per (factor × target-universe × Layer-1 methodology)
  key:   factor_id + definition_hash + layer1_methodology_hash + target_universe_declaration_hash
  fields:
    quality_flags                # sign_flip_across_core_universes, liquid_fail, illiquidity_bound, coverage_sub
    universe_profile             # per-universe IC/ICIR/coverage snapshot (json)
    target_universe_pass
    cross_universe_sign_divergence
    status_effect                # mapped onto existing STATUS_CEILINGS — NO parallel status universe
```

**Why three, not one:** `quality_flags`/`target_universe_declaration_hash`/`universe_profile` are
scope-bound — they vary by the *declared target* and the *Layer-1 methodology hash*. Forcing them onto a
per-`factor_id` row would overwrite the (research-valid on `univ_all`, target-failing on `liquid_top300`)
distinction the whole dual-scope regime exists to preserve. `Stage0EvidenceProvenance` lives in
`FactorProvenanceStore` (folded forward from v1's late-D5 placement — `factor-eval register` cannot be
correct without `evidence_tier` + role on day one).

**Filter stores (seam trap #4 — were missing):**

```
FilterCharacterizationStore      # factor-eval output (Stage 2-5); a filter is CHARACTERIZED, not "passed"
  key:   factor_id + definition_hash + role + target_universe_declaration_hash + threshold
  fields: excluded_tail_return, threshold_stability, breadth, FilterCharacterization_v1 verdict (NO IC pass/fail)
FilterDeploymentGateStore        # strategy-build output (Stage 8); the A/B pass/fail in a StrategyContext
  key:   plan_hash + filter_id + threshold
  fields: marginal_sharpe_delta, marginal_mdd_delta, FilterDeploymentGate_v1 verdict
```

---

## D2 — Identity spine: **immutable `FrozenSelectionEnvelope`** + **mandatory** chain (was optional checker)

> GPT: "If `tud_hash` is just a non-payload field and `assert_identity_chain()` is something callers
> remember to run, the guarantee is procedural, not structural. Use an explicit immutable envelope."

`TargetUniverseDeclaration` (TUD), `SelectedSet`, `FrozenSelectionEnvelope`, `DeploymentFrozenPlan` are the
**4 identity-critical typed-hash dataclasses** (frozen, sha256 over normalized JSON payload, sorted keys,
schema version — never raw text). The back-compat wrinkle (adding `tud_hash` to `FrozenSelectionSet`'s
payload would change `frozen_set_hash` and orphan the **already-spent E-wave seal** `316b17bc…9672f2`) is
solved by an **envelope that wraps the existing hash, never re-hashes the payload**:

```
FrozenSelectionEnvelope:                 # NEW, immutable, append-only — NOT a mutable object property
  frozen_set_hash:                       # existing HoldoutSealStore seal key — UNCHANGED
  target_universe_declaration_hash:
  selected_set_hash:
  frozen_selection_set_schema_version:
  created_at, created_by:
  legacy_mode: false
  envelope_hash:                         # hash OVER the envelope — NOT used as the seal key
```

- `HoldoutSealStore` still keys by `frozen_set_hash` (E-wave seal stays valid; no payload bump — a payload
  bump would create *two seal identities for the same economic run*, explicitly rejected).
- Stage-7 OOS reports MUST store `frozen_set_hash` + `envelope_hash` + `tud_hash`.
- `DeploymentFrozenPlan` MUST reference `frozen_set_hash` + `envelope_hash` + `tud_hash`.
- `assert_identity_chain(tud, selected_set, envelope, plan)` is **mandatory** (called by the select/seal/
  deploy code paths, fail-closed) — **not** an optional checker callers may forget.
- **Legacy E-wave seals:** `legacy_mode: true`, `target_universe_declaration_hash: null`,
  `legacy_reason: "pre-v1.3 seal"` — remain auditable, but **cannot claim a "v1.3 clean identity chain"**.
- **Immutability (seam trap #5):** `tud_hash` lives in the append-only envelope, **never** as a loose
  editable field on a `FrozenSelectionSet` object (else a later script could mutate it to make an old seal
  look compatible with a new TUD).

---

## D3 — Parameterize the E-wave scripts + **bitwise/tolerance regression bar** (new acceptance)

Extract (do NOT re-author) into `factor_eval_skill/`:
- `marginal.py`: `select_marginal(pool, matrix, caps, references, floor, universe) → SelectedSet`
  (greedy from `select_e_wave_marginal.py`; all E-wave constants → parameters).
- `sealed_oos.py`: `run_sealed_oos(frozen_set, n_quantiles=10, bar=BAR) → verdict`
  (from `select_e_wave_sealed_oos.py`; bar = one module constant; `n_quantiles=10` pinned).
- `deployment.py`: `run_deployment(plan: DeploymentFrozenPlan) → metrics`
  (from `eval_e_wave_v2_deployment.py`; liquid-universe + composite construction become plan parameters).

The 3 E-wave scripts become ~10-line callers. **Acceptance bar (folded):** for the E-wave historical case,
old-script output == new-library output:
- `selected_set` factors identical,
- `frozen_set_hash` identical where payload unchanged,
- OOS metrics equal within tolerance,
- deployment metrics equal within tolerance.

Without this, "parameterized" could silently change the one case that motivated the design.

---

## D4 — The two CLIs: thin fail-closed coordinators + **forbidden-verb invariants** (new)

```
factor-eval     register | declare_target | characterize | gate | select | seal
strategy-build  deploy
```

Own *mode* (deployment_bound vs exploratory_research), the *equality chain* (D2), *evidence_tier* reads,
and *sequencing*; delegate all computation to the reused engine + D3 library functions. **Hard
invariants (folded):**
- `factor-eval deploy` is **forbidden**.
- `strategy-build seal` is **forbidden**.
- `strategy-build deploy` **requires** `frozen_set_hash` + `envelope_hash` + `target_universe_declaration_hash`.

CLIs are fail-closed coordinators, never computation engines.

---

## D5 — Stage-3 reader: **target+role-aware signature** (was `factor_id`-only)

> GPT: "v1.3 caps are target-universe and role-aware; they cannot be a function of `factor_id` alone."

```
stage3_caps(
    factor_id,
    definition_hash,
    layer1_methodology_hash,
    target_universe_declaration_hash,
    role,
) -> Stage3QualityRecord
```

Reads the 7 `results.jsonl` rows → emits role-split outputs:
```
ranking:  target_universe_pass, cross_universe_sign_divergence, status_effect
filter:   FilterCharacterization_v1   (NO IC-based pass/fail)
both:     separate ranking_component + filter_component
```
`status_effect` maps onto the existing `STATUS_CEILINGS` (`coverage_tier=='sub'` → `availability_floor_fail`
is a `call`, not a re-impl) — **no parallel status universe**. `sign_flip_across_core_universes`,
`liquid_fail`, `illiquidity_bound` are NEW cross-universe logic; `coverage_sub` reuses the existing tier.
Gate/select MUST read this. The cross-universe divergence is **diagnostic** unless the TUD *requires* that
universe (the v1.3 §5 role-aware cap fix — do not re-block a small-cap-target factor merely for flipping in
CSI300).

---

## D6 — System-level OOS-window multiplicity: **count in seal layer, guard in approval layer** (was disclosure-only)

> GPT: "The 2021–2026 OOS window is shared and bounded; every distinct frozen set spending it raises
> system-level false-discovery risk, and the per-set seal does not adjust for that. Disclosure-only is too
> weak as a standing policy."

```
OOSWindowMultiplicityPolicy:
  oos_window_id:                 # e.g. "2021-01-01..2026-02-27"
  n_spent:                       # distinct frozen_set_hashes that spent this window
  n_theory_a_priori, n_a_priori_is_informed, n_oos_informed:   # by evidence_tier
  family_denominators:
  action:
    n < warn_threshold:                       disclose
    warn_threshold <= n < hard_threshold:     disclose + require reviewer acknowledgement
    n >= hard_threshold:                      require ONE of:
                                                - BH/FDR q-value report (if p-values available), OR
                                                - max-stat / family-level denominator report, OR
                                                - explicit SystemOOSMultiplicityOverride
```

**Layer split:**
- **Seal layer** (`HoldoutSealStore` append-only event log): COUNTS and records the spend. **Never changes
  the OOS metric** and **never adjusts the per-set bar** (the per-set bar stays fixed).
- **Report/approval layer**: decides whether a result may be rendered `approved_signal` without override or
  adjusted evidence. `oos_window_multiplicity(oos_window) → {n_spent, by_tier, action}` is read by the
  approval path and stamped on every new sealed-OOS report.

So: not seal-layer bar adjustment, not prose-only — a report/approval-layer **guard** keyed off the
seal-layer count.

---

## D7 — Non-E-wave acceptance test: **`mom_overnight_20d`** + strengthened criterion

> GPT recommends `mom_overnight_20d` — a base catalog momentum factor (price-only, PIT-simple, non-CICC, no
> new data, no special-handbook cohort). It is in the base catalog, **not** an E-wave factor.

```
NonEWaveAcceptanceTest:
  factor: mom_overnight_20d
  registry: TEMP (no mutation of the live registry)
  oos: DRY-RUN ONLY (no live HoldoutSeal spend)
  requirements:
    - no cicc_ / E-wave constants imported anywhere on the path
    - no replication manifest required
    - Stage0EvidenceProvenance written (FactorProvenanceStore)
    - TargetUniverseDeclaration written
    - 7-universe matrix read or generated
    - Stage3QualityRecord written (target+role-aware key)
    - candidate gate dry-run (or live-on-temp registry)
    - SelectedSet built for a one-factor pool
    - FrozenSelectionEnvelope created
    - seal DRY-RUN only — no live OOS spend
    - DeploymentFrozenPlan dry-run created
    - assert_identity_chain passes
    - hand-run metrics reproduced within tolerance
```

Pass = the generic path runs end-to-end on a non-E-wave factor, touching **zero** cohort constants, with a
verified identity chain and reproduced hand-run metrics. This test gates merge (the build's definition of
done / future-applicability proof, §11.1).

---

## Over-engineering compromise (folded)

**Identity-critical → typed canonical-hash dataclasses** (day one): `TargetUniverseDeclaration`,
`SelectedSet`, `FrozenSelectionEnvelope`, `DeploymentFrozenPlan`.

**The other 6 → validated records** (YAML authoring allowed initially): `Stage0EvidenceProvenance`,
`RoleDeclaration`, `Stage3QualityRecord`, `FilterCharacterization`, `FilterDeploymentGate`,
`RevalidationEvent`. **But** even YAML must be parsed into a canonical typed payload before hashing — hash
**normalized JSON with sorted keys + schema_version**, never raw YAML text. Pattern:
`authoring=YAML → runtime=typed validated object → hash=canonical normalized payload → store=append-only
parquet/JSONL with file_lock`.

---

## Missed seams / collision traps (folded — explicit non-mappings)

1. **`evidence_tier` ≠ replication-governance fields.** Do NOT map `replication_tier_planned` →
   `evidence_tier`, nor conflate with `evidence_class` / `formal_evidence_eligible` / cohort
   `oos_eligibility`. They answer different questions; keep them distinct columns.
2. **Direction is already fragmented** (`Hypothesis.expected_sign`, `factor_master.expected_direction`,
   `ComponentDirection`). `RoleDeclaration` **references/normalizes to `expected_direction`** — it does NOT
   add a 4th direction field.
3. **Stage-0 ≠ `Hypothesis`.** `Hypothesis`/`hypothesis_cli` is strategy+OOS-bound; do not overload it for
   factor-level provenance. Build `FactorProvenanceStore`, not a fake `Hypothesis`.
4. **Filter contracts** (`FilterCharacterizationStore` factor-eval output / `FilterDeploymentGateStore`
   strategy-build output) are first-class — v1.3 makes the ranking/filter split load-bearing.
5. **Envelope immutability** — `tud_hash` is append-only envelope state, never a mutable object property.

---

## Sequencing (reordered — Stage0/Stage3 before CLI wiring)

1. **D1 three-store split + Stage0 provenance/role stores + D2 identity spine** (TUD/SelectedSet/Envelope/
   Plan dataclasses + `assert_identity_chain`). Everything hangs off identity + provenance.
2. **D5 Stage-3 reader skeleton** (target+role-aware signature) — the CLI `gate`/`select` depend on its
   outputs; building CLI wiring first would bake wrong assumptions or stubs.
3. **D3 library extraction** with the E-wave bitwise/tolerance regression as the immediate check.
4. **D4 CLIs** wiring 1–3 + the reused engine (forbidden-verb invariants enforced in code).
5. **D6 OOS-window multiplicity** (seal-layer count + approval-layer guard).
6. **D7 non-E-wave acceptance test** (`mom_overnight_20d`) — gates the whole layer as future-applicable.

---

## Decision

GPT verdict: **"build plan sound in architecture, but revise D1/D2/D5/D6/D7 before coding"** → all
amendments folded into this v2. **Ready to start coding at step 1 (D1 three-store split + D2 identity
spine + `assert_identity_chain`)** on user green-light. The 4 identity-critical dataclasses + the envelope
are the foundation; the non-E-wave acceptance test (D7) is the merge gate.
