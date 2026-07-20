# GPT Cross-Review Request — NF Final-Integration Unit 1 RE-REVIEW #11 (archive boundary, inner-container P0 folded)

You are re-reviewing the **decision-archive boundary** of the news-flash (NF) seat. Your
previous verdict (reviewing `313df87`) confirmed the whole `_payload`/exact-type/canonical
line effective, but found **1 × P0 with two exploit paths**: exact-typing the OUTER sealed
object does NOT protect its INNER container fields — they were kept as the caller-supplied
objects. Folded per your prescriptions, then swept across the whole sealed surface.
**Commit under review: `b9c794a`** on branch `calendar-unfreeze` (raw links track the
branch head).

Your root cause, verbatim intent:
- `CardRecord` did only an outer exact-type check; `allowed_uses` / `allowed_dimensions`
  stayed the caller's object. A `frozenset` SUBCLASS iterated (`sorted` → the committed
  hash) as `context_only` but membership (`in` → `authorize`) as `factor_positive` —
  sealed identity unchanged, authorization semantics flipped; `verify_d7_artifact`
  accepted it and the demoted `NFD01` re-entered the factor LLM input.
- Same root at `SealedCardRegistry.records`: a live mapping read at verify via `values()`
  and later via `items()`/`get()` — a stateful mapping mutates the record set between.

## Files (embedded text authoritative; links for live cross-check)

- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_seal.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_evidence.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_cards.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_decision.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_executors.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_legs.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/tests/test_news_archive.py

## The invariant class and how it was closed (fold by class, not instance)

The class: **any sealed object field read once to compose the committed hash and again for
a semantic/authorization/binding check can decouple if it is a polymorphic or stateful
object** (frozenset/str/tuple/int subclass, or a live mapping) — the two reads disagree
while the sealed hash is unchanged. Every sealed object now **normalizes its semantic
fields to plain immutables in `__post_init__` BEFORE verifying/sealing**, so no field can
differ between the hash read and any later read.

- **`news_seal` shared helpers**: `plain_str` (uses `str.__str__` to take the real
  character content, bypassing an overridable `__str__`); `plain_str_tuple` (one-shot
  iteration snapshot into a plain tuple of plain str — defeats a stateful `__iter__` and a
  container subclass); `plain_object_tuple` (strips a container subclass; elements stay,
  they are exact-typed and self-verified elsewhere).
- **`CardRecord`** (`news_evidence`): `allowed_uses`/`allowed_consumers`/
  `allowed_dimensions` → plain `frozenset[plain str]` (snapshot one iteration + per-element
  `plain_str`, so iteration == membership); the str scalars → `plain_str`; `derivation` →
  plain nested tuple via `_plain_scalar` (str → plain str; `None`/`bool`/`int`/`float`
  preserved as-is; anything else refused — genuine derivation legitimately carries `None`,
  which the first cut of this fold wrongly stringified and the test caught). After
  coercion the record's iteration (hashed) and membership (`authorize`) are the SAME plain
  frozenset.
- **`SealedCardRegistry`** (`news_evidence`): `records` is snapshotted ONCE at construction
  into a deep-immutable `MappingProxyType`, with every value required to be `type(v) is
  CardRecord`; all later reads (verify `values()`, consume `items()`/`get()`) see the same
  frozen snapshot. `cutoff_iso`/`registry_hash` → `plain_str`.
- **`RenderedCard` / `D7BaseFact` / `AttributeRow` / `AttributeBundle` /
  `D7DecisionArtifact`** (`news_cards`): all str fields → `plain_str`; all hash/id tuple
  fields → `plain_str_tuple`; `base_facts`/`rows` → `plain_object_tuple`; `D7BaseFact.
  importance` required exact `int` (`verify_d7_artifact` gates the mandatory D7 split
  coverage on `importance >= FLOOR`, and an int-subclass `__ge__` could decouple that from
  the hashed value).
- **`SealedPayload`** (`news_decision`): str fields + `expected_ids`/`ref_occurrences`/
  `authorized_ids` normalized; `payload_ast` untouched (it is re-derived and byte-compared
  at the executor boundary, never trusted from the object).
- **`NewsScoringContract`** (`news_executors`): `schema_id`/`output_mode`/
  `primary_decision_horizon`/`contract_hash` → `plain_str`. **`NewsLegOutcome`**
  (`news_legs`) already rejects every subclass — its `__post_init__` does
  `type(x) is str`/`is int`/`is bool` on all fields — so it is immune with no coercion.

## Regressions pinned (your two probes)

- `test_polymorphic_frozenset_field_neutralized`: a `frozenset` subclass that iterates as
  `context_only` but claims membership `factor_positive` is coerced to a plain
  `frozenset({"context_only"})`; `type(rec.allowed_uses) is frozenset`, the canonical
  payload hashes `context_only`, and `authorize(rec, use="factor_positive", …)` is `False`
  — hashing and authorization now agree.
- `test_stateful_registry_mapping_snapshotted`: a mapping whose `.items()` flips after the
  first (snapshot) read is frozen to `MappingProxyType` at construction (later reads see
  the snapshot); a non-`CardRecord` value is refused with `恰 CardRecord`.

## Self-review (completed before this request)

Verdict: **clean for GPT**. Read-twice sweep: I traced every collection/scalar field on
every sealed object to whether it is read for the hash AND for a separate semantic/binding
check, and coerced all such fields to plain immutables at construction; `payload_ast` is
the one intentional exception (re-derived, never trusted). Genuine-value safety: coercion
is identity for plain str/tuple/int, verified by the full suite (the one genuine breakage
— `derivation` carrying `None` — was caught and fixed with `_plain_scalar`). Full suite:
788 green (NF 687 + ai_layer 50 + text/harness 51). This self-review does NOT substitute
for your gate — every prior round I believed the surface clean and you found the next
instance one level deeper; it is disclosed for you to check, not trust.

## Review questions

1. Is the inner-container decoupling class now closed across the WHOLE sealed surface —
   can you still construct any sealed object whose committed hash disagrees with a later
   semantic/authorization/binding read via a polymorphic or stateful inner field
   (frozenset/str/tuple/int subclass, live mapping, or one I missed)?
2. Is the coercion faithful and complete: does any hash-composing or semantic read still
   reach a caller-supplied object BEFORE normalization (e.g. a field I did not coerce, a
   read that runs before `__post_init__` finishes, or an element-level subclass inside a
   coerced container)?
3. `payload_ast` is deliberately not coerced (re-derived at the boundary). Is that boundary
   re-derivation genuinely independent of the object's own state, or can a stateful
   `payload_ast` still influence what the executor sees vs what was hashed?
4. Any regression from the coercions (a legitimate genuine-instance flow now failing — the
   full suite is green; the `derivation` `None` case is handled) or from `D7BaseFact.
   importance` / registry-value now requiring exact types?
5. Verdict: SOUND-TO-PROCEED (to the four-seat session-archive embedding) or further
   findings — with reproduced probes for anything you flag.
