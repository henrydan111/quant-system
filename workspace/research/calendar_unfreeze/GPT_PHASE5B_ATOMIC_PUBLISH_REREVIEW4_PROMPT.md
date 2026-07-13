# GPT 5.5 Pro re-review #4 — Phase 5-B atomic publish: re-review #3 P0/Major closed

> Send verbatim to GPT 5.5 Pro. Branch pushed; pinned HEAD: `e4eda7d` (fix commit `3e70e4a`,
> docs `e4eda7d`; your re-review #3 baseline was `ff8c25f`).

```text
ROLE
You are the same senior reviewer who issued REWORK #3 (3 P0 + 3 Major: in-process-boolean vs disk truth, the hash->ready window on a mutable tree, non-data-root lock identity, real-SIGINT semantics, concurrent-QA overwrite, orphaned publish record). Re-review adversarially: re-run your probes against the new code and hunt for holes the fixes opened. Do not rubber-stamp.

REPO (public — fetch any file to verify against the live code)
https://github.com/henrydan111/quant-system   (branch: calendar-unfreeze-phase5b-atomic-publish)
Raw file form: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/<path>

KEY FILES (updated this round)
- Driver: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/scripts/monthly_calendar_bump.py
- Locks (data-root identity + LockIdentityError): https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/src/data_infra/tushare_lock.py
- Tests: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/tests/data_infra/test_monthly_calendar_bump.py
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/tests/research_orchestrator/test_provider_raw_attestation_gate.py
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/tests/data_infra/test_daily_update_5c.py
- Self-review round 4 (incl. your preflight checklist internalized): https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/workspace/research/calendar_unfreeze/PHASE5B_ATOMIC_PUBLISH_SELF_REVIEW.md
- Invariants (hardening paragraph REWRITTEN — superseded claims corrected, not appended): CLAUDE.md 3.4

FINDING-BY-FINDING DISPOSITION (verify each against the diff below)
P0-1 (swap-completed boolean gap) -> the handler classifies from DISK FACTS: _disk_swap_state(builder, parent_pb) reads the live manifest's provider_build_id + the backup dir's existence — child_live (backup present AND live != parent; covers the pre-emit None case) takes the FULL verified undo; parent_live (no backup AND live == parent) relies on the primitive's self-rollback; unknown -> exit 5 with the journals. A durable INTENT journal (publish_intent.json) is written BEFORE the first rename (write failure = pre-swap refusal) and transitions swapping -> committed_core / aborted / rollback_incomplete / failed_state_unknown; phase_publish REFUSES while a prior intent is unresolved. Probe-replicas: test_publish_systemexit_right_after_swap_rolls_back_via_disk_truth (the REAL publish() completes, SystemExit fires before any flag could be read — parent restored, approvals byte-identical, intent 'aborted', then re-raise), test_unresolved_intent_blocks_new_publish.
P0-2 (hash->ready window) -> the READY gate now runs: lease CAS -> cheap pins -> SEAL the generation read-only (_seal_tree_readonly: every file except the control-plane publish_state.json gets the read-only attribute) -> full content hash OVER THE SEALED TREE -> atomic marker write. Certified bytes are no longer writable by any attribute-respecting process (probe-replica: test_ready_seal_blocks_later_writes — writing a live bin after ready raises PermissionError). Tamper-class failures (manifest CAS, content root, in-tree raw manifest incl. its recomputed file-list self-root) transition the marker to 'suspect', which BLOCKS publish AND finalize; recovery is ONLY the explicit verified --restore-parent (verifies the .bak parent's manifest against the report, unseals, reverse-rebinds approvals child->parent via the pure planner, strips publish-added files, swaps back, proves parent ids live + 0 binding drift; exit 5 with journal on any incomplete step) — your disposition (no silent .bak auto-restore) followed exactly. Probe-replicas: test_ready_gate_refuses_bytes_changed_after_swap (-> suspect, finalize blocked), test_finalize_qa_cannot_green_changed_bytes_then_restore_parent (the full suspect -> restore-parent drill: parent live, approvals re-bound, 0 drift, child back at the staged path).
P0-3 (lock not bound to the shared data resource) -> store-mutating locks (raw_maintenance_lock + provider_publish_lock) derive their identity from the CANONICAL RESOLVED storage.data_root in config.yaml and live at <data_root>/.locks/ — a worktree, an independent clone, or a moved copy configured onto the same store resolves the same lock files; relative "./data" configs resolve per-checkout, which is CORRECT (genuinely separate stores). An unresolvable identity (missing/blank config) raises LockIdentityError — the publish REFUSES, never proceeds under a private namespace. The account-level api_call_lock (+ rate-spacing state) stays repo-anchored (the Tushare account is a per-machine resource, not a per-store one) — flag if you disagree. Probe-replicas: test_data_lock_identity_shared_across_checkouts (two independent clones -> one lock dir), test_data_lock_identity_unresolvable_refuses.
Major-1 (real SIGINT semantics) -> your option 1, documented honestly everywhere (_defer_sigint docstring, phase_publish, CLAUDE 3.4): a REAL SIGINT during swap+bind is deferred — the consistent core COMMITS (swap + rebind + pending_qa + records), KeyboardInterrupt raises at span exit, and --finalize-qa resumes; in-flow RAISED exceptions/interrupts (crash-like: SystemExit, injected KeyboardInterrupt) take the verified rollback then re-raise. Pinned with a TRUE-signal test: signal.raise_signal(SIGINT) delivered mid-rebind -> core committed + quarantined, then finalize -> ready (test_real_sigint_defers_commits_core_then_finalize).
Major-2 (concurrent QA overwrites ready) -> QA attempt LEASE: _begin_qa_attempt registers a last-starter-wins active_qa_attempt under the publish lock; BOTH completion paths (_record_qa_failure and _finalize_ready) CAS the lease + build + non-ready state under the same lock before writing; a stale worker logs 'superseded' (exit 7) and writes NOTHING. Probe-replica: test_stale_qa_worker_cannot_overwrite_ready (stale failure after a newer worker reached ready -> 7, state stays ready).
Major-3 (orphaned publish record) -> records are per-transaction: publish_record_<txid>.json is canonical (the pending_qa marker carries transaction_id; finalize locates the record through it); the fixed-name file is a human convenience copy. Rollback cleanup is DISK-DRIVEN: per-tx record + the precomputed rebind-md path are unlinked unconditionally (missing_ok), and the fixed-name copy is deleted only when its recorded transaction_id matches this transaction — no in-process booleans anywhere in the cleanup path.
Doc-accuracy note you raised -> the READY gate now RECOMPUTES the in-tree raw manifest's file-list self-root (_manifest_root(files) == root) in addition to the root-vs-report equality; the docs no longer overclaim.

YOUR PREFLIGHT CHECKLIST (status)
1. P0 fixes + the three named regressions — DONE this round (all probe-replicas listed above are committed tests).
2. Full drill on a disposable same-volume data copy (publish -> rollback -> qa_failed -> finalize -> concurrent-QA lease -> suspect -> restore-parent) — OPERATOR ACTION, pending; the driver is copy-config-driven so the drill needs no code changes.
3. Measure the three full-tree hash passes (wall clock, peak memory, free disk) on the real tree and archive the results — OPERATOR ACTION, pending.
4. Gated reads refuse in ALL THREE quarantine states — DONE (pending_qa / qa_failed / suspect each pinned in the gate battery, at both chokepoints).
5. Separate §13 authorization for the live run only after 1-4 — agreed and recorded.

VERIFICATION (this round)
Focused battery 200 green (+11 probe replicas). Combined four suites: 1076 green / 16 skipped; the failure set is file-by-file identical to the environmental baseline you have inspected across all rounds. Store-lock relocation note: raw/publish lock files move from logs/locks to <data_root>/.locks on merge (old files become inert). No live-provider touch this session.

WHAT CHANGED (authoritative — the full fix diff, commit 3e70e4a):

```diff
diff --git a/scripts/monthly_calendar_bump.py b/scripts/monthly_calendar_bump.py
index fa1915c..ba65842 100644
--- a/scripts/monthly_calendar_bump.py
+++ b/scripts/monthly_calendar_bump.py
@@ -417,12 +417,15 @@ from contextlib import contextmanager
 
 @contextmanager
 def _defer_sigint(span: str):
-    """Defer Ctrl-C across the CRITICAL transaction span (re-review P0: an interrupt
-    landing between two approval writes previously bypassed the `except Exception`
-    rollback and left a half-rebound live provider). SIGINT received inside the span is
-    recorded and re-raised as KeyboardInterrupt at span exit — after the swap+bind (or
-    their verified rollback) completed. No-op outside the main thread (signal handlers
-    are main-thread-only; the BaseException handler remains the belt there)."""
+    """Defer Ctrl-C across the CRITICAL transaction span. SEMANTICS (re-review #3,
+    documented honestly): a REAL SIGINT during the span does NOT roll back — the span
+    runs to completion (the consistent core transaction COMMITS: swap + rebind +
+    pending_qa marker + records), and KeyboardInterrupt is raised at span exit; the
+    operator resumes with --finalize-qa. This is deliberate: aborting mid-span is the
+    hazard, a committed-but-quarantined core is safe. In-flow exceptions/interrupts
+    RAISED inside the span (crash-like: SystemExit, injected KeyboardInterrupt) are
+    handled by the BaseException rollback instead. No-op outside the main thread
+    (signal handlers are main-thread-only; the BaseException belt still applies)."""
     import signal
     import threading
     if threading.current_thread() is not threading.main_thread():
@@ -730,29 +733,149 @@ def _write_journal(journal: dict) -> None:
         logger.error("journal write failed (non-fatal breadcrumb): %s", exc)
 
 
+def _read_publish_state(qlib_dir) -> dict:
+    """The parsed marker, or {} when absent/unreadable (callers treat unknown as refusal)."""
+    p = Path(qlib_dir) / "metadata" / "publish_state.json"
+    try:
+        payload = json.loads(p.read_text(encoding="utf-8"))
+        return payload if isinstance(payload, dict) else {}
+    except (OSError, json.JSONDecodeError):
+        return {}
+
+
 def _write_publish_state(qlib_dir, state: str, build_id: str, **extra) -> None:
     """Atomic publish-state marker write (<qlib_dir>/metadata/publish_state.json — the B6
-    QA quarantine read by release_gate.assert_provider_publish_state)."""
+    QA quarantine read by release_gate.assert_provider_publish_state). Carries the
+    transaction id and the active QA attempt forward from the current marker unless the
+    caller overrides them (re-review #3: state transitions must stay attributable)."""
     meta = Path(qlib_dir) / "metadata"
     meta.mkdir(parents=True, exist_ok=True)
+    current = _read_publish_state(qlib_dir)
     payload = {"state": state, "provider_build_id": build_id,
-               "updated_cst": now_cst().isoformat(timespec="seconds"), **extra}
+               "updated_cst": now_cst().isoformat(timespec="seconds")}
+    for carried in ("transaction_id", "active_qa_attempt"):
+        if carried in current:
+            payload[carried] = current[carried]
+    payload.update(extra)
     _atomic_write_bytes(meta / "publish_state.json",
                         json.dumps(payload, ensure_ascii=False, indent=1).encode("utf-8"))
 
 
+# ── re-review #3: durable intent journal + disk-truth swap classification ────
+def _read_intent() -> dict:
+    try:
+        payload = json.loads(TRANSACTION_INTENT_PATH.read_text(encoding="utf-8"))
+        return payload if isinstance(payload, dict) else {}
+    except (OSError, json.JSONDecodeError):
+        return {}
+
+
+def _write_intent(payload: dict) -> None:
+    OUT_DIR.mkdir(parents=True, exist_ok=True)
+    payload = {**payload, "updated_cst": now_cst().isoformat(timespec="seconds")}
+    _atomic_write_bytes(TRANSACTION_INTENT_PATH,
+                        json.dumps(payload, ensure_ascii=False, indent=1).encode("utf-8"))
+
+
+def _disk_swap_state(builder, parent_pb: str) -> str:
+    """'child_live' | 'parent_live' | 'unknown' — classified from DISK FACTS (live
+    manifest + backup dir), never from in-process booleans (re-review #3 P0: an exception
+    landing between publish() returning and a flag assignment mis-classified a live child
+    as pre-swap and skipped the rollback)."""
+    qlib = Path(builder.paths.qlib_dir)
+    backup = os.path.isdir(f"{builder.paths.qlib_dir}.bak_{builder.build_id}")
+    try:
+        live = json.loads((qlib / "metadata" / "provider_build.json")
+                          .read_text(encoding="utf-8")).get("provider_build_id")
+    except (OSError, json.JSONDecodeError):
+        live = None  # post-swap pre-emit: the child tree carries no manifest yet
+    if backup and live != parent_pb:
+        return "child_live"
+    if not backup and live == parent_pb:
+        return "parent_live"
+    return "unknown"
+
+
+# ── re-review #3: read-only generation seal (the READY-gate immutability) ────
+def _seal_tree_readonly(qlib_dir, exclude_names: tuple = ("publish_state.json",)) -> int:
+    """Set every file in the tree read-only EXCEPT the control-plane marker. Sealing
+    happens BEFORE the READY-gate content hash, so the certified bytes cannot be modified
+    by any attribute-respecting writer after certification (re-review #3 P0: 'one more
+    hash' cannot close the hash->ready window on a mutable tree). Returns files sealed."""
+    import stat
+    n = 0
+    for p in Path(qlib_dir).rglob("*"):
+        if p.is_file() and p.name not in exclude_names:
+            os.chmod(p, stat.S_IREAD)
+            n += 1
+    return n
+
+
+def _unseal_tree(qlib_dir) -> int:
+    """Clear the read-only seal (used by --restore-parent before undoing a publish)."""
+    import stat
+    n = 0
+    for p in Path(qlib_dir).rglob("*"):
+        if p.is_file():
+            os.chmod(p, stat.S_IREAD | stat.S_IWRITE)
+            n += 1
+    return n
+
+
+# ── re-review #3: QA attempt lease (a stale worker must never overwrite state) ─
+def _begin_qa_attempt(builder, rep: dict) -> str | None:
+    """Register THIS worker as the active QA attempt (last-starter-wins lease) under the
+    publish lock. Returns the attempt id, or None when the marker/build state does not
+    admit a QA attempt."""
+    import uuid
+    from data_infra.tushare_lock import provider_publish_lock
+    with provider_publish_lock():
+        marker = _read_publish_state(builder.paths.qlib_dir)
+        if (marker.get("state") not in ("pending_qa", "qa_failed")
+                or marker.get("provider_build_id") != rep["staged_build_id"]):
+            return None
+        attempt = uuid.uuid4().hex[:16]
+        _write_publish_state(builder.paths.qlib_dir, marker["state"], rep["staged_build_id"],
+                             active_qa_attempt=attempt)
+        return attempt
+
+
+def _record_qa_failure(builder, rep: dict, attempt: str, qa_rc: int, j) -> int:
+    """Persist qa_failed ONLY if this worker still holds the lease and the live state is
+    still non-ready for the same build — a stale worker records 'superseded' and changes
+    NOTHING (re-review #3 Major: a delayed failing QA overwrote a newer 'ready')."""
+    from data_infra.tushare_lock import provider_publish_lock
+    with provider_publish_lock():
+        marker = _read_publish_state(builder.paths.qlib_dir)
+        if (marker.get("active_qa_attempt") != attempt
+                or marker.get("provider_build_id") != rep["staged_build_id"]
+                or marker.get("state") not in ("pending_qa", "qa_failed")):
+            j("qa", "superseded", attempt=attempt, marker_state=marker.get("state"),
+              marker_attempt=marker.get("active_qa_attempt"))
+            logger.warning("stale QA attempt %s superseded (marker state=%r attempt=%r) — "
+                           "recording nothing.", attempt, marker.get("state"),
+                           marker.get("active_qa_attempt"))
+            return 7
+        _write_publish_state(builder.paths.qlib_dir, "qa_failed", rep["staged_build_id"],
+                             qa_returncode=qa_rc)
+    j("qa", "failed", returncode=qa_rc, attempt=attempt)
+    logger.critical("PUBLISHED but post-publish QA FAILED (exit %d) — the provider stays live "
+                    "but publish-state 'qa_failed' QUARANTINES gated reads until "
+                    "--finalize-qa passes. Parent retained as .bak.", qa_rc)
+    return 6
+
+
 def _run_post_publish_qa() -> int:
     import subprocess
     py = str(PROJECT_ROOT / "venv" / "Scripts" / "python.exe")
     return subprocess.run([py, str(PROJECT_ROOT / "scripts" / "run_daily_qa.py")]).returncode
 
 
-def _write_rebind_record(*, new_pb: str, new_cp: str, old_pb: str, old_cp: str,
+def _write_rebind_record(*, path: Path, new_pb: str, new_cp: str, old_pb: str, old_cp: str,
                          n_files: int, raw_root: str, raw_files: int, backup_dir: str) -> Path:
     """Committed governance record of the rebind (mirrors the 2026-07-01/2026-07-04
-    precedent .md files). Same-build-id retries overwrite their own record."""
-    date = now_cst().strftime("%Y-%m-%d")
-    path = APPROVALS_DIR / f"{date}_rebind_to_{new_pb}.md"
+    precedent .md files). The PATH is computed once by the transaction (before the
+    protected domain) so rollback cleanup can address it from disk without booleans."""
     body = (
         f"# Re-bind to the monthly thaw publish ({new_pb} / {new_cp})\n\n"
         f"Written by the ATOMIC publish transaction (`scripts/monthly_calendar_bump.py "
@@ -1066,6 +1189,7 @@ DRYRUN_REPORT_PATH = OUT_DIR / "monthly_bump_dryrun_report.json"
 FRESH_AUDIT_PATH = OUT_DIR / "fresh_window_survivorship_audit.json"
 PUBLISH_RECORD_PATH = OUT_DIR / "publish_record.json"
 TRANSACTION_JOURNAL_PATH = OUT_DIR / "publish_transaction_journal.json"
+TRANSACTION_INTENT_PATH = OUT_DIR / "publish_intent.json"
 RAW_MANIFEST_PATH = OUT_DIR / "raw_input_manifest.json"
 
 
@@ -1401,6 +1525,24 @@ def phase_publish(args) -> int:
     with raw_maintenance_lock(), provider_publish_lock():
         # ── VERIFY: every attestation re-checked here, IMMEDIATELY before the swap, with
         # no lock release in between (the verify↔swap inseparability is the transaction).
+        # re-review #3: refuse over an UNRESOLVED prior transaction (durable intent journal)
+        # or a live provider whose marker is not settled — a suspect/pending/qa_failed
+        # provider must be finalized or restored before any new publish.
+        intent = _read_intent()
+        if intent.get("status") in ("swapping", "rollback_incomplete", "failed_state_unknown"):
+            logger.error("UNRESOLVED prior transaction %s (status=%s) — resolve it first "
+                         "(--finalize-qa / --restore-parent / manual per %s). Refusing.",
+                         intent.get("transaction_id"), intent.get("status"),
+                         TRANSACTION_JOURNAL_PATH)
+            j("verify", "refused", reason="unresolved_intent")
+            return 2
+        live_marker = _read_publish_state(PROJECT_ROOT / "data" / "qlib_data")
+        if live_marker and live_marker.get("state") != "ready":
+            logger.error("live provider publish-state is %r — finalize (--finalize-qa) or "
+                         "restore (--restore-parent) before a new publish. Refusing.",
+                         live_marker.get("state"))
+            j("verify", "refused", reason=f"live_state_{live_marker.get('state')}")
+            return 2
         live_build, live_policy = live_provider_ids()
         if live_build != rep["parent_build_id"] or live_policy != rep["parent_policy_id"]:
             logger.error("PARENT DRIFT — live provider is build=%s/policy=%s but the reviewed report "
@@ -1542,21 +1684,34 @@ def phase_publish(args) -> int:
                     live_build, live_policy, manifest["root"], manifest["file_count"],
                     att["root"], att["file_count"], git_head[:12])
 
-        # ── SWAP + BIND under DEFERRED SIGINT (re-review P0: a Ctrl-C between two approval
-        # writes previously bypassed the `except Exception` rollback). The swap primitive
-        # self-rolls-back single-rename failures, so a bounded retry vs transient Windows
-        # handle locks is safe; a double failure (live missing) is NEVER retried. From
-        # swap-success onward EVERY operation runs inside ONE protected domain whose
-        # handler catches BaseException — interrupts included — restores the approval
-        # bytes, deletes this transaction's artifacts, strips the post-swap files from the
-        # new tree, rolls the swap back, and VERIFIES every restoration before claiming
-        # exit 4; interrupts re-raise AFTER the verified rollback.
+        # ── SWAP + BIND. Interrupt semantics (re-review #3, documented honestly): a REAL
+        # SIGINT during this span is DEFERRED — the consistent core transaction (swap +
+        # rebind + pending_qa marker + records) COMMITS first, then KeyboardInterrupt is
+        # raised at span exit; the operator resumes with --finalize-qa. An in-flow
+        # exception/interrupt raised INSIDE the domain (crash-like) triggers the verified
+        # rollback and then re-raises. The handler classifies swap completion from DISK
+        # FACTS (live manifest + backup dir), never from an in-process boolean, and a
+        # durable INTENT journal is written before the first rename so an unresolved
+        # transaction blocks any later publish until recovered.
         from data_infra.pit_backend import BuildGateError
         import time as _time
-        swap_completed = False
+        import uuid
+        txid = uuid.uuid4().hex[:16]
+        journal["transaction_id"] = txid
+        record_path = OUT_DIR / f"publish_record_{txid}.json"
+        md_path = APPROVALS_DIR / f"{now_cst().strftime('%Y-%m-%d')}_rebind_to_{rep['staged_build_id']}.md"
+        try:
+            _write_intent({"transaction_id": txid, "status": "swapping",
+                           "parent_build_id": live_build, "parent_policy_id": live_policy,
+                           "child_build_id": rep["staged_build_id"],
+                           "backup_dir": f"{builder.paths.qlib_dir}.bak_{builder.build_id}",
+                           "staged_provider_dir": str(staged_dir),
+                           "record_path": str(record_path), "rebind_record_path": str(md_path)})
+        except Exception as exc:  # noqa: BLE001 — the durable intent MUST land before any rename
+            logger.error("cannot write the durable intent journal (%s) — refusing pre-swap.", exc)
+            j("verify", "refused", reason="intent_write_failed")
+            return 2
         written: list[Path] = []
-        record_md: Path | None = None
-        record_written = False
         with _defer_sigint("swap+bind"):
             try:
                 swap_exc: Exception | None = None
@@ -1582,13 +1737,14 @@ def phase_publish(args) -> int:
                     live_intact = os.path.isdir(builder.paths.qlib_dir)
                     j("swap", "failed", error=str(swap_exc), live_provider_intact=live_intact)
                     if live_intact:
+                        _write_intent({**_read_intent(), "status": "aborted"})
                         logger.error("swap failed after retries and the primitive rolled back — "
                                      "live provider intact: %s", swap_exc)
                         return 2
+                    _write_intent({**_read_intent(), "status": "failed_state_unknown"})
                     logger.critical("swap DOUBLE failure — live provider MISSING; follow the "
                                     "recovery move in the error: %s", swap_exc)
                     return 5
-                swap_completed = True
                 j("swap", "ok", backup=f"{builder.paths.qlib_dir}.bak_{builder.build_id}")
                 okm, why_m = _verify_live_manifest(
                     builder.paths.qlib_dir, build_id=rep["staged_build_id"],
@@ -1610,10 +1766,13 @@ def phase_publish(args) -> int:
                         f"{len(still)} approval(s) still drift after the rebind: {still[0].reasons()}")
                 # B6 QA quarantine: the provider is durable but NOT ready — gated reads
                 # refuse until the READY gate (QA pass + full pin re-verification) flips it.
+                # The marker carries the transaction id: finalize locates this
+                # transaction's record through it, and cleanup is disk-driven by txid.
                 _write_publish_state(builder.paths.qlib_dir, "pending_qa", rep["staged_build_id"],
-                                     parent_build_id=live_build)
+                                     parent_build_id=live_build, transaction_id=txid)
                 appr_post = _approvals_attestation()  # post-rebind pin the READY gate re-checks
                 record = {
+                    "transaction_id": txid,
                     "published_build_id": rep["staged_build_id"],
                     "calendar_policy_id": rep["new_policy_id"],
                     "parent_build_id": live_build, "parent_policy_id": live_policy,
@@ -1628,36 +1787,59 @@ def phase_publish(args) -> int:
                     "reviewed_dryrun_report": str(DRYRUN_REPORT_PATH),
                     "published_cst": now_cst().isoformat(timespec="seconds"),
                 }
-                _atomic_write_bytes(PUBLISH_RECORD_PATH,
-                                    json.dumps(record, ensure_ascii=False, indent=1).encode("utf-8"))
-                record_written = True
+                record_bytes = json.dumps(record, ensure_ascii=False, indent=1).encode("utf-8")
+                _atomic_write_bytes(record_path, record_bytes)   # canonical, per-transaction
+                _atomic_write_bytes(PUBLISH_RECORD_PATH, record_bytes)  # human convenience copy
                 # the committed governance record is written LAST — nothing may claim a
                 # completed rebind before every durable step above proved out (Blocker 2b).
-                record_md = _write_rebind_record(
+                _write_rebind_record(
+                    path=md_path,
                     new_pb=rep["staged_build_id"], new_cp=rep["new_policy_id"], old_pb=live_build,
                     old_cp=live_policy, n_files=len(written), raw_root=staged_raw["root"],
                     raw_files=staged_raw.get("file_count") or 0,
                     backup_dir=f"{builder.paths.qlib_dir}.bak_{builder.build_id}")
+                _write_intent({**_read_intent(), "status": "committed_core"})
                 j("bind", "ok", approvals_rebound=len(written))
             except BaseException as exc:  # noqa: BLE001 — interrupts included (re-review P0)
-                if not swap_completed:
+                # DISK-TRUTH classification (re-review #3 P0): never infer swap completion
+                # from an in-process boolean — an exception between publish() returning and
+                # a flag assignment would mis-classify a live child as pre-swap.
+                dstate = _disk_swap_state(builder, live_build)
+                if dstate == "parent_live":
                     # the primitive self-rolled-back (or the failure landed before any
                     # rename) — nothing durable mutated by THIS transaction.
+                    _write_intent({**_read_intent(), "status": "aborted"})
                     j("swap", "aborted_pre_completion", error=repr(exc))
-                    logger.critical("aborted before the swap completed (%r) — the primitive's "
-                                    "self-rollback applies; data/qlib_data is the parent.", exc)
+                    logger.critical("aborted before the swap completed (%r) — verified from "
+                                    "disk: data/qlib_data is the parent.", exc)
                     raise
+                if dstate == "unknown":
+                    j("swap", "failed_state_unknown", error=repr(exc))
+                    logger.critical("DISK STATE UNKNOWN after failure (%r) — neither parent-live "
+                                    "nor child-live signature matches; recover manually per the "
+                                    "intent journal (%s) + transaction journal (%s).",
+                                    exc, TRANSACTION_INTENT_PATH, TRANSACTION_JOURNAL_PATH)
+                    if isinstance(exc, (KeyboardInterrupt, SystemExit)):
+                        raise
+                    return 5
                 logger.error("post-swap step failed (%r) — restoring approvals + artifacts + "
                              "rolling the swap back.", exc)
                 problems: list[str] = []
                 problems += _restore_approval_files(written, originals)
-                for artifact, present in ((record_md, record_md is not None),
-                                          (PUBLISH_RECORD_PATH, record_written)):
-                    if present:
-                        try:
-                            Path(artifact).unlink(missing_ok=True)
-                        except OSError as uexc:
-                            problems.append(f"could not remove {artifact}: {uexc}")
+                # artifact cleanup is DISK-DRIVEN by transaction id — never gated on
+                # in-process booleans (re-review #3 Major: an interrupt after the record's
+                # atomic replace but before a flag left a false 'published' record behind).
+                for artifact in (record_path, md_path):
+                    try:
+                        Path(artifact).unlink(missing_ok=True)
+                    except OSError as uexc:
+                        problems.append(f"could not remove {artifact}: {uexc}")
+                try:  # the fixed-name copy: delete ONLY if it belongs to THIS transaction
+                    fixed = json.loads(PUBLISH_RECORD_PATH.read_text(encoding="utf-8"))
+                    if fixed.get("transaction_id") == txid:
+                        PUBLISH_RECORD_PATH.unlink(missing_ok=True)
+                except (OSError, json.JSONDecodeError):
+                    pass  # absent or foreign — nothing of ours to clean
                 # strip THIS transaction's post-swap files from the new tree so the returned
                 # staged tree matches its content attestation again for a clean retry
                 for name in ("provider_build.json", "publish_state.json"):
@@ -1677,6 +1859,8 @@ def phase_publish(args) -> int:
                         problems.append(f"post-rollback live manifest unreadable: {vexc}")
                 else:
                     problems.append(f"swap rollback failed: {rb_msg}")
+                _write_intent({**_read_intent(),
+                               "status": "aborted" if not problems else "rollback_incomplete"})
                 if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                     j("bind", "interrupted_rolled_back" if not problems
                       else "interrupted_rollback_incomplete", error=repr(exc),
@@ -1711,93 +1895,124 @@ _LIVE_PUBLISH_FILES = ("metadata/provider_build.json", "metadata/publish_state.j
 
 
 def _run_and_record_qa(builder, rep: dict, j) -> int:
-    """Run run_daily_qa, then hand the READY decision to :func:`_finalize_ready` (PASS) or
-    persist the quarantine (FAIL -> 'qa_failed', exit 6)."""
-    from data_infra.tushare_lock import provider_publish_lock
+    """Register a QA attempt LEASE, run run_daily_qa, then hand the READY decision to
+    :func:`_finalize_ready` (PASS) or persist the quarantine through the lease-checked
+    :func:`_record_qa_failure` (FAIL -> 'qa_failed', exit 6; stale worker -> 7)."""
+    attempt = _begin_qa_attempt(builder, rep)
+    if attempt is None:
+        logger.error("cannot begin a QA attempt — the marker/build state does not admit one.")
+        return 2
     qa_rc = _run_post_publish_qa()
     if qa_rc != 0:
-        with provider_publish_lock():
-            _write_publish_state(builder.paths.qlib_dir, "qa_failed", rep["staged_build_id"],
-                                 qa_returncode=qa_rc)
-        j("qa", "failed", returncode=qa_rc)
-        logger.critical("PUBLISHED but post-publish QA FAILED (exit %d) — the provider stays live "
-                        "but publish-state 'qa_failed' QUARANTINES gated reads until "
-                        "--finalize-qa passes. Parent retained as .bak.", qa_rc)
-        return 6
-    j("qa", "passed", returncode=0)
-    return _finalize_ready(builder, rep, j)
-
-
-def _finalize_ready(builder, rep: dict, j) -> int:
-    """The ONLY transition to publish-state 'ready' (re-review P0-3 + P0-4). Under the
-    transaction locks, EVERY pin is re-verified against the LIVE tree: the manifest CAS
-    (build/policy/raw-root/parent/execute-commit), the minted-policy file hash, the
-    post-rebind approvals set (vs the publish record), the in-tree raw manifest
-    self-consistency, and the FULL live content root vs the reviewed staged root
-    (excluding exactly the two files the publish itself adds). QA is a sampling check —
-    THIS is the proof; it closes the hash->swap TOCTOU window: a byte changed at ANY point
-    between the pre-swap attestation and this gate refuses 'ready' (quarantine persists,
-    exit 5)."""
+        return _record_qa_failure(builder, rep, attempt, qa_rc, j)
+    j("qa", "passed", returncode=0, attempt=attempt)
+    return _finalize_ready(builder, rep, j, attempt)
+
+
+def _finalize_ready(builder, rep: dict, j, attempt: str) -> int:
+    """The ONLY transition to publish-state 'ready' (re-review #2 P0-3/P0-4 + #3 P0-2).
+    Under the transaction locks: (0) the QA-attempt LEASE is CAS-checked (a stale worker
+    records 'superseded' and changes nothing, exit 7); (1) every cheap pin is re-verified
+    against the LIVE tree — manifest CAS (build/policy/raw-root/parent/execute-commit),
+    minted-policy file hash, post-rebind approvals set (vs this transaction's record,
+    located via the marker's transaction id), in-tree raw manifest (root AND file-list
+    self-root); (2) the payload is SEALED read-only (every file except the control-plane
+    marker) so no attribute-respecting writer can mutate it afterwards; (3) the FULL
+    sealed content is re-hashed and must equal the reviewed staged root. Tamper-class
+    failures (manifest CAS / content root) transition the marker to 'suspect' — which
+    blocks publish AND finalize until --restore-parent — and exit 5; softer pin problems
+    (records/policy/approvals) keep the current state for a retryable finalize, exit 5.
+    QA is a sampling check; THIS gate is the proof."""
     from data_infra.tushare_lock import provider_publish_lock, raw_maintenance_lock
     qlib_dir = Path(builder.paths.qlib_dir)
     with raw_maintenance_lock(), provider_publish_lock():
-        problems: list[str] = []
+        marker = _read_publish_state(qlib_dir)
+        if (marker.get("active_qa_attempt") != attempt
+                or marker.get("provider_build_id") != rep["staged_build_id"]
+                or marker.get("state") not in ("pending_qa", "qa_failed")):
+            j("ready", "superseded", attempt=attempt, marker_state=marker.get("state"),
+              marker_attempt=marker.get("active_qa_attempt"))
+            logger.warning("stale READY attempt %s superseded (marker state=%r attempt=%r) — "
+                           "changing nothing.", attempt, marker.get("state"),
+                           marker.get("active_qa_attempt"))
+            return 7
+        tamper: list[str] = []
+        soft: list[str] = []
         okm, why_m = _verify_live_manifest(
             qlib_dir, build_id=rep["staged_build_id"], policy_id=rep["new_policy_id"],
             raw_root=rep["raw_input_manifest_root"], parent_pb=rep["parent_build_id"],
             source_git_commit=rep["source_git_commit"])
         if not okm:
-            problems.append(f"live manifest CAS failed: {why_m}")
+            tamper.append(f"live manifest CAS failed: {why_m}")
         policy_file = POLICY_DIR / f"{rep['new_policy_id']}.yaml"
         if not policy_file.is_file() or _sha256_file(policy_file) != rep["new_policy_sha256"]:
-            problems.append("minted policy file hash drifted since the reviewed report")
-        try:
-            record = json.loads(PUBLISH_RECORD_PATH.read_text(encoding="utf-8"))
-        except (OSError, json.JSONDecodeError) as exc:
-            record = {}
-            problems.append(f"publish record unreadable: {exc}")
-        if record.get("published_build_id") != rep["staged_build_id"]:
-            problems.append("publish record does not describe this build")
+            soft.append("minted policy file hash drifted since the reviewed report")
+        txid = marker.get("transaction_id")
+        record: dict = {}
+        if not txid:
+            soft.append("marker carries no transaction_id — cannot locate this publish's record")
+        else:
+            try:
+                record = json.loads((OUT_DIR / f"publish_record_{txid}.json")
+                                    .read_text(encoding="utf-8"))
+            except (OSError, json.JSONDecodeError) as exc:
+                soft.append(f"publish record for transaction {txid} unreadable: {exc}")
+        if record and record.get("published_build_id") != rep["staged_build_id"]:
+            soft.append("publish record does not describe this build")
         appr = _approvals_attestation()
         if appr["bound_count"] < 1 or appr["root"] != record.get("approvals_post_rebind_root"):
-            problems.append("approvals governance set drifted since the rebind")
+            soft.append("approvals governance set drifted since the rebind")
         try:
             live_raw = json.loads((qlib_dir / "metadata" / "raw_input_manifest.json")
                                   .read_text(encoding="utf-8"))
-            if live_raw.get("root") != rep["raw_input_manifest_root"]:
-                problems.append("in-tree raw manifest root != the reviewed raw root")
+            if (live_raw.get("root") != rep["raw_input_manifest_root"]
+                    or _manifest_root(live_raw.get("files", [])) != live_raw.get("root")):
+                tamper.append("in-tree raw manifest root/file-list inconsistent with the review")
         except (OSError, json.JSONDecodeError) as exc:
-            problems.append(f"in-tree raw manifest unreadable: {exc}")
-        if not problems:
-            logger.info("READY gate: FULL live-content re-verification (%s files) ...",
+            tamper.append(f"in-tree raw manifest unreadable: {exc}")
+        if not tamper and not soft:
+            # SEAL the generation BEFORE the certifying hash (re-review #3 P0-2: one more
+            # hash cannot close the hash->ready window on a mutable tree). The marker file
+            # stays writable — it is the control plane the pointer lives in.
+            sealed = _seal_tree_readonly(qlib_dir)
+            logger.info("READY gate: sealed %d files read-only; FULL sealed-content "
+                        "re-verification (%s files) ...", sealed,
                         rep.get("staged_content_file_count"))
             att = _staged_content_attestation(
                 qlib_dir, exclude=_LIVE_PUBLISH_FILES,
                 build_manifest_path=Path(builder.paths.build_root) / "manifest.json")
             if att["root"] != rep["staged_content_root"]:
-                problems.append(
-                    f"LIVE content root {att['root']} != reviewed {rep['staged_content_root']} — "
-                    "the published bytes changed since the audited build")
-        if problems:
-            j("ready", "refused", problems=problems)
-            logger.critical("READY REFUSED — the provider STAYS QUARANTINED. Problems: %s. "
-                            "Investigate; if the published bytes are compromised, restore the "
-                            "parent from the .bak per the journal (%s).",
-                            problems, TRANSACTION_JOURNAL_PATH)
+                tamper.append(
+                    f"SEALED content root {att['root']} != reviewed {rep['staged_content_root']}"
+                    " — the published bytes changed since the audited build")
+        if tamper:
+            _write_publish_state(qlib_dir, "suspect", rep["staged_build_id"],
+                                 reason=tamper[0])
+            j("ready", "refused_suspect", problems=tamper + soft)
+            logger.critical("READY REFUSED — TAMPER-CLASS failure; publish-state 'suspect' now "
+                            "BLOCKS publish AND finalize until --restore-parent. Problems: %s "
+                            "(journal %s).", tamper + soft, TRANSACTION_JOURNAL_PATH)
+            return 5
+        if soft:
+            j("ready", "refused", problems=soft)
+            logger.critical("READY REFUSED — records/pins incomplete (state unchanged; fix and "
+                            "re-run --finalize-qa). Problems: %s.", soft)
             return 5
-        _write_publish_state(qlib_dir, "ready", rep["staged_build_id"], qa_returncode=0)
-    j("ready", "ok")
-    logger.info("publish-state 'ready' — QA passed AND every pin re-verified against the live "
-                "tree. Publish record: %s", PUBLISH_RECORD_PATH)
+        _write_publish_state(qlib_dir, "ready", rep["staged_build_id"], qa_returncode=0,
+                             qa_attempt=attempt)
+    j("ready", "ok", attempt=attempt)
+    logger.info("publish-state 'ready' — QA passed AND every pin re-verified against the SEALED "
+                "live tree. Publish record: %s", PUBLISH_RECORD_PATH)
     return 0
 
 
 def phase_finalize_qa(args) -> int:
     """Re-run the QA + READY-gate leg for a provider stuck in 'pending_qa'/'qa_failed'
-    (crash between swap and QA, or a QA failure now resolved). CAS-verifies the live
-    manifest against the reviewed report BEFORE running QA, and the full READY gate
-    (:func:`_finalize_ready` — content root included) decides afterwards; a provider whose
-    bytes changed since the review can NEVER be marked ready by this path."""
+    (crash between swap and QA — including a deferred-SIGINT commit-core — or a QA failure
+    now resolved). CAS-verifies the live manifest against the reviewed report BEFORE
+    running QA; the full READY gate (:func:`_finalize_ready` — lease + seal + content root)
+    decides afterwards; a provider whose bytes changed since the review can NEVER be
+    marked ready by this path (it transitions to 'suspect' instead)."""
     if not DRYRUN_REPORT_PATH.exists():
         logger.error("no dry-run report at %s — nothing to finalize.", DRYRUN_REPORT_PATH)
         return 2
@@ -1818,14 +2033,10 @@ def phase_finalize_qa(args) -> int:
                          "finishes the publish this report describes. Refusing.",
                          live_build, rep["staged_build_id"])
             return 2
-        state_file = Path(builder.paths.qlib_dir) / "metadata" / "publish_state.json"
-        try:
-            state = json.loads(state_file.read_text(encoding="utf-8")).get("state")
-        except (OSError, json.JSONDecodeError):
-            state = None
+        state = _read_publish_state(builder.paths.qlib_dir).get("state")
         if state not in ("pending_qa", "qa_failed"):
-            logger.error("publish-state is %r — --finalize-qa only applies to pending_qa/qa_failed.",
-                         state)
+            logger.error("publish-state is %r — --finalize-qa only applies to pending_qa/"
+                         "qa_failed (a 'suspect' provider requires --restore-parent).", state)
             return 2
         okm, why_m = _verify_live_manifest(
             builder.paths.qlib_dir, build_id=rep["staged_build_id"],
@@ -1846,6 +2057,118 @@ def phase_finalize_qa(args) -> int:
     return _run_and_record_qa(builder, rep, j)
 
 
+def phase_restore_parent(args) -> int:
+    """EXPLICIT recovery from a quarantined/suspect publish (re-review #3 disposition:
+    never silently auto-restore; provide a verified command instead). Under the
+    transaction locks: verifies the live build is the report's child AND the .bak parent's
+    manifest matches the report's parent ids; unseals the (possibly sealed) child tree;
+    reverse-rebinds the approval YAMLs child->parent (pure plan first, byte-verified);
+    strips the publish-added files; swaps the parent back; verifies parent ids live +
+    0 binding drift; clears the marker (it travels back with the child tree) and marks the
+    intent 'aborted'. Exit 0 only when every check passes; else 5 with the journal."""
+    if not DRYRUN_REPORT_PATH.exists():
+        logger.error("no dry-run report at %s — cannot verify the restore against a review.",
+                     DRYRUN_REPORT_PATH)
+        return 2
+    rep = json.loads(DRYRUN_REPORT_PATH.read_text(encoding="utf-8"))
+    builder = _make_publish_builder(rep["staged_build_id"])
+    from data_infra.tushare_lock import provider_publish_lock, raw_maintenance_lock
+
+    journal: dict = {"transaction": "restore_parent", "staged_build_id": rep["staged_build_id"],
+                     "steps": []}
+
+    def j(step: str, status: str, **info) -> None:
+        journal["steps"].append({"step": step, "status": status,
+                                 "ts_cst": now_cst().isoformat(timespec="seconds"), **info})
+        _write_journal(journal)
+
+    with raw_maintenance_lock(), provider_publish_lock():
+        qlib_dir = Path(builder.paths.qlib_dir)
+        live_build, live_policy = live_provider_ids()
+        if live_build != rep["staged_build_id"]:
+            logger.error("live build %s is not the report's child %s — nothing to restore.",
+                         live_build, rep["staged_build_id"])
+            return 2
+        state = _read_publish_state(qlib_dir).get("state")
+        if state not in ("suspect", "pending_qa", "qa_failed"):
+            logger.error("publish-state is %r — --restore-parent only undoes an uncertified "
+                         "publish (suspect/pending_qa/qa_failed).", state)
+            return 2
+        backup_dir = Path(f"{builder.paths.qlib_dir}.bak_{builder.build_id}")
+        try:
+            bak_manifest = json.loads((backup_dir / "metadata" / "provider_build.json")
+                                      .read_text(encoding="utf-8"))
+        except (OSError, json.JSONDecodeError) as exc:
+            logger.error("backup parent manifest unreadable at %s (%s) — refusing.", backup_dir, exc)
+            return 2
+        if (bak_manifest.get("provider_build_id") != rep["parent_build_id"]
+                or bak_manifest.get("calendar_policy_id") != rep["parent_policy_id"]):
+            logger.error("backup at %s is NOT the report's parent (%s/%s) — refusing.",
+                         backup_dir, rep["parent_build_id"], rep["parent_policy_id"])
+            return 2
+        try:
+            reverse_plan, current_bytes = _plan_rebind(
+                rep["staged_build_id"], rep["new_policy_id"],
+                rep["parent_build_id"], rep["parent_policy_id"])
+        except PublishTransactionError as exc:
+            logger.error("reverse rebind planning refused (%s) — approvals are not uniformly "
+                         "bound to the child; repair from git first.", exc)
+            return 2
+        j("restore", "verified_preconditions", state=state)
+        problems: list[str] = []
+        unsealed = _unseal_tree(qlib_dir)
+        j("restore", "unsealed", files=unsealed)
+        written: list[Path] = []
+        try:
+            for p, nd in reverse_plan:
+                _atomic_write_bytes(p, nd)
+                written.append(p)
+        except Exception as exc:  # noqa: BLE001
+            problems += _restore_approval_files(written, current_bytes)
+            problems.append(f"reverse rebind failed: {exc}")
+        if not problems:
+            txid = _read_publish_state(qlib_dir).get("transaction_id")
+            for name in ("provider_build.json", "publish_state.json"):
+                try:
+                    (qlib_dir / "metadata" / name).unlink(missing_ok=True)
+                except OSError as uexc:
+                    problems.append(f"could not remove new-tree {name}: {uexc}")
+            ok_rb, rb_msg = _rollback_swap(builder)
+            if not ok_rb:
+                problems.append(f"swap-back failed: {rb_msg}")
+            else:
+                try:
+                    rb_build, rb_policy = live_provider_ids()
+                    if (rb_build, rb_policy) != (rep["parent_build_id"], rep["parent_policy_id"]):
+                        problems.append(f"post-restore live ids ({rb_build}/{rb_policy}) != parent")
+                except Exception as vexc:  # noqa: BLE001
+                    problems.append(f"post-restore live manifest unreadable: {vexc}")
+                from data_infra.approval_evidence import evaluate_approval_evidence_bindings
+                drifts = evaluate_approval_evidence_bindings(
+                    approvals_dir=APPROVALS_DIR,
+                    manifest_path=qlib_dir / "metadata" / "provider_build.json")
+                still = [d for d in drifts if d.drift]
+                if still:
+                    problems.append(f"{len(still)} approvals still drift after the restore")
+                if txid:
+                    for artifact in (OUT_DIR / f"publish_record_{txid}.json",):
+                        try:
+                            artifact.unlink(missing_ok=True)
+                        except OSError as uexc:
+                            problems.append(f"could not remove {artifact}: {uexc}")
+        _write_intent({**_read_intent(), "status": "aborted" if not problems
+                       else "rollback_incomplete"})
+        if problems:
+            j("restore", "incomplete", problems=problems)
+            logger.critical("RESTORE INCOMPLETE — resolve manually per the journal (%s): %s",
+                            TRANSACTION_JOURNAL_PATH, problems)
+            return 5
+        j("restore", "ok")
+    logger.info("RESTORED: the parent provider is live again; the child sits back at the staged "
+                "path for investigation. Approvals re-bound to the parent (0 drift).")
+    return 0
+
+
 def main() -> int:
     ap = argparse.ArgumentParser(description="Monthly calendar freeze-bump driver")
     ap.add_argument("--plan", action="store_true", help="Preflight + target_end + plan only")
@@ -1857,9 +2180,14 @@ def main() -> int:
     ap.add_argument("--i-reviewed-the-dryrun", action="store_true",
                     help="Attest the dry-run report was reviewed (required for --publish-approved)")
     ap.add_argument("--finalize-qa", action="store_true",
-                    help="Re-run the post-publish QA leg for a provider quarantined at "
-                         "pending_qa/qa_failed (crash between swap and QA, or a resolved QA "
-                         "failure); flips publish-state to 'ready' on PASS")
+                    help="Re-run the post-publish QA + READY-gate leg for a provider "
+                         "quarantined at pending_qa/qa_failed (crash/deferred-SIGINT between "
+                         "swap and QA, or a resolved QA failure); flips publish-state to "
+                         "'ready' only after the full sealed-content re-verification")
+    ap.add_argument("--restore-parent", action="store_true",
+                    help="EXPLICIT verified recovery: undo an uncertified publish "
+                         "(suspect/pending_qa/qa_failed) — reverse-rebind approvals, swap the "
+                         ".bak parent back live, verify parent ids + 0 binding drift")
     ap.add_argument("--target-end", type=str, default=None, help="Override target_end (YYYYMMDD)")
     ap.add_argument("--allow-migration-exception", action="store_true",
                     help="Acknowledge that a frozen-prefix exception type recurring 2+ bumps has "
@@ -1876,8 +2204,10 @@ def main() -> int:
         return phase_publish(args)
     if args.finalize_qa:
         return phase_finalize_qa(args)
+    if args.restore_parent:
+        return phase_restore_parent(args)
     logger.error("choose a mode: --plan (review) | --execute (multi-hour, stops before publish) | "
-                 "--publish-approved --i-reviewed-the-dryrun | --finalize-qa")
+                 "--publish-approved --i-reviewed-the-dryrun | --finalize-qa | --restore-parent")
     return 2
 
 
diff --git a/src/data_infra/tushare_lock.py b/src/data_infra/tushare_lock.py
index 0d0daa2..6212007 100644
--- a/src/data_infra/tushare_lock.py
+++ b/src/data_infra/tushare_lock.py
@@ -43,7 +43,19 @@ from filelock import FileLock, Timeout  # noqa: F401 — Timeout re-exported for
 _SOURCE_ROOT = Path(__file__).resolve().parents[2]
 
 
+class LockIdentityError(RuntimeError):
+    """The shared-store lock identity could not be resolved — data-root-guarding locks
+    REFUSE instead of degrading to a per-checkout namespace (GPT re-review #3 P0: two
+    independent clones configured onto ONE data root must share one lock; when the
+    identity is unknowable the safe action is to not mutate the store at all)."""
+
+
 def _resolve_lock_root(source_root: Path) -> Path:
+    """Repo-scoped lock root for the ACCOUNT-level lock (api_call_lock + rate spacing):
+    the git COMMON dir's parent — identical for every worktree of a repo, equal to the
+    checkout root for a plain clone. Best-effort by design (the Tushare account is a
+    per-machine resource, not a per-store one); data-store-guarding locks use
+    :func:`_resolve_data_lock_dir` instead, which is FAIL-CLOSED."""
     import logging
     import subprocess
     try:
@@ -60,9 +72,8 @@ def _resolve_lock_root(source_root: Path) -> Path:
         return common.parent
     except Exception:  # noqa: BLE001 — degraded per-checkout namespace, loudly
         logging.getLogger(__name__).warning(
-            "git common-dir resolution failed under %s — lock namespace degrades to this "
-            "checkout only (cross-worktree publishers would NOT exclude each other).",
-            source_root,
+            "git common-dir resolution failed under %s — the ACCOUNT lock namespace "
+            "degrades to this checkout only.", source_root,
         )
         return source_root
 
@@ -70,11 +81,57 @@ def _resolve_lock_root(source_root: Path) -> Path:
 _LOCK_DIR = _resolve_lock_root(_SOURCE_ROOT) / "logs" / "locks"
 
 
+def _resolve_data_lock_dir(source_root: Path) -> Path:
+    """Lock directory for locks that guard the SHARED DATA STORE (raw maintenance +
+    provider publish): derived from the CANONICAL RESOLVED data root in config.yaml, and
+    physically located INSIDE it (``<data_root>/.locks``) — so any checkout (worktree,
+    independent clone, moved copy) configured onto the same store resolves the same lock
+    files (GPT re-review #3 P0: git-common-dir only unifies worktrees of one repo; two
+    clones sharing a data root still got two namespaces). FAIL-CLOSED: an unreadable
+    config / unresolvable data root raises :class:`LockIdentityError` — a store-mutating
+    caller must refuse, never proceed under a private lock namespace."""
+    try:
+        import yaml
+        with open(source_root / "config.yaml", "r", encoding="utf-8") as fh:
+            cfg = yaml.safe_load(fh) or {}
+        raw = ((cfg.get("storage") or {}).get("data_root"))
+        if not raw or not str(raw).strip():
+            raise LockIdentityError(
+                f"config.yaml under {source_root} declares no storage.data_root — cannot "
+                "derive the shared-store lock identity; refusing (fail closed)."
+            )
+        root = Path(str(raw))
+        if not root.is_absolute():
+            root = (source_root / root)
+        return root.resolve() / ".locks"
+    except LockIdentityError:
+        raise
+    except Exception as exc:  # noqa: BLE001 — unreadable config = unknowable identity
+        raise LockIdentityError(
+            f"cannot resolve the shared data root from {source_root / 'config.yaml'}: {exc} "
+            "— store-mutating locks refuse (fail closed)."
+        ) from exc
+
+
 def _lock_dir() -> Path:
     _LOCK_DIR.mkdir(parents=True, exist_ok=True)
     return _LOCK_DIR
 
 
+# Resolved lazily from config.yaml storage.data_root (see _resolve_data_lock_dir). Tests
+# inject isolation by assigning this module attribute directly (a Path), never via env.
+_DATA_LOCK_DIR = None
+
+
+def _data_lock_dir() -> Path:
+    global _DATA_LOCK_DIR
+    if _DATA_LOCK_DIR is None:
+        _DATA_LOCK_DIR = _resolve_data_lock_dir(_SOURCE_ROOT)
+    d = Path(_DATA_LOCK_DIR)
+    d.mkdir(parents=True, exist_ok=True)
+    return d
+
+
 def _filelock(name: str, timeout: float) -> FileLock:
     return FileLock(str(_lock_dir() / name), timeout=timeout)
 
@@ -87,18 +144,25 @@ def api_call_lock(timeout: float = 1800.0):
 
 @contextmanager
 def raw_maintenance_lock(timeout: float = 21600.0):  # 6h default — a monthly catch-up can run hours
-    """Process-exclusive raw-layer maintenance, held on the REAL kernel lock (no env barrier). Pass a
-    SHORT timeout in an unattended job (the daily raw job) so it fails fast + retries instead of
-    blocking behind a multi-hour monthly build until its own task time-limit kills it (GPT m3); on
-    timeout FileLock raises `Timeout` (re-exported above)."""
-    with _filelock("raw_maintenance.lock", timeout):
+    """Process-exclusive raw-layer maintenance, held on the REAL kernel lock (no env barrier).
+    Lock identity = the SHARED DATA ROOT (``<data_root>/.locks/raw_maintenance.lock``), so any
+    checkout configured onto the same store excludes any other; an unresolvable identity
+    raises :class:`LockIdentityError` (fail closed). Pass a SHORT timeout in an unattended job
+    (the daily raw job) so it fails fast + retries instead of blocking behind a multi-hour
+    monthly build until its own task time-limit kills it (GPT m3); on timeout FileLock raises
+    `Timeout` (re-exported above)."""
+    with FileLock(str(_data_lock_dir() / "raw_maintenance.lock"), timeout=timeout):
         yield
 
 
 @contextmanager
 def provider_publish_lock(timeout: float = 7200.0):
     """Process-exclusive LIVE-provider publish/swap + manifest writes (Phase 5-B B3; GPT
-    re-review Blocker 7 made this a GLOBAL publish lock, not a driver-private one).
+    re-review Blocker 7 made this a GLOBAL publish lock, not a driver-private one; re-review
+    #3 P0 anchored its identity to the SHARED DATA ROOT — ``<data_root>/.locks/`` — so two
+    independent clones configured onto one store share ONE lock; an unresolvable identity
+    raises :class:`LockIdentityError` and the publish REFUSES, never proceeds under a
+    private namespace).
 
     Held at the COMMON CHOKEPOINTS — ``StagedQlibBackendBuilder.publish()`` and the
     ``provider_build.json`` emitters in ``provider_manifest`` acquire it themselves — so ANY
@@ -111,7 +175,7 @@ def provider_publish_lock(timeout: float = 7200.0):
     deadlocking, while a second process still blocks. LOCK ORDER: any holder that also needs
     ``raw_maintenance_lock`` acquires raw FIRST, then this; publish-lock-only holders (the
     builder/emitters) never take the raw lock afterwards — no reverse-order path exists."""
-    lock = FileLock(str(_lock_dir() / "provider_publish.lock"), is_singleton=True)
+    lock = FileLock(str(_data_lock_dir() / "provider_publish.lock"), is_singleton=True)
     lock.acquire(timeout=timeout)
     try:
         yield
diff --git a/tests/data_infra/test_daily_update_5c.py b/tests/data_infra/test_daily_update_5c.py
index 395defb..1c30401 100644
--- a/tests/data_infra/test_daily_update_5c.py
+++ b/tests/data_infra/test_daily_update_5c.py
@@ -54,7 +54,7 @@ def _holder_code(lockdir, marker):
         "import sys, time, pathlib\n"
         f"sys.path.insert(0, r'{ROOT / 'src'}')\n"
         "import data_infra.tushare_lock as tl\n"
-        f"tl._LOCK_DIR = pathlib.Path(r'{lockdir}')\n"
+        f"tl._DATA_LOCK_DIR = pathlib.Path(r'{lockdir}')\n"
         "from data_infra.tushare_lock import raw_maintenance_lock\n"
         "with raw_maintenance_lock():\n"
         f"    open(r'{marker}', 'w').close()\n"
@@ -70,7 +70,7 @@ def test_raw_maintenance_lock_kernel_held_and_auto_released(tmp_path, monkeypatc
     import time as _time
     import filelock
     lockdir = tmp_path / "locks"
-    monkeypatch.setattr(tushare_lock, "_LOCK_DIR", lockdir)  # inject via attr, not env
+    monkeypatch.setattr(tushare_lock, "_DATA_LOCK_DIR", lockdir)  # inject via attr, not env
     holder = _sp.Popen([sys.executable, "-c", _holder_code(lockdir, tmp_path / "acq")])
     try:
         for _ in range(200):  # wait until the holder has acquired
@@ -96,7 +96,7 @@ def test_raw_maintenance_lock_namespace_not_env_forgeable(tmp_path, monkeypatch)
     import time as _time
     import filelock
     lockdir = tmp_path / "locks"
-    monkeypatch.setattr(tushare_lock, "_LOCK_DIR", lockdir)  # the real (injected) identity
+    monkeypatch.setattr(tushare_lock, "_DATA_LOCK_DIR", lockdir)  # the real (injected) identity
     holder = _sp.Popen([sys.executable, "-c", _holder_code(lockdir, tmp_path / "acq2")])
     try:
         for _ in range(200):
diff --git a/tests/data_infra/test_monthly_calendar_bump.py b/tests/data_infra/test_monthly_calendar_bump.py
index 124f3b5..6e51458 100644
--- a/tests/data_infra/test_monthly_calendar_bump.py
+++ b/tests/data_infra/test_monthly_calendar_bump.py
@@ -520,6 +520,20 @@ class _PubArgs:
     i_reviewed_the_dryrun = True
 
 
+@pytest.fixture(autouse=True)
+def _unseal_tmp_after(tmp_path):
+    # the READY gate seals trees read-only; unseal before the tmp cleanup so rmtree works
+    yield
+    import os as _os
+    import stat as _stat
+    for p in tmp_path.rglob("*"):
+        if p.is_file():
+            try:
+                _os.chmod(p, _stat.S_IREAD | _stat.S_IWRITE)
+            except OSError:
+                pass
+
+
 def _publish_env(tmp_path, monkeypatch, *, qa_rc: int = 0):
     root = tmp_path
     data = root / "data"
@@ -536,7 +550,10 @@ def _publish_env(tmp_path, monkeypatch, *, qa_rc: int = 0):
     monkeypatch.setattr(mcb, "RAW_MANIFEST_PATH", out / "raw_input_manifest.json")
     monkeypatch.setattr(mcb, "PUBLISH_RECORD_PATH", out / "publish_record.json")
     monkeypatch.setattr(mcb, "TRANSACTION_JOURNAL_PATH", out / "publish_transaction_journal.json")
+    monkeypatch.setattr(mcb, "TRANSACTION_INTENT_PATH", out / "publish_intent.json")
     monkeypatch.setattr(mcb, "_run_post_publish_qa", lambda: qa_rc)
+    import data_infra.tushare_lock as _tl
+    monkeypatch.setattr(_tl, "_DATA_LOCK_DIR", root / "locks")
 
     parent_pb, parent_cp = "parent_build_1", "frozen_20260701_thaw_step1"
     new_pb, new_cp = "thaw_20990101_120000", "frozen_20990101_thaw_step2"
@@ -1008,8 +1025,8 @@ def test_publish_systemexit_mid_rebind_rolls_back(tmp_path, monkeypatch):
 
 def test_ready_gate_refuses_bytes_changed_after_swap(tmp_path, monkeypatch):
     # P0 probe (hash->swap TOCTOU): bytes changed AFTER the pre-swap attestation — here
-    # while QA runs — must NOT reach 'ready'. The READY gate re-hashes the FULL live tree
-    # and refuses; the provider stays quarantined.
+    # while QA runs — must NOT reach 'ready'. The READY gate seals + re-hashes the FULL
+    # live tree, refuses, and transitions the provider to 'suspect' (tamper class).
     env = _publish_env(tmp_path, monkeypatch)
 
     def tampering_qa():
@@ -1018,27 +1035,39 @@ def test_ready_gate_refuses_bytes_changed_after_swap(tmp_path, monkeypatch):
 
     monkeypatch.setattr(mcb, "_run_post_publish_qa", tampering_qa)
     assert mcb.phase_publish(_PubArgs()) == 5
-    assert _publish_state_of(env.qlib) == "pending_qa", "quarantine must persist"
+    assert _publish_state_of(env.qlib) == "suspect", "tamper-class refusal must quarantine as suspect"
     steps = _json.loads((env.out / "publish_transaction_journal.json").read_text(encoding="utf-8"))["steps"]
-    ready = [s for s in steps if s["step"] == "ready" and s["status"] == "refused"]
+    ready = [s for s in steps if s["step"] == "ready" and s["status"] == "refused_suspect"]
     assert ready and any("content root" in p for p in ready[0]["problems"])
+    # suspect BLOCKS finalize (only --restore-parent applies)
+    monkeypatch.setattr(mcb, "_run_post_publish_qa", lambda: 0)
+    assert mcb.phase_finalize_qa(_PubArgs()) == 2
 
 
-def test_finalize_qa_cannot_green_changed_bytes(tmp_path, monkeypatch):
+def test_finalize_qa_cannot_green_changed_bytes_then_restore_parent(tmp_path, monkeypatch):
     # P0 probe: QA fails first (qa_failed), the live bin is then rewritten, QA is made to
-    # pass — finalize must still REFUSE ready (full pin re-verification), and succeed only
-    # once the original bytes are restored.
+    # pass — finalize must still refuse (suspect), and the EXPLICIT --restore-parent
+    # recovery must bring the verified parent back with approvals re-bound (0 drift).
     env = _publish_env(tmp_path, monkeypatch, qa_rc=1)
     assert mcb.phase_publish(_PubArgs()) == 6
     live_bin = env.qlib / "features" / "000001_sz" / "close.day.bin"
-    original = live_bin.read_bytes()
     live_bin.write_bytes(b"\x0b\x0b\x0b\x0b")
     monkeypatch.setattr(mcb, "_run_post_publish_qa", lambda: 0)
     assert mcb.phase_finalize_qa(_PubArgs()) == 5
-    assert _publish_state_of(env.qlib) == "qa_failed", "tampered bytes must stay quarantined"
-    live_bin.write_bytes(original)
-    assert mcb.phase_finalize_qa(_PubArgs()) == 0
-    assert _publish_state_of(env.qlib) == "ready"
+    assert _publish_state_of(env.qlib) == "suspect", "tampered bytes must be quarantined as suspect"
+    assert mcb.phase_finalize_qa(_PubArgs()) == 2, "suspect blocks finalize"
+    assert mcb.phase_publish(_PubArgs()) == 2, "suspect blocks a new publish"
+    # explicit verified recovery: parent live again, approvals back on parent, 0 drift
+    assert mcb.phase_restore_parent(_PubArgs()) == 0
+    assert (env.qlib / "LIVE_MARKER.txt").exists()
+    assert mcb.live_provider_ids() == (env.parent_pb, env.parent_cp)
+    assert f'provider_build_id: "{env.parent_pb}"' in env.a1.read_text(encoding="utf-8")
+    from data_infra.approval_evidence import evaluate_approval_evidence_bindings
+    drifts = evaluate_approval_evidence_bindings(
+        approvals_dir=env.root / "approvals",
+        manifest_path=env.qlib / "metadata" / "provider_build.json")
+    assert drifts and not any(d.drift for d in drifts)
+    assert (env.staged / "STAGED_MARKER.txt").exists(), "child back at the staged path"
 
 
 def test_publish_refuses_raw_provenance_mismatch(tmp_path, monkeypatch):
@@ -1057,26 +1086,137 @@ def test_publish_refuses_raw_provenance_mismatch(tmp_path, monkeypatch):
     _assert_untouched(env)
 
 
-def test_lock_root_is_shared_across_worktrees(tmp_path):
-    # P0 probe: two worktrees of the same repo previously resolved DIFFERENT lock dirs and
-    # could publish concurrently. The lock root is anchored to the git COMMON dir's parent
-    # — identical from the main checkout and from any linked worktree.
-    import subprocess
+def test_data_lock_identity_shared_across_checkouts(tmp_path):
+    # Re-review #3 P0: TWO INDEPENDENT CLONES (not just worktrees) configured onto ONE
+    # shared data root must resolve the SAME store-mutating lock files — the identity is
+    # derived from the canonical resolved storage.data_root, not from any git path.
+    import data_infra.tushare_lock as tl
 
+    shared_data = tmp_path / "shared_store" / "data"
+    shared_data.mkdir(parents=True)
+    clone_a, clone_b = tmp_path / "cloneA", tmp_path / "cloneB"
+    for c in (clone_a, clone_b):
+        c.mkdir()
+        (c / "config.yaml").write_text(
+            f"storage:\n  data_root: {_json.dumps(str(shared_data))}\n", encoding="utf-8")
+    lock_a = tl._resolve_data_lock_dir(clone_a)
+    lock_b = tl._resolve_data_lock_dir(clone_b)
+    assert lock_a == lock_b == shared_data.resolve() / ".locks"
+    # relative data roots resolve against each checkout — genuinely separate stores get
+    # separate (correct) lock namespaces
+    (clone_a / "config.yaml").write_text("storage:\n  data_root: ./data\n", encoding="utf-8")
+    assert tl._resolve_data_lock_dir(clone_a) == (clone_a / "data").resolve() / ".locks"
+
+
+def test_data_lock_identity_unresolvable_refuses(tmp_path):
+    # Re-review #3 P0: when the shared lock identity is unknowable, store-mutating locks
+    # REFUSE (LockIdentityError) — never a warn-and-continue private namespace.
     import data_infra.tushare_lock as tl
 
-    main = tmp_path / "mainrepo"
-    main.mkdir()
-    subprocess.run(["git", "init", "-q", str(main)], check=True)
-    (main / "x.txt").write_text("x", encoding="utf-8")
-    subprocess.run(["git", "-C", str(main), "add", "."], check=True)
-    subprocess.run(["git", "-C", str(main), "-c", "user.email=t@t", "-c", "user.name=t",
-                    "commit", "-qm", "init"], check=True)
-    wt = tmp_path / "wt1"
-    subprocess.run(["git", "-C", str(main), "worktree", "add", "-q", str(wt)], check=True)
-    root_main = tl._resolve_lock_root(main)
-    root_wt = tl._resolve_lock_root(wt)
-    assert root_main.resolve() == root_wt.resolve() == main.resolve()
+    empty = tmp_path / "no_config"
+    empty.mkdir()
+    with pytest.raises(tl.LockIdentityError):
+        tl._resolve_data_lock_dir(empty)
+    blank = tmp_path / "blank_root"
+    blank.mkdir()
+    (blank / "config.yaml").write_text("storage:\n  data_root: ''\n", encoding="utf-8")
+    with pytest.raises(tl.LockIdentityError):
+        tl._resolve_data_lock_dir(blank)
+
+
+def test_publish_systemexit_right_after_swap_rolls_back_via_disk_truth(tmp_path, monkeypatch):
+    # Re-review #3 P0 probe: SystemExit raised IMMEDIATELY after the real publish()
+    # completes — before any in-process flag could be set. The handler must classify the
+    # state from DISK (child live + backup present), run the full verified rollback, and
+    # only then re-raise.
+    env = _publish_env(tmp_path, monkeypatch)
+    real_factory = mcb._make_publish_builder
+
+    def wrapping_factory(build_id):
+        builder = real_factory(build_id)
+        real_publish = builder.publish
+
+        def exploding_publish(**kwargs):
+            real_publish(**kwargs)
+            raise SystemExit(9)  # lands exactly in the publish->flag gap
+
+        builder.publish = exploding_publish
+        return builder
+
+    monkeypatch.setattr(mcb, "_make_publish_builder", wrapping_factory)
+    with pytest.raises(SystemExit):
+        mcb.phase_publish(_PubArgs())
+    assert (env.qlib / "LIVE_MARKER.txt").exists(), "parent must be restored (disk-truth undo)"
+    assert mcb.live_provider_ids() == (env.parent_pb, env.parent_cp)
+    assert env.a1.read_bytes() == env.a1_bytes and env.a2.read_bytes() == env.a2_bytes
+    assert (env.staged / "STAGED_MARKER.txt").exists()
+    intent = _json.loads((env.out / "publish_intent.json").read_text(encoding="utf-8"))
+    assert intent["status"] == "aborted"
+
+
+def test_real_sigint_defers_commits_core_then_finalize(tmp_path, monkeypatch):
+    # Re-review #3 Major: a REAL SIGINT (delivered via raise_signal, not a hand-raised
+    # exception) is DEFERRED: the consistent core transaction COMMITS (swap + rebind +
+    # pending_qa), KeyboardInterrupt raises at span exit, and --finalize-qa completes the
+    # publish afterwards. This pins the documented semantics with a true signal.
+    import signal as _signal
+
+    env = _publish_env(tmp_path, monkeypatch)
+    real = mcb._atomic_write_bytes
+    fired: list[int] = []
+
+    def signal_during_rebind(path, data):
+        if Path(path).suffix == ".yaml" and Path(path).parent == env.root / "approvals" and not fired:
+            fired.append(1)
+            _signal.raise_signal(_signal.SIGINT)  # the REAL signal — recorded, deferred
+        real(path, data)
+
+    monkeypatch.setattr(mcb, "_atomic_write_bytes", signal_during_rebind)
+    with pytest.raises(KeyboardInterrupt):
+        mcb.phase_publish(_PubArgs())
+    # the core committed consistently and is quarantined:
+    assert (env.qlib / "STAGED_MARKER.txt").exists(), "child stays live (core committed)"
+    assert _publish_state_of(env.qlib) == "pending_qa"
+    assert f'provider_build_id: "{env.new_pb}"' in env.a1.read_text(encoding="utf-8")
+    monkeypatch.setattr(mcb, "_atomic_write_bytes", real)
+    assert mcb.phase_finalize_qa(_PubArgs()) == 0
+    assert _publish_state_of(env.qlib) == "ready"
+
+
+def test_ready_seal_blocks_later_writes(tmp_path, monkeypatch):
+    # Re-review #3 P0: the certified generation is SEALED read-only before the certifying
+    # hash — an attribute-respecting writer can no longer modify published bytes at all.
+    env = _publish_env(tmp_path, monkeypatch)
+    assert mcb.phase_publish(_PubArgs()) == 0
+    with pytest.raises(PermissionError):
+        (env.qlib / "features" / "000001_sz" / "close.day.bin").write_bytes(b"\x0c\x0c\x0c\x0c")
+
+
+def test_unresolved_intent_blocks_new_publish(tmp_path, monkeypatch):
+    env = _publish_env(tmp_path, monkeypatch)
+    mcb._write_intent({"transaction_id": "deadbeef", "status": "swapping"})
+    assert mcb.phase_publish(_PubArgs()) == 2
+    _assert_untouched(env)
+
+
+def test_stale_qa_worker_cannot_overwrite_ready(tmp_path, monkeypatch):
+    # Re-review #3 Major: worker A begins a QA attempt; worker B begins a NEWER attempt
+    # (taking the lease) and reaches ready; A's delayed failure must record 'superseded'
+    # (exit 7) and change nothing.
+    env = _publish_env(tmp_path, monkeypatch, qa_rc=1)
+    assert mcb.phase_publish(_PubArgs()) == 6  # qa_failed, quarantined
+    rep = _json.loads((env.out / "monthly_bump_dryrun_report.json").read_text(encoding="utf-8"))
+    builder = mcb._make_publish_builder(rep["staged_build_id"])
+    stale_attempt = mcb._begin_qa_attempt(builder, rep)
+    assert stale_attempt
+    monkeypatch.setattr(mcb, "_run_post_publish_qa", lambda: 0)
+    assert mcb.phase_finalize_qa(_PubArgs()) == 0  # a newer worker takes the lease -> ready
+    assert _publish_state_of(env.qlib) == "ready"
+    steps: list = []
+    rc = mcb._record_qa_failure(builder, rep, stale_attempt, 1,
+                                lambda step, status, **info: steps.append((step, status)))
+    assert rc == 7 and ("qa", "superseded") in steps
+    assert _publish_state_of(env.qlib) == "ready", "a stale failure must not overwrite ready"
 
 
 def test_builder_publish_acquires_global_lock(tmp_path, monkeypatch):
diff --git a/tests/research_orchestrator/test_provider_raw_attestation_gate.py b/tests/research_orchestrator/test_provider_raw_attestation_gate.py
index 293e8ba..fba27c5 100644
--- a/tests/research_orchestrator/test_provider_raw_attestation_gate.py
+++ b/tests/research_orchestrator/test_provider_raw_attestation_gate.py
@@ -175,6 +175,9 @@ def test_publish_state_gate_quarantines_until_ready(tmp_path):
             assert_provider_publish_state(qlib_dir=tmp_path, policy=pol, manifest=m)
     _write_state(tmp_path, "qa_failed")
     assert not evaluate_provider_publish_state(qlib_dir=tmp_path, policy=flagged, manifest=m).eligible
+    _write_state(tmp_path, "suspect")  # tamper quarantine (re-review #3) — refused everywhere
+    for pol in (flagged, legacy):
+        assert not evaluate_provider_publish_state(qlib_dir=tmp_path, policy=pol, manifest=m).eligible
     _write_state(tmp_path, "ready")
     assert evaluate_provider_publish_state(qlib_dir=tmp_path, policy=flagged, manifest=m).eligible
     # a marker naming a DIFFERENT build is stale/foreign -> refuse
```

RE-REVIEW QUESTIONS
1. Re-run your re-review #3 probes (post-swap SystemExit, pre-ready tamper, two-clone shared data root, real SIGINT, concurrent QA, record orphan): per-probe pass/fail table.
2. _disk_swap_state's classification table: is (backup AND live != parent) -> child_live sound against every reachable failure point of publish() (including a crash between rename 2 and 3, and a stale .bak from an earlier same-build attempt — note publish() rmtree's stale staging/backup at entry)? Any state it mislabels?
3. The seal: file-level read-only attributes prevent modification/deletion of existing files but NOT creation of new files in the directories. Adding a NEW bin file post-ready would not change already-certified bytes but could add a field the provider serves. In scope to block now, or an accepted residual under L2 (trusted-operator, accident threat model)? Also rule on: the seal's interaction with backup pruning (D2) — .bak trees now carry read-only files and pruning tooling must clear attributes first.
4. The intent journal lives in workspace/outputs (gitignored, per-checkout) while locks live in <data_root>/.locks — should the intent journal ALSO move into the data root so a second checkout sees an unresolved transaction? (Currently a publish from checkout B would not see checkout A's unresolved intent file, though the data-root LOCK still serializes concurrent execution and the disk-state/marker checks still refuse inconsistent stores.) Blocker or acceptable with the marker+CAS defenses?
5. suspect/restore-parent: right recovery surface? Anything --restore-parent must additionally verify before swapping the parent back (e.g., parent tree content vs a parent-era attestation — none exists for pre-5B parents)?
6. Any hole opened by the QA lease (e.g., a worker beginning an attempt between another worker's QA pass and its _finalize_ready lock acquisition — the finalize CAS would then see a foreign lease and return 7, leaving pending_qa; acceptable liveness/correctness trade?).
7. Final ruling on the remaining plan: operator drill (checklist 2) + timing/memory measurements (3) + §13 for the first live run. SHIP the code contingent on those operator actions, or more code work first?

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending line quoted and an exact suggested replacement.
- Explicit per-probe pass/fail table for your re-review #3 probes.
- Final line: SHIP / REVISE / REWORK, plus the single most important residual risk.
```
