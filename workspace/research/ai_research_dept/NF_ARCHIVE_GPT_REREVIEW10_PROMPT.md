# GPT Cross-Review Request — NF Final-Integration Unit 1 RE-REVIEW #10 (archive boundary, re-review#9 P0 folded + adversarial self-review)

You are re-reviewing the **decision-archive boundary** of the news-flash (NF) seat.
Re-review #9 confirmed P2 fixed and the contract/outcome/D7-artifact exact-type work
effective, but found **1 × P0**: the sealed-object exact-type sweep missed `CardRecord`,
the LEAF that feeds every hash above it in the identity chain. Folded per your four
prescriptions (`be5dfee`), then — while you were unavailable — I ran an **adversarial
self-review** of the full sealed-object surface and folded three more findings
(`313df87`). **Commit under review: `313df87`** on branch `calendar-unfreeze` (the raw
links below track the branch head, so they already point at `313df87`).

Your #9 root cause: `CardRecord._payload()` was virtual; `build_card_registry()`
accepted subclasses via `isinstance`; and the registry's canonical payload trusted each
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

## Adversarial self-review folded on top (`be5dfee` → `313df87`)

With GPT unavailable, I enumerated every frozen dataclass in the engine (13) and audited,
for each, whether its self-sealed hash reaches an archive-committed identity and whether
its door is exact-type + non-virtual-canonical. Three findings, all folded:

1. **`_payload` delegation drift (a FALSE claim in my own #10 prompt, now fixed).** My
   draft claimed "every `_payload()` delegates to its helper, so drift is impossible by
   construction." That was false for **`NewsLegOutcome`** and **`NewsScoringContract`** —
   both still held their OWN dict literal instead of delegating to
   `outcome_canonical_payload` / `contract_canonical_payload`. Not a decoupling P0 (the
   boundaries already hash via the non-virtual free functions under exact-type gates), but
   a latent drift hazard: if the literal and the helper diverged, a genuine object's
   self-seal would disagree with the boundary canonical recompute and fail-closed. Both now
   delegate. Pinned: `test_canonical_helpers_match_class_payload_no_drift` asserts
   `obj._payload() == <helper>(obj)` for a genuine instance of every class that has a
   module-level helper.
2. **The last four `isinstance` sites on sealed types flipped to exact-type**
   (`build_attribute_bundle`'s base_fact filter; `factor_refs` / `leg_refs` /
   `build_leg_payload_ast` on `D7DecisionArtifact`). All non-load-bearing (their
   products/registries are re-verified downstream at `verify_d7_artifact` /
   `require_sealed_registry`), flipped anyway so "the whole sealed surface is exact-typed"
   is a literal grep-verifiable fact. **Zero `isinstance` on any of the 10 sealed types
   now remains** (grep-verified).
3. **Proved (not asserted) the routing/ingest scope-out.** `AtomicClaim` /
   `AliasRegistry` / `SystemicExposureSnapshot` are referenced ONLY within
   `news_routing.py` — never consumed by the card/registry/artifact/archive chain;
   `ClusterSnapshot` / `NewsCoverageArtifact` hashes are never sealed into a
   `CardRecord.derivation` (which holds only parent record content-hashes +
   `attribute_type`), a card payload, or any archive field.

This self-review is NOT a substitute for your independent gate (every prior round found a
real P0 after I believed the surface clean) — it is disclosed here so you can check my
work, not trust it.

## Self-review (completed before this request)

Verdict: **clean for GPT**. Leaf-of-identity-chain sweep: every place `registry_hash` (or
any hash above it) is composed now routes each member through
`verified_record_content_hash` (exact-type + canonical recompute); no boundary trusts a
member's self-sealed `content_hash`. Grep-verified at `313df87`: zero boundary
`<obj>._payload()` virtual calls (only `__post_init__` `self._payload()` self-seals
remain, reachable at a boundary only after an exact-type gate); zero `isinstance` on any
of the 10 sealed types. Full invariant-class ledger (all exact-type at their doors +
non-virtual canonical helper, and every `_payload()` delegates to its helper):
NewsScoringContract, NewsLegOutcome, D7DecisionArtifact, RenderedCard, AttributeBundle,
SealedCardRegistry, D7BaseFact, AttributeRow, SealedPayload, CardRecord. Suites: 786 green
(NF 685 + ai_layer 50 + text/harness 51).

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
   `require_sealed_registry` / `authorize`, or from the self-review's four `isinstance`→
   exact-type flips (a legitimate genuine-instance flow that now fails — full suite green;
   do you see a legitimate polymorphic use these block)?
5. Self-review check: is the `_payload`→helper delegation now correct and drift-proof for
   ALL ten classes (including SealedPayload, which the drift-guard test does not construct
   directly), and do you agree the two delegation fixes were not masking a live decoupling
   (i.e. the boundaries were already non-virtual before the fix)?
6. Verdict: SOUND-TO-PROCEED (to the four-seat session-archive embedding) or further
   findings — with reproduced probes for anything you flag.
