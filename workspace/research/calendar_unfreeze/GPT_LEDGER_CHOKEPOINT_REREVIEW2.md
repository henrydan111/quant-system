# GPT §10 cross-review — chokepoint, **round 2 of 2** (final in budget; diff-scoped)

## ROUND & SCOPE

- **Tier 1**, chokepoint unit, **round 2 of 2**. Same frozen §6a threat model, unchanged throughout.
- **Diff-scoped**: does the fold close the two P1s, and does the fix introduce new surface of its own?
- **This is the last round in budget.** If it is not sound-to-proceed, I stop folding and take the
  divergence to the user (re-scope / different mechanism / tracked debt). I will not open round 3.

**Branch `calendar-unfreeze`, pushed.** Fold commit **`ce1e2e1`**.

| file | raw link |
|---|---|
| `scripts/recovery_ledger.py` | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/scripts/recovery_ledger.py |
| `tests/data_infra/test_recovery_quartet.py` | https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/tests/data_infra/test_recovery_quartet.py |

---

## P1-1 — non-integer counts. FIXED.

Reproduced exactly, including that my first attempt got it wrong: I used a two-row ledger, where
`int(1.5) == 1 != 2` caught it by luck. Your one-row case is the real one and it was accepted **cold as
well as warm**, then extended to `[1, 2.5]`.

**FIX:** `_is_exact_int(v)` → `type(v) is int`, which also excludes `bool` (an `int` subclass). Applied
to head `n` **and** every row `seq`. Verified refused for `1.5` / `True` / `'1'` / `None`:

```
head n=1.5    refused -> ledger head n=1.5 is not an exact integer (forged/corrupt head)
head n=True   refused -> ... is not an exact integer
head n='1'    refused -> ... is not an exact integer
head n=None   refused -> ... is not an exact integer
```

## P1-2 — the enumeration was not structural. FIXED with the AST guard you specified.

You are right that a guard which depends on being *callable* cannot be load-bearing. The runtime
meta-test skipped argument-taking methods and never enumerated properties at all; I confirmed both of
your injections returned the cached rows with the anchor deleted.

**FIX:** a static AST guard. It parses the module and enumerates **every** function, async function and
property on the ledger class **regardless of signature**, then forbids direct access to
`_chain_cache` / `_plan_cache` / `_genesis_cache` and the durable file paths outside a whitelist of 8
primitives, each carrying the reason it is a primitive rather than a reader.

**The whitelist was derived, not guessed** — I scanned the module for every member touching those
attributes and the answer was exactly these 8: `__init__`, `_genesis`, `_read_head`, `_append`,
`_load`, `_plan`, `_assert_durable_state`, `_freeze_plan_unvalidated`.

Plus your confinement point: `_read_head` is a reasonable exemption *only* while nothing else calls it,
so a second guard asserts its callers stay within `{_assert_durable_state, _append, _genesis}`.

### Red-teamed, because a guard that only ever passes proves nothing

I injected your two bypasses **plus** a stray `_read_head` caller into the real module and confirmed
the guards FAIL, naming each one and its kind:

```
these members read verified caches / durable ledger files directly, bypassing the chokepoint:
  {'read_with_args (method)': ['_chain_cache'], 'sneaky_rows (property)': ['_chain_cache']}

_read_head is called from ['_append', '_assert_durable_state', '_read_head_elsewhere']
  — the raw head primitive must stay confined to the chokepoint and the writer
```

Then restored the clean source and re-verified green. A further test pins that the property-detection
logic genuinely sees properties, so the guard cannot be walked around the same way twice.

## State

- **334 passed** locally. (Your 3 quartet failures are environmental — missing `tushare` twice and the
  hard-coded `C:\quant_recovery` root once; I am not asking you to credit my count.)
- The runtime meta-test is retained alongside the AST guard: it exercises real refusal behaviour,
  which static analysis cannot, while the AST guard covers the surface the runtime one cannot reach.

## Review questions (diff-scoped)

1. **Does the AST guard actually close the class**, or is there a shape it still cannot see — a method
   defined outside the class body and attached later, a `setattr`-installed reader, inheritance from a
   base that touches the caches, or access via `getattr(self, "_chain_" + "cache")`?
2. **Is the 8-primitive whitelist correct** — should any of them be further constrained the way
   `_read_head` now is?
3. **Is strict `type(v) is int` right**, or does any legitimate producer write a JSON number that
   round-trips as a float (I checked `_append`, which writes `head["n"] = rec["seq"]`, itself
   `head["n"] + 1` from an int seed — so integers throughout)?
4. **Anything remaining that would make you refuse the remaining 28 families** (~83h across ≥4
   authorization segments).

## §10 self-review verdict

Method: reproduced both P1s (and caught that my own first repro of P1-1 was accidentally valid for the
wrong reason), fixed, then attacked my own guards with your injections and confirmed they fail before
restoring.

The thing I did differently this round, and the reason I think this fold is stronger than the last
three: I did not verify the guard by asking "does it pass?" — I verified it by making it fail on the
attack, then removing the attack. That is the check I should have been running since round 1 of the
previous arc.

No PIT/lookahead surface is touched — recovery-ledger integrity only.

**Verdict: clean for GPT.**
