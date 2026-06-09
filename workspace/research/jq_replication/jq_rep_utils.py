"""Shared tooling for FAITHFUL JoinQuant strategy replication on the local backend.

JoinQuant strategies use variable holding counts + cash-out ("选不出票即空仓"),
which Qlib's TopkDropoutStrategy cannot model cleanly (it holds prior on empty
days). So this module provides a controlled equal-weight monthly simulator with
explicit cash and realistic turnover costs, on a qlib-derived daily-return panel.

The simulator is sanity-checked against VectorizedBacktester in sanity_check.py.
PIT note: factor gates come from the cached PIT-safe panels (factors_is/oos,
already Ref(...,1)-shifted). Realized daily returns (day-t return for a day-t
holding) carry no lookahead. Research-only (workspace/); project-relative paths ok.
"""
from __future__ import annotations
import sys
from pathlib import Path
from functools import lru_cache

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PRIOR = PROJECT_ROOT / "workspace" / "research" / "long_only_50cagr"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PRIOR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd
import research_utils as ru  # noqa: E402

CACHE = PROJECT_ROOT / "workspace" / "outputs" / "long_only_50cagr"
OUT = PROJECT_ROOT / "workspace" / "outputs" / "jq_replication"
OUT.mkdir(parents=True, exist_ok=True)
RETPANEL = OUT / "daily_ret_panel.parquet"


# ---------- board classification (qlib code form e.g. 000001_SZ) ----------
def board_of(code: str) -> str:
    c = code.split("_")[0]
    if c[:3] in ("300", "301"): return "chinext"     # 创业板
    if c[:3] in ("688", "689"): return "star"        # 科创板
    if c[0] in ("4", "8"):      return "bse"         # 北交/老三板
    if c[0] == "9" or c[:3] in ("200", "201"): return "bshare"
    if c[:3] in ("600", "601", "603", "605", "000", "001", "002", "003"):
        return "main"                                # 主板(含中小板)
    return "other"


def is_mainboard(code: str) -> bool:
    return board_of(code) == "main"


# ---------- combined PIT-safe factor panel (IS + OOS) ----------
@lru_cache(maxsize=1)
def factor_panel() -> pd.DataFrame:
    fis = pd.read_parquet(CACHE / "factors_is.parquet")
    fos = pd.read_parquet(CACHE / "factors_oos.parquet")
    # de-dup any overlap at the 2020/2021 seam
    f = pd.concat([fis, fos])
    f = f[~f.index.duplicated(keep="first")].sort_index()
    return f


# ---------- daily realized return panel (qlib-derived, cached) ----------
def build_return_panel(start="2013-12-01", end="2026-02-27") -> pd.DataFrame:
    """Adjusted close-to-close daily simple returns, wide (datetime x instrument),
    for the union of instruments in the factor panels. Cached to parquet."""
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=str(PROJECT_ROOT / "data" / "qlib_data"), region=REG_CN, kernels=1)
    insts = sorted(factor_panel().index.get_level_values(1).unique().tolist())
    print(f"[panel] computing adj-close for {len(insts)} instruments {start}..{end}", flush=True)
    df = D.features(insts, ["$close*$adj_factor"], start_time=start, end_time=end, freq="day")
    df.columns = ["adjclose"]
    # qlib MultiIndex is (instrument, datetime)
    adj = df["adjclose"].unstack(level=0)        # datetime x instrument
    adj = adj.sort_index()
    ret = adj.pct_change()
    ret.to_parquet(RETPANEL)
    print(f"[panel] saved {RETPANEL} shape={ret.shape}", flush=True)
    return ret


@lru_cache(maxsize=1)
def return_panel() -> pd.DataFrame:
    if not RETPANEL.exists():
        return build_return_panel()
    return pd.read_parquet(RETPANEL)


# ---------- equal-weight monthly simulator (explicit cash + turnover cost) ----------
def simulate_eqw_monthly(
    holdings: dict[pd.Timestamp, list[str]],
    start: str, end: str,
    *,
    cost_oneway: float = 0.0016,   # round-trip ~ buy(comm+slip) + sell(comm+tax+slip)
    max_weight: float | None = None,
) -> pd.Series:
    """Equal-weight a variable list of instruments each month; cash (0 return) when
    the list is empty. Charge turnover cost at each rebalance on the changed weight.

    holdings: {rebalance_date -> [instrument(qlib form) ...]}. Names held from their
    rebalance date until the next rebalance. cost_oneway is charged per unit of
    one-way turnover (|w_new - w_old| summed /  ... actually total traded notional).
    Returns daily net return Series indexed by trading day in [start,end].
    """
    R = return_panel()
    cal = ru.trading_calendar()
    days = cal[(cal >= pd.Timestamp(start)) & (cal <= pd.Timestamp(end))]
    rebals = pd.DatetimeIndex(sorted(holdings.keys()))
    # No-lookahead convention: holdings decided at rebalance r (from PIT factors <= r-1)
    # are TRADED at r and earn strictly from the day AFTER r. The rebalance day itself
    # still earns the PREVIOUS book. side='left' -> day==r maps to the prior rebalance.
    gov = rebals.searchsorted(days, side="left") - 1

    prev_w = pd.Series(dtype=float)
    out = pd.Series(0.0, index=days)
    for i, r in enumerate(rebals):
        block_mask = (gov == i)
        block = days[block_mask]
        names = [s for s in holdings[r] if s in R.columns]
        if names:
            w = pd.Series(1.0 / len(names), index=names)
            if max_weight is not None:
                w = w.clip(upper=max_weight)
                w = w / w.sum()
        else:
            w = pd.Series(dtype=float)   # cash
        # turnover (sum |Δw|, counts both buy and sell legs) -> cost_oneway = (buy+sell)/2
        all_names = prev_w.index.union(w.index)
        turn = float((w.reindex(all_names).fillna(0.0) - prev_w.reindex(all_names).fillna(0.0)).abs().sum())
        prev_w = w
        if len(block) == 0:
            continue
        if names:
            # BUY-AND-HOLD within the block: equal weight at block start, weights then
            # DRIFT (no daily rebalance). port NAV = mean over names of cumprod(1+r);
            # daily port return = NAV.pct_change. This avoids the daily-rebalance
            # "volatility harvesting" premium that inflates a naive mean(axis=1).
            sub = R.loc[R.index.isin(block), names].reindex(block).fillna(0.0)
            nav = (1.0 + sub).cumprod().mean(axis=1)        # EW at entry, then buy-and-hold
            port = nav.to_numpy().copy()
            port[1:] = nav.to_numpy()[1:] / nav.to_numpy()[:-1] - 1.0
            port[0] = nav.to_numpy()[0] - 1.0               # day-1 return from entry
        else:
            port = np.zeros(len(block))      # cash
        port[0] -= turn * cost_oneway        # charge turnover on the first earning day of the block
        out.loc[block] = port
    return out.rename("net")
