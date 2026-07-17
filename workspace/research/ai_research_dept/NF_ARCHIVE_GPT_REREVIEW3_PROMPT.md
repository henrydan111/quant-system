# GPT Cross-Review Request — NF Final-Integration Unit 1 RE-REVIEW #3 (archive boundary, re-review#2 folded)

You are re-reviewing the **decision-archive boundary** of the news-flash (NF) seat.
Re-review #2 returned **FIX-FIRST: 1 Blocker + 2 Majors**. All three folded verbatim;
every one of your probes is pinned as a regression. Commit under review: `eba3885` on
branch `calendar-unfreeze`.

Your Blocker prescription last round, folded in full: "归档不能信任 bundle 带入的
selected row;必须由受控执行器按 (decision_id, execution_id, leg) 解析唯一、状态机相连
的终态。写入器应接收实际 raw/record 并内部计算哈希,且把 provenance terminal/head 提交
到不可重写的外部链中。仅增加 prev_hash 或继续允许通用 public persist API 不足以修复。"

## Files (embedded text authoritative; links for live cross-check)

- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_archive.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_executors.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_decision.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/tests/test_news_archive.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/tests/test_news_executors.py

Unchanged context: `news_legs.py`, `news_horizon.py`, `news_cards.py`,
`news_evidence.py`, `news_seal.py` on the same branch.

## How each finding was folded

### Blocker — provenance terminals can no longer be self-forged (three layers)

**Layer 1 — the public persist API is removed; the writer is controlled.**
`_persist_execution_provenance` (module-private) now takes the ACTUAL `raw` text and
`parsed_record` dict and computes `raw_sha256` / `parsed_record_hash` INTERNALLY —
caller-supplied hashes are gone from the signature. Inside the same lock it enforces a
write-time state machine per `(execution_id, leg)`: exactly one `attempt_started`,
exactly one terminal — a second terminal for an attempted key is refused outright
(your probe's first kill: `test_state_machine_second_terminal_refused`); LLM terminals
(`valid`/`invalid`/`call_error`) must connect to a same-payload `attempt_started` row;
deterministic terminals (`deterministic_zero`/`empty_penalty`) must have NO attempt row.

**Layer 2 — terminals are committed to the non-rewritable external chain.**
`execute_news_decision` (the controlled executor) now calls
`record_execution_commitment` before returning the bundle: a new
`kind=execution_commitment` row in the DECISION LEDGER hash chain carrying
`{decision_id, execution_id, factor_entry_hash, penalty_entry_hash, outcome_hash}`.
First-write-wins per `(decision_id, execution_id)` (identical-fields retry is
idempotent; any different terminal set is refused —
`test_forged_commitment_first_write_wins`); `_read_chain` validates both row kinds
(per-kind strict key sets, `kind` tag, seq/prev_hash/entry_hash as before, decision-id
uniqueness among decision rows, `(decision_id, execution_id)` uniqueness among
commitments, and commitment-must-postdate-its-decision ordering).

**Layer 3 — archive verification resolves, never trusts.**
`verify_execution_bundle` no longer treats the bundle's rows as facts: per attempted
leg it RESOLVES the unique state-machine-connected terminal from the on-disk
provenance file by `(decision_id, execution_id, leg)` (`_resolve_terminal`; 0 or ≥2
terminals = the key has lost verifiability = fail-closed), requires the bundle row to
EQUAL that on-disk row byte-for-byte, re-checks the attempt linkage, and finally
requires the resolved terminals' entry_hashes + `outcome_hash` to match the ledger
commitment.

Your 74.0 → 50.0 substitution now dies three independent ways, each pinned:
- writer append → refused at write (`恰一终态`);
- file-level append bypassing the writer → resolution ambiguity
  (`test_appended_forged_terminal_breaks_key_verifiability`);
- file-level in-place REPLACE (unique on disk, state machine intact, record +
  evaluation consistently recomputed — the strongest surviving form) → ledger
  commitment mismatch (`test_replaced_terminal_dies_at_ledger_commitment`).

Crash semantics: terminals persisted but process dies before the commitment → the
archive can never seal that execution (commitment missing = refuse); a fresh
execution_id re-runs cleanly.

### Major — nested alias fields

`selected_provenance` must be exactly `{factor, penalty}` (checked in the shared
joint verification, so both seal and load enforce it); on load the archived `outcome`
dict must equal the rebuilt outcome's canonical `_payload()` field-for-field — the
rebuild takes named fields only, the equality closes the extras. Your two reseal
probes are pinned (`test_outcome_alias_key_reseal_refused`,
`test_selected_provenance_alias_key_reseal_refused`). Contract/records/rows were
already exact-equality or strict-key-set checked.

### Major — genesis anchor downgrade

The head-anchor check is now UNCONDITIONAL membership (`anchored not in
current_hashes` → refuse). Sealing always postdates decision registration + the
execution commitment, so the ledger is never empty at seal and genesis is never a
legal anchor. Your rewrite-to-genesis + reseal probe is pinned
(`test_genesis_anchor_downgrade_refused`).

## Self-review (completed before this request)

Verdict: **clean for GPT**. Bundle-supplied-fact sweep: outcome (rebuilt +
matrix-self-validating + outcome_hash in the ledger commitment), evaluation
(recomputed), records (hash-bound to committed terminals), execution_id (must have a
ledger commitment), selected rows (resolved from disk + committed) — no remaining
bundle field is trusted without an independent anchor. Nested-strictness sweep: every
nested archive object is now exact-equality or strict-key-set checked. Acknowledged
boundary (your R2 answer 1): none of this is access control against a caller with
write access to the dirs — the ledger chain + head anchor is the trust root, and the
four-seat integration will pin the archive root + outer immutable sealing layer.
Suites: 763 green (NF 662 + ai_layer 50 + text/harness 51).

## Review questions

1. Is the Blocker closed? Specifically: (a) can a forged terminal still enter a
   sealed archive through any path that does not rewrite the decision-ledger chain;
   (b) is the (writer state machine + on-disk resolution + ledger commitment) triple
   sound against the append/replace/API attack family you demonstrated?
2. The commitment row lives in the SAME ledger whose head anchors the archive. Any
   circularity or ordering problem (commitment after payload-sealing but before
   archive-sealing; legitimate chain growth after seal; resume/crash windows)?
3. Are the nested-strictness equalities complete, or can any archive field still
   carry unverified data to a consumer of the load return value?
4. Any residual anchor weakness after the unconditional membership check (e.g.
   anchoring to a hash that exists in an unrelated position, given entry hashes
   commit to seq + prev_hash)?
5. Verdict: SOUND-TO-PROCEED (to the four-seat session-archive embedding) or further
   findings — with reproduced probes for anything you flag.
