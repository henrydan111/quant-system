# SCRIPT_STATUS: ACTIVE — research utility (microcap timing replication, 2026-06-11)
"""Replicate the Guoren microcap index (果仁微盘指数 111001) from local raw daily data.

Official construction rules (Guoren admin, forum post p.1352062.294970440259512):
  - listing days > 60, exclude ST, KEEP suspended stocks
  - total market cap ascending, max 400 names, equal weight, DAILY rebalance
  - includes STAR market; A-shares only (no B-shares, no BSE)
  - no fees, no limit-up/down tradability constraints

Mechanics here: basket selected at T close (smallest-400 total_mv among eligible at T),
earns the equal-weight mean of constituent returns on T+1. Suspended constituents
contribute 0 while listed; names that delist drop out (mean over the rest).

Outputs index level series + stats vs the Guoren screenshot targets, and the
MA5/MA200 timing overlay with flat (out-of-market) periods.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = PROJECT_ROOT / "workspace" / "outputs" / "microcap_timing"
ST_PATH = PROJECT_ROOT / "data" / "qlib_data" / "instruments" / "st_stocks.txt"
STOCK_BASIC = PROJECT_ROOT / "data" / "reference" / "stock_basic.parquet"

N_HOLD = 400
MIN_AGE_DAYS = 60          # 上市天数大于60 (calendar days)
EVAL_START = "2014-01-02"  # Guoren chart window start
RF = 0.04                  # Guoren Sharpe risk-free (calibrated: (35.74-4)/30.89=1.03)
ANN_TRADING_DAYS = 245

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("replicate_index")


def load_panels():
    ret = pd.read_parquet(OUT_DIR / "panel_ret.parquet")
    mv = pd.read_parquet(OUT_DIR / "panel_total_mv.parquet")
    traded = pd.read_parquet(OUT_DIR / "panel_traded.parquet")
    return ret, mv, traded


def listing_window_masks(dates: pd.DatetimeIndex, codes: pd.Index):
    sb = pd.read_parquet(STOCK_BASIC)
    sb = sb.drop_duplicates(subset=["ts_code"], keep="first").set_index("ts_code")
    list_dt = pd.to_datetime(sb["list_date"], format="%Y%m%d", errors="coerce")
    delist_dt = pd.to_datetime(sb["delist_date"], format="%Y%m%d", errors="coerce")

    n = len(codes)
    larr = np.full(n, np.datetime64("NaT"), dtype="datetime64[ns]")
    darr = np.full(n, np.datetime64("NaT"), dtype="datetime64[ns]")
    for i, c in enumerate(codes):
        if c in list_dt.index:
            v = list_dt.loc[c]
            larr[i] = v if pd.notna(v) else np.datetime64("NaT")
            v = delist_dt.loc[c]
            darr[i] = v if pd.notna(v) else np.datetime64("NaT")

    dcol = dates.to_numpy()[:, None]
    listed = ~np.isnat(larr)[None, :] & (dcol >= larr[None, :])
    gone = ~np.isnat(darr)[None, :] & (dcol >= darr[None, :])
    listed &= ~gone
    age_ok = listed & (dcol > (larr + np.timedelta64(MIN_AGE_DAYS, "D"))[None, :])
    return listed, age_ok


def st_mask(dates: pd.DatetimeIndex, codes: pd.Index) -> np.ndarray:
    iv = pd.read_csv(ST_PATH, sep="\t", header=None, names=["inst", "start", "end"])
    iv["ts_code"] = iv["inst"].str.replace("_", ".", regex=False)
    iv["start"] = pd.to_datetime(iv["start"], errors="coerce")
    iv["end"] = pd.to_datetime(iv["end"], errors="coerce")
    iv = iv.dropna()
    pos = {c: i for i, c in enumerate(codes)}
    mask = np.zeros((len(dates), len(codes)), dtype=bool)
    darr = dates.to_numpy()
    for c, s, e in iv[["ts_code", "start", "end"]].itertuples(index=False):
        j = pos.get(c)
        if j is None:
            continue
        sel = (darr >= np.datetime64(s)) & (darr <= np.datetime64(e))
        if sel.any():
            mask[sel, j] = True
    return mask


def build_index() -> pd.DataFrame:
    ret, mv, traded = load_panels()
    dates, codes = ret.index, ret.columns

    keep_cols = ~(codes.str.endswith(".BJ"))  # A股 only: no BSE (B-shares absent from feed)
    ret, mv, traded = ret.loc[:, keep_cols], mv.loc[:, keep_cols], traded.loc[:, keep_cols]
    codes = ret.columns
    log.info("panel: %d days x %d codes (after .BJ drop)", len(dates), len(codes))

    listed, age_ok = listing_window_masks(dates, codes)
    st = st_mask(dates, codes)

    mv_ff = mv.ffill().to_numpy()
    mv_ff[~listed] = np.nan

    eligible = age_ok & ~st & ~np.isnan(mv_ff)

    # effective daily return: traded -> pct_chg; listed-but-suspended -> 0; else NaN
    ret_eff = ret.to_numpy(dtype="float64").copy()
    suspended = listed & (traded.to_numpy() == 0)
    ret_eff[suspended] = 0.0
    ret_eff[~listed] = np.nan

    T, N = ret_eff.shape
    basket = np.zeros((T, N), dtype=bool)
    mv_rank_input = np.where(eligible, mv_ff, np.inf)
    for t in range(T):
        k = min(N_HOLD, int(eligible[t].sum()))
        if k == 0:
            continue
        idx = np.argpartition(mv_rank_input[t], k - 1)[:k]
        basket[t, idx] = True

    # basket chosen at T earns T+1 returns
    idx_ret = np.full(T, np.nan)
    n_members = np.zeros(T, dtype=int)
    for t in range(1, T):
        members = basket[t - 1]
        r = ret_eff[t, members]
        r = r[~np.isnan(r)]
        if r.size:
            idx_ret[t] = r.mean()
            n_members[t] = r.size

    out = pd.DataFrame(
        {"ret": idx_ret, "n_members": n_members, "n_eligible": eligible.sum(axis=1)},
        index=dates,
    )
    out = out.iloc[1:]  # first day has no prior basket
    out["level"] = (1.0 + out["ret"].fillna(0)).cumprod()
    return out


def stats(levels: pd.Series, rets: pd.Series, label: str) -> dict:
    total = levels.iloc[-1] / levels.iloc[0] - 1
    n_days = (levels.index[-1] - levels.index[0]).days
    ann = (1 + total) ** (365.25 / n_days) - 1
    vol = rets.std() * np.sqrt(ANN_TRADING_DAYS)
    dd = (levels / levels.cummax() - 1).min()
    sharpe = (ann - RF) / vol if vol > 0 else np.nan
    return {
        "series": label,
        "total_return_pct": round(total * 100, 2),
        "ann_return_pct": round(ann * 100, 2),
        "ann_vol_pct": round(vol * 100, 2),
        "max_dd_pct": round(dd * 100, 2),
        "sharpe_rf4": round(sharpe, 2),
    }


def flat_periods(signal: pd.Series) -> list[tuple[str, str, int]]:
    """Contiguous runs where signal==0 -> (start, end, n_days)."""
    runs = []
    s = signal.to_numpy()
    dates = signal.index
    i = 0
    while i < len(s):
        if s[i] == 0:
            j = i
            while j + 1 < len(s) and s[j + 1] == 0:
                j += 1
            runs.append((str(dates[i].date()), str(dates[j].date()), j - i + 1))
            i = j + 1
        else:
            i += 1
    return runs


def main() -> None:
    out = build_index()
    out.to_parquet(OUT_DIR / "guoren_microcap_replica.parquet")

    ev = out.loc[EVAL_START:]
    lv = ev["level"] / ev["level"].iloc[0]

    rows = [stats(lv, ev["ret"], "replica_microcap_index (2014-01-02..end)")]

    # MA5/MA200 timing: signal at T close, position effective T+1
    full = out["level"]
    ma5 = full.rolling(5).mean()
    ma200 = full.rolling(200).mean()
    signal = (ma5 > ma200).astype(int)
    pos = signal.shift(1).fillna(0)

    timed_ret = out["ret"] * pos
    timed = pd.DataFrame({"ret": timed_ret, "pos": pos}, index=out.index).loc[EVAL_START:]
    timed["level"] = (1 + timed["ret"].fillna(0)).cumprod()
    rows.append(stats(timed["level"], timed["ret"], "replica + MA5/200 timing (no cost)"))

    res = pd.DataFrame(rows)
    res.to_csv(OUT_DIR / "replica_stats.csv", index=False)
    print("\n=== STATS (eval window 2014-01-02 .. data end) ===")
    print(res.to_string(index=False))
    print("\nGuoren targets (2014-01-02..2026-06-10): index ann 35.74 / vol 30.89 / MDD -47.83 / Sharpe 1.03")

    yearly = (1 + ev["ret"].fillna(0)).groupby(ev.index.year).prod() - 1
    print("\n=== replica yearly returns (%) ===")
    print((yearly * 100).round(1).to_string())

    fp = flat_periods(timed["pos"].astype(int))
    fp = [(s, e, n) for s, e, n in fp if n >= 3]
    print("\n=== timing flat periods (>=3 days, eval window) ===")
    for s, e, n in fp:
        print(f"  {s} .. {e}  ({n}d)")
    pd.DataFrame(fp, columns=["start", "end", "n_days"]).to_csv(
        OUT_DIR / "timing_flat_periods.csv", index=False
    )

    print("\nmember count: min %d / median %d" % (ev["n_members"].min(), ev["n_members"].median()))


if __name__ == "__main__":
    main()
