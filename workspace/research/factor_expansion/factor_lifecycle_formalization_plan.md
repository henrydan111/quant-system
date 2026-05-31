# Factor Lifecycle Formalization — Implementation Plan (v2)

**Date:** 2026-05-31. **Author:** Claude. **v2 changes:** integrates the **Codex round-1
cross-review** (all claims verified against code, see §0.5) + the **catalog re-validation +
long-only-metric empirical evidence** (§7). **Status:** PLAN ONLY — nothing implemented.

**Repository:** https://github.com/henrydan111/quant-system (public).
**Grounding:** `CLAUDE.md` §3/§7/§9; `AGENTS.md` §2a; `src/alpha_research/factor_library/catalog.py`
(`get_factor_catalog`, static); `src/alpha_research/factor_registry/store.py` (`FactorRegistryStore`,
`VALID_STATUSES`); `src/research_orchestrator/` (DAG, `factor_screening` + `hypothesis_validation`
profiles, `resolver.py`, `validation_steps.py`, `hypothesis.py`, `holdout_seal.py`);
`config/field_registry/field_status.yaml` + `src/data_infra/field_registry.py`;
`src/research_orchestrator/release_gate.py`; `src/alpha_research/walk_forward.py`;
`src/alpha_research/testing_ledger.py`.

---

## 0. Why this exists
We executed a full factor create→evaluate→select→register **workflow** end-to-end with reproducible
evidence (expansion: 69→50→13 frozen→sealed-OOS→6 validated; + walk-forward re-validation of all
171 catalog factors). Rigorous as a one-off, but **not a formalized, enforced pipeline** — it ran on
ad-hoc scripts + markdown rules. This plan formalizes it. Codex round-1 reviewed v1; this v2
incorporates that review.

## 0.5 Codex round-1 review — VERIFIED and integrated
Codex's review identified four required changes + six holes. I verified each against the code (file:line)
before integrating — all confirmed:

| # | Codex finding | Verified at | Integrated change |
|---|---|---|---|
| **H1** | **Formal-resolver status bypass** — `_resolve_formal_factor` stamps every `is_current` factor `source_layer="formal"` with NO status check; `validation_steps` `formal_only` accepts it. All 171 are `draft`, so the bypass is live. | `resolver.py:_resolve_formal_factor` (source_layer="formal", no status); `validation_steps.py:~100` | **Fail-closed enforcement moves INTO the resolver** (§2.3), not a new API. The resolver must only stamp `formal` for `status==approved` (or `candidate` w/ explicit opt-in). |
| **H2** | **Definition drift** — formal validation recomputes components from `get_factor_catalog()` by NAME, not from registry definitions. | `validation_steps.py:218-227` (`get_factor_catalog`/`get_industry_relative_defs`) | **Definition binding** (§2.7): formal compute uses the registry's stored expression OR hard-fails when `definition_hash` ≠ catalog code. |
| **H3** | **OOS re-open via mutable `design_hash`** — `design_hash` includes `success_criteria`, `pre_registered_concerns`, `expected_effect`, `expected_sign`; `holdout_seal` blocks only same-`design_hash`. Editing thresholds/prose re-opens a failed OOS. | `hypothesis.py:design_hash` payload; `holdout_seal.py` | **`frozen_set_hash`** (§2.8): an immutable selection-set/sealed-window key that EXCLUDES pass/fail wording. The seal keys on it, so thresholds can't be edited to re-run OOS. |
| **H4** | **Batch-level overfit** — "13 frozen → 6 validated" must be ONE governed decision set, not 13 independent events; count every factor visible to selection + direction flips + clustering + post-IS ensemble/threshold. | design (this session counted locally only) | **OOS-budget = the frozen set** (§2.6/D6); ledger records per-factor AND batch trials. |
| **H5** | **Testing-ledger not file-locked** — `record_event`/`record_verdict` lack the `file_lock` that cache/seal stores use; concurrent runs undercount the OOS budget. | `testing_ledger.py:142,216` (no `file_lock`) | **File-lock the ledger** (§2.6) before it becomes the OOS-budget ledger, mirroring `CacheManifestStore`/`HoldoutSealStore`. |
| **H6** | Lifecycle DAG should **reuse** existing formal-gate/OOS machinery, not invent parallel governance. | — | §2.5: new `factor_lifecycle` profile **reuses** `factor_screening` components + the `hypothesis_validation` IS-gate→OOS→publish pattern. |

Codex also corrected the **taxonomy** (statuses stay simple; signal-role is metadata — §3.taxonomy)
and the **phase ordering** (API/contract-first, schema later — §4). Both adopted.

---

## 1. Current state — what is / isn't formalized
| Stage | Exists | Formalized? |
|---|---|---|
| Creation | `get_factor_catalog()` static dict | static gates (PIT/Count/field-existence) CI-enforced; generation has no lifecycle hook |
| Evaluation | `factor_eval/`, `walk_forward.py` | methods codified; this session orchestrated them via **ad-hoc direct-call scripts**, not the orchestrator |
| Selection | `oos_topset_selection_rule.md` + `apply_oos_topset_rule.py` | one-off research artifacts, not contracts |
| Registry | `FactorRegistryStore` (draft/candidate/approved/deprecated, status_history, import_screening); 5 typed registries | **field-level governance fully formalized + tested**; factor-level registration **not executed** (CSV annotation); **catalog disconnected from registry**; **formal resolver bypasses status (H1)** |

Five gaps unchanged from v1 (catalog≠registry; orchestrator bypassed; rules are artifacts; registry-write deferred; no multiple-testing/OOS-budget accounting) — **plus the four enforcement holes H1-H3,H6** Codex located, which are the real fail-closed points.

## 2. Target architecture (revised)

### 2.1 Registry = source of truth; catalog = seed
All factors (171 + 69 + future) in one master, each with `definition_hash`, `expression`/`components`,
`status`, `status_history`, evidence (IS + walk-forward + sealed-OOS + **long-only metric**),
`field_eligibility` snapshot, `provider_build_id` binding, `last_revalidated_at`, and the new
**signal-role metadata** (§3.taxonomy). `catalog.py` → seed via `sync_catalog_to_registry()` at `draft`.

### 2.2 Status lifecycle (evidence-driven; candidate-bar depends on factor origin)
```
construct → draft → candidate → [HUMAN GATE] → approved        any → deprecated
```
| Transition | Gate |
|---|---|
| → `draft` | static gates pass; computes non-degenerate |
| `draft`→`candidate` | **a-priori factor:** per-fold IC sign-consistency + min effect/coverage + field-eligible. **generated / IS-selected factor:** ALSO requires an **IS-only held-out block / walk-forward bounded to `TimeSplit.is_end`** (Codex D3) — never spends sealed OOS |
| `candidate`→`approved` | frozen-set sealed-OOS pass **+ explicit human gate** (mirrors the `hypothesis_validation` IS gate before OOS, Codex D2) **+ promotion gate** (`assert_promotion_artifact_eligible`) |
| any→`deprecated` | OOS/holdout collapse, sign-flip, supersession, or provider-drift → `stale` (D7) |

Field-eligibility is a hard cap; **effective status = `factor_status ∩ current field gate`** (D5).

### 2.3 Enforcement lives in the FORMAL RESOLVER, not a new API (Codex H1 — the key change)
The binding fail-closed gate is in `resolver._resolve_formal_factor` + `validation_steps`:
a registry factor may be stamped `source_layer="formal"` **only if `status==approved`** (or
`candidate` when `prescription.allow_candidate_components`). Draft/deprecated → not formal →
rejected at the existing `formal_only` check. A new `get_factors(status_in=…, prioritize=…)` is a
convenience for research/sandbox (returns status-tagged), but **does not** carry the formal gate —
the resolver does. Sandbox/no-context reads unchanged.

### 2.7 Definition binding (Codex H2)
Formal compute must source each factor's expression from the **registry row**, OR hard-fail when the
registry `definition_hash` ≠ the catalog-code hash for that name. No silent recompute-from-`catalog.py`.

### 2.8 Immutable frozen-set seal (Codex H3)
A `frozen_set_hash` = sha256 over {sorted factor `definition_hash`es, universe, time_split window,
rebalance, neutralization} — **excluding** `success_criteria`/`pre_registered_concerns`/
`expected_effect`/pass-fail wording. `holdout_seal` keys the sealed-OOS claim on `frozen_set_hash`
(not `design_hash`), so editing thresholds/prose can't re-open a consumed OOS. The predeclared
selection rule + frozen-set JSON we already produce becomes the input to this hash.

### 2.4 Codified evaluation protocol
Port the ad-hoc scripts → tested `src/alpha_research/factor_lifecycle/` modules: `static_gates`,
`is_screen`, `walk_forward_eval` (bounded to `TimeSplit.is_end`), `sealed_oos` (one-shot guard),
`selection_rule` (predeclared-as-code), `long_only_metric`, `status_assign`.

### 2.5 Orchestrator `factor_lifecycle` profile (reuses machinery — Codex H6/D4)
New profile (do NOT overload `factor_screening`, which is a quick-kill discovery profile). DAG:
`sync_catalog → static_gate → is_screen → walk_forward → status_assign(candidate) → human_gate →
frozen_set_seal → sealed_oos → promotion_gate → registry_publish`. Reuses `factor_screening`
components + copies the `hypothesis_validation` IS-gate→OOS→publish pattern + the existing
release/promotion gates.

### 2.6 OOS-budget accounting (Codex H4/H5/D6)
The **frozen decision set is the OOS unit**, not the factor. The (file-locked) `testing_ledger`
records per-factor outcomes AND batch-level effective trials: every factor visible to the selection
rule, every direction flip, family-clustering choice, and any post-IS ensemble/threshold. Raw counts
first; correlation-adjusted family counts later. Promotion bar escalates with the count.

## 3. Status taxonomy — statuses stay simple; signal-role is METADATA (Codex Q7)
Keep `draft / candidate / approved / deprecated` as **lifecycle state only**. Do NOT add
`risk_sleeve`/`short_side` statuses. Add **orthogonal metadata columns**:
`expected_direction`, `signal_role` ∈ {`long_only_alpha`, `risk_sleeve`, `short_side`, `neutralizer`},
`approved_uses`, `validation_scope`, `requires_inverse_for_long_only`, `long_only_viable` (+ the
long-only metric value). True short-side portfolios extend `PortfolioSide` (the repo already models
component `direction` in `hypothesis.py`/`prescription_runtime.py`), **not** factor status. **§7's
long-only evidence is exactly what populates these fields.**

## 4. Phase ordering — API/CONTRACT-FIRST, then schema (Codex)
- **Phase 1 (safety-first, today's schema):** close the formal-resolver bypass — status-gate
  `_resolve_formal_factor` (H1) + definition-binding hard-fail (H2) + `frozen_set_hash` seal (H3) +
  file-lock the ledger (H5). This is the biggest safety win and needs no schema change. Tests first.
- **Phase 2:** extend registry schema/evidence (long-only metric, signal-role metadata, provenance binding).
- **Phase 3:** `get_factors()` status-aware API + `sync_catalog_to_registry()` (staged cutover, D1:
  static catalog kept for seeds/tests, formal path reads registry + fail-closed).
- **Phase 4:** port scripts → `factor_lifecycle/` modules.
- **Phase 5:** orchestrator `factor_lifecycle` profile.
- **Phase 6:** backfill — seed from the 171 re-validation + the 6 expansion OOS verdicts + long-only metric.

## 5. Invariants preserved (non-negotiable)
PIT (`Ref(...,1)` / `qlib_windowed_features` / `pit_research_loader` only); sealed-OOS one-shot per
**frozen_set_hash**, predeclared rule immutable, no post-OOS tuning, second-read = hard error; Count
banned; field gate + formal-resolver gate fail-closed; promotion gate guards `approved`; every status
transition writes `status_history` with evidence + commit.

## 6. Risks
Migration regression (D1 — staged cutover + name-resolution test); "access to all" leakage (enforced at
resolver, not advisory); walk-forward over-permissiveness (effect-size + multiple-testing bar);
OOS-budget erosion (ledger must escalate the bar); multi-week scope across `src/`/orchestrator/governance.

## 7. Empirical evidence now in hand (seeds Phase 6 + validates the taxonomy)
The full **171 catalog re-validation** (walk-forward IS/OOS, this session):
**93 candidate / 66 draft / 12 deprecated** (approved=0). 12 deprecated were strong-IS fundamental
*level* factors that collapsed OOS (corroborates the expansion finding: acceleration generalizes,
levels don't).

The **long-only top-bucket metric** (sign-aligned top-decile-minus-universe) directly demonstrates why
**`signal_role` must be metadata, not inferred from IC**:
- Of 16 IC-`candidate` derived factors, **only 2 have long-only Sharpe ≥ 1.0** (`comp_small_value`
  +1.40, `comp_size_quality` +1.22 — small-cap tilts); 12 of 16 < 0.5, several negative.
- `val_bp_industry_rel`: highest derived OOS ICIR (+0.775) but **long-only Sharpe +0.49** — strong
  cross-sectional IC, weak long-only (the alpha is in the spread / short leg a no-shorting book can't hold).

So the registry needs `long_only_viable` + `signal_role` populated from THIS metric: the ~55 negative-IC
base + ~12 weak-long-only derived → `risk_sleeve`/`requires_inverse_for_long_only`; the small-cap
composites → `long_only_alpha`. This is concrete data, not speculation, behind §3.

## 8. Open questions for Codex round-2
1. **Phase-1 fix shape (H1):** should `_resolve_formal_factor` return a non-formal `source_layer` for
   `draft`/`candidate`, or `_unresolved`? Which integrates cleanest with `validation_steps` `formal_only`?
2. **frozen_set_hash (H3):** put it on `Hypothesis`/`TimeSplit`, or a new `FrozenSelectionSet` object the
   seal store consumes? Backward-compat with existing `design_hash`-keyed seals?
3. **Definition binding (H2):** compute-from-registry-expression vs hard-fail-on-mismatch — which first,
   given composites/industry-rel resolve through code (`get_composite_defs`/`get_industry_relative_defs`)?
4. **Candidate bar (D3):** for the expansion factors (partly IS-selected), is walk-forward-to-`is_end`
   the right pre-candidate gate, and does `walk_forward.build_walk_forward_folds` already bound correctly?
5. **Ledger as OOS budget (H4/H5):** extend `testing_ledger` in place (add file_lock) or a new
   `oos_budget_ledger` mirroring `CacheManifestStore`?
6. **signal_role:** auto-derive from the long-only metric (LO Sharpe<threshold ⇒ risk_sleeve) or
   require human assignment? What LO-Sharpe / hit-rate threshold defines `long_only_viable`?
