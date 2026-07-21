# GPT Cross-Review Request — NF Final-Integration Unit 1 RE-REVIEW #14 (archive boundary, verify-then-consume snapshot + NewsLegOutcome consume re-verify)

You are re-reviewing the **decision-archive boundary** of the news-flash (NF) seat. Your
previous verdict (on `0d3ddff`) found **1 P0 + 1 P1**, the verify-then-consume TOCTOU tail of the
`__dict__`-injection class. Folded. **Commit under review: `e0a1dcb`** on branch
`calendar-unfreeze`.

⚠ Branch-head note: a concurrent (unrelated) incident-recovery session has since committed
`b8a2b6c` on top of `e0a1dcb` — it touches only incident files; the NF files under review are
byte-identical at `e0a1dcb` and `b8a2b6c`. The raw links below track the branch head; pin your
read to `e0a1dcb` (raw form: replace `calendar-unfreeze` with `e0a1dcb` in the URLs if you want
the exact snapshot).

Your findings, verbatim intent:
- **P0**: `require_sealed_registry()` validated the LIVE `records` mapping but returned the SAME
  object for downstream consumption. A mapping injected via `__dict__` that returns different
  content by call-phase passed `execute → seal → reload` with `binding_eligible=True`, while the
  factor LLM actually received the restricted `[NFR01] 传闻未证实` risk content. The static key
  swap (re-review#13) was fixed; the residue was the missing independent snapshot at the consume
  boundary.
- **P1**: `NewsLegOutcome` still lacked consume-time field-type re-verification (only
  `outcome_hash` was hardened). Injecting a `str` subclass into `output_mode` passed
  `verify_execution_bundle()` and the archive write, but the disk archive stored `vector_only`,
  then failed to reload while write-once blocked the correct re-seal.

## Files (embedded text authoritative; links for live cross-check — pin to `e0a1dcb`)

- https://raw.githubusercontent.com/henrydan111/quant-system/e0a1dcb/workspace/research/ai_research_dept/engine/news_evidence.py
- https://raw.githubusercontent.com/henrydan111/quant-system/e0a1dcb/workspace/research/ai_research_dept/engine/news_legs.py
- https://raw.githubusercontent.com/henrydan111/quant-system/e0a1dcb/workspace/research/ai_research_dept/engine/news_cards.py
- https://raw.githubusercontent.com/henrydan111/quant-system/e0a1dcb/workspace/research/ai_research_dept/engine/news_decision.py
- https://raw.githubusercontent.com/henrydan111/quant-system/e0a1dcb/workspace/research/ai_research_dept/engine/news_executors.py
- https://raw.githubusercontent.com/henrydan111/quant-system/e0a1dcb/workspace/research/ai_research_dept/engine/news_seal.py
- https://raw.githubusercontent.com/henrydan111/quant-system/e0a1dcb/workspace/research/ai_research_dept/tests/test_news_archive.py

## How P0 was folded — independent frozen snapshot at the consume boundary

`require_sealed_registry` no longer verifies the live object and returns it. It now RECONSTRUCTS
a fresh `SealedCardRegistry(cutoff_iso=registry.cutoff_iso, records=registry.records,
registry_hash=registry.registry_hash)`. That constructor's `__post_init__` reads the
possibly-`__dict__`-injected live mapping **exactly once** (`list(self.records.items())`),
rebuilds each value into an independent `CardRecord` via `normalize_card_record`, freezes to a
`MappingProxyType`, and `verify_sealed`s the frozen content (the `(key, verified_hash)` pairs
with `key == record.record_id`) against `registry_hash`. `require_sealed_registry` then runs
`_verify_d7_relationships` on the frozen snapshot and returns THAT. Every caller
(`verify_d7_artifact` src/fin, `leg_expected_ids`, `penalty_eligible_records`,
`build_factor_payload_ids`, `verify_bundle_registry`) already reassigns to the returned value, so
all downstream reads the frozen snapshot — a phase-shifting mapping cannot show verify one
content and consume another. `verify_d7_artifact` reads `artifact.{source,final}_registry.
registry_hash` (a str, hardened) only to bind the artifact hash; every records access goes
through the fresh `src`/`fin`.

## How P1 was folded — NewsLegOutcome consume-time field re-verify

`assert_base_outcome_fields(outcome)` (every str field `type(x) is str`; the three bools exact
`bool`; `penalty_eligible_count` exact `int`; `penalty_payload_hash` `str`/`None`) is now called
at the top of `verify_outcome_for_binding` (the consume boundary that `verify_execution_bundle`
and the archive seal/load run through), so a post-construction `str`-subclass `output_mode` (or
any injected field) is refused before any hash is trusted.

## Regressions pinned

- `test_phase_shifting_registry_mapping_refused`: a mapping whose `items()` returns legit content
  on the first (snapshot) read and mutated content later — `require_sealed_registry` returns a
  frozen `MappingProxyType` snapshot (not the live object), stable across reads.
- `test_injected_outcome_output_mode_subclass_refused`: a `str`-subclass `output_mode` injected
  into `outcome.__dict__` is refused at `verify_outcome_for_binding` (`output_mode 须恰 str`).
- `test_injected_outcome_hash_int_refused_at_verify`: updated to assert the earlier consume-time
  base-type refusal.

## Self-review (completed before this request)

Verdict: **clean for GPT**. Verify-then-consume sweep: `require_sealed_registry` is the only
consume boundary that previously returned the caller's live sealed object and re-read its mutable
attribute multiple times; it now returns an independent frozen snapshot read exactly once. Every
other consume boundary reads scalar fields (now exact-base-type-asserted at consume) or
already-frozen snapshots. `NewsLegOutcome` is the last sealed archive object that lacked a
consume-time field re-verify; it now has one. Full suite: 798 green (NF 697 + ai_layer 50 +
text/harness 51). This self-review does NOT substitute for your gate — every prior round I
believed the surface clean and you found the next instance deeper; disclosed for you to check.

## Review questions

1. Is the verify-then-consume class now closed — is `require_sealed_registry` the only boundary
   that returned/re-read a live untrusted object, or is there another consume path that verifies
   one snapshot and consumes another (an artifact/card/bundle/payload attribute read twice across
   a phase-shift)?
2. Does the fresh-snapshot reconstruction read the untrusted live mapping EXACTLY once, with no
   residual read of `registry.records` after the snapshot (I believe `__post_init__` freezes
   before its own `verify_sealed`, and `require_sealed_registry` then uses only `fresh.records`)?
3. Is `assert_base_outcome_fields` at `verify_outcome_for_binding` sufficient for the P1, or is
   there an outcome field / consume path (the archive seal, the load rebuild) that reads an
   injected field before this assert runs?
4. Any regression from the reconstruction (identity-comparison, caching, or performance
   assumptions that expected `require_sealed_registry` to return the same object) — the full
   suite is green; do you see a caller that relied on object identity?
5. Verdict: SOUND-TO-PROCEED (to the four-seat session-archive embedding) or further findings —
   with reproduced probes for anything you flag.
