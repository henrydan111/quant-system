# Factor Lifecycle Formalization — Implementation Plan (v3)

**Date:** 2026-05-31. **Author:** Claude. **v3 changes:** integrates **Codex round-2** (all new
claims verified against code, §0.6) on top of v2 (Codex round-1 + long-only evidence).
**Status:** PLAN ONLY — nothing implemented; this is the design to build from after review converges.

**Repo:** https://github.com/henrydan111/quant-system. **Grounding:** `CLAUDE.md` §3/§7/§9;
`src/alpha_research/factor_registry/store.py`; `src/research_orchestrator/{resolver,validation_steps,
hypothesis,holdout_seal,steps,sealed_backtest_runner}.py`; `src/research_orchestrator/registries/strategy_registry.py`;
`src/backtest_engine/{event_driven,vectorized}/__init__.py`; `config/field_registry/` +
`src/data_infra/field_registry.py`; `src/alpha_research/{walk_forward,testing_ledger}.py`;
`src/research_orchestrator/cache_manifest.py`.

---

## 0. Why this exists
A full factor create→evaluate→select→register **workflow** was executed end-to-end with reproducible
evidence (expansion 69→50→13→sealed-OOS→6; + walk-forward re-validation of all 171 catalog factors +
a long-only metric). Rigorous as a one-off, but **not a formalized, enforced pipeline**. This plan
formalizes it. Two cross-review rounds (Codex) are integrated below.

## 0.5 Codex round-1 (verified, in v2): H1 formal-resolver status bypass → enforce in resolver;
H2 definition drift → definition-binding hard-fail; H3 mutable `design_hash` re-opens OOS → immutable
`frozen_set_hash`; H4 batch overfit → OOS unit = frozen set; H5 unlocked `testing_ledger` → file-lock;
H6 reuse machinery; taxonomy → signal-role is metadata not status; phase order → API/contract-first.

## 0.6 Codex round-2 — VERIFIED and integrated (v3)
| # | Codex round-2 point | Verified at | v3 change |
|---|---|---|---|
| **R1** | **Writer-side gate missing.** `FactorRegistryStore.set_status` only validates the enum + writes history — **no promotion gate for `approved`**. A reader gate alone is half the model (repo pattern = reader + writer, cf. `StrategyRegistryStore.set_status`). | `store.py:set_status` (enum-only); `strategy_registry.py:set_status` (gated) | **§2.3 adds the writer gate:** `set_status("approved")` must call `assert_promotion_artifact_eligible` + require `current_git_sha`, mirroring `StrategyRegistryStore`. **Phase-1 prerequisite.** |
| **R2** | **`frozen_set_hash` payload too narrow** — must also include factor identity/version/`definition_hash`, **expected_direction**, **selection-rule hash**, **eval-protocol version**, **metric/portfolio side**; else direction/selection logic can change without changing the OOS unit. | §2.8 (v2 too narrow) | **§2.8 payload broadened** accordingly. |
| **R3** | **`deprecated` vs `stale` still blurred** — provider drift must NOT auto-set lifecycle `deprecated`; use an orthogonal `approval_validity`. | §2.2/D7 | **§2.2 splits them:** lifecycle status vs orthogonal `approval_validity ∈ {valid, stale, requires_revalidation}`. |
| **R4** | **§8 said "8 questions" but had 6.** | doc | fixed (§8). |

Round-2 also **answered v2's 6 open questions** — resolutions encoded in §2.3/§2.8/§2.4/§2.6/§3 and listed in §8.

## 0.7 Codex round-3 — integrated (GO for Phase-1 spec). All API claims verified.
- **Ordering fix:** §2.3's resolver depends on `approval_validity`, but schema was Phase 2. → **Phase 1
  must add a minimal `approval_validity` column with a fail-closed default** (missing ⇒ not formally
  usable). Approved rows cannot be formal while that field is absent. (§4)
- **`frozen_set_hash` +2 fields (§2.8):** add `candidate_pool_hash` (every factor *visible to the
  selection rule*, not just the selected — 13-of-50 ≠ 13-of-500 overfit budget) and a full
  `eval_protocol_hash` (preprocessing, winsor/rank, return horizon, label def, quantile construction,
  cost/slippage, missing-data + tie-break policy, universe filter — not just a version string).
  **Provider/calendar/build IDs stay OUT of the hash** (stored beside as provenance → drift flows to
  `approval_validity=stale`, not an OOS re-open). **Strict serialization** (schema_version, sorted
  arrays, ISO dates, normalized enums, no NaN, no timestamps/paths, `sort_keys`+compact+`allow_nan=False`,
  no raw floats — use ints/enums/hashes/decimal strings).
- **Seal migration done IN `HoldoutSealStore._load()`/schema normalization** (not as a convention), old
  `design_hash` column kept for provenance (§2.8 / Phase-1 order in §8).
- **Writer-gate rollout:** **hard-block all ungated `approved` writes immediately**; the 6 expansion
  factors backfill as **`candidate`+OOS-evidence first**, promote to `approved` only via the normal
  gated path — and **only if** an independent PIT-correct reproduction existed *before unblinding*. A
  second OOS read to manufacture that evidence would violate the seal → if absent, **do not approve the
  6 retroactively** (§8).

## 0.8 PHASE 1 COMPLETE + GPT final integration review (2026-05-31, GO) — carry-forward to Phase 2+
All five Phase-1 gates are implemented, cross-reviewed, fixed, and **merged to `wave1-field-promotion`**
(PRs #29 + #30; final code `ce26e95`). Review arc: GPT rounds 2-6 → Codex rounds 1-5 → GPT post-impl
(2 P0 approval-bypasses) → GPT post-impl P1.3/P1.4/P1.5 (1 must-fix + 1 hardening) → **GPT final
integration review = GO**, no merge-blocking gap, the 5 gates compose correctly for the formal path.
Two non-blocking carry-forward items from the final review:
- **(addressed)** explicit drift-gate test for `source_layer="factor_registry_candidate"` (the code
  already covered it via `layer.startswith("factor_registry")`) — added as
  `TestPR13DefinitionBindingGate::test_factor_registry_candidate_layer_drift_is_caught` (`ce26e95`).
- **(Phase 3/5 — when `frozen_set_hash` is wired live):** derive the seal-claim key AND
  `HoldoutContext.seal_key` from ONE shared source, and add a non-`design_hash` seal test proving the
  claim and the engine backstop key on the SAME frozen hash. Until that wiring lands the seal migration
  is back-compat plumbing — immutable frozen-set OOS budgeting is not active yet. **This is the single
  most important Phase-3/5 correctness rule.**

---

## 1. Current state (UPDATED 2026-05-31 — Phase 1 done)
Phase 1 (factor-level lifecycle ENFORCEMENT) is now merged: writer+reader gates, definition-binding,
`seal_key` migration, ledger file-lock. What remains ad-hoc: the registry EVIDENCE schema (long-only
metric, signal-role, provenance — Phase 2), the `get_factors()`/`sync_catalog_to_registry()` API
(Phase 3), the ported `factor_lifecycle/` modules (Phase 4), the orchestrator profile (Phase 5), and
the 171 + 6-candidate backfill (Phase 6). Original v2 note retained below.

## 1. Current state (unchanged from v2)
Field-level governance is formalized + tested; factor-level lifecycle is ad-hoc scripts + markdown.
The real fail-closed holes are H1 (reader bypass) **and R1 (writer ungated)** — both must close together.

## 2. Target architecture (v3)

### 2.1 Registry = source of truth; catalog = seed
One master per factor: `definition_hash`, expression/components, `status`, **`approval_validity`**,
`status_history`, evidence (IS + walk-forward + sealed-OOS + long-only metric), `field_eligibility`
snapshot, `provider_build_id`, `last_revalidated_at`, signal-role metadata (§3). `catalog.py` → seed.

### 2.2 Status lifecycle + orthogonal validity (R3)
`status ∈ {draft, candidate, approved, deprecated}` = **lifecycle state**.
`approval_validity ∈ {valid, stale, requires_revalidation}` = **orthogonal currency of evidence**.
Provider/calendar/profile-provenance drift sets `approval_validity=stale` (preserves the historical
`approved` + its evidence) and **blocks current formal use** until re-validated — it does NOT demote to
`deprecated`. `deprecated` is reserved for *failed/superseded* factors.

Transition gates: → `draft` (static gates pass, non-degenerate); `draft`→`candidate` (**a-priori:**
fold IC sign-consistency + min effect/coverage + field-eligible; **generated / IS-selected:** ALSO an
**IS-only held-out / walk-forward bounded to `TimeSplit.is_end`** — never spends sealed OOS);
`candidate`→`approved` (frozen-set sealed-OOS pass **+ human gate** [mirror `hypothesis_validation` IS
gate] **+ promotion gate**, enforced on BOTH reader and writer). Effective formal usability =
`status==approved` **AND** `approval_validity==valid` **AND** current field gate passes (§2.3/D5).

### 2.3 Fail-closed on BOTH sides (H1 reader + R1 writer)
- **Reader (resolver) — "resolve-but-label" (Codex round-5; SUPERSEDES the round-2 `draft→_unresolved`
  call below).** `resolver._resolve_formal_factor` RESOLVES every current row (top-level
  `status="resolved"`) and labels `source_layer` by registry status + validity: `approved`+valid →
  `formal`; `candidate`+valid → `factor_registry_candidate`; `draft` → `factor_registry_draft`;
  `approved`+non-valid → `factor_registry_stale`; `deprecated` → `factor_registry_deprecated`. Add
  `registry_status` + `approval_validity` to the resolver output; enforce a supplied `definition_hash`
  as a real match filter (not a fallback). The formal gate lives ONLY in `validation_steps`' explicit
  allow-set (`{formal}` + `factor_registry_candidate` iff `allow_candidate_components`; reject all
  else). **Why the round-2 call was wrong:** the shared resolver feeds 3 discovery DAGs whose
  `object_resolver` step hard-raises on unresolved (`steps.py:444`); with all 171 rows `draft`,
  `draft→_unresolved` would hard-fail discovery + break a unit test. Resolving-but-labeling keeps
  research access to all factors while validation stays fail-closed. Safety: discovery publish writes
  `candidate`/`observed` (`typed_store.py:452`), never `approved`. See `factor_lifecycle_phase1_spec.md`
  §P1.2 for the full table + tests.
  - *(Superseded round-2 wording, kept for the audit trail: "stamps `source_layer=formal` ONLY for
    `status==approved`; `draft`/`deprecated` → `_unresolved` (Codex Q1)." Replaced because `_unresolved`
    breaks the discovery hard-fail path.)*
- **Writer (store):** `FactorRegistryStore.set_status("approved")` requires `promotion_evidence`
  passing `assert_promotion_artifact_eligible` + mandatory `current_git_sha`, mirroring
  `StrategyRegistryStore.set_status`. Until that gate exists, **block creation of any `approved` row.**
- `get_factors(status_in, prioritize)` is convenience for research/sandbox (status-tagged); it does
  NOT carry the formal gate — the resolver + writer do.

### 2.7 Definition binding — hard-fail-on-mismatch FIRST (Codex Q3)
Phase 1: recompute the current code hash for each factor name and **fail formal validation when it ≠
the registry `definition_hash`**. (Compute-from-registry-expression is deferred — composites /
industry-rel still resolve through code via `get_composite_defs`/`get_industry_relative_defs`, needing
graph serialization.)

### 2.8 Immutable frozen-set seal — broadened payload (Codex R2 + Q2)
A new **`FrozenSelectionSet`** object (NOT a field on `TimeSplit` — the window is only one ingredient).
`frozen_set_hash` = sha256 over: {selected factor `(id, version, definition_hash)`, **expected_direction
per factor**, **selection-rule hash**, **evaluation-protocol version**, **metric + portfolio side**,
universe, time_split window, rebalance, neutralization} — **excluding** all pass/fail wording
(`success_criteria`/`pre_registered_concerns`/`expected_effect`). `HoldoutSealStore`, `HoldoutContext`,
`ResearchAccessContext`, and the event/vectorized backstops key the sealed-OOS claim on
`seal_key=frozen_set_hash`; **old rows: `seal_key = design_hash`** (backward-compat; `design_hash()`
itself stays unchanged so existing seals/cache remain valid).

### 2.4 Codified protocol + 2.5 orchestrator profile (unchanged from v2)
Port scripts → tested `src/alpha_research/factor_lifecycle/` modules; new `factor_lifecycle`
orchestrator profile reusing `factor_screening` components + the `hypothesis_validation`
IS-gate→OOS→publish pattern + release/promotion gates.

### 2.6 OOS-budget = frozen set; extend the ledger in place (Codex Q5 / H4 / H5)
Extend `TestingLedgerStore` in place (the orchestrator already writes gate measurements through it in
`steps.py`); add **file-locking around its read-append-write**, mirroring
`CacheManifestStore.record_cache_write` / `HoldoutSealStore.claim_holdout_access`. A separate ledger
creates reconciliation risk. Record per-factor outcomes AND batch effective trials (every factor visible
to the selection rule, direction flips, clustering, post-IS ensemble/threshold). Raw counts first.

## 3. Taxonomy — statuses simple; signal-role metadata; concrete viability thresholds (Codex Q6)
Metadata columns: `expected_direction`, `signal_role ∈ {long_only_alpha, risk_sleeve, short_side,
neutralizer}`, `approved_uses`, `validation_scope`, `requires_inverse_for_long_only`, `long_only_viable`.
**`long_only_viable=True` only if** cost-adjusted long-only top-bucket Sharpe **≥ 1.0** AND excess
return positive AND fold/subperiod hit-rate **≥ 60%**. Sharpe **< 0.5** → non-viable; **0.5-1.0** →
review-only. `signal_role` is **auto-SUGGESTED** from the metric but **human-assigned final** — weak
long-only does NOT auto-imply `risk_sleeve`; "high \|IC\| + weak long-only" = "not long-only alpha,"
then a human picks `risk_sleeve` / `short_side` / `neutralizer`. Short-side portfolios extend
`PortfolioSide`, not factor status.

## 4. Phase ordering — API/contract-first (with Codex round-2 caveats)
- **Phase 1 (safety-first):** close BOTH gates — reader (resolver status-gate, Q1 source-layers) +
  **writer (`set_status` promotion gate, R1)** — + definition-binding hard-fail (Q3) + `frozen_set_hash`
  seal (R2/Q2) + file-lock the ledger (Q5). **NOT "no plumbing change"** (Codex): `frozen_set_hash`
  touches the seal-log schema + **every** design-hash seal-check site — `steps.py`,
  `sealed_backtest_runner.py`, the event-driven backstop (`event_driven/__init__.py`), the vectorized
  backstop (`vectorized/__init__.py`). Tests first.
- **Phase 2:** registry schema/evidence (long-only metric, signal-role, `approval_validity`, provenance).
- **Phase 3:** `get_factors()` + `sync_catalog_to_registry()` (staged cutover; static catalog kept for seeds/tests).
- **Phase 4:** port scripts → `factor_lifecycle/` modules (walk-forward bounded to `is_end`, Q4).
- **Phase 5:** orchestrator `factor_lifecycle` profile.
- **Phase 6:** backfill from the 171 re-validation + 6 expansion OOS verdicts + long-only metric —
  AFTER the writer gate exists (so no `approved` row is written ungated).

## 5. Invariants preserved
PIT (`Ref(...,1)`; sanctioned wrappers only); sealed-OOS one-shot per **`frozen_set_hash`**, predeclared
rule immutable, second-read = hard error; Count banned; field gate + **reader AND writer** formal gates
fail-closed; promotion gate guards `approved` on both sides; every transition writes `status_history`.

## 6. Risks
Migration regression (staged cutover + name-resolution test); `frozen_set_hash` plumbing breadth (4 seal
sites + schema — Phase-1 is more than schema-free); leakage if writer gate lags reader gate; walk-forward
over-permissiveness; OOS-budget erosion; multi-week scope.

## 7. Empirical evidence (seeds Phase 6 + validates §3)
Full **171 re-validation:** 93 candidate / 66 draft / 12 deprecated (approved=0); fundamental *level*
factors collapsed OOS (acceleration generalizes, levels don't). **Long-only metric:** only **2 of 16**
IC-candidate derived factors are long-only-viable (`comp_small_value` LO Sharpe +1.40, `comp_size_quality`
+1.22); `val_bp_industry_rel` has the highest derived OOS ICIR (+0.775) but LO Sharpe +0.49 — proof that
high cross-sectional IC ≠ long-only return, and the data that populates `signal_role`/`long_only_viable`.

## 8. Round-2 resolutions (was "open questions") + residual round-3 items
**Resolved by Codex round-2** (encoded above): Q1 source-layers (`_unresolved` for draft/deprecated;
`factor_registry_candidate` for candidate) → §2.3. Q2 `FrozenSelectionSet` object + `seal_key` →
§2.8. Q3 hard-fail-on-mismatch first → §2.7. Q4 walk-forward bounded to `is_end` (caller passes
`time_split.is_end`; test every fold/holdout ends ≤`is_end` and <`oos_start`) → §2.2/Phase 4. Q5 extend
`TestingLedgerStore` + file-lock → §2.6. Q6 thresholds + auto-suggest/human-assign → §3.

**Round-3 resolutions (Codex; design now converged):**
1. **`FrozenSelectionSet`** = §2.8 payload **+ `candidate_pool_hash` + full `eval_protocol_hash`**,
   strict serialization, provider IDs out-of-hash (stored as provenance). RESOLVED.
2. **Seal migration order** (RESOLVED): (1) add `seal_key` to the seal-store schema, lazily fill from
   `design_hash` inside `_load()`; (2) `claim_holdout_access()`/`list_events()` accept `seal_key`
   (default `design_hash`); (3) add `seal_key` to `HoldoutContext` (fallback `design_hash`); (4) update
   the 4 check sites (`steps.py`, `sealed_backtest_runner.py`, event + vectorized backstops); (5) ONLY
   then have lifecycle code pass `FrozenSelectionSet.frozen_set_hash`. Old `design_hash` column kept.
3. **Writer gate** (RESOLVED): hard-block all ungated `approved` writes now; 6 expansion factors enter
   as `candidate`; `approved` only via the gated promotion path with a pre-unblinding independent PIT
   reproduction — else not approved retroactively.

**→ Next artifact: the Phase-1 implementation spec** (`factor_lifecycle_phase1_spec.md`) — file
touch-list, test plan, the seal-migration order above, and the writer+reader gate wiring.
