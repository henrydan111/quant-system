from __future__ import annotations

import csv
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from src.research_orchestrator.artifact_provenance import (
    ArtifactProvenance,
    read_provenance,
)
from src.data_infra.field_registry import (
    FieldApprovalError,
    FieldRegistryError,
    FieldStatusRegistry,
    load_field_registry,
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

    Post-PR-3 the gate additionally requires execution_profile_id +
    execution_profile_hash and (when manual_override=True) override_reason +
    override_diff. Profiles with allowed_for_formal=False also fail formal.
    """
    eligible: bool
    status: str
    reasons: tuple[str, ...]
    provider_build_id: str | None
    calendar_policy_id: str | None
    execution_profile_id: str | None
    execution_profile_hash: str | None
    legacy_artifact: bool
    manual_override: bool = False
    override_reason: str | None = None
    override_diff_keys: tuple[str, ...] = ()
    # PR 8 fix #5: True when execution_profile_hash equals the current
    # registry profile_hash. None means "no profile or could not resolve".
    profile_hash_matches_current: bool | None = None

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

    Post-PR-3 additional gate: if the artifact's execution profile has
    ``allowed_for_formal=False`` (resolved by id), the artifact also fails
    with reason ``execution_profile_not_allowed_for_formal``. This catches
    the case where a screening profile slips into a publication artifact.
    """
    provenance = read_provenance(artifact_config)
    eligible, reasons = provenance.is_formal_eligible()

    # PR 3: cross-check the profile registry. If the artifact names a known
    # profile but that profile is allowed_for_formal=False, fail the gate
    # even if every other field is present.
    # PR 8 fix #5: also compare the artifact's execution_profile_hash against
    # the current canonical profile_hash. A mismatch means the profile was
    # bumped since the artifact was produced, so the artifact is no longer
    # bit-for-bit reproducible against the current profile registry. We
    # surface this as a distinct reason rather than rolling it into the
    # allowed_for_formal failure, so reviewers can decide whether the
    # mismatch is a planned profile bump or accidental drift.
    if provenance.execution_profile_id:
        try:
            from src.backtest_engine.execution_profiles import (
                ExecutionProfileError,
                get_profile,
            )
            profile = get_profile(provenance.execution_profile_id)
            if not profile.allowed_for_formal:
                eligible = False
                if "execution_profile_not_allowed_for_formal" not in reasons:
                    reasons.append("execution_profile_not_allowed_for_formal")
            # Hash mismatch — only check when artifact carries a hash to
            # compare. Legacy artifacts without a hash already fail elsewhere
            # via missing_execution_profile_hash.
            if provenance.execution_profile_hash and (
                provenance.execution_profile_hash != profile.profile_hash
            ):
                eligible = False
                if "execution_profile_hash_mismatch" not in reasons:
                    reasons.append("execution_profile_hash_mismatch")
        except ExecutionProfileError:
            # Unknown profile id is a hard fail.
            eligible = False
            if "unknown_execution_profile_id" not in reasons:
                reasons.append("unknown_execution_profile_id")

    if eligible:
        status = "passed"
    elif provenance.legacy_artifact:
        status = "failed_legacy"
    else:
        status = "failed"
    # Compute profile_hash_matches_current for the result. None when we
    # couldn't look up the profile (unknown id, missing hash, etc.).
    profile_hash_matches_current: bool | None = None
    if provenance.execution_profile_id and provenance.execution_profile_hash:
        try:
            from src.backtest_engine.execution_profiles import get_profile
            current_profile = get_profile(provenance.execution_profile_id)
            profile_hash_matches_current = (
                provenance.execution_profile_hash == current_profile.profile_hash
            )
        except Exception:  # noqa: BLE001 - unknown profile already in reasons
            profile_hash_matches_current = None

    return ArtifactGateResult(
        eligible=eligible,
        status=status,
        reasons=tuple(reasons),
        provider_build_id=provenance.provider_build_id,
        calendar_policy_id=provenance.calendar_policy_id,
        execution_profile_id=provenance.execution_profile_id,
        execution_profile_hash=provenance.execution_profile_hash,
        legacy_artifact=provenance.legacy_artifact,
        manual_override=provenance.manual_override,
        override_reason=provenance.override_reason,
        override_diff_keys=tuple(sorted(provenance.override_diff.keys())),
        profile_hash_matches_current=profile_hash_matches_current,
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


@dataclass(frozen=True)
class FieldDependencyGateResult:
    """Per-stage decision driven by the field-status registry.

    PR 5 of the 2026-05-26 freeze plan. Distinct from
    :class:`ArtifactGateResult` so callers can combine artifact-provenance
    and field-dependency checks into one fail/pass decision.
    """
    stage: str
    eligible: bool
    fields_checked: tuple[str, ...]
    disallowed_fields: tuple[str, ...]
    unknown_fields: tuple[str, ...]
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_field_dependencies(
    *,
    fields: Iterable[str] = (),
    expressions: Iterable[str] = (),
    stage: str,
    registry: FieldStatusRegistry | None = None,
) -> FieldDependencyGateResult:
    """Decide whether a set of fields / expressions is admissible at ``stage``.

    Accepts EITHER bare ``$field`` tokens via ``fields`` OR full Qlib
    expressions via ``expressions`` (the parser pulls every ``$field`` out
    of each expression). Combines both. Loads the committed registry on
    demand unless ``registry`` is supplied (tests inject custom registries).
    """
    if registry is None:
        try:
            registry = load_field_registry()
        except FieldRegistryError as exc:
            return FieldDependencyGateResult(
                stage=stage,
                eligible=False,
                fields_checked=(),
                disallowed_fields=(),
                unknown_fields=(),
                reasons=(f"field_registry_load_failed:{exc}",),
            )

    # Resolve every field individually; unknown-policy gates raise-or-pass
    # decisions per stage. We intentionally call resolve_field (not
    # validate_expression) so we collect ALL problems before reporting.
    seen: dict[str, Any] = {}
    for f in fields:
        if f and f not in seen:
            seen[f] = registry.resolve_field(f, stage)
    from src.data_infra.field_registry import extract_qlib_fields
    for expr in expressions:
        for f in extract_qlib_fields(expr):
            if f not in seen:
                seen[f] = registry.resolve_field(f, stage)

    disallowed: list[str] = []
    unknowns: list[str] = []
    reasons: list[str] = []
    for f, resolution in seen.items():
        if resolution.is_unknown:
            unknowns.append(f)
            if not resolution.allowed:
                disallowed.append(f)
                reasons.append(f"{f}: unknown_field (policy[{stage}]=fail)")
        elif not resolution.allowed:
            disallowed.append(f)
            reasons.append(
                f"{f}: dataset={resolution.dataset_id} status={resolution.status_id} blocked at {stage}"
            )

    return FieldDependencyGateResult(
        stage=stage,
        eligible=len(disallowed) == 0,
        fields_checked=tuple(sorted(seen.keys())),
        disallowed_fields=tuple(sorted(disallowed)),
        unknown_fields=tuple(sorted(unknowns)),
        reasons=tuple(reasons),
    )


def assert_field_dependencies_eligible(
    *,
    fields: Iterable[str] = (),
    expressions: Iterable[str] = (),
    stage: str,
    registry: FieldStatusRegistry | None = None,
    artifact_label: str = "factor",
) -> FieldDependencyGateResult:
    """Strict variant of :func:`evaluate_field_dependencies` for formal paths."""
    result = evaluate_field_dependencies(
        fields=fields, expressions=expressions, stage=stage, registry=registry,
    )
    if not result.eligible:
        raise FieldApprovalError(
            f"Field-dependency gate blocked {artifact_label} at stage={stage}: "
            f"disallowed={list(result.disallowed_fields)}, "
            f"reasons={list(result.reasons)}"
        )
    return result


# ─────────────────────────────────────────────────────────────────────────
# Promotion gate — independent PIT-correct reproduction (PIT-prevention step 11)
# ─────────────────────────────────────────────────────────────────────────
#
# The raw-ledger bypass that caused the v33/val_heavy lookahead is now contained
# (loader chokepoint + lint + QA gate). The remaining decision-layer control:
# no strategy may receive a PRIVILEGED label unless its signal/factor inputs were
# **independently reconstructed through a PIT-correct data path**. A sandbox-loader
# panel — even the parity-verified pit_research_loader — is NOT sufficient: it is
# typically the primary path, and "independent" means a different, audited path
# whose disagreement would expose a path-specific bug. (Ref:
# Knowledge/temp_plan/pit_lookahead_prevention_plan_2026-05-29_v5_FINAL.md §6.7.)

PRIVILEGED_PROMOTION_LABELS = frozenset(
    {"champion", "deployment_candidate", "live_candidate", "approved"}
)
# Sources that count as an INDEPENDENT PIT-correct reconstruction of the signal
# panel. Anything else (None, "", "sandbox", "pit_research_loader", ...) fails.
VALID_INDEPENDENT_REPRODUCTION_SOURCES = frozenset(
    {
        "qlib_windowed_features",  # formal provider path via the windowed wrapper
        "joinquant_native_pit",    # JoinQuant get_fundamentals(date=) + pubDate filtering
        "audited_pit_source",      # another audited PIT source, named in provenance
    }
)


class PromotionGateError(RuntimeError):
    """A privileged promotion label lacks a valid independent reproduction."""


@dataclass(frozen=True)
class PromotionGateResult:
    """Decision on whether a strategy may carry a privileged promotion label.

    Exploratory labels (anything not in PRIVILEGED_PROMOTION_LABELS) are always
    eligible — research is free. A privileged label requires
    ``reproduction_source`` to be one of VALID_INDEPENDENT_REPRODUCTION_SOURCES.
    """
    label: str
    privileged: bool
    reproduction_source: str | None
    eligible: bool
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_promotion_eligibility(
    *, label: str | None, reproduction_source: str | None
) -> PromotionGateResult:
    """Decide whether ``label`` may be assigned given the reproduction source."""
    label_norm = (label or "").strip().lower()
    privileged = label_norm in PRIVILEGED_PROMOTION_LABELS
    src = (reproduction_source or "").strip()
    reasons: list[str] = []
    if privileged:
        if not src:
            reasons.append(
                f"privileged label '{label_norm}' requires an independent PIT-correct "
                f"reproduction source; none supplied"
            )
        elif src not in VALID_INDEPENDENT_REPRODUCTION_SOURCES:
            reasons.append(
                f"reproduction source '{src}' is not an INDEPENDENT PIT-correct path "
                f"(a sandbox/loader panel is insufficient). Allowed: "
                f"{sorted(VALID_INDEPENDENT_REPRODUCTION_SOURCES)}"
            )
    return PromotionGateResult(
        label=label_norm,
        privileged=privileged,
        reproduction_source=reproduction_source,
        eligible=len(reasons) == 0,
        reasons=tuple(reasons),
    )


def evaluate_promotion_from_artifact(
    artifact_config: Mapping[str, Any] | None,
) -> PromotionGateResult:
    """Read ``promotion_label`` + ``independent_reproduction.source`` from an
    artifact/registry record and evaluate. Missing keys → treated as an
    unprivileged label with no reproduction (eligible only if not privileged)."""
    cfg = artifact_config or {}
    label = cfg.get("promotion_label")
    repro = cfg.get("independent_reproduction") or {}
    source = repro.get("source") if isinstance(repro, Mapping) else None
    return evaluate_promotion_eligibility(label=label, reproduction_source=source)


def assert_promotion_eligible(
    *,
    label: str | None,
    reproduction_source: str | None,
    artifact_label: str = "strategy",
) -> PromotionGateResult:
    """Strict variant — raises :class:`PromotionGateError` on an ineligible
    privileged label. Call this at the point a strategy is labeled
    champion / deployment_candidate / live_candidate / approved."""
    result = evaluate_promotion_eligibility(
        label=label, reproduction_source=reproduction_source
    )
    if not result.eligible:
        raise PromotionGateError(
            f"Promotion gate blocked {artifact_label} for label='{result.label}': "
            f"{list(result.reasons)}"
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
