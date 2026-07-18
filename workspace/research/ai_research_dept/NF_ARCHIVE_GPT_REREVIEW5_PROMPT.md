# GPT Cross-Review Request — NF Final-Integration Unit 1 RE-REVIEW #5 (archive boundary, re-review#4 folded)

You are re-reviewing the **decision-archive boundary** of the news-flash (NF) seat.
Re-review #4 returned **FIX-FIRST: 2 × P1 + a crash variant**, with P0 declared closed
under the stated in-process trust model. All findings folded per your prescriptions.
Commit under review: `1b3d149` on branch `calendar-unfreeze`.

Your prescriptions, folded: "将每个 execution 的档案保持独立不可变,再用明确的
canonical-success 选择规则"; "读取应基于同一份账本快照完成 supersession 与锚点校验";
"增加成功承诺后的可恢复封存路径".

## Files (embedded text authoritative; links for live cross-check)

- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_archive.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_executors.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_decision.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/tests/test_news_archive.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/tests/test_news_executors.py

Unchanged context: `news_legs.py`, `news_horizon.py`, `news_cards.py`,
`news_evidence.py`, `news_seal.py` on the same branch.

## How P1-a was folded — per-execution immutable archives + canonical-success rule

- `_archive_path(archive_dir, decision_id, execution_id)`: one file per execution,
  named by the byte-exact sha256 of the JSON pair `[decision_id, execution_id]`
  (JSON encoding gives unambiguous delimiting — `("d","x:e")` ≠ `("d:x","e")`;
  whitespace variants of either id stay distinct — pinned). Write-once +
  first-write-wins now applies per `(decision, execution)`; a failed execution's
  archive occupies its own file and can never block the success archive. Your
  combined probe — `hard_failed → seal → success retry → seal success` — now ends
  with BOTH archives on disk, the decision loader returning the success archive, and
  the hard-fail archive still audit-loadable
  (`test_hard_fail_seal_then_success_seal_coexist`). No bricked decision.
- **Canonical selection is the ledger's, not the filesystem's**:
  `load_and_verify_decision_archive(decision_id, …)` resolves THE decision archive
  as the archive of the execution named by the chain's **unique success commitment**.
  No success commitment (hard-fail-only / never-executed) → refuse with a pointer to
  the execution-level API. Hard-fail execution archives are permanently valid
  per-execution audit records via the new
  `load_and_verify_execution_archive(decision_id, execution_id, …)` — supersession
  no longer blocks execution-level audit; the supersession refusal inside
  `verify_execution_bundle` was REMOVED because the semantics moved up into
  canonical selection (a hard-fail archive is simply never canonical; it is not
  retroactively "invalid as an execution record").

## How P1-b was folded — single-snapshot loads

Both loaders take ONE `_read_chain` snapshot at entry and perform canonical
selection, commitment lookup/equality, and anchor membership + ancestry against that
same snapshot — threaded through `verify_execution_bundle` via a new `chain`
parameter. (The payload rebuild's internal ledger gate re-reads, but it touches only
the immutable first-write decision registration row — no race surface; noted in the
docstring.) The canonical rule also removes your demonstrated interleaving
structurally: the decision loader can never return a `hard_failed` doc under ANY
timing — it either returns the success execution's archive or refuses. Your exact
end-state (hard-fail sealed, success committed, success archive not yet sealed) now
refuses with "档案缺失" — pointing at recovery — instead of returning
`LOAD_RETURNED_STATUS=hard_failed`
(`test_decision_load_after_success_commit_never_returns_hard_fail`).

## How the crash variant was folded — recoverable sealing after a success commitment

- Provenance rows now carry the **full `parsed_record` body** — an alias-free JSON
  deep snapshot made inside the writer, sealed within `entry_hash` next to
  `parsed_record_hash`. (Side hardening: the archived-record ↔ row binding is now
  byte-exact equality against the row body PLUS the canonical hash, closing
  canon-whitespace variants the hash alone would fold.)
- `recover_and_seal_success_archive(decision_id, artifact, …)` rebuilds the bundle
  from PURE on-disk state: the unique success commitment names the execution;
  terminals are resolved (unique + state-machine-connected) and must equal the
  commitment's entry hashes; records come from the sealed row bodies (hash-bound);
  the outcome is **re-derived through the M3⁴ matrix** from (artifact, contract,
  verdicts) and must reproduce the committed `outcome_hash` (the authority anchor);
  the evaluation is recomputed. The result goes through the NORMAL
  `seal_decision_archive` (full joint verification + write-once; an existing
  identical archive → idempotent return). Pinned: recovery round-trip equals the
  live bundle's evaluation; zero-population (deterministic paths) recovery;
  idempotency against an already-sealed archive; refusal without a success
  commitment.

## Self-review (completed before this request)

Verdict: **clean for GPT**. Write-once-bricking class sweep: prov writer (terminal
per key — retry = fresh execution_id), decision registration (idempotent for the
same world), success commitment (unique but recovery path exists), archives
(per-execution) — no remaining door where a legitimate later state is permanently
blocked by an earlier one. Multi-read class sweep: loaders single-snapshot; the
seal-side sequence (verify → `ledger_head`) re-reads, but appended rows only move
the anchor LATER, which ancestry (≤) accepts — benign. Aliasing sweep: the writer
deep-snapshots `parsed_record`; bundle rows are decoupled from caller-mutable
records. Suites: 772 green (NF 671 + ai_layer 50 + text/harness 51).

## Review questions

1. Is P1-a closed — can any sequence of legal API calls still leave a decision with
   a committed success but no obtainable canonical archive (other than the
   crash-window state, which `recover_and_seal_success_archive` repairs)?
2. Is the single-snapshot discipline complete for the load paths, and is the
   remaining seal-side re-read (`ledger_head` after verification) genuinely benign
   as argued (append-only chain ⇒ later anchor still satisfies ancestry)?
3. The recovery path re-derives the outcome and requires it to reproduce the
   committed `outcome_hash`. Can a recovery be made to seal an archive that
   diverges from what the crashed execution would have sealed (records, evaluation,
   anchor) — or to "recover" an execution that never legitimately committed?
4. The execution-level audit loader intentionally ignores supersession (a hard-fail
   archive stays loadable as that execution's record forever). Any way this
   reintroduces the confusion the canonical rule was built to prevent — e.g. a
   consumer being handed a hard-fail slice as if it were the decision's outcome?
5. Verdict: SOUND-TO-PROCEED (to the four-seat session-archive embedding) or
   further findings — with reproduced probes for anything you flag.
