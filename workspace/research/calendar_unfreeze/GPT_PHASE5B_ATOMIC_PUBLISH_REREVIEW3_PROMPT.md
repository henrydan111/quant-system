# GPT 5.5 Pro re-review #3 — Phase 5-B atomic publish: re-review #2 P0/P1 closed

> Send verbatim to GPT 5.5 Pro. Branch pushed; pinned HEAD: `bb6e797` (fix commit `ff8c25f`,
> docs `bb6e797`; your re-review #2 baseline was `e4ceeea`).

```text
ROLE
You are the same senior reviewer who issued REWORK #2 on this change (6 P0 + 1 P1, reproduced via interrupt / cross-worktree / TOCTOU probes). Re-review adversarially: re-run each of your probes against the new code and hunt for holes the fixes opened. Do not rubber-stamp.

REPO (public — fetch any file to verify against the live code)
https://github.com/henrydan111/quant-system   (branch: calendar-unfreeze-phase5b-atomic-publish)
Raw file form: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/<path>

KEY FILES (updated this round)
- Driver: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/scripts/monthly_calendar_bump.py
- Locks (git-common-dir identity): https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/src/data_infra/tushare_lock.py
- Gates (strict marker binding): https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/src/research_orchestrator/release_gate.py
- Tests (your probes as regressions): https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/tests/data_infra/test_monthly_calendar_bump.py
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/tests/research_orchestrator/test_provider_raw_attestation_gate.py
- Self-review round 3: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/workspace/research/calendar_unfreeze/PHASE5B_ATOMIC_PUBLISH_SELF_REVIEW.md
- Invariants: CLAUDE.md 3.4 (re-review #2 hardenings paragraph)

FINDING-BY-FINDING DISPOSITION (verify each against the diff below)
P0-1 lock not global across worktrees -> lock identity anchored to the GIT COMMON DIR's parent: _resolve_lock_root(source_root) runs `git rev-parse --git-common-dir` (bytes decoded EXPLICITLY as UTF-8 — your probe test caught a real bug where text=True decoded git's UTF-8 output with cp936 and mangled the Chinese repo path into a distinct mojibake lock dir), resolves relative ".git" for a plain clone (path unchanged for the production daily job) and the absolute common dir for a worktree. All worktrees of the repo now share one lock namespace; degraded per-checkout fallback ONLY when git itself is unavailable, with a loud warning — never env. Probe-replica: test_lock_root_is_shared_across_worktrees (real git repo + linked worktree, both resolve to the main root); the running worktree's _LOCK_DIR verified byte-equal to the main checkout's logs/locks.
P0-2 interrupt bypasses rollback -> the protected domain catches BaseException; SIGINT is DEFERRED across the swap+bind span (_defer_sigint: handler records, re-raises KeyboardInterrupt at span exit; main-thread only, non-main threads fall through to the BaseException belt). The swap retry loop moved INSIDE the domain with a swap_completed flag: pre-completion failures/interrupts rely on the primitive's self-rollback (journal "aborted_pre_completion", re-raise); post-completion interrupts run the FULL verified undo (restore+delete artifacts+strip tree+rollback+verify) and then re-raise (journal "interrupted_rolled_back" / "interrupted_rollback_incomplete"). Probe-replicas: test_publish_interrupt_mid_rebind_rolls_back_then_reraises (KeyboardInterrupt injected between the two approval writes -> byte-identical approvals, parent live, no md/record, THEN the interrupt propagates), test_publish_systemexit_mid_rebind_rolls_back.
P0-3 hash->swap TOCTOU + P0-4 finalize greens changed bytes (one merged fix) -> the READY gate is the TOCTOU boundary. publish-state 'ready' is only ever written by _finalize_ready, which under raw+publish locks re-verifies EVERY pin against the LIVE tree: manifest CAS (build/policy/raw-root/parent/execute-commit), minted-policy file hash, post-rebind approvals set (a NEW approvals_post_rebind_root is pinned into the publish record inside the bind domain), in-tree raw-manifest self-consistency, and the FULL live content root (exclude = exactly metadata/provider_build.json + metadata/publish_state.json; the build manifest passed explicitly from the retained build root). Any byte changed AFTER the audited build — including during QA — refuses ready (exit 5, quarantine persists). phase_finalize_qa additionally CAS-verifies the live manifest under the locks BEFORE running QA and requires the report's pin keys. QA is a sampling check; the READY gate is the proof. Probe-replicas: test_ready_gate_refuses_bytes_changed_after_swap (QA itself tampers a live bin then "passes" -> exit 5, pending_qa persists, journal names the content root), test_finalize_qa_cannot_green_changed_bytes (qa_failed -> tamper -> QA passes -> still exit 5/qa_failed; restore original bytes -> ready).
P0-5 unbound ready marker -> a present marker MUST carry a non-blank string provider_build_id (missing/blank/non-string refuses, regardless of policy or manifest); equality with the live manifest build id is mandatory when the manifest is supplied. Probe-replica: the unbound {"state":"ready"} case in test_publish_state_gate_quarantines_until_ready.
P0-6 raw provenance from a mutable sidecar -> publish derives raw provenance from the ATTESTED in-tree copy <staged>/metadata/raw_input_manifest.json (written at execute BEFORE the content attestation, hence covered by staged_content_root): the copy's root is self-checked against its own file list, must equal the report AND the OUT_DIR sidecar, its file list drives _verify_raw_manifest, and its root is what publish() emits into provider_build.json. The READY gate re-checks the in-tree copy's self-consistency on the live tree. Probe-replica: test_publish_refuses_raw_provenance_mismatch (report+sidecar consistently forged to R2 while the attested staged copy says R1 -> refuse, nothing mutated).
P1 memory -> _staged_content_attestation streams per group: each features/<code> dir (and each other top-level entry) is walked, hashed on a shared thread pool, reduced to ONE group digest, and released before the next group; only the ~5.8k group digests are retained — never the 23M-file path/digest/line lists. Group semantics and line format unchanged (root parity across the whole battery).

COST DISCLOSURE (updated)
The full-content attestation now runs THREE times per publish: execute (pin), pre-swap (fail-early refusal), READY gate (the security boundary). Each is a full staged-tree read (tens of minutes at 241GB/23M files, monthly). If you consider the pre-swap read redundant given the READY gate, say so explicitly — it is kept as fail-early (refuse-before-swap is cheaper than rollback-after).

VERIFICATION (this round)
Focused battery 189 green (+7 probe replicas listed above). Combined four suites: 1070 green / 16 skipped; the failure set is file-by-file identical to the environmental baseline you already inspected. The worktree's resolved _LOCK_DIR verified exactly equal to the main checkout's logs/locks. No live-provider touch this session.

WHAT CHANGED (authoritative — the full fix diff, commit ff8c25f):

```diff
diff --git a/scripts/monthly_calendar_bump.py b/scripts/monthly_calendar_bump.py
index e0a6340..fa1915c 100644
--- a/scripts/monthly_calendar_bump.py
+++ b/scripts/monthly_calendar_bump.py
@@ -412,6 +412,38 @@ class PublishTransactionError(RuntimeError):
     unless the message says otherwise)."""
 
 
+from contextlib import contextmanager
+
+
+@contextmanager
+def _defer_sigint(span: str):
+    """Defer Ctrl-C across the CRITICAL transaction span (re-review P0: an interrupt
+    landing between two approval writes previously bypassed the `except Exception`
+    rollback and left a half-rebound live provider). SIGINT received inside the span is
+    recorded and re-raised as KeyboardInterrupt at span exit — after the swap+bind (or
+    their verified rollback) completed. No-op outside the main thread (signal handlers
+    are main-thread-only; the BaseException handler remains the belt there)."""
+    import signal
+    import threading
+    if threading.current_thread() is not threading.main_thread():
+        yield
+        return
+    received: list = []
+
+    def _handler(signum, frame):  # noqa: ARG001
+        received.append(signum)
+        logger.warning("SIGINT received during the %s span — DEFERRED until the "
+                       "transaction reaches a consistent state.", span)
+
+    previous = signal.signal(signal.SIGINT, _handler)
+    try:
+        yield
+    finally:
+        signal.signal(signal.SIGINT, previous)
+        if received:
+            raise KeyboardInterrupt(f"deferred SIGINT after the {span} span")
+
+
 def _atomic_write_bytes(path: Path, data: bytes) -> None:
     import tempfile
     fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
@@ -424,60 +456,84 @@ def _atomic_write_bytes(path: Path, data: bytes) -> None:
             os.remove(tmp)
 
 
-def _staged_content_attestation(staged_provider, *, workers: int = 8) -> dict:
-    """FULL-CONTENT attestation over the ENTIRE staged provider tree (GPT re-review
-    Blocker 4: the published feature bytes themselves must be proven, not just identity
-    files — a build-id path is a naming convention, not an immutability control).
-
-    Every file under the staged provider (features/*.bin included) AND the build
-    manifest.json at <build_root>/manifest.json is content-hashed (sha256, thread-pooled —
-    23M small files are open-latency-bound, not bandwidth-bound). Files are grouped by
-    top-level entry (each features/<code>/ dir collapses to one group digest over its
-    sorted "relpath:size:sha256" lines) so a publish-time mismatch localizes without a
-    multi-GB sidecar; the root is the sha256 over the sorted group map. Recomputed at
-    publish IMMEDIATELY before the swap and compared to the execute-time root — any byte
-    that changed since the audited build refuses the publish. Cost: one full read of the
-    staged tree per side (disclosed; a monthly operation after a multi-hour build)."""
+def _staged_content_attestation(tree, *, workers: int = 8, exclude: tuple[str, ...] = (),
+                                build_manifest_path=None) -> dict:
+    """FULL-CONTENT attestation over an ENTIRE provider tree (GPT re-review Blocker 4: the
+    published feature bytes themselves must be proven, not just identity files).
+
+    Every file under the tree (features/*.bin included) AND the build manifest.json is
+    content-hashed (sha256; a shared thread pool — 23M small files are open-latency-bound).
+    STREAMING BY GROUP (re-review P1: materializing 23M paths+digests+lines at once would
+    exhaust memory): each top-level entry / features/<code> dir is walked, hashed, reduced
+    to ONE group digest over its sorted "relpath:size:sha256" lines, and released before
+    the next group; only the ~5.8k group digests are retained. The root is the sha256 over
+    the sorted group map.
+
+    ``exclude`` (tree-relative forward-slash paths) lets the READY-gate re-verification
+    skip exactly the files the publish itself adds to the live tree
+    (metadata/provider_build.json, metadata/publish_state.json). ``build_manifest_path``
+    defaults to <tree_parent>/manifest.json (the staged layout); the live-tree ready check
+    passes the retained build root's manifest explicitly."""
     import hashlib
     from concurrent.futures import ThreadPoolExecutor
 
-    prov = Path(staged_provider)
+    prov = Path(tree)
     if not prov.is_dir():
         return {"algo": "sha256_grouped_full_content", "root": "MISSING_STAGED_DIR",
                 "file_count": 0, "total_bytes": 0, "groups": {}}
+    excluded = set(exclude)
+    groups: dict[str, str] = {}
+    file_count = 0
+    total_bytes = 0
 
-    def _group_of(rel: str) -> str:
-        parts = rel.split("/")
-        if len(parts) >= 3 and parts[0] == "features":
-            return f"features/{parts[1]}"
-        return parts[0] if len(parts) > 1 else f"<top>/{parts[0]}"
-
-    files = sorted(
-        (str(p.relative_to(prov)).replace("\\", "/"), p)
-        for p in prov.rglob("*") if p.is_file()
-    )
-    build_manifest = prov.parent / "manifest.json"
-    if build_manifest.is_file():
-        files.append(("<build_root>/manifest.json", build_manifest))
+    def _rel(p: Path) -> str:
+        return str(p.relative_to(prov)).replace("\\", "/")
 
-    total_bytes = 0
-    lines_by_group: dict[str, list[str]] = {}
     with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
-        digests = list(pool.map(lambda item: _sha256_file(item[1]), files))
-    for (rel, p), digest in zip(files, digests):
-        size = p.stat().st_size
-        total_bytes += size
-        lines_by_group.setdefault(_group_of(rel), []).append(f"{rel}:{size}:{digest}")
-
-    groups = {
-        g: hashlib.sha256("\n".join(sorted(lines)).encode("utf-8")).hexdigest()
-        for g, lines in lines_by_group.items()
-    }
+        def hash_group(name: str, paths: list) -> None:
+            nonlocal file_count, total_bytes
+            rels = [_rel(p) if not isinstance(p, tuple) else p[0] for p in paths]
+            fps = [p if not isinstance(p, tuple) else p[1] for p in paths]
+            digests = list(pool.map(_sha256_file, fps))
+            lines = []
+            for rel, fp, dg in zip(rels, fps, digests):
+                size = fp.stat().st_size
+                total_bytes += size
+                lines.append(f"{rel}:{size}:{dg}")
+            file_count += len(lines)
+            groups[name] = hashlib.sha256("\n".join(sorted(lines)).encode("utf-8")).hexdigest()
+
+        def files_under(d: Path) -> list:
+            return [p for p in sorted(d.rglob("*")) if p.is_file() and _rel(p) not in excluded]
+
+        for entry in sorted(prov.iterdir(), key=lambda p: p.name):
+            if entry.is_file():
+                if _rel(entry) not in excluded:
+                    hash_group(f"<top>/{entry.name}", [entry])
+            elif entry.name == "features":
+                direct = [p for p in sorted(entry.iterdir())
+                          if p.is_file() and _rel(p) not in excluded]
+                if direct:
+                    hash_group("features", direct)
+                for code_dir in sorted(p for p in entry.iterdir() if p.is_dir()):
+                    fs = files_under(code_dir)
+                    if fs:
+                        hash_group(f"features/{code_dir.name}", fs)
+            else:
+                fs = files_under(entry)
+                if fs:
+                    hash_group(entry.name, fs)
+
+        build_manifest = (Path(build_manifest_path) if build_manifest_path is not None
+                          else prov.parent / "manifest.json")
+        if build_manifest.is_file():
+            hash_group("<build_root>", [("<build_root>/manifest.json", build_manifest)])
+
     root = hashlib.sha256(
         "\n".join(f"{g}:{h}" for g, h in sorted(groups.items())).encode("utf-8")
     ).hexdigest()
     return {"algo": "sha256_grouped_full_content", "root": root,
-            "file_count": len(files), "total_bytes": total_bytes, "groups": groups}
+            "file_count": file_count, "total_bytes": total_bytes, "groups": groups}
 
 
 def _approvals_attestation() -> dict:
@@ -1423,7 +1479,29 @@ def phase_publish(args) -> int:
             logger.error("rebind planning refused: %s", exc)
             j("verify", "refused", reason=f"rebind_plan:{exc}")
             return 2
-        ok, why = _verify_raw_manifest(manifest)
+        # Raw provenance from the ATTESTED staged copy (re-review P0: the fixed-name OUT_DIR
+        # sidecar is mutable and outside any attestation — a regenerated sidecar could make
+        # the published manifest claim raw cut R2 while the staged tree was built from R1).
+        # The copy inside <staged>/metadata/ is covered by the staged content attestation;
+        # it is the source of truth for BOTH the re-verification file list and the root
+        # emitted into provider_build.json. Report + sidecar must agree with it exactly.
+        staged_raw_copy = staged_dir / "metadata" / "raw_input_manifest.json"
+        try:
+            staged_raw = json.loads(staged_raw_copy.read_text(encoding="utf-8"))
+        except (OSError, json.JSONDecodeError) as exc:
+            logger.error("staged raw-input manifest copy missing/unreadable at %s (%s) — the "
+                         "staged build predates the attested-transaction contract; re-run "
+                         "--execute. Refusing.", staged_raw_copy, exc)
+            j("verify", "refused", reason="staged_raw_copy_missing")
+            return 2
+        if (staged_raw.get("root") != rep["raw_input_manifest_root"]
+                or _manifest_root(staged_raw.get("files", [])) != staged_raw.get("root")):
+            logger.error("RAW PROVENANCE MISMATCH — staged copy root %s (self-check %s) != "
+                         "report root %s. Refusing.", staged_raw.get("root"),
+                         _manifest_root(staged_raw.get("files", [])), rep["raw_input_manifest_root"])
+            j("verify", "refused", reason="staged_raw_copy_mismatch")
+            return 2
+        ok, why = _verify_raw_manifest(staged_raw)
         if not ok:
             logger.error("RAW-INPUT MANIFEST MISMATCH (%s) — the raw cut the staged build consumed "
                          "changed since the build. Re-run --execute. Refusing (fail closed).", why)
@@ -1464,196 +1542,298 @@ def phase_publish(args) -> int:
                     live_build, live_policy, manifest["root"], manifest["file_count"],
                     att["root"], att["file_count"], git_head[:12])
 
-        # ── SWAP: the proven primitive; single-rename failures self-roll-back inside it,
-        # leaving the pre-publish state — so a bounded retry vs transient Windows handle
-        # locks (indexer/Defender; the depth9 publish hit exactly this, WinError 5) is
-        # safe. A double failure (live missing) is NEVER retried.
+        # ── SWAP + BIND under DEFERRED SIGINT (re-review P0: a Ctrl-C between two approval
+        # writes previously bypassed the `except Exception` rollback). The swap primitive
+        # self-rolls-back single-rename failures, so a bounded retry vs transient Windows
+        # handle locks is safe; a double failure (live missing) is NEVER retried. From
+        # swap-success onward EVERY operation runs inside ONE protected domain whose
+        # handler catches BaseException — interrupts included — restores the approval
+        # bytes, deletes this transaction's artifacts, strips the post-swap files from the
+        # new tree, rolls the swap back, and VERIFIES every restoration before claiming
+        # exit 4; interrupts re-raise AFTER the verified rollback.
         from data_infra.pit_backend import BuildGateError
         import time as _time
-        swap_exc: Exception | None = None
-        for attempt in range(1, 4):
-            try:
-                builder.publish(calendar_policy_id=rep["new_policy_id"],
-                                raw_input_manifest_root=manifest["root"],
-                                parent_provider_build_id=live_build,
-                                source_git_commit=rep["source_git_commit"])
-                swap_exc = None
-                break
-            except BuildGateError as exc:
-                swap_exc = exc
-                break  # deterministic refusal (cross-volume / missing staged / double failure)
-            except OSError as exc:
-                swap_exc = exc
-                if not os.path.isdir(builder.paths.qlib_dir):
-                    break  # double failure — do NOT retry over a missing live provider
-                logger.warning("swap attempt %d failed (%s) — pre-publish state restored by the "
-                               "primitive; retrying in 5s", attempt, exc)
-                _time.sleep(5)
-        if swap_exc is not None:
-            live_intact = os.path.isdir(builder.paths.qlib_dir)
-            j("swap", "failed", error=str(swap_exc), live_provider_intact=live_intact)
-            if live_intact:
-                logger.error("swap failed after retries and the primitive rolled back — live "
-                             "provider intact: %s", swap_exc)
-                return 2
-            logger.critical("swap DOUBLE failure — live provider MISSING; follow the recovery move "
-                            "in the error: %s", swap_exc)
-            return 5
-
-        # ── BIND: from the successful swap onward, EVERY operation — journal, manifest
-        # verification, rebind writes, state marker, records — runs inside ONE protected
-        # domain (GPT re-review Blocker 1: the first post-swap journal write previously sat
-        # outside it, so a journal failure aborted with the child live + approvals stale).
-        # Any failure restores the approval bytes, deletes this transaction's artifacts,
-        # strips the post-swap files from the new tree, rolls the swap back, and VERIFIES
-        # every restoration before claiming exit 4 (Blocker 2).
+        swap_completed = False
         written: list[Path] = []
         record_md: Path | None = None
         record_written = False
-        state_written = False
-        try:
-            j("swap", "ok", backup=f"{builder.paths.qlib_dir}.bak_{builder.build_id}")
-            okm, why_m = _verify_live_manifest(
-                builder.paths.qlib_dir, build_id=rep["staged_build_id"],
-                policy_id=rep["new_policy_id"], raw_root=manifest["root"], parent_pb=live_build,
-                source_git_commit=rep["source_git_commit"])
-            if not okm:
-                raise PublishTransactionError(f"post-swap live manifest verification failed: {why_m}")
-            for p, nd in rebind_plan:
-                _atomic_write_bytes(p, nd)
-                written.append(p)
-            from data_infra.approval_evidence import evaluate_approval_evidence_bindings
-            drifts = evaluate_approval_evidence_bindings(
-                approvals_dir=APPROVALS_DIR,
-                manifest_path=Path(builder.paths.qlib_dir) / "metadata" / "provider_build.json")
-            still = [d for d in drifts if d.drift]
-            if still:
-                raise PublishTransactionError(
-                    f"{len(still)} approval(s) still drift after the rebind: {still[0].reasons()}")
-            # B6 QA quarantine: the provider is durable but NOT ready — gated reads refuse
-            # until run_daily_qa passes and flips this marker to 'ready'.
-            _write_publish_state(builder.paths.qlib_dir, "pending_qa", rep["staged_build_id"],
-                                 parent_build_id=live_build)
-            state_written = True
-            record = {
-                "published_build_id": rep["staged_build_id"],
-                "calendar_policy_id": rep["new_policy_id"],
-                "parent_build_id": live_build, "parent_policy_id": live_policy,
-                "raw_input_manifest_root": manifest["root"],
-                "raw_input_manifest_file_count": manifest["file_count"],
-                "staged_content_root": att["root"],
-                "staged_content_file_count": att["file_count"],
-                "source_git_commit": rep["source_git_commit"],
-                "approvals_rebound": len(written),
-                "backup_dir": f"{builder.paths.qlib_dir}.bak_{builder.build_id}",
-                "reviewed_dryrun_report": str(DRYRUN_REPORT_PATH),
-                "published_cst": now_cst().isoformat(timespec="seconds"),
-            }
-            _atomic_write_bytes(PUBLISH_RECORD_PATH,
-                                json.dumps(record, ensure_ascii=False, indent=1).encode("utf-8"))
-            record_written = True
-            # the committed governance record is written LAST — nothing may claim a
-            # completed rebind before every durable step above proved out (Blocker 2b).
-            record_md = _write_rebind_record(
-                new_pb=rep["staged_build_id"], new_cp=rep["new_policy_id"], old_pb=live_build,
-                old_cp=live_policy, n_files=len(written), raw_root=manifest["root"],
-                raw_files=manifest["file_count"],
-                backup_dir=f"{builder.paths.qlib_dir}.bak_{builder.build_id}")
-            j("bind", "ok", approvals_rebound=len(written))
-        except Exception as exc:  # noqa: BLE001 — every post-swap failure must roll back
-            logger.error("post-swap step failed (%s) — restoring approvals + artifacts + rolling "
-                         "the swap back.", exc)
-            problems: list[str] = []
-            problems += _restore_approval_files(written, originals)
-            for artifact, present in ((record_md, record_md is not None),
-                                      (PUBLISH_RECORD_PATH, record_written)):
-                if present:
+        with _defer_sigint("swap+bind"):
+            try:
+                swap_exc: Exception | None = None
+                for attempt in range(1, 4):
+                    try:
+                        builder.publish(calendar_policy_id=rep["new_policy_id"],
+                                        raw_input_manifest_root=staged_raw["root"],
+                                        parent_provider_build_id=live_build,
+                                        source_git_commit=rep["source_git_commit"])
+                        swap_exc = None
+                        break
+                    except BuildGateError as exc:
+                        swap_exc = exc
+                        break  # deterministic refusal (cross-volume / missing staged / double failure)
+                    except OSError as exc:
+                        swap_exc = exc
+                        if not os.path.isdir(builder.paths.qlib_dir):
+                            break  # double failure — do NOT retry over a missing live provider
+                        logger.warning("swap attempt %d failed (%s) — pre-publish state restored "
+                                       "by the primitive; retrying in 5s", attempt, exc)
+                        _time.sleep(5)
+                if swap_exc is not None:
+                    live_intact = os.path.isdir(builder.paths.qlib_dir)
+                    j("swap", "failed", error=str(swap_exc), live_provider_intact=live_intact)
+                    if live_intact:
+                        logger.error("swap failed after retries and the primitive rolled back — "
+                                     "live provider intact: %s", swap_exc)
+                        return 2
+                    logger.critical("swap DOUBLE failure — live provider MISSING; follow the "
+                                    "recovery move in the error: %s", swap_exc)
+                    return 5
+                swap_completed = True
+                j("swap", "ok", backup=f"{builder.paths.qlib_dir}.bak_{builder.build_id}")
+                okm, why_m = _verify_live_manifest(
+                    builder.paths.qlib_dir, build_id=rep["staged_build_id"],
+                    policy_id=rep["new_policy_id"], raw_root=staged_raw["root"],
+                    parent_pb=live_build, source_git_commit=rep["source_git_commit"])
+                if not okm:
+                    raise PublishTransactionError(
+                        f"post-swap live manifest verification failed: {why_m}")
+                for p, nd in rebind_plan:
+                    _atomic_write_bytes(p, nd)
+                    written.append(p)
+                from data_infra.approval_evidence import evaluate_approval_evidence_bindings
+                drifts = evaluate_approval_evidence_bindings(
+                    approvals_dir=APPROVALS_DIR,
+                    manifest_path=Path(builder.paths.qlib_dir) / "metadata" / "provider_build.json")
+                still = [d for d in drifts if d.drift]
+                if still:
+                    raise PublishTransactionError(
+                        f"{len(still)} approval(s) still drift after the rebind: {still[0].reasons()}")
+                # B6 QA quarantine: the provider is durable but NOT ready — gated reads
+                # refuse until the READY gate (QA pass + full pin re-verification) flips it.
+                _write_publish_state(builder.paths.qlib_dir, "pending_qa", rep["staged_build_id"],
+                                     parent_build_id=live_build)
+                appr_post = _approvals_attestation()  # post-rebind pin the READY gate re-checks
+                record = {
+                    "published_build_id": rep["staged_build_id"],
+                    "calendar_policy_id": rep["new_policy_id"],
+                    "parent_build_id": live_build, "parent_policy_id": live_policy,
+                    "raw_input_manifest_root": staged_raw["root"],
+                    "raw_input_manifest_file_count": staged_raw.get("file_count"),
+                    "staged_content_root": att["root"],
+                    "staged_content_file_count": att["file_count"],
+                    "approvals_post_rebind_root": appr_post["root"],
+                    "source_git_commit": rep["source_git_commit"],
+                    "approvals_rebound": len(written),
+                    "backup_dir": f"{builder.paths.qlib_dir}.bak_{builder.build_id}",
+                    "reviewed_dryrun_report": str(DRYRUN_REPORT_PATH),
+                    "published_cst": now_cst().isoformat(timespec="seconds"),
+                }
+                _atomic_write_bytes(PUBLISH_RECORD_PATH,
+                                    json.dumps(record, ensure_ascii=False, indent=1).encode("utf-8"))
+                record_written = True
+                # the committed governance record is written LAST — nothing may claim a
+                # completed rebind before every durable step above proved out (Blocker 2b).
+                record_md = _write_rebind_record(
+                    new_pb=rep["staged_build_id"], new_cp=rep["new_policy_id"], old_pb=live_build,
+                    old_cp=live_policy, n_files=len(written), raw_root=staged_raw["root"],
+                    raw_files=staged_raw.get("file_count") or 0,
+                    backup_dir=f"{builder.paths.qlib_dir}.bak_{builder.build_id}")
+                j("bind", "ok", approvals_rebound=len(written))
+            except BaseException as exc:  # noqa: BLE001 — interrupts included (re-review P0)
+                if not swap_completed:
+                    # the primitive self-rolled-back (or the failure landed before any
+                    # rename) — nothing durable mutated by THIS transaction.
+                    j("swap", "aborted_pre_completion", error=repr(exc))
+                    logger.critical("aborted before the swap completed (%r) — the primitive's "
+                                    "self-rollback applies; data/qlib_data is the parent.", exc)
+                    raise
+                logger.error("post-swap step failed (%r) — restoring approvals + artifacts + "
+                             "rolling the swap back.", exc)
+                problems: list[str] = []
+                problems += _restore_approval_files(written, originals)
+                for artifact, present in ((record_md, record_md is not None),
+                                          (PUBLISH_RECORD_PATH, record_written)):
+                    if present:
+                        try:
+                            Path(artifact).unlink(missing_ok=True)
+                        except OSError as uexc:
+                            problems.append(f"could not remove {artifact}: {uexc}")
+                # strip THIS transaction's post-swap files from the new tree so the returned
+                # staged tree matches its content attestation again for a clean retry
+                for name in ("provider_build.json", "publish_state.json"):
+                    fpath = Path(builder.paths.qlib_dir) / "metadata" / name
                     try:
-                        Path(artifact).unlink(missing_ok=True)
+                        fpath.unlink(missing_ok=True)
                     except OSError as uexc:
-                        problems.append(f"could not remove {artifact}: {uexc}")
-            # strip THIS transaction's post-swap files from the new tree so the returned
-            # staged tree matches its content attestation again for a clean retry
-            for name in ("provider_build.json", "publish_state.json"):
-                fpath = Path(builder.paths.qlib_dir) / "metadata" / name
-                try:
-                    fpath.unlink(missing_ok=True)
-                except OSError as uexc:
-                    problems.append(f"could not remove new-tree {name}: {uexc}")
-            ok_rb, rb_msg = _rollback_swap(builder)
-            if ok_rb:
-                try:
-                    rb_build, rb_policy = live_provider_ids()
-                    if (rb_build, rb_policy) != (live_build, live_policy):
-                        problems.append(f"post-rollback live ids ({rb_build}/{rb_policy}) != "
-                                        f"parent ({live_build}/{live_policy})")
-                except Exception as vexc:  # noqa: BLE001
-                    problems.append(f"post-rollback live manifest unreadable: {vexc}")
-            else:
-                problems.append(f"swap rollback failed: {rb_msg}")
-            if not problems:
-                j("bind", "failed_rolled_back", error=str(exc), rollback=rb_msg)
-                logger.error("ROLLED BACK to the parent live provider — VERIFIED (approval bytes "
-                             "re-read identical, parent ids live, artifacts removed): %s. Fix the "
-                             "cause and re-run --publish-approved. Cause: %s", rb_msg, exc)
-                return 4
-            j("bind", "failed_rollback_incomplete", error=str(exc), rollback=rb_msg,
-              problems=problems)
-            logger.critical("ROLLBACK INCOMPLETE — resolve manually per the journal (%s). "
-                            "Problems: %s. Cause: %s", TRANSACTION_JOURNAL_PATH, problems, exc)
-            return 5
+                        problems.append(f"could not remove new-tree {name}: {uexc}")
+                ok_rb, rb_msg = _rollback_swap(builder)
+                if ok_rb:
+                    try:
+                        rb_build, rb_policy = live_provider_ids()
+                        if (rb_build, rb_policy) != (live_build, live_policy):
+                            problems.append(f"post-rollback live ids ({rb_build}/{rb_policy}) != "
+                                            f"parent ({live_build}/{live_policy})")
+                    except Exception as vexc:  # noqa: BLE001
+                        problems.append(f"post-rollback live manifest unreadable: {vexc}")
+                else:
+                    problems.append(f"swap rollback failed: {rb_msg}")
+                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
+                    j("bind", "interrupted_rolled_back" if not problems
+                      else "interrupted_rollback_incomplete", error=repr(exc),
+                      rollback=rb_msg, problems=problems)
+                    logger.critical("INTERRUPTED mid-transaction — rollback %s. Problems: %s",
+                                    "VERIFIED complete" if not problems else "INCOMPLETE",
+                                    problems or "none")
+                    raise
+                if not problems:
+                    j("bind", "failed_rolled_back", error=str(exc), rollback=rb_msg)
+                    logger.error("ROLLED BACK to the parent live provider — VERIFIED (approval "
+                                 "bytes re-read identical, parent ids live, artifacts removed): "
+                                 "%s. Fix the cause and re-run --publish-approved. Cause: %s",
+                                 rb_msg, exc)
+                    return 4
+                j("bind", "failed_rollback_incomplete", error=str(exc), rollback=rb_msg,
+                  problems=problems)
+                logger.critical("ROLLBACK INCOMPLETE — resolve manually per the journal (%s). "
+                                "Problems: %s. Cause: %s", TRANSACTION_JOURNAL_PATH, problems, exc)
+                return 5
     # ── locks released: swap + rebind + metadata are consistent and durable (state=pending_qa).
 
     logger.info("ATOMIC PUBLISH COMPLETE: %s live under %s (parent %s retained as .bak; publish-state "
                 "pending_qa quarantines gated reads). Running post-publish QA ...",
                 rep["staged_build_id"], rep["new_policy_id"], live_build)
-    return _run_and_record_qa(builder.paths.qlib_dir, rep["staged_build_id"], j)
+    return _run_and_record_qa(builder, rep, j)
+
 
+# files the publish itself adds to the live tree AFTER the content attestation — the
+# READY-gate re-verification excludes exactly these (and nothing else).
+_LIVE_PUBLISH_FILES = ("metadata/provider_build.json", "metadata/publish_state.json")
 
-def _run_and_record_qa(qlib_dir, build_id: str, j) -> int:
-    """Run run_daily_qa and flip the publish-state marker accordingly (B6): PASS -> 'ready'
-    (gated reads open), FAIL -> 'qa_failed' (quarantine persists; exit 6). The flip is a
-    manifest-adjacent metadata write — taken under the global publish lock."""
+
+def _run_and_record_qa(builder, rep: dict, j) -> int:
+    """Run run_daily_qa, then hand the READY decision to :func:`_finalize_ready` (PASS) or
+    persist the quarantine (FAIL -> 'qa_failed', exit 6)."""
     from data_infra.tushare_lock import provider_publish_lock
     qa_rc = _run_post_publish_qa()
     if qa_rc != 0:
         with provider_publish_lock():
-            _write_publish_state(qlib_dir, "qa_failed", build_id, qa_returncode=qa_rc)
+            _write_publish_state(builder.paths.qlib_dir, "qa_failed", rep["staged_build_id"],
+                                 qa_returncode=qa_rc)
         j("qa", "failed", returncode=qa_rc)
         logger.critical("PUBLISHED but post-publish QA FAILED (exit %d) — the provider stays live "
                         "but publish-state 'qa_failed' QUARANTINES gated reads until "
                         "--finalize-qa passes. Parent retained as .bak.", qa_rc)
         return 6
-    with provider_publish_lock():
-        _write_publish_state(qlib_dir, "ready", build_id, qa_returncode=0)
-    j("qa", "ok")
-    logger.info("post-publish QA PASS — publish-state 'ready'. Publish record: %s", PUBLISH_RECORD_PATH)
+    j("qa", "passed", returncode=0)
+    return _finalize_ready(builder, rep, j)
+
+
+def _finalize_ready(builder, rep: dict, j) -> int:
+    """The ONLY transition to publish-state 'ready' (re-review P0-3 + P0-4). Under the
+    transaction locks, EVERY pin is re-verified against the LIVE tree: the manifest CAS
+    (build/policy/raw-root/parent/execute-commit), the minted-policy file hash, the
+    post-rebind approvals set (vs the publish record), the in-tree raw manifest
+    self-consistency, and the FULL live content root vs the reviewed staged root
+    (excluding exactly the two files the publish itself adds). QA is a sampling check —
+    THIS is the proof; it closes the hash->swap TOCTOU window: a byte changed at ANY point
+    between the pre-swap attestation and this gate refuses 'ready' (quarantine persists,
+    exit 5)."""
+    from data_infra.tushare_lock import provider_publish_lock, raw_maintenance_lock
+    qlib_dir = Path(builder.paths.qlib_dir)
+    with raw_maintenance_lock(), provider_publish_lock():
+        problems: list[str] = []
+        okm, why_m = _verify_live_manifest(
+            qlib_dir, build_id=rep["staged_build_id"], policy_id=rep["new_policy_id"],
+            raw_root=rep["raw_input_manifest_root"], parent_pb=rep["parent_build_id"],
+            source_git_commit=rep["source_git_commit"])
+        if not okm:
+            problems.append(f"live manifest CAS failed: {why_m}")
+        policy_file = POLICY_DIR / f"{rep['new_policy_id']}.yaml"
+        if not policy_file.is_file() or _sha256_file(policy_file) != rep["new_policy_sha256"]:
+            problems.append("minted policy file hash drifted since the reviewed report")
+        try:
+            record = json.loads(PUBLISH_RECORD_PATH.read_text(encoding="utf-8"))
+        except (OSError, json.JSONDecodeError) as exc:
+            record = {}
+            problems.append(f"publish record unreadable: {exc}")
+        if record.get("published_build_id") != rep["staged_build_id"]:
+            problems.append("publish record does not describe this build")
+        appr = _approvals_attestation()
+        if appr["bound_count"] < 1 or appr["root"] != record.get("approvals_post_rebind_root"):
+            problems.append("approvals governance set drifted since the rebind")
+        try:
+            live_raw = json.loads((qlib_dir / "metadata" / "raw_input_manifest.json")
+                                  .read_text(encoding="utf-8"))
+            if live_raw.get("root") != rep["raw_input_manifest_root"]:
+                problems.append("in-tree raw manifest root != the reviewed raw root")
+        except (OSError, json.JSONDecodeError) as exc:
+            problems.append(f"in-tree raw manifest unreadable: {exc}")
+        if not problems:
+            logger.info("READY gate: FULL live-content re-verification (%s files) ...",
+                        rep.get("staged_content_file_count"))
+            att = _staged_content_attestation(
+                qlib_dir, exclude=_LIVE_PUBLISH_FILES,
+                build_manifest_path=Path(builder.paths.build_root) / "manifest.json")
+            if att["root"] != rep["staged_content_root"]:
+                problems.append(
+                    f"LIVE content root {att['root']} != reviewed {rep['staged_content_root']} — "
+                    "the published bytes changed since the audited build")
+        if problems:
+            j("ready", "refused", problems=problems)
+            logger.critical("READY REFUSED — the provider STAYS QUARANTINED. Problems: %s. "
+                            "Investigate; if the published bytes are compromised, restore the "
+                            "parent from the .bak per the journal (%s).",
+                            problems, TRANSACTION_JOURNAL_PATH)
+            return 5
+        _write_publish_state(qlib_dir, "ready", rep["staged_build_id"], qa_returncode=0)
+    j("ready", "ok")
+    logger.info("publish-state 'ready' — QA passed AND every pin re-verified against the live "
+                "tree. Publish record: %s", PUBLISH_RECORD_PATH)
     return 0
 
 
 def phase_finalize_qa(args) -> int:
-    """Re-run the post-publish QA leg for a provider stuck in 'pending_qa'/'qa_failed'
-    (crash between swap and QA, or a QA failure now resolved). Refuses when the live build
-    is not the reviewed report's staged build (the quarantine belongs to THIS publish)."""
+    """Re-run the QA + READY-gate leg for a provider stuck in 'pending_qa'/'qa_failed'
+    (crash between swap and QA, or a QA failure now resolved). CAS-verifies the live
+    manifest against the reviewed report BEFORE running QA, and the full READY gate
+    (:func:`_finalize_ready` — content root included) decides afterwards; a provider whose
+    bytes changed since the review can NEVER be marked ready by this path."""
     if not DRYRUN_REPORT_PATH.exists():
         logger.error("no dry-run report at %s — nothing to finalize.", DRYRUN_REPORT_PATH)
         return 2
     rep = json.loads(DRYRUN_REPORT_PATH.read_text(encoding="utf-8"))
-    live_build, _ = live_provider_ids()
-    if live_build != rep.get("staged_build_id"):
-        logger.error("live build %s is not the report's staged build %s — --finalize-qa only "
-                     "finishes the publish this report describes. Refusing.",
-                     live_build, rep.get("staged_build_id"))
+    required = ("staged_build_id", "new_policy_id", "raw_input_manifest_root",
+                "parent_build_id", "source_git_commit", "new_policy_sha256",
+                "staged_content_root")
+    missing = [k for k in required if not rep.get(k)]
+    if missing:
+        logger.error("dry-run report lacks %s — cannot finalize. Refusing.", missing)
         return 2
     builder = _make_publish_builder(rep["staged_build_id"])
-    state_file = Path(builder.paths.qlib_dir) / "metadata" / "publish_state.json"
-    try:
-        state = json.loads(state_file.read_text(encoding="utf-8")).get("state")
-    except (OSError, json.JSONDecodeError):
-        state = None
-    if state not in ("pending_qa", "qa_failed"):
-        logger.error("publish-state is %r — --finalize-qa only applies to pending_qa/qa_failed.", state)
-        return 2
+    from data_infra.tushare_lock import provider_publish_lock, raw_maintenance_lock
+    with raw_maintenance_lock(), provider_publish_lock():
+        live_build, _ = live_provider_ids()
+        if live_build != rep["staged_build_id"]:
+            logger.error("live build %s is not the report's staged build %s — --finalize-qa only "
+                         "finishes the publish this report describes. Refusing.",
+                         live_build, rep["staged_build_id"])
+            return 2
+        state_file = Path(builder.paths.qlib_dir) / "metadata" / "publish_state.json"
+        try:
+            state = json.loads(state_file.read_text(encoding="utf-8")).get("state")
+        except (OSError, json.JSONDecodeError):
+            state = None
+        if state not in ("pending_qa", "qa_failed"):
+            logger.error("publish-state is %r — --finalize-qa only applies to pending_qa/qa_failed.",
+                         state)
+            return 2
+        okm, why_m = _verify_live_manifest(
+            builder.paths.qlib_dir, build_id=rep["staged_build_id"],
+            policy_id=rep["new_policy_id"], raw_root=rep["raw_input_manifest_root"],
+            parent_pb=rep["parent_build_id"], source_git_commit=rep["source_git_commit"])
+        if not okm:
+            logger.error("live manifest CAS failed before QA (%s) — refusing to finalize.", why_m)
+            return 2
 
     journal: dict = {"transaction": "finalize_qa", "staged_build_id": rep["staged_build_id"],
                      "steps": []}
@@ -1663,7 +1843,7 @@ def phase_finalize_qa(args) -> int:
                                  "ts_cst": now_cst().isoformat(timespec="seconds"), **info})
         _write_journal(journal)
 
-    return _run_and_record_qa(builder.paths.qlib_dir, rep["staged_build_id"], j)
+    return _run_and_record_qa(builder, rep, j)
 
 
 def main() -> int:
diff --git a/src/data_infra/tushare_lock.py b/src/data_infra/tushare_lock.py
index 78b6ea7..0d0daa2 100644
--- a/src/data_infra/tushare_lock.py
+++ b/src/data_infra/tushare_lock.py
@@ -30,14 +30,44 @@ from pathlib import Path
 
 from filelock import FileLock, Timeout  # noqa: F401 — Timeout re-exported for callers' soft-skip
 
-# ONE immutable lock identity for this workspace — a fixed absolute path under the project root, NOT
-# overridable by an ambient environment variable. A per-process `QUANT_LOCK_DIR` override previously
-# let a second process select a DIFFERENT namespace and acquire immediately while a real holder was
-# live (two raw writers / two parallel Tushare callers — GPT REWORK-5 Blocker 1). Tests INJECT
-# isolation by monkeypatching this module attribute in-process (or reassigning it inside a spawned
-# holder's own code), never via a production-readable env var. A shared-volume deploy that needs a
-# different directory must resolve it centrally (config), not from ambient per-process state.
-_LOCK_DIR = Path(__file__).resolve().parents[2] / "logs" / "locks"
+# ONE immutable lock identity for this REPOSITORY (all worktrees), NOT overridable by an ambient
+# environment variable. A per-process `QUANT_LOCK_DIR` override previously let a second process
+# select a DIFFERENT namespace and acquire immediately while a real holder was live (GPT REWORK-5
+# Blocker 1). Phase 5-B re-review P0: deriving the path from THIS source file's checkout is ALSO a
+# forgeable-by-accident namespace — two git WORKTREES of the same repo resolved different lock dirs
+# and could publish/fetch concurrently against the same shared store. The identity is therefore
+# anchored to the GIT COMMON DIRECTORY's parent (identical for every worktree of a repo; equal to
+# the checkout root for a plain clone, so the production daily job's lock path is unchanged).
+# Degraded fallback (git unavailable): the source checkout root, with a loud warning — never env.
+# Tests INJECT isolation by monkeypatching the module attribute in-process, never via env.
+_SOURCE_ROOT = Path(__file__).resolve().parents[2]
+
+
+def _resolve_lock_root(source_root: Path) -> Path:
+    import logging
+    import subprocess
+    try:
+        # git emits UTF-8 bytes; text=True would decode with the locale codepage (cp936 on
+        # this host) and MANGLE non-ASCII path components (the real repo root contains
+        # Chinese characters) — decode explicitly.
+        out = subprocess.check_output(
+            ["git", "rev-parse", "--git-common-dir"],
+            cwd=str(source_root), stderr=subprocess.DEVNULL,
+        ).decode("utf-8").strip()
+        common = Path(out)
+        if not common.is_absolute():
+            common = (source_root / common).resolve()
+        return common.parent
+    except Exception:  # noqa: BLE001 — degraded per-checkout namespace, loudly
+        logging.getLogger(__name__).warning(
+            "git common-dir resolution failed under %s — lock namespace degrades to this "
+            "checkout only (cross-worktree publishers would NOT exclude each other).",
+            source_root,
+        )
+        return source_root
+
+
+_LOCK_DIR = _resolve_lock_root(_SOURCE_ROOT) / "logs" / "locks"
 
 
 def _lock_dir() -> Path:
diff --git a/src/research_orchestrator/release_gate.py b/src/research_orchestrator/release_gate.py
index 9a63f29..8c56097 100644
--- a/src/research_orchestrator/release_gate.py
+++ b/src/research_orchestrator/release_gate.py
@@ -606,8 +606,18 @@ def evaluate_provider_publish_state(
                 "post-publish QA has not passed; the provider is quarantined for gated "
                 "reads. Run scripts/monthly_calendar_bump.py --finalize-qa after resolving."
             )
+        # Phase 5-B re-review P0: a marker MUST name the build it certifies — a bare
+        # {"state": "ready"} previously passed because the comparison was conditional on
+        # the field being present, severing the "this QA verdict belongs to THIS build"
+        # binding. Blank/missing marker build id fails closed; when the caller supplies
+        # the manifest, exact equality is mandatory.
         marker_build = state_payload.get("provider_build_id")
-        if build_id is not None and marker_build is not None and str(marker_build) != str(build_id):
+        if not isinstance(marker_build, str) or not marker_build.strip():
+            reasons.append(
+                f"publish-state marker carries no provider_build_id ({marker_build!r}) — an "
+                "unbound certification cannot clear any build; refusing."
+            )
+        elif build_id is not None and str(marker_build) != str(build_id):
             reasons.append(
                 f"publish-state marker names build {marker_build!r} but the live manifest is "
                 f"{build_id!r} — stale/foreign marker; refusing."
diff --git a/tests/data_infra/test_monthly_calendar_bump.py b/tests/data_infra/test_monthly_calendar_bump.py
index 5f15089..124f3b5 100644
--- a/tests/data_infra/test_monthly_calendar_bump.py
+++ b/tests/data_infra/test_monthly_calendar_bump.py
@@ -587,12 +587,16 @@ def _publish_env(tmp_path, monkeypatch, *, qa_rc: int = 0):
         "approval_id: x\nbinding_exempt: true\nbinding_exempt_reason: admin-only record\n",
         encoding="utf-8")
 
-    # raw cut + full-readset manifest sidecar over it
+    # raw cut + full-readset manifest sidecar over it + the ATTESTED staged copy (the
+    # publish-time source of truth for raw provenance, re-review P0)
     raw = data / "reference" / "trade_cal.parquet"
     raw.parent.mkdir(parents=True)
     raw.write_bytes(b"CAL0")
     manifest = mcb._full_raw_manifest(data)
     (out / "raw_input_manifest.json").write_text(_json.dumps(manifest), encoding="utf-8")
+    (staged / "metadata").mkdir()
+    (staged / "metadata" / "raw_input_manifest.json").write_text(
+        _json.dumps(manifest), encoding="utf-8")
 
     # audit artifacts + the full transaction attestation set, pinned into the dry-run report
     fp = out / "frozen_prefix_audit.json"
@@ -947,6 +951,134 @@ def test_publish_refuses_policy_file_drift(tmp_path, monkeypatch):
     _assert_untouched(env)
 
 
+# ── GPT re-review #2 probes (interrupt / TOCTOU / provenance / lock identity) ─
+def test_publish_interrupt_mid_rebind_rolls_back_then_reraises(tmp_path, monkeypatch):
+    # P0 probe: a KeyboardInterrupt between two approval writes previously bypassed the
+    # `except Exception` rollback — half-rebound approvals + child live + no marker. The
+    # protected domain now catches BaseException, performs the VERIFIED rollback, and
+    # re-raises the interrupt afterwards.
+    env = _publish_env(tmp_path, monkeypatch)
+    seen: list[Path] = []
+
+    def interrupt_on_second_approval(path, _data):
+        if path.parent == env.root / "approvals" and path.suffix == ".yaml":
+            seen.append(path)
+            if len(seen) == 2:
+                raise KeyboardInterrupt("probe: Ctrl-C between approval writes")
+        return False
+
+    real = mcb._atomic_write_bytes
+
+    def fake(path, data):
+        interrupt_on_second_approval(Path(path), data)
+        real(path, data)
+
+    monkeypatch.setattr(mcb, "_atomic_write_bytes", fake)
+    with pytest.raises(KeyboardInterrupt):
+        mcb.phase_publish(_PubArgs())
+    assert (env.qlib / "LIVE_MARKER.txt").exists(), "parent must be restored before re-raising"
+    assert mcb.live_provider_ids() == (env.parent_pb, env.parent_cp)
+    assert env.a1.read_bytes() == env.a1_bytes and env.a2.read_bytes() == env.a2_bytes
+    assert (env.staged / "STAGED_MARKER.txt").exists()
+    assert not list((env.root / "approvals").glob("*_rebind_to_*.md"))
+    steps = _json.loads((env.out / "publish_transaction_journal.json").read_text(encoding="utf-8"))["steps"]
+    assert any(s["status"] == "interrupted_rolled_back" for s in steps)
+
+
+def test_publish_systemexit_mid_rebind_rolls_back(tmp_path, monkeypatch):
+    env = _publish_env(tmp_path, monkeypatch)
+
+    def fault(path, _data):
+        if path.name == "a2.yaml":
+            raise SystemExit(3)
+        return False
+
+    real = mcb._atomic_write_bytes
+
+    def fake(path, data):
+        fault(Path(path), data)
+        real(path, data)
+
+    monkeypatch.setattr(mcb, "_atomic_write_bytes", fake)
+    with pytest.raises(SystemExit):
+        mcb.phase_publish(_PubArgs())
+    assert (env.qlib / "LIVE_MARKER.txt").exists()
+    assert env.a1.read_bytes() == env.a1_bytes and env.a2.read_bytes() == env.a2_bytes
+
+
+def test_ready_gate_refuses_bytes_changed_after_swap(tmp_path, monkeypatch):
+    # P0 probe (hash->swap TOCTOU): bytes changed AFTER the pre-swap attestation — here
+    # while QA runs — must NOT reach 'ready'. The READY gate re-hashes the FULL live tree
+    # and refuses; the provider stays quarantined.
+    env = _publish_env(tmp_path, monkeypatch)
+
+    def tampering_qa():
+        (env.qlib / "features" / "000001_sz" / "close.day.bin").write_bytes(b"\x0a\x0a\x0a\x0a")
+        return 0  # QA "passes" — sampling checks cannot see the tamper
+
+    monkeypatch.setattr(mcb, "_run_post_publish_qa", tampering_qa)
+    assert mcb.phase_publish(_PubArgs()) == 5
+    assert _publish_state_of(env.qlib) == "pending_qa", "quarantine must persist"
+    steps = _json.loads((env.out / "publish_transaction_journal.json").read_text(encoding="utf-8"))["steps"]
+    ready = [s for s in steps if s["step"] == "ready" and s["status"] == "refused"]
+    assert ready and any("content root" in p for p in ready[0]["problems"])
+
+
+def test_finalize_qa_cannot_green_changed_bytes(tmp_path, monkeypatch):
+    # P0 probe: QA fails first (qa_failed), the live bin is then rewritten, QA is made to
+    # pass — finalize must still REFUSE ready (full pin re-verification), and succeed only
+    # once the original bytes are restored.
+    env = _publish_env(tmp_path, monkeypatch, qa_rc=1)
+    assert mcb.phase_publish(_PubArgs()) == 6
+    live_bin = env.qlib / "features" / "000001_sz" / "close.day.bin"
+    original = live_bin.read_bytes()
+    live_bin.write_bytes(b"\x0b\x0b\x0b\x0b")
+    monkeypatch.setattr(mcb, "_run_post_publish_qa", lambda: 0)
+    assert mcb.phase_finalize_qa(_PubArgs()) == 5
+    assert _publish_state_of(env.qlib) == "qa_failed", "tampered bytes must stay quarantined"
+    live_bin.write_bytes(original)
+    assert mcb.phase_finalize_qa(_PubArgs()) == 0
+    assert _publish_state_of(env.qlib) == "ready"
+
+
+def test_publish_refuses_raw_provenance_mismatch(tmp_path, monkeypatch):
+    # P0 probe: report + OUT_DIR sidecar rewritten to claim raw cut R2 while the staged
+    # provider's ATTESTED in-tree copy says R1 — publish derives provenance from the
+    # staged copy and refuses the mismatch.
+    env = _publish_env(tmp_path, monkeypatch)
+    fake_root = "ab" * 32
+    rep = _json.loads((env.out / "monthly_bump_dryrun_report.json").read_text(encoding="utf-8"))
+    rep["raw_input_manifest_root"] = fake_root
+    (env.out / "monthly_bump_dryrun_report.json").write_text(_json.dumps(rep), encoding="utf-8")
+    sidecar = _json.loads((env.out / "raw_input_manifest.json").read_text(encoding="utf-8"))
+    sidecar["root"] = fake_root
+    (env.out / "raw_input_manifest.json").write_text(_json.dumps(sidecar), encoding="utf-8")
+    assert mcb.phase_publish(_PubArgs()) == 2
+    _assert_untouched(env)
+
+
+def test_lock_root_is_shared_across_worktrees(tmp_path):
+    # P0 probe: two worktrees of the same repo previously resolved DIFFERENT lock dirs and
+    # could publish concurrently. The lock root is anchored to the git COMMON dir's parent
+    # — identical from the main checkout and from any linked worktree.
+    import subprocess
+
+    import data_infra.tushare_lock as tl
+
+    main = tmp_path / "mainrepo"
+    main.mkdir()
+    subprocess.run(["git", "init", "-q", str(main)], check=True)
+    (main / "x.txt").write_text("x", encoding="utf-8")
+    subprocess.run(["git", "-C", str(main), "add", "."], check=True)
+    subprocess.run(["git", "-C", str(main), "-c", "user.email=t@t", "-c", "user.name=t",
+                    "commit", "-qm", "init"], check=True)
+    wt = tmp_path / "wt1"
+    subprocess.run(["git", "-C", str(main), "worktree", "add", "-q", str(wt)], check=True)
+    root_main = tl._resolve_lock_root(main)
+    root_wt = tl._resolve_lock_root(wt)
+    assert root_main.resolve() == root_wt.resolve() == main.resolve()
+
+
 def test_builder_publish_acquires_global_lock(tmp_path, monkeypatch):
     # GPT Blocker 7: the publish LOCK lives at the common chokepoint — a bare
     # StagedQlibBackendBuilder.publish() (any entrypoint) acquires it, and the singleton
diff --git a/tests/research_orchestrator/test_provider_raw_attestation_gate.py b/tests/research_orchestrator/test_provider_raw_attestation_gate.py
index 82a0641..293e8ba 100644
--- a/tests/research_orchestrator/test_provider_raw_attestation_gate.py
+++ b/tests/research_orchestrator/test_provider_raw_attestation_gate.py
@@ -180,6 +180,13 @@ def test_publish_state_gate_quarantines_until_ready(tmp_path):
     # a marker naming a DIFFERENT build is stale/foreign -> refuse
     _write_state(tmp_path, "ready", build_id="someone_else")
     assert not evaluate_provider_publish_state(qlib_dir=tmp_path, policy=flagged, manifest=m).eligible
+    # GPT re-review #2 P0: a bare {"state": "ready"} with NO provider_build_id must refuse
+    # — an unbound certification cannot clear any build (even with no manifest supplied).
+    import json as _j
+    (tmp_path / "metadata" / "publish_state.json").write_text(
+        _j.dumps({"state": "ready"}), encoding="utf-8")
+    unbound = evaluate_provider_publish_state(qlib_dir=tmp_path, policy=legacy, manifest=None)
+    assert not unbound.eligible and any("provider_build_id" in r for r in unbound.reasons)
 
 
 def test_formal_runtime_validation_refuses_quarantined_provider(tmp_path, monkeypatch):
```

RE-REVIEW QUESTIONS
1. Re-run your six P0 probes + the P1 memory analysis against the new code: per-probe pass/fail table.
2. The READY-gate design: is "pending_qa/qa_failed until _finalize_ready re-proves every pin" a sound TOCTOU boundary, or is there a residual window (e.g., between the READY-gate content hash completing and the marker write, both inside the same lock scope)? Is refusing with exit 5 while KEEPING the tampered provider live-but-quarantined the right posture, or must the gate auto-restore the .bak parent?
3. The SIGINT deferral spans swap+bind only (verify remains interruptible; QA + READY gate are interruptible with pending_qa persisting for --finalize-qa). Right spans? Any BaseException path that still escapes (e.g., inside _rollback_swap itself)?
4. The git-common-dir lock identity: correct anchor? Consider submodules, bare repos, a copied (non-git) deployment, and two SEPARATE clones (not worktrees) pointing at the same data root — the last still gets two namespaces; is that acceptable residual risk given worktrees were the demonstrated deployment pattern, or must the lock bind to the shared data root from config?
5. The staged in-tree raw manifest as provenance source of truth: any circularity or hole left (it is written by the same execute that computes the content root)?
6. Remaining limits: L2 (trusted-operator report tampering) unchanged; first real 241GB run still pending and separately §13-gated. Name the exact preflight sequence you require for that first run (e.g., a small --touched-symbols staged build through the FULL transaction first, a rollback drill, a --finalize-qa drill).
7. Anything in the docs (CLAUDE 3.4 hardening paragraph) that misstates the implemented behavior?

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending line quoted and an exact suggested replacement.
- Explicit per-probe pass/fail table for your re-review #2 probes.
- Final line: SHIP / REVISE / REWORK, plus the single most important residual risk.
```
