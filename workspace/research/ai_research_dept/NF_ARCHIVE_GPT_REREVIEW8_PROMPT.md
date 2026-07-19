# GPT Cross-Review Request — NF Final-Integration Unit 1 RE-REVIEW #8 (archive boundary, re-review#7 folded)

You are re-reviewing the **decision-archive boundary** of the news-flash (NF) seat.
Re-review #7 returned **FIX-FIRST: 1 × P0 (the D7 artifact family could decouple its
committed/archived hashes from its real fields via a subclass `_payload()` override) +
1 × P2 (recovery's archive-exists branch validated against a stale ledger snapshot)**.
Both folded per your prescriptions, and the invariant class was swept across the
entire sealed-object surface. Commit under review: `b396a3e` on branch
`calendar-unfreeze`.

## Files (embedded text authoritative; links for live cross-check)

- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_archive.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_cards.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_evidence.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_decision.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_executors.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_legs.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/tests/test_news_archive.py

## How P0 was folded — exact-type the whole D7 artifact family + non-virtual canonical hashing

Your root cause: `verify_d7_artifact`/`require_sealed_registry` accepted subclasses and
verified via the object's virtual `_payload()`, so a subclass overriding `_payload()`
minted a forged `artifact_hash` / `registry_hash` from real components and passed the
whole chain, then the archive stored the forged hash and a genuine artifact could not
read it. Folded exactly as prescribed:

1. **Exact-type at every D7 consume door.** `verify_d7_artifact` now requires
   `type(x) is C` for D7DecisionArtifact, RenderedCard, AttributeBundle, each
   D7BaseFact, each AttributeRow; `require_sealed_registry` requires
   `type(registry) is SealedCardRegistry` (both src and fin flow through it).
   `verify_bundle_registry` and `build_attribute_bundle`'s input card are exact-typed
   too. A subclass is refused before any hash is trusted.
2. **Non-virtual canonical hashing.** Module-level, non-overridable helpers read the
   ACTUAL fields — `artifact_canonical_payload`, `card_canonical_payload`,
   `bundle_canonical_payload`, `base_fact_canonical_payload`,
   `attribute_row_canonical_payload` (news_cards), `registry_canonical_payload`
   (news_evidence). Every boundary `verify_sealed(...)` now hashes the canonical
   helper output, not `obj._payload()`. Each class's own `_payload()` delegates to its
   helper, so genuine self-seals are byte-identical.
3. **Same class swept to the executor boundary.** `verify_payload_for_execution` and
   `make_execution_view` exact-type SealedPayload and hash via
   `sealed_payload_canonical_payload`. A repo grep returns **zero** boundary
   `<obj>._payload()` virtual calls. `factor_refs`/`leg_refs` intentionally keep
   `isinstance` — they only read the artifact's `.final_registry`, which is itself
   exact-typed at `require_sealed_registry`, and they trust no artifact-self hash.
4. **Your probes, pinned**: an `_EvilArtifact` subclass (real components, overridden
   `_payload()` forging `final_registry_hash`) is refused at `verify_d7_artifact` AND
   `record_decision` (asserted it never records); an `_EvilRegistry` subclass with a
   self-consistent forged `registry_hash` is refused at the D7 consume boundary.

## How P2 was folded — fresh-snapshot recovery exists-branch

`recover_and_seal_success_archive`'s archive-exists short-circuit previously validated
the on-disk archive against the recovery's OWN entry snapshot (`chain`), so a
competitor that grew the ledger then sealed between recovery's entry and its
exists-check made the exists-branch verify a fresh-anchor archive against the stale
snapshot → false "anchor not in chain" rejection. The exists-branch now calls
`load_and_verify_execution_archive`, which takes a FRESH `_read_chain` snapshot.
Pinned deterministically (`test_recovery_stale_snapshot_grows_then_seals_converges`):
recovery A resolves its success commitment on a stale snapshot; a competitor B grows
the ledger AND seals the archive at that instant; A reaches its exists-branch and
converges to B's archive instead of erroring. The earlier write-once-conflict race
(#6) and the serial-growth idempotency (#5) still pass.

## Self-review (completed before this request)

Verdict: **clean for GPT**. Subclass-_payload() invariant-class sweep: every sealed
type crossing a verification boundary (NewsScoringContract, NewsLegOutcome,
D7DecisionArtifact, RenderedCard, AttributeBundle, SealedCardRegistry, D7BaseFact,
AttributeRow, SealedPayload) is now exact-typed at its door and hashed via a
module-level canonical helper; zero boundary virtual `_payload()` remain (grep-verified).
Non-boundary `isinstance(artifact, …)` in `factor_refs`/`leg_refs` reads only the
exact-typed registry and trusts no self-hash — reasoned scope note, not a gap.
Recovery snapshot discipline: entry / commitment / contract-binding use one snapshot;
the exists-branch and the write-once-conflict branch both re-read fresh (they return
an independently re-verified archive). Suites: 784 green (NF 683 + ai_layer 50 +
text/harness 51).

## Review questions

1. Is P0 closed across the WHOLE sealed-object surface — can you name any remaining
   type whose caller-controllable virtual behavior still influences what gets hashed
   into a commitment/archive/payload versus what the verifier/evaluator reads
   (including SealedPayload, D7BaseFact, AttributeRow, or a helper I flagged as
   non-load-bearing)?
2. Are the module-level canonical helpers faithful to each class's genuine `_payload()`
   (I made each `_payload()` delegate to its helper, so drift is impossible by
   construction — do you agree, or is there a hashing surface that still bypasses a
   helper)?
3. Is the recovery snapshot discipline now correct in all orderings — entry vs
   exists-branch vs write-once-conflict branch each reading the right (stale-for-its-
   own-decision vs fresh-for-a-competitor's-archive) snapshot?
4. Any regression from the exact-type doors (a legitimate flow passing a genuine
   instance that now fails — the full suite is green; do you see a legitimate
   polymorphic use these block)?
5. Verdict: SOUND-TO-PROCEED (to the four-seat session-archive embedding) or further
   findings — with reproduced probes for anything you flag.
