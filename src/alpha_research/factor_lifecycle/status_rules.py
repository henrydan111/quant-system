"""Status-assignment rules for factor-lifecycle revalidation (Phase 4).

SPLIT (design-review must-fix #3) into two rule paths that must never be confused:

  * ``assign_historical_status`` — the EXISTING oos-based rule, ported verbatim from the
    legacy ``revalidate_*.py`` scripts. It is for ``historical_investigation`` PARITY
    only (it consumes ``oos_icir``) and is NOT a formal gate.
  * ``assign_candidate_status`` — the FORMAL ``draft -> candidate`` rule. IS-ONLY: it
    consumes an IS-internal heldout ICIR + sign-consistency and NEVER an ``oos_*`` field
    (the formal walk-forward structurally has no OOS). It only ever returns ``candidate``
    or ``draft`` (deprecation is a historical / failed-factor concern, not an IS-gate
    outcome). Fail-closed: missing evidence / field-ineligible -> stays ``draft``.

Long-only viability is Phase-2 METADATA and is NOT an input to either lifecycle rule
(per design review: viability stays metadata, not lifecycle status).
"""

from __future__ import annotations

import pandas as pd

# ── Historical (legacy, oos-based) thresholds — frozen, ported verbatim ────────────────
HIST_OOS_COLLAPSE = 0.03
HIST_SIGN_FLIP_IS = 0.20
HIST_OOS_MIN = 0.10
HIST_SIGN_CONSISTENCY_MIN = 0.70

# ── Formal candidate (IS-only) thresholds ──────────────────────────────────────────────
CAND_HELDOUT_ICIR_MIN = 0.10
CAND_SIGN_CONSISTENCY_MIN = 0.70


def assign_historical_status(field_ok, is_icir, oos_icir, sign_consistency) -> tuple[str, str]:
    """Legacy oos-based status rule (``historical_investigation`` parity; NOT a formal
    gate). Ported verbatim from ``revalidate_catalog_walkforward.assign_status`` /
    ``revalidate_derived_factors.assign_status``."""
    if not field_ok:
        return "draft", "field-ineligible (quarantine/pending/unknown field) -- capped at draft"
    if pd.isna(oos_icir) or pd.isna(is_icir):
        return "draft", "insufficient IS or OOS data"
    if abs(oos_icir) < HIST_OOS_COLLAPSE:
        return "deprecated", f"collapsed OOS (|OOS ICIR|={abs(oos_icir):.3f} < {HIST_OOS_COLLAPSE})"
    if is_icir * oos_icir < 0 and abs(is_icir) >= HIST_SIGN_FLIP_IS:
        return "deprecated", f"IS/OOS sign FLIP (IS={is_icir:+.3f}, OOS={oos_icir:+.3f})"
    if (is_icir * oos_icir > 0) and abs(oos_icir) >= HIST_OOS_MIN and sign_consistency >= HIST_SIGN_CONSISTENCY_MIN:
        return "candidate", (
            f"walk-forward stable (OOS ICIR={oos_icir:+.3f}, sign-consistency={sign_consistency:.2f})"
        )
    return "draft", f"marginal (OOS ICIR={oos_icir:+.3f}, sign-consistency={sign_consistency:.2f})"


def assign_candidate_status(
    field_ok,
    heldout_rank_icir,
    sign_consistency,
    *,
    evidence_kind: str = "generated_heldout",
) -> tuple[str, str]:
    """FORMAL ``draft -> candidate`` rule — IS-ONLY. Consumes the IS-internal heldout
    rank ICIR + sign-consistency; NEVER an ``oos_*`` field. Returns ``candidate`` or
    ``draft`` only. Fail-closed: missing evidence / field-ineligible -> ``draft``."""
    if not field_ok:
        return "draft", "field-ineligible -- capped at draft"
    if pd.isna(heldout_rank_icir) or pd.isna(sign_consistency):
        return "draft", f"insufficient IS heldout evidence ({evidence_kind})"
    if abs(heldout_rank_icir) >= CAND_HELDOUT_ICIR_MIN and sign_consistency >= CAND_SIGN_CONSISTENCY_MIN:
        return "candidate", (
            f"IS-heldout stable ({evidence_kind}: heldout ICIR={heldout_rank_icir:+.3f}, "
            f"sign-consistency={sign_consistency:.2f})"
        )
    return "draft", (
        f"marginal IS-heldout ({evidence_kind}: heldout ICIR={heldout_rank_icir:+.3f}, "
        f"sign-consistency={sign_consistency:.2f})"
    )
