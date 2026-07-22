# GPT §10 cross-review — ledger genesis/caching, **round 2 of 3** (diff-scoped)

## ROUND & SCOPE

- **Tier 1**, **round 2 of 3** against the SAME frozen threat model (§6a, unchanged — no re-scoping).
- Per the convergence protocol this round is **diff-scoped**: does the fold close the classes it
  claims, and does the fix introduce new surface of its own? The next full open sweep is the final
  pre-SHIP round.
- If round 3 is not SHIP I stop folding and take the divergence to the user.

**Branch `calendar-unfreeze`, pushed.** Fold commit **`f4fcd82`**.

| file | raw link |
|---|---|
| `scripts/recovery_ledger.py` | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/recovery_ledger.py |
| `tests/data_infra/test_recovery_quartet.py` | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/tests/data_infra/test_recovery_quartet.py |
| §6a threat model | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/calendar_unfreeze/ADAPTER_PHASE_DESIGN.md |

**All four findings were real, in scope, and I reproduced every one before touching code.** My own
round-0 self-review probes had missed all of them, and the reason is worth stating: they tested that
the guards FIRE, not that a caller can walk around them.

---

## P0-1 — truncation accepted on the retry. FIXED.

Reproduced exactly as described:

```
call 1: refused -> ledger head does not match the chain tail (truncat...
call 2: *** LOADED 4 rows from the truncated ledger ***
```

Cause was ordering: the full replay published `_chain_cache` *before* `_assert_head`. **FIX:** validate
head, then publish. And per your instruction the external anchors are re-checked on **every warm hit**
— they are what makes truncation visible and they cost two stats. Regression asserts three consecutive
attempts all refuse, not just the first.

## P0-2 — a deleted ledger certified as a pristine run. FIXED.

Reproduced: head file present, `_load()` → `[]`, warm and cold. **FIX:** refuse when the ledger is
absent but durable run state (head / genesis anchor / frozen plan) survives. A separate regression pins
that a genuinely fresh run — nothing on disk — still loads empty, so the refusal cannot swallow the
legitimate case.

## P0-3 — verified caches handed out live. FIXED. (the one with a working exploit)

Reproduced end to end with a real signed plan row: after mutating what `_plan()` returned, the cached
plan said `20990101` while the signed file on disk still said `20080102`; `_plan() is _plan()` was
`True`; and a mutation of a `_load()` row persisted into the next `_load()`.

**FIX, split by what each consumer actually needs:**
- `_load()` returns a **deep-frozen** view (dict → `MappingProxyType`, list → tuple), applied on **both**
  the cold and warm paths so the two can never differ in type — that being precisely the failure I
  introduced in round 0.
- `_plan()` returns a `_DetachedPlanView` that deep-copies **the row actually accessed**. The plan's
  callers legitimately treat a row as a mutable dict, so freezing it in place would ripple through every
  consumer; copying one small row costs nothing against re-verifying 102 MB, and nothing a caller does
  to what it receives can reach the cache.

## P1 — the append budget was not a bound while idle. FIXED.

Reproduced: 3000 warm reads left `since_full` at 1. **FIX:** hit and wall-clock budgets as well
(`_FULL_REVERIFY_EVERY_HITS = 500`, `_FULL_REVERIFY_AFTER_SECONDS = 300`).

I have recorded your framing verbatim in the code rather than paraphrasing it away: `(size, mtime_ns)`
is a fast **invalidator**, not proof the bytes are unchanged, and immediate detection of arbitrary
metadata-preserving corruption requires re-reading content or a stronger authenticated version
mechanism. The budget is a bound on the window, not a detection mechanism, and it no longer claims
otherwise.

## Your non-blocking note, also folded

A missing genesis anchor is no longer re-minted once any ledger/head/plan state exists — it refuses
rather than silently establishing a new baseline.

---

## Did the fix cost the thing it was protecting? No.

```
orchestration overhead   0.21 s/request   (6.4 live before round 0; 0.26 after round 0)
market/daily 13,479 req  12.4h
full set    104,176 req  95.8h
```

## Test-expectation changes (declared, so you can judge them as changes rather than find them)

Two, both consequences of the deliberate freeze rather than breakage:
1. `ev["endpoint_scope"] == ["daily"]` → `list(ev["endpoint_scope"]) == ["daily"]`. Production reads
   this field as `set(...)`, and the on-disk JSON is unchanged.
2. My own round-0 test asserting "no tuple survives into the cached rows" now asserts what actually
   matters: warm and cold return the same type, and the result is not writable. The old assertion
   directly contradicted the P0-3 fix.

6 new regressions. Suite: **327 passed**.

## Review questions (diff-scoped)

1. **Does the fold close each class, or only the instances you named?** Specifically: are there other
   readers of cached state that hand out live references — I fixed `_load` and `_plan`, but I would
   rather you check the class than take my enumeration.
2. **Does `_DetachedPlanView` introduce new surface?** It is a `Mapping` whose `__getitem__`
   deep-copies. `keys()`/`items()`/`values()` come from the `Mapping` ABC and route through
   `__getitem__`, so I believe they are detached too — please check that reasoning rather than accept
   it.
3. **Is validate-then-publish now complete**, or is there another path that stores a cache before its
   guard runs (`_append` advances the cache after writing — is that ordering sound)?
4. **Is the hit/time budget the right shape** given you classified metadata-preserving corruption as
   in scope but not immediately detectable by this mechanism?

## §10 self-review verdict

Method: reproduced all four before fixing, re-ran each probe after, and re-benchmarked to confirm the
fold did not trade the performance win away.

The honest lesson from this round: my probes asked "does the guard fire?" and yours asked "can I get
around the guard?" — the second is the only question that matters for a cache in front of an integrity
check, and it is the one I did not ask. I have written the P0-3 regressions in that adversarial form
(mutate what you were handed, then assert the attested state is unchanged) rather than the
does-it-fire form.

**Verdict: clean for GPT.**
