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
