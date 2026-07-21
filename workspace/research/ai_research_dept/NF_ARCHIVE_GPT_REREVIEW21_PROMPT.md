# GPT Cross-Review Request — NF Final-Integration Unit 1 RE-REVIEW #21 (archive boundary, identity type gate + chain snapshot)

You are re-reviewing the **decision-archive boundary** of the news-flash (NF) seat. Your previous
verdict (on `035e2e1`) was **REVISE — 2 P1**, both in the entry snapshot itself: (1) a liar-metaclass
bypass of `type(x) in (bool,int,float,str)` (equality, not identity); (2) the optional `chain` param
not snapshotted. Folded. **Commit under review: `7e51b5f`** on branch `calendar-unfreeze`.

Your findings, verbatim intent:
- `type(x) in (...)` uses `==`; a container whose metaclass overrides `__eq__` makes `type(x) == str`
  return True, passing an arbitrary container through as a scalar; its `.get()` then tampers the disk
  terminal after factor is verified. Use all-`is` identity checks; and do not read an untrusted
  type's `.__name__` in the error (it triggers a metaclass callback).
- `verify_execution_bundle` accepts and documents a caller `chain` snapshot; a list subclass's
  `__iter__` mutates verified records. Snapshot `chain` with the same recursive exact-type gate, or
  accept only a verified ledger snapshot / remove the injectable param.

## Files (embedded text authoritative; links pin to `7e51b5f`)

- https://raw.githubusercontent.com/henrydan111/quant-system/7e51b5f/workspace/research/ai_research_dept/engine/news_archive.py
- https://raw.githubusercontent.com/henrydan111/quant-system/7e51b5f/workspace/research/ai_research_dept/tests/test_news_archive.py

## How it was folded

- `_deep_plain_json` now uses an **all-`is` identity gate**: `t = type(x)`; `x is None or t is bool
  or t is int or t is float or t is str` → scalar; `t is list` → rebuild list; `t is dict` → rebuild
  dict; else refuse. `is` compares the type OBJECT's identity, which a metaclass `__eq__` cannot
  influence. The refusal message no longer reads `type(x).__name__` (no metaclass `__getattr__`
  callback). `bool` is matched before `int` by identity, so a bool is never mistaken for int.
- The optional `chain` is `_deep_plain_json`'d at entry when passed (recursive exact-type plain
  snapshot); `chain=None` still self-reads via `_read_chain` (which yields plain dicts). A `list`
  subclass is refused before its `__iter__` runs. (The load path passes `_read_chain` output, which
  is already plain, so the snapshot is idempotent for genuine callers and preserves the single-
  snapshot discipline from re-review#4.)

## Regressions pinned

- `test_liar_metaclass_container_refused_by_identity_check`: a `dict` subclass with a liar metaclass
  (`type(x) == str` True, `type(x) is str` False) is refused by the identity gate; neither its
  metaclass `__eq__` nor its `.get()` is ever called.
- `test_injected_chain_list_subclass_refused`: a `list`-subclass `chain` is refused at the entry
  snapshot; its `__iter__` is never called.

## Self-review (completed before this request)

Verdict: **clean for GPT**. Type-gate sweep: `_deep_plain_json` is the single caller-structure gate;
it now uses only identity (`is`) and `x is None` (identity) — no `==`/`in`/`__name__` on an untrusted
value. Injectable-caller-structure sweep of `verify_execution_bundle`'s signature: `bundle` (exact
dict + deep snapshot of its JSON parts), `artifact`/`contract` (sealed objects, exact-typed +
re-verified), `chain` (now snapshotted); `ledger_dir`/`prov_dir` are paths. No caller container/
metaclass code can run after entry. Full suite: 809 green (NF 708 + ai_layer 50 + text/harness 51).
This self-review does NOT substitute for your gate.

## Review questions

1. Is the entry snapshot now un-bypassable — can any caller value (metaclass tricks, `__class__`
   spoofing, `__subclasshook__`, a type whose identity you can't trust) still pass `_deep_plain_json`
   as a scalar/list/dict while actually being a container with live methods?
2. Is the all-`is` gate complete and correct — is `{None, bool, int, float, str, list, dict}` by
   identity the full JSON base set, and does any residual `==`/`in`/attribute read on an untrusted
   value remain in `_deep_plain_json` or the entry path?
3. Is `chain` fully handled — snapshotted when passed, self-read when None, and does the load path's
   separate use of its own `_read_chain` output stay consistent with verify's snapshot (same content,
   single logical snapshot)?
4. Any other injectable parameter or attribute on the archive path (artifact/contract nested
   objects, prov_dir contents) that reaches a comparison/iteration before being frozen — or is the
   sealed-object + deep-snapshot boundary now complete?
5. Verdict: SOUND-TO-PROCEED (to the four-seat session-archive embedding) or further findings — with
   reproduced probes for anything you flag.
