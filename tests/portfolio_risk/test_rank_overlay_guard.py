"""C7 rank-space guard test_stub (RED first): bounded AI re-rank of the quant book.

Per the 07-06c directive + C7: the AI overlay may swap AT MOST max_swap_count
names into the quant top-K (strongest-|tilt| first, deterministic), may promote
ONLY from within the quant promotion floor (top-2K), vetoes are UNLIMITED (risk
direction) with QUANT-ORDERED backfill (a veto can never smuggle a tilt pick),
and industry caps hold throughout. No overlay == quant book identity.
"""
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from portfolio_risk.rank_book_construction import apply_rank_overlay  # noqa: E402

IND: dict[str, str] = {}  # no industry pressure in these fixtures (cap high)


def _quant(n=12):
    # A01 (best) .. A12 (worst), scores 12..1
    return pd.Series({f"A{i:02d}": float(n - i + 1) for i in range(1, n + 1)})


def test_no_overlay_returns_quant_book():
    q = _quant()
    res = apply_rank_overlay(q, pd.Series(0.0, index=q.index), k=5,
                             max_swap_count=2, promotion_floor=10,
                             industry_of=IND, max_per_industry=5)
    assert res.final == ["A01", "A02", "A03", "A04", "A05"]
    assert res.swaps_in == [] and res.swaps_out == []


def test_swap_cap_keeps_strongest_tilts_only():
    q = _quant()
    tilt = pd.Series(0.0, index=q.index)
    # three candidates below the book want in; cap allows 2
    tilt["A06"] = +0.9
    tilt["A07"] = +0.7
    tilt["A08"] = +0.5
    tilt["A05"] = -0.9   # weakest member pushed down hard
    tilt["A04"] = -0.7
    tilt["A03"] = -0.5
    res = apply_rank_overlay(q, tilt, k=5, max_swap_count=2, promotion_floor=10,
                             industry_of=IND, max_per_industry=5)
    assert res.swaps_in == ["A06", "A07"]          # A08 (weakest tilt) clamped out
    assert set(res.swaps_out) == {"A05", "A04"}    # lowest combined leave first
    assert res.clamped is True
    assert len(res.final) == 5


def test_promotion_floor_blocks_pool_bottom():
    q = _quant(30)
    tilt = pd.Series(0.0, index=q.index)
    tilt["A25"] = +5.0   # huge tilt but quant rank 25 > floor 20 -> ineligible
    res = apply_rank_overlay(q, tilt, k=5, max_swap_count=3, promotion_floor=20,
                             industry_of=IND, max_per_industry=5)
    assert "A25" not in res.final
    assert res.final == ["A01", "A02", "A03", "A04", "A05"]


def test_veto_unlimited_with_quant_ordered_backfill():
    q = _quant()
    tilt = pd.Series(0.0, index=q.index)
    tilt["A09"] = +3.0   # tries to ride in on the veto vacancy
    res = apply_rank_overlay(q, tilt, k=5, max_swap_count=0,   # NO tilt swaps allowed
                             promotion_floor=10, vetoes={"A02", "A04"},
                             industry_of=IND, max_per_industry=5)
    # vetoes removed; backfill follows QUANT order (A06, A07) — not the tilt pick
    assert res.final == ["A01", "A03", "A05", "A06", "A07"]
    assert "A09" not in res.final


def test_deterministic_repeat():
    q = _quant()
    tilt = pd.Series(0.0, index=q.index)
    tilt["A06"] = tilt["A07"] = +0.6   # tie -> code order decides, stably
    r1 = apply_rank_overlay(q, tilt, k=5, max_swap_count=1, promotion_floor=10,
                            industry_of=IND, max_per_industry=5)
    r2 = apply_rank_overlay(q, tilt, k=5, max_swap_count=1, promotion_floor=10,
                            industry_of=IND, max_per_industry=5)
    assert r1.final == r2.final and r1.swaps_in == ["A06"]
