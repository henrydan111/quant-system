# Factor Lifecycle — Phase 2 Design Spec (registry schema / evidence)

**Date:** 2026-05-31. **Status:** DRAFT for cross-review — no code written yet. Phase 1 (the five
enforcement gates) is merged to `wave1-field-promotion`. Phase 2 = the **registry evidence/metadata
schema** (plan §4 Phase 2; §2.1 master shape; §3 taxonomy). Derived from
`factor_lifecycle_formalization_plan.md` §2.1/§2.2/§3/§4 + §0.8.

**Hard boundary:** Phase 2 is **schema + evidence population ONLY**. It does NOT change any factor's
`status`, does NOT promote anything, and does NOT wire `get_factors()` (Phase 3) or any seal/frozen-set
behavior. It adds columns and a read-only populator so the Phase-6 backfill has the evidence it needs.
`approval_validity` already landed in P1.1; Phase 2 adds the rest of §2.1.

## Why now
The catalog re-validation (`catalog_revalidation_report.md`) produced per-factor walk-forward IS/OOS
ICIR, sign-consistency, AND a **long-only top-bucket metric** (`revalidate_derived_factors.py::
long_only_topbucket`) — the decisive "IC ≠ long-only return" evidence. Today that lives in CSVs +
markdown, not in the registry. Phase 2 makes the registry the source of truth for that evidence so the
reader/writer gates (Phase 1) and the backfill (Phase 6) act on structured data, not scripts.

## Scope (work-items, dependency-ordered)
| # | Item | Files (primary) | Adds |
|---|---|---|---|
| **P2.1** | Walk-forward + sealed-OOS evidence columns | `factor_registry/store.py` | `is_rank_icir`, `oos_rank_icir`, `sign_consistency`, `oos_ls_sharpe`, `retain_pct` on `factor_evidence` |
| **P2.2** | Long-only metric columns + viability flag | `factor_registry/store.py` | `lo_excess_ann`, `lo_sharpe`, `lo_hit` on `factor_evidence`; `long_only_viable` (derived) on `factor_master` |
| **P2.3** | Signal-role metadata (taxonomy §3) | `factor_registry/store.py` | `expected_direction`, `signal_role`, `requires_inverse_for_long_only`, `approved_uses`, `validation_scope` on `factor_master` |
| **P2.4** | Provenance binding | `factor_registry/store.py` | `provider_build_id`, `calendar_policy_id`, `last_revalidated_at` on `factor_master` |
| **P2.5** | Read-only evidence importer + HTML surfacing + tests | `factor_registry/store.py`, `report.py`, `factor_registry_cli.py` | `import_revalidation(...)` populator; review HTML columns; schema-migration + viability-rule tests |

Build order: **P2.1 → P2.2 → P2.3 → P2.4 → P2.5**. Each is additive schema + a normalize-on-load default
(mirror P1.1's `approval_validity` fail-closed backfill), so old rows read back cleanly.

## P2.2 — long-only viability rule (the one with real semantics, plan §3)
`long_only_viable` is **derived** (not free-form), from the cost-adjusted long-only top-bucket metric:
- `True` ⟺ `lo_sharpe ≥ 1.0` AND `lo_excess_ann > 0` AND `lo_hit ≥ 0.60`.
- `lo_sharpe < 0.5` → `False` (non-viable).
- `0.5 ≤ lo_sharpe < 1.0` → `review_only` (a third state, NOT silently `True`).

So `long_only_viable ∈ {viable, non_viable, review_only}` (string, fail-closed default `non_viable` on
missing metric). This is the column that prevents the val_heavy / "high-|IC| ≠ tradable" trap from
re-entering selection.

## P2.3 — signal-role is auto-SUGGESTED, human-ASSIGNED (plan §3)
`signal_role ∈ {long_only_alpha, risk_sleeve, short_side, neutralizer, unassigned}`. The importer writes
an **auto-suggestion** into a separate `signal_role_suggested` column from the metric (`long_only_viable
== viable` → suggest `long_only_alpha`; high-|IC| + weak long-only → suggest *nothing*, leave for a
human). The authoritative `signal_role` stays `unassigned` until a human sets it (via a gated CLI like
P1.1's `set-status`). Weak long-only does NOT auto-imply `risk_sleeve`. `requires_inverse_for_long_only`
is set when the factor's IC sign means the long-only leg needs the inverse ranking.

## P2.4 — provenance
`provider_build_id` + `calendar_policy_id` bind each row's evidence to the provider build it was
measured on (so a future rebuild can flip `approval_validity→stale` per P1.1 / plan §2.2);
`last_revalidated_at` timestamps the most recent walk-forward/OOS evidence. Sourced from
`provider_build.json` (the §3 provider self-attestation manifest).

## P2.5 — read-only importer (NO status changes)
`FactorRegistryStore.import_revalidation(...)` ingests the existing artifacts —
`catalog_revalidation/catalog_revalidation_status.csv`, `derived_revalidation_status.csv`,
`oos_results_and_registration.md`'s frozen top-set — and writes ONLY the new evidence/metadata columns
onto the matching current rows. It MUST NOT touch `status` (every row stays `draft`; Phase 6 does the
gated status backfill). Idempotent; logs which factors were matched/missed.

## Open questions for cross-review
1. **Column home:** are the LO/walk-forward metrics best on `factor_evidence` (per-run, append-only —
   matches the existing IC evidence) with a `latest_*` mirror on `factor_master` (matching the existing
   `latest_rank_icir_5d` pattern), or directly on `factor_master`? (Leaning: evidence + latest-mirror.)
2. **`long_only_viable` storage:** derived-on-read (compute from stored LO metrics each load) vs
   stored-and-normalized (like `approval_validity`)? Derived-on-read avoids staleness but adds load cost.
3. **`review_only` semantics:** does `review_only` block formal long-only use the same as `non_viable`
   (fail-closed) until a human confirms, or is it advisory? (Leaning: fail-closed for *long-only* use;
   does not affect `risk_sleeve`/short use.)
4. **Importer trust:** the revalidation CSVs were produced by `historical_investigation`-class scripts
   (PR-7 SCRIPT_STATUS). Is importing their numbers as registry evidence acceptable for Phase 2
   (evidence ≠ approval; the writer gate still governs promotion), or must the metrics be recomputed
   through a `formal_candidate`-class path first?
5. **Phase-3 dependency (GPT §0.8 carry-forward):** none of P2.x wires a live `frozen_set_hash`. Confirm
   Phase 2 introduces no seal/frozen-set behavior, so the "single seal_key source" rule stays a Phase-3
   concern.

## Boundary / non-goals
- No status change, no promotion, no `get_factors()` (Phase 3), no orchestrator profile (Phase 5), no
  seal/frozen-set wiring (Phase 3/5), no backfill of the 171/6 (Phase 6).
- Pure additive schema + a read-only populator + tests + HTML. Every new column normalizes on load
  (fail-closed defaults) so pre-Phase-2 registries read back unchanged.

## Acceptance
All new columns added with fail-closed load defaults; `import_revalidation` populates evidence without
touching `status`; `long_only_viable` derivation matches the §3 thresholds (unit-tested at the
boundaries 0.5 / 1.0 / hit 0.60); provenance binds to `provider_build.json`; HTML review surfaces the LO
metric + signal-role; CLAUDE.md/AGENTS.md updated; full offline suite green. Then Phase 3 (`get_factors`
+ staged catalog→registry cutover) begins.
