"""Immutable content-addressable YAML factor specs for hypothesis workflows."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_HYPOTHESIS_FACTOR_DIR = PROJECT_ROOT / "data" / "hypothesis_factors"

HYPOTHESIS_FACTOR_SCHEMA = {
    "required": [
        "factor_id",
        "category",
        "expression",
        "price_basis",
        "thesis_nl",
        "mechanism",
        "expected_sign",
        "expected_decay_horizon_days",
        "expected_effect",
        "default_neutralization",
        "source",
    ],
    "expected_effect_fields": ["statistic", "point_estimate", "ci_low", "ci_high"],
    "source_fields": [
        "type",
        "identifier",
        "title",
        "authors",
        "publication_date",
        "publisher",
        "url",
    ],
}


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)


def compute_spec_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_json_dumps(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class HypothesisFactorSpec:
    spec_hash: str
    factor_id: str
    category: str
    expression: str
    price_basis: str
    thesis_nl: str
    mechanism: str
    expected_sign: int
    expected_decay_horizon_days: int
    expected_effect: dict[str, Any]
    default_neutralization: list[str] = field(default_factory=list)
    source: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def hypothesis_factor_root(root_dir: str | Path | None = None) -> Path:
    return Path(root_dir or DEFAULT_HYPOTHESIS_FACTOR_DIR).resolve()


def compile_to_qlib_expression(spec: HypothesisFactorSpec) -> str:
    return str(spec.expression)


def load_hypothesis_factor(spec_hash: str, root_dir: str | Path | None = None) -> HypothesisFactorSpec:
    root = hypothesis_factor_root(root_dir)
    path = root / f"{spec_hash}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Hypothesis factor spec not found: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    actual_hash = compute_spec_hash(payload)
    if actual_hash != spec_hash:
        raise ValueError(f"Spec hash mismatch for {path.name}: expected {spec_hash}, got {actual_hash}")
    return HypothesisFactorSpec(spec_hash=spec_hash, **payload)


def list_hypothesis_factors(root_dir: str | Path | None = None) -> list[HypothesisFactorSpec]:
    root = hypothesis_factor_root(root_dir)
    if not root.exists():
        return []
    specs: list[HypothesisFactorSpec] = []
    for path in sorted(root.glob("*.yaml")):
        specs.append(load_hypothesis_factor(path.stem, root))
    return specs
