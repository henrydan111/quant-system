"""CLI for hypothesis registration, human gates, and concern scoring."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from jsonschema import validate as jsonschema_validate

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.alpha_research.hypothesis_registry import HypothesisRegistryStore
from src.research_orchestrator.gate_report import (
    ConcernEnforcementError,
    _severity_rank,
    derive_severity,
)
from src.research_orchestrator.holdout_seal import HoldoutSealStore
from src.research_orchestrator.hypothesis import (
    SUCCESS_CRITERIA_FLOORS,
    Hypothesis,
    LaxCriteriaError,
    validate_success_criteria_floor_rails,
)
from src.research_orchestrator.input_schemas import get_schema


TEMPLATE_DIR = PROJECT_ROOT / "workspace" / "scripts" / "templates"


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _make_temp_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.tmp.{os.getpid()}.{time.time_ns()}")


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = _make_temp_path(path)
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    os.replace(temp_path, path)


def _load_payload(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() in {".yaml", ".yml"}:
        return yaml.safe_load(text) or {}
    return json.loads(text)


def _gate_report_path(run_dir: Path, gate_step: str) -> Path:
    return run_dir / "steps" / gate_step / "gate_report.json"


def _decision_path(run_dir: Path, gate_step: str) -> Path:
    return run_dir / "steps" / gate_step / "gate_decision.json"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_gate_step_candidates(run_dir: Path, *, pause_kind: str, capability: str) -> list[str]:
    candidates: list[str] = []
    for step_dir in sorted((run_dir / "steps").glob("*")):
        metadata_path = step_dir / "step_metadata.json"
        if not metadata_path.exists():
            continue
        metadata = _load_json(metadata_path)
        if str(metadata.get("capability", "")) != capability:
            continue
        if str(metadata.get("status", "")) != "paused":
            continue
        if str(metadata.get("pause_kind", "")) != pause_kind:
            continue
        candidates.append(step_dir.name)
    return candidates


def _find_predecessor_step_id_from_plan(run_dir: Path, step_id: str, capability: str) -> str:
    plan = _load_json(run_dir / "dag_plan.json")
    steps = {str(item["step_id"]): item for item in plan.get("steps", [])}
    target = steps.get(step_id)
    if target is None:
        raise SystemExit(f"Step id not found in dag_plan.json: {step_id}")
    matches = [
        dep for dep in target.get("depends_on", [])
        if str(steps.get(dep, {}).get("capability", "")) == capability
    ]
    if len(matches) != 1:
        raise SystemExit(
            f"Expected exactly one predecessor with capability {capability!r} for step {step_id!r}; got {matches or 'none'}"
        )
    return str(matches[0])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Hypothesis workflow CLI")
    parser.add_argument(
        "--registry-dir",
        default=str(PROJECT_ROOT / "data" / "hypothesis_registry"),
        help="Hypothesis registry directory",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    register_parser = subparsers.add_parser("register", help="Register a hypothesis JSON/YAML file")
    register_parser.add_argument("--file", required=True, help="Path to a serialized hypothesis payload")
    register_parser.add_argument("--registered-by", default="human", help="Registrar name")
    register_parser.add_argument("--force-relaxed-criteria", action="store_true", help="Allow manual floor-rail override")
    register_parser.add_argument("--override-reason", default="", help="Required when forcing relaxed criteria")
    register_parser.add_argument(
        "--profile-id",
        default="",
        help=(
            "Optional profile_id to validate the hypothesis floors against. "
            "When omitted (legacy behavior), validates against ALL profiles' "
            "floor rails — the strictest wins (e.g., strategy_improvement). "
            "When set (e.g., 'hypothesis_validation' or 'theme_strategy'), "
            "validates ONLY against that profile's floors. Plan ref: "
            "jolly-seeking-lollipop Gate F (Codex round-2 #4)."
        ),
    )

    draft_parser = subparsers.add_parser("draft", help="Create a starter hypothesis payload")
    draft_parser.add_argument("--template", default="blank", help="Template name")
    draft_parser.add_argument("--output", required=True, help="Output JSON file")
    draft_parser.add_argument("--force", action="store_true", help="Overwrite the output file if it already exists")

    show_parser = subparsers.add_parser("show", help="Show one hypothesis plus its history")
    show_parser.add_argument("--hypothesis-id", required=True, help="Hypothesis id")

    list_parser = subparsers.add_parser("list", help="List hypotheses from the derived master view")
    list_parser.add_argument("--status", default="", help="Optional status filter")
    list_parser.add_argument("--family", default="", help="Optional structural_family filter")
    list_parser.add_argument("--economic-family", default="", help="Optional economic_family filter")
    list_parser.add_argument("--limit", type=int, default=50, help="Maximum rows to show")

    approve_parser = subparsers.add_parser("approve", help="Approve a pending gate")
    approve_parser.add_argument("--run-dir", required=True, help="Research run directory")
    approve_parser.add_argument("--gate-step", default="gate_review", help="Gate step id")
    approve_parser.add_argument("--reviewer", required=True, help="Reviewer name")
    approve_parser.add_argument("--reason", required=True, help="Approval reason")

    reject_parser = subparsers.add_parser("reject", help="Reject a pending gate")
    reject_parser.add_argument("--run-dir", required=True, help="Research run directory")
    reject_parser.add_argument("--gate-step", default="gate_review", help="Gate step id")
    reject_parser.add_argument("--reviewer", required=True, help="Reviewer name")
    reject_parser.add_argument("--reason", required=True, help="Rejection reason")

    quarantine_parser = subparsers.add_parser("quarantine", help="Quarantine a pending gate")
    quarantine_parser.add_argument("--run-dir", required=True, help="Research run directory")
    quarantine_parser.add_argument("--gate-step", default="gate_review", help="Gate step id")
    quarantine_parser.add_argument("--reviewer", required=True, help="Reviewer name")
    quarantine_parser.add_argument("--reason", required=True, help="Quarantine reason")

    verify_parser = subparsers.add_parser("verify-seal", help="Show holdout seal events for one design hash or seal key")
    verify_parser.add_argument(
        "design_hash", nargs="?", default=None,
        help="Design hash (provenance; back-compat). Provide this OR --seal-key.",
    )
    verify_parser.add_argument(
        "--seal-key", default=None,
        help=(
            "Seal key (PR P1.4: the seal identity, e.g. a frozen_set_hash). Takes "
            "precedence over the positional design_hash. Old design_hash-only seals "
            "are resolvable either way (the store backfills seal_key=design_hash)."
        ),
    )
    verify_parser.add_argument(
        "--seal-dir",
        default=str(PROJECT_ROOT / "data" / "holdout_seals"),
        help="Holdout seal directory",
    )
    verify_parser.add_argument(
        "--expect-claims",
        type=int,
        default=None,
        help=(
            "Optional exact-count assertion: exit code 0 only if the number of "
            "OOS-stage claim events for this design_hash equals N. Without this "
            "flag, exit codes follow legacy semantics (0=no claims, 1=any claim, "
            "2=malformed hash). Plan ref: jolly-seeking-lollipop Gate F."
        ),
    )

    pending_parser = subparsers.add_parser("pending-gates", help="List paused runs awaiting input or gate decisions")
    pending_parser.add_argument("--kind", choices=("gate", "input", "all"), default="all")
    pending_parser.add_argument("--limit", type=int, default=50)
    pending_parser.add_argument(
        "--runs-root",
        default=str(PROJECT_ROOT / "workspace" / "outputs"),
        help="Root directory to scan for orchestrator runs",
    )

    score_parser = subparsers.add_parser("score-concerns", help="Populate gate_concern_scores.json")
    score_parser.add_argument("run_dir", help="Research run directory")
    score_parser.add_argument("--step-id", default="", help="Specific gate_concern_scoring step id")
    score_parser.add_argument("--from-json", default="", help="Copy a prepared JSON payload instead of prompting")
    score_parser.add_argument("--non-interactive", action="store_true", help="Require --from-json and skip prompts")

    subparsers.add_parser("summary", help="Print registry summary")
    return parser


def _register_hypothesis(store: HypothesisRegistryStore, args: argparse.Namespace) -> int:
    payload = _load_payload(Path(args.file).resolve())
    hypothesis_payload = dict(payload.get("hypothesis", payload))
    hypothesis_payload.setdefault("pre_registered_at", _now_str())
    hypothesis_payload.setdefault("registered_by", str(args.registered_by))
    hypothesis = Hypothesis.from_dict(hypothesis_payload)
    # Profile-aware floor validation (Gate F): if --profile-id given, validate
    # ONLY that profile's floors; otherwise validate ALL profiles (legacy).
    profile_filter = str(getattr(args, "profile_id", "") or "").strip()
    if profile_filter:
        if profile_filter not in SUCCESS_CRITERIA_FLOORS:
            raise SystemExit(
                f"--profile-id={profile_filter!r} is not a known profile. "
                f"Known profiles: {sorted(SUCCESS_CRITERIA_FLOORS)}"
            )
        profiles_to_check = [profile_filter]
    else:
        profiles_to_check = sorted(SUCCESS_CRITERIA_FLOORS)
    try:
        for profile_id in profiles_to_check:
            validate_success_criteria_floor_rails(hypothesis, profile_id, allow_override=False)
    except LaxCriteriaError:
        if not args.force_relaxed_criteria or not str(args.override_reason).strip():
            raise
    try:
        result = store.register(hypothesis)
    except LaxCriteriaError:
        if not args.force_relaxed_criteria or not str(args.override_reason).strip():
            raise
        result = store.register(hypothesis)
        if not result.get("already_exists"):
            store.record_manual_override(
                hypothesis_id=hypothesis.hypothesis_id,
                design_hash=hypothesis.design_hash(),
                override_reason=f"floor_rails_relaxed: {args.override_reason}",
                override_by=str(args.registered_by),
            )
    else:
        if args.force_relaxed_criteria:
            if not str(args.override_reason).strip():
                raise SystemExit("--override-reason is required when --force-relaxed-criteria is used")
            if not result.get("already_exists"):
                store.record_manual_override(
                    hypothesis_id=hypothesis.hypothesis_id,
                    design_hash=hypothesis.design_hash(),
                    override_reason=f"floor_rails_relaxed: {args.override_reason}",
                    override_by=str(args.registered_by),
                )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _draft_hypothesis(args: argparse.Namespace) -> int:
    output_path = Path(args.output).resolve()
    if output_path.exists() and not args.force:
        raise SystemExit(f"Output already exists: {output_path}. Use --force to overwrite.")
    template_name = str(args.template or "blank").strip().lower()
    template_path = TEMPLATE_DIR / f"hypothesis_{template_name}.json"
    if not template_path.exists():
        raise SystemExit(f"Unknown template: {template_name}. Expected file {template_path}")
    payload = _load_payload(template_path)
    _atomic_write_json(output_path, payload)
    print(str(output_path))
    return 0


def _show_hypothesis(store: HypothesisRegistryStore, args: argparse.Namespace) -> int:
    row = store.get(args.hypothesis_id)
    if row is None:
        raise SystemExit(f"Hypothesis not found: {args.hypothesis_id}")
    status_history = store.status_history[
        store.status_history["hypothesis_id"] == str(args.hypothesis_id)
    ].sort_values("changed_at")
    evidence = store.evidence[
        store.evidence["hypothesis_id"] == str(args.hypothesis_id)
    ].sort_values("recorded_at")
    payload = {
        "master": row,
        "status_history": status_history.to_dict(orient="records"),
        "evidence": evidence.to_dict(orient="records"),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0


def _list_hypotheses(store: HypothesisRegistryStore, args: argparse.Namespace) -> int:
    frame = store.list_by_status(str(args.status))
    if str(args.family).strip():
        frame = frame[frame["structural_family"] == str(args.family).strip()].copy()
    if str(args.economic_family).strip():
        frame = frame[frame["economic_family"] == str(args.economic_family).strip()].copy()
    frame = frame.head(max(int(args.limit), 1))
    if frame.empty:
        print("No hypotheses found.")
        return 0
    subset = frame[
        ["hypothesis_id", "status", "structural_family", "economic_family", "updated_at"]
    ].copy()
    print(subset.to_string(index=False))
    return 0


def _record_gate_decision(
    *,
    store: HypothesisRegistryStore,
    run_dir: Path,
    gate_step: str,
    reviewer: str,
    reason: str,
    decision: str,
) -> int:
    gate_report_path = _gate_report_path(run_dir, gate_step)
    if not gate_report_path.exists():
        raise SystemExit(f"Gate report not found: {gate_report_path}")
    gate_report = json.loads(gate_report_path.read_text(encoding="utf-8"))
    identity = dict(gate_report.get("identity", {}))
    hypothesis_id = str(identity.get("hypothesis_id", "") or "")
    design_hash = str(identity.get("design_hash", "") or "")
    profile_id = str(identity.get("profile_id", "") or "")
    gate_stage = str(identity.get("gate_stage", "") or "")
    if not hypothesis_id or not design_hash:
        raise SystemExit("Gate report is missing hypothesis identity fields.")

    decision_payload = {
        "decision": str(decision),
        "decision_by": str(reviewer),
        "reason": str(reason),
        "recorded_at": _now_str(),
    }
    decision_path = _decision_path(run_dir, gate_step)
    _atomic_write_json(decision_path, decision_payload)

    result = store.record_gate_decision(
        hypothesis_id=hypothesis_id,
        design_hash=design_hash,
        run_dir=str(run_dir),
        profile_id=profile_id,
        gate_id=gate_step,
        gate_stage=gate_stage,
        decision=decision,
        decision_by=reviewer,
        decision_reason=reason,
        measured_values=dict(gate_report.get("measured_values", {})),
        criteria_results=list(gate_report.get("pre_committed_rule_table", [])),
    )
    print(json.dumps({"decision_path": str(decision_path), **result}, ensure_ascii=False, indent=2))
    return 0


def _verify_seal(args: argparse.Namespace) -> int:
    # PR P1.4: query by --seal-key (the seal identity, e.g. a frozen_set_hash) when
    # given, else by the positional design_hash (back-compat — the store backfills
    # seal_key=design_hash, so old design_hash-only seals resolve either way).
    seal_key = str(getattr(args, "seal_key", None) or "").strip().lower()
    design_hash = str(args.design_hash or "").strip().lower()
    if seal_key:
        if not re.fullmatch(r"[0-9a-f]{64}", seal_key):
            print(f"Malformed seal key: {args.seal_key}", file=sys.stderr)
            return 2
        query = {"seal_key": seal_key}
        label = f"seal_key={seal_key}"
    else:
        if not re.fullmatch(r"[0-9a-f]{64}", design_hash):
            print(f"Malformed design hash: {args.design_hash}", file=sys.stderr)
            return 2
        query = {"design_hash": design_hash}
        label = f"design_hash={design_hash}"
    store = HoldoutSealStore(Path(args.seal_dir).resolve())
    events = store.list_events(**query)
    oos_events = events[events["stage"].astype(str) == "oos_test"].copy() if not events.empty else events
    print(oos_events.to_string(index=False) if not oos_events.empty else "No OOS access recorded.")
    expect_claims = getattr(args, "expect_claims", None)
    if expect_claims is not None:
        # Plan ref: jolly-seeking-lollipop Gate F. Strict assertion mode:
        # exit 0 only if the OOS claim count exactly matches N.
        actual = 0 if oos_events.empty else int(len(oos_events))
        if actual != int(expect_claims):
            print(
                f"--expect-claims={expect_claims} but found {actual} OOS claim(s) for {label}",
                file=sys.stderr,
            )
            return 1
        return 0
    return 1 if not oos_events.empty else 0


def _pending_gates(args: argparse.Namespace) -> int:
    runs_root = Path(args.runs_root).resolve()
    rows: list[dict[str, Any]] = []
    for state_path in runs_root.rglob("dag_state.json"):
        try:
            state = _load_json(state_path)
        except Exception:
            continue
        if str(state.get("status", "")) != "paused":
            continue
        run_dir = state_path.parent
        step_id = str(state.get("pending_step_id", "") or "")
        pause_kind = "input" if state.get("pending_input") else "gate"
        if args.kind != "all" and args.kind != pause_kind:
            continue
        hypothesis_id = ""
        if step_id:
            report_path = run_dir / "steps" / step_id / "gate_report.json"
            if report_path.exists():
                hypothesis_id = str(_load_json(report_path).get("identity", {}).get("hypothesis_id", "") or "")
        rows.append(
            {
                "run_dir": str(run_dir),
                "pause_kind": pause_kind,
                "step_id": step_id,
                "waiting_since": str(state.get("steps", [{}])[-1].get("finished_at", "") if state.get("steps") else ""),
                "hypothesis_id": hypothesis_id,
            }
        )
    if not rows:
        print("No paused runs found.")
        return 0
    frame = rows[: max(int(args.limit), 1)]
    print(pd.DataFrame(frame).to_string(index=False))
    return 0


def _validate_concern_scores_against_rules(
    payload: dict[str, Any],
    rule_by_id: dict[str, dict[str, Any]],
    measured_values: dict[str, Any],
) -> None:
    """Run the same semantic checks the gate_concern_scoring handler runs.

    Catches keyed_to_rule_id / anchor-metric / anchor-value-mismatch / severity-below-derived
    errors at CLI write time so the user never round-trips through a runtime failure that
    flips the step from ``paused`` to ``failed`` and clears pending_input (the recovery
    path is messy — see ``runtime.py`` ``status=='failed'`` branch in execute_dag).

    Mirrors src/research_orchestrator/steps.py::handle_gate_concern_scoring lines 1446-1478.
    """
    for score in payload.get("scores", []):
        concern_id = str(score.get("concern_id", ""))
        rule_id = str(score.get("keyed_to_rule_id", ""))
        if rule_id not in rule_by_id:
            raise ConcernEnforcementError(
                f"concern {concern_id}: keyed_to_rule_id '{rule_id}' not in rule table "
                f"(available: {sorted(rule_by_id)})"
            )
        rule_row = rule_by_id[rule_id]
        required_metric = str(rule_row.get("metric") or "")
        if not required_metric:
            raise ConcernEnforcementError(
                f"concern {concern_id}: rule '{rule_id}' has no metric field"
            )
        anchor = score.get("quantitative_anchor", {}) or {}
        if required_metric not in anchor:
            raise ConcernEnforcementError(
                f"concern {concern_id}: quantitative_anchor must contain the keyed rule metric '{required_metric}' "
                f"(got keys {sorted(anchor)})"
            )
        anchor_value = anchor[required_metric]
        if not isinstance(anchor_value, (int, float)):
            raise ConcernEnforcementError(
                f"concern {concern_id}: anchor[{required_metric}] must be numeric (got {type(anchor_value).__name__})"
            )
        actual_measured = measured_values.get(required_metric)
        if actual_measured is not None and abs(float(anchor_value) - float(actual_measured)) > 1e-6:
            raise ConcernEnforcementError(
                f"concern {concern_id}: anchor[{required_metric}]={anchor_value} does not match measured "
                f"value {actual_measured}"
            )
        derived = derive_severity(rule_row, anchor)
        declared = str(score.get("severity", ""))
        if _severity_rank(declared) < _severity_rank(derived):
            raise ConcernEnforcementError(
                f"concern {concern_id}: declared severity '{declared}' is lower than derived severity "
                f"'{derived}' (rule {rule_id} measured {anchor_value} vs threshold {rule_row.get('threshold')})"
            )


def _copy_and_validate_concern_scores(
    step_dir: Path,
    payload: dict[str, Any],
    *,
    rule_by_id: dict[str, dict[str, Any]] | None = None,
    measured_values: dict[str, Any] | None = None,
) -> Path:
    schema = get_schema("gate_concern_scores_v1")
    jsonschema_validate(instance=payload, schema=schema)
    if rule_by_id is not None:
        _validate_concern_scores_against_rules(
            payload, rule_by_id, measured_values or {}
        )
    output_path = step_dir / "gate_concern_scores.json"
    _atomic_write_json(output_path, payload)
    return output_path


def _score_concerns(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).resolve()
    step_id = str(args.step_id or "").strip()
    if not step_id:
        candidates = _find_gate_step_candidates(run_dir, pause_kind="pause_for_input", capability="gate_concern_scoring")
        if len(candidates) != 1:
            raise SystemExit(
                "Could not auto-detect a single paused gate_concern_scoring step. "
                f"Candidates: {candidates or 'none'}. Pass --step-id explicitly."
            )
        step_id = candidates[0]
    step_dir = run_dir / "steps" / step_id
    template_path = step_dir / "gate_concern_scores_template.json"
    if not template_path.exists():
        raise SystemExit(f"Concern template not found: {template_path}")
    template = _load_json(template_path)
    evaluation_step_id = _find_predecessor_step_id_from_plan(run_dir, step_id, "gate_evaluation")
    eval_outputs = _load_json(run_dir / "steps" / evaluation_step_id / "step_outputs.json")
    rule_table = list(eval_outputs.get("criteria_results", []))
    rule_by_id = {str(row.get("rule_id") or row.get("rule", "")): row for row in rule_table}

    if args.from_json:
        payload = _load_payload(Path(args.from_json).resolve())
    elif args.non_interactive:
        raise SystemExit("--from-json is required when --non-interactive is used")
    else:
        payload = dict(template)
        scores = []
        for score in template.get("scores", []):
            concern_text = str(score.get("concern_text", ""))
            print(f"Concern: {concern_text}")
            rule_id = input(f"Rule id {template.get('_rule_ids_available', [])}: ").strip()
            evidence_lines: list[str] = []
            print("Evidence (finish with a single '.' on its own line):")
            while True:
                line = input()
                if line == ".":
                    break
                evidence_lines.append(line)
            anchor_text = input("Quantitative anchor as JSON: ").strip()
            confirmed = input("Confirmed (y/n)? ").strip().lower() in {"y", "yes"}
            anchor = json.loads(anchor_text)
            severity = derive_severity(rule_by_id.get(rule_id), anchor)
            scores.append(
                {
                    "concern_id": score["concern_id"],
                    "concern_text": concern_text,
                    "keyed_to_rule_id": rule_id,
                    "measured_evidence_against_concern": "\n".join(evidence_lines).strip(),
                    "quantitative_anchor": anchor,
                    "confirmed": confirmed,
                    "severity": severity,
                }
            )
        payload = {"scores": scores}

    measured_values = dict(eval_outputs.get("measured_values", {}))
    output_path = _copy_and_validate_concern_scores(
        step_dir, payload, rule_by_id=rule_by_id, measured_values=measured_values
    )
    print(f"Saved to {output_path}. Resume with: research_orchestrator_cli.py resume --run-dir {run_dir}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    store = HypothesisRegistryStore(args.registry_dir)

    if args.command == "register":
        return _register_hypothesis(store, args)
    if args.command == "draft":
        return _draft_hypothesis(args)
    if args.command == "show":
        return _show_hypothesis(store, args)
    if args.command == "list":
        return _list_hypotheses(store, args)
    if args.command == "approve":
        return _record_gate_decision(
            store=store,
            run_dir=Path(args.run_dir).resolve(),
            gate_step=str(args.gate_step),
            reviewer=str(args.reviewer),
            reason=str(args.reason),
            decision="approved",
        )
    if args.command == "reject":
        return _record_gate_decision(
            store=store,
            run_dir=Path(args.run_dir).resolve(),
            gate_step=str(args.gate_step),
            reviewer=str(args.reviewer),
            reason=str(args.reason),
            decision="rejected",
        )
    if args.command == "quarantine":
        return _record_gate_decision(
            store=store,
            run_dir=Path(args.run_dir).resolve(),
            gate_step=str(args.gate_step),
            reviewer=str(args.reviewer),
            reason=str(args.reason),
            decision="quarantined",
        )
    if args.command == "verify-seal":
        return _verify_seal(args)
    if args.command == "pending-gates":
        return _pending_gates(args)
    if args.command == "score-concerns":
        return _score_concerns(args)
    if args.command == "summary":
        print(store.summary_text())
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
