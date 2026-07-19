# GPT Cross-Review Request — NF Final-Integration Unit 1 RE-REVIEW #10 (archive boundary, re-review#9 P0 folded)

You are re-reviewing the **decision-archive boundary** of the news-flash (NF) seat.
Re-review #9 confirmed P2 fixed and the contract/outcome/D7-artifact exact-type work
effective, but found **1 × P0**: the sealed-object exact-type sweep missed `CardRecord`,
the LEAF that feeds every hash above it in the identity chain. Folded per your four
prescriptions. Commit under review: `be5dfee` on branch `calendar-unfreeze`.

Your root cause: `CardRecord._payload()` was virtual; `build_card_registry()` accepted
subclasses via `isinstance`; and the registry's canonical payload trusted each
`r.content_hash`. So a `CardRecord` subclass forging `content_hash` from real fields
formed a whole genuine-typed chain (exact SealedCardRegistry → RenderedCard →
AttributeBundle → D7DecisionArtifact) around the forged record hash — the same P0 class
as #7, at the leaf.

## Files (embedded text authoritative; links for live cross-check)

- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_evidence.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_cards.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_legs.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_archive.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/tests/test_news_archive.py

## How P0 was folded — exact-type the CardRecord leaf; compose registry_hash from verified record payloads

1. **`card_record_canonical_payload()`** (news_evidence): module-level, non-overridable;
   `CardRecord._payload()` delegates to it, so genuine self-seals are byte-identical.
2. **`verified_record_content_hash(record)`**: requires `type(record) is CardRecord`
   (subclass refused) and recomputes + verifies `content_hash` via the canonical helper,
   returning the verified hash.
3. **`registry_canonical_payload()`** now composes `registry_hash` from
   `verified_record_content_hash(r)` for each member — never the members' self-sealed
   `content_hash`. `build_card_registry()` runs the same per record in its build loop, so
   a forged leaf dies at the registry boundary AND at every consume through
   `require_sealed_registry` (which calls `registry_canonical_payload`). `authorize()`
   also exact-types `CardRecord`, closing the whole leaf class (its inputs already come
   from a verified registry).
4. **Regression** `test_evil_card_record_subclass_refused_before_recording`: an
   `_EvilCardRecord` subclass with real NFR fields but an overridden `_payload()` forging
   `content_hash` is refused by `build_card_registry` AND by direct `SealedCardRegistry`
   construction; asserts nothing records.

## Reasoned scope of the remaining `content_hash` reads

The other `content_hash` reads all run AFTER a `require_sealed_registry` /
`build_card_registry` re-verification of every member, so trusting `content_hash` there is
now sound:
- `news_cards._records_hash` at `verify_d7_artifact` line ~740 runs on
  `src.records.values()` after `src = require_sealed_registry(artifact.source_registry)`;
- the D7 rebuild's `rec.content_hash` reads (bundle child/demoted hashes) are on records
  freshly rebuilt internally via `build_card_record`/`_build_attribute_records` (genuine),
  compared to the bundle's self-report;
- `news_legs._eligible_set_hash` runs on `penalty_eligible_records(artifact)`, which calls
  `require_sealed_registry(artifact.final_registry)` first.
`news_routing` claim/exposure objects carry their own `content_hash` but are a separate
class that does not enter the D7 registry/artifact/archive identity chain — flagged as an
explicit scope boundary, not a silent omission.

## Self-review (completed before this request)

Verdict: **clean for GPT**. Leaf-of-identity-chain sweep: every place `registry_hash` (or
any hash above it) is composed now routes each member through
`verified_record_content_hash` (exact-type + canonical recompute); no boundary trusts a
member's self-sealed `content_hash`. `isinstance(record, CardRecord)` grep-verified to
zero. Full invariant-class ledger (all now exact-type at their doors + canonical helper):
NewsScoringContract, NewsLegOutcome, D7DecisionArtifact, RenderedCard, AttributeBundle,
SealedCardRegistry, D7BaseFact, AttributeRow, SealedPayload, CardRecord. Suites: 785 green
(NF 684 + ai_layer 50 + text/harness 51).

## Review questions

1. Is the CardRecord leaf now closed — can any subclass (or duck-typed object) still get a
   forged `content_hash` into a `registry_hash`, `records_hash`, `base_content_hash`,
   bundle child/demoted hash, or `eligible_set_hash`, i.e. any hash the archive commits to?
2. Have I now enumerated the WHOLE sealed-object surface, or is there any other type whose
   self-sealed hash is composed into an archive-committed identity without an exact-type +
   canonical-recompute gate (routing objects, EvidenceRef, D7BaseFact base_content_hash
   provenance, or anything I scoped out)?
3. Are the "already-verified-before-read" arguments for the remaining `content_hash` reads
   correct in every ordering (each read is genuinely downstream of a
   require_sealed_registry / build_card_registry re-verification)?
4. Any regression from exact-typing `CardRecord` at `build_card_registry` /
   `require_sealed_registry` / `authorize` (a legitimate genuine-instance flow that now
   fails — full suite green; do you see a legitimate polymorphic use these block)?
5. Verdict: SOUND-TO-PROCEED (to the four-seat session-archive embedding) or further
   findings — with reproduced probes for anything you flag.
