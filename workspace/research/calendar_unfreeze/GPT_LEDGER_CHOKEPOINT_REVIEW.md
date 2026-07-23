# GPT §10 cross-review — the ledger durable-state CHOKEPOINT (structural fold)

## ROUND & SCOPE — read this first, it changes what I am asking for

- **Tier 1**, same frozen §6a threat model (unchanged throughout; no re-scoping at any point).
- This is **NOT round 4 of the previous arc.** That arc spent its 3-round budget, the user arbitrated,
  and the chosen option was *"switch to a structural mechanism"*. Per the convergence protocol, the
  next review **judges the chokepoint, not the sites** — so the scope below is deliberately narrow.
- **Round 1 of 2** on this new unit. Budget 2 rounds, then user arbitration again.

### What I am asking you to judge

1. **Is the gate itself sound** — does `_assert_durable_state` re-establish every durable guarantee a
   caller could otherwise be served without?
2. **Is the mechanical enumeration real** — can a NEW reader be added that serves verified state
   without failing the meta-test?

### What is explicitly OUT of scope this round

The individual call sites, the per-site history (r1/r2/r3 findings), and the performance work — all
previously reviewed and closed. If you find something there, please classify it as out-of-scope debt
rather than gating this round on it.

**Branch `calendar-unfreeze`, pushed.** Chokepoint commit **`8b666b8`**.

| file | raw link |
|---|---|
| `scripts/recovery_ledger.py` | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/recovery_ledger.py |
| `tests/data_infra/test_recovery_quartet.py` | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/tests/data_infra/test_recovery_quartet.py |
| §6a threat model | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/calendar_unfreeze/ADAPTER_PHASE_DESIGN.md |

---

## Why a chokepoint instead of a fourth patch

Three consecutive rounds gated on **one invariant class** — a cached value handed back without
re-establishing the guard that made it trustworthy:

| round | how it got out |
|---|---|
| r1 | the cache was published **before** the head check, so a truncation refused once then served from cache |
| r2 | `_DetachedPlanView` deep-copied on access but carried the live cache on `._rows` |
| r3 | `_genesis()` returned its cached anchor **without checking the anchor file still existed** |

Each was patched at its own site; the class reappeared one door down. Your round-3 reproductions
(same-process anchor deletion accepted; head `n` rewound to 0 accepted, producing sequences
`[1, 2, 3, 1]`) were both confirmed here before any change.

## The gate

`_assert_durable_state(rows, tail_hash)` — called immediately before returning verified state, on the
fresh-replay path and the warm-cache path alike. It re-establishes **all** the durable guarantees
rather than the one that happened to fail last:

1. the persisted anchor still **exists**, still names **this run**, and still holds the **cached value**;
2. head `record_hash` == chain tail;
3. head **`n` == len(rows)** *(new — checking only the hash let a rewound head through)*;
4. **seq continuity 1..n** *(new — this is what `[1,2,3,1]` violated)*.

`_genesis()` additionally no longer short-circuits past the file's existence on a cache hit.

Verified **warm and cold** for six corruption shapes — anchor deleted / content swapped / naming
another run; head hash rewound / count rewound / count inflated — all refuse in both cache states.

## The mechanical enumeration (the half that makes it structural)

`test_every_public_state_reader_goes_through_the_chokepoint` reflects over the ledger class's public
surface, deletes the anchor under a warm process, and asserts every zero-arg reader refuses.
**Default-deny**: a newly added reader FAILS until it is either wired to the gate or added to a small
exemption list **with a reason**.

It earned its keep immediately — it flagged two methods I had not considered:
- `_read_head` — a primitive **input** to the gate; routing it through would recurse;
- `execution_guard` — returns a lock context manager, serves no verified state.

Both are exempted explicitly with justification, plus an assertion that every exemption still names a
live method so the list cannot rot into a dumping ground.

## Known limit of the enumeration, stated rather than hidden

It can only *call* methods whose parameters all have defaults; anything requiring arguments is skipped
(`skipped` in the test). So a future reader that **takes arguments** and serves cached state would not
be caught. I did not solve that, and it is the first thing I would attack. Question 2 below is
specifically about this.

## Independent evidence

- 343 recovery tests pass locally.
- The gate then ran under a **real 6.73h live fetch**: 13,479/13,479 requests verified, 0 failed, and
  consolidation produced 4,493 partitions / **14,821,292 rows — an exact match to the pre-incident
  baseline** (4,493 files / 14,821,292 rows). Per-date density verified against the trading calendar:
  4,493 open sessions → 4,493 partitions, 0 missing, 0 extra, 0 zero-row.
- Orchestration overhead 0.19 s/request; the gate re-reads two small files per call.

## Review questions

1. **Does the gate close the class, or only relocate it again?** That is the question I have now
   answered wrongly three times. Please attack the gate itself: is there a way to obtain verified
   ledger or plan state without passing through `_assert_durable_state`?
2. **Is the meta-test's enumeration sound enough to be load-bearing**, given the
   defaults-only limitation above? If not, what is the cheapest form that covers argument-taking
   readers — I considered requiring every such method to route through a single internal accessor and
   asserting *that* by AST, which is heavier but does not depend on being callable.
3. **Are the two exemptions correct**, or is `_read_head` reachable in a way that matters (it is the
   only reader of the head file, and the gate consumes its result)?
4. **Anything about the gate that would make you refuse the remaining 28 families** (~83h of live
   fetching across ≥4 authorization segments).

## §10 self-review verdict

Method: reproduced both round-3 findings first, built the gate, verified six corruption shapes warm and
cold, and let the mechanical enumeration find bypasses I had not enumerated myself (it found two).

I want to be plain about the standard I am asking you to hold this to. Three times I answered this
invariant class with a mechanism that carried the problem forward, and once I asserted a fix I had not
written. The gate is the first answer that is structural rather than another instance, and the
meta-test is the first thing in this arc that can catch a bypass I did not think of. But "I could not
find a way around my own gate" is exactly the evidence that has failed three times running, which is
why question 1 is the whole review.

No PIT/lookahead surface is touched — recovery-ledger integrity only.

**Verdict: clean for GPT.**
