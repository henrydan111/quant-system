from __future__ import annotations

import csv
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from src.research_orchestrator.artifact_provenance import (
    ArtifactProvenance,
    read_provenance,
)


@dataclass(frozen=True)
class ReleaseGateResult:
    gate_root: str
    audit_root: str
    status: str
    generated_at: str
    findings_total: int
    open_findings: int
    risk_findings: int
    coverage_total: int
    coverage_passed: int
    coverage_non_passed: int
    blocking_findings: list[str]
    blocking_checks: list[str]
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _timestamp_string() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def evaluate_audit_root(*, gate_root: Path, audit_root: Path) -> ReleaseGateResult:
    notes: list[str] = []
    findings_path = audit_root / "findings.csv"
    coverage_path = audit_root / "coverage_matrix.csv"
    report_path = audit_root / "audit_report_zh.md"

    for path in (findings_path, coverage_path, report_path):
        if not path.exists():
            notes.append(f"missing_required_artifact:{path.name}")

    findings_rows = _read_csv_rows(findings_path)
    coverage_rows = _read_csv_rows(coverage_path)

    open_findings = [row for row in findings_rows if row.get("status", "").strip() == "open"]
    risk_findings = [row for row in findings_rows if row.get("status", "").strip() == "risk"]
    non_passed_checks = [row for row in coverage_rows if row.get("status", "").strip() != "passed"]

    blocking_findings = [
        f"{row.get('finding_id', '')}:{row.get('severity', '')}:{row.get('title', '')}"
        for row in open_findings + risk_findings
    ]
    blocking_checks = [
        f"{row.get('check_id', '')}:{row.get('status', '')}:{row.get('notes', '')}"
        for row in non_passed_checks
    ]

    status = "passed"
    if notes or blocking_findings or blocking_checks:
        status = "failed"

    return ReleaseGateResult(
        gate_root=str(gate_root),
        audit_root=str(audit_root),
        status=status,
        generated_at=_timestamp_string(),
        findings_total=len(findings_rows),
        open_findings=len(open_findings),
        risk_findings=len(risk_findings),
        coverage_total=len(coverage_rows),
        coverage_passed=sum(1 for row in coverage_rows if row.get("status", "").strip() == "passed"),
        coverage_non_passed=len(non_passed_checks),
        blocking_findings=blocking_findings,
        blocking_checks=blocking_checks,
        notes=notes,
    )


def render_release_gate_report(result: ReleaseGateResult) -> str:
    lines = [
        "# Research Orchestrator Release Gate",
        "",
        f"- Generated At: `{result.generated_at}`",
        f"- Gate Root: `{result.gate_root}`",
        f"- Audit Root: `{result.audit_root}`",
        f"- Final Status: **{result.status.upper()}**",
        "",
        "## Summary",
        "",
        f"- Findings total: `{result.findings_total}`",
        f"- Open findings: `{result.open_findings}`",
        f"- Risk findings: `{result.risk_findings}`",
        f"- Coverage checks: `{result.coverage_total}`",
        f"- Coverage passed: `{result.coverage_passed}`",
        f"- Coverage non-passed: `{result.coverage_non_passed}`",
        "",
        "## Blocking Findings",
        "",
    ]
    if result.blocking_findings:
        lines.extend(f"- `{item}`" for item in result.blocking_findings)
    else:
        lines.append("- None")

    lines.extend(["", "## Blocking Checks", ""])
    if result.blocking_checks:
        lines.extend(f"- `{item}`" for item in result.blocking_checks)
    else:
        lines.append("- None")

    lines.extend(["", "## Notes", ""])
    if result.notes:
        lines.extend(f"- `{item}`" for item in result.notes)
    else:
        lines.append("- None")

    lines.extend(
        [
            "",
            "## Gate Rule",
            "",
            "- Pass only if `findings.csv` has no `open`/`risk` rows and every row in `coverage_matrix.csv` is `passed`.",
            "- Any missing required audit artifact also fails the gate.",
            "",
        ]
    )
    return "\n".join(lines)


def write_release_gate_artifacts(*, gate_root: Path, result: ReleaseGateResult) -> None:
    gate_root.mkdir(parents=True, exist_ok=True)
    summary_path = gate_root / "release_gate_summary.json"
    report_path = gate_root / "release_gate_report_zh.md"
    latest_path = gate_root.parent / "latest_run.json"

    summary_path.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    report_path.write_text(render_release_gate_report(result), encoding="utf-8")
    latest_path.write_text(
        json.dumps(
            {
                "generated_at": result.generated_at,
                "gate_root": result.gate_root,
                "audit_root": result.audit_root,
                "status": result.status,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


@dataclass(frozen=True)
class ArtifactGateResult:
    """Per-artifact gate decision driven by ArtifactProvenance.

    Distinct from the audit-CSV-driven :class:`ReleaseGateResult` because the
    two evaluate different things: audit-CSV gates inspect the theme-strategy
    audit bundle, while artifact gates inspect a single result/registry
    artifact's provenance block.

    Legacy artifacts (those missing the provenance block entirely or missing
    provider_build_id / calendar_policy_id) are readable and comparable but
    cannot pass the formal gate. They surface here with
    ``status="failed_legacy"`` and a populated ``reasons`` list.
    """
    eligible: bool
    status: str
    reasons: tuple[str, ...]
    provider_build_id: str | None
    calendar_policy_id: str | None
    execution_profile_id: str | None
    execution_profile_hash: str | None
    legacy_artifact: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_artifact_provenance(
    artifact_config: Mapping[str, Any] | None,
) -> ArtifactGateResult:
    """Decide whether a single artifact is formally eligible for publication.

    Accepts either a ``BacktestResult.config``-style dict or any mapping that
    carries an ``artifact_provenance`` key. Missing / malformed provenance
    yields ``status="failed_legacy"`` rather than raising — viewers and
    historical-comparison tools can still display the artifact, but the
    release gate refuses it.
    """
    provenance = read_provenance(artifact_config)
    eligible, reasons = provenance.is_formal_eligible()
    if eligible:
        status = "passed"
    elif provenance.legacy_artifact:
        status = "failed_legacy"
    else:
        status = "failed"
    return ArtifactGateResult(
        eligible=eligible,
        status=status,
        reasons=tuple(reasons),
        provider_build_id=provenance.provider_build_id,
        calendar_policy_id=provenance.calendar_policy_id,
        execution_profile_id=provenance.execution_profile_id,
        execution_profile_hash=provenance.execution_profile_hash,
        legacy_artifact=provenance.legacy_artifact,
    )


def assert_formal_artifact_eligible(
    artifact_config: Mapping[str, Any] | None,
    *,
    artifact_label: str = "artifact",
) -> ArtifactGateResult:
    """Strict variant of :func:`evaluate_artifact_provenance` for formal paths.

    Raises ``ValueError`` if the artifact is not formal-eligible. Returns the
    :class:`ArtifactGateResult` for callers that want to log/record it.
    """
    result = evaluate_artifact_provenance(artifact_config)
    if not result.eligible:
        raise ValueError(
            f"Formal release blocked for {artifact_label}: "
            f"status={result.status}, reasons={list(result.reasons)}. "
            "Re-run with a current provider manifest and explicit calendar policy."
        )
    return result


def run_release_gate(
    *,
    gate_root: Path,
    audit_runner: Callable[..., Path],
    theme_run_dir: Path | None = None,
) -> ReleaseGateResult:
    gate_root = gate_root.resolve()
    gate_root.mkdir(parents=True, exist_ok=True)
    audit_root = gate_root / "audit"

    try:
        produced_audit_root = audit_runner(output_dir=audit_root, theme_run_dir=theme_run_dir)
        result = evaluate_audit_root(gate_root=gate_root, audit_root=Path(produced_audit_root).resolve())
    except Exception as exc:  # pragma: no cover - exercised through script-level behavior
        result = ReleaseGateResult(
            gate_root=str(gate_root),
            audit_root=str(audit_root),
            status="failed",
            generated_at=_timestamp_string(),
            findings_total=0,
            open_findings=0,
            risk_findings=0,
            coverage_total=0,
            coverage_passed=0,
            coverage_non_passed=0,
            blocking_findings=[],
            blocking_checks=[],
            notes=[f"audit_runner_exception:{type(exc).__name__}:{exc}"],
        )

    write_release_gate_artifacts(gate_root=gate_root, result=result)
    return result
