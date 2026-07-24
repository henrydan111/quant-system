# GPT Re-review #2 — Macro wave M1 (DIFF-SCOPED) — Tier-2

Round 2 of 3. Per CLAUDE.md §10, diff-scoped: does the fold close what it claims, and does it
introduce new surface? **Tier-2** (frozen; no crafted-object analysis).

**Fold commit: `66d87a9`** (you reviewed `5d9a330`). Verdict folded: **REVISE, 3 P1 + 2 P2** —
zero declines.

## Your findings → the folds

1. **P1 THS snapshot coherence.** New `select_ths_snapshot(ths_members, cutoff)`: group by
   `fetched_at`, candidates = all `<= cutoff`, pick the UNIQUE latest, use ONLY that snapshot's
   complete membership; no candidate → the M4 omission. Your probe pinned verbatim — the mixed
   old/future frame yields only the old snapshot's concepts **in both row orders**; a
   two-past-snapshots case pins that the older eligible snapshot is NOT merged in. The selected
   snapshot's content hash (canonical sorted (board, con) pairs) is computed here and lands in
   MS03's value (`ths_content_sha256`).
2. **P1 C16b bundle.** `exposure_mapping_bundle_sha256(mappings, *, ths_snapshot=None)` hashes a
   **role-labelled canonical JSON**: `{tercile_rule, ms03_rule, policy_mapping, shock_mapping,
   ths_snapshot{effective_at, content_sha256}|null}`. Role swap → different bundle; snapshot
   content change → different bundle (both pinned). Your note "M3 must separately seal the
   D-close pool's snapshot identity" is recorded as **FROZEN M3 OBLIGATION (a)** in the design
   doc (with (b) THS snapshot identity sealing and (c) absence rendering).
3. **P1 all-or-nothing metrics.** Any required metric that cannot bucket → the WHOLE MS01/MS02
   row is `metric_unavailable` with null bucket/value. Your NaN-`float_mv` probe pinned.
4. **P2 schema conflict.** The row schema is now DECLARED as the frozen 11 §0d fields **+
   `row_id`**, an explicit M1-layer amendment recorded in the design doc (the "verbatim §0d"
   claim is retracted); the unused `no_contemporaneous_snapshot` STATUS is removed from the enum
   (the omission is a value marker; the industry face stays `mapped` — you endorsed this
   semantic, the contract is now synced); the MS02 "free-float-mv" phrasing corrected.
5. **P2 tercile rules frozen.** `min_observations=6`, `min_distinct=3`,
   `tie_rule=le_boundary_falls_lower`, degenerate distribution (q1==q2) = unavailable — all
   inside the hashed rule descriptor; tiny-pool and flat-pool refusals pinned.

Your non-blocking mapping suggestion (交通运输/家电 + `fx_sensitivity:medium`) is recorded as an
open note for the user's mapping edit pass — the YAMLs are unchanged this round (they remain the
user's review object; content edits before freeze are free).

## Verification

**19** M1 tests (7 new); the four behavioural probes verified **fail-pre-fix** by stashing the
engine diff (mixed-snapshot, partial-metric, bundle-role-swap, degenerate-distribution: 4 failed
pre-fix, all pass post-fix). Full `ai_research_dept` suite **935** green.

## Files (pin to `66d87a9`)

- https://raw.githubusercontent.com/henrydan111/quant-system/66d87a9/workspace/research/ai_research_dept/engine/macro_exposure.py
- https://raw.githubusercontent.com/henrydan111/quant-system/66d87a9/workspace/research/ai_research_dept/tests/test_macro_exposure.py
- https://raw.githubusercontent.com/henrydan111/quant-system/66d87a9/workspace/research/ai_research_dept/NF_UNIT_M1_DESIGN.md (fold record + frozen M3 obligations)
- (unchanged) the two mapping YAMLs, pending the user's edit pass

## The two diff-scoped questions

1. **Do the folds close all five findings?** In particular: is `select_ths_snapshot`'s
   latest-eligible rule the right coherence semantics (vs refusing mixed frames outright — I chose
   selection because a frame carrying history + a newer snapshot is a LEGITIMATE store shape, and
   the selection is deterministic and order-free); and is the bundle's `ths_snapshot=None` static
   form still acceptable for the static C16b registration while the per-day sealed form carries
   the snapshot?
2. **Does the fix create new surface?** The snapshot content hash's canonicalization (sorted
   board|con pairs — anything it fails to capture, e.g. `con_name` changes: deliberately excluded
   as display-only); the tightened tercile thresholds interacting with small pools; the
   `row_id` amendment's downstream effect on M2/M3 contracts.

Verdict: SOUND-TO-PROCEED (to M2, the macro flash section) or specific in-tier findings.
