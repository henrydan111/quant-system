# GPT Cross-Review Request — NF Final-Integration Unit 1 RE-REVIEW #24 (bound independent copies; snapshot before callback)

You are re-reviewing the **decision-archive boundary** of the news-flash (NF) seat, round 24,
**against the FROZEN, user-approved threat model** (do not expand scope; classify each concern
in-scope vs out-of-scope and reach a scope-bounded verdict).

## Frozen threat model (review AGAINST this — authoritative)

Full text (pinned): https://raw.githubusercontent.com/henrydan111/quant-system/fe99286/workspace/research/ai_research_dept/NF_ARCHIVE_THREAT_MODEL.md

- **Trusted:** the process; engine source modules and their **class objects**; runtime/builtins;
  sha256; lock/chain/write-once machinery; on-disk bytes at rest.
- **Untrusted:** the in-process caller's **arguments** and every object reachable through them —
  crafted **instances** (dict/list/str subclasses with stateful `.items()`/`__iter__`/`__eq__`/
  `__getattribute__`, metaclass `__eq__`, `object.__setattr__` mutation during a callback the
  boundary triggers).
- **Five IN-SCOPE classes:** (1) hash/field decoupling; (2) callback-time mutation; (3) rejection-
  path callback; (4) phase-substitution; (5) pre-type-gate read. Acceptance = static reject **or**
  seal-from-reconstructed-state the caller cannot reference, proven by a fail-pre-fix regression that
  asserts the hook never fires.
- **OUT-OF-SCOPE (recorded, does NOT gate):** code-edit-equivalent capability (monkeypatch, replace
  `verify_sealed`/`json.dumps`/builtins, **class-level** dunder reassignment on an engine dataclass);
  on-disk tamper; cross-process race; sha256 break; DoS.

**Convergence rule:** a finding gates iff it demonstrates one of the five classes with a crafted
**instance** needing none of the out-of-scope capabilities.

## Commit under review

**`7df0d60`** on branch `calendar-unfreeze`. Your previous verdict (on `c515831`) was **REVISE — 2
P1**, both in-scope: (P1#1) `verify_d7_artifact` returned the **live** artifact, so a registry
`.items()` callback could `object.__setattr__`-swap the verified `artifact.bundle`/card/rows and the
consumers' post-verify reads used the poisoned live fields; the verified-but-live contract/outcome
could likewise have a field swapped to a hooked object. (P1#2) recovery iterated `artifact.rows`
before the artifact type gate. Both folded at `7df0d60`.

## Files (embedded text authoritative; links pin to `7df0d60`)

- https://raw.githubusercontent.com/henrydan111/quant-system/7df0d60/workspace/research/ai_research_dept/engine/news_cards.py
- https://raw.githubusercontent.com/henrydan111/quant-system/7df0d60/workspace/research/ai_research_dept/engine/news_archive.py
- https://raw.githubusercontent.com/henrydan111/quant-system/7df0d60/workspace/research/ai_research_dept/engine/news_legs.py
- https://raw.githubusercontent.com/henrydan111/quant-system/7df0d60/workspace/research/ai_research_dept/engine/news_executors.py
- https://raw.githubusercontent.com/henrydan111/quant-system/7df0d60/workspace/research/ai_research_dept/engine/news_decision.py
- https://raw.githubusercontent.com/henrydan111/quant-system/7df0d60/workspace/research/ai_research_dept/tests/test_news_archive.py

## How the two P1s were folded

**P1#1 (classes 2+4) — return + bind independent copies; snapshot before callback.**
`verify_d7_artifact` now RETURNS a fresh `D7DecisionArtifact` built from the already-verified locals
(`card`/`base_facts`/`src`/`rows`/`bundle`/`fin` + the captured `v_artifact_hash`); the caller holds
no reference to any returned component, and `__post_init__` re-verifies the self-hash. **Every
consumer binds the return value** — `record_decision`, `require_recorded`, `run_news_two_legs`,
`verify_outcome_for_binding`, `commit_execution`, `verify_execution_bundle`,
`_load_and_verify_archive_file`, `recover_and_seal_success_archive` (grep: no unbound
`verify_d7_artifact(artifact)` call remains outside the return statement). Two new module-level
helpers `snapshot_exact_contract` / `snapshot_exact_outcome` (in `news_executors.py` /
`news_legs.py`) verify + rebuild an independent frozen `NewsScoringContract` / `NewsLegOutcome`
BEFORE any callback point; each boundary binds the snapshot and never reads the live object again.
`verify_execution_bundle`'s `verified_outcome` now reuses the entry snapshot instead of re-reading
the live outcome.

**P1#2 (class 5) — verify+snapshot before iteration.** `recover_and_seal_success_archive` now
`snapshot_exact_contract` + `artifact = verify_d7_artifact(artifact)` at entry, so the exact-`tuple`
gate on `artifact.rows` refuses a list-subclass BEFORE `build_leg_payload_ast` iterates. `commit_execution`
gains a `decision_id` exact-`str` gate before the `==`.

## Regressions pinned (crafted instance only; each fails on pre-fix code; hook asserted never to fire)

- `test_registry_callback_bundle_swap_invisible_to_seal_and_load`: a source-registry `.items()`
  swaps `artifact.bundle` to an `_EvilBundle` (accessors return the real values); seal succeeds on
  the genuine hash, the archive is loadable, and the evil accessors are never invoked.
- `test_registry_callback_contract_field_swap_invisible`: `.items()` swaps `contract.output_mode` to
  an object with `__repr__`/`__eq__` hooks; seal succeeds on the frozen snapshot, hooks never fire.
- `test_registry_callback_outcome_field_swap_invisible`: `.items()` swaps `outcome.penalty_leg_status`
  to a `__eq__`-hooked object; seal succeeds, hook never fires.
- `test_recover_rejects_subclass_rows_before_iteration`: a list-subclass `rows` is refused at the
  exact-tuple gate; `__iter__` never runs.

## Self-review (completed before this request)

Verdict: **clean for GPT**. Grep confirms all eight `verify_d7_artifact` call sites bind the return
(only the return statement and a comment remain unbound). After each `artifact = verify_d7_artifact
(artifact)`, every downstream read is of the returned copy — the registry callback can only mutate
the discarded live original. contract/outcome are snapshotted before the first callback point
(`verify_d7_artifact` / `require_sealed_registry`). No §3 (CLAUDE.md) data/PIT/execution invariant is
touched — the NF engine is orthogonal to the six research modules. Tests: ai_research_dept 716 green
+ data_infra news 17 green. This self-review does NOT substitute for your gate.

## Review questions (within the frozen scope)

1. **Classes 1–5, crafted instance:** with `verify_d7_artifact` returning a bound copy and
   contract/outcome snapshotted before the first callback, is there any remaining consumer that reads
   a live caller object after its verification, or any pre-type-gate read/iteration? Reproduce with an
   instance-only probe if so.
2. Are the returned copy and the two snapshots faithful and complete (all fields rebuilt, self-hash
   re-verified), with no field silently dropped or aliased back to the caller?
3. Is the snapshot ORDER correct at every boundary — is the snapshot taken strictly before the first
   callback point (`require_sealed_registry` via `verify_d7_artifact`) at each of the six public
   entries?
4. **Scope classification:** for any concern, state IN-SCOPE (crafted instance, one of the five
   classes) vs OUT-OF-SCOPE (class-level dunder / monkeypatch / on-disk tamper / race / collision /
   DoS). Out-of-scope concerns are recorded, not folded.
5. **Verdict:** SOUND-TO-PROCEED (all in-scope classes closed → proceed to the four-seat session-
   archive embedding), or REVISE with a specific in-scope gap. If the only remaining concerns are
   out-of-scope per the frozen model, the correct verdict is SOUND-TO-PROCEED with those listed as
   out-of-scope notes.
