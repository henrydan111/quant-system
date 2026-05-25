"""Gate report rendering and success-criteria evaluation helpers."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Literal

from src.research_orchestrator.hypothesis import Hypothesis


def _make_temp_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.tmp.{os.getpid()}.{time.time_ns()}")


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = _make_temp_path(path)
    temp_path.write_text(text, encoding="utf-8")
    os.replace(temp_path, path)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = _make_temp_path(path)
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    os.replace(temp_path, path)


class ConcernEnforcementError(ValueError):
    """Raised when concern scoring is missing or contradicted by measured evidence."""


def _severity_rank(value: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}[str(value)]


def derive_severity(
    rule_row: dict | None,
    quantitative_anchor: dict,
) -> Literal["low", "medium", "high"]:
    if rule_row is None:
        return "medium"
    passed = rule_row.get("passed")
    if passed is True:
        return "low"
    if passed is None:
        return "medium"
    required_metric = str(rule_row.get("metric") or "")
    if not required_metric:
        return "high"
    measured = quantitative_anchor.get(required_metric)
    if not isinstance(measured, (int, float)):
        return "high"
    measured = float(measured)
    threshold = rule_row.get("threshold")
    comparator = str(rule_row.get("comparator", ">=") or ">=")
    if threshold is None or not isinstance(threshold, (int, float)):
        return "medium"
    threshold = float(threshold)
    if threshold == 0:
        return "high" if measured != 0 else "medium"
    if comparator == ">=":
        ratio = (threshold - measured) / abs(threshold)
    elif comparator == "<=":
        ratio = (measured - threshold) / abs(threshold)
    else:
        return "medium"
    if ratio > 0.5:
        return "high"
    return "medium"


def effect_size_in_ci(
    hypothesis: Hypothesis | None,
    measured_values: dict[str, Any],
) -> bool | None:
    if hypothesis is None or hypothesis.expected_effect is None:
        return None
    metric_name = str(hypothesis.expected_effect.statistic)
    actual = measured_values.get(metric_name)
    if actual is None:
        return None
    lo = float(hypothesis.expected_effect.ci_low)
    hi = float(hypothesis.expected_effect.ci_high)
    return lo <= float(actual) <= hi


def compute_automated_verdict(rule_table: list[dict[str, Any]]) -> Literal["accepted", "rejected", "quarantined"]:
    hard_rules = [row for row in rule_table if bool(row.get("is_hard"))]
    if not hard_rules:
        return "accepted"
    if any(row.get("passed") is False for row in hard_rules):
        return "rejected"
    if any(row.get("passed") is None for row in hard_rules):
        return "quarantined"
    return "accepted"


def evaluate_success_criteria(
    hypothesis: Hypothesis | None,
    measured_values: dict[str, Any],
) -> list[dict[str, Any]]:
    if hypothesis is None:
        return []

    criteria = hypothesis.success_criteria
    results: list[dict[str, Any]] = []
    field_specs = [
        ("min_rank_icir", "rank_icir", ">=", True),
        ("min_deflated_sharpe", "deflated_sharpe", ">=", True),
        ("min_cost_adjusted_sharpe", "cost_adjusted_sharpe", ">=", True),
        ("max_drawdown", "max_drawdown", "<=", True),
        ("max_annual_turnover", "annual_turnover", "<=", True),
        ("min_monotonicity_pvalue", "monotonicity_pvalue", "<=", True),
        ("max_correlation_to_approved", "correlation_to_approved", "<=", True),
        ("min_regime_pass_count", "regime_pass_count", ">=", True),
    ]
    for field_name, metric_name, comparator, is_hard in field_specs:
        threshold = getattr(criteria, field_name)
        if threshold is None:
            continue
        actual = measured_values.get(metric_name)
        passed = None
        if actual is not None:
            if comparator == ">=":
                passed = float(actual) >= float(threshold)
            else:
                passed = float(actual) <= float(threshold)
        results.append(
            {
                "rule_id": field_name,
                "rule": field_name,
                "metric": metric_name,
                "comparator": comparator,
                "threshold": threshold,
                "actual": actual,
                "passed": passed,
                "is_hard": bool(is_hard),
            }
        )

    if criteria.effect_size_must_be_in_ci and hypothesis.expected_effect is not None:
        metric_name = str(hypothesis.expected_effect.statistic)
        actual = measured_values.get(metric_name)
        passed = None
        if actual is not None:
            passed = float(hypothesis.expected_effect.ci_low) <= float(actual) <= float(hypothesis.expected_effect.ci_high)
        results.append(
            {
                "rule_id": "effect_size_must_be_in_ci",
                "rule": "effect_size_must_be_in_ci",
                "metric": metric_name,
                "comparator": "within_ci",
                "threshold": {
                    "ci_low": hypothesis.expected_effect.ci_low,
                    "ci_high": hypothesis.expected_effect.ci_high,
                },
                "actual": actual,
                "passed": passed,
                "is_hard": True,
            }
        )

    for index, rule in enumerate(criteria.custom_rules, start=1):
        # Permissive: accept string custom_rules as opaque rule_ids with
        # manual comparator + no automatic threshold check. Documented in
        # CLAUDE.md hypothesis-CLI section. Strict dict format remains the
        # canonical form and is preferred for new hypotheses.
        if isinstance(rule, str):
            rule_payload = {"rule_id": rule.strip() or f"custom_rule_{index}", "comparator": "manual", "is_hard": False, "notes": rule}
        else:
            rule_payload = rule
        rule_id = str(rule_payload.get("rule_id") or f"custom_rule_{index}")
        if any(existing.get("rule_id") == rule_id for existing in results):
            raise ValueError(f"Duplicate success-criteria rule_id: {rule_id}")
        results.append(
            {
                "rule_id": rule_id,
                "rule": rule_id,
                "metric": str(rule_payload.get("metric", "")),
                "comparator": str(rule_payload.get("comparator", "manual")),
                "threshold": rule_payload.get("threshold"),
                "actual": measured_values.get(str(rule_payload.get("metric", ""))),
                "passed": None,
                "is_hard": bool(rule_payload.get("is_hard", False)),
                "notes": str(rule_payload.get("notes", "")),
            }
        )
    return results


def render_gate_markdown(payload: dict[str, Any]) -> str:
    identity = payload.get("identity", {})
    rule_rows = payload.get("pre_committed_rule_table", [])
    measured_values = payload.get("measured_values", {})
    concerns = payload.get("pre_registered_concerns", [])
    verdict = payload.get("verdict", {})
    next_action = payload.get("next_action", {})

    lines = [
        f"# Gate Report: {identity.get('gate_id', 'gate_review')}",
        "",
        "## Identity",
        f"- Hypothesis: {identity.get('hypothesis_id', '')}",
        f"- Design hash: {identity.get('design_hash', '')}",
        f"- Profile: {identity.get('profile_id', '')}",
        f"- Gate stage: {identity.get('gate_stage', '')}",
        f"- Run dir: {identity.get('run_dir', '')}",
        "",
        "## Pre-Committed Rule Table",
    ]
    if rule_rows:
        lines.extend(
            [
                "| Rule | Metric | Comparator | Threshold | Actual | Passed | Hard |",
                "|---|---|---|---|---|---|---|",
            ]
        )
        for row in rule_rows:
            lines.append(
                f"| {row.get('rule_id', row.get('rule', ''))} | {row.get('metric', '')} | {row.get('comparator', '')} | "
                f"{row.get('threshold', '')} | {row.get('actual', '')} | {row.get('passed', '')} | {row.get('is_hard', '')} |"
            )
    else:
        lines.append("- No machine-evaluable success criteria were supplied.")

    lines.extend(["", "## Measured Values"])
    if measured_values:
        for key, value in sorted(measured_values.items()):
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- No measured values were captured.")

    lines.extend(["", "## Pre-Registered Concerns"])
    if concerns:
        for row in concerns:
            if not row.get("concern_text"):
                raise ConcernEnforcementError("gate_review invoked with empty concern_scores")
            lines.append(f"### {row.get('concern_id', row.get('label', 'concern'))}")
            lines.append(f"- Concern text: {row.get('concern_text', row.get('text', ''))}")
            lines.append(f"- Rule id: {row.get('keyed_to_rule_id', '')}")
            lines.append(f"- Evidence: {row.get('measured_evidence_against_concern', '')}")
            lines.append(f"- Confirmed: {row.get('confirmed', '')}")
            lines.append(f"- Severity: {row.get('severity', '')}")
            anchor = dict(row.get("quantitative_anchor", {}))
            if anchor:
                for key, value in sorted(anchor.items()):
                    lines.append(f"- Anchor {key}: {value}")
    else:
        lines.append("- No pre-registered concerns were supplied.")

    lines.extend(
        [
            "",
            "## Verdict",
            f"- State: {verdict.get('state', '')}",
            f"- Automated verdict: {verdict.get('automated_verdict', '')}",
            f"- Decision: {verdict.get('decision', '')}",
            f"- Decision by: {verdict.get('decision_by', '')}",
            f"- Reason: {verdict.get('reason', '')}",
            "",
            "## Next Action",
            f"- Required action: {next_action.get('required_action', '')}",
            f"- Decision path: {next_action.get('decision_path', '')}",
        ]
    )
    return "\n".join(lines) + "\n"


def write_gate_report(step_dir: str | Path, payload: dict[str, Any]) -> dict[str, str]:
    root = Path(step_dir).resolve()
    json_path = root / "gate_report.json"
    md_path = root / "gate_report.md"
    _atomic_write_json(json_path, payload)
    _atomic_write_text(md_path, render_gate_markdown(payload))
    return {
        "gate_report_json": str(json_path),
        "gate_report_md": str(md_path),
    }
