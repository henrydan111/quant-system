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
# Provider raw-input attestation gate (Phase 5-B, calendar unfreeze B3.2)
# ─────────────────────────────────────────────────────────────────────────
#
# The monthly atomic publish binds every new provider build to the exact raw-input
# cut it consumed (provider_build.json.raw_input_manifest_root = sha256 root of the
# full-readset raw_input_manifest). This gate makes that binding LOAD-BEARING for
# formal runs: when the run's calendar policy declares
# ``require_raw_input_attestation: true`` (every policy minted by the monthly bump
# does), a live manifest WITHOUT a valid root fails the formal run. Legacy/pre-thaw
# policies leave the flag unset, so providers that predate the attestation keep
# working — enforcement rolls forward with the policies, never retroactively.

_SHA256_HEX_ALPHABET = frozenset("0123456789abcdef")


class ProviderAttestationError(RuntimeError):
    """A formal run's calendar policy requires a raw-input attestation the live
    provider manifest does not carry (or carries malformed)."""


@dataclass(frozen=True)
class ProviderAttestationGateResult:
    eligible: bool
    required: bool
    policy_id: str | None
    provider_build_id: str | None
    raw_input_manifest_root: str | None
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_provider_raw_attestation(
    *,
    manifest: Any,
    policy: Any,
) -> ProviderAttestationGateResult:
    """Decide whether the live provider manifest satisfies the policy's raw-input
    attestation requirement.

    ``manifest`` is a ``ProviderManifest`` (attribute access) or a plain mapping of
    the on-disk ``provider_build.json``; ``policy`` is a ``CalendarPolicy`` (or any
    object with ``policy_id`` + ``require_raw_input_attestation``). Duck-typed on
    purpose so this module adds no data_infra import edges.
    """
    def _get(obj: Any, key: str) -> Any:
        if isinstance(obj, Mapping):
            return obj.get(key)
        return getattr(obj, key, None)

    policy_id = _get(policy, "policy_id")
    required = _get(policy, "require_raw_input_attestation") is True
    build_id = _get(manifest, "provider_build_id")
    root = _get(manifest, "raw_input_manifest_root")

    reasons: list[str] = []
    if required:
        if root is None or not str(root).strip():
            reasons.append(
                f"calendar policy {policy_id!r} requires a raw-input attestation but the "
                f"live provider manifest (build {build_id!r}) carries no "
                "raw_input_manifest_root — the build was not published through the "
                "attested monthly transaction (or the manifest was replaced)."
            )
        else:
            root_s = str(root)
            if len(root_s) != 64 or any(c not in _SHA256_HEX_ALPHABET for c in root_s):
                reasons.append(
                    f"raw_input_manifest_root on build {build_id!r} is not a 64-char sha256 "
                    f"hex root ({root_s!r}) — corrupted attestation."
                )

    return ProviderAttestationGateResult(
        eligible=len(reasons) == 0,
        required=required,
        policy_id=str(policy_id) if policy_id is not None else None,
        provider_build_id=str(build_id) if build_id is not None else None,
        raw_input_manifest_root=str(root) if root is not None else None,
        reasons=tuple(reasons),
    )


def assert_provider_raw_attestation(
    *,
    manifest: Any,
    policy: Any,
    artifact_label: str = "formal run",
) -> ProviderAttestationGateResult:
    """Strict variant of :func:`evaluate_provider_raw_attestation` for formal paths.

    Wired at BOTH read chokepoints: the formal-run provider validation
    (``backtest_engine.event_driven._validate_provider_at_runtime``) and the shared
    live-provider resolution every sanctioned data door goes through
    (``data_infra.provider_context._resolve``).
    """
    result = evaluate_provider_raw_attestation(manifest=manifest, policy=policy)
    if not result.eligible:
        raise ProviderAttestationError(
            f"Provider raw-input attestation gate blocked {artifact_label}: "
            f"{list(result.reasons)}"
        )
    return result


# ─────────────────────────────────────────────────────────────────────────
# Provider publish-state (QA quarantine) gate — Phase 5-B B3, GPT re-review Blocker 6
# ─────────────────────────────────────────────────────────────────────────
#
# The monthly atomic publish writes <qlib_dir>/metadata/publish_state.json with
# state="pending_qa" the moment the swap+rebind are durable, flips it to "ready" only
# after run_daily_qa PASSES, and to "qa_failed" on a QA failure. This gate makes that
# quarantine MECHANICAL: while the marker is not "ready", every gated read path refuses —
# a provider that published but failed (or has not yet run) QA cannot serve research.
# Roll-forward scoping mirrors the raw attestation: a policy with
# require_raw_input_attestation=True REQUIRES the marker to exist; legacy policies allow
# an absent marker (pre-5B providers never had one) but STILL honor a present non-ready
# marker (a written quarantine is always load-bearing).

PUBLISH_STATE_FILENAME = "publish_state.json"
PUBLISH_STATE_READY = "ready"
PUBLISH_STATE_PENDING_QA = "pending_qa"
PUBLISH_STATE_QA_FAILED = "qa_failed"


def read_provider_publish_state(qlib_dir: Any) -> dict[str, Any] | None:
    """The parsed publish-state marker for ``qlib_dir``, or ``None`` when absent.
    Malformed content returns ``{"state": "<malformed>"}`` so gated readers fail closed
    instead of treating corruption as legacy-absent."""
    path = Path(qlib_dir) / "metadata" / PUBLISH_STATE_FILENAME
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return {"state": "<malformed>"}
        return payload
    except (OSError, json.JSONDecodeError):
        return {"state": "<malformed>"}


def evaluate_provider_publish_state(
    *,
    qlib_dir: Any,
    policy: Any,
    manifest: Any = None,
) -> ProviderAttestationGateResult:
    """Decide whether the live provider's publish-state marker admits gated reads.

    When ``manifest`` is supplied, a present marker must also name the SAME
    ``provider_build_id`` — a marker left behind by a different build is corruption,
    not clearance."""
    def _get(obj: Any, key: str) -> Any:
        if isinstance(obj, Mapping):
            return obj.get(key)
        return getattr(obj, key, None)

    policy_id = _get(policy, "policy_id")
    required = _get(policy, "require_raw_input_attestation") is True
    build_id = _get(manifest, "provider_build_id") if manifest is not None else None
    state_payload = read_provider_publish_state(qlib_dir)

    reasons: list[str] = []
    if state_payload is None:
        if required:
            reasons.append(
                f"calendar policy {policy_id!r} requires the publish-state marker "
                f"(metadata/{PUBLISH_STATE_FILENAME}) but the live provider carries none — "
                "the build did not complete the attested publish transaction."
            )
    else:
        state = state_payload.get("state")
        if state != PUBLISH_STATE_READY:
            reasons.append(
                f"live provider publish-state is {state!r} (not '{PUBLISH_STATE_READY}') — "
                "post-publish QA has not passed; the provider is quarantined for gated "
                "reads. Run scripts/monthly_calendar_bump.py --finalize-qa after resolving."
            )
        # Phase 5-B re-review P0: a marker MUST name the build it certifies — a bare
        # {"state": "ready"} previously passed because the comparison was conditional on
        # the field being present, severing the "this QA verdict belongs to THIS build"
        # binding. Blank/missing marker build id fails closed; when the caller supplies
        # the manifest, exact equality is mandatory.
        marker_build = state_payload.get("provider_build_id")
        if not isinstance(marker_build, str) or not marker_build.strip():
            reasons.append(
                f"publish-state marker carries no provider_build_id ({marker_build!r}) — an "
                "unbound certification cannot clear any build; refusing."
            )
        elif build_id is not None and str(marker_build) != str(build_id):
            reasons.append(
                f"publish-state marker names build {marker_build!r} but the live manifest is "
                f"{build_id!r} — stale/foreign marker; refusing."
            )

    return ProviderAttestationGateResult(
        eligible=len(reasons) == 0,
        required=required,
        policy_id=str(policy_id) if policy_id is not None else None,
        provider_build_id=str(build_id) if build_id is not None else None,
        raw_input_manifest_root=None,
        reasons=tuple(reasons),
    )


def assert_provider_publish_state(
    *,
    qlib_dir: Any,
    policy: Any,
    manifest: Any = None,
    artifact_label: str = "gated read",
) -> ProviderAttestationGateResult:
    """Strict variant of :func:`evaluate_provider_publish_state` for gated paths."""
    result = evaluate_provider_publish_state(qlib_dir=qlib_dir, policy=policy, manifest=manifest)
    if not result.eligible:
        raise ProviderAttestationError(
            f"Provider publish-state gate blocked {artifact_label}: {list(result.reasons)}"
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

# Privileged REGISTRY STATUSES (the typed-registry `set_status` vocabulary) vs
# forward-looking PROMOTION LABELS — kept distinct (GPT PR #22 review): "approved"
# is a real registry status whose transition is enforced by
# StrategyRegistryStore.set_status; the labels are manual/external deployment tags.
PRIVILEGED_REGISTRY_STATUSES = frozenset({"approved"})
PRIVILEGED_PROMOTION_LABELS = frozenset(
    {"champion", "deployment_candidate", "live_candidate"}
)
# Sources that count as an INDEPENDENT PIT-correct reconstruction of the signal
# panel. Anything else (None, "", "sandbox", "pit_research_loader", ...) fails.
VALID_INDEPENDENT_REPRODUCTION_SOURCES = frozenset(
    {
        "qlib_windowed_features",  # formal provider path via the windowed wrapper
        "joinquant_native_pit",    # JoinQuant get_fundamentals(date=) + pubDate filtering
        "audited_pit_source",      # another audited PIT source — REQUIRES source_name + audit_artifact
    }
)
# The v5 §6.7 promotion-artifact checks REQUIRED for a privileged promotion —
# each must be explicitly "passed". Fail-closed: a MISSING key fails (a promotion
# artifact must positively attest every check, not omit it).
_REQUIRED_PASSED_CHECKS = (
    "unsafe_pit_dates_lint",
    "synthetic_lookahead_canary",
    "restatement_canary",
    "q0_canary_multiperiod",
    "q0_canary_stateful_restatement",
    "q0_canary_missing_field",
    "availability_assertion",
)


class PromotionGateError(RuntimeError):
    """A privileged promotion status/label lacks valid independent-reproduction evidence."""


class FactorLevelApprovedRetiredError(PromotionGateError):
    """v1.4 (2026-07-03): the factor-level `approved` mint is RETIRED — `candidate` is the
    terminal factor-level research status. Promotion is book-level: a sealed
    `DeploymentFrozenPlan`/`StrategyCandidate` through `StrategyRegistryStore` (one holdout
    seal per book, keyed by the derived `book_seal_key`). Legacy approved rows are
    revalidated via `FactorRegistryStore.revalidate_legacy_approved(...)`; the only mint
    exception is the audited `FactorRegistryStore.legacy_factor_approval_override(...)`.
    Design: workspace/research/factor_eval_methodology/FACTOR_EVAL_V1.4_AMENDMENT_book_level_promotion.md.
    """


@dataclass(frozen=True)
class PromotionGateResult:
    """Decision on whether a strategy may carry a privileged registry status or
    promotion label. Exploratory statuses/labels are always eligible."""
    status: str
    label: str
    privileged: bool
    reproduction_source: str | None
    eligible: bool
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _is_privileged(status: str | None, label: str | None) -> bool:
    return (
        (status or "").strip().lower() in PRIVILEGED_REGISTRY_STATUSES
        or (label or "").strip().lower() in PRIVILEGED_PROMOTION_LABELS
    )


def evaluate_promotion_eligibility(
    *,
    status: str | None = None,
    label: str | None = None,
    reproduction_source: str | None = None,
    reproduction_evidence: Mapping[str, Any] | None = None,
) -> PromotionGateResult:
    """Core source-level check: a privileged ``status`` (e.g. registry "approved")
    OR ``label`` (champion/deployment_candidate/live_candidate) requires
    ``reproduction_source`` ∈ VALID_INDEPENDENT_REPRODUCTION_SOURCES. The
    ``audited_pit_source`` source additionally requires a named source + audit
    artifact in ``reproduction_evidence``."""
    status_norm = (status or "").strip().lower()
    label_norm = (label or "").strip().lower()
    privileged = _is_privileged(status, label)
    src = (reproduction_source or "").strip()
    ev = reproduction_evidence or {}
    reasons: list[str] = []
    if privileged:
        if not src:
            reasons.append(
                "privileged promotion requires an independent PIT-correct reproduction "
                "source; none supplied"
            )
        elif src not in VALID_INDEPENDENT_REPRODUCTION_SOURCES:
            reasons.append(
                f"reproduction source '{src}' is not an INDEPENDENT PIT-correct path "
                f"(a sandbox/loader panel is insufficient). Allowed: "
                f"{sorted(VALID_INDEPENDENT_REPRODUCTION_SOURCES)}"
            )
        elif src == "audited_pit_source" and not (
            isinstance(ev, Mapping) and ev.get("source_name") and ev.get("audit_artifact")
        ):
            reasons.append(
                "audited_pit_source requires a named 'source_name' + 'audit_artifact' in "
                "independent_reproduction evidence (a bare magic string is insufficient)"
            )
    return PromotionGateResult(
        status=status_norm, label=label_norm, privileged=privileged,
        reproduction_source=reproduction_source,
        eligible=len(reasons) == 0, reasons=tuple(reasons),
    )


def evaluate_promotion_artifact(
    artifact: Mapping[str, Any] | None,
    *,
    current_git_sha: str | None = None,
) -> PromotionGateResult:
    """Evaluate the full v5 §6.7 promotion artifact: source + lint/canary/parity
    statuses + clean git state. For a privileged promotion, fails unless the
    independent reproduction is valid AND ``unsafe_pit_dates_lint``=="passed" AND
    ``live_provider_parity`` is "passed" (or a legal "not_required_for_label" with
    NO pit_research_loader anywhere) AND ``dirty_tree`` is not True AND (when
    ``current_git_sha`` is supplied) ``git_sha`` matches."""
    cfg = artifact or {}
    status = cfg.get("promotion_status")
    label = cfg.get("promotion_label")
    repro = cfg.get("independent_reproduction") if isinstance(cfg.get("independent_reproduction"), Mapping) else {}
    source = repro.get("source")
    base = evaluate_promotion_eligibility(
        status=status, label=label, reproduction_source=source, reproduction_evidence=repro,
    )
    reasons: list[str] = list(base.reasons)
    if base.privileged:
        for key in _REQUIRED_PASSED_CHECKS:
            if cfg.get(key) != "passed":
                reasons.append(f"{key} != 'passed' (got {cfg.get(key)!r}); required for privileged promotion")
        # live_provider_parity may be 'not_required_for_label' ONLY if NO
        # pit_research_loader panel entered the primary OR reproduction path.
        used_loader = (
            bool(cfg.get("primary_used_pit_research_loader"))
            or bool(cfg.get("reproduction_used_pit_research_loader"))
            or bool(repro.get("used_pit_research_loader"))
            or source == "pit_research_loader"
        )
        lpp = cfg.get("live_provider_parity")
        if lpp == "not_required_for_label":
            if used_loader:
                reasons.append(
                    "live_provider_parity='not_required_for_label' is illegal: a "
                    "pit_research_loader panel entered the primary or reproduction path"
                )
        elif lpp != "passed":
            reasons.append(f"live_provider_parity != 'passed' (got {lpp!r})")
        # Fail-closed on clean-state evidence: dirty_tree MUST be explicitly False.
        if cfg.get("dirty_tree") is not False:
            reasons.append(
                f"dirty_tree must be explicitly false for privileged promotion (got {cfg.get('dirty_tree')!r})"
            )
        # When a current SHA is supplied, the artifact MUST carry a matching git_sha.
        if current_git_sha is not None:
            git_sha = cfg.get("git_sha")
            if not git_sha:
                reasons.append("git_sha is required when current_git_sha is supplied")
            elif git_sha != current_git_sha:
                reasons.append(f"git_sha {git_sha!r} != current {current_git_sha!r}")
    return PromotionGateResult(
        status=base.status, label=base.label, privileged=base.privileged,
        reproduction_source=source, eligible=len(reasons) == 0, reasons=tuple(reasons),
    )


# Back-compat thin reader (now delegates to the full artifact evaluator).
def evaluate_promotion_from_artifact(
    artifact_config: Mapping[str, Any] | None,
) -> PromotionGateResult:
    return evaluate_promotion_artifact(artifact_config)


def assert_promotion_eligible(
    *,
    status: str | None = None,
    label: str | None = None,
    reproduction_source: str | None = None,
    reproduction_evidence: Mapping[str, Any] | None = None,
    artifact_label: str = "strategy",
) -> PromotionGateResult:
    """Strict source-level check — raises :class:`PromotionGateError` on an
    ineligible privileged status/label."""
    result = evaluate_promotion_eligibility(
        status=status, label=label, reproduction_source=reproduction_source,
        reproduction_evidence=reproduction_evidence,
    )
    if not result.eligible:
        raise PromotionGateError(
            f"Promotion gate blocked {artifact_label} (status={result.status!r} "
            f"label={result.label!r}): {list(result.reasons)}"
        )
    return result


def assert_promotion_artifact_eligible(
    artifact: Mapping[str, Any] | None,
    *,
    current_git_sha: str | None = None,
    artifact_label: str = "strategy",
) -> PromotionGateResult:
    """Strict full-artifact check — raises on any failed evidence requirement.
    This is what enforces a privileged registry status transition."""
    result = evaluate_promotion_artifact(artifact, current_git_sha=current_git_sha)
    if not result.eligible:
        raise PromotionGateError(
            f"Promotion gate blocked {artifact_label} (status={result.status!r} "
            f"label={result.label!r}): {list(result.reasons)}"
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
