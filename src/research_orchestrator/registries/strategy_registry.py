from __future__ import annotations

import json
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

# v1.4 PR3 (A8): the 8 BookSealIdentity fields a strategy promotion artifact must carry so
# the gate can RECOMPUTE book_seal_key (tamper check) instead of trusting the stored string.
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


def assert_book_seal_promotion_evidence(
    artifact: Mapping[str, Any] | None,
    *,
    seal_store,
    artifact_label: str = "strategy",
) -> dict[str, Any]:
    """v1.4 A8 — the book-seal wiring of the strategy promotion door. A privileged
    strategy transition must be backed by the ONE book sealed-evaluation artifact
    (amendment §2 A2): this verifies, fail-closed,

    * a ``book_seal`` section exists and carries ``book_seal_key`` + the full
      :data:`BOOK_SEAL_IDENTITY_FIELDS` identity payload;
    * the key RECOMPUTES from the identity payload (``BookSealIdentity``) — a stored
      key that does not match its own fields is tampered/stale;
    * ``mode`` is literally ``"live"`` (a dryrun pilot artifact is never promotable);
    * the seal spend actually HAPPENED: a ``HoldoutSealStore`` event exists with
      ``seal_key == book_seal_key``;
    * the book verdict PASSED its pre-declared bar (``bar_passed is True`` — literal
      True, mirroring the strict-literal discipline);
    * the component-diagnostics leg completed (``component_diagnostics_ok is True``) —
      the A2 artifact reports BOTH layers, and a diagnostics failure blocks promotion
      until the artifact is regenerated via same-run resume.

    Returns the validated ``book_seal`` section.
    """
    cfg = artifact or {}
    book = cfg.get("book_seal")
    if not isinstance(book, Mapping) or not book:
        raise PromotionGateError(
            f"Promotion gate blocked {artifact_label}: promotion_evidence must carry a "
            f"'book_seal' section (the v1.4 A2 book sealed-evaluation artifact) — factor-level "
            f"or seal-less evidence cannot promote a strategy"
        )
    key = str(book.get("book_seal_key", "")).strip()
    if not key:
        raise PromotionGateError(
            f"Promotion gate blocked {artifact_label}: book_seal.book_seal_key is required"
        )
    identity_payload = book.get("book_seal_identity")
    if not isinstance(identity_payload, Mapping):
        raise PromotionGateError(
            f"Promotion gate blocked {artifact_label}: book_seal.book_seal_identity (the full "
            f"identity payload) is required so the key can be recomputed"
        )
    missing = [f for f in BOOK_SEAL_IDENTITY_FIELDS if not str(identity_payload.get(f, "")).strip()]
    if missing:
        raise PromotionGateError(
            f"Promotion gate blocked {artifact_label}: book_seal_identity missing {missing}"
        )
    from src.alpha_research.factor_eval_skill.identity import BookSealIdentity

    recomputed = BookSealIdentity(
        **{f: str(identity_payload[f]) for f in BOOK_SEAL_IDENTITY_FIELDS}
    ).book_seal_key
    if recomputed != key:
        raise PromotionGateError(
            f"Promotion gate blocked {artifact_label}: book_seal_key {key!r} does not recompute "
            f"from its identity payload (got {recomputed!r}) — tampered or stale artifact"
        )
    if str(book.get("mode", "")).strip() != "live":
        raise PromotionGateError(
            f"Promotion gate blocked {artifact_label}: book_seal.mode must be 'live' "
            f"(got {book.get('mode')!r}); a dryrun pilot artifact is never promotable"
        )
    events = seal_store.list_events(seal_key=key)
    if events.empty:
        raise PromotionGateError(
            f"Promotion gate blocked {artifact_label}: no holdout seal event exists for "
            f"book_seal_key {key!r} — the spend this artifact reports never happened in the "
            f"supplied seal store"
        )
    verdict = book.get("book_verdict")
    if not isinstance(verdict, Mapping) or verdict.get("bar_passed") is not True:
        raise PromotionGateError(
            f"Promotion gate blocked {artifact_label}: book_verdict.bar_passed must be "
            f"literally True (got {None if not isinstance(verdict, Mapping) else verdict.get('bar_passed')!r}) "
            f"— a book that failed its pre-declared bar cannot be promoted"
        )
    if book.get("component_diagnostics_ok") is not True:
        raise PromotionGateError(
            f"Promotion gate blocked {artifact_label}: component_diagnostics_ok must be "
            f"literally True — the A2 artifact reports BOTH the book verdict and the "
            f"component diagnostics; regenerate via same-run resume if the leg failed"
        )
    return dict(book)


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
        seal_store=None,
    ) -> dict[str, Any]:
        """Gate privileged promotions (PIT-prevention step 11 + v1.4 A8 book-seal wiring).

        A transition to a PRIVILEGED registry status (e.g. ``"approved"``) is the
        decision-layer act that the val_heavy near-deployment slipped through. It
        is now refused unless ``promotion_evidence`` proves the strategy's signal
        panel was INDEPENDENTLY reconstructed through a PIT-correct data path
        (``qlib_windowed_features`` / JoinQuant-native / ``audited_pit_source``) —
        a sandbox/loader panel is insufficient — AND the evidence artifact passes
        the lint/parity/clean-tree checks (see
        :func:`src.research_orchestrator.release_gate.evaluate_promotion_artifact`),
        AND (v1.4 A8, PR3) the evidence is wired to the ONE book sealed-evaluation
        artifact: a recomputable ``book_seal_key``, an existing seal event in the
        holdout store (``holdout_seal_dir`` / ``seal_store`` is therefore REQUIRED
        for a privileged transition), a LIVE-mode run, a PASSED pre-declared bar,
        and completed component diagnostics
        (:func:`assert_book_seal_promotion_evidence`).

        Non-privileged transitions (candidate / under_review / rejected / archived)
        are unchanged. Raises :class:`PromotionGateError` when the gate fails.
        """
        if str(status).strip().lower() in PRIVILEGED_REGISTRY_STATUSES:
            # current_git_sha is MANDATORY for a privileged transition — it binds
            # the approval to a committed HEAD (the artifact's git_sha must match),
            # so the gate cannot be satisfied from an uncommitted / unknown tree by
            # simply omitting the SHA. (GPT PR #22 round-3.)
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
            # v1.4 A8 (PR3): the strategy promotion door is additionally wired to the
            # book seal artifact — fail-closed if no seal store is supplied to verify
            # the spend against.
            if seal_store is None:
                if not holdout_seal_dir:
                    raise PromotionGateError(
                        f"Promotion gate blocked strategy_candidate:{object_id}: "
                        f"holdout_seal_dir (or seal_store) is required for a privileged "
                        f"strategy transition — the book seal spend must be verified "
                        f"against the holdout store (v1.4 A8)"
                    )
                from src.research_orchestrator.holdout_seal import HoldoutSealStore

                seal_store = HoldoutSealStore(holdout_seal_dir)
            assert_book_seal_promotion_evidence(
                artifact,
                seal_store=seal_store,
                artifact_label=f"strategy_candidate:{object_id}",
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
    artifact: Mapping[str, Any],
    research_profile: str = "book_sealed_evaluation",
    run_dir: str | Path | None = None,
    display_name_zh: str = "",
    notes: str = "",
    generated_at: str | None = None,
) -> dict[str, Any]:
    """v1.4 PR3 — publish a ``StrategyCandidate`` v0 carrying its book sealed-evaluation
    artifact, through the sanctioned :meth:`TypedRegistryStore.publish_objects` door.

    The published row's ``definition_payload_json`` embeds the full A2 artifact under
    ``"book_seal"`` (so the later privileged ``set_status('approved')`` evidence can be
    assembled from the registry row) and its ``definition_hash`` is the
    ``book_seal_key`` — the strategy's spend identity. Status starts at the store's
    default (``candidate``); promotion to ``approved`` is the SEPARATE gated
    :meth:`StrategyRegistryStore.set_status` call. Fail-closed: the artifact must be a
    book sealed-evaluation artifact with a non-blank ``book_seal_key``.
    """
    art = dict(artifact or {})
    if art.get("artifact_type") != "book_sealed_evaluation":
        raise ValueError(
            f"publish_strategy_candidate requires a book_sealed_evaluation artifact, got "
            f"artifact_type={art.get('artifact_type')!r}"
        )
    key = str(art.get("book_seal_key", "")).strip()
    if not key:
        raise ValueError("publish_strategy_candidate: artifact.book_seal_key is blank")
    name = str(object_name).strip()
    if not name:
        raise ValueError("publish_strategy_candidate: object_name is required")
    generated = generated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    definition = {
        "schema_version": 1,
        "object_kind": "strategy_candidate_v0",
        "book_seal": art,
    }
    snapshot = TypedObjectSnapshot(
        object_id=f"strategy_candidate::{name}",
        object_name=name,
        object_type="strategy_candidate",
        research_profile=research_profile,
        definition_payload_json=json.dumps(definition, ensure_ascii=False, sort_keys=True),
        definition_hash=key,
        display_name_zh=display_name_zh,
        notes=notes,
    )
    summary = {
        "book_seal_key": key,
        "mode": art.get("mode"),
        "oos_window_id": art.get("oos_window_id"),
        "bar_passed": (art.get("book_verdict") or {}).get("bar_passed"),
        "promotion_eligible": art.get("promotion_eligible"),
    }
    result = store.publish_objects(
        run_type="book_sealed_evaluation",
        research_profile=research_profile,
        run_dir=run_dir,
        generated_at=generated,
        objects=[snapshot],
        summaries_by_object_id={snapshot.object_id: summary},
    )
    store.save()
    return result
