# GPT 5.5 Pro re-review #2 — Phase 5-B atomic publish: REWORK findings closed

> Send verbatim to GPT 5.5 Pro. Branch pushed; pinned HEAD: `708a218` (REWORK code+tests =
> `e4ceeea`, docs = `708a218`; your reviewed baseline was `0525cc1`).

```text
ROLE
You are the same senior reviewer who issued the REWORK on this change (7 Blockers + 3 Majors, all reproduced by your fault-injection probes). Re-review the fixes adversarially: re-run the SAME probes mentally (or actually) against the new code, and hunt for NEW holes the fixes may have opened. Do not rubber-stamp.

REPO (public — fetch any file to verify against the live code)
https://github.com/henrydan111/quant-system   (branch: calendar-unfreeze-phase5b-atomic-publish)
Raw file form: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/<path>

KEY FILES (all updated this round)
- Driver (transaction + attestations + --finalize-qa): https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/scripts/monthly_calendar_bump.py
- Locks (singleton global publish lock): https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/src/data_infra/tushare_lock.py
- Swap primitive + lock chokepoint + git-commit binding: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/src/data_infra/pit_backend.py
- Manifest emitters (locked writes): https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/src/data_infra/provider_manifest.py
- Shared read chokepoint (gates wired, state-aware cache key): https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/src/data_infra/provider_context.py
- Gates (attestation + NEW publish-state quarantine): https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/src/research_orchestrator/release_gate.py
- Policy loader (strict-bool refuses): https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/src/research_orchestrator/calendar_policy.py
- Event-driven runtime validation (both gates): https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/src/backtest_engine/event_driven/__init__.py
- Tests (your probes as regressions): https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/tests/data_infra/test_monthly_calendar_bump.py
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/tests/research_orchestrator/test_provider_raw_attestation_gate.py
- Self-review round 2 (fix log incl. two self-caught issues): https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/workspace/research/calendar_unfreeze/PHASE5B_ATOMIC_PUBLISH_SELF_REVIEW.md
- Updated invariants + runbook: CLAUDE.md 3.4 / AGENTS.md 2a / workspace/research/calendar_unfreeze/UNFREEZE_PLAN.md (Phase 3.4 / 4.1 / 5.2)

FINDING-BY-FINDING DISPOSITION (verify each against the diff below)
B1 (journal outside rollback domain) -> _write_journal is a NON-RAISING breadcrumb (internal try/except -> logger.error), AND everything from swap-success onward — j("swap","ok"), live-manifest verification, rebind writes, pending_qa marker, publish record, rebind md — sits inside ONE try whose handler restores/rolls back. Probe-replica: test_publish_survives_journal_write_failure_after_swap (journal path pointed at a DIRECTORY so every write fails; transaction completes exit 0, consistent).
B2 (exit-4 can lie) -> rebind is planned PRE-SWAP by _plan_rebind (PURE; zero writes; originals returned to the caller before anything is written — a planning refusal is now a pre-swap exit 2). The handler: _restore_approval_files re-reads each restored file and returns a failure list; the publish record + rebind md (now written LAST) are deleted; the post-swap files (provider_build.json, publish_state.json) are stripped from the returned tree so its content re-attestation passes on retry; _rollback_swap runs; live_provider_ids() is re-checked == parent. exit 4 ONLY when the problems list is empty; otherwise exit 5 and the journal step carries the problems verbatim. Probe-replicas: test_publish_rolls_back_when_rebind_write_fails_midway, test_publish_reports_5_when_restore_also_fails (a1 rebound then its RESTORE faulted -> exit 5, journal names a1.yaml), test_publish_rolls_back_when_record_write_fails (no false 'completed rebind' md survives).
B3 (approvals CAS fail-open on deletion) -> execute pins _approvals_attestation (sorted *.yaml names + per-file sha256 + bound count); publish requires exact root equality AND bound_count >= 1, plus the existing per-value CAS. Probe-replicas: test_publish_refuses_deleted_approvals (single delete AND delete-all), test_publish_refuses_added_approval.
B4 / L1 rejected -> _staged_content_attestation: EVERY file in the staged tree (feature bins included) + the build manifest.json is sha256-hashed (ThreadPool; deterministic grouped digests per features/<code>; root over the sorted group map; per-build sidecar persisted). Execute pins the root; publish re-hashes the FULL tree under the locks immediately before the swap. Probe-replica: test_publish_refuses_feature_bin_mutation (same-size byte mutation refused). Disclosed cost: one full tree read per side, monthly.
B5 (formal Qlib read door uncovered) -> both gates wired in provider_context._resolve — the shared resolution of BOTH sanctioned doors (pit_research_loader sandbox + qlib_windowed_features formal). The publish_state.json content digest is folded into the rotation-safe cache key, so a --finalize-qa flip re-keys and re-runs the gates (no stale cached verdict). Note: this gates the SANDBOX door too (stricter than you demanded) — deliberate, disclosed. Tests: test_provider_context_enforces_attestation_and_state, ..._legacy_policy_still_resolves.
B6 / L4 conditionally rejected -> mechanical quarantine: the transaction writes metadata/publish_state.json = pending_qa INSIDE the protected domain; QA PASS flips it to ready (under the publish lock), failure writes qa_failed + exit 6. release_gate.assert_provider_publish_state enforces at BOTH chokepoints; semantics: required(policy flag) + absent -> refuse; a PRESENT non-ready marker refuses even under legacy policies; a marker naming a different build refuses. New --finalize-qa mode resumes the QA leg (refuses unless live build == the report's staged build and state is pending_qa/qa_failed). Tests: test_publish_qa_failure_returns_6_and_quarantines, test_publish_state_gate_quarantines_until_ready, test_formal_runtime_validation_refuses_quarantined_provider.
B7 (lock not global) -> provider_publish_lock moved to the COMMON chokepoints: StagedQlibBackendBuilder.publish() and both provider_build.json emitters acquire it themselves. Mechanism: per-path SINGLETON FileLock (is_singleton=True, verified on filelock 3.25.2: same instance, counted acquire) -> the transaction's nested acquisition is reentrant, a second process blocks; sibling-RELATIVE imports make the dual src./plain module namespaces share one lock instance. Probe-replica: test_builder_publish_acquires_global_lock; the happy path exercises the real nesting.
M1 (strict-bool fail-open) -> a non-bool require_raw_input_attestation now raises CalendarPolicyError at load (probe: "true"/1/"yes" all refuse); the minted policy FILE sha256 is pinned in the report and re-verified at publish (test_publish_refuses_policy_file_drift).
M2 (provenance not bound to the real build) -> _git_state() (HEAD + dirty digest over git status --porcelain) captured at EXECUTE into the report; publish REQUIRES equality (drift = exit 2) and passes the execute-time commit into publish() -> the emitted manifest carries it (verified post-swap). The raw manifest now persists three ways: fixed name, per-build-id sidecar, and INSIDE the staged provider's metadata/ (written before the content attestation, so it ships covered by the attestation and survives with the published/.bak tree).
M3 / L5 rejected -> UNFREEZE_PLAN Phase 3.4, 4.1 and 5.2 rewritten: struck the manual _depth9_safe_publish/_rebind steps, described the atomic transaction + quarantine, cross-referenced the CLAUDE 3.4 invariant.

VERIFICATION (this round)
Focused battery 156 green (incl. the 16 probe-replica tests above). Combined four suites: 1064 green / 16 skipped; the 39 failures are the IDENTICAL 8 environment-dependent files as the baseline you already inspected (missing live data in this worktree clone; each cross-checked green on the main tree with full data; the 2 test_pre_open_isolation failures pre-date this work and are being fixed in a separate session). provider_context/pr8 consumer files re-run in isolation: 81 green. No live-provider touch this session.

WHAT CHANGED (authoritative — the full REWORK diff, commit e4ceeea; docs commit 708a218 not embedded):

```diff
diff --git a/scripts/monthly_calendar_bump.py b/scripts/monthly_calendar_bump.py
index 13d7bb1..e0a6340 100644
--- a/scripts/monthly_calendar_bump.py
+++ b/scripts/monthly_calendar_bump.py
@@ -424,34 +424,96 @@ def _atomic_write_bytes(path: Path, data: bytes) -> None:
             os.remove(tmp)
 
 
-def _staged_attestation(staged_provider) -> dict:
-    """Cheap tamper-evidence over the staged provider's IDENTITY-bearing small files:
-    calendars/day.txt + every instruments/*.txt (full content SHA-256) + the build
-    manifest.json at <build_root>/manifest.json + the features top-level dir count.
-    Recomputed at publish and compared to the execute-time root, so a staged tree whose
-    calendar/universe/build-record moved between the audited build and the swap refuses.
-    DELIBERATE LIMIT (disclosed): the 241GB features/*.bin content is attested by the
-    execute-time frozen-prefix + fresh-window audits, not re-hashed here — a full
-    content re-hash at publish would take longer than the build itself."""
+def _staged_content_attestation(staged_provider, *, workers: int = 8) -> dict:
+    """FULL-CONTENT attestation over the ENTIRE staged provider tree (GPT re-review
+    Blocker 4: the published feature bytes themselves must be proven, not just identity
+    files — a build-id path is a naming convention, not an immutability control).
+
+    Every file under the staged provider (features/*.bin included) AND the build
+    manifest.json at <build_root>/manifest.json is content-hashed (sha256, thread-pooled —
+    23M small files are open-latency-bound, not bandwidth-bound). Files are grouped by
+    top-level entry (each features/<code>/ dir collapses to one group digest over its
+    sorted "relpath:size:sha256" lines) so a publish-time mismatch localizes without a
+    multi-GB sidecar; the root is the sha256 over the sorted group map. Recomputed at
+    publish IMMEDIATELY before the swap and compared to the execute-time root — any byte
+    that changed since the audited build refuses the publish. Cost: one full read of the
+    staged tree per side (disclosed; a monthly operation after a multi-hour build)."""
+    import hashlib
+    from concurrent.futures import ThreadPoolExecutor
+
     prov = Path(staged_provider)
-    comp: dict = {}
-    cal = prov / "calendars" / "day.txt"
-    comp["calendars/day.txt"] = _sha256_file(cal) if cal.is_file() else "MISSING"
-    inst = prov / "instruments"
-    if inst.is_dir():
-        for p in sorted(inst.glob("*.txt")):
-            comp[f"instruments/{p.name}"] = _sha256_file(p)
-    else:
-        comp["instruments"] = "MISSING"
-    build_manifest = prov.parent / "manifest.json"
-    comp["build_manifest.json"] = _sha256_file(build_manifest) if build_manifest.is_file() else "MISSING"
-    feats = prov / "features"
-    comp["features_top_level_dir_count"] = (
-        sum(1 for p in feats.iterdir() if p.is_dir()) if feats.is_dir() else 0
+    if not prov.is_dir():
+        return {"algo": "sha256_grouped_full_content", "root": "MISSING_STAGED_DIR",
+                "file_count": 0, "total_bytes": 0, "groups": {}}
+
+    def _group_of(rel: str) -> str:
+        parts = rel.split("/")
+        if len(parts) >= 3 and parts[0] == "features":
+            return f"features/{parts[1]}"
+        return parts[0] if len(parts) > 1 else f"<top>/{parts[0]}"
+
+    files = sorted(
+        (str(p.relative_to(prov)).replace("\\", "/"), p)
+        for p in prov.rglob("*") if p.is_file()
     )
+    build_manifest = prov.parent / "manifest.json"
+    if build_manifest.is_file():
+        files.append(("<build_root>/manifest.json", build_manifest))
+
+    total_bytes = 0
+    lines_by_group: dict[str, list[str]] = {}
+    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
+        digests = list(pool.map(lambda item: _sha256_file(item[1]), files))
+    for (rel, p), digest in zip(files, digests):
+        size = p.stat().st_size
+        total_bytes += size
+        lines_by_group.setdefault(_group_of(rel), []).append(f"{rel}:{size}:{digest}")
+
+    groups = {
+        g: hashlib.sha256("\n".join(sorted(lines)).encode("utf-8")).hexdigest()
+        for g, lines in lines_by_group.items()
+    }
+    root = hashlib.sha256(
+        "\n".join(f"{g}:{h}" for g, h in sorted(groups.items())).encode("utf-8")
+    ).hexdigest()
+    return {"algo": "sha256_grouped_full_content", "root": root,
+            "file_count": len(files), "total_bytes": total_bytes, "groups": groups}
+
+
+def _approvals_attestation() -> dict:
+    """Pin the approvals GOVERNANCE SET: sorted *.yaml filenames, per-file sha256, bound
+    count. The publish transaction requires EXACT equality with the execute-time pin AND a
+    non-empty bound set — closing the fail-open where deleting (or adding) approval YAMLs
+    between execute and publish still published with `approvals_rebound: 0` (GPT re-review
+    Blocker 3: the loader returns [] for a missing/emptied directory)."""
+    import hashlib
+    files = {p.name: _sha256_file(p) for p in sorted(APPROVALS_DIR.glob("*.yaml"))} \
+        if APPROVALS_DIR.is_dir() else {}
+    from data_infra.approval_evidence import ApprovalEvidenceConfigError, load_approval_bindings
+    try:
+        bound = len(load_approval_bindings(APPROVALS_DIR))
+    except ApprovalEvidenceConfigError:
+        bound = -1  # malformed governance dir — roots will still match only if unchanged
+    root = hashlib.sha256(
+        "\n".join(f"{n}:{h}" for n, h in sorted(files.items())).encode("utf-8")
+    ).hexdigest()
+    return {"algo": "sha256", "root": root, "file_count": len(files), "bound_count": bound}
+
+
+def _git_state() -> tuple[str, str]:
+    """(HEAD sha, dirty digest) of the source tree — captured at EXECUTE so the published
+    manifest attributes the build to the commit that actually produced the bytes; publish
+    REQUIRES equality (GPT re-review Major 2: a publish-time rev-parse misattributes the
+    build when code moved in between). The dirty digest is 'clean' or a sha256 over
+    `git status --porcelain` so an uncommitted-change flip also refuses."""
     import hashlib
-    root = hashlib.sha256(json.dumps(comp, sort_keys=True).encode("utf-8")).hexdigest()
-    return {"algo": "sha256", "root": root, "components": comp}
+    import subprocess
+    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True,
+                                   cwd=str(PROJECT_ROOT)).strip()
+    porcelain = subprocess.check_output(["git", "status", "--porcelain"], text=True,
+                                        cwd=str(PROJECT_ROOT))
+    dirty = "clean" if not porcelain.strip() else hashlib.sha256(porcelain.encode("utf-8")).hexdigest()
+    return head, dirty
 
 
 def _approvals_all_bound_to(pb: str, cp: str) -> tuple[bool, str]:
@@ -494,14 +556,12 @@ def _sub_binding_token(data: bytes, key: str, old: str, new: str, path: Path) ->
     return pat.sub(rb"\g<1>\g<2>" + new.encode("utf-8") + rb"\g<3>\g<4>", data, count=1)
 
 
-def _rebind_approval_files(old_pb: str, old_cp: str, new_pb: str, new_cp: str,
-                           ) -> tuple[list[Path], dict[Path, bytes]]:
-    """Two-phase byte-preserving rebind of every bound approval YAML (mirrors the
-    _rebind_approvals_depth9/thaw precedents, generalized). Phase 1 plans EVERY
-    substitution in memory and re-parses each result (the rebound YAML must parse to
-    exactly the new ids) — any failure writes NOTHING. Phase 2 writes atomically
-    per-file and restores already-written files if a write fails, then re-raises.
-    Returns (changed_paths, originals) so the caller can restore on later failures."""
+def _plan_rebind(old_pb: str, old_cp: str, new_pb: str, new_cp: str,
+                 ) -> tuple[list[tuple[Path, bytes]], dict[Path, bytes]]:
+    """PURE rebind planner (writes NOTHING — GPT re-review Blocker 2: the caller must hold
+    the originals BEFORE any write so restoration lives in exactly one verified place).
+    Plans every substitution in memory and re-parses each result (the rebound YAML must
+    parse to exactly the new ids). Returns (plan, originals)."""
     from data_infra.approval_evidence import load_approval_bindings
     bindings = load_approval_bindings(APPROVALS_DIR)
     plan: list[tuple[Path, bytes]] = []
@@ -519,21 +579,22 @@ def _rebind_approval_files(old_pb: str, old_cp: str, new_pb: str, new_cp: str,
             )
         originals[p] = data
         plan.append((p, nd))
-    written: list[Path] = []
-    try:
-        for p, nd in plan:
-            _atomic_write_bytes(p, nd)
-            written.append(p)
-    except Exception:
-        for p in written:
-            _atomic_write_bytes(p, originals[p])
-        raise
-    return [p for p, _ in plan], originals
+    return plan, originals
 
 
-def _restore_approval_files(originals: dict[Path, bytes]) -> None:
-    for p, data in originals.items():
-        _atomic_write_bytes(p, data)
+def _restore_approval_files(written: list[Path], originals: dict[Path, bytes]) -> list[str]:
+    """Restore the WRITTEN approval files from their original bytes and VERIFY each
+    restoration by re-reading (GPT re-review Blocker 2: an exit-4 'fully rolled back'
+    claim must be proven, not assumed). Returns the list of failures (empty = verified)."""
+    failures: list[str] = []
+    for p in written:
+        try:
+            _atomic_write_bytes(p, originals[p])
+            if p.read_bytes() != originals[p]:
+                failures.append(f"{p.name}: post-restore bytes differ from original")
+        except Exception as exc:  # noqa: BLE001 — collect, never mask a partial restore
+            failures.append(f"{p.name}: restore failed: {exc}")
+    return failures
 
 
 def _make_publish_builder(staged_build_id: str):
@@ -574,10 +635,12 @@ def _rollback_swap(builder) -> tuple[bool, str]:
 
 
 def _verify_live_manifest(qlib_dir, *, build_id: str, policy_id: str, raw_root: str,
-                          parent_pb: str) -> tuple[bool, str]:
+                          parent_pb: str, source_git_commit: str | None = None,
+                          ) -> tuple[bool, str]:
     """Post-swap check: the LIVE provider_build.json must attest exactly this
-    transaction (build id, policy, raw-input root, parent). Catches the emit path
-    failing silently (it is deliberately non-raising for legacy callers)."""
+    transaction (build id, policy, raw-input root, parent, and — Major 2 — the
+    EXECUTE-time source commit). Catches the emit path failing silently (it is
+    deliberately non-raising for legacy callers)."""
     from data_infra.provider_manifest import ProviderManifestError, load_provider_manifest
     try:
         m = load_provider_manifest(qlib_dir)
@@ -592,14 +655,34 @@ def _verify_live_manifest(qlib_dir, *, build_id: str, policy_id: str, raw_root:
         problems.append(f"raw_input_manifest_root={m.raw_input_manifest_root!r} != {raw_root!r}")
     if m.parent_provider_build_id != parent_pb:
         problems.append(f"parent_provider_build_id={m.parent_provider_build_id!r} != {parent_pb!r}")
+    if source_git_commit is not None and m.source_git_commit != source_git_commit:
+        problems.append(f"source_git_commit={m.source_git_commit!r} != {source_git_commit!r}")
     return (not problems), ("; ".join(problems) or "ok")
 
 
 def _write_journal(journal: dict) -> None:
-    OUT_DIR.mkdir(parents=True, exist_ok=True)
-    journal["updated_cst"] = now_cst().isoformat(timespec="seconds")
-    _atomic_write_bytes(TRANSACTION_JOURNAL_PATH,
-                        json.dumps(journal, ensure_ascii=False, indent=1).encode("utf-8"))
+    """NON-RAISING journal write (GPT re-review Blocker 1: a journal-write failure after a
+    successful swap must never abort the transaction outside the rollback domain — the
+    journal is a recovery breadcrumb, not a gate; a genuinely broken disk still fails the
+    transaction through the guarded record writes)."""
+    try:
+        OUT_DIR.mkdir(parents=True, exist_ok=True)
+        journal["updated_cst"] = now_cst().isoformat(timespec="seconds")
+        _atomic_write_bytes(TRANSACTION_JOURNAL_PATH,
+                            json.dumps(journal, ensure_ascii=False, indent=1).encode("utf-8"))
+    except Exception as exc:  # noqa: BLE001
+        logger.error("journal write failed (non-fatal breadcrumb): %s", exc)
+
+
+def _write_publish_state(qlib_dir, state: str, build_id: str, **extra) -> None:
+    """Atomic publish-state marker write (<qlib_dir>/metadata/publish_state.json — the B6
+    QA quarantine read by release_gate.assert_provider_publish_state)."""
+    meta = Path(qlib_dir) / "metadata"
+    meta.mkdir(parents=True, exist_ok=True)
+    payload = {"state": state, "provider_build_id": build_id,
+               "updated_cst": now_cst().isoformat(timespec="seconds"), **extra}
+    _atomic_write_bytes(meta / "publish_state.json",
+                        json.dumps(payload, ensure_ascii=False, indent=1).encode("utf-8"))
 
 
 def _run_post_publish_qa() -> int:
@@ -1124,14 +1207,35 @@ def _build_impl(args, parent_build, parent_policy, parent_end, target_end) -> in
     # subset). Sidecar carries the per-file hashes; the 256-bit root is recorded in the report, re-verified
     # by the publish transaction under its locks, and bound into the published provider_build.json (B3.2).
     raw_manifest = _full_raw_manifest()
-    RAW_MANIFEST_PATH.write_text(json.dumps(raw_manifest, ensure_ascii=False, indent=1), encoding="utf-8")
+    raw_manifest_json = json.dumps(raw_manifest, ensure_ascii=False, indent=1)
+    RAW_MANIFEST_PATH.write_text(raw_manifest_json, encoding="utf-8")
+    # GPT re-review Major 2: the fixed-name sidecar is overwritten by the next bump — ALSO
+    # persist a per-build copy AND ship one inside the provider's own metadata dir (written
+    # BEFORE the content attestation below, so it is part of the attested tree and survives
+    # with the published/.bak provider as the audit store of its raw cut).
+    (OUT_DIR / f"raw_input_manifest_{build_id}.json").write_text(raw_manifest_json, encoding="utf-8")
+    staged_meta = staged_provider / "metadata"
+    staged_meta.mkdir(parents=True, exist_ok=True)
+    (staged_meta / "raw_input_manifest.json").write_text(raw_manifest_json, encoding="utf-8")
     logger.info("raw-input manifest: %d files (full read set), root=%s",
                 raw_manifest["file_count"], raw_manifest["root"])
 
-    # 4e. transaction attestations (Phase 5-B): pin the audit artifacts + the staged tree's
-    # identity files at execute time; the publish transaction re-verifies all of them under
-    # its locks IMMEDIATELY before the swap and refuses on any drift.
-    staged_att = _staged_attestation(staged_provider)
+    # 4e. transaction attestations (Phase 5-B): pin the audit artifacts, the FULL staged
+    # tree content, the approvals governance set, the minted policy file, and the source
+    # git state at execute time; the publish transaction re-verifies ALL of them under its
+    # locks IMMEDIATELY before the swap and refuses on any drift.
+    logger.info("staged FULL-CONTENT attestation (every file incl. feature bins) ...")
+    staged_att = _staged_content_attestation(staged_provider)
+    (OUT_DIR / f"staged_content_manifest_{build_id}.json").write_text(
+        json.dumps(staged_att, ensure_ascii=False, indent=1), encoding="utf-8")
+    logger.info("staged content root=%s over %d files / %.1f GB",
+                staged_att["root"], staged_att["file_count"], staged_att["total_bytes"] / 2**30)
+    approvals_att = _approvals_attestation()
+    if approvals_att["bound_count"] < 1:
+        logger.error("approvals attestation found %d bound YAMLs — a bump must rebind a "
+                     "non-empty governance set; refusing.", approvals_att["bound_count"])
+        return 1
+    git_head, git_dirty = _git_state()
 
     # 5. dry-run report -> STOP for human sign-off.
     report = {
@@ -1144,8 +1248,16 @@ def _build_impl(args, parent_build, parent_policy, parent_end, target_end) -> in
         "frozen_prefix_audit_sha256": _sha256_file(fp_artifact),
         "fresh_window_audit_ok": fresh["ok"], "fresh_window_audit_artifact": str(FRESH_AUDIT_PATH.name),
         "fresh_window_audit_sha256": _sha256_file(FRESH_AUDIT_PATH),
-        "staged_attestation_root": staged_att["root"],
-        "staged_attestation_components": staged_att["components"],
+        "staged_content_root": staged_att["root"],
+        "staged_content_file_count": staged_att["file_count"],
+        "staged_content_total_bytes": staged_att["total_bytes"],
+        "staged_content_manifest_artifact": f"staged_content_manifest_{build_id}.json",
+        "approvals_attestation_root": approvals_att["root"],
+        "approvals_file_count": approvals_att["file_count"],
+        "approvals_bound_count": approvals_att["bound_count"],
+        "new_policy_sha256": _sha256_file(policy_path),
+        "source_git_commit": git_head,
+        "git_dirty_digest": git_dirty,
         "report_rc_replay_halo_start": _report_rc_halo_start(target_end),
         "endpoint_completeness": complete_ev,
         "raw_input_manifest_root": raw_manifest["root"],  # full-content input-cut attestation (M3)
@@ -1200,7 +1312,8 @@ def phase_publish(args) -> int:
     required_keys = ("target_end", "new_policy_id", "staged_build_id", "staged_provider_dir",
                      "parent_build_id", "parent_policy_id", "raw_input_manifest_root",
                      "frozen_prefix_audit_sha256", "fresh_window_audit_sha256",
-                     "staged_attestation_root")
+                     "staged_content_root", "approvals_attestation_root",
+                     "new_policy_sha256", "source_git_commit", "git_dirty_digest")
     missing = [k for k in required_keys if not rep.get(k)]
     if missing:
         logger.error("dry-run report lacks the Phase-5-B transaction attestations %s — re-run "
@@ -1252,18 +1365,13 @@ def phase_publish(args) -> int:
             logger.error("staged provider missing at %s — refusing.", staged_dir)
             j("verify", "refused", reason="staged_missing")
             return 2
-        att = _staged_attestation(staged_dir)
-        if att["root"] != rep["staged_attestation_root"]:
-            logger.error("STAGED-TREE DRIFT — staged attestation root %s != the reviewed report's %s "
-                         "(calendar/instruments/build-manifest moved since the audited build). "
-                         "Re-run --execute. Refusing.", att["root"], rep["staged_attestation_root"])
-            j("verify", "refused", reason="staged_attestation_drift")
-            return 2
-        ok, why = _verify_raw_manifest(manifest)
-        if not ok:
-            logger.error("RAW-INPUT MANIFEST MISMATCH (%s) — the raw cut the staged build consumed "
-                         "changed since the build. Re-run --execute. Refusing (fail closed).", why)
-            j("verify", "refused", reason=f"raw_manifest:{why}")
+        # Source-tree binding (Major 2): the code publishing must be the code that built.
+        git_head, git_dirty = _git_state()
+        if git_head != rep["source_git_commit"] or git_dirty != rep["git_dirty_digest"]:
+            logger.error("SOURCE DRIFT — git HEAD/dirty now (%s/%s) != at execute (%s/%s). The "
+                         "manifest would misattribute the build; re-run --execute. Refusing.",
+                         git_head, git_dirty, rep["source_git_commit"], rep["git_dirty_digest"])
+            j("verify", "refused", reason="git_state_drift")
             return 2
         try:
             pol = load_calendar_policy(rep["new_policy_id"], root=POLICY_DIR)
@@ -1271,6 +1379,12 @@ def phase_publish(args) -> int:
             logger.error("new policy %s no longer loads: %s — refusing.", rep["new_policy_id"], exc)
             j("verify", "refused", reason="policy_load_failed")
             return 2
+        policy_file = POLICY_DIR / f"{rep['new_policy_id']}.yaml"
+        if _sha256_file(policy_file) != rep["new_policy_sha256"]:
+            logger.error("POLICY FILE DRIFT — %s hash != the minted policy the report pinned. "
+                         "Refusing.", policy_file)
+            j("verify", "refused", reason="policy_file_drift")
+            return 2
         end_iso = f"{rep['target_end'][:4]}-{rep['target_end'][4:6]}-{rep['target_end'][6:]}"
         if (pol.spent_oos_end != SPENT_OOS_END or pol.fresh_holdout_start != FRESH_HOLDOUT_START
                 or not pol.frozen or pol.calendar_end_date != end_iso
@@ -1281,12 +1395,61 @@ def phase_publish(args) -> int:
                          pol.calendar_end_date, pol.require_raw_input_attestation)
             j("verify", "refused", reason="policy_drift")
             return 2
+        # Approvals: the governance SET must be exactly the execute-time pin (a deleted or
+        # added YAML refuses — Blocker 3 closed the loader's empty-dir fail-open), non-empty,
+        # AND every binding must still point at the parent.
+        approvals_att = _approvals_attestation()
+        if (approvals_att["root"] != rep["approvals_attestation_root"]
+                or approvals_att["bound_count"] < 1):
+            logger.error("APPROVALS SET DRIFT — attestation root/bound-count (%s/%d) != the "
+                         "reviewed report pin (%s/%s). A YAML was added/removed/edited since "
+                         "execute; re-run --execute. Refusing.", approvals_att["root"],
+                         approvals_att["bound_count"], rep["approvals_attestation_root"],
+                         rep.get("approvals_bound_count"))
+            j("verify", "refused", reason="approvals_set_drift")
+            return 2
         ok_bind, bind_msg = _approvals_all_bound_to(live_build, live_policy)
         if not ok_bind:
             logger.error("APPROVALS DRIFT — %s. Refusing (the post-swap rebind would not be a clean "
                          "parent->child rewrite).", bind_msg)
             j("verify", "refused", reason=f"approvals:{bind_msg}")
             return 2
+        # Plan the rebind NOW (pure, no writes): any planning refusal is a pre-swap refusal,
+        # and the caller holds every original byte before anything is written (Blocker 2).
+        try:
+            rebind_plan, originals = _plan_rebind(
+                live_build, live_policy, rep["staged_build_id"], rep["new_policy_id"])
+        except PublishTransactionError as exc:
+            logger.error("rebind planning refused: %s", exc)
+            j("verify", "refused", reason=f"rebind_plan:{exc}")
+            return 2
+        ok, why = _verify_raw_manifest(manifest)
+        if not ok:
+            logger.error("RAW-INPUT MANIFEST MISMATCH (%s) — the raw cut the staged build consumed "
+                         "changed since the build. Re-run --execute. Refusing (fail closed).", why)
+            j("verify", "refused", reason=f"raw_manifest:{why}")
+            return 2
+        # FULL-CONTENT staged re-attestation (Blocker 4): every byte about to be published —
+        # feature bins included — must equal what the audits attested at execute.
+        logger.info("re-attesting staged FULL content (%s files, %.1f GB) ...",
+                    rep.get("staged_content_file_count"),
+                    (rep.get("staged_content_total_bytes") or 0) / 2**30)
+        att = _staged_content_attestation(staged_dir)
+        if att["root"] != rep["staged_content_root"]:
+            changed_groups = []
+            try:
+                pinned = json.loads((OUT_DIR / rep["staged_content_manifest_artifact"])
+                                    .read_text(encoding="utf-8")).get("groups", {})
+                changed_groups = sorted(g for g in set(pinned) | set(att["groups"])
+                                        if pinned.get(g) != att["groups"].get(g))[:10]
+            except Exception:  # noqa: BLE001 — localization is best-effort diagnostics
+                pass
+            logger.error("STAGED-CONTENT DRIFT — full-content root %s != the reviewed report's %s "
+                         "(bytes changed since the audited build; first changed groups: %s). "
+                         "Re-run --execute. Refusing.", att["root"], rep["staged_content_root"],
+                         changed_groups)
+            j("verify", "refused", reason="staged_content_drift", changed_groups=changed_groups)
+            return 2
         builder = _make_publish_builder(rep["staged_build_id"])
         if Path(builder.paths.provider_dir).resolve() != staged_dir.resolve():
             logger.error("report staged_provider_dir %s is not the canonical staged path %s for "
@@ -1294,10 +1457,12 @@ def phase_publish(args) -> int:
                          rep["staged_build_id"])
             j("verify", "refused", reason="staged_path_mismatch")
             return 2
-        j("verify", "ok", raw_files=manifest["file_count"], approvals=bind_msg)
-        logger.info("verify OK under locks: parent (%s/%s), raw root %s (%d files), audits + staged "
-                    "attestation + policy + approvals — swapping now.", live_build, live_policy,
-                    manifest["root"], manifest["file_count"])
+        j("verify", "ok", raw_files=manifest["file_count"],
+          staged_files=att["file_count"], approvals=bind_msg)
+        logger.info("verify OK under locks: parent (%s/%s), raw root %s (%d files), staged content "
+                    "root %s (%d files), git %s, audits + policy + approvals — swapping now.",
+                    live_build, live_policy, manifest["root"], manifest["file_count"],
+                    att["root"], att["file_count"], git_head[:12])
 
         # ── SWAP: the proven primitive; single-rename failures self-roll-back inside it,
         # leaving the pre-publish state — so a bounded retry vs transient Windows handle
@@ -1310,7 +1475,8 @@ def phase_publish(args) -> int:
             try:
                 builder.publish(calendar_policy_id=rep["new_policy_id"],
                                 raw_input_manifest_root=manifest["root"],
-                                parent_provider_build_id=live_build)
+                                parent_provider_build_id=live_build,
+                                source_git_commit=rep["source_git_commit"])
                 swap_exc = None
                 break
             except BuildGateError as exc:
@@ -1333,19 +1499,29 @@ def phase_publish(args) -> int:
             logger.critical("swap DOUBLE failure — live provider MISSING; follow the recovery move "
                             "in the error: %s", swap_exc)
             return 5
-        j("swap", "ok", backup=f"{builder.paths.qlib_dir}.bak_{builder.build_id}")
 
-        # ── BIND: live manifest verification -> approvals rebind -> 0-drift -> records.
-        # Any failure here restores the approval bytes and rolls the swap back.
-        originals: dict[Path, bytes] = {}
+        # ── BIND: from the successful swap onward, EVERY operation — journal, manifest
+        # verification, rebind writes, state marker, records — runs inside ONE protected
+        # domain (GPT re-review Blocker 1: the first post-swap journal write previously sat
+        # outside it, so a journal failure aborted with the child live + approvals stale).
+        # Any failure restores the approval bytes, deletes this transaction's artifacts,
+        # strips the post-swap files from the new tree, rolls the swap back, and VERIFIES
+        # every restoration before claiming exit 4 (Blocker 2).
+        written: list[Path] = []
+        record_md: Path | None = None
+        record_written = False
+        state_written = False
         try:
+            j("swap", "ok", backup=f"{builder.paths.qlib_dir}.bak_{builder.build_id}")
             okm, why_m = _verify_live_manifest(
                 builder.paths.qlib_dir, build_id=rep["staged_build_id"],
-                policy_id=rep["new_policy_id"], raw_root=manifest["root"], parent_pb=live_build)
+                policy_id=rep["new_policy_id"], raw_root=manifest["root"], parent_pb=live_build,
+                source_git_commit=rep["source_git_commit"])
             if not okm:
                 raise PublishTransactionError(f"post-swap live manifest verification failed: {why_m}")
-            changed, originals = _rebind_approval_files(
-                live_build, live_policy, rep["staged_build_id"], rep["new_policy_id"])
+            for p, nd in rebind_plan:
+                _atomic_write_bytes(p, nd)
+                written.append(p)
             from data_infra.approval_evidence import evaluate_approval_evidence_bindings
             drifts = evaluate_approval_evidence_bindings(
                 approvals_dir=APPROVALS_DIR,
@@ -1354,63 +1530,142 @@ def phase_publish(args) -> int:
             if still:
                 raise PublishTransactionError(
                     f"{len(still)} approval(s) still drift after the rebind: {still[0].reasons()}")
-            record_md = _write_rebind_record(
-                new_pb=rep["staged_build_id"], new_cp=rep["new_policy_id"], old_pb=live_build,
-                old_cp=live_policy, n_files=len(changed), raw_root=manifest["root"],
-                raw_files=manifest["file_count"],
-                backup_dir=f"{builder.paths.qlib_dir}.bak_{builder.build_id}")
+            # B6 QA quarantine: the provider is durable but NOT ready — gated reads refuse
+            # until run_daily_qa passes and flips this marker to 'ready'.
+            _write_publish_state(builder.paths.qlib_dir, "pending_qa", rep["staged_build_id"],
+                                 parent_build_id=live_build)
+            state_written = True
             record = {
                 "published_build_id": rep["staged_build_id"],
                 "calendar_policy_id": rep["new_policy_id"],
                 "parent_build_id": live_build, "parent_policy_id": live_policy,
                 "raw_input_manifest_root": manifest["root"],
                 "raw_input_manifest_file_count": manifest["file_count"],
-                "staged_attestation_root": att["root"],
-                "approvals_rebound": len(changed),
-                "rebind_record": str(record_md),
+                "staged_content_root": att["root"],
+                "staged_content_file_count": att["file_count"],
+                "source_git_commit": rep["source_git_commit"],
+                "approvals_rebound": len(written),
                 "backup_dir": f"{builder.paths.qlib_dir}.bak_{builder.build_id}",
                 "reviewed_dryrun_report": str(DRYRUN_REPORT_PATH),
                 "published_cst": now_cst().isoformat(timespec="seconds"),
             }
             _atomic_write_bytes(PUBLISH_RECORD_PATH,
                                 json.dumps(record, ensure_ascii=False, indent=1).encode("utf-8"))
+            record_written = True
+            # the committed governance record is written LAST — nothing may claim a
+            # completed rebind before every durable step above proved out (Blocker 2b).
+            record_md = _write_rebind_record(
+                new_pb=rep["staged_build_id"], new_cp=rep["new_policy_id"], old_pb=live_build,
+                old_cp=live_policy, n_files=len(written), raw_root=manifest["root"],
+                raw_files=manifest["file_count"],
+                backup_dir=f"{builder.paths.qlib_dir}.bak_{builder.build_id}")
+            j("bind", "ok", approvals_rebound=len(written))
         except Exception as exc:  # noqa: BLE001 — every post-swap failure must roll back
-            logger.error("post-swap step failed (%s) — restoring approvals + rolling the swap back.", exc)
-            try:
-                _restore_approval_files(originals)
-            except Exception as rexc:  # noqa: BLE001
-                j("bind", "failed", error=str(exc), approvals_restore_error=str(rexc))
-                logger.critical("approval restore ALSO failed (%s) — repair the approval YAMLs from "
-                                "git before retrying.", rexc)
-                _rollback_swap(builder)
-                return 5
-            ok_rb, msg = _rollback_swap(builder)
-            j("bind", "failed_rolled_back" if ok_rb else "failed_rollback_failed",
-              error=str(exc), rollback=msg)
+            logger.error("post-swap step failed (%s) — restoring approvals + artifacts + rolling "
+                         "the swap back.", exc)
+            problems: list[str] = []
+            problems += _restore_approval_files(written, originals)
+            for artifact, present in ((record_md, record_md is not None),
+                                      (PUBLISH_RECORD_PATH, record_written)):
+                if present:
+                    try:
+                        Path(artifact).unlink(missing_ok=True)
+                    except OSError as uexc:
+                        problems.append(f"could not remove {artifact}: {uexc}")
+            # strip THIS transaction's post-swap files from the new tree so the returned
+            # staged tree matches its content attestation again for a clean retry
+            for name in ("provider_build.json", "publish_state.json"):
+                fpath = Path(builder.paths.qlib_dir) / "metadata" / name
+                try:
+                    fpath.unlink(missing_ok=True)
+                except OSError as uexc:
+                    problems.append(f"could not remove new-tree {name}: {uexc}")
+            ok_rb, rb_msg = _rollback_swap(builder)
             if ok_rb:
-                logger.error("ROLLED BACK to the parent live provider (%s). Fix the cause and re-run "
-                             "--publish-approved. Cause: %s", msg, exc)
+                try:
+                    rb_build, rb_policy = live_provider_ids()
+                    if (rb_build, rb_policy) != (live_build, live_policy):
+                        problems.append(f"post-rollback live ids ({rb_build}/{rb_policy}) != "
+                                        f"parent ({live_build}/{live_policy})")
+                except Exception as vexc:  # noqa: BLE001
+                    problems.append(f"post-rollback live manifest unreadable: {vexc}")
+            else:
+                problems.append(f"swap rollback failed: {rb_msg}")
+            if not problems:
+                j("bind", "failed_rolled_back", error=str(exc), rollback=rb_msg)
+                logger.error("ROLLED BACK to the parent live provider — VERIFIED (approval bytes "
+                             "re-read identical, parent ids live, artifacts removed): %s. Fix the "
+                             "cause and re-run --publish-approved. Cause: %s", rb_msg, exc)
                 return 4
-            logger.critical("ROLLBACK FAILED: %s — resolve manually per the journal (%s). Cause: %s",
-                            msg, TRANSACTION_JOURNAL_PATH, exc)
+            j("bind", "failed_rollback_incomplete", error=str(exc), rollback=rb_msg,
+              problems=problems)
+            logger.critical("ROLLBACK INCOMPLETE — resolve manually per the journal (%s). "
+                            "Problems: %s. Cause: %s", TRANSACTION_JOURNAL_PATH, problems, exc)
             return 5
-        j("bind", "ok", approvals_rebound=len(changed))
-    # ── locks released: swap + rebind + metadata are consistent and durable.
+    # ── locks released: swap + rebind + metadata are consistent and durable (state=pending_qa).
+
+    logger.info("ATOMIC PUBLISH COMPLETE: %s live under %s (parent %s retained as .bak; publish-state "
+                "pending_qa quarantines gated reads). Running post-publish QA ...",
+                rep["staged_build_id"], rep["new_policy_id"], live_build)
+    return _run_and_record_qa(builder.paths.qlib_dir, rep["staged_build_id"], j)
+
 
-    logger.info("ATOMIC PUBLISH COMPLETE: %s live under %s (parent %s retained as .bak). Running "
-                "post-publish QA ...", rep["staged_build_id"], rep["new_policy_id"], live_build)
+def _run_and_record_qa(qlib_dir, build_id: str, j) -> int:
+    """Run run_daily_qa and flip the publish-state marker accordingly (B6): PASS -> 'ready'
+    (gated reads open), FAIL -> 'qa_failed' (quarantine persists; exit 6). The flip is a
+    manifest-adjacent metadata write — taken under the global publish lock."""
+    from data_infra.tushare_lock import provider_publish_lock
     qa_rc = _run_post_publish_qa()
     if qa_rc != 0:
+        with provider_publish_lock():
+            _write_publish_state(qlib_dir, "qa_failed", build_id, qa_returncode=qa_rc)
         j("qa", "failed", returncode=qa_rc)
-        logger.critical("PUBLISHED but post-publish QA FAILED (exit %d) — investigate before any "
-                        "formal run. The provider stays live; parent retained at %s.bak_%s.",
-                        qa_rc, builder.paths.qlib_dir, builder.build_id)
+        logger.critical("PUBLISHED but post-publish QA FAILED (exit %d) — the provider stays live "
+                        "but publish-state 'qa_failed' QUARANTINES gated reads until "
+                        "--finalize-qa passes. Parent retained as .bak.", qa_rc)
         return 6
+    with provider_publish_lock():
+        _write_publish_state(qlib_dir, "ready", build_id, qa_returncode=0)
     j("qa", "ok")
-    logger.info("post-publish QA PASS. Publish record: %s", PUBLISH_RECORD_PATH)
+    logger.info("post-publish QA PASS — publish-state 'ready'. Publish record: %s", PUBLISH_RECORD_PATH)
     return 0
 
 
+def phase_finalize_qa(args) -> int:
+    """Re-run the post-publish QA leg for a provider stuck in 'pending_qa'/'qa_failed'
+    (crash between swap and QA, or a QA failure now resolved). Refuses when the live build
+    is not the reviewed report's staged build (the quarantine belongs to THIS publish)."""
+    if not DRYRUN_REPORT_PATH.exists():
+        logger.error("no dry-run report at %s — nothing to finalize.", DRYRUN_REPORT_PATH)
+        return 2
+    rep = json.loads(DRYRUN_REPORT_PATH.read_text(encoding="utf-8"))
+    live_build, _ = live_provider_ids()
+    if live_build != rep.get("staged_build_id"):
+        logger.error("live build %s is not the report's staged build %s — --finalize-qa only "
+                     "finishes the publish this report describes. Refusing.",
+                     live_build, rep.get("staged_build_id"))
+        return 2
+    builder = _make_publish_builder(rep["staged_build_id"])
+    state_file = Path(builder.paths.qlib_dir) / "metadata" / "publish_state.json"
+    try:
+        state = json.loads(state_file.read_text(encoding="utf-8")).get("state")
+    except (OSError, json.JSONDecodeError):
+        state = None
+    if state not in ("pending_qa", "qa_failed"):
+        logger.error("publish-state is %r — --finalize-qa only applies to pending_qa/qa_failed.", state)
+        return 2
+
+    journal: dict = {"transaction": "finalize_qa", "staged_build_id": rep["staged_build_id"],
+                     "steps": []}
+
+    def j(step: str, status: str, **info) -> None:
+        journal["steps"].append({"step": step, "status": status,
+                                 "ts_cst": now_cst().isoformat(timespec="seconds"), **info})
+        _write_journal(journal)
+
+    return _run_and_record_qa(builder.paths.qlib_dir, rep["staged_build_id"], j)
+
+
 def main() -> int:
     ap = argparse.ArgumentParser(description="Monthly calendar freeze-bump driver")
     ap.add_argument("--plan", action="store_true", help="Preflight + target_end + plan only")
@@ -1421,6 +1676,10 @@ def main() -> int:
                          "requires --i-reviewed-the-dryrun)")
     ap.add_argument("--i-reviewed-the-dryrun", action="store_true",
                     help="Attest the dry-run report was reviewed (required for --publish-approved)")
+    ap.add_argument("--finalize-qa", action="store_true",
+                    help="Re-run the post-publish QA leg for a provider quarantined at "
+                         "pending_qa/qa_failed (crash between swap and QA, or a resolved QA "
+                         "failure); flips publish-state to 'ready' on PASS")
     ap.add_argument("--target-end", type=str, default=None, help="Override target_end (YYYYMMDD)")
     ap.add_argument("--allow-migration-exception", action="store_true",
                     help="Acknowledge that a frozen-prefix exception type recurring 2+ bumps has "
@@ -1435,8 +1694,10 @@ def main() -> int:
         return phase_execute(args)
     if args.publish_approved:
         return phase_publish(args)
+    if args.finalize_qa:
+        return phase_finalize_qa(args)
     logger.error("choose a mode: --plan (review) | --execute (multi-hour, stops before publish) | "
-                 "--publish-approved --i-reviewed-the-dryrun")
+                 "--publish-approved --i-reviewed-the-dryrun | --finalize-qa")
     return 2
 
 
diff --git a/src/backtest_engine/event_driven/__init__.py b/src/backtest_engine/event_driven/__init__.py
index c88f976..4d088ee 100644
--- a/src/backtest_engine/event_driven/__init__.py
+++ b/src/backtest_engine/event_driven/__init__.py
@@ -238,14 +238,23 @@ def _validate_provider_at_runtime(
             manifest, live_calendar_end, allow_calendar_mismatch=False,
         )
 
-    # Phase 5-B (B3.2): policies minted by the monthly bump require the live manifest
-    # to carry raw_input_manifest_root (the attested raw-input cut of the publish).
-    # Legacy policies leave the flag unset and skip cleanly inside the gate.
-    from src.research_orchestrator.release_gate import assert_provider_raw_attestation
+    # Phase 5-B (B3.2 + B6): policies minted by the monthly bump require the live manifest
+    # to carry raw_input_manifest_root (the attested raw-input cut of the publish) AND the
+    # publish-state marker to read "ready" (QA quarantine — a provider that swapped but has
+    # not passed post-publish QA must not serve a formal run). Legacy policies skip the
+    # attestation/marker-presence requirements but still honor a present non-ready marker.
+    from src.research_orchestrator.release_gate import (
+        assert_provider_publish_state,
+        assert_provider_raw_attestation,
+    )
     assert_provider_raw_attestation(
         manifest=manifest, policy=policy,
         artifact_label=f"run_mode={run_mode!r} under policy {calendar_policy_id!r}",
     )
+    assert_provider_publish_state(
+        qlib_dir=qlib_dir, policy=policy, manifest=manifest,
+        artifact_label=f"run_mode={run_mode!r} under policy {calendar_policy_id!r}",
+    )
 
 
 class EventDrivenBacktester:
diff --git a/src/data_infra/pit_backend.py b/src/data_infra/pit_backend.py
index 9b69464..dd91cc4 100644
--- a/src/data_infra/pit_backend.py
+++ b/src/data_infra/pit_backend.py
@@ -4599,6 +4599,7 @@ class StagedQlibBackendBuilder:
         emit_manifest: bool = True,
         raw_input_manifest_root: str | None = None,
         parent_provider_build_id: str | None = None,
+        source_git_commit: str | None = None,
     ) -> None:
         """Atomically promote the staged provider into ``data/qlib_data``.
 
@@ -4626,6 +4627,30 @@ class StagedQlibBackendBuilder:
         record ``provider_build_id``. Disable with ``emit_manifest=False`` only
         for hot-restore drills where attestation is not desired.
         """
+        # Phase 5-B B7: the GLOBAL provider-publish lock is acquired HERE, at the common
+        # chokepoint, so every sanctioned publisher excludes every other regardless of
+        # entrypoint. Reentrant (per-path singleton FileLock — shared across the dual
+        # src./plain namespaces) — the monthly transaction already holding it nests
+        # without deadlock. Sibling-relative import resolves under either namespace root.
+        from .tushare_lock import provider_publish_lock
+        with provider_publish_lock():
+            self._publish_locked(
+                calendar_policy_id=calendar_policy_id,
+                emit_manifest=emit_manifest,
+                raw_input_manifest_root=raw_input_manifest_root,
+                parent_provider_build_id=parent_provider_build_id,
+                source_git_commit=source_git_commit,
+            )
+
+    def _publish_locked(
+        self,
+        *,
+        calendar_policy_id: str,
+        emit_manifest: bool,
+        raw_input_manifest_root: str | None,
+        parent_provider_build_id: str | None,
+        source_git_commit: str | None,
+    ) -> None:
         if not os.path.isdir(self.paths.provider_dir):
             raise BuildGateError("Cannot publish: staged provider directory is missing")
 
@@ -4705,6 +4730,7 @@ class StagedQlibBackendBuilder:
                 calendar_policy_id=calendar_policy_id,
                 raw_input_manifest_root=raw_input_manifest_root,
                 parent_provider_build_id=parent_provider_build_id,
+                source_git_commit=source_git_commit,
             )
 
     def _emit_provider_manifest_at_publish(
@@ -4713,6 +4739,7 @@ class StagedQlibBackendBuilder:
         calendar_policy_id: str,
         raw_input_manifest_root: str | None = None,
         parent_provider_build_id: str | None = None,
+        source_git_commit: str | None = None,
     ) -> None:
         """Emit data/qlib_data/metadata/provider_build.json after publish.
 
@@ -4734,14 +4761,18 @@ class StagedQlibBackendBuilder:
             logger.warning("Failed to read calendars/day.txt for manifest emission: %s", exc)
             return
 
-        source_commit: str | None = None
-        try:
-            import subprocess
-            source_commit = (
-                subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip() or None
-            )
-        except (OSError, subprocess.CalledProcessError):
-            source_commit = None
+        # Phase 5-B (GPT re-review Major 2): when the caller binds the BUILD-time commit
+        # (the monthly transaction records it at execute), stamp THAT — publish-time
+        # `rev-parse HEAD` misattributes the build if code moved between build and publish.
+        source_commit: str | None = source_git_commit
+        if source_commit is None:
+            try:
+                import subprocess
+                source_commit = (
+                    subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip() or None
+                )
+            except (OSError, subprocess.CalledProcessError):
+                source_commit = None
 
         from data_infra.provider_manifest import emit_manifest_at_publish
         try:
diff --git a/src/data_infra/provider_context.py b/src/data_infra/provider_context.py
index e066e74..c806f16 100644
--- a/src/data_infra/provider_context.py
+++ b/src/data_infra/provider_context.py
@@ -80,7 +80,19 @@ def _resolve() -> tuple[str, str, pd.Timestamp, Optional[str]]:
             f"live provider manifest under {qlib_dir} changed during read — "
             "fail closed (mid-publish; retry)."
         )
-    key = (str(manifest_file), stat.st_mtime_ns, stat.st_size, digest)
+    # Phase 5-B B6: the publish-state marker is part of the provider's IDENTITY for gated
+    # reads — fold its content digest into the cache key so a --finalize-qa flip (which
+    # does not touch the manifest) re-runs the gates instead of serving a cached verdict.
+    state_file = qlib_dir / "metadata" / "publish_state.json"
+    try:
+        state_digest = (
+            hashlib.sha256(state_file.read_bytes()).hexdigest() if state_file.exists() else "absent"
+        )
+    except Exception as exc:
+        raise ProviderContextError(
+            f"cannot read the live provider publish-state marker under {qlib_dir}: {exc} — fail closed."
+        ) from exc
+    key = (str(manifest_file), stat.st_mtime_ns, stat.st_size, digest + ":" + state_digest)
 
     cached = _CACHE.get(key)
     if cached is not None:
@@ -104,6 +116,29 @@ def _resolve() -> tuple[str, str, pd.Timestamp, Optional[str]]:
             f"{exc} — fail closed."
         ) from exc
 
+    # Phase 5-B (GPT re-review Blockers 5 + 6): BOTH sanctioned data doors — the sandbox
+    # pit_research_loader and the formal qlib_windowed_features — resolve through here, so
+    # this is where the raw-input attestation and the QA-quarantine publish-state become
+    # load-bearing for every gated read (the event-driven runtime validator re-checks them
+    # independently for formal backtests). Gate errors surface verbatim, wrapped as the
+    # fail-closed context error callers already handle.
+    try:
+        from src.research_orchestrator.release_gate import (
+            assert_provider_publish_state,
+            assert_provider_raw_attestation,
+        )
+        assert_provider_raw_attestation(
+            manifest=manifest, policy=policy, artifact_label="live-provider resolution")
+        assert_provider_publish_state(
+            qlib_dir=qlib_dir, policy=policy, manifest=manifest,
+            artifact_label="live-provider resolution")
+    except ProviderContextError:
+        raise
+    except Exception as exc:
+        raise ProviderContextError(
+            f"live provider refused by the publish gates: {exc} — fail closed."
+        ) from exc
+
     # R6-m5: the miss path re-reads the manifest inside load_provider_manifest;
     # re-hash after the full resolution and require the content identity to be
     # UNCHANGED vs the key — a rotation landing mid-resolution fails closed
diff --git a/src/data_infra/provider_manifest.py b/src/data_infra/provider_manifest.py
index 626db38..aff2765 100644
--- a/src/data_infra/provider_manifest.py
+++ b/src/data_infra/provider_manifest.py
@@ -428,17 +428,31 @@ def emit_retroactive_manifest(
         retroactive_manifest_evidence=tuple(evidence_list),
     )
 
-    target = manifest_path_for(qlib_dir)
-    target.parent.mkdir(parents=True, exist_ok=True)
-    tmp = target.with_name(target.name + f".tmp.{os.getpid()}")
-    with open(tmp, "w", encoding="utf-8") as handle:
-        json.dump(manifest.to_dict(), handle, ensure_ascii=False, indent=2, sort_keys=True)
-        handle.write("\n")
-    os.replace(tmp, target)
+    target = _write_manifest_locked(qlib_dir, manifest)
     logger.info("Wrote retroactive provider manifest to %s", target)
     return target
 
 
+def _write_manifest_locked(qlib_dir: Path, manifest: ProviderManifest) -> Path:
+    """Atomic manifest write under the GLOBAL provider-publish lock (Phase 5-B B7): every
+    sanctioned ``provider_build.json`` writer serializes against the swap transaction and
+    against each other. Reentrant for callers already holding the lock (the FileLock is a
+    per-PATH library-level singleton, so the dual src./plain module namespaces share one
+    lock instance). Relative import: this module is legitimately imported under BOTH
+    namespace roots, and a sibling-relative import resolves under either."""
+    from .tushare_lock import provider_publish_lock
+
+    target = manifest_path_for(qlib_dir)
+    with provider_publish_lock():
+        target.parent.mkdir(parents=True, exist_ok=True)
+        tmp = target.with_name(target.name + f".tmp.{os.getpid()}")
+        with open(tmp, "w", encoding="utf-8") as handle:
+            json.dump(manifest.to_dict(), handle, ensure_ascii=False, indent=2, sort_keys=True)
+            handle.write("\n")
+        os.replace(tmp, target)
+    return target
+
+
 def emit_manifest_at_publish(
     *,
     qlib_dir: str | os.PathLike[str],
@@ -502,12 +516,6 @@ def emit_manifest_at_publish(
         parent_provider_build_id=parent_provider_build_id,
     )
 
-    target = manifest_path_for(qlib_dir)
-    target.parent.mkdir(parents=True, exist_ok=True)
-    tmp = target.with_name(target.name + f".tmp.{os.getpid()}")
-    with open(tmp, "w", encoding="utf-8") as handle:
-        json.dump(manifest.to_dict(), handle, ensure_ascii=False, indent=2, sort_keys=True)
-        handle.write("\n")
-    os.replace(tmp, target)
+    target = _write_manifest_locked(qlib_dir, manifest)
     logger.info("Wrote provider manifest to %s", target)
     return target
diff --git a/src/data_infra/tushare_lock.py b/src/data_infra/tushare_lock.py
index 9dbbd5a..78b6ea7 100644
--- a/src/data_infra/tushare_lock.py
+++ b/src/data_infra/tushare_lock.py
@@ -67,13 +67,26 @@ def raw_maintenance_lock(timeout: float = 21600.0):  # 6h default — a monthly
 
 @contextmanager
 def provider_publish_lock(timeout: float = 7200.0):
-    """Process-exclusive LIVE-provider publish/swap (the monthly bump's atomic verify->swap->rebind
-    transaction, Phase 5-B B3). Serializes anything that replaces ``data/qlib_data`` or rewrites its
-    ``provider_build.json`` so two publishers can never interleave renames. LOCK ORDER: acquire
-    ``raw_maintenance_lock`` FIRST, then this — every holder follows that one order (the publish
-    transaction), so there is no reverse-order path and no lock-order deadlock."""
-    with _filelock("provider_publish.lock", timeout):
+    """Process-exclusive LIVE-provider publish/swap + manifest writes (Phase 5-B B3; GPT
+    re-review Blocker 7 made this a GLOBAL publish lock, not a driver-private one).
+
+    Held at the COMMON CHOKEPOINTS — ``StagedQlibBackendBuilder.publish()`` and the
+    ``provider_build.json`` emitters in ``provider_manifest`` acquire it themselves — so ANY
+    sanctioned publisher/manifest writer excludes any other, whichever entrypoint invoked it.
+    The monthly transaction additionally holds it across its whole verify->swap->rebind scope.
+
+    REENTRANT within a process/thread: the underlying ``FileLock`` is a per-path SINGLETON
+    (``is_singleton=True``; verified on filelock 3.25.2 — same instance, counted acquire), so
+    the transaction holding the lock can call ``publish()`` which re-acquires without
+    deadlocking, while a second process still blocks. LOCK ORDER: any holder that also needs
+    ``raw_maintenance_lock`` acquires raw FIRST, then this; publish-lock-only holders (the
+    builder/emitters) never take the raw lock afterwards — no reverse-order path exists."""
+    lock = FileLock(str(_lock_dir() / "provider_publish.lock"), is_singleton=True)
+    lock.acquire(timeout=timeout)
+    try:
         yield
+    finally:
+        lock.release()
 
 
 # ── global cross-process rate spacing (a shared next-allowed timestamp, held under the API lock) ──
diff --git a/src/research_orchestrator/calendar_policy.py b/src/research_orchestrator/calendar_policy.py
index 4859baf..397c233 100644
--- a/src/research_orchestrator/calendar_policy.py
+++ b/src/research_orchestrator/calendar_policy.py
@@ -102,6 +102,19 @@ class CalendarPolicy:
                 "spent_oos_end / fresh_holdout_start — both or neither."
             )
 
+        # Phase 5-B B3.2 (GPT re-review Major 1): the attestation requirement must be a real
+        # bool or absent. A truthy-but-non-bool value (the YAML string "true", 1, ...) must
+        # REFUSE, not silently read as False — that would be a fail-open typo path on a
+        # load-bearing enforcement flag.
+        require_attestation = payload.get("require_raw_input_attestation", False)
+        if not isinstance(require_attestation, bool):
+            raise CalendarPolicyError(
+                f"Calendar policy {payload['policy_id']!r}: require_raw_input_attestation "
+                f"must be a YAML bool (true/false) or absent, got "
+                f"{require_attestation!r} ({type(require_attestation).__name__}). A quoted "
+                "'true' would silently disable a load-bearing enforcement flag — fail closed."
+            )
+
         return cls(
             policy_id=str(payload["policy_id"]),
             policy_schema_version=schema_version,
@@ -117,7 +130,7 @@ class CalendarPolicy:
             notes=tuple(str(n) for n in payload.get("notes", ())),
             spent_oos_end=str(spent) if spent is not None else None,
             fresh_holdout_start=str(fresh) if fresh is not None else None,
-            require_raw_input_attestation=payload.get("require_raw_input_attestation") is True,
+            require_raw_input_attestation=require_attestation,
         )
 
     def permits_calendar_mismatch(self, run_mode: str) -> bool:
diff --git a/src/research_orchestrator/release_gate.py b/src/research_orchestrator/release_gate.py
index 732b401..9a63f29 100644
--- a/src/research_orchestrator/release_gate.py
+++ b/src/research_orchestrator/release_gate.py
@@ -519,9 +519,10 @@ def assert_provider_raw_attestation(
 ) -> ProviderAttestationGateResult:
     """Strict variant of :func:`evaluate_provider_raw_attestation` for formal paths.
 
-    Wired at the formal-run provider-validation chokepoint
-    (``backtest_engine.event_driven._validate_provider_at_runtime``), where both the
-    loaded manifest and the calendar policy are in hand.
+    Wired at BOTH read chokepoints: the formal-run provider validation
+    (``backtest_engine.event_driven._validate_provider_at_runtime``) and the shared
+    live-provider resolution every sanctioned data door goes through
+    (``data_infra.provider_context._resolve``).
     """
     result = evaluate_provider_raw_attestation(manifest=manifest, policy=policy)
     if not result.eligible:
@@ -532,6 +533,112 @@ def assert_provider_raw_attestation(
     return result
 
 
+# ─────────────────────────────────────────────────────────────────────────
+# Provider publish-state (QA quarantine) gate — Phase 5-B B3, GPT re-review Blocker 6
+# ─────────────────────────────────────────────────────────────────────────
+#
+# The monthly atomic publish writes <qlib_dir>/metadata/publish_state.json with
+# state="pending_qa" the moment the swap+rebind are durable, flips it to "ready" only
+# after run_daily_qa PASSES, and to "qa_failed" on a QA failure. This gate makes that
+# quarantine MECHANICAL: while the marker is not "ready", every gated read path refuses —
+# a provider that published but failed (or has not yet run) QA cannot serve research.
+# Roll-forward scoping mirrors the raw attestation: a policy with
+# require_raw_input_attestation=True REQUIRES the marker to exist; legacy policies allow
+# an absent marker (pre-5B providers never had one) but STILL honor a present non-ready
+# marker (a written quarantine is always load-bearing).
+
+PUBLISH_STATE_FILENAME = "publish_state.json"
+PUBLISH_STATE_READY = "ready"
+PUBLISH_STATE_PENDING_QA = "pending_qa"
+PUBLISH_STATE_QA_FAILED = "qa_failed"
+
+
+def read_provider_publish_state(qlib_dir: Any) -> dict[str, Any] | None:
+    """The parsed publish-state marker for ``qlib_dir``, or ``None`` when absent.
+    Malformed content returns ``{"state": "<malformed>"}`` so gated readers fail closed
+    instead of treating corruption as legacy-absent."""
+    path = Path(qlib_dir) / "metadata" / PUBLISH_STATE_FILENAME
+    if not path.exists():
+        return None
+    try:
+        payload = json.loads(path.read_text(encoding="utf-8"))
+        if not isinstance(payload, dict):
+            return {"state": "<malformed>"}
+        return payload
+    except (OSError, json.JSONDecodeError):
+        return {"state": "<malformed>"}
+
+
+def evaluate_provider_publish_state(
+    *,
+    qlib_dir: Any,
+    policy: Any,
+    manifest: Any = None,
+) -> ProviderAttestationGateResult:
+    """Decide whether the live provider's publish-state marker admits gated reads.
+
+    When ``manifest`` is supplied, a present marker must also name the SAME
+    ``provider_build_id`` — a marker left behind by a different build is corruption,
+    not clearance."""
+    def _get(obj: Any, key: str) -> Any:
+        if isinstance(obj, Mapping):
+            return obj.get(key)
+        return getattr(obj, key, None)
+
+    policy_id = _get(policy, "policy_id")
+    required = _get(policy, "require_raw_input_attestation") is True
+    build_id = _get(manifest, "provider_build_id") if manifest is not None else None
+    state_payload = read_provider_publish_state(qlib_dir)
+
+    reasons: list[str] = []
+    if state_payload is None:
+        if required:
+            reasons.append(
+                f"calendar policy {policy_id!r} requires the publish-state marker "
+                f"(metadata/{PUBLISH_STATE_FILENAME}) but the live provider carries none — "
+                "the build did not complete the attested publish transaction."
+            )
+    else:
+        state = state_payload.get("state")
+        if state != PUBLISH_STATE_READY:
+            reasons.append(
+                f"live provider publish-state is {state!r} (not '{PUBLISH_STATE_READY}') — "
+                "post-publish QA has not passed; the provider is quarantined for gated "
+                "reads. Run scripts/monthly_calendar_bump.py --finalize-qa after resolving."
+            )
+        marker_build = state_payload.get("provider_build_id")
+        if build_id is not None and marker_build is not None and str(marker_build) != str(build_id):
+            reasons.append(
+                f"publish-state marker names build {marker_build!r} but the live manifest is "
+                f"{build_id!r} — stale/foreign marker; refusing."
+            )
+
+    return ProviderAttestationGateResult(
+        eligible=len(reasons) == 0,
+        required=required,
+        policy_id=str(policy_id) if policy_id is not None else None,
+        provider_build_id=str(build_id) if build_id is not None else None,
+        raw_input_manifest_root=None,
+        reasons=tuple(reasons),
+    )
+
+
+def assert_provider_publish_state(
+    *,
+    qlib_dir: Any,
+    policy: Any,
+    manifest: Any = None,
+    artifact_label: str = "gated read",
+) -> ProviderAttestationGateResult:
+    """Strict variant of :func:`evaluate_provider_publish_state` for gated paths."""
+    result = evaluate_provider_publish_state(qlib_dir=qlib_dir, policy=policy, manifest=manifest)
+    if not result.eligible:
+        raise ProviderAttestationError(
+            f"Provider publish-state gate blocked {artifact_label}: {list(result.reasons)}"
+        )
+    return result
+
+
 # ─────────────────────────────────────────────────────────────────────────
 # Promotion gate — independent PIT-correct reproduction (PIT-prevention step 11)
 # ─────────────────────────────────────────────────────────────────────────
diff --git a/tests/data_infra/test_monthly_calendar_bump.py b/tests/data_infra/test_monthly_calendar_bump.py
index aa0eb9f..5f15089 100644
--- a/tests/data_infra/test_monthly_calendar_bump.py
+++ b/tests/data_infra/test_monthly_calendar_bump.py
@@ -550,7 +550,8 @@ def _publish_env(tmp_path, monkeypatch, *, qa_rc: int = 0):
     (qlib / "metadata" / "provider_build.json").write_text(_json.dumps(
         {"provider_build_id": parent_pb, "calendar_policy_id": parent_cp}), encoding="utf-8")
 
-    # staged provider (the child) at the canonical build path
+    # staged provider (the child) at the canonical build path — incl. a feature BIN whose
+    # bytes the full-content attestation must protect (GPT re-review Blocker 4)
     staged = data / "qlib_builds" / new_pb / "provider"
     (staged / "calendars").mkdir(parents=True)
     (staged / "calendars" / "day.txt").write_text("2008-01-02\n2099-01-01\n", encoding="utf-8")
@@ -558,6 +559,7 @@ def _publish_env(tmp_path, monkeypatch, *, qa_rc: int = 0):
     (staged / "instruments" / "all_stocks.txt").write_text(
         "000001_SZ\t2008-01-02\t2099-01-01\n", encoding="utf-8")
     (staged / "features" / "000001_sz").mkdir(parents=True)
+    (staged / "features" / "000001_sz" / "close.day.bin").write_bytes(b"\x01\x02\x03\x04")
     (staged / "STAGED_MARKER.txt").write_text("child", encoding="utf-8")
     (data / "qlib_builds" / new_pb / "manifest.json").write_text("{}", encoding="utf-8")
 
@@ -592,19 +594,33 @@ def _publish_env(tmp_path, monkeypatch, *, qa_rc: int = 0):
     manifest = mcb._full_raw_manifest(data)
     (out / "raw_input_manifest.json").write_text(_json.dumps(manifest), encoding="utf-8")
 
-    # audit artifacts + staged attestation, pinned into the dry-run report
+    # audit artifacts + the full transaction attestation set, pinned into the dry-run report
     fp = out / "frozen_prefix_audit.json"
     fp.write_text(_json.dumps({"staged": str(staged), "ok": True}), encoding="utf-8")
     fw = out / "fresh_window_survivorship_audit.json"
     fw.write_text(_json.dumps({"ok": True, "violations": []}), encoding="utf-8")
-    att = mcb._staged_attestation(staged)
+    monkeypatch.setattr(mcb, "_git_state", lambda: ("testsha0123", "clean"))
+    att = mcb._staged_content_attestation(staged)
+    (out / f"staged_content_manifest_{new_pb}.json").write_text(
+        _json.dumps(att), encoding="utf-8")
+    appr_att = mcb._approvals_attestation()
+    policy_file = root / "policies" / f"{new_cp}.yaml"
     report = {
         "target_end": "20990101", "new_policy_id": new_cp, "staged_build_id": new_pb,
         "staged_provider_dir": str(staged), "parent_build_id": parent_pb,
         "parent_policy_id": parent_cp, "raw_input_manifest_root": manifest["root"],
         "frozen_prefix_audit_sha256": mcb._sha256_file(fp),
         "fresh_window_audit_sha256": mcb._sha256_file(fw),
-        "staged_attestation_root": att["root"],
+        "staged_content_root": att["root"],
+        "staged_content_file_count": att["file_count"],
+        "staged_content_total_bytes": att["total_bytes"],
+        "staged_content_manifest_artifact": f"staged_content_manifest_{new_pb}.json",
+        "approvals_attestation_root": appr_att["root"],
+        "approvals_file_count": appr_att["file_count"],
+        "approvals_bound_count": appr_att["bound_count"],
+        "new_policy_sha256": mcb._sha256_file(policy_file),
+        "source_git_commit": "testsha0123",
+        "git_dirty_digest": "clean",
     }
     (out / "monthly_bump_dryrun_report.json").write_text(_json.dumps(report), encoding="utf-8")
 
@@ -615,11 +631,18 @@ def _publish_env(tmp_path, monkeypatch, *, qa_rc: int = 0):
     monkeypatch.setattr(mcb, "_make_publish_builder", _builder)
     return _types.SimpleNamespace(
         root=root, data=data, qlib=qlib, staged=staged, out=out, raw=raw,
+        staged_bin=staged / "features" / "000001_sz" / "close.day.bin",
+        policy_file=policy_file,
         parent_pb=parent_pb, parent_cp=parent_cp, new_pb=new_pb, new_cp=new_cp,
         manifest=manifest, a1=a1, a2=a2,
         a1_bytes=a1.read_bytes(), a2_bytes=a2.read_bytes())
 
 
+def _publish_state_of(qlib) -> str | None:
+    p = qlib / "metadata" / "publish_state.json"
+    return _json.loads(p.read_text(encoding="utf-8"))["state"] if p.exists() else None
+
+
 def _assert_untouched(env):
     """The refusal contract: NOTHING durable mutated — parent still live, staged still
     staged, approvals byte-identical."""
@@ -642,6 +665,8 @@ def test_publish_transaction_happy_path(tmp_path, monkeypatch):
     assert m["calendar_policy_id"] == env.new_cp
     assert m["raw_input_manifest_root"] == env.manifest["root"]
     assert m["parent_provider_build_id"] == env.parent_pb
+    assert m["source_git_commit"] == "testsha0123"  # the EXECUTE-time commit, not publish-time
+    assert _publish_state_of(env.qlib) == "ready"   # QA passed -> quarantine lifted
     # rebind: both quoting styles preserved, values swapped; exempt untouched
     t1 = env.a1.read_text(encoding="utf-8")
     assert f'provider_build_id: "{env.new_pb}"' in t1 and f"calendar_policy_id: {env.new_cp}" in t1
@@ -704,7 +729,7 @@ def test_publish_refuses_pre_phase5b_report(tmp_path, monkeypatch):
     # — publish verifies exactly what execute attested, or nothing.
     env = _publish_env(tmp_path, monkeypatch)
     rep = _json.loads((env.out / "monthly_bump_dryrun_report.json").read_text(encoding="utf-8"))
-    del rep["staged_attestation_root"]
+    del rep["staged_content_root"]
     (env.out / "monthly_bump_dryrun_report.json").write_text(_json.dumps(rep), encoding="utf-8")
     assert mcb.phase_publish(_PubArgs()) == 2
     _assert_untouched(env)
@@ -725,6 +750,15 @@ def test_publish_rolls_back_on_postswap_failure(tmp_path, monkeypatch):
     assert mcb.live_provider_ids() == (env.parent_pb, env.parent_cp)
     assert env.a1.read_bytes() == env.a1_bytes and env.a2.read_bytes() == env.a2_bytes
     assert not (env.data / f"qlib_data.bak_{env.new_pb}").exists(), "rollback must consume the backup"
+    # this transaction's artifacts must not survive a rollback (GPT re-review Blocker 2b):
+    assert not (env.out / "publish_record.json").exists(), "publish record must be removed"
+    assert not list((env.root / "approvals").glob("*_rebind_to_*.md")), "no rebind md may remain"
+    # ... and the returned staged tree is stripped back to its ATTESTED content, so a
+    # clean retry passes the content re-attestation:
+    assert not (env.staged / "metadata" / "provider_build.json").exists()
+    assert not (env.staged / "metadata" / "publish_state.json").exists()
+    rep = _json.loads((env.out / "monthly_bump_dryrun_report.json").read_text(encoding="utf-8"))
+    assert mcb._staged_content_attestation(env.staged)["root"] == rep["staged_content_root"]
     steps = _json.loads((env.out / "publish_transaction_journal.json").read_text(encoding="utf-8"))["steps"]
     assert any(s["step"] == "bind" and s["status"] == "failed_rolled_back" for s in steps)
 
@@ -746,15 +780,26 @@ def test_publish_rolls_back_when_manifest_emission_fails(tmp_path, monkeypatch):
     assert env.a1.read_bytes() == env.a1_bytes
 
 
-def test_publish_qa_failure_returns_6_and_keeps_provider(tmp_path, monkeypatch):
-    # QA runs OUTSIDE the transaction: a QA failure alarms (exit 6) but does not undo a
-    # consistent swap+rebind+metadata — the operator investigates with the .bak retained.
+def test_publish_qa_failure_returns_6_and_quarantines(tmp_path, monkeypatch):
+    # QA runs OUTSIDE the transaction: a QA failure alarms (exit 6) and does not undo a
+    # consistent swap+rebind+metadata — but the publish-state marker QUARANTINES gated
+    # reads mechanically (GPT re-review Blocker 6), and --finalize-qa lifts it on a pass.
     env = _publish_env(tmp_path, monkeypatch, qa_rc=1)
     assert mcb.phase_publish(_PubArgs()) == 6
     assert (env.qlib / "STAGED_MARKER.txt").exists(), "the published provider stays live"
     m = _json.loads((env.qlib / "metadata" / "provider_build.json").read_text(encoding="utf-8"))
     assert m["provider_build_id"] == env.new_pb
     assert f'provider_build_id: "{env.new_pb}"' in env.a1.read_text(encoding="utf-8")
+    assert _publish_state_of(env.qlib) == "qa_failed", "quarantine marker must persist"
+    # the marker is load-bearing at the gate:
+    from src.research_orchestrator.release_gate import evaluate_provider_publish_state
+    gate = evaluate_provider_publish_state(qlib_dir=env.qlib, policy=object(), manifest=None)
+    assert not gate.eligible and any("qa_failed" in r for r in gate.reasons)
+    # QA resolved -> --finalize-qa flips to ready
+    monkeypatch.setattr(mcb, "_run_post_publish_qa", lambda: 0)
+    assert mcb.phase_finalize_qa(_PubArgs()) == 0
+    assert _publish_state_of(env.qlib) == "ready"
+    assert evaluate_provider_publish_state(qlib_dir=env.qlib, policy=object(), manifest=None).eligible
 
 
 def test_generate_thaw_policy_requires_raw_attestation(tmp_path, monkeypatch):
@@ -763,3 +808,167 @@ def test_generate_thaw_policy_requires_raw_attestation(tmp_path, monkeypatch):
     _pid, path = mcb.generate_thaw_policy("20990131", "pb", write=True)
     body = _yamlmod.safe_load(path.read_text(encoding="utf-8"))
     assert body["require_raw_input_attestation"] is True
+
+
+# ── GPT re-review probes (Blockers 1-4, 7 + Majors) ──────────────────────────
+def test_publish_survives_journal_write_failure_after_swap(tmp_path, monkeypatch):
+    # GPT Blocker 1 probe: the first post-swap journal write previously sat OUTSIDE the
+    # rollback domain — a journal fault left the child live with stale approvals and no
+    # rollback. Now the journal is a non-raising breadcrumb: the transaction completes.
+    env = _publish_env(tmp_path, monkeypatch)
+    monkeypatch.setattr(mcb, "TRANSACTION_JOURNAL_PATH", env.out)  # a DIRECTORY -> every write fails
+    assert mcb.phase_publish(_PubArgs()) == 0
+    assert (env.qlib / "STAGED_MARKER.txt").exists() and _publish_state_of(env.qlib) == "ready"
+    assert f'provider_build_id: "{env.new_pb}"' in env.a1.read_text(encoding="utf-8")
+
+
+def _selective_write_fault(monkeypatch, should_fail):
+    """Patch mcb._atomic_write_bytes with a predicate-driven fault injector; all other
+    writes pass through to the real implementation."""
+    real = mcb._atomic_write_bytes
+
+    def fake(path, data):
+        if should_fail(Path(path), data):
+            raise OSError("injected write fault")
+        real(path, data)
+
+    monkeypatch.setattr(mcb, "_atomic_write_bytes", fake)
+
+
+def test_publish_rolls_back_when_rebind_write_fails_midway(tmp_path, monkeypatch):
+    # GPT Blocker 2 probe: fail the SECOND approval write mid-rebind. The caller holds
+    # every original (pure planner), restores + VERIFIES, rolls the swap back -> exit 4
+    # with byte-identical approvals and the parent live again.
+    env = _publish_env(tmp_path, monkeypatch)
+    seen: list[Path] = []
+
+    def fail_second_approval(path, _data):
+        if path.parent == env.root / "approvals" and path.suffix == ".yaml":
+            seen.append(path)
+            return len(seen) == 2
+        return False
+
+    _selective_write_fault(monkeypatch, fail_second_approval)
+    assert mcb.phase_publish(_PubArgs()) == 4
+    assert env.a1.read_bytes() == env.a1_bytes and env.a2.read_bytes() == env.a2_bytes
+    assert (env.qlib / "LIVE_MARKER.txt").exists()
+    assert mcb.live_provider_ids() == (env.parent_pb, env.parent_cp)
+    assert not list((env.root / "approvals").glob("*_rebind_to_*.md"))
+
+
+def test_publish_reports_5_when_restore_also_fails(tmp_path, monkeypatch):
+    # GPT Blocker 2 probe (double fault): a1 is rebound, a2's write fails (triggering the
+    # rollback), and then RESTORING a1 also fails — the transaction must NOT claim a
+    # verified rollback (the old code returned exit 4 with a half-rebound approvals dir);
+    # exit 5 with the journal naming the inconsistent file.
+    env = _publish_env(tmp_path, monkeypatch)
+    a1_writes: dict[str, int] = {}
+
+    def fault(path, _data):
+        if path.name == "a2.yaml":
+            return True  # rebind write of a2 fails -> handler engages with written=[a1]
+        if path.name == "a1.yaml":
+            a1_writes["n"] = a1_writes.get("n", 0) + 1
+            return a1_writes["n"] == 2  # 1st = rebind OK, 2nd = the RESTORE fails
+        return False
+
+    _selective_write_fault(monkeypatch, fault)
+    assert mcb.phase_publish(_PubArgs()) == 5
+    steps = _json.loads((env.out / "publish_transaction_journal.json").read_text(encoding="utf-8"))["steps"]
+    bad = [s for s in steps if s["status"] == "failed_rollback_incomplete"]
+    assert bad and any("a1.yaml" in p for p in bad[0]["problems"])
+
+
+def test_publish_rolls_back_when_record_write_fails(tmp_path, monkeypatch):
+    # GPT Blocker 2b probe: the publish-record write fails AFTER the rebind — everything
+    # (approvals, provider, state marker, record artifacts) must be restored; the
+    # governance rebind md is written LAST so no false 'completed rebind' record survives.
+    env = _publish_env(tmp_path, monkeypatch)
+    _selective_write_fault(monkeypatch, lambda p, _d: p.name == "publish_record.json")
+    assert mcb.phase_publish(_PubArgs()) == 4
+    assert env.a1.read_bytes() == env.a1_bytes and env.a2.read_bytes() == env.a2_bytes
+    assert (env.qlib / "LIVE_MARKER.txt").exists()
+    assert not list((env.root / "approvals").glob("*_rebind_to_*.md")), \
+        "a false 'successful rebind' governance record must not survive the rollback"
+    assert not (env.staged / "metadata" / "publish_state.json").exists()
+    assert not (env.out / "publish_record.json").exists()
+
+
+def test_publish_refuses_deleted_approvals(tmp_path, monkeypatch):
+    # GPT Blocker 3 probe: deleting bound approval YAMLs between execute and publish
+    # previously published with `approvals_rebound: 0`. The pinned governance-set
+    # attestation now refuses — including the delete-ALL case.
+    env = _publish_env(tmp_path, monkeypatch)
+    env.a2.unlink()
+    assert mcb.phase_publish(_PubArgs()) == 2
+    env.a1.unlink()
+    (env.root / "approvals" / "exempt.yaml").unlink()
+    assert mcb.phase_publish(_PubArgs()) == 2
+    assert (env.qlib / "LIVE_MARKER.txt").exists() and (env.staged / "STAGED_MARKER.txt").exists()
+
+
+def test_publish_refuses_added_approval(tmp_path, monkeypatch):
+    # The set pin is two-sided: an approval ADDED after the review also refuses (it would
+    # be silently rebound without ever having been part of the reviewed report).
+    env = _publish_env(tmp_path, monkeypatch)
+    (env.root / "approvals" / "a3_new.yaml").write_text(
+        f"approval_id: a3\ndataset_id: d3\nto_status: approved\ndate: '2026-07-10'\n"
+        f"provider_build_id: {env.parent_pb}\ncalendar_policy_id: {env.parent_cp}\n",
+        encoding="utf-8")
+    assert mcb.phase_publish(_PubArgs()) == 2
+    _assert_untouched(env)
+
+
+def test_publish_refuses_feature_bin_mutation(tmp_path, monkeypatch):
+    # GPT Blocker 4 probe: mutate a feature BIN's bytes (same size) after the audited
+    # build — the FULL-CONTENT re-attestation must refuse to publish the changed bytes.
+    env = _publish_env(tmp_path, monkeypatch)
+    env.staged_bin.write_bytes(b"\x09\x09\x09\x09")  # same size, different content
+    assert mcb.phase_publish(_PubArgs()) == 2
+    _assert_untouched(env)
+
+
+def test_publish_refuses_git_state_drift(tmp_path, monkeypatch):
+    # GPT Major 2 probe: code moved between execute and publish — the manifest would
+    # misattribute the build; refuse.
+    env = _publish_env(tmp_path, monkeypatch)
+    monkeypatch.setattr(mcb, "_git_state", lambda: ("othersha", "clean"))
+    assert mcb.phase_publish(_PubArgs()) == 2
+    _assert_untouched(env)
+
+
+def test_publish_refuses_policy_file_drift(tmp_path, monkeypatch):
+    # GPT Major 1 probe: the minted policy FILE (not just a few fields) is pinned by
+    # hash — any edit refuses.
+    env = _publish_env(tmp_path, monkeypatch)
+    env.policy_file.write_text(
+        env.policy_file.read_text(encoding="utf-8") + "\n# edited\n", encoding="utf-8")
+    assert mcb.phase_publish(_PubArgs()) == 2
+    _assert_untouched(env)
+
+
+def test_builder_publish_acquires_global_lock(tmp_path, monkeypatch):
+    # GPT Blocker 7: the publish LOCK lives at the common chokepoint — a bare
+    # StagedQlibBackendBuilder.publish() (any entrypoint) acquires it, and the singleton
+    # FileLock makes the monthly transaction's nested acquisition reentrant (the happy-path
+    # test exercises the nesting for real).
+    import data_infra.tushare_lock as tl
+    from data_infra.pit_backend import StagedQlibBackendBuilder
+
+    entered = []
+    from contextlib import contextmanager
+
+    @contextmanager
+    def recording(timeout: float = 7200.0):
+        entered.append(timeout)
+        yield
+
+    monkeypatch.setattr(tl, "provider_publish_lock", recording)
+    data = tmp_path / "data"
+    staged = data / "qlib_builds" / "lockprobe" / "provider"
+    staged.mkdir(parents=True)
+    (staged / "x.txt").write_text("x", encoding="utf-8")
+    b = StagedQlibBackendBuilder(data_root=str(data), qlib_dir=str(data / "qlib_data"),
+                                 build_id="lockprobe")
+    b.publish(calendar_policy_id="frozen_20260701_thaw_step1", emit_manifest=False)
+    assert entered, "publish() must acquire the global provider-publish lock"
diff --git a/tests/research_orchestrator/test_provider_raw_attestation_gate.py b/tests/research_orchestrator/test_provider_raw_attestation_gate.py
index 2246915..82a0641 100644
--- a/tests/research_orchestrator/test_provider_raw_attestation_gate.py
+++ b/tests/research_orchestrator/test_provider_raw_attestation_gate.py
@@ -72,11 +72,16 @@ def _manifest(**overrides) -> ProviderManifest:
 def test_policy_flag_defaults_false_and_parses_strict_bool():
     assert _policy(require=False).require_raw_input_attestation is False
     assert _policy(require=True).require_raw_input_attestation is True
-    # strict bool: a YAML string "true" must NOT enable enforcement silently … but it
-    # must not DISABLE fail-closed either — the gate treats only `is True` as required,
-    # mirroring the binding_exempt discipline.
-    sneaky = _policy(require=False, require_raw_input_attestation="true")
-    assert sneaky.require_raw_input_attestation is False
+
+
+def test_policy_flag_non_bool_fails_closed():
+    # GPT re-review Major 1: a truthy-but-non-bool value (the quoted YAML string "true")
+    # previously read as False — silently DISABLING a load-bearing enforcement flag. It
+    # must refuse to load instead.
+    from src.research_orchestrator.calendar_policy import CalendarPolicyError
+    for bad in ("true", 1, "yes"):
+        with pytest.raises(CalendarPolicyError, match="require_raw_input_attestation"):
+            _policy(require=False, require_raw_input_attestation=bad)
 
 
 # ── the gate itself ──────────────────────────────────────────────────────────
@@ -119,15 +124,24 @@ def _wire_runtime_validation(tmp_path, monkeypatch, policy):
     (tmp_path / "calendars" / "day.txt").write_text("2008-01-02\n2099-01-01\n", encoding="utf-8")
 
 
+def _write_state(tmp_path, state: str, build_id: str = "thaw_20990101_120000") -> None:
+    import json
+    meta = tmp_path / "metadata"
+    meta.mkdir(parents=True, exist_ok=True)
+    (meta / "publish_state.json").write_text(
+        json.dumps({"state": state, "provider_build_id": build_id}), encoding="utf-8")
+
+
 def test_formal_runtime_validation_enforces_attestation(tmp_path, monkeypatch):
     from src.backtest_engine.event_driven import _validate_provider_at_runtime
 
     _wire_runtime_validation(tmp_path, monkeypatch, _policy(require=True))
+    _write_state(tmp_path, "ready")
     with pytest.raises(ProviderAttestationError, match="raw_input_manifest_root"):
         _validate_provider_at_runtime(
             manifest=_manifest(), calendar_policy_id="frozen_20990101_thaw_stepN",
             run_mode="formal", qlib_dir=tmp_path)
-    # same run with an attested manifest passes
+    # same run with an attested manifest + ready state passes
     _validate_provider_at_runtime(
         manifest=_manifest(raw_input_manifest_root=_ROOT, parent_provider_build_id="p"),
         calendar_policy_id="frozen_20990101_thaw_stepN", run_mode="formal", qlib_dir=tmp_path)
@@ -140,3 +154,89 @@ def test_formal_runtime_validation_legacy_policy_unaffected(tmp_path, monkeypatc
     _validate_provider_at_runtime(
         manifest=_manifest(), calendar_policy_id="frozen_20990101_thaw_stepN",
         run_mode="formal", qlib_dir=tmp_path)
+
+
+# ── publish-state (QA quarantine) gate — GPT re-review Blocker 6 ─────────────
+def test_publish_state_gate_quarantines_until_ready(tmp_path):
+    from src.research_orchestrator.release_gate import (
+        assert_provider_publish_state,
+        evaluate_provider_publish_state,
+    )
+    flagged, legacy = _policy(require=True), _policy(require=False)
+    m = _manifest(raw_input_manifest_root=_ROOT)
+    # required + ABSENT marker -> refuse (the build skipped the attested transaction)
+    assert not evaluate_provider_publish_state(qlib_dir=tmp_path, policy=flagged, manifest=m).eligible
+    # legacy + absent -> eligible (pre-5B providers never had one)
+    assert evaluate_provider_publish_state(qlib_dir=tmp_path, policy=legacy, manifest=m).eligible
+    # a PRESENT non-ready marker quarantines EVEN under a legacy policy
+    _write_state(tmp_path, "pending_qa")
+    for pol in (flagged, legacy):
+        with pytest.raises(ProviderAttestationError, match="pending_qa"):
+            assert_provider_publish_state(qlib_dir=tmp_path, policy=pol, manifest=m)
+    _write_state(tmp_path, "qa_failed")
+    assert not evaluate_provider_publish_state(qlib_dir=tmp_path, policy=flagged, manifest=m).eligible
+    _write_state(tmp_path, "ready")
+    assert evaluate_provider_publish_state(qlib_dir=tmp_path, policy=flagged, manifest=m).eligible
+    # a marker naming a DIFFERENT build is stale/foreign -> refuse
+    _write_state(tmp_path, "ready", build_id="someone_else")
+    assert not evaluate_provider_publish_state(qlib_dir=tmp_path, policy=flagged, manifest=m).eligible
+
+
+def test_formal_runtime_validation_refuses_quarantined_provider(tmp_path, monkeypatch):
+    from src.backtest_engine.event_driven import _validate_provider_at_runtime
+
+    _wire_runtime_validation(tmp_path, monkeypatch, _policy(require=True))
+    _write_state(tmp_path, "qa_failed")
+    with pytest.raises(ProviderAttestationError, match="qa_failed"):
+        _validate_provider_at_runtime(
+            manifest=_manifest(raw_input_manifest_root=_ROOT, parent_provider_build_id="p"),
+            calendar_policy_id="frozen_20990101_thaw_stepN", run_mode="formal", qlib_dir=tmp_path)
+
+
+# ── provider_context chokepoint — GPT re-review Blocker 5 ────────────────────
+def _wire_provider_context(tmp_path, monkeypatch, policy):
+    """Point the shared live-provider resolution (every sanctioned data door) at a tmp
+    provider + injected policy."""
+    import json
+    from src.data_infra import provider_context as pc
+    from src.research_orchestrator import calendar_policy as cp
+
+    (tmp_path / "calendars").mkdir(parents=True, exist_ok=True)
+    (tmp_path / "calendars" / "day.txt").write_text("2008-01-02\n2099-01-01\n", encoding="utf-8")
+
+    def write_manifest(**overrides):
+        payload = _manifest(**overrides).to_dict()
+        meta = tmp_path / "metadata"
+        meta.mkdir(parents=True, exist_ok=True)
+        (meta / "provider_build.json").write_text(json.dumps(payload), encoding="utf-8")
+
+    monkeypatch.setattr(pc, "_qlib_dir", lambda: tmp_path)
+    monkeypatch.setattr(cp, "load_calendar_policy", lambda pid, root=None: policy)
+    pc.refresh_live_provider_context()
+    return pc, write_manifest
+
+
+def test_provider_context_enforces_attestation_and_state(tmp_path, monkeypatch):
+    # The formal Qlib read door (qlib_windowed_features) and the sandbox loader BOTH
+    # resolve through provider_context._resolve — an unattested or quarantined provider
+    # must refuse there, not only at the event-driven runtime validator.
+    pc, write_manifest = _wire_provider_context(tmp_path, monkeypatch, _policy(require=True))
+    write_manifest()  # no raw_input_manifest_root
+    with pytest.raises(pc.ProviderContextError, match="raw_input_manifest_root"):
+        pc.live_provider_ids()
+    write_manifest(raw_input_manifest_root=_ROOT, parent_provider_build_id="p")
+    with pytest.raises(pc.ProviderContextError, match="publish-state|publish_state"):
+        pc.live_provider_ids()  # attested but NO marker -> still refused
+    _write_state(tmp_path, "pending_qa")
+    with pytest.raises(pc.ProviderContextError, match="pending_qa"):
+        pc.live_provider_ids()
+    _write_state(tmp_path, "ready")
+    build, policy_id = pc.live_provider_ids()  # the state flip re-keys the cache — no stale verdict
+    assert build == "thaw_20990101_120000" and policy_id == "frozen_20990101_thaw_stepN"
+
+
+def test_provider_context_legacy_policy_still_resolves(tmp_path, monkeypatch):
+    pc, write_manifest = _wire_provider_context(tmp_path, monkeypatch, _policy(require=False))
+    write_manifest()
+    build, _ = pc.live_provider_ids()
+    assert build == "thaw_20990101_120000"
```

RE-REVIEW QUESTIONS
1. Re-run your seven probes against the new code: does ANY still reproduce? For each, state pass/fail explicitly.
2. NEW holes opened by the fixes: (a) the pure-plan rebind — plan computed pre-swap on attested bytes, written post-swap under the same locks: any interleaving that invalidates the plan? (b) the rollback handler's artifact deletions (record md, publish record, new-tree provider_build.json/publish_state.json) — can a deletion failure leave a state worse than the old behavior? (c) the non-raising journal — does making it a breadcrumb hide any failure that MUST abort?
3. The publish-state quarantine: is the legacy-policy semantics right (absent marker allowed for legacy, present non-ready marker always refuses)? Is the marker's placement INSIDE the provider tree (travels with swap/rollback/.bak) correct, or should it live outside the tree?
4. The singleton lock at the chokepoint: any deadlock path given the documented order (raw -> publish; publish-only holders never take raw afterwards)? Any caller of publish()/emitters that could now block behind a long transaction in a way that breaks something?
5. provider_context gating BOTH doors (sandbox included) during pending_qa/qa_failed windows: acceptable, or must the sandbox door stay open?
6. The full-content staged attestation: implementation correct (determinism, thread-pool hashing, grouping, the build-manifest inclusion, the pre-attestation placement of metadata/raw_input_manifest.json)? Is the disclosed cost acceptable, and is the sidecar retention (per-build under workspace outputs + in-tree copy) the right audit store?
7. Explicit accept/reject on the remaining limits: L2 (trusted-operator report tampering) and L3 (first real 241GB run still pending, separately §13-gated — name the preflight you require for it).
8. Anything in the docs (CLAUDE 3.4 bullets, UNFREEZE_PLAN rewrites) that misstates the implemented behavior?

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending line quoted and an exact suggested replacement.
- Explicit per-probe pass/fail table for your original seven probes.
- Final line: SHIP / REVISE / REWORK, plus the single most important residual risk.
```
