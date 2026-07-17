# GPT Cross-Review Request — NF Final-Integration Unit 1 RE-REVIEW #2 (archive boundary, FIX-FIRST folded)

You are re-reviewing the **decision-archive boundary** of the news-flash (NF) seat for a
standalone LLM stock-scoring product (虚拟AI投研部). Your first review returned
**FIX-FIRST: 2 Blockers + 1 Major**. All three have been folded verbatim, each of your
reproduced probes is pinned as a regression that fails on the pre-fix code. Commit under
review: `1d27def` on branch `calendar-unfreeze`.

Your final line last round: "FIX-FIRST — make the archive write-once and bind each
archived parsed record to its exact selected provenance terminal before embedding this
seat slice into the four-seat session archive."

## Files (embedded text authoritative; links for live cross-check)

- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_archive.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_executors.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/tests/test_news_archive.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/tests/test_news_executors.py

Unchanged context (same as last round): `news_decision.py`, `news_legs.py`,
`news_horizon.py`, `news_cards.py`, `news_evidence.py` on the same branch.

## How each finding was folded

### Blocker 1 — archive overwritable → WRITE-ONCE + first-write-wins

`seal_decision_archive` now:
1. runs the full joint verification, builds the complete archive payload
   (including `ledger_head_at_seal`), then
2. takes a **per-decision mkdir lock** (`_prov_lock` keyed on the archive file path —
   one file per decision) around the entire read-check-write;
3. if the file exists: load it; return it **only if the fully re-derived archive is
   `==` identical** (idempotent retry — same bundle, unchanged ledger); otherwise
   `RegistryError` naming the existing vs new `execution_id`. A second, equally-valid
   execution of the same decision has a fresh `execution_id`, so its archive differs →
   refused;
4. only the not-exists branch writes (tmp + fsync + `os.replace`, inside the lock).

Pinned: `TestWriteOnce::test_second_valid_execution_cannot_overwrite` (second real
execution → refused; on-disk archive still carries the FIRST execution_id) and
`::test_identical_reseal_is_idempotent` (same bundle → returns existing, one file).

Same-class sweep: all other `os.replace` writers in the NF engine are append-only
rewrites under lock (provenance, ledger) or already first-write-wins (decision ledger);
`analyst_chain.py`'s writers belong to the main chain's own reviewed machinery, out of
this unit.

### Blocker 2 — terminal-row ↔ leg ↔ record binding

- **Provenance rows now carry `parsed_record_hash`** (canonical `seal_hash` of the
  parsed record), sealed inside `entry_hash`. `persist_execution_provenance` enforces:
  record-bearing verdicts (`valid` / `deterministic_zero` / `empty_penalty`) REQUIRE a
  64-hex value; record-free verdicts (`attempt_started` / `invalid` / `call_error`)
  must carry None; `leg` must be `factor|penalty`. All three record-bearing persist
  sites in `news_executors.py` pass the hash of the exact record they stash into the
  returned bundle.
- **`_verify_selected_row`** additionally enforces the strict row key set
  (`PROV_ROW_KEYS`, symmetric-difference named in the error) and
  **`row["leg"] == leg`** — your foreign-leg probe: a genuine on-disk row of the OTHER
  leg placed in the factor slot passes entry_hash + on-disk membership but dies on the
  leg binding (`test_cross_leg_row_in_factor_slot_refused`); a `leg="foreign_leg"` row
  can no longer even be persisted (`test_foreign_leg_name_refused_at_persist`).
- **`_require_record_bound`**: every archived record is a dict whose canonical hash
  must equal its selected terminal's `parsed_record_hash`; with `expect=` the record
  must additionally be field-exact equal to the deterministic record
  (`deterministic_zero_factor_record()` / the empty-penalty record). Your
  records+evaluation joint tamper now dies at the hash binding
  (`test_records_and_evaluation_joint_tamper_refused`).
- **Records shape restricted by leg status** (`verify_execution_bundle`):
  `bundle.records` must be exactly `{factor, penalty}`; factor failed → None (your
  hard-fail-with-arbitrary-JSON probe: `test_hard_fail_arbitrary_records_refused`);
  penalty not_run/failed → None; penalty success → hash-bound dict; empty_success →
  field-exact deterministic empty record + hash binding
  (`test_empty_penalty_record_tamper_refused`).
- **`deterministic_zero` legitimacy is re-derived from the artifact**: on factor
  success the verifier recomputes `leg_expected_ids(final_registry, factor_positive,
  news)`; non-empty population → verdict MUST be `valid`; empty → MUST be
  `deterministic_zero` (both directions). Your forged-zero probe — a genuinely
  persisted `deterministic_zero` row + all-zero records + consistently recomputed
  evaluation while real evidence exists — dies on the population re-derivation
  (`test_forged_deterministic_zero_with_evidence_refused`).

### Major — load-side identity + byte-exact filename

`load_and_verify_decision_archive` now enforces, in order: strict top-level key set
(`_ARCHIVE_KEYS`, 15 keys, extra/missing = refuse) → seal recompute → `archive_schema
== "news_decision_archive_v1"` (value pinned, so a re-sealed schema tamper still dies)
→ **three-way decision identity** `archive.decision_id == requested_id ==
artifact.bundle.decision_id` (your d1→d2 file-copy replay dies here) →
contract hash+payload → `artifact_hash` → `bundle_hash` → `final_registry_hash`,
then the outcome rebuild + full joint verification + head anchor as before.

`_archive_path` = full byte-exact `hashlib.sha256(decision_id.encode("utf-8"))`
hex digest (whitespace-variant decision ids get distinct files —
`test_whitespace_variant_decision_ids_get_distinct_paths`); `decision_id` must be a
non-empty `str`. Repo-wide sweep: no other filesystem path is derived from the
whitespace-folding `seal_hash`.

## Self-review (completed before this request)

Verdict: **clean for GPT**. Checked: §3 hard invariants untouched (pure product-engine
code under `workspace/research/ai_research_dept/`, zero imports into `src/`, pipeline
remains NON_EVIDENTIARY with zero production callers until FORWARD_PREREG); each fold
done by invariant class, not instance (overwrite doors swept across the NF engine;
canon-hash-in-path swept repo-wide; row-level identity now covers key set + leg + all
id fields); JSON round-trip safety of the idempotent `==` compare verified (archive
payload is all scalars/lists/dicts — no tuples); 15 new adversarial regressions, each
reproducing one of your probes; suites: NF 652 + ai_layer 50 + text/harness 51 green.

## Review questions

1. Is the write-once semantics airtight — any residual path (crash timing, lock
   bypass, tmp-file race, a caller writing via `_archive_path` directly) by which a
   sealed archive can be replaced with different content?
2. Is the terminal-row↔leg↔record binding now complete, or can you still construct a
   bundle/archive whose records diverge from what the selected terminals attest —
   including via rows YOU persist yourself through `persist_execution_provenance`
   (the append-only provenance file is not hash-chained by design; the ledger head is
   the external anchor — is that boundary still sound given the new fields)?
3. Any remaining load-side identity gap (cross-directory replay, contract/artifact
   substitution, key aliasing) after the strict key set + three-way identity +
   redundant-hash checks?
4. The deterministic_zero biconditional re-derives the population from the CURRENT
   artifact. Is there any exploitable asymmetry between seal-time and load-time
   artifact state (the artifact is itself sealed and verified via `verify_d7_artifact`
   + `artifact_hash`/`bundle_hash`/`final_registry_hash` equality)?
5. Verdict: SOUND-TO-PROCEED (to the four-seat session-archive embedding) or further
   findings — with reproduced probes for anything you flag.
