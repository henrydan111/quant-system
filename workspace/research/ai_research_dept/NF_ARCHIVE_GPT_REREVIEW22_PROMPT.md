# GPT Cross-Review Request — NF Final-Integration Unit 1 RE-REVIEW #22 (archive boundary, static rejection errors + pre-checked artifact sub-components)

You are re-reviewing the **decision-archive boundary** of the news-flash (NF) seat. Your previous
verdict (on `7e51b5f`) was **REVISE — 2 P1**: (1) the rejection path still ran caller code by
formatting `type(x).__name__` / untrusted `repr` into the error; (2) artifact sub-objects were read
into the root hash before their exact-type gate. Folded. **Commit under review: `8efb05d`** on branch
`calendar-unfreeze`.

Your findings, verbatim intent:
- `news_archive.py:288/:297` and the contract/artifact/seal boundaries (and `verify_sealed`'s
  `repr`) formatted untrusted type names / reprs before raising; a metaclass `__getattribute__` /
  `__repr__` runs. Make these error messages static; never read an untrusted type name or value repr
  on a security-boundary rejection path.
- `artifact_canonical_payload()` reads `bf.fact_hash`, `r.row_hash`, `source_registry.registry_hash`,
  `final_registry.registry_hash`, but the element exact-type checks and `require_sealed_registry()`
  run afterward, so an injected object's accessor executes first (a frozen dataclass is mutable via
  `object.__setattr__`). Pre-check all sub-components (exact type + field validation + registry
  snapshot) first, then build the canonical payload / root hash from the validated locals.

## Files (embedded text authoritative; links pin to `8efb05d`)

- https://raw.githubusercontent.com/henrydan111/quant-system/8efb05d/workspace/research/ai_research_dept/engine/news_archive.py
- https://raw.githubusercontent.com/henrydan111/quant-system/8efb05d/workspace/research/ai_research_dept/engine/news_cards.py
- https://raw.githubusercontent.com/henrydan111/quant-system/8efb05d/workspace/research/ai_research_dept/engine/news_seal.py
- https://raw.githubusercontent.com/henrydan111/quant-system/8efb05d/workspace/research/ai_research_dept/engine/news_evidence.py
- https://raw.githubusercontent.com/henrydan111/quant-system/8efb05d/workspace/research/ai_research_dept/engine/news_legs.py
- https://raw.githubusercontent.com/henrydan111/quant-system/8efb05d/workspace/research/ai_research_dept/engine/news_executors.py
- https://raw.githubusercontent.com/henrydan111/quant-system/8efb05d/workspace/research/ai_research_dept/tests/test_news_archive.py

## How it was folded

**P1 static rejection errors.** Every boundary rejection on an untrusted object/value is now a STATIC
message with no interpolation of the untrusted value or its type. Swept across: `verify_execution_
bundle` (bundle/outcome/execution_id), `require_exact_contract`, `verify_sealed` (news_seal;
`field_name` is an internal constant so it stays), `require_sealed_registry` /
`verified_record_content_hash` / `normalize_card_record` / `assert_base_record_fields` /
`_plain_scalar` (news_evidence), `verify_outcome_for_binding` / `assert_base_outcome_fields` /
`NewsLegOutcome` exact-type / outcome_hash gate (news_legs), `require_exact_contract` /
`commit_execution` / schema_id gate (news_executors), `_require_record_bound` / `_archive_path` / the
load-path decision-identity and no-success-commitment errors (news_archive), the D7 exact-type gates
/ `_assert_str_fields` / importance gate (news_cards).

**P1 pre-check before root hash.** `verify_d7_artifact` now, in order: exact-types `artifact` /
`card` / `bundle` + `assert_base_*`; exact-types + field-asserts EVERY `base_fact` and `row`;
`require_sealed_registry(source)` and `(final)`; ONLY THEN `verify_sealed(artifact_canonical_payload
(artifact), …)` and the per-component canonical verifies. So every attribute the canonical payload
reads belongs to an already-exact-typed component; no injected accessor runs before its type gate.

## Regressions pinned

- `test_boundary_rejection_reads_no_untrusted_type_name`: a wrong-type outcome whose metaclass flags
  `__name__` access is refused with its `__name__` NEVER read.
- `test_artifact_subobject_accessor_not_run_before_typecheck`: an injected `base_fact` whose
  `fact_hash` is a side-effecting property is refused at the exact-type check before the accessor
  runs.

## Self-review (completed before this request)

Verdict: **clean for GPT**. Rejection-path sweep: grepped `type(...).__name__` and `{...!r}` across
the archive-path engine modules; every untrusted-value interpolation on a boundary rejection is now
static (remaining `!r`/`__name__` are on trusted/plain values — disk JSON, validated fields,
constants — or in the unrelated analyst_chain module). Read-before-type-gate sweep of
`verify_d7_artifact`: the only reads of sub-object attributes now follow the exact-type +
require_sealed_registry pre-checks. Full suite: 811 green (NF 710 + ai_layer 50 + text/harness 51).
This self-review does NOT substitute for your gate.

## Review questions

1. Is the rejection-path class closed — does any security-boundary error on the archive write path
   still interpolate an untrusted value's `repr`/`str`/`type().__name__` (or otherwise touch a caller
   object's magic method) before raising?
2. Is the `verify_d7_artifact` reorder complete — does `artifact_canonical_payload` (and the card /
   bundle / base_fact / row / registry canonical payloads) now read only attributes of components
   that were exact-type-checked and (for registries) snapshotted first, with no residual pre-gate
   read?
3. Are the remaining `!r`/`__name__` interpolations I judged "trusted" actually trusted (disk-loaded
   JSON, already-validated sealed fields, module constants), or did I miss an untrusted one?
4. Any regression from the reorder or the static messages (the full suite incl. normal/zero/
   hard-fail/recovery/load is green; error text lost the offending value but kept the invariant)?
5. Verdict: SOUND-TO-PROCEED (to the four-seat session-archive embedding) or further findings — with
   reproduced probes for anything you flag.
