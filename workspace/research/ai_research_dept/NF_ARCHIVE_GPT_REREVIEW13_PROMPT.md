# GPT Cross-Review Request — NF Final-Integration Unit 1 RE-REVIEW #13 (archive boundary, key-binding + consume-time base-type + hardened verify_sealed)

You are re-reviewing the **decision-archive boundary** of the news-flash (NF) seat. Your
previous verdict (on `adf451a`) found **2 P0 + 2 P1**, all the same `__dict__`-injection class
deeper: construction-time coercion is not durable, so consume boundaries must re-verify — and
one binding was not hash-covered at all. Folded. **Commit under review: `0d3ddff`** on branch
`calendar-unfreeze` (raw links track the branch head).

Your findings, verbatim intent:
- **P0**: the registry sealed only the VALUE hash set, not the key→`record.record_id` binding.
  Swapping two keys in `final_registry.__dict__["records"]` left `registry_hash` unchanged but
  `get(NFD01)` returned NFR01's risk content into the factor payload.
- **P0**: `RenderedCard.factor_payload_text` had no consume-time exact-base-type check — a str
  subclass whose `str()` returns the sealed text but `.splitlines()` is forged kept `card_hash`
  valid while the forged text reached the factor LLM; `plain_str()` passing non-str through was
  a root cause.
- **P1**: `outcome_hash`'s exact-type check ran only at construction; a post-construction int
  subclass made the archive write `outcome_hash: 0`, then load silently recomputed while
  write-once blocked the correct re-seal.
- **P1**: `contract_hash` had no runtime exact-type / re-verify; a post-construction injection
  wrote `contract_hash: 0`, unreadable by the normal contract, blocking the correct re-seal.

## Files (embedded text authoritative; links for live cross-check)

- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_seal.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_evidence.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_cards.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_legs.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_executors.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_decision.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/tests/test_news_archive.py

## How the findings were folded

**P0 registry key binding** — `registry_canonical_payload` and `build_card_registry` now seal
sorted `(key, verified_record_content_hash)` PAIRS (was: value hashes only) and enforce
`key == record.record_id` at every compose/verify. A swapped `__dict__["records"]` key is
refused (`键 ≠ record_id`).

**P0 consume-time exact-base-type** — added `assert_base_card_fields` / `assert_base_fact_fields`
/ `assert_base_row_fields` / `assert_base_bundle_fields` / `assert_base_artifact_fields` (every
str field `type(x) is str`; every hash/id tuple a plain tuple of plain str; `importance` exact
int) and wired them into `verify_d7_artifact` (card / bundle / artifact + each base_fact / row)
and `verify_payload_for_execution` (SealedPayload), BEFORE any hash is trusted. The existing
CardRecord `assert_base_record_fields` (re-review#12) covers the registry leaf. So every sealed
object that enters the archive is exact-base-type-verified at its consume boundary, not just at
construction.

**P1 the single global choke point** — `verify_sealed` now REJECTS a `claimed_hash` that is not
an exact `str` of 64 lowercase hex, before the `!=` compare. An int/str subclass with an evil
`__ne__` can no longer slip a fake hash past ANY seal verification — this closes the whole
injected-hash family at one function.

**P1 outcome_hash / contract_hash** — `NewsLegOutcome.outcome_hash`'s exact-type gate moved
BEFORE the truthy branch (an injected `int 0` is falsy and used to skip the check and silently
recompute — now `type(x) is not str` raises first). `require_exact_contract` re-verifies the
contract's fields + self-hash via the hardened `verify_sealed` at every consume (construction
coercion alone was undone by a post-construction `contract.__dict__` injection).

## Regressions pinned (your four)

- `test_registry_key_record_id_swap_refused`: swap two keys in
  `final_registry.__dict__["records"]` → `require_sealed_registry` refuses (`键`/`record_id`).
- `test_card_text_splitlines_injection_refused`: a str-subclass `factor_payload_text` (real
  `str()`, forged `.splitlines()`) → `verify_d7_artifact` refuses (`factor_payload_text 须恰
  str`).
- `test_injected_outcome_hash_int_refused_at_verify`: an int-subclass `outcome_hash` injected
  post-construction → refused at the binding boundary (`SealError`).
- `test_injected_contract_hash_int_refused_at_consume`: an int-subclass `contract_hash` injected
  post-construction → `require_exact_contract` refuses (`SealError`).

## Self-review (completed before this request)

Verdict: **clean for GPT**. Consume-boundary sweep: every sealed object reaching the archive
(CardRecord, SealedCardRegistry incl. its key binding, RenderedCard, D7BaseFact, AttributeRow,
AttributeBundle, D7DecisionArtifact, SealedPayload, NewsScoringContract, NewsLegOutcome) now has
its fields re-verified as exact base types at the consume boundary that precedes any hash trust
or membership read, not only at construction. All hash comparisons flow through the hardened
`verify_sealed` (exact str + 64-hex). I confirmed each attack is refused with the four
regressions. Full suite: 796 green (NF 695 + ai_layer 50 + text/harness 51). This self-review
does NOT substitute for your gate — every prior round I believed the surface clean and you found
the next instance deeper; disclosed for you to check, not trust.

## Review questions

1. Is the `__dict__`-injection class now closed at CONSUME time across the whole archive surface
   — can you still inject a field (str/tuple/int subclass, aliased container, swapped mapping
   key) that a consume boundary trusts before re-verifying its exact base type?
2. Is the registry key↔record_id binding complete — besides the top-level key swap, can a D7
   child key, a duplicate, or a mapping with extra/missing keys still desync key from
   record_id or from the D7 relationship checks?
3. Is the hardened `verify_sealed` (exact str + 64-hex) safe for every caller (no legitimate
   caller passes a non-64-hex or empty claimed_hash to it — the `if self.x_hash:` guards
   compute-vs-verify, and the full suite is green)?
4. Are there consume paths that read a sealed object's field BEFORE the new assert runs (e.g.
   a helper that trusts `card.factor_payload_text` / `sp.payload_text` without going through
   `verify_d7_artifact` / `verify_payload_for_execution` first)?
5. Verdict: SOUND-TO-PROCEED (to the four-seat session-archive embedding) or further findings —
   with reproduced probes for anything you flag.
