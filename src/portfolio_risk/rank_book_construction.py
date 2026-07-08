"""Deterministic rank-space book construction (MVP, 2026-07-06c directive).

The MVP book is **top-K equal weight** from a score ranking, with deterministic
guardrails standing in for the (deferred) full risk model:

- per-industry cap (directive: <= ceil(K/3)) — hot-stock pools cluster in hot
  sectors; the raw 金股 EW book carried a −52% MDD, and concentration is the
  first thing to bound;
- an ``exclude`` (veto) set — the C15 red-flag hook for the AI leg;
- candidates-only membership — selection can never reach outside the given
  scores (the pool mask is applied upstream, Layer-2 discipline).

Selection is fully deterministic: score descending, ties broken by instrument
code; NaN scores never selected; fewer eligible than K returns fewer (no
padding, no fail-open).

NOTE (recorded): industry labels come from the CURRENT stock_basic snapshot —
acceptable for a risk guardrail (mild misclassification risk, no lookahead
alpha channel), NOT acceptable as a signal input. PIT industry (index_member_all)
is a Phase-2A ingestion item. Missing industry maps to the ``UNKNOWN`` bucket,
which is capped like any other industry (fail-closed, not fail-open).

This module lives in ``portfolio_risk`` (the C7/C14 owner for construction /
action mapping). The module remains outside all formal paths (§3 dormant-module
boundary); the MVP runner is NON-FORMAL workspace research.

Enforced by: tests/portfolio_risk/test_rank_book_construction.py.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Set
from dataclasses import dataclass, field

import pandas as pd

UNKNOWN_INDUSTRY = "UNKNOWN"


def select_top_k_equal_weight(
    scores: pd.Series,
    k: int,
    *,
    industry_of: Mapping[str, str],
    max_per_industry: int,
    exclude: Set[str] = frozenset(),
) -> list[str]:
    """Pick the top-``k`` codes by score under the deterministic guardrails.

    Args:
        scores: index = instrument codes (the candidate set — e.g. the golden
            pool at one rebalance), values = composite score (higher = better).
        k: target book size (equal weight downstream).
        industry_of: code -> industry label; missing codes fall into the
            ``UNKNOWN`` bucket (capped like a real industry).
        max_per_industry: hard cap per industry bucket (directive: ceil(K/3)).
        exclude: veto set — removed before selection (red flags / C15).

    Returns:
        Ordered list (selection order) of at most ``k`` codes. Fewer when the
        caps/candidates cannot fill ``k`` — never padded, never out-of-candidates.
    """
    if k <= 0:
        return []
    if max_per_industry <= 0:
        raise ValueError("max_per_industry must be >= 1")

    s = scores.dropna()
    if exclude:
        s = s[~s.index.isin(exclude)]
    # deterministic order: score desc, then code asc
    ordered = s.sort_index().sort_values(ascending=False, kind="stable")

    picked: list[str] = []
    per_industry: dict[str, int] = defaultdict(int)
    for code in ordered.index:
        ind = industry_of.get(code) or UNKNOWN_INDUSTRY
        if per_industry[ind] >= max_per_industry:
            continue
        picked.append(code)
        per_industry[ind] += 1
        if len(picked) == k:
            break
    return picked


@dataclass
class OverlayResult:
    """Audit record of one bounded re-rank (C7 rank-space instantiation)."""

    final: list[str]
    quant_book: list[str]
    swaps_in: list[str] = field(default_factory=list)
    swaps_out: list[str] = field(default_factory=list)
    clamped: bool = False


def apply_rank_overlay(
    quant_scores: pd.Series,
    overlay_tilt: pd.Series,
    k: int,
    *,
    max_swap_count: int,
    promotion_floor: int,
    vetoes: Set[str] = frozenset(),
    industry_of: Mapping[str, str],
    max_per_industry: int,
) -> OverlayResult:
    """Bounded AI re-rank of the quant top-K (deterministic, C7 rank-space).

    Rules (pre-registered, 2026-07-06c directive):
      - vetoes are UNLIMITED (risk direction) and backfilled in QUANT order —
        a veto can never smuggle a tilt pick into the book;
      - tilt swaps are capped at ``max_swap_count``; when more entrants are
        proposed, the strongest-|tilt| entrants win (tie -> code order) and the
        rest are clamped (``clamped=True``);
      - entrants must sit within the quant ``promotion_floor`` (rank <= floor);
      - swap-outs leave lowest-combined-score first; industry caps hold.

    ``overlay_tilt`` is the DETERMINISTIC per-name tilt already computed from
    scorecard finals by pre-registered mapping (the LLM never chooses it).
    """
    tilt = overlay_tilt.reindex(quant_scores.index).fillna(0.0)

    # pure quant reference book (the leg the AI must beat)
    quant_book = select_top_k_equal_weight(
        quant_scores, k, industry_of=industry_of, max_per_industry=max_per_industry
    )
    # veto stage: unlimited removal, QUANT-ordered backfill
    base = select_top_k_equal_weight(
        quant_scores, k, industry_of=industry_of, max_per_industry=max_per_industry,
        exclude=vetoes,
    )

    # eligibility: quant rank (1 = best; tie -> code) within the promotion floor
    order = quant_scores.dropna().sort_index().sort_values(ascending=False, kind="stable")
    qrank = pd.Series(range(1, len(order) + 1), index=order.index, dtype=float)
    eligible = set(qrank[qrank <= promotion_floor].index) - set(vetoes)

    combined = quant_scores.rank(pct=True).add(tilt, fill_value=0.0)
    proposed = select_top_k_equal_weight(
        combined[combined.index.isin(eligible)], k,
        industry_of=industry_of, max_per_industry=max_per_industry,
    )

    entrants = [c for c in proposed if c not in base]
    entrants.sort(key=lambda c: (-abs(float(tilt.get(c, 0.0))), c))
    kept = entrants[:max_swap_count]
    clamped = len(entrants) > max_swap_count

    final = list(base)
    swaps_in: list[str] = []
    swaps_out: list[str] = []
    per_ind: dict[str, int] = defaultdict(int)
    for c in final:
        per_ind[industry_of.get(c) or UNKNOWN_INDUSTRY] += 1

    for entrant in kept:
        removable = [c for c in final if c not in swaps_in]
        if not removable:
            break
        out = min(removable, key=lambda c: (float(combined.get(c, float("-inf"))), c))
        ind_in = industry_of.get(entrant) or UNKNOWN_INDUSTRY
        ind_out = industry_of.get(out) or UNKNOWN_INDUSTRY
        if ind_in != ind_out and per_ind[ind_in] >= max_per_industry:
            continue  # entrant's industry at cap -> skip (does not consume a swap)
        final.remove(out)
        per_ind[ind_out] -= 1
        final.append(entrant)
        per_ind[ind_in] += 1
        swaps_in.append(entrant)
        swaps_out.append(out)

    # stable presentation: quant-score order (code tie-break)
    final.sort(key=lambda c: (-float(quant_scores.get(c, float("-inf"))), c))
    return OverlayResult(final=final, quant_book=quant_book,
                         swaps_in=swaps_in, swaps_out=swaps_out, clamped=clamped)
