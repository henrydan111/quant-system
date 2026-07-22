# GPT Cross-Review Request — NF Final-Integration Unit 1 RE-REVIEW #23 (archive boundary, reconstructed component copies + load capture-before-compare)

You are re-reviewing the **decision-archive boundary** of the news-flash (NF) seat. Your previous
verdict (on `8efb05d`) was **REVISE — 2 P1**: (1) the artifact pre-check was bypassed by
phase-substitution during the registry snapshot (`require_sealed_registry` runs the live mapping's
`.items()`, which swaps the already-verified `artifact.base_facts`/rows/card/bundle); (2)
load/recover read artifact/contract/decision_id before the type gate. Folded. **Commit under review:
`c515831`** on branch `calendar-unfreeze`.

Your findings, verbatim intent:
- Make card, bundle, facts, rows, and both registries into independent trusted snapshots and use
  only those locals afterward; do not call `artifact_canonical_payload(artifact)` or re-read live
  `artifact.*`; best to return a trusted artifact view.
- Reject non-exact-`str` IDs at all load/recover public entries; validate + snapshot contract/artifact
  before any comparison in `_load_and_verify_archive_file`, then compare only captured base values.

## Files (embedded text authoritative; links pin to `c515831`)

- https://raw.githubusercontent.com/henrydan111/quant-system/c515831/workspace/research/ai_research_dept/engine/news_cards.py
- https://raw.githubusercontent.com/henrydan111/quant-system/c515831/workspace/research/ai_research_dept/engine/news_archive.py
- https://raw.githubusercontent.com/henrydan111/quant-system/c515831/workspace/research/ai_research_dept/engine/news_evidence.py
- https://raw.githubusercontent.com/henrydan111/quant-system/c515831/workspace/research/ai_research_dept/tests/test_news_archive.py

## How it was folded

**P1 reconstruct-before-callback.** `verify_d7_artifact` now, BEFORE the `require_sealed_registry`
callbacks: exact-types + field-asserts artifact/card/bundle; captures `v_artifact_hash`;
RECONSTRUCTS `card`, `bundle`, every `base_fact`, and every `row` into fresh independent dataclass
copies (the caller holds no reference to them; each `__post_init__` re-verifies its self-hash).
Then `require_sealed_registry(source)`/`(final)` return fresh frozen registries (`src`/`fin`). AFTER
the callback, the root hash is built from the copies + `src`/`fin` (not `artifact_canonical_payload
(artifact)`), and the ENTIRE rebuild runs on the copies — no live `artifact.*` is read after the
callback. A `.items()` swap now hits only the discarded live artifact (invisible); a swapped
registry is caught by the hash bindings (its `registry_hash` won't match the copies'
`bundle.final_registry_hash` / `v_artifact_hash`).

**P1 load capture-before-compare.** `_load_and_verify_archive_file` now requires exact-`str`
`decision_id`/`execution_id`, runs `require_exact_contract` + `verify_d7_artifact`, and captures the
validated hashes (`v_contract_hash`, `v_contract_payload`, `v_artifact_hash`, `v_bundle_hash`,
`v_final_registry_hash`, `v_bundle_decision_id`) BEFORE reading the archive; the identity
comparisons then use only those captured base values (archive fields are plain disk JSON).
`load_and_verify_decision_archive` and `recover_and_seal_success_archive` reject a non-`str`
`decision_id` before `_find_success_commitment`.

## Regressions pinned

- `test_registry_items_callback_cannot_swap_verified_base_facts`: a source-registry mapping whose
  `.items()` swaps `artifact.base_facts` to a side-effecting `EvilFact` does not poison
  `verify_d7_artifact`, and the `EvilFact.fact_hash` accessor is NEVER read.
- `test_load_rejects_nonstr_decision_id_before_compare`: a non-`str` `decision_id` is refused at load
  before any `__eq__` runs.

## Self-review (completed before this request)

Verdict: **clean for GPT**. Live-artifact-read sweep of `verify_d7_artifact`: after the reconstruction
+ registry snapshot, every read is of the copies (`card`/`bundle`/`base_facts`/`rows`) or the fresh
`src`/`fin`; grep confirms no `artifact.base_facts`/`artifact.rows` read after the callback. The two
`require_sealed_registry(artifact.{source,final}_registry)` reads are the callback boundary itself;
the components are already copied. Load path: IDs exact-str-gated, contract/artifact validated +
captured before comparison. Full suite: 813 green (NF 712 + ai_layer 50 + text/harness 51). This
self-review does NOT substitute for your gate.

## Review questions

1. Is the phase-substitution class closed — after the reconstruction, can any callback (registry
   `.items()`, or any other) still swap a component that a later read trusts, or does everything
   downstream use the independent copies + fresh registries?
2. Are the reconstructed copies faithful and complete (card/bundle/base_fact/row rebuilt from their
   fields with self-hash re-verified), and is there any component the rebuild still reads from live
   `artifact.*` after the callback?
3. Is the load capture-before-compare complete — are all six identity comparisons on captured base
   values, and is `verify_d7_artifact` (now trustworthy per P1#1) the right validation to run before
   the archive read?
4. Any residual pre-type-gate read on the load/recover entries, or any other public entry that
   compares an untrusted ID/object before gating it?
5. Verdict: SOUND-TO-PROCEED (to the four-seat session-archive embedding) or further findings — with
   reproduced probes for anything you flag.
