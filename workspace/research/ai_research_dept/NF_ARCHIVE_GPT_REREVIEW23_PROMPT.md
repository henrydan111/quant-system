# GPT Cross-Review Request — NF Final-Integration Unit 1 RE-REVIEW #23 (archive boundary, reviewed AGAINST a now-frozen threat model)

You are re-reviewing the **decision-archive boundary** of the news-flash (NF) seat. This arc is at
round 23. Per our convergence discipline (CLAUDE.md §10), the threat model is now **FROZEN and
user-approved**, and your review must be conducted **against that fixed spec** — not against an
open-ended adversarial standard. The point of this round is to reach a scope-bounded verdict.

## Frozen threat model (review AGAINST this — embedded text is authoritative)

Full text (pinned): https://raw.githubusercontent.com/henrydan111/quant-system/fe99286/workspace/research/ai_research_dept/NF_ARCHIVE_THREAT_MODEL.md

- **Trusted:** the OS process; the engine source modules and their **class objects**; the Python
  runtime/builtins; sha256; the file-lock + hash-chain + write-once machinery (own invariants, not
  this arc); on-disk ledger/archive bytes at rest.
- **Untrusted:** the **in-process caller's arguments** to the boundary functions — `bundle`,
  `artifact`, `contract`, `registry`, `records`, `bundle_eval`, `chain`, `decision_id`,
  `execution_id`, and every object reachable through them. A caller may pass crafted **instances**:
  subclasses of `dict`/`list`/`str` with stateful `.items()`/`__iter__`/`__getitem__`/`__eq__`/
  `__ne__`, instances with overridden `__getattribute__`/`__repr__`/`__str__`, metaclass `__eq__`,
  and objects mutated via `object.__setattr__` during a callback the boundary triggers.
- **Five IN-SCOPE failure classes** (must be closed): (1) hash/field decoupling (forgery);
  (2) callback-time mutation (TOCTOU-via-callback); (3) rejection-path callback; (4) phase-
  substitution; (5) pre-type-gate read. Acceptance per class = STATIC reject **or** seal-from-
  reconstructed-state that the caller holds no live reference to, proven by a regression that fails
  pre-fix and asserts the hook never fires.
- **OUT-OF-SCOPE (recorded, does NOT gate):** code-edit-equivalent capability — monkeypatching
  engine functions, replacing `verify_sealed`/`json.dumps`/builtins, or reassigning an engine
  frozen-dataclass's **class-level** dunder (`D7BaseFact.__eq__ = …`); on-disk tampering
  (hash-chain/write-once's job); cross-process races (file_lock's job); sha256 breaks; DoS.

**Convergence rule:** a finding GATES iff it demonstrates one of the five in-scope classes with an
input that needs none of the out-of-scope capabilities (i.e. a crafted **instance**, not a class-
level/source mutation). A finding that requires an out-of-scope capability is recorded as
out-of-scope and does **not** block SOUND-TO-PROCEED.

## Commit under review

**`c515831`** on branch `calendar-unfreeze`. Your previous verdict (on `8efb05d`) was **REVISE — 2
P1**, both in-scope: (1) artifact pre-check bypassed by phase-substitution during the registry
snapshot; (2) load/recover read artifact/contract/decision_id before the type gate. Both folded at
`c515831`.

## Files (embedded text authoritative; code links pin to `c515831`)

- https://raw.githubusercontent.com/henrydan111/quant-system/c515831/workspace/research/ai_research_dept/engine/news_cards.py
- https://raw.githubusercontent.com/henrydan111/quant-system/c515831/workspace/research/ai_research_dept/engine/news_archive.py
- https://raw.githubusercontent.com/henrydan111/quant-system/c515831/workspace/research/ai_research_dept/engine/news_evidence.py
- https://raw.githubusercontent.com/henrydan111/quant-system/c515831/workspace/research/ai_research_dept/tests/test_news_archive.py

## How the two P1s were folded

**P1 phase-substitution (class 4).** `verify_d7_artifact` now, BEFORE the `require_sealed_registry`
callbacks: exact-types + field-asserts artifact/card/bundle; captures `v_artifact_hash`;
RECONSTRUCTS `card`, `bundle`, every `base_fact`, and every `row` into fresh independent dataclass
copies (the caller holds no reference to them; each `__post_init__` re-verifies its self-hash). Then
`require_sealed_registry(source)`/`(final)` return fresh frozen registries (`src`/`fin`). AFTER the
callback, the root hash is built from the copies + `src`/`fin` (not `artifact_canonical_payload
(artifact)`), and the ENTIRE rebuild runs on the copies — no live `artifact.*` is read after the
callback. A `.items()` swap now hits only the discarded live artifact (invisible); a swapped
registry is caught by the hash bindings.

**P1 pre-type-gate read (class 5).** `_load_and_verify_archive_file` now requires exact-`str`
`decision_id`/`execution_id`, runs `require_exact_contract` + `verify_d7_artifact`, and captures the
validated hashes (`v_contract_hash`, `v_contract_payload`, `v_artifact_hash`, `v_bundle_hash`,
`v_final_registry_hash`, `v_bundle_decision_id`) BEFORE reading the archive; the identity comparisons
then use only those captured base values (archive fields are plain disk JSON).
`load_and_verify_decision_archive` and `recover_and_seal_success_archive` reject a non-`str`
`decision_id` before `_find_success_commitment`.

## Regressions pinned (each fails on pre-fix code)

- `test_registry_items_callback_cannot_swap_verified_base_facts` (class 4): a source-registry mapping
  whose `.items()` swaps `artifact.base_facts` to a side-effecting `EvilFact` does not poison
  `verify_d7_artifact`, and the `EvilFact.fact_hash` accessor is NEVER read.
- `test_load_rejects_nonstr_decision_id_before_compare` (class 5): a non-`str` `decision_id` is
  refused at load before any `__eq__` runs.

## Self-review (completed before this request)

Verdict: **clean for GPT**. Live-artifact-read sweep of `verify_d7_artifact`: after the reconstruction
+ registry snapshot, every read is of the copies (`card`/`bundle`/`base_facts`/`rows`) or the fresh
`src`/`fin`; grep confirms no `artifact.base_facts`/`artifact.rows` read after the callback. Load
path: IDs exact-str-gated, contract/artifact validated + captured before comparison. Full suite: 813
green (NF 712 + ai_layer 50 + text/harness 51). This self-review does NOT substitute for your gate.

## Review questions (answer within the frozen scope)

1. **In-scope classes 1–5:** does the code at `c515831` close all five for crafted-**instance**
   inputs? If you find a gap, name the class, give a reproduced probe using only an instance (no
   §out-of-scope capability), and confirm it fails on the current code.
2. Are the reconstructed copies in `verify_d7_artifact` faithful and complete, with no residual live
   `artifact.*` read after the registry callback?
3. Is the load capture-before-compare complete — all identity comparisons on captured base values —
   and is `verify_d7_artifact` the right pre-read validation?
4. **Scope classification:** for any concern you have, state explicitly whether it is IN-SCOPE (a
   crafted instance triggering one of the five classes) or OUT-OF-SCOPE (needs class-level dunder
   reassignment / monkeypatching / on-disk tamper / race / collision / DoS). Out-of-scope concerns
   are recorded, not folded.
5. **Verdict:** SOUND-TO-PROCEED (all in-scope classes closed → proceed to the four-seat
   session-archive embedding), or REVISE with the specific in-scope gap. If your only remaining
   concerns are out-of-scope per the frozen model, the correct verdict is SOUND-TO-PROCEED with those
   concerns listed as out-of-scope notes.
