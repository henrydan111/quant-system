# GPT Cross-Review Request — NF Final-Integration Unit 1 RE-REVIEW #25 (class-wide safe render; bundle key sweep)

You are re-reviewing the **decision-archive boundary** of the news-flash (NF) seat, round 25,
**against the FROZEN, user-approved threat model**. Classify each concern in-scope vs out-of-scope
and reach a scope-bounded verdict.

⚠ **Read the commit under review carefully:** your last verdict was produced against `7df0d60`. Both
P1s from it are folded at **`4b14542`**, which is what you are reviewing now.

## Frozen threat model (review AGAINST this — authoritative)

Full text (pinned): https://raw.githubusercontent.com/henrydan111/quant-system/fe99286/workspace/research/ai_research_dept/NF_ARCHIVE_THREAT_MODEL.md

- **Trusted:** the process; engine source modules and their **class objects**; runtime/builtins;
  sha256; lock/chain/write-once machinery; on-disk bytes at rest.
- **Untrusted:** the in-process caller's **arguments** and everything reachable through them —
  crafted **instances** (dict/list/str subclasses with stateful `.items()`/`__iter__`/`__eq__`/
  `__hash__`/`__getattribute__`, metaclass `__eq__`, `object.__setattr__` during a callback).
- **Five IN-SCOPE classes:** (1) hash/field decoupling; (2) callback-time mutation; (3) rejection-path
  callback; (4) phase-substitution; (5) pre-type-gate read. Acceptance = reject with **no caller code
  run** *or* seal-from-reconstructed-state, proven by a fail-pre-fix regression asserting the hook
  never fires.
- **OUT-OF-SCOPE (recorded, does NOT gate):** code-edit-equivalent capability (monkeypatch, replacing
  `verify_sealed`/`json.dumps`/builtins, **class-level** dunder reassignment); on-disk tamper;
  cross-process race; sha256 break; DoS.

**Convergence rule:** a finding gates iff it demonstrates one of the five classes with a crafted
**instance** needing none of the out-of-scope capabilities.

## Commit under review

**`4b14542`** on branch `calendar-unfreeze`.

## Files (embedded text authoritative; links pin to `4b14542`)

- https://raw.githubusercontent.com/henrydan111/quant-system/4b14542/workspace/research/ai_research_dept/engine/news_seal.py
- https://raw.githubusercontent.com/henrydan111/quant-system/4b14542/workspace/research/ai_research_dept/engine/news_archive.py
- https://raw.githubusercontent.com/henrydan111/quant-system/4b14542/workspace/research/ai_research_dept/engine/news_decision.py
- https://raw.githubusercontent.com/henrydan111/quant-system/4b14542/workspace/research/ai_research_dept/engine/news_legs.py
- https://raw.githubusercontent.com/henrydan111/quant-system/4b14542/workspace/research/ai_research_dept/engine/news_cards.py
- https://raw.githubusercontent.com/henrydan111/quant-system/4b14542/workspace/research/ai_research_dept/engine/news_evidence.py
- https://raw.githubusercontent.com/henrydan111/quant-system/4b14542/workspace/research/ai_research_dept/engine/news_executors.py
- https://raw.githubusercontent.com/henrydan111/quant-system/4b14542/workspace/research/ai_research_dept/engine/news_horizon.py
- https://raw.githubusercontent.com/henrydan111/quant-system/4b14542/workspace/research/ai_research_dept/tests/test_news_archive.py

## How the two P1s were folded — **by invariant class, repo-wide**

**P1#1 (class 3 — rejection path runs caller code).** Root cause named as a class: `{x!r}` calls the
untrusted object's `__repr__` and `type(x).__name__` calls its metaclass `__getattribute__`; at a
**type gate** — where we reject `x` precisely because its type is not trusted — both necessarily fire
on the untrusted object. Rather than patch the four sites you reproduced, two shared primitives were
added in `news_seal.py`:

```python
def safe_kind(x) -> str:          # builtin type() + `is` identity + literal return
    if x is None: return "None"
    t = type(x)
    for cls, name in _PLAIN_KINDS:          # bool/int/float/str/list/dict/tuple
        if t is cls: return name
    return "<非纯值>"

def safe_repr(x) -> str:          # builtin repr ONLY for exactly-plain scalars
    if x is None or type(x) is bool or type(x) is int or type(x) is float \
            or type(x) is str:
        return repr(x)
    return f"<{safe_kind(x)}>"
```

Both are zero-caller-code by construction: only the builtin `type()`, `is` identity comparisons
against builtin type objects, and literal returns. For any untrusted object (including a `str`
subclass) `safe_repr` returns a literal placeholder — it never reaches `repr`. **Note on your
"应统一改为静态错误信息":** these are not literally static strings, but they satisfy the acceptance
criterion in substance (no caller code on the rejection path) while staying diagnostic for genuine
plain-value errors. Please confirm the primitive itself is sound, or say why a fully-static message
is required.

Every type/membership gate on a caller-supplied value was then swept across `news_decision`,
`news_legs`, `news_cards`, `news_evidence`, `news_executors`, `news_horizon`. Several gates also
gained the missing exact-`str` check that had made the membership test reachable with a subclass
(e.g. `type(domain) is not str or domain not in DOMAINS`). `news_horizon._safe_repr` — which called
`repr()` on arbitrary objects and read `type(v).__name__` on its fallback — now delegates to the
shared primitive.

**P1#2 (class 5 — pre-type-gate read).** Two holes closed:
- `require_recorded` had **no** `decision_id` gate at all: it verified the artifact and then took the
  untrusted id into ledger lookup and `==` against disk strings (a `str` subclass's `__eq__` ran).
  An exact-`str` non-empty gate now runs at entry, before `verify_d7_artifact`.
- `verify_execution_bundle` read `bundle["outcome"]` before any key check. An **exact** dict may still
  carry a non-`str` key whose `__hash__` collides with `hash("outcome")`; the builtin lookup then
  probes past it and calls that key's `__eq__`. A key sweep now runs **before the first
  `bundle[...]`/`bundle.get(...)`**: `for k in bundle: if type(k) is not str: raise` — exact dict's
  `__iter__` is builtin and yields keys without calling their `__hash__`/`__eq__`.

## Regressions pinned (crafted instance only; **both verified to FAIL on the pre-fix engine**)

- `test_bundle_colliding_key_eq_never_runs`: an `_EvilKey` with `__hash__ == hash("outcome")` and
  `__eq__` returning **False** (so it is a *distinct* key in the same bucket, which is what forces the
  lookup to probe past it). Pre-fix: **DID NOT RAISE — the poisoned bundle actually sealed an
  archive**. Post-fix: refused at the key sweep, `__eq__` call count 0, no archive file written.
- `test_type_gate_rejections_run_no_caller_code`: an `_EvilStr(str, metaclass=_LoudMeta)` counting
  `__name__` / `__repr__` / `__eq__` is passed to `record_decision`, `require_recorded`,
  `run_news_two_legs(output_mode=…)`, `verify_outcome_for_binding(expected_output_mode=…)`. Pre-fix:
  **DID NOT RAISE** (require_recorded had no gate). Post-fix: all four raise, total hook count 0.

## Self-review (completed before this request)

Verdict: **clean for GPT**. All five sites you named verified closed by grep
(`news_decision:210` record_decision, `news_decision:348-352` require_recorded entry gate,
`news_legs:297/300` run_news_two_legs, `news_legs:387` verify_outcome_for_binding,
`news_archive:299` bundle key sweep). The class-wide sweep covers six modules, not just those five.
Fail-pre-fix was verified by stashing the engine changes and re-running the two regressions. No §3
(CLAUDE.md) data/PIT/execution invariant is touched — the NF engine is orthogonal to the six research
modules. Tests: ai_research_dept **718** green + data_infra news 17 green. This self-review does NOT
substitute for your gate.

## Review questions (within the frozen scope)

1. **Class 3, class-wide:** is `safe_repr`/`safe_kind` sound as the primitive (zero caller code for
   any untrusted instance), and is the sweep complete — any remaining type/membership gate in the six
   modules that still interpolates an untrusted value via `!r` or `type(x).__name__`?
2. **Class 5:** is the `bundle` key sweep correctly placed before every `bundle[...]`/`.get(...)`, and
   is `for k in bundle` genuinely free of caller code for an exact dict? Any other boundary entry that
   indexes a caller dict by literal key before sweeping, or compares an untrusted id before gating it?
3. Do the gates that gained an exact-`str` precondition change any legitimate behavior (a plain value
   that used to pass and now doesn't)?
4. **Scope classification:** for any concern, state IN-SCOPE (crafted instance, one of the five
   classes) vs OUT-OF-SCOPE. Out-of-scope concerns are recorded, not folded.
5. **Verdict:** SOUND-TO-PROCEED (all in-scope classes closed → proceed to the four-seat
   session-archive embedding), or REVISE with a specific in-scope gap **reproduced against `4b14542`**.
   If the only remaining concerns are out-of-scope per the frozen model, the correct verdict is
   SOUND-TO-PROCEED with those listed as notes.
