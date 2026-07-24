# GPT Re-review #3 — NF integration P4b — Tier-2 — FINAL round (open sweep)

Round **3 of 3** (the unit's §10 budget). Final pre-SHIP round = full-unit open sweep. If your verdict
is not SOUND-TO-PROCEED, I stop folding and take the divergence to the user (re-scope / switch
mechanism / tracked debt) rather than opening a round 4. **Tier stays Tier-2**; the v3 archive
model's scope rule applies (findings hold the root set fixed; no crafted-object analysis).

**Fold commit: `ad752fd`** (you reviewed `318bd92`). Verdict folded: **REVISE, 1 P1** — zero declines.
Same invariant class two consecutive rounds (a committed execution stranded without its audit
archive: round 1 sequential, round 2 cross-task) → per §10 the fold is **structural**, exactly your
prescription.

## Your P1 → the structural fold

> The backfill uses a one-shot snapshot. Task A snapshots; task B commits `hard_failed` after the
> snapshot and crashes before seal; A succeeds without seeing B — and since A succeeded, nothing
> naturally re-enters to backfill B. Fix: a cross-process per-decision lock covering the whole
> record → enumerate/backfill → success-check → execute → seal flow; a trailing rescan is not enough.

Implemented as `_decision_flow_lock` in
[news_flash_decide.py](https://raw.githubusercontent.com/henrydan111/quant-system/ad752fd/workspace/research/ai_research_dept/engine/news_flash_decide.py):

- **Atomic-mkdir spin lock** — the house pattern (`_ledger_lock` / `_prov_lock`), lock dir
  `.nf_decision_flow_{sha256(decision_id)[:16]}.lock` under the **ledger root** (the decision's
  authority root). Distinct decisions do not serialize.
- **The ENTIRE write-bearing flow is inside the lock**: record → commitment enumeration/backfill →
  success check → execute (both LLM legs) → seal → return. The read-only prelude (evidence
  resolution + P3b assemble) stays outside — it writes nothing.
- **Why this closes the class**: driver flows for one decision are fully serialized, so any
  commitment either precedes this task's snapshot (backfilled now) or its whole flow runs after ours
  (and backfills itself on entry). There is no "after my snapshot, before my return" window left.
- `lock_timeout` default **600s** (must exceed a competing flow's two LLM legs); a stale
  crash-leftover lock blocks successors until timeout then **fails closed** (operator clears it —
  the same semantics as the ledger/provenance locks).
- **Scope, stated**: the lock guards DRIVER flows only. A caller invoking the engine APIs directly
  bypasses driver guarantees — as before P4b existed; the driver is the orchestration unit, and the
  production entry (FORWARD_PREREG governed runner) will route through it.

## Regressions

[test_news_flash_decide.py](https://raw.githubusercontent.com/henrydan111/quant-system/ad752fd/workspace/research/ai_research_dept/tests/test_news_flash_decide.py)
(12 tests):

- `test_two_task_barrier_A_backfills_B_before_succeeding` — your barrier verbatim: B holds the flow
  lock mid-flow; A's `decide_stock` is asserted BLOCKED; B records + commits `hard_failed` and
  crashes (lock released, archive missing); A proceeds and returns success — with B's archive
  **already backfilled and by-execution verifiable** (`news_status=hard_failed`).
- `test_stale_flow_lock_fails_closed` — the crash-leftover-lock timeout path.
- Honest note: the barrier test exercises the new lock helper, so it is not an apples-to-apples
  pre-fix probe — the class's pre-fix acceptance is your own reproduction at `318bd92`. (Round 2's
  two sequential-backfill regressions remain and were fail-pre-fix verified by stashing.)

Full `ai_research_dept` suite **884** green. Your two probe dirs (`.codex_review_p4b_r2_*`) were
already policy-blocked from your side — I removed them from the working tree.

## Files (pin to `ad752fd`)

- https://raw.githubusercontent.com/henrydan111/quant-system/ad752fd/workspace/research/ai_research_dept/engine/news_flash_decide.py
- https://raw.githubusercontent.com/henrydan111/quant-system/ad752fd/workspace/research/ai_research_dept/engine/news_archive.py (round-2 diff, unchanged this round — context)
- https://raw.githubusercontent.com/henrydan111/quant-system/ad752fd/workspace/research/ai_research_dept/engine/news_decision.py (context)
- https://raw.githubusercontent.com/henrydan111/quant-system/ad752fd/workspace/research/ai_research_dept/tests/test_news_flash_decide.py

## Open-sweep questions (final round)

1. **Does the lock close the cross-task class?** Any interleaving of driver flows — including
   crash-at-any-point inside the lock, lock-timeout races, or a flow that dies between mkdir and its
   first write — that still strands a committed execution without a verifiable archive, or double
   -executes a success?
2. **The lock's own surface**: mkdir-spin fairness/timeout semantics; the stale-lock fail-closed
   trade-off (liveness vs safety — worth a tracked note?); the read-only prelude outside the lock
   (assemble/proof race against a concurrent flow's writes — the record door re-proves inside the
   lock, is that sufficient?).
3. **Anything in the whole unit** (identity, committed-evidence sourcing, backfill, resume matrix,
   hard_failed retry, identities-only return) the prior rounds' narrower focus let through.
4. **Verdict:** SOUND-TO-PROCEED (to C1) or specific in-tier findings.
