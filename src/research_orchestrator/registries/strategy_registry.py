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

# R2 Major 1 + R3 Major 1 — the governed-runner VERIFIER registry: a LIVE artifact is
# promotable only when its governed_execution attestation names a runner registered HERE,
# and the registered value is a VERIFIER CALLABLE (called with the attestation + the
# canonical artifact; it must raise PromotionGateError on any inconsistency) — never a
# bare name string. The registry is EMPTY until the governed S6 book runner PR lands
# (which registers its verifier), so every live artifact — including one hand-seeded
# into the stores — FAILS CLOSED at the promotion gate. Independent of the verifier, the
# gate itself resolves the attested execution profile against the REAL profile registry
# (unknown id / not-allowed-for-formal / hash mismatch all refuse), so registering a
# runner name can never skip profile verification. Do not add entries outside the S6 PR.
REGISTERED_GOVERNED_RUNNER_VERIFIERS: dict[str, Any] = {}
_GOVERNED_ATTESTATION_FIELDS = (
    "runner_id",
    "runner_version",
    "execution_profile_id",
    "execution_profile_hash",
    "allowed_for_formal",
    "return_type",
    "max_gross_exposure",
    "result_hash",
)


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
    diagnostic_store=None,
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
    * the artifact's verdict re-hashes to the EXECUTION-TIME ``book_verdict_hash`` the
      state machine persisted when the OOS ran, and that persisted verdict passed —
      the gate never re-judges with the current evaluator (R7 B3: the persisted
      verdict is final; evaluator drift = quarantine/migrate, never silent re-judgment);
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

    # R7 Blocker 3: the EXECUTION-TIME persisted verdict is the FINAL arbiter — the gate
    # verifies the artifact's embedded verdict IS the verdict the state machine persisted
    # when the OOS ran (book_verdict_hash recorded at persist_verdict time), then requires
    # bar_passed. It NEVER re-judges with the current evaluator: a later code version
    # (changed thresholds, changed conventions) must not be able to flip an already-
    # observed verdict in either direction; evaluator drift is a quarantine/migrate
    # decision, not a silent re-judgment. (The plan's pre_declared_bar and the evaluator
    # semantics were sealed into the identity/verdict at execution time.)
    verdict = artifact.get("book_verdict") if isinstance(artifact.get("book_verdict"), Mapping) else {}
    plan_payload = artifact.get("plan") if isinstance(artifact.get("plan"), Mapping) else {}
    if not isinstance(plan_payload.get("pre_declared_bar"), Mapping) or not isinstance(
        verdict.get("metrics"), Mapping
    ):
        _refuse(label, "artifact lacks plan.pre_declared_bar / book_verdict.metrics")
    metrics = verdict.get("metrics")
    state_row = artifact_store.current(key)
    persisted_hash = str((state_row or {}).get("book_verdict_hash") or "").strip()
    if not persisted_hash:
        _refuse(label, "the artifact store carries no execution-time book_verdict_hash for "
                       "this key — a pre-R7 record must be explicitly migrated, never "
                       "re-judged by current code")
    from src.alpha_research.factor_eval_skill._hashing import payload_hash as _vphash

    if _vphash(dict(verdict)) != persisted_hash:
        _refuse(label, "artifact book_verdict differs from the execution-time persisted "
                       "verdict (book_verdict_hash mismatch) — the persisted verdict is "
                       "immutable and final")
    if verdict.get("bar_passed") is not True:
        _refuse(label, "the execution-time persisted verdict did not pass the pre-declared "
                       "bar — a book that failed its own bar cannot be promoted")

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

    # R2 Major 3: the diagnostic rows must EXIST in the durable StrategyComponentDiagnosticStore
    # — artifact-embedded rows alone (with dangling record ids) are not evidence.
    if diagnostic_store is not None:
        ids = diag.get("diagnostic_record_ids")
        if not isinstance(ids, list) or not ids:
            _refuse(label, "component_diagnostics.diagnostic_record_ids is empty — the durable "
                           "diagnostic rows were never written")
        store_rows = diagnostic_store.list_all()
        by_id = {str(r["record_id"]): r for _, r in store_rows.iterrows()} if not store_rows.empty else {}
        seen_components = set()
        for rid in ids:
            row = by_id.get(str(rid))
            if row is None:
                _refuse(label, f"diagnostic record id {rid!r} does not exist in the "
                               f"StrategyComponentDiagnosticStore — dangling evidence reference")
            if str(row["book_seal_key"]) != key:
                _refuse(label, f"diagnostic record {rid!r} belongs to book_seal_key "
                               f"{row['book_seal_key']!r}, not {key!r}")
            if str(row["request_hash"]) != str(artifact.get("request_hash", "")):
                _refuse(label, f"diagnostic record {rid!r} belongs to a different request")
            seen_components.add(str(row["component_factor_id"]))
        artifact_components = {str(e.get("component_factor_id")) for e in rows_list}
        if seen_components != artifact_components:
            _refuse(label, f"durable diagnostic components {sorted(seen_components)} != the "
                           f"artifact's {sorted(artifact_components)}")

    # R2 Major 1 (LAST check, after every binding): a live artifact must carry a
    # governed_execution attestation from a REGISTERED governed runner. The registry is
    # empty until the S6 runner PR — every live artifact fails closed here until then.
    governed = artifact.get("governed_execution")
    if not isinstance(governed, Mapping) or not governed:
        _refuse(label, "artifact carries no governed_execution attestation — a live artifact "
                       "must be produced by a REGISTERED governed runner (none exist yet: the "
                       "S6 runner PR adds the first); live artifacts fail closed until then")
    missing_att = [f for f in _GOVERNED_ATTESTATION_FIELDS if str(governed.get(f, "")).strip() == ""]
    if missing_att:
        _refuse(label, f"governed_execution attestation missing {missing_att}")
    if governed.get("allowed_for_formal") is not True:
        _refuse(label, "governed_execution.allowed_for_formal must be literally True")
    if str(governed.get("return_type")) != "total_return":
        _refuse(label, f"governed_execution.return_type must be 'total_return' "
                       f"(got {governed.get('return_type')!r})")
    try:
        gross_ok = float(governed.get("max_gross_exposure")) <= 1.0
    except (TypeError, ValueError):
        gross_ok = False
    if not gross_ok:
        _refuse(label, f"governed_execution.max_gross_exposure must be <= 1.0 "
                       f"(got {governed.get('max_gross_exposure')!r})")
    from src.alpha_research.factor_eval_skill._hashing import payload_hash as _phash

    if str(governed.get("result_hash")) != _phash({str(k): v for k, v in metrics.items()}):
        _refuse(label, "governed_execution.result_hash does not recompute from the persisted "
                       "book metrics — the attestation is not bound to this result")
    # R3 Major 1: resolve the attested execution profile against the REAL registry —
    # registering a runner name can never skip this. Unknown id / not formal / hash
    # mismatch all refuse (the same triple the release gate enforces for artifacts).
    from src.backtest_engine.execution_profiles import ExecutionProfileError, get_profile

    try:
        profile = get_profile(str(governed.get("execution_profile_id")))
    except ExecutionProfileError as exc:
        _refuse(label, f"governed_execution.execution_profile_id does not resolve: {exc}")
    if not profile.allowed_for_formal:
        _refuse(label, f"execution profile {profile.profile_id!r} is not allowed_for_formal")
    if str(governed.get("execution_profile_hash")) != str(profile.profile_hash):
        _refuse(label, f"governed_execution.execution_profile_hash "
                       f"{governed.get('execution_profile_hash')!r} != the live registry's "
                       f"{profile.profile_hash!r} for {profile.profile_id!r}")
    runner_id = str(governed.get("runner_id", ""))
    verifier = REGISTERED_GOVERNED_RUNNER_VERIFIERS.get(runner_id)
    if verifier is None:
        _refuse(label, f"governed_execution.runner_id {runner_id!r} has no REGISTERED governed-"
                       f"runner VERIFIER (registered: "
                       f"{sorted(REGISTERED_GOVERNED_RUNNER_VERIFIERS) or 'NONE — S6 pending'}) "
                       f"— fail-closed")
    verifier(governed=governed, artifact=artifact)
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
    ) -> dict[str, Any]:
        """Gate privileged promotions (PIT-prevention step 11 + v1.4 A8 book-seal wiring).

        A transition to a PRIVILEGED registry status (e.g. ``"approved"``) is refused
        unless (P1.1) ``promotion_evidence`` proves an INDEPENDENT PIT-correct
        reconstruction and passes the lint/canary/clean-tree checks
        (:func:`src.research_orchestrator.release_gate.evaluate_promotion_artifact`)
        with a matching committed ``current_git_sha``, AND (v1.4 A8) the approval is
        bound to the CANONICAL book sealed-evaluation artifact — R7 Blocker 4: the
        seal store, artifact store, and diagnostic store all derive from the ONE
        configured global holdout root (:func:`resolve_configured_global_holdout_root`);
        there are NO caller store/dir parameters, so a fully-consistent sealed world
        fabricated in a caller-chosen directory can never be promoted. S6 must write
        its live artifacts into the same canonical root.

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
            # R7 Blocker 4: every governance store at the CANONICAL root — never a
            # caller-supplied path or store object.
            from src.alpha_research.factor_eval_skill.book_seal_stores import (
                BookSealArtifactStore,
                StrategyComponentDiagnosticStore,
            )
            from src.research_orchestrator.holdout_seal import (
                HoldoutSealStore,
                resolve_configured_global_holdout_root,
            )

            root = resolve_configured_global_holdout_root()
            assert_book_seal_promotion_evidence(
                object_id=str(object_id),
                registry_store=self,
                artifact_store=BookSealArtifactStore(root),
                seal_store=HoldoutSealStore(root),
                diagnostic_store=StrategyComponentDiagnosticStore(root),
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
    # R7 Blocker 4: the artifact loads from the CANONICAL store — no caller store param.
    from src.alpha_research.factor_eval_skill.book_seal_stores import BookSealArtifactStore
    from src.research_orchestrator.holdout_seal import resolve_configured_global_holdout_root

    artifact_store = BookSealArtifactStore(resolve_configured_global_holdout_root())
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
