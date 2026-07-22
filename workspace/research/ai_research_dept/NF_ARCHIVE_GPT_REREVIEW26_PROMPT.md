# GPT Cross-Review Request — NF Final-Integration Unit 1 RE-REVIEW #26 (structural fold: one fail-closed chokepoint + AST meta-tests)

You are re-reviewing the **decision-archive boundary** of the news-flash (NF) seat **against the
FROZEN, user-approved threat model**. Classify every concern in-scope vs out-of-scope and return a
scope-bounded verdict.

**Commit under review: `8fed4eb`** on branch `calendar-unfreeze`.

## Round budget — please read

Per our convergence protocol, a review unit gets **3 implementation re-review rounds against its
frozen threat model**; this is round 3 (#24, #25, #26). Classes 3 and 5 gated in both #24 and #25, so
#25 was folded **structurally** rather than per-site, as the protocol requires. If your verdict here
is again a same-class REVISE, the protocol hands the decision to the user (re-scope the model / swap
the mechanism / accept as tracked debt) rather than continuing to fold. So please be explicit about
whether any finding is (a) a *new* class, (b) *the same class through a door the chokepoint does not
cover*, or (c) a site the mechanical guard should have caught but didn't — (c) especially, since the
guard is the thing that is supposed to make the class impossible by construction.

## Frozen threat model (review AGAINST this — authoritative)

Full text (pinned): https://raw.githubusercontent.com/henrydan111/quant-system/fe99286/workspace/research/ai_research_dept/NF_ARCHIVE_THREAT_MODEL.md

- **Trusted:** the process; engine source modules and their **class objects**; runtime/builtins;
  sha256; lock/chain/write-once machinery; on-disk bytes at rest.
- **Untrusted:** the in-process caller's **arguments** and everything reachable through them —
  crafted **instances** (dict/list/str subclasses with stateful `.items()`/`__iter__`/`__eq__`/
  `__hash__`/`__str__`/`__getattribute__`, metaclass `__eq__`, `object.__setattr__` during a callback).
- **Five IN-SCOPE classes:** (1) hash/field decoupling; (2) callback-time mutation; (3) rejection-path
  callback; (4) phase-substitution; (5) pre-type-gate read. Acceptance = reject with **no caller code
  run** *or* seal-from-reconstructed-state, proven by a fail-pre-fix regression.
- **OUT-OF-SCOPE (recorded, does NOT gate):** code-edit-equivalent capability (monkeypatch, replacing
  `verify_sealed`/`json.dumps`/builtins, **class-level** dunder reassignment); on-disk tamper;
  cross-process race; sha256 break; DoS.

## Files (embedded text authoritative; links pin to `8fed4eb`)

- https://raw.githubusercontent.com/henrydan111/quant-system/8fed4eb/workspace/research/ai_research_dept/engine/news_seal.py
- https://raw.githubusercontent.com/henrydan111/quant-system/8fed4eb/workspace/research/ai_research_dept/engine/news_evidence.py
- https://raw.githubusercontent.com/henrydan111/quant-system/8fed4eb/workspace/research/ai_research_dept/engine/news_cards.py
- https://raw.githubusercontent.com/henrydan111/quant-system/8fed4eb/workspace/research/ai_research_dept/engine/news_archive.py
- https://raw.githubusercontent.com/henrydan111/quant-system/8fed4eb/workspace/research/ai_research_dept/tests/test_news_engine_invariants.py

## How the two P1s were folded — **structurally**

**P1#1 (class 3) — one all-`is` scalar test.** `type(x) in (bool,int,float)` expands to
`type(x) == bool or …`; a lying metaclass answers with its own `__eq__`, which both lets an arbitrary
object impersonate a plain scalar and *is* caller code on the rejection path (you measured `__eq__`×2,
`__hash__`×1, `__repr__`×1). New single primitive:

```python
_PLAIN_SCALARS = (bool, int, float, str)

def is_plain_scalar(x, *, allow_str: bool = True) -> bool:
    t = type(x)
    for cls in _PLAIN_SCALARS:
        if t is cls:                       # `is` identity — metaclass __eq__ cannot intervene
            return allow_str or cls is not str
    return False
```

Both `news_evidence` sites now route through it.

**P1#2 (class 5) — delete the fork; one FAIL-CLOSED chokepoint.** Root cause: `news_evidence` carried
its **own** `_plain_str` whose fallback was `str(x)` — that ran an untrusted object's `__str__` at a
snapshot boundary *and* returned whatever it produced, so an object whose `__str__` returns a str
**subclass** left `SealedCardRegistry.cutoff_iso` not-exactly-`str` while `verify_d7_artifact` still
succeeded. The fork is **deleted**; `news_seal.plain_str` is the single normalizer and is now
fail-closed:

```python
def plain_str(x) -> str:
    if type(x) is str:
        return x
    if isinstance(x, str):                 # subclass → builtin flatten, no caller code
        return str.__str__(x)
    raise SealError("须恰 str(…绝不 str() 强转…;静态错误)")
```

`SealedCardRegistry.__post_init__` additionally applies a static `isinstance` gate to `cutoff_iso`,
`registry_hash`, and every records key **before** any normalization.

## The mechanical guard (this is the part to attack)

`tests/test_news_engine_invariants.py` AST-scans **all 8 NF security modules** and fails on the banned
shapes, so a newly added function cannot reintroduce either class:

1. no `type(...)` compared with `==` / `!=` / `in` / `not in` (must be `is` / `is not`);
2. no bare `str(x)` call in a security module (whitelist: the `sys.path` bootstrap only).

**Guard #2 immediately caught TEN more sites of the same class that per-site patching had missed** —
including `news_seal.canon`'s dict-key `str(k)` and its non-str fallback, **both on the HASH path**,
feeding an untrusted `__str__` result straight into the seal hash; plus 5 in `news_cards`' render
paths and 3 diagnostic messages. All closed. `canon`'s fallback is now str-only and its
whitespace-folding behavior is unchanged — hashes identical, full suite green before and after.

## Regressions pinned

Your two probes: a lying metaclass cannot impersonate a scalar (hook count 0); the registry snapshot
refuses an object whose `__str__` returns a str subclass (`__str__` never called). **6 of the 7 new
tests were verified to FAIL on the pre-fix engine** (the 7th pins `canon`'s unchanged str path and is
correctly green on both).

## Self-review (completed before this request)

Verdict: **clean for GPT**. Both named sites closed; the fork is gone (one normalizer, one semantic);
the two AST guards enumerate the module surface rather than sampling it. `canon` was tightened as the
same class on the hash path and empirically shown hash-neutral. Known deliberate non-change:
`canon` still accepts `pd.Timestamp`-like objects via `hasattr(v, "to_pydatetime")` (an attribute
probe that can run `__getattr__`) — it is reached only with payloads built by our own
canonical-payload helpers from exact-typed fields; **please rule explicitly on whether that is
in-scope**, rather than leaving it for a later round. Tests: ai_research_dept **723** green +
data_infra news 17 green. This self-review does NOT substitute for your gate.

## Review questions (within the frozen scope)

1. **Is the chokepoint sound?** `plain_str` fail-closed + `is_plain_scalar` all-`is` — can a crafted
   instance still get a non-exact-`str` value into a sealed snapshot, or run code on a rejection path,
   through either primitive?
2. **Is the guard's coverage honest?** Do the two AST rules actually make classes 3/5 impossible to
   reintroduce in these 8 modules, or is there a third shape of the same class the scan does not
   express (name it precisely — that is more valuable than another instance)?
3. `canon`'s `hasattr(v, "to_pydatetime")` probe: IN-SCOPE or OUT-OF-SCOPE under the frozen model?
4. **Scope classification** for every concern: IN-SCOPE (crafted instance, one of the five classes) vs
   OUT-OF-SCOPE. And for in-scope ones, is it a *new class*, *the same class past the chokepoint*, or
   *a site the guard should have caught*?
5. **Verdict:** SOUND-TO-PROCEED (proceed to the four-seat session-archive embedding), or REVISE with a
   specific in-scope gap **reproduced against `8fed4eb`**. If the only remaining concerns are
   out-of-scope, the correct verdict is SOUND-TO-PROCEED with those listed as notes.
