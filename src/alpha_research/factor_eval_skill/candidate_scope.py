"""v1.4 A7 — target-scoped candidate admission (round-1 B1 + round-2 N1).

``allow_candidate_components=True`` admits only ``candidate_on_declared_target``: a
candidate whose latest Stage-5/Stage-3 evidence is bound to the CURRENT
``target_universe_declaration_hash``, or whose legacy evidence carries an explicitly
versioned TUD-equivalence alias with EXACT equality on the full TUD identity
(``target_universe_id`` + ``universe_definition_filters`` + ``eligibility_policy`` +
``asof_policy``). A status-only candidate match is REFUSED with
``candidate_scope_mismatch`` BEFORE dataset build and BEFORE any holdout access; the
refused candidate's path forward is a target-scoped IS re-audition under the current TUD
(cheap, IS-only, no OOS access). Universe-id equality alone is NEVER sufficient.

The orchestrator's ``hypothesis_validation`` prescriptions declare a
``UniverseSpec`` (theme/broad), not a TUD — ``tud_from_prescription_universe`` is the
CANONICAL, VERSIONED adapter (policy strings carry ``_v1``; changing the adapter changes
every derived ``tud_hash``, which is intentional: adapter drift = new scope identity).

Scope note (recorded for the implementation review): the Stage-3 lookup here relaxes the
``layer1_methodology_hash`` key component (the ADMISSION gate pins factor identity via
``definition_hash`` + TUD + role; the strict layer1-matched form remains in
``cmd_select``'s ``_assert_pool_eligible``, which runs before any selection).

Design: workspace/research/factor_eval_methodology/FACTOR_EVAL_V1.4_AMENDMENT_book_level_promotion.md §2 A7.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from src.alpha_research.factor_eval_skill._hashing import (
    canonical_json,
    payload_hash,
    to_jsonable,
)
from src.alpha_research.factor_eval_skill.identity import TargetUniverseDeclaration
from src.alpha_research.factor_eval_skill.stores import (
    Stage3QualityRecordStore,
    TudEquivalenceAliasStore,
)

# The versioned adapter identity: bumping this string re-scopes every derived TUD.
_ADAPTER_POLICY = "orchestrator_prescription_v1"


class CandidateScopeMismatchError(RuntimeError):
    """A candidate was admitted by status but its Stage-5 evidence is not bound to the
    declared target (no matching Stage-3 record, no exactly-equal TUD alias)."""


def tud_from_prescription_universe(universe_spec: Any) -> TargetUniverseDeclaration:
    """Canonical adapter: an orchestrator ``UniverseSpec`` (theme/broad) -> the
    ``TargetUniverseDeclaration`` its scope check keys on. Deterministic over
    ``UniverseSpec.normalized_dict()`` (the same stable payload ``design_hash`` uses)."""
    normalized = universe_spec.normalized_dict()
    kind = str(normalized.get("kind", ""))
    if kind == "theme":
        target_id = f"theme:{normalized.get('theme_universe_candidate_id', '')}"
    elif kind == "broad":
        target_id = f"broad:{payload_hash(normalized)[:16]}"
    else:  # pragma: no cover - UniverseSpec.validate() refuses unknown kinds upstream
        raise ValueError(f"unknown prescription universe kind: {kind!r}")
    return TargetUniverseDeclaration(
        target_universe_id=target_id,
        universe_definition_filters=normalized,
        eligibility_policy=_ADAPTER_POLICY,
        asof_policy=_ADAPTER_POLICY,
    )


def _eligible_scope_record(
    store: Stage3QualityRecordStore, *, factor_id: str, definition_hash: str, tud_hash: str
) -> Mapping[str, Any] | None:
    """The latest ELIGIBLE ranking/both Stage-3 record binding this factor (by
    definition_hash) to this target. Lazy import avoids importing the whole
    orchestration module at package-import time."""
    from src.alpha_research.factor_eval_skill.orchestration import (
        ALLOWED_SELECTION_ROLES,
        _ranking_record_eligible,
    )

    for role in ALLOWED_SELECTION_ROLES:
        rec = store.latest(
            factor_id=str(factor_id),
            definition_hash=str(definition_hash),
            target_universe_declaration_hash=str(tud_hash),
            role=role,
        )
        if rec is not None and _ranking_record_eligible(rec):
            return rec
    return None


def _alias_matches_tud(alias: Mapping[str, Any], tud: TargetUniverseDeclaration) -> tuple[bool, str]:
    """N1 exact-equality check: the alias payload must equal the CURRENT TUD on all four
    TUD-identity fields; any absent/stale/non-canonical/mismatched field refuses."""
    missing = [
        f for f in TudEquivalenceAliasStore.REQUIRED_FIELDS
        if not str(alias.get(f) or "").strip()
    ]
    if missing:
        return False, f"alias missing required fields {missing}"
    if str(alias.get("recorded_before_stage7_freeze")) != "True":
        return False, "alias not recorded before Stage-7 freeze"
    checks = (
        ("target_universe_id", str(tud.target_universe_id)),
        ("universe_definition_filters_json", canonical_json(to_jsonable(tud.universe_definition_filters))),
        ("eligibility_policy", str(tud.eligibility_policy)),
        ("asof_policy", str(tud.asof_policy)),
    )
    for field, expected in checks:
        if str(alias.get(field) or "") != expected:
            return False, (
                f"alias {field} mismatch vs current TUD (universe-id equality alone is "
                f"never sufficient — round-2 N1)"
            )
    return True, ""


def assert_candidates_on_declared_target(
    store_root: str | Path,
    *,
    candidates: Sequence[tuple[str, str]],
    tud: TargetUniverseDeclaration,
    artifact_label: str = "",
) -> dict[str, Any]:
    """The A7 gate: every ``(factor_id, definition_hash)`` admitted as a candidate
    component must be ``candidate_on_declared_target`` — a matching eligible Stage-3
    record on ``tud.tud_hash``, or an exactly-equal TUD-equivalence alias. Refuses with
    ``CandidateScopeMismatchError`` (reason code ``candidate_scope_mismatch``) listing
    every failing factor. Returns a report mapping for the run artifact."""
    root = Path(store_root)
    stage3 = Stage3QualityRecordStore(root)
    aliases = TudEquivalenceAliasStore(root)
    tud_hash = tud.tud_hash

    report: dict[str, Any] = {
        "tud_hash": tud_hash,
        "target_universe_id": tud.target_universe_id,
        "checked": [],
        "mismatches": [],
    }
    for factor_id, definition_hash in candidates:
        rec = _eligible_scope_record(
            stage3, factor_id=factor_id, definition_hash=definition_hash, tud_hash=tud_hash
        )
        if rec is not None:
            report["checked"].append(
                {"factor_id": factor_id, "binding": "stage3_record", "record_id": rec.get("record_id", "")}
            )
            continue
        alias = aliases.latest_for_factor(factor_id=factor_id, definition_hash=definition_hash)
        if alias is not None:
            ok, why = _alias_matches_tud(alias, tud)
            if ok:
                report["checked"].append(
                    {"factor_id": factor_id, "binding": "tud_equivalence_alias",
                     "alias_id": alias.get("alias_id", "")}
                )
                continue
            report["mismatches"].append({"factor_id": factor_id, "reason": why})
        else:
            report["mismatches"].append(
                {"factor_id": factor_id,
                 "reason": "no eligible ranking/both Stage-3 record on the declared target "
                           "and no TUD-equivalence alias"}
            )
    if report["mismatches"]:
        details = "; ".join(f"{m['factor_id']}: {m['reason']}" for m in report["mismatches"])
        raise CandidateScopeMismatchError(
            f"candidate_scope_mismatch ({artifact_label or 'validation'}): "
            f"allow_candidate_components admits only candidate_on_declared_target "
            f"(target={tud.target_universe_id}, tud_hash={tud_hash[:16]}…) — {details}. "
            f"Path forward: run a target-scoped IS re-audition (characterize + gate under "
            f"this TUD via the factor-eval skill), or record a TUD-equivalence alias with "
            f"EXACT TUD-payload equality (universe-id equality alone is never sufficient). "
            f"Refused BEFORE dataset build and BEFORE any holdout access (v1.4 A7)."
        )
    return report
