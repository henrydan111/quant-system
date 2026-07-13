from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from src.research_orchestrator.registries.typed_store import (
    TypedObjectSnapshot,
    TypedRegistryStore,
)
from src.research_orchestrator.release_gate import (
    PRIVILEGED_REGISTRY_STATUSES,
    PromotionGateError,
    assert_promotion_artifact_eligible,
)

# v1.4 PR3 (A8): the 8 BookSealIdentity fields the canonical artifact must carry so
# the gate can RECOMPUTE book_seal_key (tamper check) instead of trusting a stored string.
BOOK_SEAL_IDENTITY_FIELDS = (
    "plan_hash",
    "frozen_set_hash",
    "selected_set_hash",
    "target_universe_declaration_hash",
    "execution_envelope_hash",
    "eval_protocol_hash",
    "oos_window_id",
    "pre_declared_bar_hash",
)
# Mandatory finite metrics per component-diagnostic row (mirrors book_seal's contract).
_MANDATORY_DIAG_METRICS = ("oos_rank_icir", "oos_ls_sharpe")


def _refuse(object_id: str, reason: str) -> None:
    raise PromotionGateError(
        f"Promotion gate blocked strategy_candidate:{object_id}: {reason}"
    )


def assert_book_seal_promotion_evidence(
    *,
    object_id: str,
    registry_store: "StrategyRegistryStore",
    artifact_store,
    seal_store,
    version: int | None = None,
) -> dict[str, Any]:
    """v1.4 A8 (post-R1-REWORK Blocker 2) — the book-seal wiring of the strategy
    promotion door. The gate NEVER accepts a caller-supplied artifact dictionary: it
    loads the CANONICAL artifact from the ``BookSealArtifactStore`` by the
    content hash the REGISTRY ROW references, then verifies fail-closed that

    * the registry row being approved references exactly this artifact
      (``definition_hash == artifact.book_seal_key`` and the row payload's
      ``artifact_hash`` is the loaded content hash — cross-object evidence refused);
    * the ``book_seal_key`` RECOMPUTES from the artifact's 8-field identity payload;
    * ``mode`` is literally ``"live"`` (a dryrun pilot artifact is never promotable);
    * the seal spend actually happened AND is THIS artifact's spend: a
      ``HoldoutSealStore`` event exists with ``seal_key == book_seal_key`` whose
      ``event_id`` and ``request_hash`` match the artifact's, and whose
      run/step/provider/calendar/stage bindings match;
    * the bar verdict is RECOMPUTED from the persisted metrics against the plan's
      pre-declared bar (an edited ``bar_passed`` boolean is worthless) and passes;
    * the component diagnostics are complete: rows present, every row carrying finite
      mandatory metrics, count consistent — recomputed, not trusted from a boolean;
    * the artifact's multiplicity decision did not require a refused override.

    Returns the validated canonical artifact.
    """
    label = str(object_id)
    rows = registry_store.find_current(
        object_type="strategy_candidate", object_id=str(object_id),
        version=version,
    )
    if rows.empty:
        _refuse(label, "no current strategy_candidate row to approve (publish first)")
    row = rows.iloc[-1]
    try:
        definition = json.loads(str(row["definition_payload_json"]))
    except (TypeError, ValueError):
        _refuse(label, "registry row definition_payload_json is not valid JSON")
    ref = definition.get("book_seal") if isinstance(definition, Mapping) else None
    if not isinstance(ref, Mapping):
        _refuse(label, "registry row carries no book_seal reference — factor-level or "
                       "seal-less evidence cannot promote a strategy")
    artifact_hash = str(ref.get("artifact_hash", "")).strip()
    if not artifact_hash:
        _refuse(label, "registry row book_seal.artifact_hash is blank")

    # canonical artifact — loaded from the store, content-verified at read (R1 B2)
    from src.alpha_research.factor_eval_skill.book_seal_stores import BookSealStoreError

    try:
        artifact = artifact_store.load_artifact(artifact_hash)
    except BookSealStoreError as exc:
        _refuse(label, f"canonical artifact load failed: {exc}")

    key = str(artifact.get("book_seal_key", "")).strip()
    if not key:
        _refuse(label, "canonical artifact has no book_seal_key")
    if str(row["definition_hash"]) != key:
        _refuse(label, f"registry row definition_hash {row['definition_hash']!r} != the "
                       f"canonical artifact's book_seal_key {key!r} — foreign evidence refused")
    if str(ref.get("book_seal_key", "")) != key:
        _refuse(label, "registry row book_seal.book_seal_key does not match the canonical artifact")

    identity_payload = artifact.get("book_seal_identity")
    if not isinstance(identity_payload, Mapping):
        _refuse(label, "canonical artifact missing book_seal_identity")
    missing = [f for f in BOOK_SEAL_IDENTITY_FIELDS if not str(identity_payload.get(f, "")).strip()]
    if missing:
        _refuse(label, f"book_seal_identity missing {missing}")
    from src.alpha_research.factor_eval_skill.identity import BookSealIdentity

    recomputed = BookSealIdentity(
        **{f: str(identity_payload[f]) for f in BOOK_SEAL_IDENTITY_FIELDS}
    ).book_seal_key
    if recomputed != key:
        _refuse(label, f"book_seal_key {key!r} does not recompute from its identity payload "
                       f"(got {recomputed!r}) — tampered or stale artifact")

    if str(artifact.get("mode", "")).strip() != "live":
        _refuse(label, f"artifact mode must be 'live' (got {artifact.get('mode')!r}); a dryrun "
                       f"pilot artifact is never promotable")

    # the seal spend must exist AND be THIS artifact's spend (R1 B2)
    events = seal_store.list_events(seal_key=key)
    if events.empty:
        _refuse(label, f"no holdout seal event exists for book_seal_key {key!r}")
    event = events.iloc[0].to_dict()
    art_event = artifact.get("seal_event") if isinstance(artifact.get("seal_event"), Mapping) else {}
    if str(event.get("event_id", "")) != str(art_event.get("event_id", "")):
        _refuse(label, f"seal event_id mismatch: store {event.get('event_id')!r} vs artifact "
                       f"{art_event.get('event_id')!r}")
    if str(event.get("request_hash", "")) != str(artifact.get("request_hash", "")):
        _refuse(label, f"seal request_hash {event.get('request_hash')!r} != artifact "
                       f"request_hash {artifact.get('request_hash')!r}")
    for field, art_value in (
        ("run_dir", artifact.get("run_dir")),
        ("step_id", artifact.get("step_id")),
        ("provider_build_id", artifact.get("provider_build_id")),
        ("calendar_policy_id", artifact.get("calendar_policy_id")),
        ("stage", "oos_test"),
    ):
        if str(event.get(field, "")) != str(art_value):
            _refuse(label, f"seal event {field} {event.get(field)!r} != artifact {art_value!r}")
    if str(identity_payload.get("oos_window_id")) != str(artifact.get("oos_window_id")):
        _refuse(label, "artifact oos_window_id does not match its identity payload")

    # recompute the bar from the persisted metrics — never trust a stored boolean (R1 B2)
    verdict = artifact.get("book_verdict") if isinstance(artifact.get("book_verdict"), Mapping) else {}
    plan_payload = artifact.get("plan") if isinstance(artifact.get("plan"), Mapping) else {}
    bar = plan_payload.get("pre_declared_bar")
    metrics = verdict.get("metrics")
    if not isinstance(bar, Mapping) or not isinstance(metrics, Mapping):
        _refuse(label, "artifact lacks plan.pre_declared_bar / book_verdict.metrics to recompute the bar")
    from src.alpha_research.factor_eval_skill.book_seal import (
        BookSealError,
        evaluate_pre_declared_bar,
    )

    try:
        recomputed_verdict = evaluate_pre_declared_bar(metrics, bar)
    except BookSealError as exc:
        _refuse(label, f"bar recomputation failed: {exc}")
    if not recomputed_verdict.bar_passed:
        _refuse(label, "the RECOMPUTED pre-declared bar does not pass — a book that failed its "
                       "own bar cannot be promoted")
    if verdict.get("bar_passed") is not True:
        _refuse(label, "persisted bar_passed is not literally True (inconsistent artifact)")

    # diagnostics completeness — recomputed from the rows, never a trusted boolean (R1 B4)
    diag = artifact.get("component_diagnostics")
    if not isinstance(diag, Mapping):
        _refuse(label, "artifact carries no component_diagnostics")
    rows_list = diag.get("rows")
    if not isinstance(rows_list, list) or not rows_list:
        _refuse(label, "component_diagnostics.rows is empty — the A2 artifact must report the "
                       "component leg")
    if int(diag.get("n_components", -1)) != len(rows_list):
        _refuse(label, "component_diagnostics.n_components does not match its rows")
    for entry in rows_list:
        fid = entry.get("component_factor_id", "?")
        for metric in _MANDATORY_DIAG_METRICS:
            try:
                ok = math.isfinite(float(entry.get(metric)))
            except (TypeError, ValueError):
                ok = False
            if not ok:
                _refuse(label, f"component diagnostic for {fid!r} has non-finite {metric!r}")
        if entry.get("promotion_eligible") not in (False, "False"):
            _refuse(label, f"component diagnostic for {fid!r} claims promotion eligibility — "
                           f"diagnostics mint no status")

    action = str((artifact.get("multiplicity") or {}).get("action", ""))
    if action == "refuse_without_override":
        _refuse(label, "the artifact's governing multiplicity report is refuse_without_override")
    return artifact


class StrategyRegistryStore(TypedRegistryStore):
    def __init__(self, registry_dir: str | Path) -> None:
        super().__init__(
            registry_dir,
            registry_slug="strategy_registry",
            allowed_object_types=("strategy_candidate",),
            review_title="Strategy Registry Review",
        )

    def set_status(
        self,
        *,
        object_id: str,
        status: str,
        reason: str,
        version: int | None = None,
        source_run_id: str | None = None,
        promotion_evidence: Mapping[str, Any] | None = None,
        current_git_sha: str | None = None,
        holdout_seal_dir: str | Path | None = None,
        book_artifact_dir: str | Path | None = None,
        seal_store=None,
        artifact_store=None,
    ) -> dict[str, Any]:
        """Gate privileged promotions (PIT-prevention step 11 + v1.4 A8 book-seal wiring).

        A transition to a PRIVILEGED registry status (e.g. ``"approved"``) is refused
        unless (P1.1) ``promotion_evidence`` proves an INDEPENDENT PIT-correct
        reconstruction and passes the lint/canary/clean-tree checks
        (:func:`src.research_orchestrator.release_gate.evaluate_promotion_artifact`)
        with a matching committed ``current_git_sha``, AND (v1.4 A8, post-R1-REWORK)
        the approval is bound to the CANONICAL book sealed-evaluation artifact loaded
        from the ``BookSealArtifactStore`` (``book_artifact_dir`` / ``artifact_store``)
        and cross-checked against the holdout store (``holdout_seal_dir`` /
        ``seal_store``) — see :func:`assert_book_seal_promotion_evidence`. Both stores
        are REQUIRED for a privileged transition (fail-closed).

        Non-privileged transitions (candidate / under_review / rejected / archived)
        are unchanged. Raises :class:`PromotionGateError` when the gate fails.
        """
        if str(status).strip().lower() in PRIVILEGED_REGISTRY_STATUSES:
            if not current_git_sha:
                raise PromotionGateError(
                    f"Promotion gate blocked strategy_candidate:{object_id}: "
                    f"current_git_sha is required for a privileged registry status "
                    f"transition (binds the approval to a committed HEAD)"
                )
            artifact = dict(promotion_evidence or {})
            # Force (NOT setdefault) the transition status: a caller-supplied
            # promotion_status="draft"/"candidate" would otherwise make the gate
            # evaluate the artifact as non-privileged and trivially pass — an
            # approval bypass (GPT cross-review P0, mirror of the factor-registry fix).
            artifact["promotion_status"] = status
            assert_promotion_artifact_eligible(
                artifact,
                current_git_sha=current_git_sha,
                artifact_label=f"strategy_candidate:{object_id}",
            )
            if seal_store is None:
                if not holdout_seal_dir:
                    _refuse(str(object_id),
                            "holdout_seal_dir (or seal_store) is required for a privileged "
                            "strategy transition — the book seal spend must be verified "
                            "against the holdout store (v1.4 A8)")
                from src.research_orchestrator.holdout_seal import HoldoutSealStore

                seal_store = HoldoutSealStore(holdout_seal_dir)
            if artifact_store is None:
                if not book_artifact_dir:
                    _refuse(str(object_id),
                            "book_artifact_dir (or artifact_store) is required for a privileged "
                            "strategy transition — the gate loads the CANONICAL artifact, never "
                            "a caller-supplied dictionary (v1.4 A8 / R1 Blocker 2)")
                from src.alpha_research.factor_eval_skill.book_seal_stores import (
                    BookSealArtifactStore,
                )

                artifact_store = BookSealArtifactStore(book_artifact_dir)
            assert_book_seal_promotion_evidence(
                object_id=str(object_id),
                registry_store=self,
                artifact_store=artifact_store,
                seal_store=seal_store,
                version=version,
            )
        return super().set_status(
            object_id=object_id,
            status=status,
            reason=reason,
            version=version,
            source_run_id=source_run_id,
        )


def publish_strategy_candidate(
    store: StrategyRegistryStore,
    *,
    object_name: str,
    artifact_hash: str,
    artifact_store,
    research_profile: str = "book_sealed_evaluation",
    run_dir: str | Path | None = None,
    display_name_zh: str = "",
    notes: str = "",
    generated_at: str | None = None,
) -> dict[str, Any]:
    """v1.4 PR3 (post-R1-REWORK) — publish a ``StrategyCandidate`` v0 referencing its
    CANONICAL book sealed-evaluation artifact, through the sanctioned
    :meth:`TypedRegistryStore.publish_objects` door.

    The artifact is LOADED from the ``BookSealArtifactStore`` by ``artifact_hash``
    (never accepted as a caller dictionary — R1 B2); the row's
    ``definition_payload_json`` stores the REFERENCE (``artifact_hash`` +
    ``book_seal_key`` + window/mode) and ``definition_hash = book_seal_key``.
    Same-key immutability (R1 B2): republishing an object whose current row already
    references a DIFFERENT payload refuses instead of mutating the row in place;
    an identical republish is an idempotent no-op. Status starts at the store's
    default; promotion to ``approved`` is the SEPARATE gated
    :meth:`StrategyRegistryStore.set_status` call."""
    key_hash = str(artifact_hash).strip()
    if not key_hash:
        raise ValueError("publish_strategy_candidate: artifact_hash is required")
    artifact = artifact_store.load_artifact(key_hash)   # canonical; raises if absent/tampered
    if artifact.get("artifact_type") != "book_sealed_evaluation":
        raise ValueError(
            f"publish_strategy_candidate requires a book_sealed_evaluation artifact, got "
            f"artifact_type={artifact.get('artifact_type')!r}"
        )
    key = str(artifact.get("book_seal_key", "")).strip()
    if not key:
        raise ValueError("publish_strategy_candidate: canonical artifact has no book_seal_key")
    name = str(object_name).strip()
    if not name:
        raise ValueError("publish_strategy_candidate: object_name is required")
    object_id = f"strategy_candidate::{name}"
    definition = {
        "schema_version": 2,
        "object_kind": "strategy_candidate_v0",
        "book_seal": {
            "artifact_hash": key_hash,
            "book_seal_key": key,
            "oos_window_id": artifact.get("oos_window_id"),
            "mode": artifact.get("mode"),
        },
    }
    payload_json = json.dumps(definition, ensure_ascii=False, sort_keys=True)
    existing = store.find_current(object_type="strategy_candidate", object_id=object_id)
    if not existing.empty:
        prior = existing.iloc[-1]
        if str(prior["definition_payload_json"]) == payload_json:
            return {"run_id": None, "object_count": 0, "object_ids": [object_id],
                    "idempotent": True}
        raise ValueError(
            f"publish_strategy_candidate: {object_id} already exists with a DIFFERENT payload "
            f"— rows are immutable; a changed evaluation is a NEW object/version, never an "
            f"in-place update (R1 Blocker 2)"
        )
    generated = generated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    snapshot = TypedObjectSnapshot(
        object_id=object_id,
        object_name=name,
        object_type="strategy_candidate",
        research_profile=research_profile,
        definition_payload_json=payload_json,
        definition_hash=key,
        display_name_zh=display_name_zh,
        notes=notes,
    )
    summary = {
        "book_seal_key": key,
        "artifact_hash": key_hash,
        "mode": artifact.get("mode"),
        "oos_window_id": artifact.get("oos_window_id"),
        "bar_passed": (artifact.get("book_verdict") or {}).get("bar_passed"),
        "promotion_eligible": artifact.get("promotion_eligible"),
        "diagnostic_record_ids": (artifact.get("component_diagnostics") or {}).get(
            "diagnostic_record_ids", []
        ),
    }
    result = store.publish_objects(
        run_type="book_sealed_evaluation",
        research_profile=research_profile,
        run_dir=run_dir,
        generated_at=generated,
        objects=[snapshot],
        summaries_by_object_id={object_id: summary},
    )
    store.save()
    return result
