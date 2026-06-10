# ──────────────────────────────────────────────────────────────────────
# script_status: research_tooling
# formal_research_allowed: false
# deployment_target: unified_eval_evidence_only
# requires_provider_manifest: false
# requires_preload_strict: false
# pr2_audit_class: C
# notes: |
#   Self-healing supervisor for the full-catalog unified-eval run. Loops the resumable
#   driver (unified_eval_full_run.py) until it exits 0. Designed to run under a Windows
#   SCHEDULED TASK (own process tree) because session-spawned background trees were
#   silently killed three times (~20-40 min in; no WER record, no traceback, 36GB RAM
#   free). ASCII-only source; all paths derived from __file__ (the documented .bat/OEM
#   codepage pitfall with the Chinese project path does not apply to direct python.exe
#   scheduled-task invocations).
# ──────────────────────────────────────────────────────────────────────
"""Supervisor: keep relaunching the resumable unified-eval full run until it completes."""
from __future__ import annotations

import datetime
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PY = PROJECT_ROOT / "venv" / "Scripts" / "python.exe"
DRIVER = PROJECT_ROOT / "workspace" / "scripts" / "unified_eval_full_run.py"
OUTDIR = PROJECT_ROOT / "workspace" / "outputs" / "unified_eval"
RUN_LOG = OUTDIR / "full_run.log"
SUP_LOG = OUTDIR / "supervisor.log"
MAX_ATTEMPTS = 80


def _log(msg: str) -> None:
    line = f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n"
    with SUP_LOG.open("a", encoding="utf-8") as fh:
        fh.write(line)


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    _log(f"supervisor start (pid={None}) driver={DRIVER}")
    for attempt in range(1, MAX_ATTEMPTS + 1):
        _log(f"attempt {attempt}: launching driver")
        with RUN_LOG.open("a", encoding="utf-8") as out:
            rc = subprocess.run([str(PY), str(DRIVER), "--batch-size", "10"],
                                cwd=str(PROJECT_ROOT), stdout=out, stderr=out).returncode
        _log(f"attempt {attempt}: driver exit={rc}")
        if rc == 0:
            _log("COMPLETED")
            return 0
        time.sleep(5)
    _log("GAVE UP after MAX_ATTEMPTS")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
