"""FrozenSelectionSet — the immutable identity of a selected factor set for OOS sealing.

PR P1.4 of the factor_lifecycle plan. ``frozen_set_hash`` keys the holdout seal so the
OOS budget is spent per FROZEN SELECTION SET, not per mutable ``design_hash``:

- Editing pass/fail wording or success-criteria / expected-effect prose does NOT
  change the hash (those fields are simply not part of the payload), so a consumed
  OOS stays sealed across cosmetic edits.
- Changing the selected factors, their ``expected_direction``, the
  ``candidate_pool_hash`` (every factor visible to the selection rule, not just the
  selected ones), the ``selection_rule_hash``, the ``eval_protocol_hash``
  (preprocessing / winsor / rank / horizon / label / quantile / cost-slippage /
  missing-data / tie-break / universe-filter), the ``metric``, ``portfolio_side``,
  ``universe``, ``time_split_window``, ``rebalance``, or ``neutralization`` DOES
  change it.

Provider / calendar / build IDs are NOT in the hash — they are provenance carried
beside it. Serialization is strict: ``sort_keys``, compact separators,
``allow_nan=False``, ISO dates, normalized enum strings, no raw floats (only
ints / enums / hashes / decimal strings), no timestamps / run paths.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

SCHEMA_VERSION = 1


def _norm_enum(value: str) -> str:
    """Normalize an enum-ish string so cosmetic case/whitespace differences do not
    change the hash."""
    return str(value).strip().lower()


@dataclass(frozen=True)
class SelectedFactor:
    """One member of a frozen selection set. ``expected_direction`` is the sign the
    factor is held under (e.g. ``"long"`` / ``"short"`` / ``"neutral"``)."""

    factor_id: str
    version: int
    definition_hash: str
    expected_direction: str

    def to_payload(self) -> list[Any]:
        return [
            str(self.factor_id),
            int(self.version),
            str(self.definition_hash),
            _norm_enum(self.expected_direction),
        ]


@dataclass(frozen=True)
class FrozenSelectionSet:
    """An immutable, hashable selection set. ``selected`` is a tuple of
    :class:`SelectedFactor`; ``frozen_set_hash`` is order-independent over it."""

    selected: tuple[SelectedFactor, ...]
    candidate_pool_hash: str
    selection_rule_hash: str
    eval_protocol_hash: str
    metric: str
    portfolio_side: str
    universe: str
    time_split_window: str
    rebalance: str
    neutralization: str
    schema_version: int = SCHEMA_VERSION

    def _payload(self) -> dict[str, Any]:
        # Sort selected factors so the hash is independent of insertion order.
        selected_sorted = sorted(
            (factor.to_payload() for factor in self.selected),
            key=lambda payload: (payload[0], payload[1], payload[2]),
        )
        return {
            "schema_version": int(self.schema_version),
            "selected": selected_sorted,
            "candidate_pool_hash": str(self.candidate_pool_hash),
            "selection_rule_hash": str(self.selection_rule_hash),
            "eval_protocol_hash": str(self.eval_protocol_hash),
            "metric": _norm_enum(self.metric),
            "portfolio_side": _norm_enum(self.portfolio_side),
            "universe": _norm_enum(self.universe),
            "time_split_window": str(self.time_split_window),
            "rebalance": _norm_enum(self.rebalance),
            "neutralization": _norm_enum(self.neutralization),
        }

    @property
    def frozen_set_hash(self) -> str:
        """sha256 over the strict-serialized payload. EXCLUDES all pass/fail wording
        and provider/calendar/build IDs (carried beside as provenance)."""
        serialized = json.dumps(
            self._payload(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
            ensure_ascii=True,
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def to_provenance(self) -> dict[str, Any]:
        """The hashed payload + the hash, for recording beside the seal (the
        provider/calendar/build IDs are recorded separately by the caller)."""
        return {"frozen_set_hash": self.frozen_set_hash, "payload": self._payload()}
