# GPT Cross-Review Request — NF Final-Integration Unit 1 RE-REVIEW #16 (archive boundary, whole payload is a frozen verified snapshot)

You are re-reviewing the **decision-archive boundary** of the news-flash (NF) seat. Your
previous verdict (on `15318c6`) was **REVISE — 1 P1**: outcome was independent, but the REST of
the verified payload still mixed in post-verification live reads (records, factor provenance,
contract, artifact), so a callback fired during verification could pollute the write-once
archive. Folded. **Commit under review: `5a19609`** on branch `calendar-unfreeze`.

Your finding, verbatim intent:
- After verification, seal still made/supplemented archive content from caller-held mutable
  objects: `records` tampered post-verify-pre-snapshot; `selected_provenance.get("penalty")`
  callback tampering records; factor provenance taken from caller `f_row` not disk `f_resolved`;
  `seal_decision_archive()` re-reading live `contract`/`artifact` (zeroing `artifact_hash`/
  `contract_hash` reached the archive). Prescription: build records/provenance only from resolved
  disk terminal rows + deep-copy immediately; recompute evaluation from those; freeze
  contract/artifact canonical payloads + hashes into `verified` during verification;
  `seal_decision_archive()` must not read live inputs afterward.

## Files (embedded text authoritative; links pin to `5a19609`)

- https://raw.githubusercontent.com/henrydan111/quant-system/5a19609/workspace/research/ai_research_dept/engine/news_archive.py
- https://raw.githubusercontent.com/henrydan111/quant-system/5a19609/workspace/research/ai_research_dept/engine/news_executors.py
- https://raw.githubusercontent.com/henrydan111/quant-system/5a19609/workspace/research/ai_research_dept/engine/news_legs.py
- https://raw.githubusercontent.com/henrydan111/quant-system/5a19609/workspace/research/ai_research_dept/tests/test_news_archive.py

## How it was folded — the whole archive payload is a frozen verified snapshot

`verify_execution_bundle` now produces the COMPLETE archive payload as `verified`, and
`seal_decision_archive` writes `{**verified, "ledger_head_at_seal": ledger_head(...)}` + the seal
— reading nothing else live:

- **Captured before any callback-capable read**: `v_contract_payload` /`v_contract_hash`
  immediately after `require_exact_contract`; `v_artifact_hash`/`v_bundle_hash`/
  `v_final_registry_hash` immediately after `verify_d7_artifact` — both BEFORE the `sel.get()` /
  records reads.
- **records + selected_provenance from the DISK-resolved terminal rows only**: the factor/penalty
  records are the sealed `parsed_record` of `f_resolved` / `p_selected` (the `_resolve_terminal`
  outputs), never the caller's `bundle["records"]` / `f_row` / `sel`. The commitment check now
  compares the disk-resolved entry hashes and the captured contract values.
- **evaluation recomputed** from those trusted records.
- **JSON deep-copy** of the whole `verified` payload (de-aliased + NaN/non-serializable rejected).
- `seal_decision_archive` reads only `verified` + `ledger_head`; the reconstructed
  `NewsLegOutcome` is returned separately as `verified_outcome`; `commitment` unchanged for the
  load ancestry check.

## Regressions pinned

- `test_archive_records_provenance_from_disk_resolved`: the archive's factor record and
  provenance equal the disk-resolved terminal row's `parsed_record` / `entry_hash`, not the
  caller's bundle.
- `test_post_verify_live_mutation_never_reaches_archive`: a `selected_provenance.get()` callback
  that zeroes `artifact_hash` and `contract_hash` mid-verify never reaches the archive — it keeps
  the captured values and reloads cleanly.
- `test_seal_consumes_independent_verified_snapshot`: the `verified` payload's records /
  selected_provenance are distinct objects from the bundle's; the reconstructed outcome is a
  distinct object with the same `outcome_hash`.

## Self-review (completed before this request)

Verdict: **clean for GPT**. Live-read sweep of the two archive writers:
`seal_decision_archive` now reads only `verified` + `ledger_head(ledger_dir)`;
`recover_and_seal_success_archive` already rebuilds the bundle from pure on-disk state + the
ledger commitment and then routes through `seal_decision_archive` (so it inherits the frozen
snapshot). Capture-before-callback: the contract/artifact values are captured on the lines
immediately following their validation, before any `sel`/records read. Disk-sourced content:
records/provenance come from `_resolve_terminal` outputs. Full suite: 802 green (NF 701 +
ai_layer 50 + text/harness 51). This self-review does NOT substitute for your gate.

## Review questions

1. Is the verify-live/write-live class now fully closed — does `seal_decision_archive` (or any
   archive writer) read ANY security-relevant value from a caller-held mutable (bundle, contract,
   artifact, or a nested object) rather than from the frozen `verified` payload / disk-resolved
   state?
2. Are all the captured values truly captured before any callback-capable read — is there a
   `sel.get()`, `bundle[...]`, records access, or `__getitem__`/`__eq__` on a caller object that
   runs BETWEEN a value's validation and its capture into `verified`?
3. Is building records/provenance from `f_resolved`/`p_selected` (the `_resolve_terminal` outputs,
   which are themselves re-derived from the on-disk provenance file each call) genuinely
   independent of the caller, and does the JSON deep-copy fully de-alias the payload?
4. Any regression from routing the entire payload through `verified` (records now disk-sourced,
   selected_provenance now disk-resolved rows, evaluation recomputed, whole thing JSON
   round-tripped) — the full suite incl. normal/zero/hard-fail/recovery/load round trips is green.
5. Verdict: SOUND-TO-PROCEED (to the four-seat session-archive embedding) or further findings —
   with reproduced probes for anything you flag.
