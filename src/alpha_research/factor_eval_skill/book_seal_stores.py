"""v1.4 PR3 REWORK (GPT implementation review R1, 2026-07-12) — the three stores that make
the book seal spend IMMUTABLE, AUTHORIZED, and AUDITABLE:

* :class:`BookSealArtifactStore` — the canonical, append-only state machine of a book
  sealed evaluation (``claimed → verdict_persisted → complete | diagnostics_failed``).
  The FIRST persisted book verdict is immutable; resume can finish unfinished work but
  can never re-run a persisted verdict or reopen a complete artifact (R1 Blocker 1).
  The promotion gate loads the canonical artifact FROM HERE by ``artifact_hash`` —
  never from a caller-supplied dictionary (R1 Blocker 2).
* :class:`OverrideAuthorizationStore` — consume-once, pre-recorded, scope-bound override
  authorizations for A5 fresh-window studies and A6 multiplicity overrides. An invented
  non-empty string is NOT an authorization (R1 Blocker 3/5): the record must pre-exist
  with an explicit human sign-off + burn statement, match the window/scope exactly, and
  is consumed exactly once.
* :class:`StrategyComponentDiagnosticStore` — durable append-only component-diagnostic
  rows (R1 Major 2), keyed by ``book_seal_key + request_hash + component_factor_id``
  (the artifact stores the resulting record ids; ``artifact_hash`` then covers them).

All three follow the repo's ``AppendOnlyStore`` pattern (string schema, atomic write,
whole read-check-append under ``file_lock``).
"""
from __future__ import annotations

import json
from typing import Any, Mapping

import pandas as pd

from src.alpha_research.factor_eval_skill._hashing import canonical_json, payload_hash
from src.alpha_research.factor_eval_skill._store import (
    AppendOnlyStore,
    _atomic_write_dataframe,
    _now_str,
)
from src.research_orchestrator.file_lock import file_lock

ARTIFACT_STATES = ("claimed", "verdict_persisted", "diagnostics_failed", "complete")
OVERRIDE_KINDS = ("a5_fresh_window", "a6_multiplicity")


class BookSealStoreError(RuntimeError):
    """Fail-closed error for the book-seal stores."""


class BookSealArtifactStore(AppendOnlyStore):
    """The canonical state machine + immutable artifact record of a book sealed
    evaluation. Append-only: each state transition is a new row carrying the prior
    verdict forward; ``current()`` returns the latest row per ``book_seal_key``.

    Invariants (enforced fail-closed):
    - one ``claimed`` open per ``book_seal_key`` (a second ``open_claim`` refuses);
    - ``persist_verdict`` only from ``claimed``, and only ONCE — the verdict is
      immutable thereafter (every later row carries it verbatim);
    - ``complete`` only from ``verdict_persisted`` / ``diagnostics_failed``, only once;
    - every transition must match the opening ``request_hash`` (a changed request can
      never continue a prior spend).
    """

    FILENAME = "book_seal_artifacts.parquet"
    COLUMNS = (
        "record_id",
        "recorded_at",
        "book_seal_key",
        "request_hash",
        "state",
        "run_dir",
        "step_id",
        "mode",
        "oos_window_id",
        "provider_build_id",
        "calendar_policy_id",
        "seal_event_id",
        "book_verdict_json",
        "book_verdict_hash",
        "artifact_json",
        "artifact_hash",
        "error",
    )
    SCHEMA = {column: "string" for column in COLUMNS}
    KEY_FIELDS = ("book_seal_key", "state")

    def current(self, book_seal_key: str) -> dict[str, Any] | None:
        frame = self._load()
        frame = frame[frame["book_seal_key"].astype("string") == str(book_seal_key)]
        if frame.empty:
            return None
        return frame.iloc[-1].to_dict()

    def _append_locked_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """Append one pre-validated row; caller MUST already hold ``self.lock_path``."""
        recorded_at = _now_str()
        full: dict[str, Any] = {column: "" for column in self.COLUMNS}
        full.update({k: ("" if v is None else v) for k, v in row.items()})
        full["recorded_at"] = recorded_at
        full["record_id"] = self._record_id(full, recorded_at)
        frame = pd.concat([self._load(), pd.DataFrame([full])], ignore_index=True)
        _atomic_write_dataframe(frame, self.log_path)
        return full

    def open_claim(
        self,
        *,
        book_seal_key: str,
        request_hash: str,
        run_dir: str,
        step_id: str,
        mode: str,
        oos_window_id: str,
        provider_build_id: str,
        calendar_policy_id: str,
        seal_event_id: str,
    ) -> dict[str, Any]:
        if not str(book_seal_key).strip() or not str(request_hash).strip():
            raise BookSealStoreError("open_claim requires non-blank book_seal_key + request_hash")
        with file_lock(self.lock_path):
            existing = self.current(book_seal_key)
            if existing is not None:
                raise BookSealStoreError(
                    f"open_claim refused: book_seal_key {book_seal_key} already has state "
                    f"{existing.get('state')!r} (resume goes through the runner's resume path)"
                )
            return self._append_locked_row(
                {
                    "book_seal_key": str(book_seal_key),
                    "request_hash": str(request_hash),
                    "state": "claimed",
                    "run_dir": str(run_dir),
                    "step_id": str(step_id),
                    "mode": str(mode),
                    "oos_window_id": str(oos_window_id),
                    "provider_build_id": str(provider_build_id),
                    "calendar_policy_id": str(calendar_policy_id),
                    "seal_event_id": str(seal_event_id),
                }
            )

    def _transition(
        self,
        *,
        book_seal_key: str,
        request_hash: str,
        allowed_from: tuple[str, ...],
        new_state: str,
        extra: Mapping[str, Any],
    ) -> dict[str, Any]:
        with file_lock(self.lock_path):
            cur = self.current(book_seal_key)
            if cur is None:
                raise BookSealStoreError(f"no open claim for book_seal_key {book_seal_key}")
            if str(cur.get("request_hash")) != str(request_hash):
                raise BookSealStoreError(
                    f"request_hash mismatch for {book_seal_key}: transition under "
                    f"{request_hash!r} but the claim was opened under {cur.get('request_hash')!r}"
                )
            state = str(cur.get("state"))
            if state not in allowed_from:
                raise BookSealStoreError(
                    f"illegal transition {state!r} -> {new_state!r} for {book_seal_key} "
                    f"(allowed from {allowed_from})"
                )
            row = {
                column: cur.get(column, "")
                for column in self.COLUMNS
                if column not in ("record_id", "recorded_at")
            }
            row.update(extra)
            row["state"] = new_state
            return self._append_locked_row(row)

    def persist_verdict(
        self, *, book_seal_key: str, request_hash: str, verdict: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Persist the IMMUTABLE book verdict, exactly once, from ``claimed``."""
        verdict_json = canonical_json(dict(verdict))
        return self._transition(
            book_seal_key=book_seal_key,
            request_hash=request_hash,
            allowed_from=("claimed",),
            new_state="verdict_persisted",
            extra={
                "book_verdict_json": verdict_json,
                "book_verdict_hash": payload_hash(dict(verdict)),
            },
        )

    def mark_diagnostics_failed(
        self, *, book_seal_key: str, request_hash: str, error: str
    ) -> dict[str, Any]:
        return self._transition(
            book_seal_key=book_seal_key,
            request_hash=request_hash,
            allowed_from=("verdict_persisted", "diagnostics_failed"),
            new_state="diagnostics_failed",
            extra={"error": str(error)},
        )

    def complete(
        self, *, book_seal_key: str, request_hash: str, artifact: Mapping[str, Any]
    ) -> dict[str, Any]:
        artifact_json = canonical_json(dict(artifact))
        return self._transition(
            book_seal_key=book_seal_key,
            request_hash=request_hash,
            allowed_from=("verdict_persisted", "diagnostics_failed"),
            new_state="complete",
            extra={
                "artifact_json": artifact_json,
                "artifact_hash": payload_hash(dict(artifact)),
            },
        )

    def load_artifact(self, artifact_hash: str) -> dict[str, Any]:
        """Load the CANONICAL completed artifact by content hash — the ONLY artifact
        source the promotion gate accepts. Verifies the stored json re-hashes to the
        requested hash (tamper check at read time)."""
        frame = self._load()
        frame = frame[
            (frame["state"].astype("string") == "complete")
            & (frame["artifact_hash"].astype("string") == str(artifact_hash))
        ]
        if frame.empty:
            raise BookSealStoreError(f"no complete artifact with artifact_hash {artifact_hash!r}")
        raw = str(frame.iloc[-1]["artifact_json"])
        artifact = json.loads(raw)
        if payload_hash(artifact) != str(artifact_hash):
            raise BookSealStoreError(
                f"artifact store row for {artifact_hash!r} does not re-hash to its own key — "
                "store corruption or tamper"
            )
        return artifact


class OverrideAuthorizationStore(AppendOnlyStore):
    """Pre-recorded, consume-once, scope-bound override authorizations (R1 B3/B5).

    ``record_authorization`` is the HUMAN act (explicit sign-off + burn statement +
    bounded scope), done BEFORE any access. ``consume_authorization`` is the machine
    act: under one lock it verifies the record exists, the kind/window/scope match
    EXACTLY, it has not been consumed, then appends the consumption row. An invented
    override id, a scope mismatch, or a second use all refuse."""

    FILENAME = "override_authorizations.parquet"
    COLUMNS = (
        "record_id",
        "recorded_at",
        "action",              # authorized | consumed
        "kind",                # a5_fresh_window | a6_multiplicity
        "override_id",
        "oos_window_id",
        "scope_key",           # frozen_set_hash (A5) / book_seal_key or family (A6)
        "user_signoff",
        "reason",
        "adjusted_stats_note", # A6: the adjusted max-stat/FDR/DSR/PSR commitment
        "consumed_by_request_hash",
    )
    SCHEMA = {column: "string" for column in COLUMNS}
    KEY_FIELDS = ("kind", "override_id", "action")

    def record_authorization(
        self,
        *,
        kind: str,
        override_id: str,
        oos_window_id: str,
        scope_key: str,
        user_signoff: str,
        reason: str,
        adjusted_stats_note: str = "",
    ) -> dict[str, Any]:
        if kind not in OVERRIDE_KINDS:
            raise BookSealStoreError(f"kind must be one of {OVERRIDE_KINDS}, got {kind!r}")
        for name, value in (
            ("override_id", override_id),
            ("oos_window_id", oos_window_id),
            ("scope_key", scope_key),
            ("user_signoff", user_signoff),
            ("reason", reason),
        ):
            if not str(value).strip():
                raise BookSealStoreError(f"record_authorization requires non-blank {name}")
        if kind == "a6_multiplicity" and not str(adjusted_stats_note).strip():
            raise BookSealStoreError(
                "an a6_multiplicity authorization must commit to adjusted statistics "
                "(adjusted_stats_note) — the hard budget is never bypassed for free"
            )
        with file_lock(self.lock_path):
            frame = self._load()
            dup = frame[
                (frame["kind"].astype("string") == kind)
                & (frame["override_id"].astype("string") == str(override_id))
            ]
            if not dup.empty:
                raise BookSealStoreError(
                    f"override_id {override_id!r} already exists for kind {kind!r} "
                    "(override ids are single-use and never re-recorded)"
                )
            recorded_at = _now_str()
            row: dict[str, Any] = {column: "" for column in self.COLUMNS}
            row.update(
                {
                    "action": "authorized",
                    "kind": kind,
                    "override_id": str(override_id),
                    "oos_window_id": str(oos_window_id),
                    "scope_key": str(scope_key),
                    "user_signoff": str(user_signoff),
                    "reason": str(reason),
                    "adjusted_stats_note": str(adjusted_stats_note),
                }
            )
            row["recorded_at"] = recorded_at
            row["record_id"] = self._record_id(row, recorded_at)
            frame = pd.concat([frame, pd.DataFrame([row])], ignore_index=True)
            _atomic_write_dataframe(frame, self.log_path)
            return row

    def consume_authorization(
        self,
        *,
        kind: str,
        override_id: str,
        oos_window_id: str,
        scope_key: str,
        consumed_by_request_hash: str = "",
    ) -> dict[str, Any]:
        if kind not in OVERRIDE_KINDS:
            raise BookSealStoreError(f"kind must be one of {OVERRIDE_KINDS}, got {kind!r}")
        if not str(override_id).strip():
            raise BookSealStoreError(f"a non-blank {kind} override_id is required")
        with file_lock(self.lock_path):
            frame = self._load()
            mine = frame[
                (frame["kind"].astype("string") == kind)
                & (frame["override_id"].astype("string") == str(override_id))
            ]
            auth = mine[mine["action"].astype("string") == "authorized"]
            if auth.empty:
                raise BookSealStoreError(
                    f"override_id {override_id!r} (kind={kind}) was never pre-recorded — an "
                    "invented string is not an authorization; record it with an explicit user "
                    "sign-off BEFORE access"
                )
            record = auth.iloc[-1].to_dict()
            if str(record.get("oos_window_id")) != str(oos_window_id):
                raise BookSealStoreError(
                    f"override {override_id!r} is bound to window "
                    f"{record.get('oos_window_id')!r}, not {oos_window_id!r}"
                )
            if str(record.get("scope_key")) != str(scope_key):
                raise BookSealStoreError(
                    f"override {override_id!r} is bound to scope "
                    f"{record.get('scope_key')!r}, not {scope_key!r}"
                )
            consumed = mine[mine["action"].astype("string") == "consumed"]
            if not consumed.empty:
                raise BookSealStoreError(
                    f"override {override_id!r} was already consumed at "
                    f"{consumed.iloc[-1]['recorded_at']} — authorizations are single-use"
                )
            recorded_at = _now_str()
            row = {column: record.get(column, "") for column in self.COLUMNS}
            row["action"] = "consumed"
            row["consumed_by_request_hash"] = str(consumed_by_request_hash)
            row["recorded_at"] = recorded_at
            row["record_id"] = self._record_id(row, recorded_at)
            frame = pd.concat([frame, pd.DataFrame([row])], ignore_index=True)
            _atomic_write_dataframe(frame, self.log_path)
            return row


class StrategyComponentDiagnosticStore(AppendOnlyStore):
    """Durable, append-only component-diagnostic rows (R1 Major 2). Keyed by
    ``book_seal_key + request_hash + component_factor_id``; the completed artifact stores
    the record ids, so ``artifact_hash`` covers them transitively. Never writes any
    factor-master status."""

    FILENAME = "strategy_component_diagnostics.parquet"
    COLUMNS = (
        "record_id",
        "recorded_at",
        "book_seal_key",
        "request_hash",
        "book_plan_hash",
        "component_factor_id",
        "component_side",
        "component_weight",
        "oos_window_id",
        "oos_rank_icir",
        "oos_ls_sharpe",
        "aligned_rank_icir",
        "aligned_ls_sharpe",
        "reference_pass",
        "run_type",
        "spent_in_book_context",
        "fresh_oos_eligible",
        "promotion_eligible",
    )
    SCHEMA = {column: "string" for column in COLUMNS}
    KEY_FIELDS = ("book_seal_key", "request_hash", "component_factor_id")

    def append_rows(self, rows: list[Mapping[str, Any]]) -> list[str]:
        ids: list[str] = []
        for row in rows:
            written = self.record(**{k: str(v) for k, v in row.items() if k in self.COLUMNS})
            ids.append(str(written["record_id"]))
        return ids
