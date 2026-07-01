"""Canonical payload hashing for factor-eval-skill identity objects.

Mirrors ``src/research_orchestrator/frozen_selection_set.py`` EXACTLY so hashes are
consistent project-wide: sha256 over ``json.dumps(payload, sort_keys=True,
separators=(",", ":"), allow_nan=False, ensure_ascii=True)``. This is the single
serialization used before every skill-object hash and before every structured-field
write, so a TUD/SelectedSet/Envelope/Plan hash computed here is bit-comparable with a
``FrozenSelectionSet.frozen_set_hash`` computed there.

Part-G v2 over-engineering rule: even YAML-authored records must be parsed into a
canonical normalized payload before hashing — never hash raw YAML/JSON text. Use
:func:`payload_hash` on the normalized mapping, not on the source string.
"""
from __future__ import annotations

import hashlib
import json
from types import MappingProxyType
from typing import Any, Mapping


def normalize_enum(value: str) -> str:
    """Normalize an enum-ish string so cosmetic case/whitespace differences do not
    change the hash (mirrors ``FrozenSelectionSet._norm_enum``)."""
    return str(value).strip().lower()


def canonical_json(payload: Any) -> str:
    """Strict deterministic serialization: sorted keys (recursively), compact
    separators, no NaN/inf, ascii. The one serialization used before every hash."""
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        ensure_ascii=True,
    )


def payload_hash(payload: Any) -> str:
    """sha256 hex over :func:`canonical_json`. The single hashing primitive for all
    identity-critical objects (TUD / SelectedSet / Envelope / Plan) and for the
    ``role_context_hash``; identical algorithm to ``FrozenSelectionSet.frozen_set_hash``."""
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def normalize_mapping(mapping: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a JSON-native, deterministically-serializable dict (``{}`` for ``None``).

    Fail-closed: validates serializability up-front (via :func:`canonical_json`) so a
    non-JSON-native or NaN/inf-bearing filter/construction spec raises at construction
    time, not silently at hash time."""
    if mapping is None:
        return {}
    normalized = dict(mapping)
    canonical_json(normalized)  # raises TypeError/ValueError if not JSON-native or NaN/inf
    return normalized


def deep_freeze(obj: Any) -> Any:
    """Recursively convert a JSON-native structure into an immutable one (Mapping ->
    MappingProxyType, list/tuple -> tuple). Identity dataclasses freeze their Mapping fields
    with this at construction so a later in-place mutation CANNOT silently change the object's
    hash (GPT cross-review 2026-06-21: a frozen dataclass does NOT deep-freeze its dicts)."""
    if isinstance(obj, Mapping):
        return MappingProxyType({str(k): deep_freeze(v) for k, v in obj.items()})
    if isinstance(obj, (list, tuple)):
        return tuple(deep_freeze(v) for v in obj)
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    raise TypeError(f"non-JSON-native value in identity payload: {type(obj).__name__}")


def to_jsonable(obj: Any) -> Any:
    """Recursively convert a :func:`deep_freeze`-d structure back to JSON-native dict/list
    (the form :func:`canonical_json` serializes)."""
    if isinstance(obj, Mapping):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    return obj


def frozen_mapping(value: Mapping[str, Any] | None) -> MappingProxyType:
    """Deep-freeze a mapping (``{}`` for ``None``) AND validate it is JSON-native + finite —
    fail-closed at construction, not at hash time. The return is read-only (mutation raises)."""
    frozen = deep_freeze(dict(value) if value is not None else {})
    canonical_json(to_jsonable(frozen))  # raises on non-native / NaN / inf
    return frozen
