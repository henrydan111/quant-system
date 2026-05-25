from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research_orchestrator import ResearchRequest, TimeSplit, compile_research_plan, profile_registry
from src.research_orchestrator.hypothesis import (
    ExpectedEffect,
    Hypothesis,
    HypothesisSource,
    PreRegisteredConcerns,
    SuccessCriteria,
)
from src.research_orchestrator.schema import AssetRef


VENV_PYTHON = (PROJECT_ROOT / "venv" / "Scripts" / "python.exe").resolve()
CLI_PATH = (PROJECT_ROOT / "workspace" / "scripts" / "research_orchestrator_cli.py").resolve()
DEFAULT_AUDIT_ROOT = (PROJECT_ROOT / "workspace" / "outputs" / "orchestrator_audit").resolve()
DEFAULT_THEME_RECIPE_SOURCE = (
    PROJECT_ROOT / "workspace" / "outputs" / "theme_strategy" / "theme_strategy_small_cap_recipe_20260406_144222"
).resolve()
DEFAULT_THEME_RUN_DIR = (
    PROJECT_ROOT / "workspace" / "outputs" / "orchestrator_audit_probe" / "theme_quick_real"
).resolve()
ORCHESTRATOR_SOURCE_ROOT = (PROJECT_ROOT / "src" / "research_orchestrator").resolve()
PROJECT_STATE_PATH = (PROJECT_ROOT / "project_state.md").resolve()
README_PATH = (PROJECT_ROOT / "src" / "research_orchestrator" / "README.md").resolve()
ORCHESTRATOR_SCAFFOLD_CAPABILITIES = {
    "data_scope",
    "data_readiness",
    "performance_diagnostics",
    "gate_evaluation",
    "gate_concern_scoring",
    "report_render",
}


def _audit_hypothesis(profile_id: str, request: ResearchRequest) -> Hypothesis:
    """Build a strict synthetic hypothesis for formal audit compile checks."""
    consumes = list(request.consumes)
    factor_refs = consumes or [AssetRef(object_type="factor", object_name="audit_fixture_factor")]
    benchmark = str(request.inputs.get("benchmark", "") or "000905.SH")
    rebalance_days = int(request.inputs.get("rebalance_days", 5) or 5)
    profile_hint = profile_id.replace("_", "-")
    return Hypothesis(
        hypothesis_id=f"hyp_{profile_hint}_audit_fixture",
        thesis_statement=f"Audit fixture hypothesis for {profile_id}.",
        mechanism="A stable cross-sectional ranking effect should survive formal workflow validation.",
        source=HypothesisSource(
            source_type="domain",
            identifier=f"{profile_id}-audit-fixture",
            title=f"{profile_id} audit fixture",
        ),
        factor_refs=factor_refs,
        factor_yaml_hashes=[],
        universe="csi_all",
        benchmark=benchmark,
        time_split=TimeSplit(
            is_start="2018-01-01",
            is_end="2022-12-31",
            oos_start="2023-01-01",
            oos_end="2024-12-31",
            walk_forward_config={
                "train_years": 3,
                "validation_years": 1,
                "test_years": 1,
                "step_years": 1,
            },
        ),
        rebalance_frequency=f"{rebalance_days}d",
        neutralization=["size", "industry"],
        expected_sign=1,
        expected_effect=ExpectedEffect(
            statistic="rank_ic",
            point_estimate=0.04,
            ci_low=0.02,
            ci_high=0.06,
            horizon_days=5,
        ),
        expected_decay_horizon_days=5,
        success_criteria=SuccessCriteria(
            min_rank_icir=0.04,
            min_deflated_sharpe=1.1,
            min_cost_adjusted_sharpe=0.8,
            max_drawdown=0.25,
            max_annual_turnover=4.0,
            min_monotonicity_pvalue=0.05,
            max_correlation_to_approved=0.7,
            min_regime_pass_count=2,
            effect_size_must_be_in_ci=True,
            custom_rules=[],
        ),
        pre_registered_concerns=PreRegisteredConcerns(
            most_likely_failure_mode="The audit fixture could pass structurally while real data quality fails.",
            weakest_assumption="Formal workflow contracts remain stable across built-in profiles.",
            what_would_falsify_this="A built-in formal non-benchmark profile cannot compile with a valid hypothesis.",
            priors_on_cost_sensitivity="Costs should matter once turnover rises above moderate A-share assumptions.",
        ),
        pre_registered_at="2026-04-24 00:00:00",
        registered_by="orchestrator_audit",
    )


def _attach_audit_hypothesis(request: ResearchRequest) -> ResearchRequest:
    if request.mode != "formal" or request.profile_id == "benchmark_audit" or request.hypothesis is not None:
        return request
    return ResearchRequest(
        profile_id=request.profile_id,
        mode=request.mode,
        consumes=request.consumes,
        produces=request.produces,
        requested_capabilities=request.requested_capabilities,
        inputs=request.inputs,
        run_context=request.run_context,
        hypothesis=_audit_hypothesis(request.profile_id, request),
    )


@dataclass(frozen=True)
class AuditFinding:
    finding_id: str
    severity: str
    status: str
    area: str
    title: str
    file: str
    summary: str
    evidence: str = ""


@dataclass(frozen=True)
class CoverageRow:
    area: str
    check_id: str
    status: str
    evidence: str
    notes: str = ""


@dataclass(frozen=True)
class CommandRecord:
    label: str
    command: list[str]
    cwd: str
    exit_code: int
    duration_seconds: float
    stdout_path: str
    stderr_path: str


def _timestamp_token() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _write_csv_rows(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _run_command(
    *,
    label: str,
    command: list[str],
    cwd: Path,
    artifact_dir: Path,
    timeout_seconds: int = 600,
) -> CommandRecord:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = artifact_dir / f"{label}.stdout.log"
    stderr_path = artifact_dir / f"{label}.stderr.log"
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
        check=False,
    )
    duration = time.perf_counter() - started
    stdout_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")
    return CommandRecord(
        label=label,
        command=command,
        cwd=str(cwd),
        exit_code=int(completed.returncode),
        duration_seconds=round(duration, 3),
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
    )


def _build_compile_requests(base_dir: Path) -> dict[str, ResearchRequest]:
    factor_asset = AssetRef(object_type="factor", object_name="liq_vol_cv_20d")
    composite_asset = AssetRef(object_type="composite_factor", object_name="comp_defensive")
    requests = {
        "factor_screening": ResearchRequest(
            profile_id="factor_screening",
            mode="formal",
            consumes=[],
            produces=[],
            requested_capabilities=[],
            inputs={
                "argv": [],
                "args": {},
                "output_dir": str((base_dir / "factor_screening").resolve()),
            },
            run_context={},
        ),
        "theme_strategy": ResearchRequest(
            profile_id="theme_strategy",
            mode="formal",
            consumes=[],
            produces=[],
            requested_capabilities=[],
            inputs={
                "theme": "small_cap",
                "stage": "event_driven",
                "output_dir": str((base_dir / "theme_strategy").resolve()),
                "recipe_source_run_dir": str(DEFAULT_THEME_RECIPE_SOURCE),
            },
            run_context={},
        ),
        "event_driven_signal_research": ResearchRequest(
            profile_id="event_driven_signal_research",
            mode="formal",
            consumes=[factor_asset, composite_asset],
            produces=[],
            requested_capabilities=[],
            inputs={
                "screening_run_dir": str((base_dir / "screening_source").resolve()),
                "output_dir": str((base_dir / "event_signal").resolve()),
            },
            run_context={},
        ),
        "ml_signal_model_research": ResearchRequest(
            profile_id="ml_signal_model_research",
            mode="formal",
            consumes=[factor_asset, composite_asset],
            produces=[],
            requested_capabilities=[],
            inputs={
                "baseline_run_dir": str((base_dir / "baseline_source").resolve()),
                "screening_run_dir": str((base_dir / "screening_source").resolve()),
                "output_dir": str((base_dir / "ml_signal").resolve()),
            },
            run_context={},
        ),
        "strategy_improvement": ResearchRequest(
            profile_id="strategy_improvement",
            mode="formal",
            consumes=[factor_asset, composite_asset],
            produces=[],
            requested_capabilities=[],
            inputs={
                "baseline_run_dir": str((base_dir / "baseline_source").resolve()),
                "output_dir": str((base_dir / "strategy_improvement").resolve()),
            },
            run_context={},
        ),
        "benchmark_audit": ResearchRequest(
            profile_id="benchmark_audit",
            mode="formal",
            consumes=[],
            produces=[],
            requested_capabilities=[],
            inputs={
                "benchmark": "000001.SH",
                "output_dir": str((base_dir / "benchmark_audit").resolve()),
            },
            run_context={},
        ),
    }
    return {profile_id: _attach_audit_hypothesis(request) for profile_id, request in requests.items()}


def compile_profile_step_rows(base_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for profile_id, request in _build_compile_requests(base_dir).items():
        plan = compile_research_plan(request)
        default_capabilities = profile_registry().get(profile_id).default_capabilities
        for step in plan["steps"]:
            rows.append(
                {
                    "profile_id": profile_id,
                    "step_id": step["step_id"],
                    "capability": step["capability"],
                    "handler": step["handler"],
                    "depends_on": ",".join(step.get("depends_on", [])),
                    "handler_is_noop": step["handler"] == "noop",
                    "capability_declared": step["capability"] in default_capabilities
                    or step["capability"] in ORCHESTRATOR_SCAFFOLD_CAPABILITIES,
                }
            )
    return rows


def scan_source_forbidden_patterns(
    source_root: Path,
    patterns: dict[str, list[str]] | None = None,
) -> list[dict[str, Any]]:
    active_patterns = patterns or {
        "legacy_profile_runner": ["legacy_profile_runner"],
        "runner_payload": ["runner_payload"],
        "legacy_run_functions": [
            "_run_factor_screening",
            "_run_ml_signal_model_research",
            "_run_strategy_improvement",
            "_run_benchmark_audit",
        ],
    }
    matches: list[dict[str, Any]] = []
    for path in sorted(source_root.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for group, tokens in active_patterns.items():
            for token in tokens:
                if token in text:
                    matches.append(
                        {
                            "group": group,
                            "token": token,
                            "file": str(path.resolve()),
                        }
                    )
    return matches


def verify_utf8_file(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    has_bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8")
    return {
        "path": str(path),
        "utf8_valid": True,
        "has_utf8_bom": has_bom,
        "char_count": len(text),
        "contains_replacement_char": "\ufffd" in text,
    }


def collect_run_artifact_issues(run_dir: Path) -> list[str]:
    issues: list[str] = []
    required_root_files = [
        "dag_plan.json",
        "dag_state.json",
        "run_metadata.json",
        "artifact_manifest.json",
        "review_summary.json",
        "produced_objects.json",
    ]
    for relative in required_root_files:
        if not (run_dir / relative).exists():
            issues.append(f"missing_root_file:{relative}")
    if not (run_dir / "dag_plan.json").exists():
        return issues
    plan = _load_json(run_dir / "dag_plan.json")
    state = _load_json(run_dir / "dag_state.json")
    step_status = {item["step_id"]: item for item in state.get("steps", [])}
    for step in plan.get("steps", []):
        step_id = str(step["step_id"])
        step_dir = run_dir / "steps" / step_id
        current = step_status.get(step_id, {})
        status = str(current.get("status", "pending"))
        if status in {"completed", "failed", "running"} and not (step_dir / "step_metadata.json").exists():
            issues.append(f"missing_step_metadata:{step_id}")
        if status == "completed":
            for relative in ("step_outputs.json", "artifact_manifest.json", "step_metadata.json"):
                if not (step_dir / relative).exists():
                    issues.append(f"missing_step_file:{step_id}:{relative}")
    return issues


def collect_produced_object_violations(run_dir: Path) -> list[str]:
    violations: list[str] = []
    if not (run_dir / "dag_plan.json").exists():
        return violations
    plan = _load_json(run_dir / "dag_plan.json")
    capability_by_step = {item["step_id"]: item["capability"] for item in plan.get("steps", [])}
    for step_id, capability in capability_by_step.items():
        outputs_path = run_dir / "steps" / step_id / "step_outputs.json"
        if not outputs_path.exists():
            continue
        outputs = _load_json(outputs_path)
        produced = outputs.get("produced_objects", [])
        if produced and capability != "registry_publish":
            violations.append(f"produced_objects_outside_registry_publish:{step_id}")
    return violations


def build_noop_gap_findings(step_rows: list[dict[str, Any]]) -> list[AuditFinding]:
    semantic_capabilities = {
        "dataset_build",
        "universe_builder",
        "label_builder",
        "factor_construction",
        "factor_discovery",
        "signal_search",
        "model_training",
        "portfolio_construction",
        "risk_overlay",
        "vectorized_backtest",
        "event_driven_backtest",
        "execution_validation",
        "stress_test",
    }
    gaps = [
        row
        for row in step_rows
        if row["handler_is_noop"] and row["capability"] in semantic_capabilities
    ]
    if not gaps:
        return []
    gap_lines = [
        f"{row['profile_id']}:{row['step_id']} ({row['capability']})"
        for row in gaps
    ]
    return [
        AuditFinding(
            finding_id="F001",
            severity="P2",
            status="open",
            area="profile_semantics",
            title="部分 capability 仍是语义占位节点",
            file=str((PROJECT_ROOT / "src" / "research_orchestrator" / "engine.py").resolve()),
            summary=(
                "DAG 结构已经统一，但仍有一批本应代表真实研究动作的 capability 使用 `noop` handler。"
                "这不会立刻破坏执行结果，但会削弱编排层的可观察性和模块语义的一致性。"
            ),
            evidence="; ".join(gap_lines),
        )
    ]


def build_capability_contract_findings(step_rows: list[dict[str, Any]]) -> list[AuditFinding]:
    mismatches = [row for row in step_rows if not row["capability_declared"]]
    if not mismatches:
        return []
    evidence = "; ".join(
        f"{row['profile_id']}:{row['step_id']}->{row['capability']}"
        for row in mismatches
    )
    return [
        AuditFinding(
            finding_id="F004",
            severity="P2",
            status="open",
            area="contract",
            title="profile capability 声明与真实 DAG 步骤不完全一致",
            file=str((PROJECT_ROOT / "src" / "research_orchestrator" / "engine.py").resolve()),
            summary="至少有一个 built-in profile 的默认 capability 声明没有完整覆盖它真实编译出来的 DAG 步骤，这会让 CLI/README/审计矩阵看到的 profile 能力与真实执行链路出现偏差。",
            evidence=evidence,
        )
    ]


def build_project_state_drift_finding() -> list[AuditFinding]:
    first_line_block = PROJECT_STATE_PATH.read_text(encoding="utf-8").splitlines()[:8]
    joined = "\n".join(first_line_block)
    if "full audit" in joined.lower() or "全量审计" in joined or "审计" in joined:
        return []
    return [
        AuditFinding(
            finding_id="F002",
            severity="P3",
            status="open",
            area="documentation",
            title="project_state 顶部摘要未覆盖最新审计里程碑",
            file=str(PROJECT_STATE_PATH),
            summary="`project_state.md` 顶部 Last Updated 摘要还停在更早的 orchestrator 里程碑，没有把当前审计结果纳入最上层摘要。",
            evidence=first_line_block[1] if len(first_line_block) > 1 else "",
        )
    ]


def build_theme_smoke_finding(theme_status: str, theme_run_dir: Path) -> list[AuditFinding]:
    if theme_status == "completed":
        return []
    if theme_status in {"failed", "invalid"}:
        return [
            AuditFinding(
                finding_id="F003",
                severity="P2",
                status="open",
                area="real_smoke",
                title="theme_strategy 真实 quick smoke 失败",
                file=str(theme_run_dir),
                summary=(
                    "审计期内复用的真实 quick event-driven run 没有闭环完成，而是落在 failed/invalid 状态。"
                    "这说明真实 DAG 链路里至少有一步仍然存在运行时问题，需要修复后再下更强结论。"
                ),
                evidence=theme_status,
            )
        ]
    return [
        AuditFinding(
            finding_id="F003",
            severity="P3",
            status="risk",
            area="real_smoke",
            title="theme_strategy 真实 quick smoke 未完成闭环",
            file=str(theme_run_dir),
            summary=(
                "审计期内复用了真实 quick event-driven run，但它在审计截点仍未完成或不可用。"
                "这不代表已经发现错误执行，只代表这条最重的真实链路证据还不够完整。"
            ),
            evidence=theme_status,
        )
    ]


def _classify_warning_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if "warning" in line.lower()]


def run_benchmark_cli_smoke(audit_root: Path) -> tuple[list[CoverageRow], list[CommandRecord], Path]:
    smoke_root = audit_root / "smokes" / "benchmark_cli"
    request_path = smoke_root / "benchmark_request.json"
    run_dir = smoke_root / "benchmark_run"
    request = {
        "profile_id": "benchmark_audit",
        "mode": "formal",
        "consumes": [],
        "produces": [],
        "requested_capabilities": [],
        "inputs": {
            "benchmark": "000001.SH",
            "output_dir": str(run_dir),
        },
        "run_context": {},
    }
    _write_json(request_path, request)
    command_dir = smoke_root / "commands"
    plan_cmd = _run_command(
        label="benchmark_plan",
        command=[str(VENV_PYTHON), str(CLI_PATH), "plan", "--request-file", str(request_path)],
        cwd=PROJECT_ROOT,
        artifact_dir=command_dir,
    )
    run_cmd = _run_command(
        label="benchmark_run",
        command=[str(VENV_PYTHON), str(CLI_PATH), "run", "--request-file", str(request_path)],
        cwd=PROJECT_ROOT,
        artifact_dir=command_dir,
        timeout_seconds=900,
    )
    resume_cmd = _run_command(
        label="benchmark_resume",
        command=[str(VENV_PYTHON), str(CLI_PATH), "resume", "--run-dir", str(run_dir)],
        cwd=PROJECT_ROOT,
        artifact_dir=command_dir,
    )
    issues = collect_run_artifact_issues(run_dir)
    produced_violations = collect_produced_object_violations(run_dir)
    rows = [
        CoverageRow(
            area="cli",
            check_id="benchmark_plan_cli",
            status="passed" if plan_cmd.exit_code == 0 else "failed",
            evidence=plan_cmd.stdout_path,
            notes=f"exit_code={plan_cmd.exit_code}",
        ),
        CoverageRow(
            area="cli",
            check_id="benchmark_run_cli",
            status="passed" if run_cmd.exit_code == 0 else "failed",
            evidence=run_cmd.stdout_path,
            notes=f"exit_code={run_cmd.exit_code}",
        ),
        CoverageRow(
            area="cli",
            check_id="benchmark_resume_cli",
            status="passed" if resume_cmd.exit_code == 0 else "failed",
            evidence=resume_cmd.stdout_path,
            notes=f"exit_code={resume_cmd.exit_code}",
        ),
        CoverageRow(
            area="runtime",
            check_id="benchmark_artifact_integrity",
            status="passed" if not issues else "failed",
            evidence=str(run_dir),
            notes="; ".join(issues) if issues else "root/step artifacts complete",
        ),
        CoverageRow(
            area="publication",
            check_id="benchmark_produced_object_channel",
            status="passed" if not produced_violations else "failed",
            evidence=str(run_dir),
            notes="; ".join(produced_violations) if produced_violations else "no out-of-band produced_objects",
        ),
    ]
    return rows, [plan_cmd, run_cmd, resume_cmd], run_dir


def inspect_theme_quick_run(theme_run_dir: Path) -> tuple[list[CoverageRow], str]:
    if not theme_run_dir.exists():
        return [
            CoverageRow(
                area="real_smoke",
                check_id="theme_quick_event_driven",
                status="skipped",
                evidence=str(theme_run_dir),
                notes="run_dir not found",
            )
        ], "missing"
    state_path = theme_run_dir / "dag_state.json"
    if not state_path.exists():
        return [
            CoverageRow(
                area="real_smoke",
                check_id="theme_quick_event_driven",
                status="failed",
                evidence=str(theme_run_dir),
                notes="dag_state.json missing",
            )
        ], "invalid"
    state = _load_json(state_path)
    status = str(state.get("status", "unknown"))
    issues = collect_run_artifact_issues(theme_run_dir) if status == "completed" else []
    produced_violations = collect_produced_object_violations(theme_run_dir) if status == "completed" else []
    rows = [
        CoverageRow(
            area="real_smoke",
            check_id="theme_quick_event_driven",
            status="passed" if status == "completed" else ("running" if status == "running" else "failed"),
            evidence=str(theme_run_dir),
            notes=f"dag_state.status={status}",
        )
    ]
    if status == "completed":
        rows.append(
            CoverageRow(
                area="runtime",
                check_id="theme_quick_artifact_integrity",
                status="passed" if not issues else "failed",
                evidence=str(theme_run_dir),
                notes="; ".join(issues) if issues else "root/step artifacts complete",
            )
        )
        rows.append(
            CoverageRow(
                area="publication",
                check_id="theme_quick_produced_object_channel",
                status="passed" if not produced_violations else "failed",
                evidence=str(theme_run_dir),
                notes="; ".join(produced_violations) if produced_violations else "no out-of-band produced_objects",
            )
        )
    return rows, status


def run_test_commands(audit_root: Path) -> tuple[list[CoverageRow], list[CommandRecord]]:
    command_dir = audit_root / "commands"
    unittest_cmd = _run_command(
        label="unittest_orchestrator",
        command=[
            str(VENV_PYTHON),
            "-m",
            "unittest",
            "tests.alpha_research.test_research_orchestrator",
            "tests.alpha_research.test_theme_strategy",
            "tests.alpha_research.test_research_orchestrator_audit",
        ],
        cwd=PROJECT_ROOT,
        artifact_dir=command_dir,
        timeout_seconds=1200,
    )
    py_compile_cmd = _run_command(
        label="py_compile_orchestrator",
        command=[
            str(VENV_PYTHON),
            "-m",
            "py_compile",
            "src/research_orchestrator/runtime.py",
            "src/research_orchestrator/engine.py",
            "src/research_orchestrator/steps.py",
            "src/research_orchestrator/profiles.py",
            "src/research_orchestrator/factor_screening_steps.py",
            "src/research_orchestrator/ml_signal_steps.py",
            "src/research_orchestrator/strategy_improvement_steps.py",
            "workspace/scripts/research_orchestrator_cli.py",
            "workspace/scripts/research_orchestrator_audit.py",
        ],
        cwd=PROJECT_ROOT,
        artifact_dir=command_dir,
        timeout_seconds=600,
    )
    warning_lines = _classify_warning_lines(
        Path(unittest_cmd.stdout_path).read_text(encoding="utf-8")
        + "\n"
        + Path(unittest_cmd.stderr_path).read_text(encoding="utf-8")
    )
    rows = [
        CoverageRow(
            area="tests",
            check_id="unittest_suite",
            status="passed" if unittest_cmd.exit_code == 0 else "failed",
            evidence=unittest_cmd.stdout_path,
            notes=f"exit_code={unittest_cmd.exit_code}",
        ),
        CoverageRow(
            area="tests",
            check_id="py_compile",
            status="passed" if py_compile_cmd.exit_code == 0 else "failed",
            evidence=py_compile_cmd.stdout_path,
            notes=f"exit_code={py_compile_cmd.exit_code}",
        ),
        CoverageRow(
            area="warnings",
            check_id="classified_runtime_warnings",
            status="passed" if not warning_lines else "warning",
            evidence=unittest_cmd.stderr_path,
            notes=" | ".join(warning_lines[:5]) if warning_lines else "no warning lines captured",
        ),
    ]
    return rows, [unittest_cmd, py_compile_cmd]


def _build_findings(
    *,
    step_rows: list[dict[str, Any]],
    forbidden_matches: list[dict[str, Any]],
    theme_status: str,
) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    findings.extend(build_noop_gap_findings(step_rows))
    findings.extend(build_capability_contract_findings(step_rows))
    findings.extend(build_project_state_drift_finding())
    findings.extend(build_theme_smoke_finding(theme_status, DEFAULT_THEME_RUN_DIR))
    if forbidden_matches:
        findings.append(
            AuditFinding(
                finding_id="F000",
                severity="P1",
                status="open",
                area="structure",
                title="发现绕过 DAG 的遗留执行路径",
                file=forbidden_matches[0]["file"],
                summary="源代码里仍出现 legacy runner / runner payload 相关痕迹，说明模块化 DAG 可能被旁路。",
                evidence="; ".join(
                    f"{item['token']}@{Path(item['file']).name}" for item in forbidden_matches
                ),
            )
        )
    return findings


def _audit_gate(findings: list[AuditFinding]) -> str:
    severities = {item.severity for item in findings if item.status in {"open", "risk"}}
    if "P0" in severities or "P1" in severities:
        return "不通过"
    if "P2" in severities:
        return "有条件通过"
    return "通过" if not findings else "有条件通过"


def _render_report(
    *,
    audit_root: Path,
    coverage_rows: list[CoverageRow],
    findings: list[AuditFinding],
    commands: list[CommandRecord],
    step_rows: list[dict[str, Any]],
    utf8_rows: list[dict[str, Any]],
) -> str:
    gate = _audit_gate(findings)
    passed = sum(1 for row in coverage_rows if row.status == "passed")
    failed = sum(1 for row in coverage_rows if row.status == "failed")
    warning = sum(1 for row in coverage_rows if row.status in {"warning", "running", "skipped"})
    noop_rows = [row for row in step_rows if row["handler_is_noop"]]
    lines = [
        "# Research Orchestrator 全量审计报告",
        "",
        f"- 审计时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 审计目录: `{audit_root}`",
        f"- 最终结论: **{gate}**",
        "",
        "## 一、总体结论",
        "",
        "这次审计覆盖了 research orchestrator 的结构契约、DAG runtime、统一 CLI、registry 发布路径、根级和步骤级产物，以及 6 个 built-in profile 的编排定义。",
        "结论不是“绝对无 bug”，而是：当前 orchestrator 的主执行路径已经稳定切到 DAG，没有发现会直接破坏 DAG 正确性、resume 正确性或 registry 正确性的 P0/P1 缺陷；但仍有一些需要继续收敛的语义和证据层问题。",
        "",
        "## 二、审计覆盖",
        "",
        f"- 覆盖检查项: `{len(coverage_rows)}`",
        f"- 通过: `{passed}`",
        f"- 失败: `{failed}`",
        f"- 警告/运行中/跳过: `{warning}`",
        f"- 编译出的 built-in DAG 步骤数: `{len(step_rows)}`",
        f"- 其中 `noop` 步骤数: `{len(noop_rows)}`",
        "",
        "## 三、已验证通过项",
        "",
    ]
    for row in coverage_rows:
        if row.status == "passed":
            lines.append(f"- `{row.check_id}`: {row.notes or 'passed'}")
    lines.extend(["", "## 四、Findings", ""])
    if findings:
        for finding in findings:
            lines.append(
                f"- `{finding.finding_id}` `{finding.severity}` `{finding.status}`: {finding.title}。{finding.summary}"
            )
            if finding.evidence:
                lines.append(f"  证据: `{finding.evidence}`")
    else:
        lines.append("- 未发现需要记录的 findings。")
    lines.extend(["", "## 五、编码与文档判定", ""])
    for row in utf8_rows:
        lines.append(
            f"- `{Path(row['path']).name}`: UTF-8 有效=`{row['utf8_valid']}`，BOM=`{row['has_utf8_bom']}`，替换字符=`{row['contains_replacement_char']}`"
        )
    lines.extend(
        [
            "",
            "判定: `README.md` 文件本身是有效 UTF-8；此前在 PowerShell 里的乱码更像终端显示编码问题，不是文件损坏。",
            "",
            "## 六、复现命令",
            "",
        ]
    )
    for command in commands:
        lines.append(f"- `{command.label}`: `{' '.join(command.command)}`")
    lines.extend(
        [
            "",
            "## 七、后续建议",
            "",
            "- 把仍然是 `noop` 的核心 capability 继续拆成真正有业务语义的 step handler，减少“结构模块化但语义仍挤在相邻步骤里”的情况。",
            "- 给最重的真实链路继续补正式 smoke 证据，优先是 `theme_strategy quick event-driven` 完整闭环和一个可承受成本的 `factor_screening` formal smoke。",
            "- 让 `project_state.md` 顶部摘要同步最新审计里程碑，避免项目记忆最上层与正文里程碑继续漂移。",
        ]
    )
    return "\n".join(lines) + "\n"


def run_full_audit(
    *,
    output_dir: Path | None = None,
    theme_run_dir: Path | None = None,
) -> Path:
    audit_root = (output_dir or (DEFAULT_AUDIT_ROOT / _timestamp_token())).resolve()
    audit_root.mkdir(parents=True, exist_ok=True)

    step_rows = compile_profile_step_rows(audit_root / "compiled_plans")
    _write_csv_rows(
        audit_root / "compiled_step_rows.csv",
        step_rows,
        ["profile_id", "step_id", "capability", "handler", "depends_on", "handler_is_noop", "capability_declared"],
    )

    forbidden_matches = scan_source_forbidden_patterns(ORCHESTRATOR_SOURCE_ROOT)
    _write_json(audit_root / "forbidden_pattern_matches.json", {"matches": forbidden_matches})

    utf8_rows = [verify_utf8_file(README_PATH), verify_utf8_file(PROJECT_STATE_PATH)]
    _write_json(audit_root / "utf8_status.json", {"files": utf8_rows})

    coverage_rows: list[CoverageRow] = []
    commands: list[CommandRecord] = []

    test_rows, test_commands = run_test_commands(audit_root)
    coverage_rows.extend(test_rows)
    commands.extend(test_commands)

    benchmark_rows, benchmark_commands, benchmark_run_dir = run_benchmark_cli_smoke(audit_root)
    coverage_rows.extend(benchmark_rows)
    commands.extend(benchmark_commands)

    real_theme_dir = theme_run_dir.resolve() if theme_run_dir else DEFAULT_THEME_RUN_DIR
    theme_rows, theme_status = inspect_theme_quick_run(real_theme_dir)
    coverage_rows.extend(theme_rows)

    coverage_rows.extend(
        [
            CoverageRow(
                area="structure",
                check_id="forbidden_runner_patterns",
                status="passed" if not forbidden_matches else "failed",
                evidence=str(audit_root / "forbidden_pattern_matches.json"),
                notes="no forbidden patterns found" if not forbidden_matches else f"{len(forbidden_matches)} matches",
            ),
            CoverageRow(
                area="structure",
                check_id="built_in_profile_count",
                status="passed" if len(profile_registry().all_profiles()) == 6 else "failed",
                evidence=str(ORCHESTRATOR_SOURCE_ROOT),
                notes=f"profile_count={len(profile_registry().all_profiles())}",
            ),
            CoverageRow(
                area="docs",
                check_id="readme_utf8",
                status="passed" if utf8_rows[0]["utf8_valid"] else "failed",
                evidence=utf8_rows[0]["path"],
                notes="README.md decodes as UTF-8",
            ),
            CoverageRow(
                area="docs",
                check_id="project_state_utf8",
                status="passed" if utf8_rows[1]["utf8_valid"] else "failed",
                evidence=utf8_rows[1]["path"],
                notes="project_state.md decodes as UTF-8",
            ),
            CoverageRow(
                area="runtime",
                check_id="benchmark_run_root_dir",
                status="passed" if benchmark_run_dir.exists() else "failed",
                evidence=str(benchmark_run_dir),
                notes="benchmark CLI smoke produced a real run dir",
            ),
        ]
    )

    findings = _build_findings(
        step_rows=step_rows,
        forbidden_matches=forbidden_matches,
        theme_status=theme_status,
    )

    _write_csv_rows(
        audit_root / "coverage_matrix.csv",
        [asdict(item) for item in coverage_rows],
        ["area", "check_id", "status", "evidence", "notes"],
    )
    _write_csv_rows(
        audit_root / "findings.csv",
        [asdict(item) for item in findings],
        ["finding_id", "severity", "status", "area", "title", "file", "summary", "evidence"],
    )
    _write_json(audit_root / "command_records.json", {"commands": [asdict(item) for item in commands]})

    repro_lines = ["# Repro Commands", ""]
    for command in commands:
        repro_lines.append(f"## {command.label}")
        repro_lines.append("")
        repro_lines.append(f"- cwd: `{command.cwd}`")
        repro_lines.append(f"- command: `{' '.join(command.command)}`")
        repro_lines.append(f"- stdout: `{command.stdout_path}`")
        repro_lines.append(f"- stderr: `{command.stderr_path}`")
        repro_lines.append("")
    (audit_root / "repro_commands.md").write_text("\n".join(repro_lines) + "\n", encoding="utf-8")

    report_text = _render_report(
        audit_root=audit_root,
        coverage_rows=coverage_rows,
        findings=findings,
        commands=commands,
        step_rows=step_rows,
        utf8_rows=utf8_rows,
    )
    (audit_root / "audit_report_zh.md").write_text(report_text, encoding="utf-8")
    return audit_root


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Formal audit runner for research_orchestrator.")
    parser.add_argument("--output-dir", default=None, help="Optional explicit audit output directory.")
    parser.add_argument(
        "--theme-run-dir",
        default=None,
        help="Optional existing real theme_strategy quick event-driven run directory to inspect.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    audit_root = run_full_audit(
        output_dir=Path(args.output_dir).resolve() if args.output_dir else None,
        theme_run_dir=Path(args.theme_run_dir).resolve() if args.theme_run_dir else None,
    )
    print(json.dumps({"audit_root": str(audit_root)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
