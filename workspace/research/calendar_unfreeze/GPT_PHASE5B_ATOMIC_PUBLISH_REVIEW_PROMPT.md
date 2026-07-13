# GPT 5.5 Pro cross-review — Phase 5-B B3: atomic monthly provider publish transaction

> Send verbatim to GPT 5.5 Pro. Branch is pushed; every raw link resolves. Pinned HEAD: `333f5a9`
> (diff below covers the two substantive commits `381a52d` feat + `b41cb15` test; `246ed7c` is the
> 2026-07-04 manual-rebind paper-trail import, `333f5a9` the docs mirror).

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. A single lookahead, a spent out-of-sample window, or a survivorship-filtered universe invalidates the result even if every test passes. Be skeptical, surface blockers, and do not rubber-stamp. This change touches the MOST LOAD-BEARING artifact in the system: the transaction that replaces the live 241GB Qlib provider and rewrites the field-approval governance bindings.

REPO (public — fetch any file to verify against the live code)
https://github.com/henrydan111/quant-system   (branch: calendar-unfreeze-phase5b-atomic-publish)
Raw file form: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/<path>

CONTEXT — read these to judge the change against the contract:
- CLAUDE.md (hard invariants §3.4 incl. the two NEW bullets this change adds; §13 risky actions)
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/CLAUDE.md
- The driver (the transaction lives in phase_publish; attestations pinned in _build_impl):
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/scripts/monthly_calendar_bump.py
- The swap primitive (StagedQlibBackendBuilder.publish, ~line 4595) + manifest emission:
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/src/data_infra/pit_backend.py
- Locks: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/src/data_infra/tushare_lock.py
- Manifest loader/emitter: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/src/data_infra/provider_manifest.py
- Schema: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/schemas/provider_build.schema.json
- Policy loader (new flag): https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/src/research_orchestrator/calendar_policy.py
- Release gate (new attestation gate): https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/src/research_orchestrator/release_gate.py
- Formal-run chokepoint wiring (_validate_provider_at_runtime): https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/src/backtest_engine/event_driven/__init__.py
- Approval-binding machinery the rebind must satisfy: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/src/data_infra/approval_evidence.py
- Tests: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/tests/data_infra/test_monthly_calendar_bump.py
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/tests/research_orchestrator/test_provider_raw_attestation_gate.py
  https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/tests/data_infra/test_provider_manifest.py
- Structured self-review (fix log + 5 disclosed limits): https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/workspace/research/calendar_unfreeze/PHASE5B_ATOMIC_PUBLISH_SELF_REVIEW.md
- Prior round (your REWORK-5 verdict that mandated this): https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze-phase5b-atomic-publish/workspace/research/calendar_unfreeze/PHASE5C_SELF_REVIEW.md (round 7, "B3 残留")

BACKGROUND — what you (GPT) ruled in REWORK-5 and what this implements
Your REWORK-5 B3 finding: the monthly publish had a fail-closed verification GATE (parent compare-and-swap + full-readset raw-input manifest re-hash) followed by a MANUAL swap+rebind interval — and "a manual interval after verification cannot be the integrity boundary". The user deferred the fix to a dedicated Phase 5-B task (no staged build existed to integration-test then). This change is that task:
  B3.3-5: phase_publish now IS the publish — one lock scope (raw_maintenance_lock -> NEW provider_publish_lock, fixed order), verify EVERYTHING immediately before the swap, swap via the proven StagedQlibBackendBuilder.publish 3-rename primitive, re-load + verify the live manifest, byte-preserving two-phase rebind of all ~25 bound approval YAMLs with exact-token per-file CAS, 0-drift assertion, committed rebind record, publish record, step journal. Any post-swap failure restores approval bytes AND rolls the swap back (reverse 3-rename) — exit 4; rollback failure -> exit 5 with journal-guided recovery; run_daily_qa runs OUTSIDE the locks afterwards — failure = exit 6 (published state kept, parent retained as .bak).
  B3.2: the published provider_build.json now carries raw_input_manifest_root (sha256 root of the full-readset raw cut; 64-hex validated fail-closed in the loader) + parent_provider_build_id. Both OPTIONAL in schema/loader (the CURRENT live provider predates them and must keep loading). Enforcement rolls FORWARD via a policy flag: CalendarPolicy.require_raw_input_attestation (strict bool, default False; generate_thaw_policy mints every new policy with true), enforced at the formal-run chokepoint (_validate_provider_at_runtime -> release_gate.assert_provider_raw_attestation). Legacy policies skip, so the current live thaw_step1 provider keeps serving formal runs until the next bump-published provider takes over.
Also in this branch: the uncommitted 2026-07-04 manual thaw_step1 rebind of the 25 approval YAMLs was imported as a paper-trail commit (the transaction's approvals-CAS refuses to run until committed bindings match the live parent), and an execute-phase early approvals-CAS refuses a stale binding BEFORE the multi-hour build.

SELF-REVIEW PREFLIGHT — completed before this GPT request: verdict "clean for GPT"; checked §3 invariants + each quantitative-research principle in the canonical template. Fixes made during self-review: CRLF-corrupting regex group in the rebind token substitution; BuildGateError wrongly included in the transient-retry set (now OSError-only, live-missing never retried); ApprovalEvidenceConfigError could escape as a raw traceback (now a clean refusal); a QA-branch builder re-construction; the tests/research_orchestrator/__init__.py namespace landmine (pytest binds the PLAIN top-level name research_orchestrator to the TESTS package, poisoning bare-namespace imports — the script now imports via the src.-prefix). Residual concerns for reviewer: the 5 disclosed limits below.

DISCLOSED LIMITS (be explicit about whether each is acceptable)
L1. Staged attestation depth: between execute (audits) and publish, only the staged tree's IDENTITY files are re-hashed (calendars/day.txt, instruments/*.txt, build manifest.json — full content sha256 — plus the features top-level dir count). The 241GB features/*.bin content is NOT re-hashed at publish (a full re-hash costs about a rebuild); it is attested by the execute-time frozen-prefix + fresh-window audits, and the staged dir is a build-id-scoped path no other process writes.
L2. The dry-run report is the operator's own review vehicle: an operator who edits report+artifacts consistently is not stopped (threat model = out-of-band processes/drift, not a malicious operator).
L3. End-to-end execution against a REAL 241GB staged build has NOT run (no staged build exists this session; §13 requires user confirmation). The transaction is exercised end-to-end on synthetic staged/live trees with real renames, real manifest emission, real YAML rewrites (23 new tests, all green; 1049 green across the 4 combined suites, remaining failures classified as worktree-missing-live-data with main-tree cross-checks).
L4. Exit 6 (QA failure post-publish) does NOT roll back: QA runs outside the locks after a consistent swap+rebind+metadata; a QA failure may be unrelated to the publish, and rolling back a consistent publish introduces new failure modes (Windows handle locks on fresh trees). Parent retained as .bak (one rename from restore).
L5. UNFREEZE_PLAN.md still describes the manual "_depth9_safe_publish.py" step; the plan doc is the shipped design record — its revision is proposed to ride with your verdict rather than being edited unilaterally.

WHAT CHANGED (authoritative — treat the embedded diff as the source of truth; the links cross-check the surrounding code). Diff = commits 381a52d (feat) + b41cb15 (test) against the branch base:

```diff
diff --git a/schemas/provider_build.schema.json b/schemas/provider_build.schema.json
index 54bd362..a66257b 100644
--- a/schemas/provider_build.schema.json
+++ b/schemas/provider_build.schema.json
@@ -108,6 +108,16 @@
       "type": "array",
       "items": {"type": "string"},
       "description": "When retroactive_manifest is true, list the evidence sources (e.g., 'README status snapshot', 'project_state downstream revalidation note', 'tests/data_infra/test_event_like_daily_namespace.py output', 'provider field inventory hash'). Required when retroactive_manifest is true."
+    },
+    "raw_input_manifest_root": {
+      "type": ["string", "null"],
+      "pattern": "^[0-9a-f]{64}$",
+      "description": "Phase 5-B (calendar unfreeze, B3.2): sha256 root of the full-readset raw-input manifest the staged build consumed (workspace/outputs/calendar_unfreeze/raw_input_manifest.json sidecar carries the per-file hashes). Binds provider_build_id -> the attested raw cut. OPTIONAL: pre-thaw builds lack it and must keep loading; presence for formal runs is enforced by the release gate when the calendar policy sets require_raw_input_attestation."
+    },
+    "parent_provider_build_id": {
+      "type": ["string", "null"],
+      "minLength": 1,
+      "description": "Phase 5-B: the provider_build_id this build was verified against and atomically replaced (the monthly bump's parent compare-and-swap anchor). OPTIONAL for pre-thaw builds."
     }
   },
   "allOf": [
diff --git a/scripts/monthly_calendar_bump.py b/scripts/monthly_calendar_bump.py
index a94ad58..13d7bb1 100644
--- a/scripts/monthly_calendar_bump.py
+++ b/scripts/monthly_calendar_bump.py
@@ -8,9 +8,13 @@ UNFREEZE_PLAN.md Phase 5-B (GPT §10 SHIP). Three modes:
   (default execute) Catch up raw -> new policy YAML -> full rebuild (staged) -> frozen-prefix
                     audit + FRESH-WINDOW SURVIVORSHIP audit -> dry-run report. STOPS before
                     publish (prints the --publish-approved instruction).
-  --publish-approved  The publish leg (only after a human reviewed the dry-run report):
-                    safe atomic swap -> approvals rebind -> post-publish QA -> parent-build
-                    metadata. §13 risk action — NEVER in the automated flow.
+  --publish-approved  The ATOMIC publish transaction (Phase 5-B B3; only after a human
+                    reviewed the dry-run report): under raw+publish locks, re-verify
+                    parent CAS + raw manifest + audit/staged attestations IMMEDIATELY
+                    before the safe staged-first swap, emit provider_build.json with
+                    raw_input_manifest_root + parent binding, rebind the approval YAMLs
+                    (rollback-on-failure), then post-publish QA. §13 risk action —
+                    human-invoked only, NEVER in the automated flow.
 
 Design invariants honored:
   - spent_oos_end STAYS 2026-02-27 across every bump (D3 §6); only calendar_end advances,
@@ -42,10 +46,16 @@ import yaml
 
 PROJECT_ROOT = Path(__file__).resolve().parents[1]
 sys.path.insert(0, str(PROJECT_ROOT / "src"))
+# ROOT itself is needed for the `src.`-prefixed import form. research_orchestrator MUST be
+# imported as `src.research_orchestrator...` here: the plain top-level name is shadowed in
+# any pytest process that collects tests/research_orchestrator/ (that dir has an
+# __init__.py, so pytest binds sys.modules['research_orchestrator'] to the TESTS package).
+sys.path.insert(0, str(PROJECT_ROOT))
 
 SPENT_OOS_END = "2026-02-27"        # D3 §6: FROZEN across every bump
 FRESH_HOLDOUT_START = "2026-02-28"  # must equal REPORT_RC_FRESH_HOLDOUT_START
 POLICY_DIR = PROJECT_ROOT / "config" / "calendar_policies"
+APPROVALS_DIR = PROJECT_ROOT / "config" / "field_registry" / "approvals"
 OUT_DIR = PROJECT_ROOT / "workspace" / "outputs" / "calendar_unfreeze"
 
 logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s",
@@ -144,6 +154,10 @@ def generate_thaw_policy(target_end: str, parent_build_id: str, *, write: bool)
         "frozen": True, "reason": f"thaw_step{step}_monthly_freeze_bump",
         "established_at": end_iso,
         "spent_oos_end": SPENT_OOS_END, "fresh_holdout_start": FRESH_HOLDOUT_START,
+        # Phase 5-B B3.2: every bump-minted policy makes the raw-input attestation
+        # LOAD-BEARING — formal runs under it require the live provider_build.json to
+        # carry raw_input_manifest_root (release_gate.assert_provider_raw_attestation).
+        "require_raw_input_attestation": True,
         "allowed_modes": ["sandbox", "joinquant_replication", "formal_research_with_explicit_freeze",
                           "joinquant_daily", "joinquant_open_close_replica", "formal", "oos_test"],
         "default_formal_behavior": "require_explicit_policy",
@@ -392,6 +406,236 @@ def _verify_raw_manifest(manifest: dict, data_root=None) -> tuple[bool, str]:
     return True, "ok"
 
 
+# ── Phase 5-B B3.3-5: atomic publish transaction helpers ─────────────────────
+class PublishTransactionError(RuntimeError):
+    """A publish-transaction invariant failed (fail closed; nothing durable mutated
+    unless the message says otherwise)."""
+
+
+def _atomic_write_bytes(path: Path, data: bytes) -> None:
+    import tempfile
+    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
+    try:
+        with os.fdopen(fd, "wb") as fh:
+            fh.write(data)
+        os.replace(tmp, str(path))
+    finally:
+        if os.path.exists(tmp):
+            os.remove(tmp)
+
+
+def _staged_attestation(staged_provider) -> dict:
+    """Cheap tamper-evidence over the staged provider's IDENTITY-bearing small files:
+    calendars/day.txt + every instruments/*.txt (full content SHA-256) + the build
+    manifest.json at <build_root>/manifest.json + the features top-level dir count.
+    Recomputed at publish and compared to the execute-time root, so a staged tree whose
+    calendar/universe/build-record moved between the audited build and the swap refuses.
+    DELIBERATE LIMIT (disclosed): the 241GB features/*.bin content is attested by the
+    execute-time frozen-prefix + fresh-window audits, not re-hashed here — a full
+    content re-hash at publish would take longer than the build itself."""
+    prov = Path(staged_provider)
+    comp: dict = {}
+    cal = prov / "calendars" / "day.txt"
+    comp["calendars/day.txt"] = _sha256_file(cal) if cal.is_file() else "MISSING"
+    inst = prov / "instruments"
+    if inst.is_dir():
+        for p in sorted(inst.glob("*.txt")):
+            comp[f"instruments/{p.name}"] = _sha256_file(p)
+    else:
+        comp["instruments"] = "MISSING"
+    build_manifest = prov.parent / "manifest.json"
+    comp["build_manifest.json"] = _sha256_file(build_manifest) if build_manifest.is_file() else "MISSING"
+    feats = prov / "features"
+    comp["features_top_level_dir_count"] = (
+        sum(1 for p in feats.iterdir() if p.is_dir()) if feats.is_dir() else 0
+    )
+    import hashlib
+    root = hashlib.sha256(json.dumps(comp, sort_keys=True).encode("utf-8")).hexdigest()
+    return {"algo": "sha256", "root": root, "components": comp}
+
+
+def _approvals_all_bound_to(pb: str, cp: str) -> tuple[bool, str]:
+    """Approvals compare-and-swap precondition: every NON-exempt approval YAML must be
+    bound to exactly the parent (pb, cp) so the post-swap rebind is a clean two-token
+    rewrite. Any other binding means an approval was added/rebound out-of-band since
+    the report — refuse (fail closed). Uses the strict governance loader, so a
+    malformed approval also refuses here."""
+    from data_infra.approval_evidence import ApprovalEvidenceConfigError, load_approval_bindings
+    try:
+        bindings = load_approval_bindings(APPROVALS_DIR)
+    except ApprovalEvidenceConfigError as exc:
+        return False, f"approvals directory fails the governance loader: {exc}"
+    bad = [b for b in bindings
+           if b.declared_provider_build_id != pb or b.declared_calendar_policy_id != cp]
+    if bad:
+        detail = "; ".join(
+            f"{Path(b.approval_file).name}=({b.declared_provider_build_id}/"
+            f"{b.declared_calendar_policy_id})" for b in bad[:5])
+        return False, (f"{len(bad)}/{len(bindings)} approval YAML(s) are NOT bound to the "
+                       f"parent ({pb}/{cp}): {detail}")
+    return True, f"{len(bindings)} bound approval YAML(s) verified against the parent ids"
+
+
+def _sub_binding_token(data: bytes, key: str, old: str, new: str, path: Path) -> bytes:
+    """Replace the single `key: <old>` binding VALUE in a YAML's raw bytes, preserving
+    every other byte (quoting style, EOLs, comments). Requires exactly ONE such line —
+    zero or multiple means the file drifted from the loader-validated shape (refuse)."""
+    import re
+    pat = re.compile(
+        rb"(?m)^(" + key.encode("utf-8") + rb":[ \t]*)([\"']?)"
+        + re.escape(old.encode("utf-8")) + rb"([\"']?)([ \t]*\r?)$"
+    )
+    hits = pat.findall(data)
+    if len(hits) != 1:
+        raise PublishTransactionError(
+            f"{path.name}: expected exactly 1 '{key}: {old}' binding line, found {len(hits)} "
+            "— the file drifted from its loader-validated shape; refusing the rebind."
+        )
+    return pat.sub(rb"\g<1>\g<2>" + new.encode("utf-8") + rb"\g<3>\g<4>", data, count=1)
+
+
+def _rebind_approval_files(old_pb: str, old_cp: str, new_pb: str, new_cp: str,
+                           ) -> tuple[list[Path], dict[Path, bytes]]:
+    """Two-phase byte-preserving rebind of every bound approval YAML (mirrors the
+    _rebind_approvals_depth9/thaw precedents, generalized). Phase 1 plans EVERY
+    substitution in memory and re-parses each result (the rebound YAML must parse to
+    exactly the new ids) — any failure writes NOTHING. Phase 2 writes atomically
+    per-file and restores already-written files if a write fails, then re-raises.
+    Returns (changed_paths, originals) so the caller can restore on later failures."""
+    from data_infra.approval_evidence import load_approval_bindings
+    bindings = load_approval_bindings(APPROVALS_DIR)
+    plan: list[tuple[Path, bytes]] = []
+    originals: dict[Path, bytes] = {}
+    for b in bindings:
+        p = Path(b.approval_file)
+        data = p.read_bytes()
+        nd = _sub_binding_token(data, "provider_build_id", old_pb, new_pb, p)
+        nd = _sub_binding_token(nd, "calendar_policy_id", old_cp, new_cp, p)
+        parsed = yaml.safe_load(nd.decode("utf-8"))
+        if (not isinstance(parsed, dict) or parsed.get("provider_build_id") != new_pb
+                or parsed.get("calendar_policy_id") != new_cp):
+            raise PublishTransactionError(
+                f"{p.name}: rebound YAML does not parse back to the new ids — refusing."
+            )
+        originals[p] = data
+        plan.append((p, nd))
+    written: list[Path] = []
+    try:
+        for p, nd in plan:
+            _atomic_write_bytes(p, nd)
+            written.append(p)
+    except Exception:
+        for p in written:
+            _atomic_write_bytes(p, originals[p])
+        raise
+    return [p for p, _ in plan], originals
+
+
+def _restore_approval_files(originals: dict[Path, bytes]) -> None:
+    for p, data in originals.items():
+        _atomic_write_bytes(p, data)
+
+
+def _make_publish_builder(staged_build_id: str):
+    """Builder handle for the proven safe staged-first swap primitive
+    (StagedQlibBackendBuilder.publish). Tests inject a tmp-rooted builder here."""
+    from data_infra.pit_backend import StagedQlibBackendBuilder
+    return StagedQlibBackendBuilder(build_id=staged_build_id)
+
+
+def _rollback_swap(builder) -> tuple[bool, str]:
+    """Best-effort inverse of StagedQlibBackendBuilder.publish(): NEW live -> adjacent,
+    backup -> live (parent restored), NEW tree -> back to the staged provider_dir.
+    Returns (live_restored, message). Only the middle rename is CRITICAL — after it the
+    parent provider is live again; a stranded NEW tree is loudly named, never silent."""
+    qlib = str(builder.paths.qlib_dir)
+    bak = f"{qlib}.bak_{builder.build_id}"
+    staging = f"{qlib}.new_{builder.build_id}"
+    if not os.path.isdir(bak):
+        return False, f"cannot roll back: parent backup missing at {bak}"
+    if os.path.exists(staging):
+        return False, f"cannot roll back: stale {staging} exists — resolve manually"
+    try:
+        os.replace(qlib, staging)  # NEW live -> adjacent (parent still safe in bak)
+    except OSError as exc:
+        return False, f"rollback live->staging rename failed ({exc}); the NEW build is still live"
+    try:
+        os.replace(bak, qlib)  # backup -> live: the CRITICAL restore
+    except OSError as exc:
+        return False, (f"CRITICAL: live provider MISSING — recover manually: move {bak!r} -> "
+                       f"{qlib!r} (the NEW build sits at {staging!r}); restore rename failed: {exc}")
+    try:
+        os.replace(staging, builder.paths.provider_dir)
+        note = "the NEW tree is back at the staged provider_dir for a clean retry"
+    except OSError:
+        note = (f"parent live restored; the NEW tree remains at {staging} — move it back to "
+                f"{builder.paths.provider_dir} before retrying")
+    return True, f"rolled back to the parent live provider; {note}"
+
+
+def _verify_live_manifest(qlib_dir, *, build_id: str, policy_id: str, raw_root: str,
+                          parent_pb: str) -> tuple[bool, str]:
+    """Post-swap check: the LIVE provider_build.json must attest exactly this
+    transaction (build id, policy, raw-input root, parent). Catches the emit path
+    failing silently (it is deliberately non-raising for legacy callers)."""
+    from data_infra.provider_manifest import ProviderManifestError, load_provider_manifest
+    try:
+        m = load_provider_manifest(qlib_dir)
+    except ProviderManifestError as exc:
+        return False, f"live manifest absent/unreadable after the swap: {exc}"
+    problems = []
+    if m.provider_build_id != build_id:
+        problems.append(f"provider_build_id={m.provider_build_id!r} != {build_id!r}")
+    if m.calendar_policy_id != policy_id:
+        problems.append(f"calendar_policy_id={m.calendar_policy_id!r} != {policy_id!r}")
+    if m.raw_input_manifest_root != raw_root:
+        problems.append(f"raw_input_manifest_root={m.raw_input_manifest_root!r} != {raw_root!r}")
+    if m.parent_provider_build_id != parent_pb:
+        problems.append(f"parent_provider_build_id={m.parent_provider_build_id!r} != {parent_pb!r}")
+    return (not problems), ("; ".join(problems) or "ok")
+
+
+def _write_journal(journal: dict) -> None:
+    OUT_DIR.mkdir(parents=True, exist_ok=True)
+    journal["updated_cst"] = now_cst().isoformat(timespec="seconds")
+    _atomic_write_bytes(TRANSACTION_JOURNAL_PATH,
+                        json.dumps(journal, ensure_ascii=False, indent=1).encode("utf-8"))
+
+
+def _run_post_publish_qa() -> int:
+    import subprocess
+    py = str(PROJECT_ROOT / "venv" / "Scripts" / "python.exe")
+    return subprocess.run([py, str(PROJECT_ROOT / "scripts" / "run_daily_qa.py")]).returncode
+
+
+def _write_rebind_record(*, new_pb: str, new_cp: str, old_pb: str, old_cp: str,
+                         n_files: int, raw_root: str, raw_files: int, backup_dir: str) -> Path:
+    """Committed governance record of the rebind (mirrors the 2026-07-01/2026-07-04
+    precedent .md files). Same-build-id retries overwrite their own record."""
+    date = now_cst().strftime("%Y-%m-%d")
+    path = APPROVALS_DIR / f"{date}_rebind_to_{new_pb}.md"
+    body = (
+        f"# Re-bind to the monthly thaw publish ({new_pb} / {new_cp})\n\n"
+        f"Written by the ATOMIC publish transaction (`scripts/monthly_calendar_bump.py "
+        f"--publish-approved`, Phase 5-B B3) on {now_cst().isoformat(timespec='seconds')}.\n\n"
+        f"{n_files} approval YAMLs re-bound on BOTH ids (provider `{old_pb}` -> `{new_pb}`; "
+        f"policy `{old_cp}` -> `{new_cp}`) inside the same lock scope as the swap: the parent "
+        f"compare-and-swap, the full-readset raw-input manifest re-hash (root `{raw_root}`, "
+        f"{raw_files} files), the audit-artifact hashes, and the staged attestation were all "
+        f"re-verified IMMEDIATELY before the safe staged-first swap "
+        f"(StagedQlibBackendBuilder.publish), under raw_maintenance_lock + "
+        f"provider_publish_lock.\n\n"
+        f"`raw_input_manifest_root` + `parent_provider_build_id` are bound into the published "
+        f"`data/qlib_data/metadata/provider_build.json`. "
+        f"`evaluate_approval_evidence_bindings()` -> 0 drift after the rebind. Prior live "
+        f"retained as `{backup_dir}` (one rename from restore). Transaction record: "
+        f"`workspace/outputs/calendar_unfreeze/publish_record.json`; journal: "
+        f"`publish_transaction_journal.json`.\n"
+    )
+    _atomic_write_bytes(path, body.encode("utf-8"))
+    return path
+
+
 def _prune_cyq_state(suffix: str) -> None:
     """On a post-catch-up completeness failure, drop the Stage-D cyq_perf resume keys from the
     catch-up state file so a rerun RE-FETCHES cyq (m1): a zero-row cyq fetch from a late endpoint
@@ -681,7 +925,8 @@ def phase_plan(args) -> dict:
 
 DRYRUN_REPORT_PATH = OUT_DIR / "monthly_bump_dryrun_report.json"
 FRESH_AUDIT_PATH = OUT_DIR / "fresh_window_survivorship_audit.json"
-PUBLISH_HANDOFF_PATH = OUT_DIR / "publish_handoff.json"
+PUBLISH_RECORD_PATH = OUT_DIR / "publish_record.json"
+TRANSACTION_JOURNAL_PATH = OUT_DIR / "publish_transaction_journal.json"
 RAW_MANIFEST_PATH = OUT_DIR / "raw_input_manifest.json"
 
 
@@ -723,7 +968,7 @@ def _phase_execute_impl(args) -> int:
     # policy must not be silently regressed. Route through the typed loader so the YAML-parsed
     # ISO dates are normalized to strings (a bare yaml.safe_load yields datetime.date objects,
     # which would false-fail a string compare) and the loader's own validation runs.
-    from research_orchestrator.calendar_policy import load_calendar_policy
+    from src.research_orchestrator.calendar_policy import load_calendar_policy
     parent_pol = load_calendar_policy(parent_policy)
     if parent_pol.spent_oos_end != SPENT_OOS_END:
         logger.error("parent policy spent_oos_end %s != Phase-5 constant %s — refusing",
@@ -735,6 +980,16 @@ def _phase_execute_impl(args) -> int:
         return 2
     parent_end = parent_pol.calendar_end_date.replace("-", "")
 
+    # Approvals compare-and-swap PRECONDITION (Phase 5-B): surface a stale/out-of-band
+    # approval binding BEFORE the multi-hour build, not at publish time. The publish
+    # transaction re-checks the same condition under its locks.
+    ok_bind, bind_msg = _approvals_all_bound_to(parent_build, parent_policy)
+    if not ok_bind:
+        logger.error("approval-binding precondition FAILED: %s — commit/repair the approval "
+                     "rebind to the live parent before bumping.", bind_msg)
+        return 2
+    logger.info("approval-binding precondition OK: %s", bind_msg)
+
     # B2: target_end via the multi-endpoint readiness contract; validate any override.
     ready_target, ev = determine_target_end(now_cst(), probe_ready=endpoint_ready)
     if args.target_end:
@@ -866,13 +1121,18 @@ def _build_impl(args, parent_build, parent_policy, parent_end, target_end) -> in
 
     # 4d. full-read-set raw-input manifest (Blocker 3) — computed here UNDER the lock, so it attests the
     # exact cut the staged build just consumed (EVERY DATASET_SPECS file + reference, not a 6-dataset
-    # subset). Sidecar carries the per-file hashes; the 256-bit root is recorded in the report +
-    # re-verified before publish + (manual step) bound into the published provider_build.json.
+    # subset). Sidecar carries the per-file hashes; the 256-bit root is recorded in the report, re-verified
+    # by the publish transaction under its locks, and bound into the published provider_build.json (B3.2).
     raw_manifest = _full_raw_manifest()
     RAW_MANIFEST_PATH.write_text(json.dumps(raw_manifest, ensure_ascii=False, indent=1), encoding="utf-8")
     logger.info("raw-input manifest: %d files (full read set), root=%s",
                 raw_manifest["file_count"], raw_manifest["root"])
 
+    # 4e. transaction attestations (Phase 5-B): pin the audit artifacts + the staged tree's
+    # identity files at execute time; the publish transaction re-verifies all of them under
+    # its locks IMMEDIATELY before the swap and refuses on any drift.
+    staged_att = _staged_attestation(staged_provider)
+
     # 5. dry-run report -> STOP for human sign-off.
     report = {
         "target_end": target_end, "new_policy_id": policy_id, "staged_build_id": build_id,
@@ -881,7 +1141,11 @@ def _build_impl(args, parent_build, parent_policy, parent_end, target_end) -> in
         "spent_oos_end": SPENT_OOS_END, "fresh_holdout_start": FRESH_HOLDOUT_START,
         "disk_free_gb": _disk_free_gb(),
         "frozen_prefix_audit_ok": True, "frozen_prefix_audit_artifact": "frozen_prefix_audit.json",
+        "frozen_prefix_audit_sha256": _sha256_file(fp_artifact),
         "fresh_window_audit_ok": fresh["ok"], "fresh_window_audit_artifact": str(FRESH_AUDIT_PATH.name),
+        "fresh_window_audit_sha256": _sha256_file(FRESH_AUDIT_PATH),
+        "staged_attestation_root": staged_att["root"],
+        "staged_attestation_components": staged_att["components"],
         "report_rc_replay_halo_start": _report_rc_halo_start(target_end),
         "endpoint_completeness": complete_ev,
         "raw_input_manifest_root": raw_manifest["root"],  # full-content input-cut attestation (M3)
@@ -899,9 +1163,29 @@ def _build_impl(args, parent_build, parent_policy, parent_end, target_end) -> in
 
 
 def phase_publish(args) -> int:
-    """§13 human-gated publish leg. Requires a reviewed dry-run report. Safe swap -> rebind ->
-    QA -> parent-build metadata. This driver refuses to run publish unless the operator passes
-    --i-reviewed-the-dryrun AND the report exists (belt: the report is the approval evidence)."""
+    """§13 human-gated ATOMIC publish transaction (Phase 5-B B3.3-5: verification and the
+    swap are inseparable — "a manual interval after verification cannot be the integrity
+    boundary", GPT REWORK-5). Under raw_maintenance_lock + provider_publish_lock, in one
+    scope with nothing released in between:
+
+      verify: parent compare-and-swap (live build/policy == report parent) + full-readset
+              raw-input manifest re-hash + audit-artifact hashes + staged attestation +
+              new-policy re-validation + approvals compare-and-swap
+      swap:   StagedQlibBackendBuilder.publish() — the proven safe staged-first 3-rename
+              swap (single-failure self-rollback), emitting provider_build.json WITH
+              raw_input_manifest_root + parent_provider_build_id (B3.2)
+      bind:   re-load + verify the live manifest, byte-preserving rebind of every bound
+              approval YAML (two-phase, restore-on-failure), 0-drift assertion, committed
+              rebind record, publish record
+
+    then post-publish QA (run_daily_qa) OUTSIDE the locks. Any post-swap failure restores
+    the approval bytes AND rolls the swap back to the parent live provider.
+
+    Exit codes: 0 = published + rebound + QA pass; 2 = refused pre-swap (nothing mutated);
+    4 = post-swap failure, fully rolled back (nothing durably mutated); 5 = CRITICAL
+    inconsistent state (see publish_transaction_journal.json for the exact recovery move);
+    6 = published + consistent, but post-publish QA failed (investigate before any formal
+    run; the provider stays live, parent retained as .bak)."""
     if not args.i_reviewed_the_dryrun:
         logger.error("publish requires --i-reviewed-the-dryrun (you must have read %s). Refusing.",
                      DRYRUN_REPORT_PATH)
@@ -911,70 +1195,220 @@ def phase_publish(args) -> int:
         return 2
     rep = json.loads(DRYRUN_REPORT_PATH.read_text(encoding="utf-8"))
 
-    # Verify-before-publish gate (Blocker 3), all UNDER the raw lock so nothing moves during the check:
-    #  (a) COMPARE-AND-SWAP the parent — the live provider_build/policy MUST still be the report's parent
-    #      (else the report was computed against a since-replaced provider; refuse).
-    #  (b) RE-HASH the full read-set manifest (exactly the files the staged build consumed) and confirm
-    #      the recorded root — a mismatch means the raw cut moved out-of-band since the build.
-    # This still precedes the MANUAL §13 swap (see the residual note in required_manual_steps): the swap
-    # itself must re-run this check immediately before os.replace to be fully atomic — that automated
-    # transaction is the remaining B3 work.
-    from data_infra.tushare_lock import raw_maintenance_lock
+    # The transaction refuses a pre-Phase-5-B report (no attestation fields): the whole
+    # point is that publish verifies EXACTLY what execute attested.
+    required_keys = ("target_end", "new_policy_id", "staged_build_id", "staged_provider_dir",
+                     "parent_build_id", "parent_policy_id", "raw_input_manifest_root",
+                     "frozen_prefix_audit_sha256", "fresh_window_audit_sha256",
+                     "staged_attestation_root")
+    missing = [k for k in required_keys if not rep.get(k)]
+    if missing:
+        logger.error("dry-run report lacks the Phase-5-B transaction attestations %s — re-run "
+                     "--execute with the current driver. Refusing publish.", missing)
+        return 2
     if not RAW_MANIFEST_PATH.exists():
         logger.error("no raw-input manifest sidecar at %s — re-run --execute. Refusing publish.", RAW_MANIFEST_PATH)
         return 2
     manifest = json.loads(RAW_MANIFEST_PATH.read_text(encoding="utf-8"))
-    if manifest.get("root") != rep.get("raw_input_manifest_root"):
+    if manifest.get("root") != rep["raw_input_manifest_root"]:
         logger.error("manifest sidecar root %s != report root %s — inconsistent artifacts; refusing.",
-                     manifest.get("root"), rep.get("raw_input_manifest_root"))
+                     manifest.get("root"), rep["raw_input_manifest_root"])
         return 2
-    with raw_maintenance_lock():
+
+    from data_infra.tushare_lock import provider_publish_lock, raw_maintenance_lock
+    from src.research_orchestrator.calendar_policy import CalendarPolicyError, load_calendar_policy
+
+    journal: dict = {"transaction": "monthly_provider_publish",
+                     "staged_build_id": rep["staged_build_id"],
+                     "new_policy_id": rep["new_policy_id"],
+                     "parent_build_id": rep["parent_build_id"], "steps": []}
+
+    def j(step: str, status: str, **info) -> None:
+        journal["steps"].append({"step": step, "status": status,
+                                 "ts_cst": now_cst().isoformat(timespec="seconds"), **info})
+        _write_journal(journal)
+
+    # LOCK ORDER (fixed everywhere): raw_maintenance_lock FIRST, then provider_publish_lock.
+    with raw_maintenance_lock(), provider_publish_lock():
+        # ── VERIFY: every attestation re-checked here, IMMEDIATELY before the swap, with
+        # no lock release in between (the verify↔swap inseparability is the transaction).
         live_build, live_policy = live_provider_ids()
-        if live_build != rep.get("parent_build_id") or live_policy != rep.get("parent_policy_id"):
-            logger.error("PARENT DRIFT — the live provider is now build=%s/policy=%s but the reviewed "
-                         "report was computed against parent build=%s/policy=%s. The staged build no "
-                         "longer extends the live provider; re-run --execute. Refusing publish.",
-                         live_build, live_policy, rep.get("parent_build_id"), rep.get("parent_policy_id"))
+        if live_build != rep["parent_build_id"] or live_policy != rep["parent_policy_id"]:
+            logger.error("PARENT DRIFT — live provider is build=%s/policy=%s but the reviewed report "
+                         "was computed against parent build=%s/policy=%s. Re-run --execute. Refusing.",
+                         live_build, live_policy, rep["parent_build_id"], rep["parent_policy_id"])
+            j("verify", "refused", reason="parent_drift")
+            return 2
+        for artifact, key in (("frozen_prefix_audit.json", "frozen_prefix_audit_sha256"),
+                              (FRESH_AUDIT_PATH.name, "fresh_window_audit_sha256")):
+            p = OUT_DIR / artifact
+            if not p.is_file() or _sha256_file(p) != rep[key]:
+                logger.error("AUDIT-ARTIFACT DRIFT — %s missing or hash != the reviewed report's %s. "
+                             "Re-run --execute. Refusing.", p, key)
+                j("verify", "refused", reason=f"audit_artifact_drift:{artifact}")
+                return 2
+        staged_dir = Path(rep["staged_provider_dir"])
+        if not staged_dir.is_dir():
+            logger.error("staged provider missing at %s — refusing.", staged_dir)
+            j("verify", "refused", reason="staged_missing")
+            return 2
+        att = _staged_attestation(staged_dir)
+        if att["root"] != rep["staged_attestation_root"]:
+            logger.error("STAGED-TREE DRIFT — staged attestation root %s != the reviewed report's %s "
+                         "(calendar/instruments/build-manifest moved since the audited build). "
+                         "Re-run --execute. Refusing.", att["root"], rep["staged_attestation_root"])
+            j("verify", "refused", reason="staged_attestation_drift")
             return 2
         ok, why = _verify_raw_manifest(manifest)
-    if not ok:
-        logger.error("RAW-INPUT MANIFEST MISMATCH (%s) — the raw cut the staged build consumed changed "
-                     "since the build; the staged provider no longer attests the live raw. Re-run "
-                     "--execute. Refusing publish (fail closed).", why)
-        return 2
-    logger.info("verify-before-publish OK: parent unchanged (%s/%s) + raw manifest re-verified "
-                "(root=%s, %d files).", live_build, live_policy, manifest["root"], manifest["file_count"])
-
-    # m1: the live swap/rebind/QA are deliberately not auto-wired (they mutate the live
-    # provider — §13 — and follow the proven depth9/sharecap precedents). Emit an explicit
-    # handoff artifact the proven scripts consume, and return NON-ZERO so a caller/scheduler
-    # never mistakes this manual-handoff gate for a completed publish.
-    handoff = {
-        "reviewed_dryrun_report": str(DRYRUN_REPORT_PATH),
-        "staged_build_id": rep.get("staged_build_id"),
-        "staged_provider_dir": rep.get("staged_provider_dir"),
-        "new_policy_id": rep.get("new_policy_id"),
-        "parent_build_id": rep.get("parent_build_id"),
-        "raw_input_manifest_root": manifest["root"],  # bind the verified cut into the publish
-        "raw_input_manifest_file_count": manifest["file_count"],
-        "required_manual_steps": [
-            "RESIDUAL (B3, not yet automated): the swap below must re-run _verify_raw_manifest + the "
-            "parent compare-and-swap IMMEDIATELY before os.replace, so verification is atomic with the "
-            "swap (a manual interval after verification is not the integrity boundary — GPT REWORK-5)",
-            "safe atomic swap (staged->adjacent->live, backup old live) per _depth9_safe_publish.py",
-            "rebind ~25 approval YAMLs to the new build+policy id per _rebind_approvals_*.py",
-            "write raw_input_manifest_root into the published data/qlib_data/metadata/provider_build.json "
-            "(bind provider_build_id -> the attested raw cut, B3)",
-            "run scripts/run_daily_qa.py — must be Overall PASS (manifest + approval binding + POLICY001)",
-            "write parent-build metadata + retain the referenced old live as .bak",
-        ],
-        "generated_cst": now_cst().isoformat(timespec="seconds"),
-    }
-    PUBLISH_HANDOFF_PATH.write_text(json.dumps(handoff, ensure_ascii=False, indent=1), encoding="utf-8")
-    logger.warning("Publish is MANUAL (§13). Wrote handoff %s. Execute the required_manual_steps "
-                   "with the proven scripts, then run_daily_qa. This gate confirmed the review; it "
-                   "did NOT publish.", PUBLISH_HANDOFF_PATH)
-    return 3  # non-zero: a manual-handoff gate, not a completed publish
+        if not ok:
+            logger.error("RAW-INPUT MANIFEST MISMATCH (%s) — the raw cut the staged build consumed "
+                         "changed since the build. Re-run --execute. Refusing (fail closed).", why)
+            j("verify", "refused", reason=f"raw_manifest:{why}")
+            return 2
+        try:
+            pol = load_calendar_policy(rep["new_policy_id"], root=POLICY_DIR)
+        except CalendarPolicyError as exc:
+            logger.error("new policy %s no longer loads: %s — refusing.", rep["new_policy_id"], exc)
+            j("verify", "refused", reason="policy_load_failed")
+            return 2
+        end_iso = f"{rep['target_end'][:4]}-{rep['target_end'][4:6]}-{rep['target_end'][6:]}"
+        if (pol.spent_oos_end != SPENT_OOS_END or pol.fresh_holdout_start != FRESH_HOLDOUT_START
+                or not pol.frozen or pol.calendar_end_date != end_iso
+                or pol.require_raw_input_attestation is not True):
+            logger.error("new policy %s drifted from the minted contract (spent=%s fresh=%s frozen=%s "
+                         "end=%s require_raw_input_attestation=%s) — refusing.", pol.policy_id,
+                         pol.spent_oos_end, pol.fresh_holdout_start, pol.frozen,
+                         pol.calendar_end_date, pol.require_raw_input_attestation)
+            j("verify", "refused", reason="policy_drift")
+            return 2
+        ok_bind, bind_msg = _approvals_all_bound_to(live_build, live_policy)
+        if not ok_bind:
+            logger.error("APPROVALS DRIFT — %s. Refusing (the post-swap rebind would not be a clean "
+                         "parent->child rewrite).", bind_msg)
+            j("verify", "refused", reason=f"approvals:{bind_msg}")
+            return 2
+        builder = _make_publish_builder(rep["staged_build_id"])
+        if Path(builder.paths.provider_dir).resolve() != staged_dir.resolve():
+            logger.error("report staged_provider_dir %s is not the canonical staged path %s for "
+                         "build_id %s — refusing.", staged_dir, builder.paths.provider_dir,
+                         rep["staged_build_id"])
+            j("verify", "refused", reason="staged_path_mismatch")
+            return 2
+        j("verify", "ok", raw_files=manifest["file_count"], approvals=bind_msg)
+        logger.info("verify OK under locks: parent (%s/%s), raw root %s (%d files), audits + staged "
+                    "attestation + policy + approvals — swapping now.", live_build, live_policy,
+                    manifest["root"], manifest["file_count"])
+
+        # ── SWAP: the proven primitive; single-rename failures self-roll-back inside it,
+        # leaving the pre-publish state — so a bounded retry vs transient Windows handle
+        # locks (indexer/Defender; the depth9 publish hit exactly this, WinError 5) is
+        # safe. A double failure (live missing) is NEVER retried.
+        from data_infra.pit_backend import BuildGateError
+        import time as _time
+        swap_exc: Exception | None = None
+        for attempt in range(1, 4):
+            try:
+                builder.publish(calendar_policy_id=rep["new_policy_id"],
+                                raw_input_manifest_root=manifest["root"],
+                                parent_provider_build_id=live_build)
+                swap_exc = None
+                break
+            except BuildGateError as exc:
+                swap_exc = exc
+                break  # deterministic refusal (cross-volume / missing staged / double failure)
+            except OSError as exc:
+                swap_exc = exc
+                if not os.path.isdir(builder.paths.qlib_dir):
+                    break  # double failure — do NOT retry over a missing live provider
+                logger.warning("swap attempt %d failed (%s) — pre-publish state restored by the "
+                               "primitive; retrying in 5s", attempt, exc)
+                _time.sleep(5)
+        if swap_exc is not None:
+            live_intact = os.path.isdir(builder.paths.qlib_dir)
+            j("swap", "failed", error=str(swap_exc), live_provider_intact=live_intact)
+            if live_intact:
+                logger.error("swap failed after retries and the primitive rolled back — live "
+                             "provider intact: %s", swap_exc)
+                return 2
+            logger.critical("swap DOUBLE failure — live provider MISSING; follow the recovery move "
+                            "in the error: %s", swap_exc)
+            return 5
+        j("swap", "ok", backup=f"{builder.paths.qlib_dir}.bak_{builder.build_id}")
+
+        # ── BIND: live manifest verification -> approvals rebind -> 0-drift -> records.
+        # Any failure here restores the approval bytes and rolls the swap back.
+        originals: dict[Path, bytes] = {}
+        try:
+            okm, why_m = _verify_live_manifest(
+                builder.paths.qlib_dir, build_id=rep["staged_build_id"],
+                policy_id=rep["new_policy_id"], raw_root=manifest["root"], parent_pb=live_build)
+            if not okm:
+                raise PublishTransactionError(f"post-swap live manifest verification failed: {why_m}")
+            changed, originals = _rebind_approval_files(
+                live_build, live_policy, rep["staged_build_id"], rep["new_policy_id"])
+            from data_infra.approval_evidence import evaluate_approval_evidence_bindings
+            drifts = evaluate_approval_evidence_bindings(
+                approvals_dir=APPROVALS_DIR,
+                manifest_path=Path(builder.paths.qlib_dir) / "metadata" / "provider_build.json")
+            still = [d for d in drifts if d.drift]
+            if still:
+                raise PublishTransactionError(
+                    f"{len(still)} approval(s) still drift after the rebind: {still[0].reasons()}")
+            record_md = _write_rebind_record(
+                new_pb=rep["staged_build_id"], new_cp=rep["new_policy_id"], old_pb=live_build,
+                old_cp=live_policy, n_files=len(changed), raw_root=manifest["root"],
+                raw_files=manifest["file_count"],
+                backup_dir=f"{builder.paths.qlib_dir}.bak_{builder.build_id}")
+            record = {
+                "published_build_id": rep["staged_build_id"],
+                "calendar_policy_id": rep["new_policy_id"],
+                "parent_build_id": live_build, "parent_policy_id": live_policy,
+                "raw_input_manifest_root": manifest["root"],
+                "raw_input_manifest_file_count": manifest["file_count"],
+                "staged_attestation_root": att["root"],
+                "approvals_rebound": len(changed),
+                "rebind_record": str(record_md),
+                "backup_dir": f"{builder.paths.qlib_dir}.bak_{builder.build_id}",
+                "reviewed_dryrun_report": str(DRYRUN_REPORT_PATH),
+                "published_cst": now_cst().isoformat(timespec="seconds"),
+            }
+            _atomic_write_bytes(PUBLISH_RECORD_PATH,
+                                json.dumps(record, ensure_ascii=False, indent=1).encode("utf-8"))
+        except Exception as exc:  # noqa: BLE001 — every post-swap failure must roll back
+            logger.error("post-swap step failed (%s) — restoring approvals + rolling the swap back.", exc)
+            try:
+                _restore_approval_files(originals)
+            except Exception as rexc:  # noqa: BLE001
+                j("bind", "failed", error=str(exc), approvals_restore_error=str(rexc))
+                logger.critical("approval restore ALSO failed (%s) — repair the approval YAMLs from "
+                                "git before retrying.", rexc)
+                _rollback_swap(builder)
+                return 5
+            ok_rb, msg = _rollback_swap(builder)
+            j("bind", "failed_rolled_back" if ok_rb else "failed_rollback_failed",
+              error=str(exc), rollback=msg)
+            if ok_rb:
+                logger.error("ROLLED BACK to the parent live provider (%s). Fix the cause and re-run "
+                             "--publish-approved. Cause: %s", msg, exc)
+                return 4
+            logger.critical("ROLLBACK FAILED: %s — resolve manually per the journal (%s). Cause: %s",
+                            msg, TRANSACTION_JOURNAL_PATH, exc)
+            return 5
+        j("bind", "ok", approvals_rebound=len(changed))
+    # ── locks released: swap + rebind + metadata are consistent and durable.
+
+    logger.info("ATOMIC PUBLISH COMPLETE: %s live under %s (parent %s retained as .bak). Running "
+                "post-publish QA ...", rep["staged_build_id"], rep["new_policy_id"], live_build)
+    qa_rc = _run_post_publish_qa()
+    if qa_rc != 0:
+        j("qa", "failed", returncode=qa_rc)
+        logger.critical("PUBLISHED but post-publish QA FAILED (exit %d) — investigate before any "
+                        "formal run. The provider stays live; parent retained at %s.bak_%s.",
+                        qa_rc, builder.paths.qlib_dir, builder.build_id)
+        return 6
+    j("qa", "ok")
+    logger.info("post-publish QA PASS. Publish record: %s", PUBLISH_RECORD_PATH)
+    return 0
 
 
 def main() -> int:
@@ -982,7 +1416,9 @@ def main() -> int:
     ap.add_argument("--plan", action="store_true", help="Preflight + target_end + plan only")
     ap.add_argument("--execute", action="store_true",
                     help="Run catch-up->rebuild->audits->dry-run report (multi-hour); STOPS before publish")
-    ap.add_argument("--publish-approved", action="store_true", help="Run the publish leg")
+    ap.add_argument("--publish-approved", action="store_true",
+                    help="Run the ATOMIC publish transaction (verify+swap+rebind+QA; §13, "
+                         "requires --i-reviewed-the-dryrun)")
     ap.add_argument("--i-reviewed-the-dryrun", action="store_true",
                     help="Attest the dry-run report was reviewed (required for --publish-approved)")
     ap.add_argument("--target-end", type=str, default=None, help="Override target_end (YYYYMMDD)")
diff --git a/src/backtest_engine/event_driven/__init__.py b/src/backtest_engine/event_driven/__init__.py
index 2a4772f..c88f976 100644
--- a/src/backtest_engine/event_driven/__init__.py
+++ b/src/backtest_engine/event_driven/__init__.py
@@ -238,6 +238,15 @@ def _validate_provider_at_runtime(
             manifest, live_calendar_end, allow_calendar_mismatch=False,
         )
 
+    # Phase 5-B (B3.2): policies minted by the monthly bump require the live manifest
+    # to carry raw_input_manifest_root (the attested raw-input cut of the publish).
+    # Legacy policies leave the flag unset and skip cleanly inside the gate.
+    from src.research_orchestrator.release_gate import assert_provider_raw_attestation
+    assert_provider_raw_attestation(
+        manifest=manifest, policy=policy,
+        artifact_label=f"run_mode={run_mode!r} under policy {calendar_policy_id!r}",
+    )
+
 
 class EventDrivenBacktester:
     """High-level API for running event-driven backtests.
diff --git a/src/data_infra/pit_backend.py b/src/data_infra/pit_backend.py
index 7112a8c..9b69464 100644
--- a/src/data_infra/pit_backend.py
+++ b/src/data_infra/pit_backend.py
@@ -4597,6 +4597,8 @@ class StagedQlibBackendBuilder:
         *,
         calendar_policy_id: str,
         emit_manifest: bool = True,
+        raw_input_manifest_root: str | None = None,
+        parent_provider_build_id: str | None = None,
     ) -> None:
         """Atomically promote the staged provider into ``data/qlib_data``.
 
@@ -4699,9 +4701,19 @@ class StagedQlibBackendBuilder:
         logger.info("Published staged provider to %s (safe staged-first swap)", self.paths.qlib_dir)
 
         if emit_manifest:
-            self._emit_provider_manifest_at_publish(calendar_policy_id=calendar_policy_id)
+            self._emit_provider_manifest_at_publish(
+                calendar_policy_id=calendar_policy_id,
+                raw_input_manifest_root=raw_input_manifest_root,
+                parent_provider_build_id=parent_provider_build_id,
+            )
 
-    def _emit_provider_manifest_at_publish(self, *, calendar_policy_id: str) -> None:
+    def _emit_provider_manifest_at_publish(
+        self,
+        *,
+        calendar_policy_id: str,
+        raw_input_manifest_root: str | None = None,
+        parent_provider_build_id: str | None = None,
+    ) -> None:
         """Emit data/qlib_data/metadata/provider_build.json after publish.
 
         Pulls calendar bounds from the freshly-published Qlib provider's
@@ -4743,8 +4755,14 @@ class StagedQlibBackendBuilder:
                 source_git_commit=source_commit,
                 builder_mode="all",
                 builder_stage="full",
+                raw_input_manifest_root=raw_input_manifest_root,
+                parent_provider_build_id=parent_provider_build_id,
             )
         except Exception as exc:  # noqa: BLE001
+            # Deliberately non-raising for legacy callers (the provider IS live; the manifest
+            # can be re-emitted). The monthly atomic transaction does NOT rely on this leniency:
+            # it re-loads and verifies the live manifest post-swap and rolls the swap back if
+            # the expected attestation is absent (scripts/monthly_calendar_bump.py Phase 5-B).
             logger.error("Failed to emit provider manifest at publish: %s", exc)
 
     def run(
diff --git a/src/data_infra/provider_manifest.py b/src/data_infra/provider_manifest.py
index 7b75bdf..626db38 100644
--- a/src/data_infra/provider_manifest.py
+++ b/src/data_infra/provider_manifest.py
@@ -121,6 +121,13 @@ class ProviderManifest:
     validation: Optional[dict[str, Any]] = None
     retroactive_manifest: bool = False
     retroactive_manifest_evidence: tuple[str, ...] = field(default_factory=tuple)
+    # Phase 5-B (calendar unfreeze, B3.2): bind the published build to the exact raw-input
+    # cut it consumed (sha256 root of the full-readset raw_input_manifest) and to its parent
+    # build. OPTIONAL — pre-thaw manifests lack them and must keep loading; presence for
+    # formal runs is enforced by the release gate when the calendar policy requires it
+    # (require_raw_input_attestation), NOT by this loader.
+    raw_input_manifest_root: Optional[str] = None
+    parent_provider_build_id: Optional[str] = None
 
     @classmethod
     def from_dict(cls, payload: dict[str, Any]) -> "ProviderManifest":
@@ -155,6 +162,24 @@ class ProviderManifest:
                 "retroactive_manifest_evidence array."
             )
 
+        # Phase 5-B: when present, raw_input_manifest_root must be a sha256 hex root — a
+        # malformed value is a corrupted attestation, not a legacy manifest (fail closed).
+        raw_root = payload.get("raw_input_manifest_root")
+        if raw_root is not None:
+            raw_root = str(raw_root)
+            if len(raw_root) != 64 or any(c not in "0123456789abcdef" for c in raw_root):
+                raise ProviderManifestError(
+                    f"raw_input_manifest_root must be a 64-char lowercase sha256 hex root, "
+                    f"got {raw_root!r}."
+                )
+        parent_build = payload.get("parent_provider_build_id")
+        if parent_build is not None:
+            parent_build = str(parent_build)
+            if not parent_build.strip():
+                raise ProviderManifestError(
+                    "parent_provider_build_id, when present, must be a non-blank string."
+                )
+
         return cls(
             schema_version=schema_version,
             provider_build_id=str(payload["provider_build_id"]),
@@ -179,6 +204,8 @@ class ProviderManifest:
             validation=payload.get("validation"),
             retroactive_manifest=retroactive,
             retroactive_manifest_evidence=evidence,
+            raw_input_manifest_root=raw_root,
+            parent_provider_build_id=parent_build,
         )
 
     def to_dict(self) -> dict[str, Any]:
@@ -198,6 +225,12 @@ class ProviderManifest:
         }
         if self.retroactive_manifest:
             out["retroactive_manifest_evidence"] = list(self.retroactive_manifest_evidence)
+        # Emit the Phase 5-B attestation bindings only when present, so pre-thaw manifests
+        # round-trip byte-stable (schema keeps them optional).
+        if self.raw_input_manifest_root is not None:
+            out["raw_input_manifest_root"] = self.raw_input_manifest_root
+        if self.parent_provider_build_id is not None:
+            out["parent_provider_build_id"] = self.parent_provider_build_id
         return out
 
 
@@ -419,6 +452,8 @@ def emit_manifest_at_publish(
     builder_stage: str = "full",
     canonical_kline_hash: Optional[dict[str, Any]] = None,
     validation: Optional[dict[str, Any]] = None,
+    raw_input_manifest_root: Optional[str] = None,
+    parent_provider_build_id: Optional[str] = None,
 ) -> Path:
     """Emit a fresh manifest for a provider that is being published right now.
 
@@ -426,6 +461,10 @@ def emit_manifest_at_publish(
     Distinct from :func:`emit_retroactive_manifest` because no evidence array
     is required (the manifest is being produced contemporaneously with the
     publish).
+
+    ``raw_input_manifest_root`` / ``parent_provider_build_id`` (Phase 5-B B3.2)
+    bind the published build to the attested raw-input cut and its parent build;
+    the monthly atomic publish transaction supplies them, legacy callers omit.
     """
     qlib_dir = Path(qlib_dir)
     now_iso = datetime.utcnow().replace(microsecond=0).isoformat()
@@ -459,6 +498,8 @@ def emit_manifest_at_publish(
         canonical_kline_hash=canonical_kline_hash,
         validation=validation,
         retroactive_manifest=False,
+        raw_input_manifest_root=raw_input_manifest_root,
+        parent_provider_build_id=parent_provider_build_id,
     )
 
     target = manifest_path_for(qlib_dir)
diff --git a/src/data_infra/tushare_lock.py b/src/data_infra/tushare_lock.py
index 440ac1e..9dbbd5a 100644
--- a/src/data_infra/tushare_lock.py
+++ b/src/data_infra/tushare_lock.py
@@ -65,6 +65,17 @@ def raw_maintenance_lock(timeout: float = 21600.0):  # 6h default — a monthly
         yield
 
 
+@contextmanager
+def provider_publish_lock(timeout: float = 7200.0):
+    """Process-exclusive LIVE-provider publish/swap (the monthly bump's atomic verify->swap->rebind
+    transaction, Phase 5-B B3). Serializes anything that replaces ``data/qlib_data`` or rewrites its
+    ``provider_build.json`` so two publishers can never interleave renames. LOCK ORDER: acquire
+    ``raw_maintenance_lock`` FIRST, then this — every holder follows that one order (the publish
+    transaction), so there is no reverse-order path and no lock-order deadlock."""
+    with _filelock("provider_publish.lock", timeout):
+        yield
+
+
 # ── global cross-process rate spacing (a shared next-allowed timestamp, held under the API lock) ──
 def _next_allowed_path() -> Path:
     return _lock_dir() / "tushare_next_allowed.txt"
diff --git a/src/research_orchestrator/calendar_policy.py b/src/research_orchestrator/calendar_policy.py
index d0126ca..4859baf 100644
--- a/src/research_orchestrator/calendar_policy.py
+++ b/src/research_orchestrator/calendar_policy.py
@@ -47,6 +47,13 @@ class CalendarPolicy:
     # fallback in resolve_spent_oos_boundary(). When present, BOTH must be set.
     spent_oos_end: Optional[str] = None
     fresh_holdout_start: Optional[str] = None
+    # Phase 5-B (B3.2): when True, formal runs under this policy REQUIRE the live
+    # provider_build.json to carry raw_input_manifest_root (the attested raw-input cut) —
+    # enforced by release_gate.assert_provider_raw_attestation at the formal-run
+    # provider-validation chokepoint. Default False so pre-thaw / legacy policies (whose
+    # providers predate the attestation) stay valid; every policy minted by the monthly
+    # bump sets it true.
+    require_raw_input_attestation: bool = False
 
     @classmethod
     def from_dict(cls, payload: dict[str, Any]) -> "CalendarPolicy":
@@ -110,6 +117,7 @@ class CalendarPolicy:
             notes=tuple(str(n) for n in payload.get("notes", ())),
             spent_oos_end=str(spent) if spent is not None else None,
             fresh_holdout_start=str(fresh) if fresh is not None else None,
+            require_raw_input_attestation=payload.get("require_raw_input_attestation") is True,
         )
 
     def permits_calendar_mismatch(self, run_mode: str) -> bool:
diff --git a/src/research_orchestrator/release_gate.py b/src/research_orchestrator/release_gate.py
index 1d076b0..732b401 100644
--- a/src/research_orchestrator/release_gate.py
+++ b/src/research_orchestrator/release_gate.py
@@ -427,6 +427,111 @@ def assert_field_dependencies_eligible(
     return result
 
 
+# ─────────────────────────────────────────────────────────────────────────
+# Provider raw-input attestation gate (Phase 5-B, calendar unfreeze B3.2)
+# ─────────────────────────────────────────────────────────────────────────
+#
+# The monthly atomic publish binds every new provider build to the exact raw-input
+# cut it consumed (provider_build.json.raw_input_manifest_root = sha256 root of the
+# full-readset raw_input_manifest). This gate makes that binding LOAD-BEARING for
+# formal runs: when the run's calendar policy declares
+# ``require_raw_input_attestation: true`` (every policy minted by the monthly bump
+# does), a live manifest WITHOUT a valid root fails the formal run. Legacy/pre-thaw
+# policies leave the flag unset, so providers that predate the attestation keep
+# working — enforcement rolls forward with the policies, never retroactively.
+
+_SHA256_HEX_ALPHABET = frozenset("0123456789abcdef")
+
+
+class ProviderAttestationError(RuntimeError):
+    """A formal run's calendar policy requires a raw-input attestation the live
+    provider manifest does not carry (or carries malformed)."""
+
+
+@dataclass(frozen=True)
+class ProviderAttestationGateResult:
+    eligible: bool
+    required: bool
+    policy_id: str | None
+    provider_build_id: str | None
+    raw_input_manifest_root: str | None
+    reasons: tuple[str, ...]
+
+    def to_dict(self) -> dict[str, Any]:
+        return asdict(self)
+
+
+def evaluate_provider_raw_attestation(
+    *,
+    manifest: Any,
+    policy: Any,
+) -> ProviderAttestationGateResult:
+    """Decide whether the live provider manifest satisfies the policy's raw-input
+    attestation requirement.
+
+    ``manifest`` is a ``ProviderManifest`` (attribute access) or a plain mapping of
+    the on-disk ``provider_build.json``; ``policy`` is a ``CalendarPolicy`` (or any
+    object with ``policy_id`` + ``require_raw_input_attestation``). Duck-typed on
+    purpose so this module adds no data_infra import edges.
+    """
+    def _get(obj: Any, key: str) -> Any:
+        if isinstance(obj, Mapping):
+            return obj.get(key)
+        return getattr(obj, key, None)
+
+    policy_id = _get(policy, "policy_id")
+    required = _get(policy, "require_raw_input_attestation") is True
+    build_id = _get(manifest, "provider_build_id")
+    root = _get(manifest, "raw_input_manifest_root")
+
+    reasons: list[str] = []
+    if required:
+        if root is None or not str(root).strip():
+            reasons.append(
+                f"calendar policy {policy_id!r} requires a raw-input attestation but the "
+                f"live provider manifest (build {build_id!r}) carries no "
+                "raw_input_manifest_root — the build was not published through the "
+                "attested monthly transaction (or the manifest was replaced)."
+            )
+        else:
+            root_s = str(root)
+            if len(root_s) != 64 or any(c not in _SHA256_HEX_ALPHABET for c in root_s):
+                reasons.append(
+                    f"raw_input_manifest_root on build {build_id!r} is not a 64-char sha256 "
+                    f"hex root ({root_s!r}) — corrupted attestation."
+                )
+
+    return ProviderAttestationGateResult(
+        eligible=len(reasons) == 0,
+        required=required,
+        policy_id=str(policy_id) if policy_id is not None else None,
+        provider_build_id=str(build_id) if build_id is not None else None,
+        raw_input_manifest_root=str(root) if root is not None else None,
+        reasons=tuple(reasons),
+    )
+
+
+def assert_provider_raw_attestation(
+    *,
+    manifest: Any,
+    policy: Any,
+    artifact_label: str = "formal run",
+) -> ProviderAttestationGateResult:
+    """Strict variant of :func:`evaluate_provider_raw_attestation` for formal paths.
+
+    Wired at the formal-run provider-validation chokepoint
+    (``backtest_engine.event_driven._validate_provider_at_runtime``), where both the
+    loaded manifest and the calendar policy are in hand.
+    """
+    result = evaluate_provider_raw_attestation(manifest=manifest, policy=policy)
+    if not result.eligible:
+        raise ProviderAttestationError(
+            f"Provider raw-input attestation gate blocked {artifact_label}: "
+            f"{list(result.reasons)}"
+        )
+    return result
+
+
 # ─────────────────────────────────────────────────────────────────────────
 # Promotion gate — independent PIT-correct reproduction (PIT-prevention step 11)
 # ─────────────────────────────────────────────────────────────────────────
diff --git a/tests/data_infra/test_monthly_calendar_bump.py b/tests/data_infra/test_monthly_calendar_bump.py
index e3205c5..aa0eb9f 100644
--- a/tests/data_infra/test_monthly_calendar_bump.py
+++ b/tests/data_infra/test_monthly_calendar_bump.py
@@ -504,3 +504,262 @@ def test_full_raw_manifest_covers_readset_and_detects_mutation(tmp_path):
     assert m1["root"] != m2["root"], "a mutated income file MUST change the manifest root"
     bad, why = mcb._verify_raw_manifest(m1, data_root)
     assert not bad and "income" in why  # verify-before-publish catches the out-of-band mutation
+
+
+# ── Phase 5-B B3.3-5: the atomic publish transaction ─────────────────────────
+# phase_publish is now verify+swap+rebind+metadata in ONE lock scope. These tests drive
+# the REAL transaction end-to-end against a synthetic staged/live pair (real renames,
+# real manifest emission, real approval rewrites) — only the QA subprocess is stubbed.
+import json as _json  # noqa: E402
+import types as _types  # noqa: E402
+
+import yaml as _yamlmod  # noqa: E402
+
+
+class _PubArgs:
+    i_reviewed_the_dryrun = True
+
+
+def _publish_env(tmp_path, monkeypatch, *, qa_rc: int = 0):
+    root = tmp_path
+    data = root / "data"
+    out = root / "out"
+    out.mkdir(parents=True)
+    (root / "policies").mkdir()
+    (root / "approvals").mkdir()
+    monkeypatch.setattr(mcb, "PROJECT_ROOT", root)
+    monkeypatch.setattr(mcb, "OUT_DIR", out)
+    monkeypatch.setattr(mcb, "POLICY_DIR", root / "policies")
+    monkeypatch.setattr(mcb, "APPROVALS_DIR", root / "approvals")
+    monkeypatch.setattr(mcb, "DRYRUN_REPORT_PATH", out / "monthly_bump_dryrun_report.json")
+    monkeypatch.setattr(mcb, "FRESH_AUDIT_PATH", out / "fresh_window_survivorship_audit.json")
+    monkeypatch.setattr(mcb, "RAW_MANIFEST_PATH", out / "raw_input_manifest.json")
+    monkeypatch.setattr(mcb, "PUBLISH_RECORD_PATH", out / "publish_record.json")
+    monkeypatch.setattr(mcb, "TRANSACTION_JOURNAL_PATH", out / "publish_transaction_journal.json")
+    monkeypatch.setattr(mcb, "_run_post_publish_qa", lambda: qa_rc)
+
+    parent_pb, parent_cp = "parent_build_1", "frozen_20260701_thaw_step1"
+    new_pb, new_cp = "thaw_20990101_120000", "frozen_20990101_thaw_step2"
+
+    # live provider (the parent)
+    qlib = data / "qlib_data"
+    (qlib / "metadata").mkdir(parents=True)
+    (qlib / "calendars").mkdir()
+    (qlib / "calendars" / "day.txt").write_text("2008-01-02\n2026-07-01\n", encoding="utf-8")
+    (qlib / "LIVE_MARKER.txt").write_text("parent", encoding="utf-8")
+    (qlib / "metadata" / "provider_build.json").write_text(_json.dumps(
+        {"provider_build_id": parent_pb, "calendar_policy_id": parent_cp}), encoding="utf-8")
+
+    # staged provider (the child) at the canonical build path
+    staged = data / "qlib_builds" / new_pb / "provider"
+    (staged / "calendars").mkdir(parents=True)
+    (staged / "calendars" / "day.txt").write_text("2008-01-02\n2099-01-01\n", encoding="utf-8")
+    (staged / "instruments").mkdir()
+    (staged / "instruments" / "all_stocks.txt").write_text(
+        "000001_SZ\t2008-01-02\t2099-01-01\n", encoding="utf-8")
+    (staged / "features" / "000001_sz").mkdir(parents=True)
+    (staged / "STAGED_MARKER.txt").write_text("child", encoding="utf-8")
+    (data / "qlib_builds" / new_pb / "manifest.json").write_text("{}", encoding="utf-8")
+
+    # the minted policy the report points at
+    (root / "policies" / f"{new_cp}.yaml").write_text(_yamlmod.safe_dump({
+        "policy_id": new_cp, "policy_schema_version": 1,
+        "calendar_start_date": "2008-01-02", "calendar_end_date": "2099-01-01",
+        "data_end_date": "2099-01-01", "frozen": True, "reason": "test",
+        "established_at": "2099-01-01", "spent_oos_end": mcb.SPENT_OOS_END,
+        "fresh_holdout_start": mcb.FRESH_HOLDOUT_START,
+        "require_raw_input_attestation": True,
+        "allowed_modes": ["formal"], "default_formal_behavior": "require_explicit_policy",
+    }, sort_keys=False), encoding="utf-8")
+
+    # bound approvals in BOTH quoting styles + one exempt admin record
+    a1 = root / "approvals" / "a1.yaml"
+    a1.write_text(f'approval_id: a1\ndataset_id: d1\nto_status: approved\ndate: "2026-07-01"\n'
+                  f'provider_build_id: "{parent_pb}"\ncalendar_policy_id: {parent_cp}\n',
+                  encoding="utf-8")
+    a2 = root / "approvals" / "a2.yaml"
+    a2.write_text(f"approval_id: a2\ndataset_id: d2\nto_status: approved\ndate: '2026-07-01'\n"
+                  f"provider_build_id: {parent_pb}\ncalendar_policy_id: '{parent_cp}'\n",
+                  encoding="utf-8")
+    (root / "approvals" / "exempt.yaml").write_text(
+        "approval_id: x\nbinding_exempt: true\nbinding_exempt_reason: admin-only record\n",
+        encoding="utf-8")
+
+    # raw cut + full-readset manifest sidecar over it
+    raw = data / "reference" / "trade_cal.parquet"
+    raw.parent.mkdir(parents=True)
+    raw.write_bytes(b"CAL0")
+    manifest = mcb._full_raw_manifest(data)
+    (out / "raw_input_manifest.json").write_text(_json.dumps(manifest), encoding="utf-8")
+
+    # audit artifacts + staged attestation, pinned into the dry-run report
+    fp = out / "frozen_prefix_audit.json"
+    fp.write_text(_json.dumps({"staged": str(staged), "ok": True}), encoding="utf-8")
+    fw = out / "fresh_window_survivorship_audit.json"
+    fw.write_text(_json.dumps({"ok": True, "violations": []}), encoding="utf-8")
+    att = mcb._staged_attestation(staged)
+    report = {
+        "target_end": "20990101", "new_policy_id": new_cp, "staged_build_id": new_pb,
+        "staged_provider_dir": str(staged), "parent_build_id": parent_pb,
+        "parent_policy_id": parent_cp, "raw_input_manifest_root": manifest["root"],
+        "frozen_prefix_audit_sha256": mcb._sha256_file(fp),
+        "fresh_window_audit_sha256": mcb._sha256_file(fw),
+        "staged_attestation_root": att["root"],
+    }
+    (out / "monthly_bump_dryrun_report.json").write_text(_json.dumps(report), encoding="utf-8")
+
+    def _builder(build_id: str):
+        from data_infra.pit_backend import StagedQlibBackendBuilder
+        return StagedQlibBackendBuilder(data_root=str(data), qlib_dir=str(qlib), build_id=build_id)
+
+    monkeypatch.setattr(mcb, "_make_publish_builder", _builder)
+    return _types.SimpleNamespace(
+        root=root, data=data, qlib=qlib, staged=staged, out=out, raw=raw,
+        parent_pb=parent_pb, parent_cp=parent_cp, new_pb=new_pb, new_cp=new_cp,
+        manifest=manifest, a1=a1, a2=a2,
+        a1_bytes=a1.read_bytes(), a2_bytes=a2.read_bytes())
+
+
+def _assert_untouched(env):
+    """The refusal contract: NOTHING durable mutated — parent still live, staged still
+    staged, approvals byte-identical."""
+    assert (env.qlib / "LIVE_MARKER.txt").exists(), "parent must still be live"
+    assert (env.staged / "STAGED_MARKER.txt").exists(), "staged tree must stay staged"
+    assert env.a1.read_bytes() == env.a1_bytes and env.a2.read_bytes() == env.a2_bytes
+    assert not (env.data / f"qlib_data.bak_{env.new_pb}").exists(), "no backup may appear"
+
+
+def test_publish_transaction_happy_path(tmp_path, monkeypatch):
+    env = _publish_env(tmp_path, monkeypatch)
+    assert mcb.phase_publish(_PubArgs()) == 0
+    # swap: child live, parent retained as .bak
+    assert (env.qlib / "STAGED_MARKER.txt").exists()
+    bak = env.data / f"qlib_data.bak_{env.new_pb}"
+    assert (bak / "LIVE_MARKER.txt").exists()
+    # metadata: the live manifest binds build -> policy -> raw cut -> parent
+    m = _json.loads((env.qlib / "metadata" / "provider_build.json").read_text(encoding="utf-8"))
+    assert m["provider_build_id"] == env.new_pb
+    assert m["calendar_policy_id"] == env.new_cp
+    assert m["raw_input_manifest_root"] == env.manifest["root"]
+    assert m["parent_provider_build_id"] == env.parent_pb
+    # rebind: both quoting styles preserved, values swapped; exempt untouched
+    t1 = env.a1.read_text(encoding="utf-8")
+    assert f'provider_build_id: "{env.new_pb}"' in t1 and f"calendar_policy_id: {env.new_cp}" in t1
+    t2 = env.a2.read_text(encoding="utf-8")
+    assert f"provider_build_id: {env.new_pb}" in t2 and f"calendar_policy_id: '{env.new_cp}'" in t2
+    from data_infra.approval_evidence import evaluate_approval_evidence_bindings
+    drifts = evaluate_approval_evidence_bindings(
+        approvals_dir=env.root / "approvals",
+        manifest_path=env.qlib / "metadata" / "provider_build.json")
+    assert drifts and not any(d.drift for d in drifts)
+    # records
+    assert (env.out / "publish_record.json").exists()
+    assert (env.out / "publish_transaction_journal.json").exists()
+    assert list((env.root / "approvals").glob(f"*_rebind_to_{env.new_pb}.md"))
+
+
+def test_publish_refuses_parent_drift(tmp_path, monkeypatch):
+    env = _publish_env(tmp_path, monkeypatch)
+    (env.qlib / "metadata" / "provider_build.json").write_text(_json.dumps(
+        {"provider_build_id": "someone_else", "calendar_policy_id": env.parent_cp}), encoding="utf-8")
+    assert mcb.phase_publish(_PubArgs()) == 2
+    assert (env.qlib / "LIVE_MARKER.txt").exists() and (env.staged / "STAGED_MARKER.txt").exists()
+    assert env.a1.read_bytes() == env.a1_bytes
+
+
+def test_publish_refuses_raw_input_mutation(tmp_path, monkeypatch):
+    env = _publish_env(tmp_path, monkeypatch)
+    env.raw.write_bytes(b"CALX")  # same size, different content — content hash must catch it
+    assert mcb.phase_publish(_PubArgs()) == 2
+    _assert_untouched(env)
+
+
+def test_publish_refuses_audit_artifact_drift(tmp_path, monkeypatch):
+    env = _publish_env(tmp_path, monkeypatch)
+    fp = env.out / "frozen_prefix_audit.json"
+    fp.write_text(_json.dumps({"staged": str(env.staged), "ok": True, "edited": 1}), encoding="utf-8")
+    assert mcb.phase_publish(_PubArgs()) == 2
+    _assert_untouched(env)
+
+
+def test_publish_refuses_staged_tree_drift(tmp_path, monkeypatch):
+    env = _publish_env(tmp_path, monkeypatch)
+    cal = env.staged / "calendars" / "day.txt"
+    cal.write_text(cal.read_text(encoding="utf-8") + "2099-01-02\n", encoding="utf-8")
+    assert mcb.phase_publish(_PubArgs()) == 2
+    _assert_untouched(env)
+
+
+def test_publish_refuses_foreign_approval_binding(tmp_path, monkeypatch):
+    env = _publish_env(tmp_path, monkeypatch)
+    env.a2.write_text("approval_id: a2\ndataset_id: d2\nto_status: approved\ndate: '2026-07-01'\n"
+                      "provider_build_id: other_build\ncalendar_policy_id: other_policy\n",
+                      encoding="utf-8")
+    assert mcb.phase_publish(_PubArgs()) == 2
+    assert (env.qlib / "LIVE_MARKER.txt").exists() and (env.staged / "STAGED_MARKER.txt").exists()
+
+
+def test_publish_refuses_pre_phase5b_report(tmp_path, monkeypatch):
+    # A report produced by the pre-transaction driver (no attestation fields) must refuse
+    # — publish verifies exactly what execute attested, or nothing.
+    env = _publish_env(tmp_path, monkeypatch)
+    rep = _json.loads((env.out / "monthly_bump_dryrun_report.json").read_text(encoding="utf-8"))
+    del rep["staged_attestation_root"]
+    (env.out / "monthly_bump_dryrun_report.json").write_text(_json.dumps(rep), encoding="utf-8")
+    assert mcb.phase_publish(_PubArgs()) == 2
+    _assert_untouched(env)
+
+
+def test_publish_rolls_back_on_postswap_failure(tmp_path, monkeypatch):
+    # A failure AFTER the swap (here: the rebind-record write) must restore the approval
+    # bytes AND roll the swap back — parent live again, staged tree back for a clean retry.
+    env = _publish_env(tmp_path, monkeypatch)
+
+    def _boom(**kwargs):
+        raise RuntimeError("record write failed")
+
+    monkeypatch.setattr(mcb, "_write_rebind_record", _boom)
+    assert mcb.phase_publish(_PubArgs()) == 4
+    assert (env.qlib / "LIVE_MARKER.txt").exists(), "parent live provider must be restored"
+    assert (env.staged / "STAGED_MARKER.txt").exists(), "staged tree must be back at provider_dir"
+    assert mcb.live_provider_ids() == (env.parent_pb, env.parent_cp)
+    assert env.a1.read_bytes() == env.a1_bytes and env.a2.read_bytes() == env.a2_bytes
+    assert not (env.data / f"qlib_data.bak_{env.new_pb}").exists(), "rollback must consume the backup"
+    steps = _json.loads((env.out / "publish_transaction_journal.json").read_text(encoding="utf-8"))["steps"]
+    assert any(s["step"] == "bind" and s["status"] == "failed_rolled_back" for s in steps)
+
+
+def test_publish_rolls_back_when_manifest_emission_fails(tmp_path, monkeypatch):
+    # The builder's emit path is deliberately non-raising; the transaction must catch the
+    # absent/short manifest via _verify_live_manifest and roll the whole swap back.
+    env = _publish_env(tmp_path, monkeypatch)
+    import data_infra.provider_manifest as pm
+
+    def _boom(**kwargs):
+        raise OSError("disk full")
+
+    monkeypatch.setattr(pm, "emit_manifest_at_publish", _boom)
+    assert mcb.phase_publish(_PubArgs()) == 4
+    assert (env.qlib / "LIVE_MARKER.txt").exists()
+    assert (env.staged / "STAGED_MARKER.txt").exists()
+    assert mcb.live_provider_ids() == (env.parent_pb, env.parent_cp)
+    assert env.a1.read_bytes() == env.a1_bytes
+
+
+def test_publish_qa_failure_returns_6_and_keeps_provider(tmp_path, monkeypatch):
+    # QA runs OUTSIDE the transaction: a QA failure alarms (exit 6) but does not undo a
+    # consistent swap+rebind+metadata — the operator investigates with the .bak retained.
+    env = _publish_env(tmp_path, monkeypatch, qa_rc=1)
+    assert mcb.phase_publish(_PubArgs()) == 6
+    assert (env.qlib / "STAGED_MARKER.txt").exists(), "the published provider stays live"
+    m = _json.loads((env.qlib / "metadata" / "provider_build.json").read_text(encoding="utf-8"))
+    assert m["provider_build_id"] == env.new_pb
+    assert f'provider_build_id: "{env.new_pb}"' in env.a1.read_text(encoding="utf-8")
+
+
+def test_generate_thaw_policy_requires_raw_attestation(tmp_path, monkeypatch):
+    # Every bump-minted policy makes the raw-input attestation load-bearing for formal runs.
+    monkeypatch.setattr(mcb, "POLICY_DIR", tmp_path)
+    _pid, path = mcb.generate_thaw_policy("20990131", "pb", write=True)
+    body = _yamlmod.safe_load(path.read_text(encoding="utf-8"))
+    assert body["require_raw_input_attestation"] is True
diff --git a/tests/data_infra/test_provider_manifest.py b/tests/data_infra/test_provider_manifest.py
index 51b5507..44c1cc1 100644
--- a/tests/data_infra/test_provider_manifest.py
+++ b/tests/data_infra/test_provider_manifest.py
@@ -67,6 +67,46 @@ def _valid_payload(**overrides) -> dict:
     return base
 
 
+class TestRawInputAttestationFields:
+    """Phase 5-B B3.2: raw_input_manifest_root + parent_provider_build_id are OPTIONAL
+    (pre-thaw manifests keep loading) but validated when present, and round-trip."""
+
+    def test_legacy_manifest_without_fields_loads_as_none(self, tmp_path: Path) -> None:
+        _write_manifest(tmp_path, _valid_payload())
+        manifest = load_provider_manifest(tmp_path)
+        assert manifest.raw_input_manifest_root is None
+        assert manifest.parent_provider_build_id is None
+        # and to_dict does NOT invent the keys (legacy round-trip stability)
+        d = manifest.to_dict()
+        assert "raw_input_manifest_root" not in d
+        assert "parent_provider_build_id" not in d
+
+    def test_attested_manifest_roundtrips(self, tmp_path: Path) -> None:
+        root = "ab" * 32
+        _write_manifest(tmp_path, _valid_payload(
+            raw_input_manifest_root=root, parent_provider_build_id="parent_build_1"))
+        manifest = load_provider_manifest(tmp_path)
+        assert manifest.raw_input_manifest_root == root
+        assert manifest.parent_provider_build_id == "parent_build_1"
+        d = manifest.to_dict()
+        assert d["raw_input_manifest_root"] == root
+        assert d["parent_provider_build_id"] == "parent_build_1"
+
+    def test_malformed_raw_root_fails_closed(self, tmp_path: Path) -> None:
+        # A present-but-garbage attestation is corruption, not legacy — must raise.
+        _write_manifest(tmp_path, _valid_payload(raw_input_manifest_root="not-a-hash"))
+        with pytest.raises(ProviderManifestError, match="raw_input_manifest_root"):
+            load_provider_manifest(tmp_path)
+        _write_manifest(tmp_path, _valid_payload(raw_input_manifest_root="AB" * 32))  # uppercase
+        with pytest.raises(ProviderManifestError, match="raw_input_manifest_root"):
+            load_provider_manifest(tmp_path)
+
+    def test_blank_parent_build_id_fails_closed(self, tmp_path: Path) -> None:
+        _write_manifest(tmp_path, _valid_payload(parent_provider_build_id="  "))
+        with pytest.raises(ProviderManifestError, match="parent_provider_build_id"):
+            load_provider_manifest(tmp_path)
+
+
 class TestProviderManifestLoadErrors:
     """Negative path: missing/malformed manifest must raise."""
 
diff --git a/tests/research_orchestrator/test_provider_raw_attestation_gate.py b/tests/research_orchestrator/test_provider_raw_attestation_gate.py
new file mode 100644
index 0000000..2246915
--- /dev/null
+++ b/tests/research_orchestrator/test_provider_raw_attestation_gate.py
@@ -0,0 +1,142 @@
+"""Phase 5-B B3.2: the provider raw-input attestation gate.
+
+The monthly atomic publish binds every new build to its raw-input cut
+(provider_build.json.raw_input_manifest_root). These tests pin the enforcement side:
+
+  * CalendarPolicy parses ``require_raw_input_attestation`` (strict-bool, default False).
+  * release_gate.assert_provider_raw_attestation fails a formal run whose policy requires
+    the attestation when the live manifest lacks (or carries a malformed) root — and
+    SKIPS cleanly for legacy policies, so pre-thaw providers keep working.
+  * The formal-run chokepoint (event_driven._validate_provider_at_runtime) actually
+    invokes the gate — a policy-flagged run against an unattested manifest raises.
+"""
+from __future__ import annotations
+
+import pytest
+
+from src.data_infra.provider_manifest import ProviderManifest
+from src.research_orchestrator.calendar_policy import CalendarPolicy
+from src.research_orchestrator.release_gate import (
+    ProviderAttestationError,
+    assert_provider_raw_attestation,
+    evaluate_provider_raw_attestation,
+)
+
+_ROOT = "cd" * 32
+
+
+def _policy(require: bool, **overrides) -> CalendarPolicy:
+    payload = {
+        "policy_id": "frozen_20990101_thaw_stepN",
+        "policy_schema_version": 1,
+        "calendar_start_date": "2008-01-02",
+        "calendar_end_date": "2099-01-01",
+        "data_end_date": "2099-01-01",
+        "frozen": True,
+        "reason": "test",
+        "established_at": "2099-01-01",
+        "spent_oos_end": "2026-02-27",
+        "fresh_holdout_start": "2026-02-28",
+        "allowed_modes": ["formal", "oos_test"],
+        "default_formal_behavior": "require_explicit_policy",
+    }
+    if require:
+        payload["require_raw_input_attestation"] = True
+    payload.update(overrides)
+    return CalendarPolicy.from_dict(payload)
+
+
+def _manifest(**overrides) -> ProviderManifest:
+    payload = {
+        "schema_version": 1,
+        "provider_build_id": "thaw_20990101_120000",
+        "provider_published_at": "2099-01-01T00:00:00",
+        "calendar_policy_id": "frozen_20990101_thaw_stepN",
+        "provider": {
+            "path": "data/qlib_data", "region": "REG_CN",
+            "calendar_start_date": "2008-01-02", "calendar_end_date": "2099-01-01",
+            "data_end_date": "2099-01-01",
+        },
+        "event_endpoint_namespacing": {
+            "status": "enforced",
+            "affected_datasets": ["top_list", "top_inst", "block_trade", "cyq_perf"],
+            "prefix_rule": "{dataset}__{column}",
+            "canonical_kline_fields_protected": ["$open", "$high", "$low", "$close", "$vol", "$amount"],
+        },
+    }
+    payload.update(overrides)
+    return ProviderManifest.from_dict(payload)
+
+
+# ── policy flag parsing ───────────────────────────────────────────────────────
+def test_policy_flag_defaults_false_and_parses_strict_bool():
+    assert _policy(require=False).require_raw_input_attestation is False
+    assert _policy(require=True).require_raw_input_attestation is True
+    # strict bool: a YAML string "true" must NOT enable enforcement silently … but it
+    # must not DISABLE fail-closed either — the gate treats only `is True` as required,
+    # mirroring the binding_exempt discipline.
+    sneaky = _policy(require=False, require_raw_input_attestation="true")
+    assert sneaky.require_raw_input_attestation is False
+
+
+# ── the gate itself ──────────────────────────────────────────────────────────
+def test_gate_passes_when_policy_requires_and_root_present():
+    result = assert_provider_raw_attestation(
+        manifest=_manifest(raw_input_manifest_root=_ROOT, parent_provider_build_id="p"),
+        policy=_policy(require=True))
+    assert result.eligible and result.required
+    assert result.raw_input_manifest_root == _ROOT
+
+
+def test_gate_blocks_missing_root_when_required():
+    with pytest.raises(ProviderAttestationError, match="raw_input_manifest_root"):
+        assert_provider_raw_attestation(manifest=_manifest(), policy=_policy(require=True))
+
+
+def test_gate_blocks_malformed_root_when_required():
+    # bypass the loader (which would already refuse) by evaluating a raw mapping — the
+    # gate must not trust its input to have been loader-validated.
+    result = evaluate_provider_raw_attestation(
+        manifest={"provider_build_id": "b", "raw_input_manifest_root": "zz"},
+        policy=_policy(require=True))
+    assert not result.eligible and any("sha256" in r for r in result.reasons)
+
+
+def test_gate_skips_for_legacy_policy():
+    # Pre-thaw policies never set the flag: an unattested manifest stays eligible.
+    result = evaluate_provider_raw_attestation(manifest=_manifest(), policy=_policy(require=False))
+    assert result.eligible and not result.required
+
+
+# ── formal-run chokepoint wiring ─────────────────────────────────────────────
+def _wire_runtime_validation(tmp_path, monkeypatch, policy):
+    """Drive event_driven._validate_provider_at_runtime against a synthetic provider
+    dir + injected policy (the loader is patched at its source module, which the
+    chokepoint imports at call time)."""
+    from src.research_orchestrator import calendar_policy as cp
+    monkeypatch.setattr(cp, "load_calendar_policy", lambda pid: policy)
+    (tmp_path / "calendars").mkdir(parents=True)
+    (tmp_path / "calendars" / "day.txt").write_text("2008-01-02\n2099-01-01\n", encoding="utf-8")
+
+
+def test_formal_runtime_validation_enforces_attestation(tmp_path, monkeypatch):
+    from src.backtest_engine.event_driven import _validate_provider_at_runtime
+
+    _wire_runtime_validation(tmp_path, monkeypatch, _policy(require=True))
+    with pytest.raises(ProviderAttestationError, match="raw_input_manifest_root"):
+        _validate_provider_at_runtime(
+            manifest=_manifest(), calendar_policy_id="frozen_20990101_thaw_stepN",
+            run_mode="formal", qlib_dir=tmp_path)
+    # same run with an attested manifest passes
+    _validate_provider_at_runtime(
+        manifest=_manifest(raw_input_manifest_root=_ROOT, parent_provider_build_id="p"),
+        calendar_policy_id="frozen_20990101_thaw_stepN", run_mode="formal", qlib_dir=tmp_path)
+
+
+def test_formal_runtime_validation_legacy_policy_unaffected(tmp_path, monkeypatch):
+    from src.backtest_engine.event_driven import _validate_provider_at_runtime
+
+    _wire_runtime_validation(tmp_path, monkeypatch, _policy(require=False))
+    _validate_provider_at_runtime(
+        manifest=_manifest(), calendar_policy_id="frozen_20990101_thaw_stepN",
+        run_mode="formal", qlib_dir=tmp_path)
```

QUANTITATIVE-RESEARCH PRINCIPLES — check the change against EACH; a violation is a Blocker
1. PIT / NO-LOOKAHEAD (the cardinal rule). This change adds no research data path, but it GUARDS the PIT evidence chain: the published provider must be byte-bound to the audited raw cut. Ask: can any interleaving (lock release, retry, rollback, crash) publish a provider whose content does NOT match what the audits attested?
2. OUT-OF-SAMPLE IS SACRED & SEALED. spent_oos_end must stay frozen at 2026-02-27 through every code path here (policy re-validation, minting). Ask: can this transaction ever publish under a policy whose spent/fresh boundary drifted?
3. SURVIVORSHIP. The fresh-window survivorship audit's artifact hash is pinned into the report and re-verified — can a swapped-in provider evade it?
4-6, 8, 9 (factor-eval / execution realism / leverage / four-layer / multiple testing): not exercised by this change — confirm no hidden interaction.
7. NO HEDGE WORDS. The self-review's verification numbers must be reproducible from the named commands.

REVIEW QUESTIONS (answer each explicitly)
1. TRANSACTION ATOMICITY: within the lock scope, is there ANY window where verified state can drift before os.replace consumes it? Is the lock ORDER (raw -> publish) deadlock-free against every other holder in the repo (daily_raw_job, catch-up drivers, QA)? Is running run_daily_qa OUTSIDE the locks (L4) the right boundary, or must it be inside?
2. ROLLBACK CORRECTNESS: walk the reverse 3-rename (_rollback_swap) against every failure point in publish() and the bind phase. Can any sequence leave qlib_dir missing, double-named trees, or a half-rebound approvals dir WITHOUT exit 5 + an accurate journal recovery hint? Is restoring approval bytes BEFORE rolling the swap back the right order?
3. THE SWAP RETRY: bounded OSError retry (3x5s) around publish() — is retrying after a single-rename failure genuinely safe given publish()'s internal rollback guarantees (each failure restores pre-publish state)? Any state where retry compounds damage?
4. B3.2 ENFORCEMENT DESIGN: is policy-flag roll-forward (require_raw_input_attestation on newly minted policies only) the correct enforcement scope — or must presence be enforced retroactively/harder (e.g., schema-required, gate-on-all-formal-runs), accepting that the current live provider would then fail formal runs until the next publish? Is the strict-bool (is True) parsing right, or should a truthy-but-non-bool value REFUSE instead of silently reading False?
5. REBIND ROBUSTNESS: the exact-token regex substitution (^key:[ \t]*["']?OLD["']?[ \t]*\r?$, exactly-one-match per key per file, then a full YAML re-parse asserting the new ids, two-phase write with restore). Any YAML shape among committed approvals it corrupts or wrongly refuses? Is byte-preservation the right call vs a structured rewrite?
6. STAGED ATTESTATION DEPTH (L1): is identity-file hashing + execute-time content audits + build-scoped path an acceptable integrity boundary for the features tree, or do you require a deeper mechanism (e.g., stat-walk root, sampled content re-hash) before first real use?
7. TEST-NAMESPACE LANDMINE: tests/research_orchestrator/__init__.py makes any pytest run bind the plain name research_orchestrator to the tests package (same for backtest_engine, architecture). We worked around it via src.-prefixed imports in the script. Should the repo-level fix (removing those __init__.py / renaming test packages) be mandated now, and does any OTHER plain-namespace import in production scripts share the hazard?
8. EVIDENCE: what proof is missing before the first REAL run of this transaction (next monthly bump, §13-gated)? Name the exact preflight you would require (e.g., a small --touched-symbols staged build first, a rollback drill on the real tree).

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending line quoted and an exact suggested replacement. Map every Blocker to the principle or invariant it violates.
- Explicit accept/reject on each of L1-L5.
- Final line: SHIP / REVISE / REWORK, plus the single most important residual risk.
```
