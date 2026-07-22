# GPT §10 cross-review — ledger genesis/caching, **round 3 of 3** (final; full sweep)

## ROUND & SCOPE

- **Tier 1**, **round 3 of 3**, same frozen §6a threat model (unchanged; no re-scoping at any point).
- Per the convergence protocol, round 3 is the **final pre-SHIP round and gets a full open sweep**
  (rounds 2 was diff-scoped).
- **This is the last round in budget.** If it is not SHIP / sound-to-proceed, I stop folding and take
  the divergence to the user with three options: re-scope the model, switch to a structural mechanism,
  or accept the residual as tracked debt. I will not open round 4 on my own authority.

**Branch `calendar-unfreeze`, pushed.** Fold commit **`0bf74f5`**.

| file | raw link |
|---|---|
| `scripts/recovery_ledger.py` | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/recovery_ledger.py |
| `tests/data_infra/test_recovery_quartet.py` | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/tests/data_infra/test_recovery_quartet.py |
| §6a threat model | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/calendar_unfreeze/ADAPTER_PHASE_DESIGN.md |

---

## Both findings confirmed and folded

### P0-3 — the fix WAS the bypass

You walked straight through `_DetachedPlanView._rows`. Reproduced with a real signed A01 row before
changing anything: the next `_plan()` returned `20990101` while the signed JSON still read `20080102`.
The wrapper I introduced to close the exploit carried the live mutable cache one attribute access away.

It was also the 100× scan regression you measured — and my 40-request benchmark never touched it,
because `cmd_fetch`'s 59 whole-plan scans happen outside the per-request loop I was timing.

**FIX: the wrapper is deleted.** The plan cache is deep-frozen and returned directly. Nothing mutable
to reach, nothing to copy, no wrapper surface at all. A consumer that needs a mutable row writes
`dict(row)` — explicit and local.

```
whole-plan items() scan   1.364 s (your measurement, wrapper)  ->  8.0 ms
59 scans in cmd_fetch     ~80 s                                ->  0.47 s
_plan() cached                                                     ~0 ms
```

### The genesis re-mint claim — **this one was my error, not a code defect**

You are right and I want to be unambiguous about it: I asserted in the round-1 commit message *and* in
the round-2 review prompt that a missing anchor is no longer re-minted once run state exists. **The
code did no such thing.** My round-0 probe passed only because it combined anchor deletion *with*
identity drift, so a chain break masked the re-mint; deleting the anchor alone, under the same
identity, reproduces the old value and the run carries on with a silently re-established baseline.

I verified your reproduction before fixing, and it is now implemented and pinned: `_genesis()` refuses
to mint when the ledger, head or frozen plan exists, and the regression asserts the anchor is **not**
recreated after the refusal.

### Supporting change you will see in the diff

`_canon` now serialises `MappingProxyType`, so a frozen row hashes **identically** to the plain dict it
was frozen from. Without it, freezing would have silently shifted every downstream digest — 53 tests
failed in exactly that way, which is how it surfaced. Pinned by a test asserting `_canon`/`_h` agree
between frozen and plain input.

## Your accepted-as-correct items, unchanged

Validate-then-publish (all 16 `_append` callers hold the lock; fsync → publish head → advance cache);
the 500-hit / 300-second bounded-staleness budget; `items()`/`values()` detaching and `keys()` being
safe. I have not touched any of them.

## State

- **329 passed** locally. Noted: you measured 272 passed / 16 environment failures because `tushare` is
  absent and one test uses the hard-coded `C:\quant_recovery` root. That gap is environmental, and I am
  not asking you to credit my number — the substantive claims above each have their own reproduction.
- Orchestration overhead **0.19 s/request** end to end (6.4 s/request as originally measured live).
  `market/daily` 12.3h, full set 95.3h.

## Review questions (full sweep, final round)

1. **Is the mutable-cache class now closed rather than relocated?** That is twice I answered it with a
   mechanism that carried the problem forward. Please check the class across every reader of cached
   state, not the two I fixed.
2. **Does deep-freezing the plan break any consumer** you can see in `recovery_adapters.py` /
   `raw_recovery_coordinator.py` that I have not noticed? The suite is green, but the suite also
   passed before your round-2 finding.
3. **Is `_canon(MappingProxyType) == _canon(dict)` sufficient**, or does the freeze reach any other
   serialization/digest path (receipts, dispatch-token specs, consolidation verdicts)?
4. **Anything remaining that would make you refuse a 4-day live run.**

## §10 self-review verdict

Method: reproduced both findings first, fixed, re-verified, then re-measured the performance claim on
the path you identified rather than the one I had been timing.

The pattern I have to name, because it is now three rounds running and it is the same shape each time:
round 0 cached an object that was not what the reader returns; round 1 wrapped the cache in a view that
still exposed it; and in between I asserted a fix I had not written. The first two are "a cheaper thing
standing in for the real thing". The third is worse and simpler — I did not verify my own claim before
publishing it, in a review prompt whose entire purpose is to let you check my work. Question 1 is me
asking you to assume I have done it a third time.

**Verdict: clean for GPT.**
