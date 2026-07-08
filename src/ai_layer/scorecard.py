"""C16 · deterministic scorecard aggregation + LLM containment.

The LLM emits ONLY per-dimension 0-5 scores with evidence spans (C12 typed
records). Deterministic code computes::

    final = clamp( Σ weight[name]·score  −  Σ 2·penalty_score , 0, 100 )

(the serenity_scorecard shape). Containment rules (CONTRACTS.md C16):

- a record carrying an LLM-emitted ``final`` / ``action`` / ``decision`` /
  ``target_rank`` / ``buy`` / ``sell`` / ``tilt`` field is REJECTED outright —
  the LLM never emits the final number or an action;
- a factor score without evidence spans, outside [0,5], or with a name NOT in
  the PRE-REGISTERED weights is a **NO-SCORE**: it contributes 0 points
  (conservative), never a neutral-positive fill — and an invented score name
  cannot smuggle influence;
- penalties (red flags, C15) count UNCAPPED by registration — the risk
  direction is never throttled — at the fixed 2x weight.

Weights are a pre-registered immutable artifact (part of the CandidateID /
refinery_config_version); they are inputs here, never tuned here.

Enforced by: tests/ai_layer/test_scorecard_deterministic.py.
"""
from __future__ import annotations

from collections.abc import Mapping
from numbers import Number

PENALTY_MULTIPLIER = 2.0
FINAL_MIN, FINAL_MAX = 0.0, 100.0

#: LLM output fields that constitute a containment breach (C16: the LLM never
#: emits a final number or an action).
FORBIDDEN_FIELDS = ("final", "action", "decision", "target_rank", "buy", "sell", "tilt")


class ScorecardViolation(Exception):
    """The LLM output breached C16 containment (or the record is malformed)."""


def validate_scorecard_record(record: dict, *, weights: Mapping[str, float]) -> None:
    """Structural + containment validation. Raises ScorecardViolation."""
    if not isinstance(record, dict):
        raise ScorecardViolation("scorecard record must be a dict")
    for field in FORBIDDEN_FIELDS:
        if field in record:
            raise ScorecardViolation(
                f"LLM-emitted '{field}' breaches C16 containment — the LLM emits "
                f"dimension scores + evidence ONLY; deterministic code computes the final"
            )
    for key in ("factor_scores", "penalty_scores"):
        if key in record and not isinstance(record[key], list):
            raise ScorecardViolation(f"'{key}' must be a list of typed entries")
    for entry in record.get("factor_scores", []):
        if not isinstance(entry, dict) or "name" not in entry or "score_0_5" not in entry:
            raise ScorecardViolation(f"malformed factor_score entry: {entry!r}")
    if not weights:
        raise ScorecardViolation("pre-registered weights must be non-empty")


def _valid_score(value) -> bool:
    return isinstance(value, Number) and 0 <= float(value) <= 5


def compute_scorecard_final(record: dict, *, weights: Mapping[str, float]) -> float:
    """Deterministic final. NO-SCORE entries contribute 0 (never neutral-positive)."""
    validate_scorecard_record(record, weights=weights)

    points = 0.0
    for entry in record.get("factor_scores", []):
        name = entry.get("name")
        score = entry.get("score_0_5")
        evidence = entry.get("evidence_spans") or []
        if name not in weights:        # unregistered name -> no influence (C16b)
            continue
        if not evidence:               # unsupported -> NO-SCORE
            continue
        if not _valid_score(score):    # out of range -> NO-SCORE
            continue
        points += float(weights[name]) * float(score)

    penalty = 0.0
    for entry in record.get("penalty_scores", []):
        score = entry.get("score_0_5")
        if _valid_score(score):        # penalties count regardless of registration
            penalty += PENALTY_MULTIPLIER * float(score)

    return max(FINAL_MIN, min(FINAL_MAX, points - penalty))
