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

#: impl-review B1: unknown top-level / entry fields HARD-FAIL (ignore-not-reject
#: was ruled insufficient containment).
ALLOWED_TOP_LEVEL = frozenset(
    {"factor_scores", "penalty_scores", "risk_flags", "what_could_weaken"}
)
ALLOWED_ENTRY_KEYS = frozenset({"name", "score_0_5", "evidence_spans", "_invalid_evidence"})
_MAX_SPAN_CHARS = 160


class ScorecardViolation(Exception):
    """The LLM output breached C16 containment (or the record is malformed)."""


def _norm_text(s: str) -> str:
    return " ".join(str(s).split())


def _span_is_grounded(span: str, evidence_context: str) -> bool:
    """impl-review B1: an evidence span counts ONLY if it literally appears in
    the visible dossier/spans context — a hallucinated span cannot unlock points."""
    span_n = _norm_text(span)
    return 0 < len(span_n) <= _MAX_SPAN_CHARS and span_n in _norm_text(evidence_context)


def validate_scorecard_record(
    record: dict,
    *,
    weights: Mapping[str, float],
    evidence_context: str,
) -> None:
    """Structural + containment + evidence-grounding validation (fail-closed).

    Marks entries whose non-empty evidence is NOT grounded in
    ``evidence_context`` with ``_invalid_evidence`` -> NO-SCORE downstream
    (applies to factor scores AND penalties). Raises on any unknown field.
    """
    if not isinstance(record, dict):
        raise ScorecardViolation("scorecard record must be a dict")
    unknown_top = set(record) - ALLOWED_TOP_LEVEL
    if unknown_top:
        # forbidden names get the specific message; any other unknown fails too
        for field in FORBIDDEN_FIELDS:
            if field in unknown_top:
                raise ScorecardViolation(
                    f"LLM-emitted '{field}' breaches C16 containment — the LLM emits "
                    f"dimension scores + evidence ONLY; deterministic code computes the final"
                )
        raise ScorecardViolation(
            f"unknown top-level fields breach C12/C16 containment: {sorted(unknown_top)}"
        )
    for key in ("factor_scores", "penalty_scores"):
        if key in record and not isinstance(record[key], list):
            raise ScorecardViolation(f"'{key}' must be a list of typed entries")
    for key in ("factor_scores", "penalty_scores"):
        for entry in record.get(key, []):
            if not isinstance(entry, dict) or "name" not in entry or "score_0_5" not in entry:
                raise ScorecardViolation(f"malformed {key} entry: {entry!r}")
            unknown = set(entry) - ALLOWED_ENTRY_KEYS
            if unknown:
                raise ScorecardViolation(f"unknown {key} entry fields: {sorted(unknown)}")
            spans = entry.get("evidence_spans") or []
            if not all(isinstance(s, str) and _span_is_grounded(s, evidence_context)
                       for s in spans):
                entry["_invalid_evidence"] = True
    if not weights:
        raise ScorecardViolation("pre-registered weights must be non-empty")


def _valid_score(value) -> bool:
    return isinstance(value, Number) and 0 <= float(value) <= 5


def compute_scorecard_final(
    record: dict,
    *,
    weights: Mapping[str, float],
    evidence_context: str,
) -> float:
    """Deterministic final. NO-SCORE entries contribute 0 (never neutral-positive).

    NO-SCORE = unregistered name / empty evidence / out-of-range / UNGROUNDED
    evidence (``_invalid_evidence``, impl-review B1 — applies to penalties too).
    """
    validate_scorecard_record(record, weights=weights, evidence_context=evidence_context)

    points = 0.0
    for entry in record.get("factor_scores", []):
        name = entry.get("name")
        score = entry.get("score_0_5")
        evidence = entry.get("evidence_spans") or []
        if name not in weights:              # unregistered name -> no influence (C16b)
            continue
        if not evidence:                     # unsupported -> NO-SCORE
            continue
        if entry.get("_invalid_evidence"):   # hallucinated span -> NO-SCORE (B1)
            continue
        if not _valid_score(score):          # out of range -> NO-SCORE
            continue
        points += float(weights[name]) * float(score)

    penalty = 0.0
    for entry in record.get("penalty_scores", []):
        score = entry.get("score_0_5")
        if entry.get("_invalid_evidence"):   # ungrounded penalty evidence -> NO-SCORE
            continue
        if _valid_score(score):              # penalties count regardless of registration
            penalty += PENALTY_MULTIPLIER * float(score)

    return max(FINAL_MIN, min(FINAL_MAX, points - penalty))
