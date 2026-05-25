import json
import shutil
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

import workspace.scripts.research_orchestrator_audit as orch_audit


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ResearchOrchestratorAuditTests(unittest.TestCase):
    @contextmanager
    def make_temp_dir(self, name: str):
        outputs_root = PROJECT_ROOT / "workspace" / "outputs"
        outputs_root.mkdir(parents=True, exist_ok=True)
        temp_root = outputs_root / f"{name}_{uuid.uuid4().hex[:8]}"
        if temp_root.exists():
            shutil.rmtree(temp_root, ignore_errors=True)
        temp_root.mkdir(parents=True, exist_ok=True)
        try:
            yield str(temp_root)
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_compile_profile_step_rows_covers_all_builtin_profiles(self):
        with self.make_temp_dir("orch_audit_compile") as temp_dir:
            rows = orch_audit.compile_profile_step_rows(Path(temp_dir))
        profiles = {row["profile_id"] for row in rows}
        self.assertEqual(
            profiles,
            {
                "factor_screening",
                "theme_strategy",
                "event_driven_signal_research",
                "ml_signal_model_research",
                "strategy_improvement",
                "benchmark_audit",
            },
        )
        self.assertTrue(all(row["capability_declared"] for row in rows))
        self.assertEqual(orch_audit.build_noop_gap_findings(rows), [])

    def test_compile_requests_attach_formal_hypotheses_except_benchmark(self):
        with self.make_temp_dir("orch_audit_hypotheses") as temp_dir:
            requests = orch_audit._build_compile_requests(Path(temp_dir))

        for profile_id, request in requests.items():
            if profile_id == "benchmark_audit":
                self.assertIsNone(request.hypothesis)
            else:
                self.assertIsNotNone(request.hypothesis)
                request.hypothesis.validate()

    def test_scan_source_forbidden_patterns_detects_matches(self):
        with self.make_temp_dir("orch_audit_scan") as temp_dir:
            temp_root = Path(temp_dir)
            test_file = temp_root / "bad.py"
            test_file.write_text("legacy_profile_runner = True\n", encoding="utf-8")
            matches = orch_audit.scan_source_forbidden_patterns(temp_root)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["token"], "legacy_profile_runner")

    def test_verify_utf8_file_accepts_utf8_content(self):
        with self.make_temp_dir("orch_audit_utf8") as temp_dir:
            path = Path(temp_dir) / "sample.md"
            path.write_text("研究编排器审计\n", encoding="utf-8")
            status = orch_audit.verify_utf8_file(path)
        self.assertTrue(status["utf8_valid"])
        self.assertFalse(status["contains_replacement_char"])

    def test_collect_run_artifact_issues_and_produced_object_violations(self):
        with self.make_temp_dir("orch_audit_run") as temp_dir:
            run_dir = Path(temp_dir) / "run"
            (run_dir / "steps" / "signal_search").mkdir(parents=True, exist_ok=True)
            (run_dir / "steps" / "registry_publish").mkdir(parents=True, exist_ok=True)
            (run_dir / "dag_plan.json").write_text(
                json.dumps(
                    {
                        "steps": [
                            {"step_id": "signal_search", "capability": "signal_search"},
                            {"step_id": "registry_publish", "capability": "registry_publish"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (run_dir / "dag_state.json").write_text(
                json.dumps(
                    {
                        "steps": [
                            {"step_id": "signal_search", "status": "completed"},
                            {"step_id": "registry_publish", "status": "completed"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            for name in (
                "run_metadata.json",
                "artifact_manifest.json",
                "review_summary.json",
                "produced_objects.json",
            ):
                (run_dir / name).write_text("{}", encoding="utf-8")
            (run_dir / "steps" / "signal_search" / "step_metadata.json").write_text("{}", encoding="utf-8")
            (run_dir / "steps" / "signal_search" / "step_outputs.json").write_text(
                json.dumps({"produced_objects": [{"object_id": "bad"}]}),
                encoding="utf-8",
            )
            (run_dir / "steps" / "signal_search" / "artifact_manifest.json").write_text("{}", encoding="utf-8")
            (run_dir / "steps" / "registry_publish" / "step_metadata.json").write_text("{}", encoding="utf-8")
            (run_dir / "steps" / "registry_publish" / "step_outputs.json").write_text(
                json.dumps({"produced_objects": [{"object_id": "good"}]}),
                encoding="utf-8",
            )
            (run_dir / "steps" / "registry_publish" / "artifact_manifest.json").write_text("{}", encoding="utf-8")

            issues = orch_audit.collect_run_artifact_issues(run_dir)
            violations = orch_audit.collect_produced_object_violations(run_dir)

        self.assertFalse(issues)
        self.assertEqual(violations, ["produced_objects_outside_registry_publish:signal_search"])

    def test_build_noop_gap_findings_flags_semantic_noop(self):
        findings = orch_audit.build_noop_gap_findings(
            [
                {
                    "profile_id": "theme_strategy",
                    "step_id": "vectorized_backtest",
                    "capability": "vectorized_backtest",
                    "handler_is_noop": True,
                },
                {
                    "profile_id": "benchmark_audit",
                    "step_id": "benchmark_audit",
                    "capability": "benchmark_audit",
                    "handler_is_noop": False,
                },
            ]
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].finding_id, "F001")

    def test_build_capability_contract_findings_flags_mismatch(self):
        findings = orch_audit.build_capability_contract_findings(
            [
                {
                    "profile_id": "strategy_improvement",
                    "step_id": "dataset_build",
                    "capability": "dataset_build",
                    "capability_declared": False,
                }
            ]
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].finding_id, "F004")


if __name__ == "__main__":
    unittest.main()
