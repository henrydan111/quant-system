"""Safe-ordered publish of the staged depth-9 provider (avoids the broken-window failure of publish()'s
backup-first order). Order: staged -> data/qlib_data.depth9_new FIRST (qlib_data untouched if the staged tree
is still locked by the indexer/Defender); only then live->backup and new->live, each with rollback. Idempotent
preflight; fail-closed rollbacks. One-shot (no infinite wait) — re-run after clearing the lock."""
import os
import sys
import time

sys.path.insert(0, "src")
QL = "data/qlib_data"
NEW = "data/qlib_data.depth9_new"
BAK = "data/qlib_data.bak_depth9_20260630"
STG = "data/qlib_builds/depth9_20260630/provider"


def rn(a, b):
    os.replace(a, b)


def main() -> int:
    if os.path.isdir(QL) and os.path.isdir(QL + "/features/600519_sh") and \
       any(f.endswith("_q8.day.bin") for f in os.listdir(QL + "/features/600519_sh")):
        print("qlib_data already at depth-9 — nothing to do"); return 0
    if not os.path.isdir(STG):
        print(f"ERROR: staged provider missing at {STG}"); return 2
    if os.path.isdir(NEW):
        print(f"ERROR: stale {NEW} exists — remove before retry"); return 3
    if os.path.exists(BAK):
        print(f"ERROR: stale backup {BAK} exists — resolve before retry"); return 4

    # step 1: staged -> NEW (qlib_data untouched if locked)
    moved = False
    for i in range(6):
        try:
            rn(STG, NEW); moved = True; print(f"staged->NEW OK (attempt {i+1}) — lock clear", flush=True); break
        except PermissionError as e:
            print(f"staged->NEW attempt {i+1} DENIED: {e}", flush=True); time.sleep(6)
    if not moved:
        print("STAGED STILL LOCKED — qlib_data untouched (depth-5 stays live). Clear indexer/Defender lock, retry.", flush=True)
        return 1

    # step 2: live -> backup
    try:
        rn(QL, BAK); print("live->backup OK", flush=True)
    except PermissionError as e:
        print(f"live->backup DENIED ({e}); rolling staged back", flush=True)
        rn(NEW, STG); print("rolled back; depth-5 stays live", flush=True); return 5

    # step 3: NEW -> live (retry vs indexer race on the just-moved dir)
    ok = False
    for i in range(6):
        try:
            rn(NEW, QL); ok = True; print(f"NEW->live OK (attempt {i+1})", flush=True); break
        except PermissionError as e:
            print(f"NEW->live attempt {i+1} DENIED: {e}", flush=True); time.sleep(4)
    if not ok:
        print("NEW->live failed; restoring depth-5 backup", flush=True)
        rn(BAK, QL); print(f"depth-5 restored live; depth-9 sits at {NEW}", flush=True); return 6

    print("PUBLISHED: depth-9 provider is LIVE", flush=True)

    # step 4: provider_build.json attestation
    try:
        from data_infra.pit_backend import StagedQlibBackendBuilder
        StagedQlibBackendBuilder(build_id="depth9_20260630")._emit_provider_manifest_at_publish(
            calendar_policy_id="frozen_20260227_system_build")
        print("provider_build.json emitted", flush=True)
    except Exception as e:
        print(f"WARN manifest emit failed (provider IS live; emit separately): {e}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
