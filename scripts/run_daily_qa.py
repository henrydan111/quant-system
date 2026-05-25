"""P1-4: Manual QA orchestrator for the data backend.

This script is invoked MANUALLY before research sessions or after any
data-infra change. It is NOT a scheduler and does NOT send alerts —
those are intentionally out-of-scope (see plan v3 scope guardrails).
It simply runs the existing QA checks in a defined order and writes a
structured JSON report plus a human-readable markdown summary.

Checks orchestrated (in order):
  1. ``DataAuditor.audit_daily_files`` (via in-process call)
  2. ``scripts/audit_qlib.py --sample-size 30`` (live provider smoke)
  3. ``tests/data_infra/test_provider_boundary.py`` (P0-1 delist contract)
  4. ``tests/data_infra/test_pit_live_provider.py`` (P0-3 PIT regression)

Exit code non-zero on any failure.

Usage
=====

    E:/量化系统/venv/Scripts/python.exe scripts/run_daily_qa.py

The markdown summary goes to stdout; the JSON report goes to
``logs/qa_report_<yyyymmdd_hhmmss>.json``.

See CLAUDE.md §6.2 (operational QA runner) and project_state.md
remediation milestone for context.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENV_PYTHON = PROJECT_ROOT / "venv" / "Scripts" / "python.exe"
LOGS_DIR = PROJECT_ROOT / "logs"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _run(cmd: list[str], label: str) -> dict:
    """Run a subprocess, capture output, return a structured result."""
    logger.info("[%s] %s", label, " ".join(cmd))
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
    )
    ok = result.returncode == 0
    logger.info("[%s] exit=%d", label, result.returncode)
    return {
        "label": label,
        "command": " ".join(cmd),
        "exit_code": result.returncode,
        "ok": ok,
        "stdout_tail": result.stdout.splitlines()[-20:] if result.stdout else [],
        "stderr_tail": result.stderr.splitlines()[-10:] if result.stderr else [],
    }


def _audit_daily_files_inprocess() -> dict:
    """Run DataAuditor in-process on the live data/market/daily tree."""
    try:
        sys.path.insert(0, str(PROJECT_ROOT / "src"))
        from data_infra.verification.data_auditor import DataAuditor

        auditor = DataAuditor()
        # Audit last ~30 days of daily files as a smoke; full audit is slow
        import pandas as pd
        cal = pd.read_parquet(PROJECT_ROOT / "data" / "reference" / "trade_cal.parquet")
        cal = cal[cal["is_open"] == 1].sort_values("cal_date")
        end_date = str(cal["cal_date"].iloc[-1])
        start_date = str(cal["cal_date"].iloc[-30])
        result = auditor.audit_daily_files(start_date=start_date, end_date=end_date)
        n_anomalies = len(result.get("anomalies", [])) if isinstance(result, dict) else 0
        n_missing = len(result.get("missing_dates", [])) if isinstance(result, dict) else 0
        ok = n_anomalies == 0 and n_missing == 0
        return {
            "label": "DataAuditor.audit_daily_files",
            "ok": ok,
            "exit_code": 0 if ok else 1,
            "n_anomalies": n_anomalies,
            "n_missing": n_missing,
            "window": f"{start_date}..{end_date}",
        }
    except Exception as exc:
        logger.warning("DataAuditor.audit_daily_files failed: %s", exc)
        return {
            "label": "DataAuditor.audit_daily_files",
            "ok": False,
            "exit_code": 1,
            "error": str(exc),
        }


def main() -> int:
    python = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable

    checks = []

    # 1. DataAuditor
    checks.append(_audit_daily_files_inprocess())

    # 2. audit_qlib smoke
    checks.append(
        _run(
            [python, "scripts/audit_qlib.py", "--sample-size", "30"],
            "audit_qlib",
        )
    )

    # 3. Provider boundary regression
    checks.append(
        _run(
            [python, "-m", "pytest", "tests/data_infra/test_provider_boundary.py", "-q"],
            "provider_boundary_tests",
        )
    )

    # 4. PIT live harness
    checks.append(
        _run(
            [python, "-m", "pytest", "tests/data_infra/test_pit_live_provider.py", "-q"],
            "pit_live_harness",
        )
    )

    # Report
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = LOGS_DIR / f"qa_report_{timestamp}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(
            {"timestamp": timestamp, "checks": checks},
            f,
            ensure_ascii=False,
            indent=2,
        )

    # Markdown summary to stdout
    all_ok = all(c["ok"] for c in checks)
    print()
    print("# Daily QA Report")
    print()
    print(f"**Timestamp**: {timestamp}")
    print(f"**Overall**: {'PASS' if all_ok else 'FAIL'}")
    print(f"**Report**: {report_path}")
    print()
    print("## Checks")
    print()
    for c in checks:
        status = "PASS" if c["ok"] else "FAIL"
        print(f"- **{c['label']}**: {status}")
        if not c["ok"]:
            tail = c.get("stdout_tail", []) or c.get("error", "")
            if tail:
                print(f"  - tail: `{tail[-3:] if isinstance(tail, list) else tail}`")
    print()

    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
