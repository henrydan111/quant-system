# GPT Cross-Review Request — NF Final-Integration Unit 1 RE-REVIEW #19 (archive boundary, selected-row canonical compare; class-wide sweep)

You are re-reviewing the **decision-archive boundary** of the news-flash (NF) seat. Your previous
verdict (on `e454b13`) was **REVISE — 1 P1**: the same caller-callback class at the
`selected_provenance` row compare (`row != resolved` handed the trusted disk `resolved` to the
caller row's `__ne__`, which mutated `resolved["parsed_record"]` in place). Folded, and the class
was swept archive-path-wide. **Commit under review: `a0d4c94`** on branch `calendar-unfreeze`.

Your finding, verbatim intent:
- `_verify_selected_row` accepted a dict-subclass row (`isinstance`), did `row != resolved` with the
  caller row on the left; its `__ne__` received the trusted disk `resolved`, forged
  `resolved["parsed_record"]`, and returned `False`; `trusted_records` (built from `f_resolved` /
  `p_resolved`) then carried the forge into the archive. Prescription: treat each selected row as an
  untrusted JSON assertion; produce an independent plain-JSON snapshot / compare two canonical JSON
  strings (not `row != resolved`); after the compare, `_check_terminal_row`, record binding, and
  verdict reads must use ONLY `resolved`, never the caller `f_row`/`p_row`; regression for factor and
  penalty.

## Files (embedded text authoritative; links pin to `a0d4c94`)

- https://raw.githubusercontent.com/henrydan111/quant-system/a0d4c94/workspace/research/ai_research_dept/engine/news_archive.py
- https://raw.githubusercontent.com/henrydan111/quant-system/a0d4c94/workspace/research/ai_research_dept/engine/news_executors.py
- https://raw.githubusercontent.com/henrydan111/quant-system/a0d4c94/workspace/research/ai_research_dept/tests/test_news_archive.py

## How it was folded

- `_canon_json(x) = json.dumps(x, sort_keys=True, ensure_ascii=False, allow_nan=False)` — the single
  helper for comparing anything caller-supplied. `json.dumps` serializes content without invoking
  `__eq__`/`__ne__`; a non-JSON value (an object with magic methods) raises → refused.
- `_verify_selected_row` canonically compares `row` vs `resolved` (no `!=`, no callback) and passes
  the DISK-resolved `resolved` — never the caller `row` — to `_check_terminal_row`.
- Every downstream read in `verify_execution_bundle` uses the disk-resolved rows (`f_resolved` /
  `p_resolved`), never the caller `f_row`/`p_row`/`row`: the `deterministic_zero` verdict dispatch,
  the empty-penalty sentinel check (`p_resolved["verdict"]`/`["payload_hash"]`), and every
  `_require_record_bound` call.
- `_require_record_bound` compares via `_canon_json` too (the caller record can no longer receive a
  trusted value through `!=`).

## Class-wide sweep (my self-review, for you to check)

I grepped the archive write path (`verify_execution_bundle` → `seal_decision_archive`) for every
`!=`/`==` where a trusted mutable could be handed to a caller object. After this fold:
- selected-row compare → `_canon_json` (was the P1).
- record binding → `_canon_json` (`_require_record_bound`).
- evaluation compare → exact-dict gate + `_canon_json` (re-review#18).
- outcome → reconstructed independent `NewsLegOutcome`; its fields exact-typed (re-review#15/#18).
- contract/artifact/registry → captured/frozen right after validation; commitment compares use the
  captured `v_contract_payload` and the disk-resolved entry hashes (re-review#16/#17).
The only remaining `!=` in the path are `str != str` hash comparisons (`seal_hash(record) !=
row["parsed_record_hash"]`, `commitment[...] != <captured/disk str>`) — both operands are plain
strings from trusted sources (seal_hash output / disk rows / captured values), so no caller
`__ne__` is invoked. The seal path builds the archive purely from `verified` + `ledger_head`.

## Regressions pinned

- `test_selected_row_ne_callback_never_fires`: a dict-subclass selected row (factor AND penalty)
  whose `__ne__` would forge `parsed_record` has its `__ne__` NEVER called; the archive keeps the
  genuine disk record.
- `test_selected_row_nonjson_value_refused`: a selected row carrying a non-JSON value is refused at
  the canonical-JSON gate.

## Self-review (completed before this request)

Verdict: **clean for GPT**. The recurring root cause across #15–#19 was a trusted mutable on one
side of a `!=`/`==` with a caller object on the other (outcome field read, registry swap, eval dict,
selected row). Every such site in the archive write path is now either a canonical-JSON string
compare, an exact-type gate, or a read of captured/disk-resolved/reconstructed state; the archive is
built entirely from that trusted state. Full suite: 806 green (NF 705 + ai_layer 50 + text/harness
51). This self-review does NOT substitute for your gate.

## Review questions

1. Is the caller-callback class now closed across the WHOLE archive write path — can you find any
   remaining `!=`/`==`/`in`/`__getitem__` where a caller-supplied object (bundle, sel, a row,
   records, evaluation, contract, artifact) can run a magic method that touches a trusted mutable or
   the value the archive commits?
2. Is the canonical-JSON compare sound for selected rows and records — does `json.dumps(sort_keys)`
   fully neutralize a dict-subclass (content-only serialization, non-JSON values rejected), and is
   comparing to `_canon_json(resolved)` (disk row) safe given `resolved` is never passed to a caller
   method?
3. Is "downstream uses only `resolved`" complete — is there any remaining read of the caller
   `f_row`/`p_row`/`row`/`sel[...]` after the canonical compare in `verify_execution_bundle`?
4. Any regression from routing selected-row and record comparisons through canonical JSON (the full
   suite incl. normal/zero/hard-fail/recovery/load is green)?
5. Verdict: SOUND-TO-PROCEED (to the four-seat session-archive embedding) or further findings — with
   reproduced probes for anything you flag.
