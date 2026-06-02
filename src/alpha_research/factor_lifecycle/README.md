# Factor Lifecycle — how a factor goes from `draft` to `candidate` (and toward `approved`)

**Read this first** if you are touching factor promotion, the `factor_lifecycle` orchestrator
profile, the factor registry, or anything that decides "is this factor good enough to use?"

This is the **followable, start-to-finish guide**. For *what changed when*, read the dated
update notes in [project_state.md](../../../project_state.md) (Phases 1–7, 2026-05/06). For the
*enforced invariants* (the load-bearing rules), read [CLAUDE.md](../../../CLAUDE.md) §3. This
doc explains *how the whole thing works and why it is safe*.

---

## 1. The problem this solves

The system has a library of **171 factors** ([catalog.py](../factor_library/catalog.py) — 147
base + 20 composite + 4 industry-relative). They all started at status **`draft`**: defined in
code, with no proof they work. A past lookahead-leakage bug had once let factors "peek at the
future" and produced fake winners that nearly got deployed. So this arc built a **governed,
leak-proof, auditable pipeline** to move a factor from "just code" to "validated enough to
consider" — without ever cheating on the future, and without anyone being able to quietly fake
a promotion.

## 2. The status ladder

Every factor row in the registry ([data/factor_registry/](../../../data/factor_registry/)) has a
**status**:

| Status | Plain meaning | Who can use it |
|---|---|---|
| **draft** | Defined in code; no formal proof. | All discovery/sandbox research (status is ignored there — see §4). |
| **candidate** | Passed the **in-sample-only** walk-forward audition. "Worth taking seriously / worth spending OOS budget on." | Formal validation, only if the run opts in (`allow_candidate_components`). |
| **approved** | Passed the **full promotion gate**: independent, sealed out-of-sample proof + a committed git SHA. Deployable-grade. | Formal validation, always. |
| **deprecated** | Retired / failed. | — |

**Key rule:** `candidate` is an *additive* tier. It does **not** restrict research, and it can
**never auto-promote** to `approved`. As of 2026-06-02 the live registry is **87 `candidate` +
84 `draft` + 0 `approved`** (72 base from Phase 6 + 15 Layer-2 from Phase 7).

## 3. The two safety guarantees behind everything

1. **Never peek at the future (the label-realization boundary).** A factor is auditioned on an
   in-sample window (e.g. 2014-01-01 … `is_end`=2020-12-31). But the thing it predicts — the
   `horizon`-day *forward return* — realizes *after* each date. The trap: a factor value on
   2020-12-31 has its answer in *January 2021*, outside the window. So the boundary is on the
   **label-realization date**, not the factor date: a row is kept only if *both* its factor date
   **and** `r(t) = open_days[pos(t)+horizon]` (the exact trading day the return realizes) are
   `≤ is_end`. Enforced by 3 belts in
   [walk_forward_validation.py](walk_forward_validation.py) (`IsWindowedPanel` raises
   `IsEndLeakageError` on any violation).

2. **Gates at every door.** You cannot promote a factor by editing a file. Each transition runs
   through code that checks the definition is unchanged, the evidence is real, and (for
   `approved`) that independent OOS proof + a git SHA exist — and *refuses* otherwise.

## 4. The pipeline, end to end

The `factor_lifecycle` orchestrator profile (the **8th** built-in; see
[CLAUDE.md](../../../CLAUDE.md) §9) is **in-sample only by construction** — its DAG has *no*
`oos_test` stage, *no* event/vectorized backtest, and *no* holdout-seal claim. Its four steps
([factor_lifecycle_steps.py](../../research_orchestrator/factor_lifecycle_steps.py)):

```
object_resolver  →  dataset_build  →  walk_forward  →  [human gate]  →  registry_publish
```

1. **resolver** — looks up the requested factors in the registry, labels each by status, and
   accepts `draft`/`candidate`/`approved` for *this* gate (the gate's whole job is to grade
   drafts). Runs the **definition-binding** check (registry definition must equal the code) and
   computes **per-factor field eligibility** (every `$field` must clear the field-status
   registry, [config/field_registry/field_status.yaml](../../../config/field_registry/field_status.yaml)).
2. **dataset_build** — builds the **in-sample-only** panel for the field-eligible factors
   (`load_is_windowed_panel` for base; `load_is_windowed_panel_with_layer2` for composites /
   industry-relative). Composites/industry-relative are *same-date cross-sectional transforms*
   of base factors, so they inherit the `is_end` boundary unchanged.
3. **walk_forward** — runs `run_is_walk_forward`: per-factor `candidate`/`draft` verdict from the
   in-sample rank-IC + sign-consistency (`|rank_icir| ≥ 0.10 ∧ yearly sign-consistency ≥ 0.70`).
   No `oos_*` field is ever produced. Records each measurement to the file-locked testing ledger.
4. **registry_publish** — *only* if a human reviewer's gate decision is `approved` does it write a
   formal in-sample evidence row + `set_status('candidate')` for each passing factor (and persist
   `expected_direction`). It **never** writes `approved`. `rejected`/`quarantined` → no writes.

**Discovery research is unaffected.** `get_factor_catalog()` stays the authoritative computable
definition source for *all* sandbox/discovery work (its ~42 call sites ignore status). The
status-aware reader `get_factors(status_in=…)` ([factor_library/selection.py](../factor_library/selection.py))
is an *opt-in* filter for research that *wants* tiering — it is **not** the formal gate.

## 5. What each phase built (the map)

| Phase | Built | One-line purpose |
|---|---|---|
| **1** | 5 enforcement gates (writer, reader/"resolve-but-label", definition-binding, seal-key, ledger lock) | The rails that *prevent* a bad promotion. |
| **2** | Registry evidence schema + definition-bound importer | A place to *store* a factor's track record (evidence ≠ status). |
| **3** | `get_factors` status-aware reader + `sync_catalog_to_registry` | Lets research filter by status (exploration only, not the gate). |
| **4** | `run_is_walk_forward` (IS-only, `is_end`-bounded) + `run_historical_*` | The leak-proof audition (the heart). |
| **5** | The `factor_lifecycle` orchestrator profile (IS-only DAG, 4 handlers) | The assembly line. |
| **6** | First run on the 147 **base** factors → **72 candidate** | Operational use; caught + fixed 2 real bugs. |
| **7** | Extended to the 24 **composite + industry-relative** factors → **15 candidate** | Layer-2 gating; fixed the `cs_rank` cross-sectional PIT-leak. |

## 6. Where the system is now (2026-06-02)

- Live registry: **87 `candidate` + 84 `draft` + 0 `approved`** (171 total).
- The 84 drafts are the honestly-rejected set: ~33 field-ineligible (quarantine/pending datasets:
  `alpha_*`/`flow_*`/`margin_*`/`north_*`), the OOS-collapsers, and the in-sample-marginal.
- Every promotion carries **in-sample-only** evidence (no `oos_*`), is **definition-bound**, and
  is labeled **`oos_informed_backfill`** — see §7.
- Provenance: [phase6_selection_provenance.json](../../../workspace/research/factor_expansion/phase6_selection_provenance.json)
  + [phase7_selection_provenance.json](../../../workspace/research/factor_expansion/phase7_selection_provenance.json)
  + `testing_ledger` `phase6/phase7_selection_funnel` events.

## 7. Non-negotiable invariants (do not break these)

1. **`candidate` ≠ `approved`, and never auto-promotes.** Approval goes through the promotion gate
   in [release_gate.py](../../research_orchestrator/release_gate.py) /
   [factor_registry/store.py](../factor_registry/store.py) `set_status` — it requires a
   `current_git_sha` + `promotion_evidence` from an **independent PIT-correct OOS reproduction**
   (a sandbox/loader panel is *insufficient*).
2. **`get_factor_catalog()` is the source of truth for all discovery.** Registry status gates only
   *formal* validation components, never discovery.
3. **Never hand-roll the forward-return label or PIT alignment.** Use the sanctioned builders; the
   `is_end` belts and the field-status registry are load-bearing. Cross-sectional helpers
   (`cs_rank`/`cs_zscore`/`cs_demean`/`winsorize`) group by the **datetime level by name**
   (fail-closed) — a positional `level=0` is a lookahead-leak path (Phase 7 fix).
4. **The 87 are `oos_informed_backfill`.** They were *selected* using prior full-window knowledge,
   so for them **2021–2026 is "burned"** (already observed). They must **never** be described as a
   fresh OOS-free selection, and any future `candidate → approved` step for them must use a
   genuinely-**sealed** window.
5. **The 6 sealed-OOS expansion winners are a SEPARATE path** — already OOS-spent; do not run them
   through this IS-only gate.

## 8. How to run a `factor_lifecycle` gate (reproducible)

The profile is formal-only, so it needs a `Hypothesis` (no floor rails apply — `factor_lifecycle`
is not in `SUCCESS_CRITERIA_FLOORS`; set only `success_criteria.min_rank_icir`). Reusable tooling
from Phases 6–7 ([workspace/scripts/](../../../workspace/scripts/)):

- `phase6_setup_request.py --mode temp|live --factors a,b,c|--factors-file <json> --tag <t>` —
  builds the orchestrator request (and, for `temp`, a copied registry so live is untouched).
- `research_orchestrator_cli.py run --request-file <…>` — runs the DAG; it **pauses** at the two
  human gates.
- `phase6_drive_gates.py --run-dir <…> --decision approved` — authors the concern scores + the
  gate decision and resumes to publish.
- Always: **dry-run (compute-only) → temp-registry validation → live**, and record an
  `oos_informed_backfill` provenance artifact + ledger funnel event (see
  `phase6/phase7_record_selection_provenance.py`). A live registry write is confirm-first (§13).

## 9. Where the deeper detail lives

- **Validator + belts:** [walk_forward_validation.py](walk_forward_validation.py),
  [metrics.py](metrics.py), [status_rules.py](status_rules.py).
- **Orchestrator profile + 4 handlers:** [factor_lifecycle_steps.py](../../research_orchestrator/factor_lifecycle_steps.py),
  DAG in [engine.py](../../research_orchestrator/engine.py) (`_factor_lifecycle_dag_builder`).
- **Registry + gates:** [factor_registry/store.py](../factor_registry/store.py),
  [release_gate.py](../../research_orchestrator/release_gate.py),
  [validation_steps.py](../../research_orchestrator/validation_steps.py) (resolver allow-set, P1.3).
- **Field gate:** [field_status.yaml](../../../config/field_registry/field_status.yaml),
  [field_registry.py](../../data_infra/field_registry.py).
- **Per-phase design specs + GPT cross-reviews:** [workspace/research/factor_expansion/](../../../workspace/research/factor_expansion/)
  (`factor_lifecycle_phase{1..5}_spec.md`, `composite_gating_design.md`, `phase{6,7}_*review*.md`).
- **The dated "what changed" history:** [project_state.md](../../../project_state.md).
- **The enforced invariants (authoritative):** [CLAUDE.md](../../../CLAUDE.md) §3.
