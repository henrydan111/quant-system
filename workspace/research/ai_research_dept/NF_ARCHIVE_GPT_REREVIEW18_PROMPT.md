# GPT Cross-Review Request — NF Final-Integration Unit 1 RE-REVIEW #18 (archive boundary, frozen trusted_eval + no-user-callback compare)

You are re-reviewing the **decision-archive boundary** of the news-flash (NF) seat. Your previous
verdict (on `2112c60`) was **REVISE — 1 P1**: #17 froze the scoring registry, but the sanity compare
`trusted_eval != bundle["evaluation"]` still handed the mutable `trusted_eval` dict to a caller
callback. Folded. **Commit under review: `e454b13`** on branch `calendar-unfreeze`.

Your finding, verbatim intent:
- `trusted_eval` is a plain dict on the LEFT; when `bundle["evaluation"]` is a non-dict whose
  comparison makes `dict.__ne__` return `NotImplemented`, Python calls
  `bundle_eval.__ne__(trusted_eval)`, passing the ACTUAL `trusted_eval` object — the callback
  mutated it in place (`other["news_final"]=52.0`) and returned `False`; the archive wrote the
  mutated dict under the original registry hash. Prescription: build an independent strict-JSON
  archive snapshot before reading/comparing the caller evaluation; the archive uses only that
  snapshot; gate the caller evaluation with an exact-`dict` type gate and canonical-JSON comparison
  (avoid user `__eq__`/`__ne__`). Also: `_check_terminal_row` should use the frozen registry.

## Files (embedded text authoritative; links pin to `e454b13`)

- https://raw.githubusercontent.com/henrydan111/quant-system/e454b13/workspace/research/ai_research_dept/engine/news_archive.py
- https://raw.githubusercontent.com/henrydan111/quant-system/e454b13/workspace/research/ai_research_dept/engine/news_executors.py
- https://raw.githubusercontent.com/henrydan111/quant-system/e454b13/workspace/research/ai_research_dept/tests/test_news_archive.py

## How it was folded

- **trusted_eval frozen before any compare**: immediately after `trusted_eval` is computed (from
  the frozen `v_final_registry` snapshot + disk-resolved records), it is replaced by an independent
  JSON deep-copy (`json.loads(json.dumps(trusted_eval, allow_nan=False))`). The archive uses that
  copy; no callback can reach it.
- **no-user-callback compare**: the caller evaluation is now only a sanity compare via an EXACT-dict
  gate (`type(be) is not dict` → refuse) plus a canonical-JSON string comparison
  (`json.dumps(trusted_eval, sort_keys=True) != json.dumps(be, sort_keys=True)`) — the `!=` is
  between two plain strings, so no user-defined `__eq__`/`__ne__` is ever invoked, and the exact-dict
  gate rejects both non-dicts and dict subclasses. `bundle["evaluation"]` is never archived.
- **point-4 defense-in-depth**: `_check_terminal_row` / `_verify_selected_row` take an optional
  `final_registry`; `verify_execution_bundle` threads the frozen `v_final_registry` into the factor
  `deterministic_zero` re-derivation, so that check does not read live `artifact.final_registry`
  after a caller-callback point either.

## Regressions pinned

- `test_nondict_evaluation_refused_before_ne_fires`: a non-dict `bundle["evaluation"]` whose `__ne__`
  would mutate `trusted_eval` in place AND swap the registry is refused at the exact-dict gate, and
  its `__ne__` is NEVER called (both side effects dead); nothing is sealed.
- `test_trusted_eval_frozen_independent_of_bundle_eval`: the archived evaluation is a frozen JSON
  copy distinct from `bundle["evaluation"]` and reloads cleanly.

## Self-review (completed before this request)

Verdict: **clean for GPT**. Mutable-value-to-caller-callback sweep of the archive path: the only
place a trusted mutable was compared against a caller object was the evaluation compare; it now
freezes first and compares via canonical JSON under an exact-dict gate (no user callback). All other
archive fields are captured/disk-resolved and JSON-deep-copied. Registry reads for the archived
score and the deterministic_zero check use the frozen `v_final_registry`. Full suite: 804 green (NF
703 + ai_layer 50 + text/harness 51). This self-review does NOT substitute for your gate.

## Review questions

1. Is the mutable-value/caller-callback class now fully closed — does any archive-path comparison or
   read still pass a trusted mutable (dict/list/the outcome) to a caller-controlled object's
   `__eq__`/`__ne__`/`__contains__`/`__getitem__`, or read a live caller value after it has been
   captured/frozen?
2. Is the canonical-JSON sanity compare sound — can a caller `bundle["evaluation"]` that passes
   `type(be) is dict` still influence anything (its values are plain via the exact-dict gate; the
   compare is string-vs-string; and it is never archived — do you agree)?
3. Is the point-4 `final_registry` threading complete for the deterministic_zero re-derivation, and
   are there other `_check_terminal_row` reads (`contract.schema_id`, etc.) that should also come
   from captured values?
4. Any regression from freezing/JSON-round-tripping the evaluation and the exact-dict gate — the
   full suite incl. normal/zero/hard-fail/recovery/load round trips is green.
5. Verdict: SOUND-TO-PROCEED (to the four-seat session-archive embedding) or further findings —
   with reproduced probes for anything you flag.
