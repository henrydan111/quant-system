"""C16 · deterministic scorecard aggregation + LLM containment.

The LLM emits ONLY per-dimension 0-5 scores with evidence spans (C12 typed
records). Deterministic code computes::

    final = clamp( Σ weight[name]·score  −  Σ 2·penalty_score , 0, 100 )

(the serenity_scorecard shape). Containment rules (CONTRACTS.md C15/C16,
hardened by GPT impl-review #1 B1 and #2 Blocker-1):

- a record carrying an LLM-emitted ``final`` / ``action`` / ``decision`` /
  ``target_rank`` / ``buy`` / ``sell`` / ``tilt`` field is REJECTED outright —
  the LLM never emits the final number or an action;
- unknown top-level fields AND unknown entry fields are REJECTED (an
  unmodeled field is a smuggling channel, not noise; this also blocks an
  LLM-supplied ``_invalid_evidence`` marker — no such internal marker exists);
- ONE evidence rule for factors AND penalties (`_evidence_ok`): the entry
  counts only when ``evidence_spans`` is NON-EMPTY and every span literally
  appears (whitespace-normalized, ≤160 chars) in the visible raw-text
  ``evidence_context`` (the dossier). No spans / hallucinated span /
  out-of-range score / unregistered factor name = **NO-SCORE** (contributes 0,
  never a neutral fill). An evidence-free red flag belongs in ``risk_flags``
  (audit-only) — it can never move the final;
- penalties that DO carry grounded evidence count UNCAPPED by registration
  (the risk direction is never throttled) at the fixed 2x weight.

Weights are a pre-registered immutable artifact (part of the CandidateID /
refinery_config_version); they are inputs here, never tuned here.

Enforced by: tests/ai_layer/test_scorecard_deterministic.py ·
test_scorecard_rejects_unknown_top_level_fields.py ·
test_scorecard_evidence_spans_must_be_grounded.py.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from numbers import Number

PENALTY_MULTIPLIER = 2.0
FINAL_MIN, FINAL_MAX = 0.0, 100.0

#: LLM output fields that constitute a containment breach (C16: the LLM never
#: emits a final number or an action).
FORBIDDEN_FIELDS = ("final", "action", "decision", "target_rank", "buy", "sell", "tilt")

ALLOWED_TOP_LEVEL = frozenset(
    {"factor_scores", "penalty_scores", "risk_flags", "what_could_weaken"}
)
#: R2 Blocker-1: no internal markers accepted from the wire — evidence validity
#: is computed, never trusted from the record.
ALLOWED_ENTRY_KEYS = frozenset({"name", "score_0_5", "evidence_spans"})
_MAX_SPAN_CHARS = 160
#: R3 Major-3: a 1-2 character quote cannot carry evidentiary weight — trivial
#: substrings would ground in almost any dossier.
_MIN_SPAN_CHARS = 8
_TRIVIAL_SPANS = frozenset({"公司", "公告", "投资者", "互动易"})


class ScorecardViolation(Exception):
    """The LLM output breached C16 containment (or the record is malformed)."""


def _norm_text(s: str) -> str:
    return " ".join(str(s).split())


def _span_is_grounded(span: str, evidence_context: str) -> bool:
    """An evidence span counts ONLY if it literally appears in the raw visible
    text (impl-review B1/B1+) AND is substantive: 8-160 normalized chars, not a
    trivial generic token (R3 Major-3) — a hallucinated or near-empty span
    cannot unlock points."""
    span_n = _norm_text(span)
    if not (_MIN_SPAN_CHARS <= len(span_n) <= _MAX_SPAN_CHARS):
        return False
    if span_n in _TRIVIAL_SPANS:
        return False
    return span_n in _norm_text(evidence_context)


def _evidence_ok(entry: dict, evidence_context: str) -> bool:
    """ONE rule for factors and penalties (R2 Blocker-1): non-empty spans,
    every span grounded. ``all([])`` can never sneak an evidence-free entry in."""
    spans = entry.get("evidence_spans") or []
    return bool(spans) and all(
        isinstance(s, str) and _span_is_grounded(s, evidence_context) for s in spans
    )


#: strict-mode falsifier schema (chain_v2.x): bounded list of typed conditions
_FALSIFIER_KEYS = frozenset({"condition", "observable_in"})
_FALSIFIER_DOMAINS = frozenset({"fund", "tech", "news", "market"})
_MAX_FALSIFIERS = 5
_MAX_FALSIFIER_CHARS = 60


def validate_scorecard_record(record: dict, *, weights: Mapping[str, float],
                              require_registered_exact: bool = False,
                              falsifier_schema: bool = False) -> None:
    """Structural + containment validation (fail-closed). Evidence grounding is
    enforced in ``compute_scorecard_final`` — it is computed, never marked.

    Duplicate factor/penalty names are rejected UNCONDITIONALLY (GPT review
    Blocker-2: duplicates were summed by ``compute_scorecard_final`` — a single
    grounded x=5,w=10 entry scored 50, two identical entries scored 100, and the
    archive's name-keyed dict then hid the duplication; that is a C16 breach for
    every consumer, so the fix is not opt-in).

    Strict extras for chain_v2.x consumers (opt-in so the frozen MVP forward
    product's validation semantics are untouched):
    - ``require_registered_exact``: every registered factor appears exactly once
      (no-data dims stay present with empty evidence) and no unregistered names;
      ``score_0_5`` must be a finite number in [0, 5] (hard fail, not NO-SCORE).
    - ``falsifier_schema``: ``what_could_weaken`` is a bounded list of exactly
      ``{condition, observable_in}`` with observable_in a |-joined subset of
      {fund, tech, news, market}.
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
        seen: set[str] = set()
        for entry in record.get(key, []):
            if not isinstance(entry, dict) or "name" not in entry or "score_0_5" not in entry:
                raise ScorecardViolation(f"malformed {key} entry: {entry!r}")
            unknown = set(entry) - ALLOWED_ENTRY_KEYS
            if unknown:
                raise ScorecardViolation(f"unknown {key} entry fields: {sorted(unknown)}")
            name = entry["name"]
            # name 必须是非空字符串(复审#2 minor:NaN/非字符串名破坏无条件重名契约)
            if not isinstance(name, str) or not name.strip():
                raise ScorecardViolation(f"{key} entry name must be a non-empty string: {name!r}")
            if name in seen:
                raise ScorecardViolation(
                    f"duplicate {key} names would double-count weights (C16): {name!r}")
            seen.add(name)
            if require_registered_exact:
                s = entry["score_0_5"]
                if (not isinstance(s, Number) or isinstance(s, bool)
                        or not math.isfinite(float(s)) or not 0 <= float(s) <= 5):
                    raise ScorecardViolation(
                        f"{key} '{entry['name']}' score_0_5 not a finite number in [0,5]: {s!r}")
    if require_registered_exact:
        fnames = {e["name"] for e in record.get("factor_scores", [])}
        missing = sorted(set(weights) - fnames)
        extra = sorted(fnames - set(weights))
        if missing or extra:
            raise ScorecardViolation(
                f"registered dims must appear exactly once: missing={missing} extra={extra}")
    if falsifier_schema:
        wcw = record.get("what_could_weaken", [])
        if not isinstance(wcw, list) or len(wcw) > _MAX_FALSIFIERS:
            raise ScorecardViolation(
                f"what_could_weaken must be a list of <= {_MAX_FALSIFIERS} typed entries")
        for w in wcw:
            if not isinstance(w, dict) or set(w) != _FALSIFIER_KEYS:
                raise ScorecardViolation(f"falsifier must be exactly {{condition, observable_in}}: {w!r}")
            if (not isinstance(w["condition"], str)
                    or not 0 < len(w["condition"]) <= _MAX_FALSIFIER_CHARS):
                raise ScorecardViolation("falsifier condition must be a bounded non-empty string")
            parts = [p for p in str(w["observable_in"]).split("|") if p]
            if not parts or not all(p in _FALSIFIER_DOMAINS for p in parts):
                raise ScorecardViolation(
                    f"observable_in must be |-joined subset of {sorted(_FALSIFIER_DOMAINS)}: "
                    f"{w['observable_in']!r}")
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

    NO-SCORE = unregistered factor name / failed ``_evidence_ok`` (empty or
    ungrounded spans — applies to penalties too, R2 Blocker-1) / out-of-range
    score. Evidence-free risk observations live in ``risk_flags`` (audit-only).
    """
    validate_scorecard_record(record, weights=weights)

    points = 0.0
    for entry in record.get("factor_scores", []):
        if entry.get("name") not in weights:     # unregistered name -> no influence
            continue
        if not _evidence_ok(entry, evidence_context):
            continue                             # unsupported/hallucinated -> NO-SCORE
        score = entry.get("score_0_5")
        if not _valid_score(score):              # out of range -> NO-SCORE
            continue
        points += float(weights[entry["name"]]) * float(score)

    penalty = 0.0
    for entry in record.get("penalty_scores", []):
        if not _evidence_ok(entry, evidence_context):
            continue                             # evidence-free red flag -> audit-only
        score = entry.get("score_0_5")
        if _valid_score(score):                  # grounded penalties count, uncapped
            penalty += PENALTY_MULTIPLIER * float(score)

    return max(FINAL_MIN, min(FINAL_MAX, points - penalty))
