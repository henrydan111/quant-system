# GPT Cross-Review Request — NF Final-Integration Unit 1 RE-REVIEW #20 (archive boundary, recursive plain-JSON snapshot at entry — root-cause fix for the caller-container class)

You are re-reviewing the **decision-archive boundary** of the news-flash (NF) seat. Your previous
verdict (on `a0d4c94`) was **REVISE — 1 P1**: `_canon_json` did not close the container-subclass
class, because `json.dumps()` calls a dict/list SUBCLASS's `.items()`/iteration, and
`_require_record_bound` serializes the caller record twice (compare, then `seal_hash`), so a stateful
`items()` mutates the trusted disk row on the second call. Folded with the ROOT-CAUSE fix you
prescribed. **Commit under review: `035e2e1`** on branch `calendar-unfreeze`.

Your finding + prescription, verbatim intent:
- `json.dumps()` is not a "does not run caller code" purifier; a stateful `items()`/`get()`/
  `__getitem__` runs during it, and `sel.get()`, `records[...]`, `bundle.get("evaluation")` are the
  same unclosed root. Require `bundle`, `selected_provenance`, `records` and their nested content to
  be exact base JSON types, recursively copy to a plain-JSON snapshot BEFORE reading disk provenance
  / resolving `f_resolved`/`p_resolved`; then use only that snapshot. Add factor/penalty
  stateful-`items()` regressions and a "penalty `sel.get()` cannot mutate an already-verified factor
  row" regression.

## Files (embedded text authoritative; links pin to `035e2e1`)

- https://raw.githubusercontent.com/henrydan111/quant-system/035e2e1/workspace/research/ai_research_dept/engine/news_archive.py
- https://raw.githubusercontent.com/henrydan111/quant-system/035e2e1/workspace/research/ai_research_dept/tests/test_news_archive.py

## How it was folded — snapshot first, at entry, before any disk read

- `_deep_plain_json(x)`: recursively requires EXACT base JSON types
  (`dict`/`list`/`str`/`int`/`float`/`bool`/`None`; subclasses and custom objects refused) and
  rebuilds a plain structure. The exact-type gate (`type(x) is dict` / `type(x) is list`) runs BEFORE
  any `.items()`/iteration, so **no caller container code executes** — a dict/list subclass or a
  non-JSON value is refused outright, and its `.items()`/`get()`/`__getitem__`/`__ne__` is never
  called.
- `verify_execution_bundle` entry: `bundle` must be an EXACT dict; the outcome is the sealed object
  (exact-typed + `assert_base_outcome_fields`); the caller JSON parts — `execution_id`,
  `selected_provenance`, `records`, `evaluation` — are each `_deep_plain_json`'d into independent
  plain snapshots BEFORE `read_execution_provenance` / `_resolve_terminal`. Everything downstream uses
  only those snapshots; `sel`/`records`/`evaluation` are never re-read from the live bundle, and no
  subclass container method can run.
- `_canon_json` now only ever sees the plain snapshots, so its double serialization in
  `_require_record_bound` (compare then `seal_hash`) is deterministic and mutation-free.

This is the root-cause fix for the whole "caller container/callback" class (#15–#20): every
caller-supplied structure is frozen to a plain-JSON snapshot at the single entry point, so no `!=`,
`==`, `in`, `.items()`, `.get()`, `__getitem__`, or `__ne__` on a caller object can run after entry.

## Regressions pinned

- `test_records_stateful_items_refused_at_snapshot`: a `records[leg]` dict subclass with a stateful
  `items()` (the reviewer's exact double-serialization vector) is refused at the entry gate; its
  `items()` is NEVER called (factor and penalty).
- `test_selected_row_subclass_refused_at_snapshot`: a dict-subclass selected row (stateful
  `items()`/`__ne__` forge) is refused at the gate; container methods never called (factor and
  penalty).
- `test_container_subclass_selected_provenance_refused_at_snapshot`: a dict-subclass
  `selected_provenance` whose `get()` would tamper live inputs is refused; `get()`/`items()` never
  called — this also covers "penalty `sel.get()` cannot run caller code after the factor row is
  verified" (there is no live `sel.get()` at all; `sel` is a plain snapshot).
- `test_selected_row_nonjson_value_refused`, `test_nondict_evaluation_refused_before_ne_fires`:
  non-JSON values refused at the gate.

## Self-review (completed before this request)

Verdict: **clean for GPT**. Live-bundle-read sweep of `verify_execution_bundle`: the only reads of
`bundle` are `type(bundle) is dict`, `bundle["outcome"]` (exact-dict → builtin), and four
`bundle.get(...)` calls that feed `_deep_plain_json` (exact-dict → builtin). Everything else uses the
plain snapshots (`sel`, `records`, `bundle_eval`, `execution_id`) or disk-resolved rows or captured
contract/artifact values. No `.items()`/`.get()`/`__getitem__`/`!=`/`==` on a caller subclass can run
after entry. Full suite: 807 green (NF 706 + ai_layer 50 + text/harness 51). This self-review does
NOT substitute for your gate.

## Review questions

1. Is the caller-container/callback class now closed at the ROOT — after the entry `_deep_plain_json`
   snapshot, can any caller-supplied container method (`.items()`, `.get()`, `__getitem__`,
   `__iter__`, `__ne__`, `__eq__`, `__hash__`) still run anywhere in the archive write path?
2. Is `_deep_plain_json` itself caller-code-free — does the `type(x) is dict/list` gate truly precede
   every `.items()`/iteration, and are exact scalars (`type(x) in (bool,int,float,str)`, `x is None`)
   the complete safe set (str/int/bool subclasses refused)?
3. Does the snapshot cover every caller-supplied structure the archive path consumes (execution_id,
   selected_provenance, records, evaluation), and is the outcome (a sealed object, not JSON) handled
   correctly outside the snapshot?
4. Any regression from requiring exact base JSON types for the caller bundle parts (a legitimate
   caller that passed a dict/str subclass would now be refused — is that acceptable, given genuine
   callers build plain dicts; the full suite incl. normal/zero/hard-fail/recovery/load is green)?
5. Verdict: SOUND-TO-PROCEED (to the four-seat session-archive embedding) or further findings — with
   reproduced probes for anything you flag.
