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


def _provider_manifest_check() -> dict:
    """Validate the local provider_build.json against the live Qlib calendar.

    PR 1: Formal runs require the manifest; daily QA fails loudly if it is
    missing or inconsistent with the on-disk provider.
    """
    try:
        sys.path.insert(0, str(PROJECT_ROOT / "src"))
        # Resolve qlib_dir from config.yaml's storage block.
        import yaml as _yaml
        with open(PROJECT_ROOT / "config.yaml", "r", encoding="utf-8") as handle:
            config = _yaml.safe_load(handle) or {}
        storage = config.get("storage", {})
        qlib_dir = storage.get("qlib_data_dir", "./data/qlib_data")
        if not Path(qlib_dir).is_absolute():
            qlib_dir = str(PROJECT_ROOT / qlib_dir.lstrip("./"))

        from data_infra.provider_manifest import (
            load_provider_manifest,
            validate_provider_manifest_against_qlib,
        )
        from research_orchestrator.calendar_policy import load_calendar_policy

        manifest = load_provider_manifest(qlib_dir)

        # Read live calendar end-date directly from the file.
        calendar_path = Path(qlib_dir) / "calendars" / "day.txt"
        with open(calendar_path, "r", encoding="utf-8") as handle:
            cal_lines = [line.strip() for line in handle if line.strip()]
        live_calendar_end = cal_lines[-1] if cal_lines else ""

        # Cross-check against the calendar policy.
        policy = load_calendar_policy(manifest.calendar_policy_id)

        # PR 8a fix #3: daily QA must enforce the same semantics as the
        # formal-runtime validator. The pre-PR-8a behavior of
        # `allow_mismatch = policy.frozen` was too broad — it permitted ANY
        # mismatch as long as the policy was frozen. The correct semantics
        # are: frozen policies require strict equality between manifest /
        # policy / live calendar; non-frozen policies use max_calendar_lag.
        if policy.frozen:
            if live_calendar_end != policy.calendar_end_date:
                raise RuntimeError(
                    f"Frozen calendar policy {policy.policy_id!r} declares "
                    f"calendar_end_date={policy.calendar_end_date} but the "
                    f"local Qlib calendar ends at {live_calendar_end}. "
                    "Rebuild the provider or load a non-frozen policy."
                )
            if manifest.provider.calendar_end_date != policy.calendar_end_date:
                raise RuntimeError(
                    f"Manifest calendar_end_date={manifest.provider.calendar_end_date} "
                    f"does not match frozen policy {policy.policy_id!r} "
                    f"calendar_end_date={policy.calendar_end_date}."
                )
            validate_provider_manifest_against_qlib(
                manifest, live_calendar_end, allow_calendar_mismatch=False,
            )
        else:
            validate_provider_manifest_against_qlib(
                manifest, live_calendar_end, allow_calendar_mismatch=False,
            )

        return {
            "label": "provider_manifest_check",
            "ok": True,
            "exit_code": 0,
            "provider_build_id": manifest.provider_build_id,
            "calendar_policy_id": manifest.calendar_policy_id,
            "calendar_end_date": manifest.provider.calendar_end_date,
            "live_calendar_end": live_calendar_end,
            "retroactive_manifest": manifest.retroactive_manifest,
            "namespacing_status": manifest.event_endpoint_namespacing.status,
        }
    except Exception as exc:
        logger.warning("provider_manifest_check failed: %s", exc)
        return {
            "label": "provider_manifest_check",
            "ok": False,
            "exit_code": 1,
            "error": str(exc),
        }


def _approval_evidence_binding_check() -> dict:
    """PR 10 follow-up: scan config/field_registry/approvals/*.yaml and
    verify each binding (provider_build_id + calendar_policy_id) matches
    the current data/qlib_data/metadata/provider_build.json.

    A drift means an approval's on-disk evidence was verified against a
    different provider build than the one currently published. The
    approval must be re-verified before formal use of the affected
    dataset's fields. See PR 9a round-3's indicators approval YAML for
    the binding contract.
    """
    try:
        sys.path.insert(0, str(PROJECT_ROOT / "src"))
        from data_infra.approval_evidence import (
            evaluate_approval_evidence_bindings,
        )

        approvals_dir = PROJECT_ROOT / "config" / "field_registry" / "approvals"
        manifest_path = (
            PROJECT_ROOT / "data" / "qlib_data" / "metadata" / "provider_build.json"
        )
        drifts = evaluate_approval_evidence_bindings(
            approvals_dir=approvals_dir, manifest_path=manifest_path,
        )
        n_total = len(drifts)
        drifted = [d for d in drifts if d.drift]
        n_drifted = len(drifted)
        ok = n_drifted == 0
        reasons = [r for d in drifted for r in d.reasons()]
        return {
            "label": "approval_evidence_binding",
            "ok": ok,
            "exit_code": 0 if ok else 1,
            "n_approvals_with_binding": n_total,
            "n_drifted": n_drifted,
            "drifted_approvals": [d.binding.approval_id for d in drifted],
            "reasons": reasons[:10],  # keep the report compact
        }
    except Exception as exc:  # noqa: BLE001 — defensive in QA runner
        logger.warning("approval_evidence_binding check failed: %s", exc)
        return {
            "label": "approval_evidence_binding",
            "ok": False,
            "exit_code": 1,
            "error": str(exc),
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

    # 0. Provider manifest (PR 1) — runs first so downstream checks can rely
    # on a known calendar_policy_id and provider_build_id being recorded.
    checks.append(_provider_manifest_check())

    # 0a. No-bare-Qlib-features lint (PR 6) — banned outside the canonical
    # wrapper so the ResearchAccessContext can enforce window/seal/field
    # constraints at the data-access layer.
    checks.append(
        _run(
            [python, "scripts/lint_no_bare_qlib_features.py", "src/"],
            "no_bare_qlib_features_lint",
        )
    )

    # 0b. Approval-evidence binding drift (PR 10 follow-up to PR 9c) —
    # every field-registry approval YAML pins a provider_build_id +
    # calendar_policy_id; this check ensures the current provider build
    # has not drifted from any approval's binding without an explicit
    # re-verification.
    checks.append(_approval_evidence_binding_check())

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
