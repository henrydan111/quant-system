# GPT Re-review #2 — NF integration P4b (DIFF-SCOPED) — Tier-2

Round 2 of 3. Per CLAUDE.md §10, diff-scoped: does the fold close the invariant it claims, and does
the fix introduce new surface? **Tier stays Tier-2** (the v3 archive model's scope rule applies to
the `news_archive.py` part of the diff: findings hold the root set fixed; no crafted-object
analysis).

**Fold commit: `318bd92`** (you reviewed `7f34551`). Verdict folded: **REVISE, 1 P1** — zero declines.

## Your P1, restated

> A `hard_failed` commitment whose process dies before `seal_decision_archive` loses its
> per-execution audit archive forever: the driver only looks for success commitments, and the
> recovery function explicitly supports success only. Re-entry starts a fresh execution while the old
> one's commitment + provenance rows point at an archive that can never exist — violating the
> driver's own "each execution keeps its own immutable audit archive".

Accepted in full; folded exactly along your prescription ("按 (decision_id, execution_id) 从磁盘重建
并封档;重入时先补封…即使之后已有 success,也应补齐旧失败审计档案").

## The fold — three pieces

1. **`news_archive.recover_and_seal_execution_archive(decision_id, execution_id, ...)`** — the
   recovery core, generalized from the success-only function. Deltas from the old body:
   - commitment located by `(decision_id, execution_id)` (`_find_commitment`), not the unique success;
   - leg statuses **re-derived from the resolved terminal verdicts** via two explicit registries
     (`valid|deterministic_zero→success`, `invalid|call_error→failed`, `empty_penalty→empty_success`;
     unregistered verdict → refuse); `penalty_entry_hash is None → not_run`, with the old
     "success commitment lacking a penalty terminal is illegal" refusal preserved;
   - records are `None` on failed/`not_run` legs and `evaluation` is `None` off-success —
     byte-matching `verify_execution_bundle`'s own failed-leg semantics (it refuses a sealed record
     on a failed leg), so the rebuilt bundle is exactly what the joint verifier demands;
   - the payload rebuild: factor always; penalty iff the penalty leg actually ran
     (`success`/`failed`) — mirroring what the live execution built;
   - the **`outcome_hash` anchor is unchanged**: the rebuilt outcome must equal the commitment's,
     which pins every derived status transitively. Everything else (contract byte-check, P4a
     assembly-from-ledger, write-once-conflict loser-reads-winner) is byte-identical to the old body.
   - **`recover_and_seal_success_archive` is now a thin wrapper** — locate the unique success
     commitment, delegate. All pre-existing recovery tests pass unchanged through the delegation.
2. **`news_decision.list_execution_commitments`** — chain-ordered reader, `require_exact_id` gate
   (the id-gate meta-test shape).
3. **The driver backfills FIRST**: on every re-entry, every committed execution whose archive is
   missing — success or hard_failed — is recovered from pure disk BEFORE any resume or fresh retry;
   the success-resume branch then simply loads (its archive is guaranteed by the backfill).

## Verification — genuinely fail-pre-fix this round

Public signatures did not change, so I stashed the engine diff and ran the two new regressions
against `7f34551`: **2 failed pre-fix** (`load_and_verify_execution_archive` → 档案缺失), all pass
post-fix. The probes:

- `test_unsealed_hard_failed_commitment_is_backfilled_on_reentry` — your reproduction verbatim:
  hard_failed committed, crash before seal, re-enter with a good LLM → success sealed AND the old
  execution loads/verifies **by execution** (`news_status=hard_failed`, `evaluation=None`, schema v2);
- `test_backfill_also_runs_when_success_already_exists` — your explicit ask: an unsealed hard_failed
  AND an unsealed success both backfilled in one re-entry, each verifiable.

10 P4b tests + archive/meta files 102 + full `ai_research_dept` **882** green. Your two probe dirs
(`.codex_review_p4b_*`) removed from the working tree.

## Files (pin to `318bd92`)

- https://raw.githubusercontent.com/henrydan111/quant-system/318bd92/workspace/research/ai_research_dept/engine/news_flash_decide.py
- https://raw.githubusercontent.com/henrydan111/quant-system/318bd92/workspace/research/ai_research_dept/engine/news_archive.py
- https://raw.githubusercontent.com/henrydan111/quant-system/318bd92/workspace/research/ai_research_dept/engine/news_decision.py
- https://raw.githubusercontent.com/henrydan111/quant-system/318bd92/workspace/research/ai_research_dept/tests/test_news_flash_decide.py

## The two diff-scoped questions

1. **Does the fold close the class?** The re-entry matrix now: fresh / success-sealed /
   success-committed-unsealed / hard_failed-committed-unsealed / hard_failed-sealed /
   mixed-history / nothing-routed. Any cell that still strands a committed execution without a
   verifiable archive — or any state the backfill itself can produce that a later re-entry cannot
   resolve?
2. **Does the fix create new surface?** Specifically: the verdict→status registries (any legal
   live-execution outcome the rebuild cannot reproduce, or an illegal one it now accepts — note the
   `outcome_hash` anchor must also pass); the `not_run` branch's success-refusal; the wrapper
   delegation; and the driver's backfill-before-resume ordering (a backfill failure now blocks the
   retry — intended fail-closed, flag if you see a liveness concern worth recording).

Verdict: SOUND-TO-PROCEED (to C1) or specific in-tier findings.
