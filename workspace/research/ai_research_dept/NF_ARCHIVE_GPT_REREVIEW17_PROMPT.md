# GPT Cross-Review Request — NF Final-Integration Unit 1 RE-REVIEW #17 (archive boundary, frozen scoring registry)

You are re-reviewing the **decision-archive boundary** of the news-flash (NF) seat. Your
previous verdict (on `5a19609`) was **REVISE — 1 P1**: #16 froze `final_registry_hash` but not the
`artifact.final_registry` OBJECT that actually computes the score. Folded. **Commit under review:
`2112c60`** on branch `calendar-unfreeze`.

Your finding, verbatim intent:
- After `verify_d7_artifact`, the recompute compared `trusted_eval` to the caller's
  `bundle["evaluation"]` (no type gate); its `__ne__` fired a callback that swapped
  `artifact.final_registry` to another self-consistent `SealedCardRegistry` (verifies, scores
  differently) with the hash unchanged; the later `trusted_eval` used that live registry and wrote
  a wrong score (74→52) into an archive stamped with the original registry hash — reload failed,
  write-once blocked the correct re-seal. Prescription: generate and use an independent
  artifact/registry snapshot immediately after `verify_d7_artifact`; the terminal checks, both
  evaluations, and the archive payload must use only that snapshot; compute the trusted evaluation
  before reading/comparing the caller evaluation.

## Files (embedded text authoritative; links pin to `2112c60`)

- https://raw.githubusercontent.com/henrydan111/quant-system/2112c60/workspace/research/ai_research_dept/engine/news_archive.py
- https://raw.githubusercontent.com/henrydan111/quant-system/2112c60/workspace/research/ai_research_dept/engine/news_evidence.py
- https://raw.githubusercontent.com/henrydan111/quant-system/2112c60/workspace/research/ai_research_dept/tests/test_news_archive.py

## How it was folded

- Immediately after `verify_d7_artifact`, `verify_execution_bundle` captures an INDEPENDENT frozen
  registry snapshot: `v_final_registry = require_sealed_registry(artifact.final_registry)`. Per
  re-review#14, `require_sealed_registry` reconstructs a fresh `SealedCardRegistry` (reads the live
  mapping exactly once, rebuilds each `CardRecord`, freezes to a `MappingProxyType`, re-verifies) —
  so `v_final_registry` is a deep-frozen snapshot independent of the caller's `artifact.
  final_registry`.
- The trusted records are built from the disk-resolved terminal rows and `trusted_eval` is computed
  from `v_final_registry` BEFORE the `!= bundle["evaluation"]` compare — the trusted score is
  finalized before any caller callback can run. The caller evaluation is now only a post-hoc sanity
  compare and is never archived.
- The verified snapshot reuses that already-computed `trusted_records` / `trusted_eval` and never
  touches `artifact.final_registry` again. seal still writes only `{**verified, ledger_head}`.

## Regression pinned

- `test_registry_swap_via_evaluation_callback_ineffective`: a `bundle["evaluation"]` whose `__ne__`
  swaps `artifact.final_registry` mid-verify does not change the archived score (computed from the
  frozen snapshot), and the archive reloads cleanly once the live registry is restored.

## Self-review (completed before this request)

Verdict: **clean for GPT**. Live-registry-read sweep of the archive path: after
`v_final_registry` is captured, `verify_execution_bundle` computes both the sanity compare and the
archived `trusted_eval` from `v_final_registry`; the snapshot reuses those; no post-capture read of
`artifact.final_registry` remains in the archive path. (The factor/penalty terminal checks earlier
use `artifact` via `_check_terminal_row`'s `leg_expected_ids(artifact.final_registry)`, but those
run BEFORE the caller-evaluation callback point, on the genuine registry, and each is followed by
the disk-resolved binding; the exploited read was the post-compare `trusted_eval`, now frozen.)
Full suite: 803 green (NF 702 + ai_layer 50 + text/harness 51). This self-review does NOT substitute
for your gate.

## Review questions

1. Is the scoring input now fully frozen — does the archive path read `artifact.final_registry` (or
   any other live scoring input: `artifact.final_registry.records`, the source registry, base
   facts) AFTER a caller-callback-capable point, for the trusted evaluation or anything the archive
   commits to?
2. Is capturing `v_final_registry` right after `verify_d7_artifact` early enough — is there a
   callback-capable read (`sel.get`, `bundle[...]`, records `__getitem__`, a comparison against a
   caller object) BETWEEN `verify_d7_artifact` and the `require_sealed_registry` capture?
3. `trusted_eval` is computed before the `!= bundle["evaluation"]` compare. Is the compare itself
   safe now (its callback can no longer influence the archived value), or should the caller
   evaluation be dropped entirely / type-gated rather than compared?
4. Are the earlier `_check_terminal_row` reads of `artifact.final_registry` (before the callback
   point) genuinely safe, or can a caller object earlier in the flow trigger a registry swap before
   those reads?
5. Verdict: SOUND-TO-PROCEED (to the four-seat session-archive embedding) or further findings —
   with reproduced probes for anything you flag.
