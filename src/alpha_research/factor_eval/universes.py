"""Multi-universe evaluation framework: named universe specs + daily boolean masks.

Layer-2 of the four-layer pipeline (§8.1): factors are computed on the FULL market
first; these masks then scope ranking/grouping. Membership is a mask, never a row
drop, and tradability is NOT encoded here beyond the CICC pool-exclusion screens.

Universe composition = base population − standard exclusion screens (CICC 股票池口径):

    base        one of: all listed A-shares / index constituents (as-of monthly
                snapshots) / board prefixes (创业板+科创板) / monthly mcap-rank
                (microcap) / monthly liquidity-rank (deployable liquid pool)
    screens     ST或*ST · 停牌 (vol==0 or NaN close proxy) · 一字板 (high==low, at
                limit when limit columns provided) · 上市未满一年 (365 calendar days)

Reference-data masks (index snapshots / ST ranges / listing ages) come from
``data_infra.universe_membership``; this module adds the price-panel-dependent
screens and the named registry. The price panel is INJECTED by the caller (loaded
through the sanctioned research doors) — this module performs no data access itself.

Mask shape convention: ``DataFrame(bool, index=dates, columns=instruments)``,
instruments in Qlib upper form (``000001_SZ``).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.data_infra import universe_membership as um

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Specs
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class UniverseSpec:
    """A named, reproducible universe definition.

    ``base`` grammar: ``all`` | ``index:<index_code>`` | ``board:<prefix,...>`` |
    ``mcap_bottom:<N>`` | ``adv_top:<N>``. Rank-based bases refresh on the last
    trading day of each month among the screened population and carry forward
    daily until the next refresh.
    """

    universe_id: str
    label: str
    base: str
    start_date: str | None = None  # evaluation must not start before this
    description: str = ""
    apply_screens: bool = True  # CICC exclusion screens on top of base


UNIVERSE_SPECS: dict[str, UniverseSpec] = {
    spec.universe_id: spec
    for spec in (
        UniverseSpec(
            "univ_all", "全市场", "all",
            description="All listed A-shares minus the CICC exclusion screens. CICC 全市场 domain.",
        ),
        UniverseSpec(
            "univ_csi300", "沪深300", "index:000300.SH",
            description="CSI300 constituents (monthly as-of snapshots). 大盘 domain.",
        ),
        UniverseSpec(
            "univ_csi500", "中证500", "index:000905.SH",
            description="CSI500 constituents. 中盘 domain.",
        ),
        UniverseSpec(
            "univ_csi1000", "中证1000", "index:000852.SH", start_date="2014-11-01",
            description="CSI1000 constituents; index data begins 2014-10 (CICC tests it from 2014-11-01).",
        ),
        UniverseSpec(
            "univ_microcap", "微盘", "mcap_bottom:400",
            description="Smallest 400 by total market cap among the screened population, "
                        "refreshed monthly (万得微盘股指数口径的近似). 微盘 domain.",
        ),
        UniverseSpec(
            "univ_growth", "成长板块", "board:300,301,688",
            start_date="2010-06-01",
            description="创业板 (300/301) + 科创板 (688) by code prefix; ChiNext opened 2009-10, "
                        "first names clear the 1-year age screen from late 2010. 成长 domain.",
        ),
        UniverseSpec(
            "univ_liquid_top300", "流动性前300", "adv_top:300",
            description="Top 300 by 20-day mean turnover (amount), refreshed monthly. "
                        "The deployable-liquidity domain used by deployment gates. "
                        "NOTE: panel['amount'] must include >=20 days of warmup history "
                        "before the evaluation window (ADV is fail-closed False during warmup).",
        ),
    )
}


# ---------------------------------------------------------------------------
# Panel-dependent screens
# ---------------------------------------------------------------------------

def suspended_mask(panel: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """True where the stock cannot trade that day: ``vol`` is 0/NaN or close is NaN.

    Mirrors the engine's suspension proxy (§3.3): a suspended-but-listed name has a
    NaN-OHLCV row; ``vol == 0`` covers exchange-recorded zero-volume halts.
    """
    vol = panel["vol"]
    out = vol.isna() | (vol == 0)
    if "close" in panel:
        out = out | panel["close"].isna()
    return out


def one_word_limit_mask(panel: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """True on 一字板 days: no intraday range (high==low) pinned at a price limit.

    With ``up_limit``/``down_limit`` in the panel (the Tushare published fields —
    preferred, they carry fen-rounding and special-band rules), a flat day must sit
    at a limit to count. Without them, any flat traded day counts (conservative).
    Suspended days are excluded here (they are flat with NaN/0 volume and belong to
    :func:`suspended_mask`).
    """
    high, low = panel["high"], panel["low"]
    flat = (high == low) & high.notna()
    traded = ~suspended_mask(panel)
    flat = flat & traded
    if "up_limit" in panel and "down_limit" in panel:
        ref = panel["close"] if "close" in panel else high
        at_limit = pd.DataFrame(False, index=flat.index, columns=flat.columns)
        up, down = panel["up_limit"], panel["down_limit"]
        tol = 1e-4
        at_limit |= (ref - up).abs() <= tol
        at_limit |= (ref - down).abs() <= tol
        flat = flat & at_limit
    return flat


def cicc_exclusion_mask(
    dates: pd.DatetimeIndex,
    instruments: list[str],
    panel: dict[str, pd.DataFrame],
    *,
    reference: dict[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    """The combined CICC pool-exclusion screen: True = excluded that day.

    Screens: ST/*ST, 停牌, 一字板, 上市未满一年 (and not-listed-at-all).
    ``reference`` may inject precomputed {"st", "young", "listed"} masks (tests /
    batch reuse); otherwise they are loaded from the reference datasets.
    """
    if reference is None:
        listing = um.listing_status_masks(dates, instruments)
        reference = {
            "st": um.st_mask(dates, instruments),
            "young": listing["young"],
            "listed": listing["listed"],
        }
    excluded = ~reference["listed"]
    excluded |= reference["st"]
    excluded |= reference["young"]
    excluded |= suspended_mask(panel).reindex(index=dates, columns=instruments, fill_value=True)
    excluded |= one_word_limit_mask(panel).reindex(index=dates, columns=instruments, fill_value=False)
    return excluded


# ---------------------------------------------------------------------------
# Rank-refresh bases (microcap / liquid)
# ---------------------------------------------------------------------------

def month_end_refresh_dates(dates: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Last trading date of each month present in ``dates``."""
    s = pd.Series(dates, index=dates)
    return pd.DatetimeIndex(s.groupby([dates.year, dates.month]).max().to_numpy())


def monthly_rank_base(
    score: pd.DataFrame,
    n: int,
    side: str,
    eligible: pd.DataFrame,
    dates: pd.DatetimeIndex,
) -> pd.DataFrame:
    """Select ``n`` names by ``score`` rank among ``eligible`` at each month-end,
    carry the selection forward daily until the next refresh.

    ``side``: ``"top"`` (largest score) or ``"bottom"`` (smallest). Refresh dates
    with fewer than ``n`` eligible names select all of them (logged).
    """
    if side not in ("top", "bottom"):
        raise ValueError(f"side must be 'top'|'bottom', got {side!r}")
    refresh = month_end_refresh_dates(dates)
    mask = pd.DataFrame(False, index=dates, columns=score.columns)
    current: pd.Index | None = None
    short_months = 0
    refresh_set = set(refresh)
    for dt in dates:
        if dt in refresh_set or current is None:
            row = score.loc[dt].where(eligible.loc[dt])
            row = row.dropna()
            if len(row) < n:
                short_months += 1
                current = row.index
            else:
                ranked = row.sort_values(ascending=(side == "bottom"))
                current = ranked.index[:n]
        mask.loc[dt, current] = True
    if short_months:
        logger.warning("monthly_rank_base: %d refresh dates had fewer than %d eligible names",
                       short_months, n)
    return mask


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def _board_base(instruments: list[str], prefixes: list[str],
                dates: pd.DatetimeIndex) -> pd.DataFrame:
    cols = np.array([any(inst.split("_")[0].startswith(p) for p in prefixes)
                     for inst in instruments])
    values = np.broadcast_to(cols, (len(dates), len(instruments))).copy()
    return pd.DataFrame(values, index=dates, columns=instruments)


def build_universe_mask(
    universe_id: str,
    dates: pd.DatetimeIndex,
    instruments: list[str],
    panel: dict[str, pd.DataFrame],
    *,
    reference: dict[str, pd.DataFrame] | None = None,
    index_snapshots: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build the daily boolean mask for a named universe.

    ``panel`` must provide wide frames keyed ``vol``/``high``/``low`` (``close``,
    ``up_limit``, ``down_limit`` recommended; ``total_mv`` required for
    ``mcap_bottom``; ``amount`` for ``adv_top``), all indexed like (dates,
    instruments). Returns the mask; dates before ``spec.start_date`` are forced
    all-False.
    """
    spec = UNIVERSE_SPECS.get(universe_id)
    if spec is None:
        raise KeyError(f"unknown universe_id {universe_id!r}; known: {sorted(UNIVERSE_SPECS)}")

    if reference is None:
        listing = um.listing_status_masks(dates, instruments)
        reference = {
            "st": um.st_mask(dates, instruments),
            "young": listing["young"],
            "listed": listing["listed"],
        }
    excluded = cicc_exclusion_mask(dates, instruments, panel, reference=reference)
    eligible = ~excluded

    kind, _, arg = spec.base.partition(":")
    if kind == "all":
        base = reference["listed"].copy()
    elif kind == "index":
        base = um.index_membership_mask(arg, dates, instruments, snapshots=index_snapshots)
    elif kind == "board":
        base = _board_base(instruments, arg.split(","), dates)
    elif kind == "mcap_bottom":
        if "total_mv" not in panel:
            raise KeyError(f"{universe_id} needs panel['total_mv']")
        base = monthly_rank_base(panel["total_mv"], int(arg), "bottom", eligible, dates)
    elif kind == "adv_top":
        if "amount" not in panel:
            raise KeyError(f"{universe_id} needs panel['amount']")
        adv20 = panel["amount"].rolling(20, min_periods=10).mean()
        base = monthly_rank_base(adv20, int(arg), "top", eligible, dates)
    else:
        raise ValueError(f"unknown base kind {kind!r} in spec {universe_id}")

    mask = base & eligible if spec.apply_screens else base

    if spec.start_date is not None:
        mask.loc[mask.index < pd.Timestamp(spec.start_date)] = False
    return mask
