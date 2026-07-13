# GPT 5.5 Pro re-review #5 — Phase 5-B atomic publish: re-review #4 P0/Major closed

> Send verbatim to GPT 5.5 Pro. Branch pushed; pinned HEAD: `201df67` (fix commit `ec8cafc`,
> docs `201df67`; your re-review #4 baseline was `3e70e4a`).

```text
ROLE
You are the same senior reviewer who issued REWORK #4 (5 P0 + 1 Major: checkout-local recovery state / restore-interrupt half-rebind / forgeable finalize CAS / provider lock keyed off raw root + driver path hardcodes / basename-wide seal exemption / per-repo account lock). Re-review adversarially: re-run each probe against the new code and hunt for holes the fixes opened. Do not rubber-stamp.

REPO (public — fetch any file to verify against the live code)
https://github.com/henrydan111/quant-system   (branch: calendar-unfreeze-phase5b-atomic-publish)
Raw file form: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/<path>

KEY FILES (updated this round)
- Driver: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/scripts/monthly_calendar_bump.py
- Locks (per-resource identities + per-token account lock): https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/src/data_infra/tushare_lock.py
- Swap primitive (qlib-dir-keyed lock): https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/src/data_infra/pit_backend.py
- Manifest emitters (qlib-dir-keyed lock): https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/src/data_infra/provider_manifest.py
- Tests: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/tests/data_infra/test_monthly_calendar_bump.py
- Self-review round 5 (incl. 3 disclosed residuals): https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/workspace/research/calendar_unfreeze/PHASE5B_ATOMIC_PUBLISH_SELF_REVIEW.md
- Invariants (hardening paragraph rewritten): CLAUDE.md 3.4

FINDING-BY-FINDING DISPOSITION (verify each against the diff below)
P0-1 (recovery state checkout-local) -> the intent journal, per-transaction records (publish_record_<txid>.json), and the reviewed-report SNAPSHOT (report_<txid>.json) now live in the SHARED store transaction dir _tx_dir() = <data_root>/qlib_transactions/, adjacent to the provider. The pending marker binds transaction_id; --finalize-qa / --restore-parent load the pins from the snapshot the LIVE MARKER names (_load_tx_report), never this checkout's workspace. phase_publish refuses while ANY unresolved intent (status in swapping/rollback_incomplete/failed_state_unknown/restore_interrupted) exists in the shared dir. Probe-replica: test_unresolved_intent_blocks_new_publish_cross_checkout (asserts the intent path is inside the shared store AND blocks).
P0-2 (restore interrupt half-rebind) -> phase_restore_parent runs its unseal + reverse-rebind + metadata-strip + swap-back inside _defer_sigint + except BaseException; an interrupt mid-domain calls _restore_approval_files(written, current_bytes) to un-write the partial reverse rebind (byte-verified back to uniformly child-bound), journals restore_interrupted, and re-raises — the command is re-runnable. The final intent-status write is INSIDE the deferral so a deferred real SIGINT fires only after the intent reaches a settled status. Probe-replica: test_restore_parent_interrupt_rolls_back_partial_rebind (KeyboardInterrupt between the two reverse writes -> approvals uniformly child-bound again, then re-run -> exit 0, parent live).
P0-3 (forgeable finalize CAS) -> the pending marker pins record_sha256 at publish; _finalize_ready (1) requires the on-disk record's sha256 to equal it (a rewritten record is tamper-class), (2) cross-checks every record field (txid/build/policy/parent/raw-root/content-root/commit) against the report snapshot, and (3) runs the SEMANTIC evaluate_approval_evidence_bindings against the live manifest — a forged approvals_post_rebind_root cannot fake an approval bound to a foreign build; any binding drift is tamper-class -> suspect. Probe-replicas: test_finalize_refuses_forged_record (record rewritten -> digest breaks), test_finalize_refuses_binding_drift_even_with_consistent_forge (attacker ALSO re-pins record_sha256 -> the semantic binding still catches the foreign-build approval).
P0-4 (provider lock keyed off raw root; driver path hardcodes) -> provider_publish_lock(qlib_dir=...) is keyed by the canonical live provider dir (<qlib_parent>/.locks/provider_publish__<name>.lock); StagedQlibBackendBuilder.publish() and the manifest emitters pass their own qlib_dir. The driver resolves ALL live/raw paths from one BuildPaths (_live_paths / _tx_dir / live_provider_ids) and _assert_standard_layout() refuses a split/relocated layout before any mutation. Probe-replicas: test_provider_lock_keyed_by_qlib_dir_not_raw_root (two raw roots, one provider -> one lock file), test_publish_refuses_nonstandard_layout.
P0-5 (basename-wide seal exemption) -> _seal_tree_readonly exempts the EXACT tree-relative path metadata/publish_state.json (not any file so named); the external build manifest (part of the content root) is chmod'd read-only too. Probe-replica: test_seal_covers_nested_control_plane_basename_and_build_manifest (a nested metadata/audit_payload/publish_state.json AND the build manifest raise PermissionError after ready; the real marker stays writable).
Major-1 (per-repo account lock) -> the account lock + rate-spacing state move to ~/.quant_tushare_locks/<sha256(token)[:16]>/, resolved from TUSHARE_TOKEN (env, else the checkout .env); no token -> a shared 'no_token' namespace (conservative). The token appears only as an irreversible fingerprint. Probe-replica: test_account_lock_is_per_token_not_per_checkout (same token across checkouts -> one dir; different token -> different; plaintext absent).

DISCLOSED RESIDUALS (I did not fix these; rule on each)
R1. The seal blocks modification/deletion of EXISTING files but not CREATION of new files in sealed directories. A new bin added post-ready would not change certified bytes but could add a field the provider serves. In scope now, or accepted under L2 (trusted-operator, accident threat model)?
R2. .bak parent trees now carry read-only files (the prior generation was sealed). The D2 retention/pruning tooling must clear attributes first (_unseal_tree is reusable). Flagging for the pruning path; is a note sufficient or must I wire it now?
R3. QA-lease liveness: a worker that begins an attempt between another worker's QA-pass and its _finalize_ready lock acquisition makes finalize see a foreign lease and return 7 (leaving pending_qa; a re-finalize succeeds). Correctness-safe; acceptable liveness?

VERIFICATION (this round)
Focused battery 207 green (+9 probe replicas). Combined four suites: 1083 green / 16 skipped; the failure set is file-by-file identical to the environmental baseline you have inspected across all rounds; the provider_context gate-consumer files (cache_generation_self_heal, r4_wall_hardening, d3_formal_door_clamp, spent_oos_boundary) pass 55/55 in isolation. Lock relocations on merge: provider lock -> <qlib_parent>/.locks/, raw lock -> <data_root>/.locks/, account lock -> ~/.quant_tushare_locks/, transaction state -> <data_root>/qlib_transactions/. No live-provider touch this session.

WHAT CHANGED (authoritative — the full fix diff, commit ec8cafc):

```diff
diff --git a/scripts/monthly_calendar_bump.py b/scripts/monthly_calendar_bump.py
index ba65842..4dffab9 100644
--- a/scripts/monthly_calendar_bump.py
+++ b/scripts/monthly_calendar_bump.py
@@ -336,8 +336,45 @@ class ExceptionRegistry:
         self.path.write_text(json.dumps(self.rows, ensure_ascii=False, indent=1), encoding="utf-8")
 
 
+def _live_paths():
+    """The ONE canonical path resolution for everything this driver reads/mutates on the
+    live side (GPT re-review #4 P0: PROJECT_ROOT/data hardcodes diverge from a config that
+    relocates storage.data_root / storage.qlib_data_dir). Returns the pit_backend
+    BuildPaths (data_root, qlib_dir, ...). Tests monkeypatch THIS function."""
+    from data_infra.pit_backend import resolve_build_paths
+    return resolve_build_paths()
+
+
+def _assert_standard_layout() -> bool:
+    """This driver currently supports ONLY the standard layout (qlib_dir directly under
+    data_root, both under the project); a split-root configuration REFUSES up front (the
+    GPT-sanctioned alternative to threading BuildPaths through every raw reader). The
+    provider lock itself is already keyed by the canonical qlib_dir regardless."""
+    p = _live_paths()
+    data_root = Path(p.data_root).resolve()
+    qlib_dir = Path(p.qlib_dir).resolve()
+    expected_data = (PROJECT_ROOT / "data").resolve()
+    if data_root != expected_data or qlib_dir != data_root / "qlib_data":
+        logger.error("non-standard storage layout (data_root=%s, qlib_dir=%s; expected %s and "
+                     "%s) — this driver refuses under a split/relocated layout.",
+                     data_root, qlib_dir, expected_data, expected_data / "qlib_data")
+        return False
+    return True
+
+
+def _tx_dir() -> Path:
+    """CANONICAL SHARED transaction directory, adjacent to the provider inside the shared
+    store (GPT re-review #4 P0: checkout-local OUT_DIR state let a second checkout inherit
+    an un-QA'd child after a hard crash). Intent, per-transaction records, and the report
+    snapshot live HERE; publish/finalize/restore read ONLY from here."""
+    d = Path(_live_paths().data_root) / "qlib_transactions"
+    d.mkdir(parents=True, exist_ok=True)
+    return d
+
+
 def live_provider_ids() -> tuple[str, str]:
-    m = json.loads((PROJECT_ROOT / "data" / "qlib_data" / "metadata" / "provider_build.json").read_text(encoding="utf-8"))
+    m = json.loads((Path(_live_paths().qlib_dir) / "metadata" / "provider_build.json")
+                   .read_text(encoding="utf-8"))
     return m["provider_build_id"], m["calendar_policy_id"]
 
 
@@ -753,7 +790,9 @@ def _write_publish_state(qlib_dir, state: str, build_id: str, **extra) -> None:
     current = _read_publish_state(qlib_dir)
     payload = {"state": state, "provider_build_id": build_id,
                "updated_cst": now_cst().isoformat(timespec="seconds")}
-    for carried in ("transaction_id", "active_qa_attempt"):
+    # every binding field survives a state transition unless explicitly overridden — the
+    # record digest in particular anchors the READY gate across attempt rewrites.
+    for carried in ("transaction_id", "active_qa_attempt", "record_sha256", "parent_build_id"):
         if carried in current:
             payload[carried] = current[carried]
     payload.update(extra)
@@ -761,19 +800,22 @@ def _write_publish_state(qlib_dir, state: str, build_id: str, **extra) -> None:
                         json.dumps(payload, ensure_ascii=False, indent=1).encode("utf-8"))
 
 
-# ── re-review #3: durable intent journal + disk-truth swap classification ────
+# ── re-review #3/#4: durable SHARED intent journal + disk-truth swap classification ──
+def _intent_path() -> Path:
+    return _tx_dir() / "publish_intent.json"
+
+
 def _read_intent() -> dict:
     try:
-        payload = json.loads(TRANSACTION_INTENT_PATH.read_text(encoding="utf-8"))
+        payload = json.loads(_intent_path().read_text(encoding="utf-8"))
         return payload if isinstance(payload, dict) else {}
     except (OSError, json.JSONDecodeError):
         return {}
 
 
 def _write_intent(payload: dict) -> None:
-    OUT_DIR.mkdir(parents=True, exist_ok=True)
     payload = {**payload, "updated_cst": now_cst().isoformat(timespec="seconds")}
-    _atomic_write_bytes(TRANSACTION_INTENT_PATH,
+    _atomic_write_bytes(_intent_path(),
                         json.dumps(payload, ensure_ascii=False, indent=1).encode("utf-8"))
 
 
@@ -797,15 +839,18 @@ def _disk_swap_state(builder, parent_pb: str) -> str:
 
 
 # ── re-review #3: read-only generation seal (the READY-gate immutability) ────
-def _seal_tree_readonly(qlib_dir, exclude_names: tuple = ("publish_state.json",)) -> int:
-    """Set every file in the tree read-only EXCEPT the control-plane marker. Sealing
-    happens BEFORE the READY-gate content hash, so the certified bytes cannot be modified
-    by any attribute-respecting writer after certification (re-review #3 P0: 'one more
-    hash' cannot close the hash->ready window on a mutable tree). Returns files sealed."""
+def _seal_tree_readonly(qlib_dir, exclude_rel: tuple = ("metadata/publish_state.json",)) -> int:
+    """Set every file in the tree read-only EXCEPT the exact control-plane path(s) —
+    TREE-RELATIVE comparison, not basename (GPT re-review #4 P0: a basename exemption left
+    any attested payload file that happened to be NAMED publish_state.json writable after
+    certification). Sealing happens BEFORE the READY-gate content hash, so the certified
+    bytes cannot be modified by any attribute-respecting writer. Returns files sealed."""
     import stat
+    root = Path(qlib_dir)
+    excluded = set(exclude_rel)
     n = 0
-    for p in Path(qlib_dir).rglob("*"):
-        if p.is_file() and p.name not in exclude_names:
+    for p in root.rglob("*"):
+        if p.is_file() and str(p.relative_to(root)).replace("\\", "/") not in excluded:
             os.chmod(p, stat.S_IREAD)
             n += 1
     return n
@@ -829,7 +874,7 @@ def _begin_qa_attempt(builder, rep: dict) -> str | None:
     admit a QA attempt."""
     import uuid
     from data_infra.tushare_lock import provider_publish_lock
-    with provider_publish_lock():
+    with provider_publish_lock(qlib_dir=builder.paths.qlib_dir):
         marker = _read_publish_state(builder.paths.qlib_dir)
         if (marker.get("state") not in ("pending_qa", "qa_failed")
                 or marker.get("provider_build_id") != rep["staged_build_id"]):
@@ -845,7 +890,7 @@ def _record_qa_failure(builder, rep: dict, attempt: str, qa_rc: int, j) -> int:
     still non-ready for the same build — a stale worker records 'superseded' and changes
     NOTHING (re-review #3 Major: a delayed failing QA overwrote a newer 'ready')."""
     from data_infra.tushare_lock import provider_publish_lock
-    with provider_publish_lock():
+    with provider_publish_lock(qlib_dir=builder.paths.qlib_dir):
         marker = _read_publish_state(builder.paths.qlib_dir)
         if (marker.get("active_qa_attempt") != attempt
                 or marker.get("provider_build_id") != rep["staged_build_id"]
@@ -1165,6 +1210,8 @@ def assert_endpoints_complete(parent_end: str, target_end: str) -> tuple[bool, d
 
 # ── phases ───────────────────────────────────────────────────────────────────
 def phase_plan(args) -> dict:
+    if not _assert_standard_layout():
+        raise SystemExit(2)
     parent_build, parent_policy = live_provider_ids()
     target_end, evidence = determine_target_end(now_cst(), probe_ready=None)
     plan = {
@@ -1189,8 +1236,9 @@ DRYRUN_REPORT_PATH = OUT_DIR / "monthly_bump_dryrun_report.json"
 FRESH_AUDIT_PATH = OUT_DIR / "fresh_window_survivorship_audit.json"
 PUBLISH_RECORD_PATH = OUT_DIR / "publish_record.json"
 TRANSACTION_JOURNAL_PATH = OUT_DIR / "publish_transaction_journal.json"
-TRANSACTION_INTENT_PATH = OUT_DIR / "publish_intent.json"
 RAW_MANIFEST_PATH = OUT_DIR / "raw_input_manifest.json"
+# the SHARED intent journal / per-transaction records live in the store's transaction
+# dir (_tx_dir(), adjacent to the provider) — NOT in this checkout's workspace.
 
 
 def _report_rc_halo_start(target_end: str) -> str:
@@ -1224,6 +1272,8 @@ def _phase_execute_impl(args) -> int:
     self-locks). Then hands off to _build_under_lock."""
     import subprocess
 
+    if not _assert_standard_layout():
+        return 2
     parent_build, parent_policy = live_provider_ids()
 
     # M1: the parent policy MUST still be in the Phase-5 frozen regime (spent_oos_end /
@@ -1473,15 +1523,17 @@ def phase_publish(args) -> int:
     then post-publish QA (run_daily_qa) OUTSIDE the locks. Any post-swap failure restores
     the approval bytes AND rolls the swap back to the parent live provider.
 
-    Exit codes: 0 = published + rebound + QA pass; 2 = refused pre-swap (nothing mutated);
-    4 = post-swap failure, fully rolled back (nothing durably mutated); 5 = CRITICAL
-    inconsistent state (see publish_transaction_journal.json for the exact recovery move);
-    6 = published + consistent, but post-publish QA failed (investigate before any formal
-    run; the provider stays live, parent retained as .bak)."""
+    Exit codes: 0 = published + rebound + QA pass + READY-gate certified; 2 = refused
+    pre-swap (nothing mutated); 4 = post-swap failure, fully rolled back (verified); 5 =
+    CRITICAL inconsistent/suspect state (see the journals for the exact recovery move);
+    6 = published + consistent, but post-publish QA failed (quarantined; --finalize-qa);
+    7 = this worker's QA attempt was superseded by a newer one (nothing changed)."""
     if not args.i_reviewed_the_dryrun:
         logger.error("publish requires --i-reviewed-the-dryrun (you must have read %s). Refusing.",
                      DRYRUN_REPORT_PATH)
         return 2
+    if not _assert_standard_layout():
+        return 2
     if not DRYRUN_REPORT_PATH.exists():
         logger.error("no dry-run report at %s — run the execute phase first.", DRYRUN_REPORT_PATH)
         return 2
@@ -1521,22 +1573,23 @@ def phase_publish(args) -> int:
                                  "ts_cst": now_cst().isoformat(timespec="seconds"), **info})
         _write_journal(journal)
 
-    # LOCK ORDER (fixed everywhere): raw_maintenance_lock FIRST, then provider_publish_lock.
-    with raw_maintenance_lock(), provider_publish_lock():
+    # LOCK ORDER (fixed everywhere): raw_maintenance_lock FIRST, then provider_publish_lock
+    # (keyed by the canonical live provider dir — re-review #4 P0).
+    with raw_maintenance_lock(), provider_publish_lock(qlib_dir=_live_paths().qlib_dir):
         # ── VERIFY: every attestation re-checked here, IMMEDIATELY before the swap, with
         # no lock release in between (the verify↔swap inseparability is the transaction).
-        # re-review #3: refuse over an UNRESOLVED prior transaction (durable intent journal)
-        # or a live provider whose marker is not settled — a suspect/pending/qa_failed
-        # provider must be finalized or restored before any new publish.
+        # re-review #3/#4: refuse over an UNRESOLVED prior transaction (the intent journal
+        # is SHARED — it lives in the store's transaction dir, so a hard crash in ANOTHER
+        # checkout blocks this one too) or a live provider whose marker is not settled.
         intent = _read_intent()
-        if intent.get("status") in ("swapping", "rollback_incomplete", "failed_state_unknown"):
+        if intent.get("status") in ("swapping", "rollback_incomplete", "failed_state_unknown",
+                                    "restore_interrupted"):
             logger.error("UNRESOLVED prior transaction %s (status=%s) — resolve it first "
                          "(--finalize-qa / --restore-parent / manual per %s). Refusing.",
-                         intent.get("transaction_id"), intent.get("status"),
-                         TRANSACTION_JOURNAL_PATH)
+                         intent.get("transaction_id"), intent.get("status"), _intent_path())
             j("verify", "refused", reason="unresolved_intent")
             return 2
-        live_marker = _read_publish_state(PROJECT_ROOT / "data" / "qlib_data")
+        live_marker = _read_publish_state(_live_paths().qlib_dir)
         if live_marker and live_marker.get("state") != "ready":
             logger.error("live provider publish-state is %r — finalize (--finalize-qa) or "
                          "restore (--restore-parent) before a new publish. Refusing.",
@@ -1698,17 +1751,26 @@ def phase_publish(args) -> int:
         import uuid
         txid = uuid.uuid4().hex[:16]
         journal["transaction_id"] = txid
-        record_path = OUT_DIR / f"publish_record_{txid}.json"
+        record_path = _tx_dir() / f"publish_record_{txid}.json"
+        report_snapshot_path = _tx_dir() / f"report_{txid}.json"
         md_path = APPROVALS_DIR / f"{now_cst().strftime('%Y-%m-%d')}_rebind_to_{rep['staged_build_id']}.md"
         try:
+            # the SHARED intent journal + the reviewed-report SNAPSHOT must land in the
+            # store's transaction dir BEFORE any rename: any checkout can then detect,
+            # finalize, or restore this transaction without this checkout's workspace.
+            _atomic_write_bytes(report_snapshot_path,
+                                json.dumps(rep, ensure_ascii=False, indent=1).encode("utf-8"))
             _write_intent({"transaction_id": txid, "status": "swapping",
                            "parent_build_id": live_build, "parent_policy_id": live_policy,
                            "child_build_id": rep["staged_build_id"],
                            "backup_dir": f"{builder.paths.qlib_dir}.bak_{builder.build_id}",
                            "staged_provider_dir": str(staged_dir),
-                           "record_path": str(record_path), "rebind_record_path": str(md_path)})
+                           "record_path": str(record_path),
+                           "report_snapshot_path": str(report_snapshot_path),
+                           "rebind_record_path": str(md_path)})
         except Exception as exc:  # noqa: BLE001 — the durable intent MUST land before any rename
-            logger.error("cannot write the durable intent journal (%s) — refusing pre-swap.", exc)
+            logger.error("cannot write the shared intent journal / report snapshot (%s) — "
+                         "refusing pre-swap.", exc)
             j("verify", "refused", reason="intent_write_failed")
             return 2
         written: list[Path] = []
@@ -1766,10 +1828,10 @@ def phase_publish(args) -> int:
                         f"{len(still)} approval(s) still drift after the rebind: {still[0].reasons()}")
                 # B6 QA quarantine: the provider is durable but NOT ready — gated reads
                 # refuse until the READY gate (QA pass + full pin re-verification) flips it.
-                # The marker carries the transaction id: finalize locates this
-                # transaction's record through it, and cleanup is disk-driven by txid.
-                _write_publish_state(builder.paths.qlib_dir, "pending_qa", rep["staged_build_id"],
-                                     parent_build_id=live_build, transaction_id=txid)
+                # ORDER (re-review #4 P0: the record must not be forgeable after the fact):
+                # the per-transaction RECORD is written FIRST into the SHARED transaction
+                # dir; the marker then binds transaction_id + the record's sha256, so any
+                # later record edit breaks the marker binding at the READY gate.
                 appr_post = _approvals_attestation()  # post-rebind pin the READY gate re-checks
                 record = {
                     "transaction_id": txid,
@@ -1785,11 +1847,16 @@ def phase_publish(args) -> int:
                     "approvals_rebound": len(written),
                     "backup_dir": f"{builder.paths.qlib_dir}.bak_{builder.build_id}",
                     "reviewed_dryrun_report": str(DRYRUN_REPORT_PATH),
+                    "report_snapshot_path": str(report_snapshot_path),
                     "published_cst": now_cst().isoformat(timespec="seconds"),
                 }
                 record_bytes = json.dumps(record, ensure_ascii=False, indent=1).encode("utf-8")
                 _atomic_write_bytes(record_path, record_bytes)   # canonical, per-transaction
                 _atomic_write_bytes(PUBLISH_RECORD_PATH, record_bytes)  # human convenience copy
+                import hashlib as _hashlib
+                _write_publish_state(builder.paths.qlib_dir, "pending_qa", rep["staged_build_id"],
+                                     parent_build_id=live_build, transaction_id=txid,
+                                     record_sha256=_hashlib.sha256(record_bytes).hexdigest())
                 # the committed governance record is written LAST — nothing may claim a
                 # completed rebind before every durable step above proved out (Blocker 2b).
                 _write_rebind_record(
@@ -1818,7 +1885,7 @@ def phase_publish(args) -> int:
                     logger.critical("DISK STATE UNKNOWN after failure (%r) — neither parent-live "
                                     "nor child-live signature matches; recover manually per the "
                                     "intent journal (%s) + transaction journal (%s).",
-                                    exc, TRANSACTION_INTENT_PATH, TRANSACTION_JOURNAL_PATH)
+                                    exc, _intent_path(), TRANSACTION_JOURNAL_PATH)
                     if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                         raise
                     return 5
@@ -1829,7 +1896,7 @@ def phase_publish(args) -> int:
                 # artifact cleanup is DISK-DRIVEN by transaction id — never gated on
                 # in-process booleans (re-review #3 Major: an interrupt after the record's
                 # atomic replace but before a flag left a false 'published' record behind).
-                for artifact in (record_path, md_path):
+                for artifact in (record_path, report_snapshot_path, md_path):
                     try:
                         Path(artifact).unlink(missing_ok=True)
                     except OSError as uexc:
@@ -1923,9 +1990,10 @@ def _finalize_ready(builder, rep: dict, j, attempt: str) -> int:
     blocks publish AND finalize until --restore-parent — and exit 5; softer pin problems
     (records/policy/approvals) keep the current state for a retryable finalize, exit 5.
     QA is a sampling check; THIS gate is the proof."""
+    import hashlib as _hashlib
     from data_infra.tushare_lock import provider_publish_lock, raw_maintenance_lock
     qlib_dir = Path(builder.paths.qlib_dir)
-    with raw_maintenance_lock(), provider_publish_lock():
+    with raw_maintenance_lock(), provider_publish_lock(qlib_dir=qlib_dir):
         marker = _read_publish_state(qlib_dir)
         if (marker.get("active_qa_attempt") != attempt
                 or marker.get("provider_build_id") != rep["staged_build_id"]
@@ -1947,21 +2015,54 @@ def _finalize_ready(builder, rep: dict, j, attempt: str) -> int:
         policy_file = POLICY_DIR / f"{rep['new_policy_id']}.yaml"
         if not policy_file.is_file() or _sha256_file(policy_file) != rep["new_policy_sha256"]:
             soft.append("minted policy file hash drifted since the reviewed report")
+        # The RECORD is only trusted through the marker's digest binding (re-review #4 P0:
+        # a rewritten record plus a wrongly rebound approval previously reached ready) —
+        # locate it in the SHARED transaction dir via the marker's txid, require its
+        # sha256 to equal the one the marker pinned at publish, and cross-check every
+        # identity field against the reviewed report.
         txid = marker.get("transaction_id")
         record: dict = {}
         if not txid:
-            soft.append("marker carries no transaction_id — cannot locate this publish's record")
+            tamper.append("marker carries no transaction_id — cannot locate this publish's record")
         else:
+            record_file = _tx_dir() / f"publish_record_{txid}.json"
             try:
-                record = json.loads((OUT_DIR / f"publish_record_{txid}.json")
-                                    .read_text(encoding="utf-8"))
-            except (OSError, json.JSONDecodeError) as exc:
-                soft.append(f"publish record for transaction {txid} unreadable: {exc}")
-        if record and record.get("published_build_id") != rep["staged_build_id"]:
-            soft.append("publish record does not describe this build")
+                record_bytes = record_file.read_bytes()
+                if _hashlib.sha256(record_bytes).hexdigest() != marker.get("record_sha256"):
+                    tamper.append("publish record digest != the marker's pinned record_sha256 "
+                                  "(the record was rewritten after publish)")
+                record = json.loads(record_bytes.decode("utf-8"))
+            except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
+                tamper.append(f"publish record for transaction {txid} unreadable: {exc}")
+        if record:
+            expected_fields = {
+                "transaction_id": txid,
+                "published_build_id": rep["staged_build_id"],
+                "calendar_policy_id": rep["new_policy_id"],
+                "parent_build_id": rep["parent_build_id"],
+                "raw_input_manifest_root": rep["raw_input_manifest_root"],
+                "staged_content_root": rep["staged_content_root"],
+                "source_git_commit": rep["source_git_commit"],
+            }
+            mismatched = [k for k, v in expected_fields.items() if record.get(k) != v]
+            if mismatched:
+                tamper.append(f"publish record fields {mismatched} do not match the review")
         appr = _approvals_attestation()
         if appr["bound_count"] < 1 or appr["root"] != record.get("approvals_post_rebind_root"):
             soft.append("approvals governance set drifted since the rebind")
+        # SEMANTIC binding check (re-review #4 P0): every approval must actually bind to
+        # THIS live build/policy — root equality against a record can be forged, the
+        # binding evaluation cannot. Any drift is tamper-class.
+        try:
+            from data_infra.approval_evidence import evaluate_approval_evidence_bindings
+            drift = [d for d in evaluate_approval_evidence_bindings(
+                approvals_dir=APPROVALS_DIR,
+                manifest_path=qlib_dir / "metadata" / "provider_build.json") if d.drift]
+            if drift:
+                tamper.append(f"{len(drift)} approval binding(s) drift from the live manifest: "
+                              f"{drift[0].reasons()}")
+        except Exception as exc:  # noqa: BLE001 — governance loader failure = not certifiable
+            tamper.append(f"approval binding evaluation failed: {exc}")
         try:
             live_raw = json.loads((qlib_dir / "metadata" / "raw_input_manifest.json")
                                   .read_text(encoding="utf-8"))
@@ -1972,15 +2073,20 @@ def _finalize_ready(builder, rep: dict, j, attempt: str) -> int:
             tamper.append(f"in-tree raw manifest unreadable: {exc}")
         if not tamper and not soft:
             # SEAL the generation BEFORE the certifying hash (re-review #3 P0-2: one more
-            # hash cannot close the hash->ready window on a mutable tree). The marker file
-            # stays writable — it is the control plane the pointer lives in.
+            # hash cannot close the hash->ready window on a mutable tree). Exemption is the
+            # EXACT control-plane relpath; the external build manifest — part of the
+            # attestation — is sealed too (re-review #4 P0).
             sealed = _seal_tree_readonly(qlib_dir)
+            build_manifest = Path(builder.paths.build_root) / "manifest.json"
+            if build_manifest.is_file():
+                import stat as _stat
+                os.chmod(build_manifest, _stat.S_IREAD)
             logger.info("READY gate: sealed %d files read-only; FULL sealed-content "
                         "re-verification (%s files) ...", sealed,
                         rep.get("staged_content_file_count"))
             att = _staged_content_attestation(
                 qlib_dir, exclude=_LIVE_PUBLISH_FILES,
-                build_manifest_path=Path(builder.paths.build_root) / "manifest.json")
+                build_manifest_path=build_manifest)
             if att["root"] != rep["staged_content_root"]:
                 tamper.append(
                     f"SEALED content root {att['root']} != reviewed {rep['staged_content_root']}"
@@ -2006,27 +2112,49 @@ def _finalize_ready(builder, rep: dict, j, attempt: str) -> int:
     return 0
 
 
+def _load_tx_report() -> dict | None:
+    """The reviewed-report SNAPSHOT for the transaction the LIVE MARKER names — read from
+    the SHARED transaction dir (re-review #4 P0: finalize/restore must work from ANY
+    checkout, so they load the snapshot bound at publish, never this checkout's
+    workspace copy). None when the marker/txid/snapshot chain is broken."""
+    marker = _read_publish_state(_live_paths().qlib_dir)
+    txid = marker.get("transaction_id")
+    if not txid:
+        logger.error("live marker carries no transaction_id — no transaction to act on.")
+        return None
+    snap = _tx_dir() / f"report_{txid}.json"
+    try:
+        rep = json.loads(snap.read_text(encoding="utf-8"))
+        return rep if isinstance(rep, dict) else None
+    except (OSError, json.JSONDecodeError) as exc:
+        logger.error("report snapshot for transaction %s unreadable at %s (%s).", txid, snap, exc)
+        return None
+
+
 def phase_finalize_qa(args) -> int:
     """Re-run the QA + READY-gate leg for a provider stuck in 'pending_qa'/'qa_failed'
     (crash between swap and QA — including a deferred-SIGINT commit-core — or a QA failure
-    now resolved). CAS-verifies the live manifest against the reviewed report BEFORE
-    running QA; the full READY gate (:func:`_finalize_ready` — lease + seal + content root)
-    decides afterwards; a provider whose bytes changed since the review can NEVER be
-    marked ready by this path (it transitions to 'suspect' instead)."""
-    if not DRYRUN_REPORT_PATH.exists():
-        logger.error("no dry-run report at %s — nothing to finalize.", DRYRUN_REPORT_PATH)
+    now resolved). Works from ANY checkout: the reviewed pins come from the SHARED report
+    snapshot the marker's transaction id names. CAS-verifies the live manifest BEFORE
+    running QA; the full READY gate (:func:`_finalize_ready` — lease + record digest +
+    semantic binding drift + seal + content root) decides afterwards; a provider whose
+    bytes changed since the review can NEVER be marked ready by this path (it transitions
+    to 'suspect' instead)."""
+    if not _assert_standard_layout():
+        return 2
+    rep = _load_tx_report()
+    if rep is None:
         return 2
-    rep = json.loads(DRYRUN_REPORT_PATH.read_text(encoding="utf-8"))
     required = ("staged_build_id", "new_policy_id", "raw_input_manifest_root",
                 "parent_build_id", "source_git_commit", "new_policy_sha256",
                 "staged_content_root")
     missing = [k for k in required if not rep.get(k)]
     if missing:
-        logger.error("dry-run report lacks %s — cannot finalize. Refusing.", missing)
+        logger.error("report snapshot lacks %s — cannot finalize. Refusing.", missing)
         return 2
     builder = _make_publish_builder(rep["staged_build_id"])
     from data_infra.tushare_lock import provider_publish_lock, raw_maintenance_lock
-    with raw_maintenance_lock(), provider_publish_lock():
+    with raw_maintenance_lock(), provider_publish_lock(qlib_dir=builder.paths.qlib_dir):
         live_build, _ = live_provider_ids()
         if live_build != rep["staged_build_id"]:
             logger.error("live build %s is not the report's staged build %s — --finalize-qa only "
@@ -2059,18 +2187,23 @@ def phase_finalize_qa(args) -> int:
 
 def phase_restore_parent(args) -> int:
     """EXPLICIT recovery from a quarantined/suspect publish (re-review #3 disposition:
-    never silently auto-restore; provide a verified command instead). Under the
-    transaction locks: verifies the live build is the report's child AND the .bak parent's
-    manifest matches the report's parent ids; unseals the (possibly sealed) child tree;
-    reverse-rebinds the approval YAMLs child->parent (pure plan first, byte-verified);
+    never silently auto-restore; provide a verified command instead). Works from ANY
+    checkout (pins come from the SHARED report snapshot). Under the transaction locks and
+    a BaseException-safe, SIGINT-deferred domain (re-review #4 P0: an interrupt between
+    two reverse approval writes previously left a half-rebound live child that the
+    built-in recovery then refused): verifies the live build is the report's child AND
+    the .bak parent's manifest matches the parent ids; unseals the (possibly sealed)
+    child tree; reverse-rebinds the approval YAMLs child->parent (pure plan first);
     strips the publish-added files; swaps the parent back; verifies parent ids live +
-    0 binding drift; clears the marker (it travels back with the child tree) and marks the
-    intent 'aborted'. Exit 0 only when every check passes; else 5 with the journal."""
-    if not DRYRUN_REPORT_PATH.exists():
-        logger.error("no dry-run report at %s — cannot verify the restore against a review.",
-                     DRYRUN_REPORT_PATH)
+    0 binding drift. On ANY failure/interrupt mid-domain, the already-written reverse
+    approvals are restored (byte-verified) so the state returns to uniformly-child-bound
+    and --restore-parent can simply be re-run; interrupts journal 'restore_interrupted'
+    and re-raise. Exit 0 only when every check passes; else 5 with the journal."""
+    if not _assert_standard_layout():
+        return 2
+    rep = _load_tx_report()
+    if rep is None:
         return 2
-    rep = json.loads(DRYRUN_REPORT_PATH.read_text(encoding="utf-8"))
     builder = _make_publish_builder(rep["staged_build_id"])
     from data_infra.tushare_lock import provider_publish_lock, raw_maintenance_lock
 
@@ -2082,14 +2215,15 @@ def phase_restore_parent(args) -> int:
                                  "ts_cst": now_cst().isoformat(timespec="seconds"), **info})
         _write_journal(journal)
 
-    with raw_maintenance_lock(), provider_publish_lock():
+    with raw_maintenance_lock(), provider_publish_lock(qlib_dir=builder.paths.qlib_dir):
         qlib_dir = Path(builder.paths.qlib_dir)
         live_build, live_policy = live_provider_ids()
         if live_build != rep["staged_build_id"]:
             logger.error("live build %s is not the report's child %s — nothing to restore.",
                          live_build, rep["staged_build_id"])
             return 2
-        state = _read_publish_state(qlib_dir).get("state")
+        marker = _read_publish_state(qlib_dir)
+        state = marker.get("state")
         if state not in ("suspect", "pending_qa", "qa_failed"):
             logger.error("publish-state is %r — --restore-parent only undoes an uncertified "
                          "publish (suspect/pending_qa/qa_failed).", state)
@@ -2115,55 +2249,68 @@ def phase_restore_parent(args) -> int:
                          "bound to the child; repair from git first.", exc)
             return 2
         j("restore", "verified_preconditions", state=state)
+        txid = marker.get("transaction_id")
         problems: list[str] = []
-        unsealed = _unseal_tree(qlib_dir)
-        j("restore", "unsealed", files=unsealed)
         written: list[Path] = []
-        try:
-            for p, nd in reverse_plan:
-                _atomic_write_bytes(p, nd)
-                written.append(p)
-        except Exception as exc:  # noqa: BLE001
-            problems += _restore_approval_files(written, current_bytes)
-            problems.append(f"reverse rebind failed: {exc}")
-        if not problems:
-            txid = _read_publish_state(qlib_dir).get("transaction_id")
-            for name in ("provider_build.json", "publish_state.json"):
-                try:
+        with _defer_sigint("restore-parent"):
+            try:
+                unsealed = _unseal_tree(qlib_dir)
+                j("restore", "unsealed", files=unsealed)
+                for p, nd in reverse_plan:
+                    _atomic_write_bytes(p, nd)
+                    written.append(p)
+                for name in ("provider_build.json", "publish_state.json"):
                     (qlib_dir / "metadata" / name).unlink(missing_ok=True)
-                except OSError as uexc:
-                    problems.append(f"could not remove new-tree {name}: {uexc}")
-            ok_rb, rb_msg = _rollback_swap(builder)
-            if not ok_rb:
-                problems.append(f"swap-back failed: {rb_msg}")
-            else:
-                try:
-                    rb_build, rb_policy = live_provider_ids()
-                    if (rb_build, rb_policy) != (rep["parent_build_id"], rep["parent_policy_id"]):
-                        problems.append(f"post-restore live ids ({rb_build}/{rb_policy}) != parent")
-                except Exception as vexc:  # noqa: BLE001
-                    problems.append(f"post-restore live manifest unreadable: {vexc}")
-                from data_infra.approval_evidence import evaluate_approval_evidence_bindings
-                drifts = evaluate_approval_evidence_bindings(
-                    approvals_dir=APPROVALS_DIR,
-                    manifest_path=qlib_dir / "metadata" / "provider_build.json")
-                still = [d for d in drifts if d.drift]
-                if still:
-                    problems.append(f"{len(still)} approvals still drift after the restore")
-                if txid:
-                    for artifact in (OUT_DIR / f"publish_record_{txid}.json",):
+                ok_rb, rb_msg = _rollback_swap(builder)
+                if not ok_rb:
+                    problems.append(f"swap-back failed: {rb_msg}")
+                else:
+                    try:
+                        rb_build, rb_policy = live_provider_ids()
+                        if (rb_build, rb_policy) != (rep["parent_build_id"], rep["parent_policy_id"]):
+                            problems.append(
+                                f"post-restore live ids ({rb_build}/{rb_policy}) != parent")
+                    except Exception as vexc:  # noqa: BLE001
+                        problems.append(f"post-restore live manifest unreadable: {vexc}")
+                    from data_infra.approval_evidence import evaluate_approval_evidence_bindings
+                    drifts = evaluate_approval_evidence_bindings(
+                        approvals_dir=APPROVALS_DIR,
+                        manifest_path=qlib_dir / "metadata" / "provider_build.json")
+                    still = [d for d in drifts if d.drift]
+                    if still:
+                        problems.append(f"{len(still)} approvals still drift after the restore")
+                    if txid:
                         try:
-                            artifact.unlink(missing_ok=True)
+                            (_tx_dir() / f"publish_record_{txid}.json").unlink(missing_ok=True)
                         except OSError as uexc:
-                            problems.append(f"could not remove {artifact}: {uexc}")
-        _write_intent({**_read_intent(), "status": "aborted" if not problems
-                       else "rollback_incomplete"})
-        if problems:
-            j("restore", "incomplete", problems=problems)
-            logger.critical("RESTORE INCOMPLETE — resolve manually per the journal (%s): %s",
-                            TRANSACTION_JOURNAL_PATH, problems)
-            return 5
-        j("restore", "ok")
+                            problems.append(f"could not remove the transaction record: {uexc}")
+            except BaseException as exc:  # noqa: BLE001 — interrupts included (re-review #4)
+                # un-restore the partial reverse rebind so the state returns to
+                # uniformly-child-bound and this command can simply be re-run.
+                undo_failures = _restore_approval_files(written, current_bytes)
+                _write_intent({**_read_intent(), "status": "restore_interrupted"})
+                j("restore", "interrupted" if not undo_failures else "interrupted_incomplete",
+                  error=repr(exc), undo_failures=undo_failures)
+                logger.critical("RESTORE INTERRUPTED (%r) — partial reverse writes %s; re-run "
+                                "--restore-parent. Journal: %s", exc,
+                                "undone (byte-verified)" if not undo_failures
+                                else f"NOT fully undone: {undo_failures}",
+                                TRANSACTION_JOURNAL_PATH)
+                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
+                    raise
+                problems.append(f"restore aborted mid-domain: {exc!r}")
+                problems += undo_failures
+            # the final bookkeeping stays INSIDE the deferral: a deferred real SIGINT then
+            # fires only after the intent reached a settled status (a raise here would
+            # otherwise leave 'swapping'-era state blocking every future publish).
+            _write_intent({**_read_intent(), "status": "aborted" if not problems
+                           else "rollback_incomplete"})
+            if problems:
+                j("restore", "incomplete", problems=problems)
+                logger.critical("RESTORE INCOMPLETE — resolve manually per the journal (%s): %s",
+                                TRANSACTION_JOURNAL_PATH, problems)
+                return 5
+            j("restore", "ok")
     logger.info("RESTORED: the parent provider is live again; the child sits back at the staged "
                 "path for investigation. Approvals re-bound to the parent (0 drift).")
     return 0
diff --git a/src/data_infra/pit_backend.py b/src/data_infra/pit_backend.py
index dd91cc4..196f16e 100644
--- a/src/data_infra/pit_backend.py
+++ b/src/data_infra/pit_backend.py
@@ -4629,11 +4629,11 @@ class StagedQlibBackendBuilder:
         """
         # Phase 5-B B7: the GLOBAL provider-publish lock is acquired HERE, at the common
         # chokepoint, so every sanctioned publisher excludes every other regardless of
-        # entrypoint. Reentrant (per-path singleton FileLock — shared across the dual
-        # src./plain namespaces) — the monthly transaction already holding it nests
-        # without deadlock. Sibling-relative import resolves under either namespace root.
+        # entrypoint. Keyed by the EXACT provider dir this publish swaps (re-review #4
+        # P0). Reentrant (per-path singleton FileLock — shared across the dual src./plain
+        # namespaces) — the monthly transaction already holding it nests without deadlock.
         from .tushare_lock import provider_publish_lock
-        with provider_publish_lock():
+        with provider_publish_lock(qlib_dir=self.paths.qlib_dir):
             self._publish_locked(
                 calendar_policy_id=calendar_policy_id,
                 emit_manifest=emit_manifest,
diff --git a/src/data_infra/provider_manifest.py b/src/data_infra/provider_manifest.py
index aff2765..259615b 100644
--- a/src/data_infra/provider_manifest.py
+++ b/src/data_infra/provider_manifest.py
@@ -443,7 +443,7 @@ def _write_manifest_locked(qlib_dir: Path, manifest: ProviderManifest) -> Path:
     from .tushare_lock import provider_publish_lock
 
     target = manifest_path_for(qlib_dir)
-    with provider_publish_lock():
+    with provider_publish_lock(qlib_dir=qlib_dir):
         target.parent.mkdir(parents=True, exist_ok=True)
         tmp = target.with_name(target.name + f".tmp.{os.getpid()}")
         with open(tmp, "w", encoding="utf-8") as handle:
diff --git a/src/data_infra/tushare_lock.py b/src/data_infra/tushare_lock.py
index 6212007..4111745 100644
--- a/src/data_infra/tushare_lock.py
+++ b/src/data_infra/tushare_lock.py
@@ -50,35 +50,27 @@ class LockIdentityError(RuntimeError):
     identity is unknowable the safe action is to not mutate the store at all)."""
 
 
-def _resolve_lock_root(source_root: Path) -> Path:
-    """Repo-scoped lock root for the ACCOUNT-level lock (api_call_lock + rate spacing):
-    the git COMMON dir's parent — identical for every worktree of a repo, equal to the
-    checkout root for a plain clone. Best-effort by design (the Tushare account is a
-    per-machine resource, not a per-store one); data-store-guarding locks use
-    :func:`_resolve_data_lock_dir` instead, which is FAIL-CLOSED."""
-    import logging
-    import subprocess
-    try:
-        # git emits UTF-8 bytes; text=True would decode with the locale codepage (cp936 on
-        # this host) and MANGLE non-ASCII path components (the real repo root contains
-        # Chinese characters) — decode explicitly.
-        out = subprocess.check_output(
-            ["git", "rev-parse", "--git-common-dir"],
-            cwd=str(source_root), stderr=subprocess.DEVNULL,
-        ).decode("utf-8").strip()
-        common = Path(out)
-        if not common.is_absolute():
-            common = (source_root / common).resolve()
-        return common.parent
-    except Exception:  # noqa: BLE001 — degraded per-checkout namespace, loudly
-        logging.getLogger(__name__).warning(
-            "git common-dir resolution failed under %s — the ACCOUNT lock namespace "
-            "degrades to this checkout only.", source_root,
-        )
-        return source_root
-
-
-_LOCK_DIR = _resolve_lock_root(_SOURCE_ROOT) / "logs" / "locks"
+def _resolve_account_lock_dir(source_root: Path) -> Path:
+    """Lock directory for the ACCOUNT-level lock (api_call_lock + rate-spacing state):
+    a stable PER-USER directory keyed by an irreversible fingerprint of the Tushare
+    token (GPT re-review #4 Major: repo/checkout-anchored namespaces let two independent
+    clones on one machine call the SAME account concurrently). Token resolution: the
+    TUSHARE_TOKEN env var, else the checkout's .env file; no token resolves to the
+    conservative shared 'no_token' namespace (all no-token processes serialize)."""
+    import hashlib
+    token = os.environ.get("TUSHARE_TOKEN", "").strip()
+    if not token:
+        env_file = source_root / ".env"
+        try:
+            for line in env_file.read_text(encoding="utf-8").splitlines():
+                line = line.strip()
+                if line.startswith("TUSHARE_TOKEN=") and not line.startswith("#"):
+                    token = line.split("=", 1)[1].strip().strip('"').strip("'")
+                    break
+        except OSError:
+            token = ""
+    fingerprint = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16] if token else "no_token"
+    return Path.home() / ".quant_tushare_locks" / fingerprint
 
 
 def _resolve_data_lock_dir(source_root: Path) -> Path:
@@ -113,14 +105,19 @@ def _resolve_data_lock_dir(source_root: Path) -> Path:
         ) from exc
 
 
-def _lock_dir() -> Path:
-    _LOCK_DIR.mkdir(parents=True, exist_ok=True)
-    return _LOCK_DIR
+# Resolved lazily (see the _resolve_* functions). Tests inject isolation by assigning
+# these module attributes directly (a Path), never via env.
+_ACCOUNT_LOCK_DIR = None
+_DATA_LOCK_DIR = None
 
 
-# Resolved lazily from config.yaml storage.data_root (see _resolve_data_lock_dir). Tests
-# inject isolation by assigning this module attribute directly (a Path), never via env.
-_DATA_LOCK_DIR = None
+def _account_lock_dir() -> Path:
+    global _ACCOUNT_LOCK_DIR
+    if _ACCOUNT_LOCK_DIR is None:
+        _ACCOUNT_LOCK_DIR = _resolve_account_lock_dir(_SOURCE_ROOT)
+    d = Path(_ACCOUNT_LOCK_DIR)
+    d.mkdir(parents=True, exist_ok=True)
+    return d
 
 
 def _data_lock_dir() -> Path:
@@ -132,13 +129,44 @@ def _data_lock_dir() -> Path:
     return d
 
 
-def _filelock(name: str, timeout: float) -> FileLock:
-    return FileLock(str(_lock_dir() / name), timeout=timeout)
+def _resolve_provider_lock_path(source_root: Path, qlib_dir=None) -> Path:
+    """Lock FILE for the provider-publish lock, keyed by the CANONICAL LIVE PROVIDER
+    directory itself (GPT re-review #4 P0: config permits storage.qlib_data_dir to live
+    apart from storage.data_root — keying off the raw root gave two checkouts targeting
+    ONE provider two different locks). The lock file sits ADJACENT to the provider
+    (never inside it — the tree is what gets swapped), named after the provider dir.
+    ``qlib_dir`` overrides config resolution (the builder passes the exact tree it
+    swaps); an unresolvable identity raises :class:`LockIdentityError`."""
+    if qlib_dir is None:
+        try:
+            import yaml
+            with open(source_root / "config.yaml", "r", encoding="utf-8") as fh:
+                cfg = yaml.safe_load(fh) or {}
+            raw = ((cfg.get("storage") or {}).get("qlib_data_dir"))
+            if not raw or not str(raw).strip():
+                raise LockIdentityError(
+                    f"config.yaml under {source_root} declares no storage.qlib_data_dir — "
+                    "cannot derive the provider lock identity; refusing (fail closed)."
+                )
+            qlib_dir = Path(str(raw))
+            if not qlib_dir.is_absolute():
+                qlib_dir = source_root / qlib_dir
+        except LockIdentityError:
+            raise
+        except Exception as exc:  # noqa: BLE001
+            raise LockIdentityError(
+                f"cannot resolve storage.qlib_data_dir from {source_root / 'config.yaml'}: "
+                f"{exc} — the provider lock refuses (fail closed)."
+            ) from exc
+    q = Path(qlib_dir).resolve()
+    lock_dir = q.parent / ".locks"
+    lock_dir.mkdir(parents=True, exist_ok=True)
+    return lock_dir / f"provider_publish__{q.name}.lock"
 
 
 @contextmanager
 def api_call_lock(timeout: float = 1800.0):
-    with _filelock("tushare_api.lock", timeout):
+    with FileLock(str(_account_lock_dir() / "tushare_api.lock"), timeout=timeout):
         yield
 
 
@@ -156,18 +184,19 @@ def raw_maintenance_lock(timeout: float = 21600.0):  # 6h default — a monthly
 
 
 @contextmanager
-def provider_publish_lock(timeout: float = 7200.0):
+def provider_publish_lock(timeout: float = 7200.0, qlib_dir=None):
     """Process-exclusive LIVE-provider publish/swap + manifest writes (Phase 5-B B3; GPT
-    re-review Blocker 7 made this a GLOBAL publish lock, not a driver-private one; re-review
-    #3 P0 anchored its identity to the SHARED DATA ROOT — ``<data_root>/.locks/`` — so two
-    independent clones configured onto one store share ONE lock; an unresolvable identity
-    raises :class:`LockIdentityError` and the publish REFUSES, never proceeds under a
-    private namespace).
+    re-review Blocker 7 made this a GLOBAL publish lock; re-review #4 P0 keyed its identity
+    to the CANONICAL LIVE PROVIDER DIRECTORY itself — the lock file sits adjacent to the
+    provider (``<qlib_parent>/.locks/provider_publish__<qlib_name>.lock``), so ANY checkout
+    targeting the same provider shares ONE lock even when their raw data roots differ; an
+    unresolvable identity raises :class:`LockIdentityError` and the publish REFUSES).
 
     Held at the COMMON CHOKEPOINTS — ``StagedQlibBackendBuilder.publish()`` and the
-    ``provider_build.json`` emitters in ``provider_manifest`` acquire it themselves — so ANY
-    sanctioned publisher/manifest writer excludes any other, whichever entrypoint invoked it.
-    The monthly transaction additionally holds it across its whole verify->swap->rebind scope.
+    ``provider_build.json`` emitters pass the exact ``qlib_dir`` they mutate — so ANY
+    sanctioned publisher/manifest writer excludes any other, whichever entrypoint invoked
+    it. The monthly transaction additionally holds it across its whole
+    verify->swap->rebind scope.
 
     REENTRANT within a process/thread: the underlying ``FileLock`` is a per-path SINGLETON
     (``is_singleton=True``; verified on filelock 3.25.2 — same instance, counted acquire), so
@@ -175,7 +204,8 @@ def provider_publish_lock(timeout: float = 7200.0):
     deadlocking, while a second process still blocks. LOCK ORDER: any holder that also needs
     ``raw_maintenance_lock`` acquires raw FIRST, then this; publish-lock-only holders (the
     builder/emitters) never take the raw lock afterwards — no reverse-order path exists."""
-    lock = FileLock(str(_data_lock_dir() / "provider_publish.lock"), is_singleton=True)
+    lock = FileLock(str(_resolve_provider_lock_path(_SOURCE_ROOT, qlib_dir=qlib_dir)),
+                    is_singleton=True)
     lock.acquire(timeout=timeout)
     try:
         yield
@@ -183,9 +213,10 @@ def provider_publish_lock(timeout: float = 7200.0):
         lock.release()
 
 
-# ── global cross-process rate spacing (a shared next-allowed timestamp, held under the API lock) ──
+# ── global cross-process rate spacing (a shared next-allowed timestamp, held under the API lock;
+# lives in the PER-ACCOUNT namespace so independent clones share one spacing state) ──
 def _next_allowed_path() -> Path:
-    return _lock_dir() / "tushare_next_allowed.txt"
+    return _account_lock_dir() / "tushare_next_allowed.txt"
 
 
 def _read_next_allowed() -> tuple[float | None, bool]:
@@ -211,7 +242,7 @@ def _set_next_allowed(delta: float) -> bool:
     persisted, so the caller enforces the spacing IN-BAND (sleep while holding the API lock) rather than
     silently dropping it (GPT minor 1)."""
     try:
-        d = _lock_dir()
+        d = _account_lock_dir()
         fd, tmp = tempfile.mkstemp(dir=str(d), prefix=".next_allowed.", suffix=".tmp")
         try:
             with os.fdopen(fd, "w") as fh:
diff --git a/tests/data_infra/test_daily_update_5c.py b/tests/data_infra/test_daily_update_5c.py
index 1c30401..c8c506b 100644
--- a/tests/data_infra/test_daily_update_5c.py
+++ b/tests/data_infra/test_daily_update_5c.py
@@ -213,7 +213,7 @@ def test_spaced_call_fails_closed_when_state_unwritable(tmp_path, monkeypatch):
     # GPT minor 1: if the shared next-allowed timestamp can't be persisted, spacing must be enforced
     # IN-BAND (sleep under the API lock), never silently dropped to zero.
     import time as _time
-    monkeypatch.setattr(tushare_lock, "_LOCK_DIR", tmp_path / "locks")  # inject via attr, not env
+    monkeypatch.setattr(tushare_lock, "_ACCOUNT_LOCK_DIR", tmp_path / "locks")  # inject via attr, not env
     monkeypatch.setattr(tushare_lock, "_set_next_allowed", lambda delta: False)  # simulate unwritable
     t0 = _time.time()
     tushare_lock.spaced_call(lambda: "ok", 0.4)
@@ -224,7 +224,7 @@ def test_spaced_call_fails_closed_on_nan_state(tmp_path, monkeypatch):
     # GPT REWORK-5 minor 1: a state file containing `nan` parses via float() but makes delay>0 False and
     # fires immediately. isfinite-guard must force the conservative in-band sleep.
     import time as _time
-    monkeypatch.setattr(tushare_lock, "_LOCK_DIR", tmp_path / "locks")
+    monkeypatch.setattr(tushare_lock, "_ACCOUNT_LOCK_DIR", tmp_path / "locks")
     (tmp_path / "locks").mkdir(parents=True)
     tushare_lock._next_allowed_path().write_text("nan")
     t0 = _time.time()
diff --git a/tests/data_infra/test_fetchers.py b/tests/data_infra/test_fetchers.py
index 38ca678..d206899 100644
--- a/tests/data_infra/test_fetchers.py
+++ b/tests/data_infra/test_fetchers.py
@@ -97,7 +97,7 @@ def test_locked_pro_routes_calls_and_refuses_raw_escape(tmp_path, monkeypatch):
     import pytest
     from data_infra import tushare_lock
     from data_infra.fetchers import _LockedPro
-    monkeypatch.setattr(tushare_lock, "_LOCK_DIR", tmp_path / "locks")  # inject via attr, not env
+    monkeypatch.setattr(tushare_lock, "_ACCOUNT_LOCK_DIR", tmp_path / "locks")  # inject via attr, not env
 
     captured = []
 
diff --git a/tests/data_infra/test_monthly_calendar_bump.py b/tests/data_infra/test_monthly_calendar_bump.py
index 6e51458..b9535bc 100644
--- a/tests/data_infra/test_monthly_calendar_bump.py
+++ b/tests/data_infra/test_monthly_calendar_bump.py
@@ -550,8 +550,10 @@ def _publish_env(tmp_path, monkeypatch, *, qa_rc: int = 0):
     monkeypatch.setattr(mcb, "RAW_MANIFEST_PATH", out / "raw_input_manifest.json")
     monkeypatch.setattr(mcb, "PUBLISH_RECORD_PATH", out / "publish_record.json")
     monkeypatch.setattr(mcb, "TRANSACTION_JOURNAL_PATH", out / "publish_transaction_journal.json")
-    monkeypatch.setattr(mcb, "TRANSACTION_INTENT_PATH", out / "publish_intent.json")
     monkeypatch.setattr(mcb, "_run_post_publish_qa", lambda: qa_rc)
+    monkeypatch.setattr(mcb, "_live_paths",
+                        lambda: _types.SimpleNamespace(data_root=str(root / "data"),
+                                                       qlib_dir=str(root / "data" / "qlib_data")))
     import data_infra.tushare_lock as _tl
     monkeypatch.setattr(_tl, "_DATA_LOCK_DIR", root / "locks")
 
@@ -578,6 +580,11 @@ def _publish_env(tmp_path, monkeypatch, *, qa_rc: int = 0):
     (staged / "features" / "000001_sz").mkdir(parents=True)
     (staged / "features" / "000001_sz" / "close.day.bin").write_bytes(b"\x01\x02\x03\x04")
     (staged / "STAGED_MARKER.txt").write_text("child", encoding="utf-8")
+    # a payload file that shares the control-plane BASENAME (re-review #4 P0: the seal
+    # exemption must be by exact relpath, not name)
+    (staged / "metadata" / "audit_payload").mkdir(parents=True)
+    (staged / "metadata" / "audit_payload" / "publish_state.json").write_text(
+        '{"decoy": true}', encoding="utf-8")
     (data / "qlib_builds" / new_pb / "manifest.json").write_text("{}", encoding="utf-8")
 
     # the minted policy the report points at
@@ -611,7 +618,6 @@ def _publish_env(tmp_path, monkeypatch, *, qa_rc: int = 0):
     raw.write_bytes(b"CAL0")
     manifest = mcb._full_raw_manifest(data)
     (out / "raw_input_manifest.json").write_text(_json.dumps(manifest), encoding="utf-8")
-    (staged / "metadata").mkdir()
     (staged / "metadata" / "raw_input_manifest.json").write_text(
         _json.dumps(manifest), encoding="utf-8")
 
@@ -1150,7 +1156,7 @@ def test_publish_systemexit_right_after_swap_rolls_back_via_disk_truth(tmp_path,
     assert mcb.live_provider_ids() == (env.parent_pb, env.parent_cp)
     assert env.a1.read_bytes() == env.a1_bytes and env.a2.read_bytes() == env.a2_bytes
     assert (env.staged / "STAGED_MARKER.txt").exists()
-    intent = _json.loads((env.out / "publish_intent.json").read_text(encoding="utf-8"))
+    intent = _json.loads(mcb._intent_path().read_text(encoding="utf-8"))
     assert intent["status"] == "aborted"
 
 
@@ -1192,13 +1198,159 @@ def test_ready_seal_blocks_later_writes(tmp_path, monkeypatch):
         (env.qlib / "features" / "000001_sz" / "close.day.bin").write_bytes(b"\x0c\x0c\x0c\x0c")
 
 
-def test_unresolved_intent_blocks_new_publish(tmp_path, monkeypatch):
+def test_unresolved_intent_blocks_new_publish_cross_checkout(tmp_path, monkeypatch):
+    # Re-review #4 P0: the intent journal lives in the STORE's transaction dir (adjacent
+    # to the provider), so a hard crash in ANY checkout blocks a publish from EVERY
+    # checkout sharing the store — never checkout-local workspace state.
     env = _publish_env(tmp_path, monkeypatch)
     mcb._write_intent({"transaction_id": "deadbeef", "status": "swapping"})
+    assert mcb._intent_path().is_relative_to(env.data), \
+        "the intent journal must live inside the shared store, not the checkout workspace"
     assert mcb.phase_publish(_PubArgs()) == 2
     _assert_untouched(env)
 
 
+# ── GPT re-review #3 probes (record forge / seal relpath / restore interrupt / locks) ─
+def test_finalize_refuses_forged_record(tmp_path, monkeypatch):
+    # P0 probe: after qa_failed, forge ONE approval to another build AND rewrite the
+    # per-transaction record's approvals_post_rebind_root to the new current root. The
+    # marker's pinned record digest breaks -> tamper-class refusal (suspect), never ready.
+    env = _publish_env(tmp_path, monkeypatch, qa_rc=1)
+    assert mcb.phase_publish(_PubArgs()) == 6
+    forged = env.a2.read_text(encoding="utf-8").replace(env.new_pb, "forged_other_build")
+    env.a2.write_text(forged, encoding="utf-8")
+    marker = _json.loads((env.qlib / "metadata" / "publish_state.json").read_text(encoding="utf-8"))
+    record_file = env.data / "qlib_transactions" / f"publish_record_{marker['transaction_id']}.json"
+    record = _json.loads(record_file.read_text(encoding="utf-8"))
+    record["approvals_post_rebind_root"] = mcb._approvals_attestation()["root"]
+    record_file.write_text(_json.dumps(record, indent=1), encoding="utf-8")
+    monkeypatch.setattr(mcb, "_run_post_publish_qa", lambda: 0)
+    assert mcb.phase_finalize_qa(_PubArgs()) == 5
+    assert _publish_state_of(env.qlib) == "suspect", "a forged record must quarantine, not certify"
+
+
+def test_finalize_refuses_binding_drift_even_with_consistent_forge(tmp_path, monkeypatch):
+    # P0 probe (deeper): the attacker ALSO re-pins the marker's record_sha256 so the
+    # digest check passes — the SEMANTIC binding evaluation still catches the approval
+    # bound to a foreign build. No root-equality shortcut can fake it.
+    import hashlib as _hl
+    env = _publish_env(tmp_path, monkeypatch, qa_rc=1)
+    assert mcb.phase_publish(_PubArgs()) == 6
+    forged = env.a2.read_text(encoding="utf-8").replace(env.new_pb, "forged_other_build")
+    env.a2.write_text(forged, encoding="utf-8")
+    marker_path = env.qlib / "metadata" / "publish_state.json"
+    marker = _json.loads(marker_path.read_text(encoding="utf-8"))
+    record_file = env.data / "qlib_transactions" / f"publish_record_{marker['transaction_id']}.json"
+    record = _json.loads(record_file.read_text(encoding="utf-8"))
+    record["approvals_post_rebind_root"] = mcb._approvals_attestation()["root"]
+    record_bytes = _json.dumps(record, ensure_ascii=False, indent=1).encode("utf-8")
+    record_file.write_bytes(record_bytes)
+    marker["record_sha256"] = _hl.sha256(record_bytes).hexdigest()
+    marker_path.write_text(_json.dumps(marker, indent=1), encoding="utf-8")
+    monkeypatch.setattr(mcb, "_run_post_publish_qa", lambda: 0)
+    assert mcb.phase_finalize_qa(_PubArgs()) == 5
+    assert _publish_state_of(env.qlib) == "suspect"
+    steps = _json.loads((env.out / "publish_transaction_journal.json").read_text(encoding="utf-8"))["steps"]
+    bad = [s for s in steps if s["status"] == "refused_suspect"]
+    assert bad and any("binding" in p for p in bad[0]["problems"])
+
+
+def test_seal_covers_nested_control_plane_basename_and_build_manifest(tmp_path, monkeypatch):
+    # P0 probe: a payload file NAMED publish_state.json in a nested dir was previously
+    # exempt (basename comparison) and writable after ready; the exemption is now the
+    # exact relpath. The external build manifest (part of the attestation) seals too.
+    env = _publish_env(tmp_path, monkeypatch)
+    assert mcb.phase_publish(_PubArgs()) == 0
+    decoy = env.qlib / "metadata" / "audit_payload" / "publish_state.json"
+    with pytest.raises(PermissionError):
+        decoy.write_text('{"tampered": true}', encoding="utf-8")
+    with pytest.raises(PermissionError):
+        (env.data / "qlib_builds" / env.new_pb / "manifest.json").write_text("{}", encoding="utf-8")
+    # the REAL control-plane marker stays writable
+    mcb._write_publish_state(env.qlib, "ready", env.new_pb)
+
+
+def test_restore_parent_interrupt_rolls_back_partial_rebind(tmp_path, monkeypatch):
+    # P0 probe: KeyboardInterrupt between the two REVERSE approval writes previously left
+    # a half-rebound child live and the built-in recovery refused. The restore domain is
+    # now BaseException-safe: partial reverse writes are undone (byte-verified) so
+    # --restore-parent can simply be re-run.
+    env = _publish_env(tmp_path, monkeypatch, qa_rc=1)
+    assert mcb.phase_publish(_PubArgs()) == 6  # quarantined child live
+    a1_child, a2_child = env.a1.read_bytes(), env.a2.read_bytes()
+    real = mcb._atomic_write_bytes
+    seen: list[Path] = []
+
+    def interrupt_second_reverse(path, data):
+        p = Path(path)
+        if p.parent == env.root / "approvals" and p.suffix == ".yaml":
+            seen.append(p)
+            if len(seen) == 2:
+                raise KeyboardInterrupt("probe: Ctrl-C mid reverse rebind")
+        real(path, data)
+
+    monkeypatch.setattr(mcb, "_atomic_write_bytes", interrupt_second_reverse)
+    with pytest.raises(KeyboardInterrupt):
+        mcb.phase_restore_parent(_PubArgs())
+    assert env.a1.read_bytes() == a1_child and env.a2.read_bytes() == a2_child, \
+        "partial reverse writes must be undone — approvals uniformly child-bound again"
+    assert (env.qlib / "STAGED_MARKER.txt").exists(), "child still live (restore aborted cleanly)"
+    monkeypatch.setattr(mcb, "_atomic_write_bytes", real)
+    assert mcb.phase_restore_parent(_PubArgs()) == 0, "the restore must be re-runnable"
+    assert mcb.live_provider_ids() == (env.parent_pb, env.parent_cp)
+
+
+def test_publish_refuses_nonstandard_layout(tmp_path, monkeypatch):
+    env = _publish_env(tmp_path, monkeypatch)
+    monkeypatch.setattr(mcb, "_live_paths",
+                        lambda: _types.SimpleNamespace(data_root=str(tmp_path / "elsewhere"),
+                                                       qlib_dir=str(env.qlib)))
+    assert mcb.phase_publish(_PubArgs()) == 2
+    assert (env.staged / "STAGED_MARKER.txt").exists()
+
+
+def test_provider_lock_keyed_by_qlib_dir_not_raw_root(tmp_path):
+    # Re-review #4 P0: two checkouts with DIFFERENT raw data_roots but ONE live provider
+    # must resolve the SAME provider-publish lock file.
+    import data_infra.tushare_lock as tl
+
+    shared_qlib = tmp_path / "store" / "qlib_data"
+    shared_qlib.mkdir(parents=True)
+    a, b = tmp_path / "cloneA", tmp_path / "cloneB"
+    for c, raw in ((a, "rawA"), (b, "rawB")):
+        c.mkdir()
+        (c / "config.yaml").write_text(
+            "storage:\n"
+            f"  data_root: {_json.dumps(str(tmp_path / raw))}\n"
+            f"  qlib_data_dir: {_json.dumps(str(shared_qlib))}\n", encoding="utf-8")
+    lock_a = tl._resolve_provider_lock_path(a)
+    lock_b = tl._resolve_provider_lock_path(b)
+    assert lock_a == lock_b == shared_qlib.parent.resolve() / ".locks" / "provider_publish__qlib_data.lock"
+    # explicit qlib_dir override (what the builder passes) resolves identically
+    assert tl._resolve_provider_lock_path(a, qlib_dir=shared_qlib) == lock_a
+    # unresolvable identity refuses
+    blank = tmp_path / "blank"
+    blank.mkdir()
+    (blank / "config.yaml").write_text("storage: {}\n", encoding="utf-8")
+    with pytest.raises(tl.LockIdentityError):
+        tl._resolve_provider_lock_path(blank)
+
+
+def test_account_lock_is_per_token_not_per_checkout(tmp_path, monkeypatch):
+    # Re-review #4 Major: the Tushare account lock namespace is a per-user directory keyed
+    # by the token fingerprint — identical for ANY checkout under the same token, distinct
+    # across tokens.
+    import data_infra.tushare_lock as tl
+
+    monkeypatch.setenv("TUSHARE_TOKEN", "tok_A_secret")
+    a = tl._resolve_account_lock_dir(tmp_path / "cloneA")
+    b = tl._resolve_account_lock_dir(tmp_path / "cloneB")
+    assert a == b and a.parent == Path.home() / ".quant_tushare_locks"
+    assert "tok_A_secret" not in str(a), "the token must appear only as an irreversible fingerprint"
+    monkeypatch.setenv("TUSHARE_TOKEN", "tok_B_other")
+    assert tl._resolve_account_lock_dir(tmp_path / "cloneA") != a
+
+
 def test_stale_qa_worker_cannot_overwrite_ready(tmp_path, monkeypatch):
     # Re-review #3 Major: worker A begins a QA attempt; worker B begins a NEWER attempt
     # (taking the lease) and reaches ready; A's delayed failure must record 'superseded'
@@ -1231,8 +1383,8 @@ def test_builder_publish_acquires_global_lock(tmp_path, monkeypatch):
     from contextlib import contextmanager
 
     @contextmanager
-    def recording(timeout: float = 7200.0):
-        entered.append(timeout)
+    def recording(timeout: float = 7200.0, qlib_dir=None):
+        entered.append(qlib_dir)  # publish() must key the lock by the EXACT provider dir
         yield
 
     monkeypatch.setattr(tl, "provider_publish_lock", recording)
@@ -1243,4 +1395,5 @@ def test_builder_publish_acquires_global_lock(tmp_path, monkeypatch):
     b = StagedQlibBackendBuilder(data_root=str(data), qlib_dir=str(data / "qlib_data"),
                                  build_id="lockprobe")
     b.publish(calendar_policy_id="frozen_20260701_thaw_step1", emit_manifest=False)
-    assert entered, "publish() must acquire the global provider-publish lock"
+    assert entered and Path(entered[0]).resolve() == (data / "qlib_data").resolve(), \
+        "publish() must acquire the provider-publish lock keyed by its own qlib_dir"
```

RE-REVIEW QUESTIONS
1. Re-run your five P0 probes + the account-lock Major: per-probe pass/fail table.
2. The shared transaction dir <data_root>/qlib_transactions/ is inside the (gitignored) data store — correct home? Does binding recovery to the LIVE MARKER's transaction_id (rather than a checkout-local report) fully close the cross-checkout inheritance, or is there a residual where the marker names a txid whose snapshot is absent (e.g. a hand-deleted qlib_transactions/)? The finalize path returns 2 in that case — sufficient?
3. The record_sha256 + field cross-check + semantic-binding triple at finalize: is any single one redundant, or do you want all three? Is there a forge that survives all three (e.g. rewriting BOTH the record AND the report snapshot AND re-pinning record_sha256 — note the snapshot is itself in the shared dir, unsigned)? If the snapshot is a soft link in the trust chain, propose the exact hardening (a snapshot digest in the marker too?).
4. _assert_standard_layout refuses split/relocated layouts entirely (the GPT-sanctioned alternative to threading BuildPaths through every raw reader). Acceptable as a hard constraint, or must split-root be supported?
5. Rule on R1/R2/R3 (seal-vs-new-files, .bak pruning attributes, QA-lease liveness) — Blocker / Major / accept.
6. Anything NEW the fixes opened: the per-token account lock reads .env — any path where a wrong/empty token silently narrows serialization? The restore's deferred-SIGINT-after-settled-intent ordering — any interrupt window it leaves?
7. Final ruling: SHIP the code contingent on the operator drill (disposable-copy full-cycle + timing/memory measurements) + §13 for the first live run, or more code work first?

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending line quoted and an exact suggested replacement.
- Explicit per-probe pass/fail table for your re-review #4 probes.
- Final line: SHIP / REVISE / REWORK, plus the single most important residual risk.
```
