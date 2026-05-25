import csv
import json
import shutil
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import workspace.scripts.research_orchestrator_release_gate as release_gate_cli
from src.research_orchestrator.release_gate import (
    ReleaseGateResult,
    evaluate_audit_root,
    run_release_gate,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ResearchOrchestratorReleaseGateTests(unittest.TestCase):
    @contextmanager
    def make_temp_dir(self, name: str):
        outputs_root = PROJECT_ROOT / "workspace" / "outputs"
        outputs_root.mkdir(parents=True, exist_ok=True)
        temp_root = outputs_root / f"{name}_{uuid.uuid4().hex[:8]}"
        if temp_root.exists():
            shutil.rmtree(temp_root, ignore_errors=True)
        temp_root.mkdir(parents=True, exist_ok=True)
        try:
            yield temp_root
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def _write_audit_files(
        self,
        audit_root: Path,
        *,
        findings: list[dict[str, str]] | None = None,
        coverage: list[dict[str, str]] | None = None,
    ) -> None:
        audit_root.mkdir(parents=True, exist_ok=True)
        findings_rows = findings or []
        coverage_rows = coverage or [{"area": "tests", "check_id": "unit", "status": "passed", "evidence": "ok", "notes": ""}]
        with (audit_root / "findings.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["finding_id", "severity", "status", "area", "title", "file", "summary", "evidence"],
            )
            writer.writeheader()
            for row in findings_rows:
                writer.writerow(row)
        with (audit_root / "coverage_matrix.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["area", "check_id", "status", "evidence", "notes"])
            writer.writeheader()
            for row in coverage_rows:
                writer.writerow(row)
        (audit_root / "audit_report_zh.md").write_text("# report\n", encoding="utf-8")

    def test_evaluate_audit_root_passes_when_findings_empty_and_all_checks_pass(self):
        with self.make_temp_dir("release_gate_pass") as temp_dir:
            audit_root = temp_dir / "audit"
            self._write_audit_files(audit_root)
            result = evaluate_audit_root(gate_root=temp_dir, audit_root=audit_root)

        self.assertEqual(result.status, "passed")
        self.assertEqual(result.findings_total, 0)
        self.assertEqual(result.coverage_non_passed, 0)

    def test_evaluate_audit_root_fails_on_open_finding(self):
        with self.make_temp_dir("release_gate_finding") as temp_dir:
            audit_root = temp_dir / "audit"
            self._write_audit_files(
                audit_root,
                findings=[
                    {
                        "finding_id": "F001",
                        "severity": "P2",
                        "status": "open",
                        "area": "runtime",
                        "title": "gap",
                        "file": "x.py",
                        "summary": "bad",
                        "evidence": "x",
                    }
                ],
            )
            result = evaluate_audit_root(gate_root=temp_dir, audit_root=audit_root)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.open_findings, 1)
        self.assertTrue(result.blocking_findings)

    def test_evaluate_audit_root_fails_on_non_passed_coverage(self):
        with self.make_temp_dir("release_gate_coverage") as temp_dir:
            audit_root = temp_dir / "audit"
            self._write_audit_files(
                audit_root,
                coverage=[
                    {
                        "area": "runtime",
                        "check_id": "resume",
                        "status": "warning",
                        "evidence": "resume.log",
                        "notes": "not closed",
                    }
                ],
            )
            result = evaluate_audit_root(gate_root=temp_dir, audit_root=audit_root)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.coverage_non_passed, 1)
        self.assertTrue(result.blocking_checks)

    def test_run_release_gate_writes_summary_report_and_latest_pointer(self):
        with self.make_temp_dir("release_gate_run") as temp_dir:
            gate_root = temp_dir / "gate"

            def fake_audit_runner(*, output_dir: Path, theme_run_dir: Path | None = None) -> Path:
                self._write_audit_files(output_dir)
                return output_dir

            result = run_release_gate(gate_root=gate_root, audit_runner=fake_audit_runner)

            summary_path = gate_root / "release_gate_summary.json"
            report_path = gate_root / "release_gate_report_zh.md"
            latest_path = gate_root.parent / "latest_run.json"

            self.assertEqual(result.status, "passed")
            self.assertTrue(summary_path.exists())
            self.assertTrue(report_path.exists())
            self.assertTrue(latest_path.exists())
            summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary_payload["status"], "passed")

    def test_cli_main_returns_zero_on_pass(self):
        fake_result = ReleaseGateResult(
            gate_root="E:/gate",
            audit_root="E:/gate/audit",
            status="passed",
            generated_at="2026-04-10 12:00:00",
            findings_total=0,
            open_findings=0,
            risk_findings=0,
            coverage_total=3,
            coverage_passed=3,
            coverage_non_passed=0,
            blocking_findings=[],
            blocking_checks=[],
            notes=[],
        )
        with patch.object(release_gate_cli, "run_release_gate", return_value=fake_result):
            exit_code = release_gate_cli.main(["--output-dir", str(PROJECT_ROOT / "workspace" / "outputs" / "dummy_gate")])
        self.assertEqual(exit_code, 0)

    def test_cli_main_returns_one_on_fail(self):
        fake_result = ReleaseGateResult(
            gate_root="E:/gate",
            audit_root="E:/gate/audit",
            status="failed",
            generated_at="2026-04-10 12:00:00",
            findings_total=1,
            open_findings=1,
            risk_findings=0,
            coverage_total=3,
            coverage_passed=2,
            coverage_non_passed=1,
            blocking_findings=["F001:P2:gap"],
            blocking_checks=["resume:warning:not closed"],
            notes=[],
        )
        with patch.object(release_gate_cli, "run_release_gate", return_value=fake_result):
            exit_code = release_gate_cli.main(["--output-dir", str(PROJECT_ROOT / "workspace" / "outputs" / "dummy_gate")])
        self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
