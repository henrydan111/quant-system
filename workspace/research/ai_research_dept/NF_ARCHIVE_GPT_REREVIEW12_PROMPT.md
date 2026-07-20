# GPT Cross-Review Request — NF Final-Integration Unit 1 RE-REVIEW #12 (archive boundary, __dict__-injection P0 + hash P1s folded)

You are re-reviewing the **decision-archive boundary** of the news-flash (NF) seat. Your
previous verdict (on `b9c794a`) confirmed the two new regressions but found **1 P0 + 2 P1**,
all the same decoupling class one level deeper: a frozen dataclass's `__dict__` is directly
writable (no `object.__setattr__`), so the #11 construction-time coercion can be undone by a
later `record.__dict__[...] = evil` injection. Folded. **Commit under review: `adf451a`** on
branch `calendar-unfreeze` (raw links track the branch head).

Your findings, verbatim intent:
- **P0**: `SealedCardRegistry` froze the outer mapping but stored the caller's `CardRecord`
  objects; a stateful mapping, during its single `items()`, replaced a record's internal set
  via `record.__dict__` with an object that iterates (`sorted`→hash) as `context_only` but
  membership (`in`→`authorize`) as `factor_positive`. `verify_d7_artifact` passed, the demoted
  `NFD01` re-entered the factor LLM, the archive sealed.
- **P1**: `NewsLegOutcome.outcome_hash` had no exact-type/normalization — a `str` subclass
  passed `verify_sealed` + the commitment compare, sealed a fake hash, then failed to reload
  while write-once blocked the correct re-seal.
- **P1**: `NewsScoringContract.contract_hash`'s `type(...) is str` guard skipped `str`
  subclasses (same fake-hash path); `schema_id` also lacked a precise type gate.

## Files (embedded text authoritative; links for live cross-check)

- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_evidence.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_legs.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_executors.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_decision.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_cards.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/tests/test_news_archive.py

## How P0 was folded — durable base-type verification at every consume, not just at construction

The root insight: construction-time coercion is not durable because `__dict__` stays
writable. So the field types are re-verified at EVERY consume:

- **`assert_base_record_fields(record)`** (`news_evidence`): the record's semantic fields must
  be EXACT base types — `allowed_uses`/`allowed_consumers`/`allowed_dimensions` each
  `type(s) is frozenset` with every element `type(u) is str`; the str scalars `type(x) is
  str`; `derivation` a plain nested tuple of `str`/`None`/`bool`/`int`/`float`. A
  `__dict__`-injected subclass (iterate ≠ membership) is refused HERE, before the hash
  recompute and before `authorize`.
- **`verified_record_content_hash`** runs `assert_base_record_fields` first, so `registry_hash`
  composition and every identity-chain recompute reject an injected field.
- **`SealedCardRegistry.__post_init__`** now REBUILDS each value via `normalize_card_record`
  into a fresh independent `CardRecord` (the caller keeps no reference to the stored object);
  `normalize_card_record` asserts base types before rebuilding, so an injection during the
  single `items()` iteration is caught at construction.
- **`authorize()`** self-guards with `assert_base_record_fields` at its membership read, so the
  gate holds regardless of whether an upstream `require_sealed_registry` ran. (All membership
  reads in the engine are on the three CardRecord frozenset fields; every path either
  `require_sealed_registry`s first or goes through `authorize` — grep-verified: `in
  r.allowed_*` at `news_legs.penalty_eligible_records` [require_sealed_registry first],
  `news_decision.leg_expected_ids` [require_sealed_registry first], `news_evidence.authorize`
  [now self-guards].)

Only CardRecord's frozenset fields have the iterate-vs-membership asymmetry that makes this
exploitable; the tuple/hash fields on the other sealed objects are only ever read as
compared iterations (a stateful container would fail the rebuild comparison), so the class is
closed by the record-field verification.

## How the P1s were folded

- **`NewsLegOutcome.outcome_hash`**: required exact `str` + 64-hex before `verify_sealed`/
  compare (a `str` subclass is refused, not merely coerced).
- **`NewsScoringContract`**: `schema_id`/`output_mode`/`primary_decision_horizon`/
  `contract_hash` coerced via `plain_str` UNCONDITIONALLY (`isinstance str` → flattened to a
  plain str, so the `type(...) is str` skip is gone), plus an explicit exact-`str` gate on
  `schema_id`.

## Regressions pinned (your three, plus the post-construction case)

- `test_dict_injected_record_field_refused_at_construction`: a mapping that injects an evil
  `frozenset` (iterate=context_only / membership=factor_positive) into a record's `__dict__`
  during `items()` is refused at registry construction; nothing seals.
- `test_dict_injection_after_construction_refused_at_consume`: the same injection into a
  stored record's `__dict__` after construction is refused at the next
  `require_sealed_registry`.
- `test_fake_outcome_hash_subclass_refused`: a `str`-subclass `outcome_hash` is refused at
  `NewsLegOutcome` construction.
- `test_fake_contract_hash_subclass_neutralized`: a `str`-subclass `contract_hash` is
  flattened to a plain `str` (right value) or rejected by `verify_sealed` (wrong value).

## Self-review (completed before this request)

Verdict: **clean for GPT**. `__dict__`-injection class sweep: the only fields with an
iterate-vs-membership asymmetry are CardRecord's three frozenset fields; they are re-verified
as exact base types at every consume (registry recompute, and `authorize` self-guard), and the
registry rebuilds values into independent records. Every membership read in the engine was
traced to a `require_sealed_registry`/`authorize` gate. The two hash P1s were exact-typed. I
confirmed the reviewer's `__dict__`-injection attack is now refused with a direct probe before
writing the regressions. Full suite: 792 green (NF 691 + ai_layer 50 + text/harness 51). This
self-review does NOT substitute for your gate — every prior round I believed the surface clean
and you found the next instance one level deeper; disclosed for you to check, not trust.

## Review questions

1. Is the `__dict__`-injection / stateful-container class now closed — can you still inject
   (via `__dict__`, an aliased mutable, or a stateful container) a field whose committed hash
   disagrees with a later semantic/authorization read, on CardRecord OR any other sealed
   object reached by the archive?
2. Is the "only CardRecord frozenset fields have the iterate-vs-membership asymmetry" argument
   correct, or is there a membership/`in`/`get`/dict-key read on some other `__dict__`-mutable
   sealed field I did not gate?
3. Are `assert_base_record_fields` and the `normalize_card_record` rebuild placed at every
   consume that precedes a membership read or a hash trust (registry recompute, authorize,
   penalty_eligible_records, leg_expected_ids, build_factor_payload_ids)?
4. Any regression from the exact-type gates on `outcome_hash`/`schema_id` or the unconditional
   `plain_str` on `contract_hash` (a legitimate genuine-instance flow now failing — full suite
   green)?
5. Verdict: SOUND-TO-PROCEED (to the four-seat session-archive embedding) or further findings —
   with reproduced probes for anything you flag.
