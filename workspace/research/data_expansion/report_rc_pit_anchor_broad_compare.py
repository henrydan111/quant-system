"""Broad-universe comparison: Tushare report_date+1 consensus E/P vs JQ PIT consensus.

Consumes the scaled JoinQuant pull (jq_consensus_pit_broad.csv from
jq_pit_anchor_broad_pull.py). Generalizes report_rc_pit_anchor_level_check.py (5 blue
chips) to the survivorship-correct as-of universe, and adds the breakdowns that close
the "only-blue-chips" objection:

  * per-date cross-sectional Spearman (does the report_date+1 ranking match PIT?)
  * size-decile Spearman (is agreement maintained for SMALL caps, not just large?)
  * later-delisted subset (do names that later delisted also agree? => the anchor's
    faithfulness is not a survivorship artifact)

Verdict logic: high cross-sectional agreement that DOES NOT decay for small caps or
delisted names => report_date+1 reconstructs the genuine PIT consensus across the broad
market => validated PIT anchor for the backfilled era.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
from data_infra.pit_backend import strictly_next_open_trade_day  # noqa: E402

RC_DIR = PROJECT_ROOT / "data" / "analyst" / "report_rc"
DAILY_DIR = PROJECT_ROOT / "data" / "market" / "daily"
TRADE_CAL = PROJECT_ROOT / "data" / "reference" / "trade_cal.parquet"
JQ_BROAD = PROJECT_ROOT / "聚宽回测明细" / "jq_consensus_pit_broad.csv"
OUT_DIR = PROJECT_ROOT / "workspace" / "outputs"
MAX_AGE_DAYS = 400


def jq_to_ts(code: str) -> str:
    if code.endswith(".XSHG"):
        return code[:-5] + ".SH"
    if code.endswith(".XSHE"):
        return code[:-5] + ".SZ"
    return code


def load_rc(years) -> pd.DataFrame:
    cols = ["ts_code", "report_date", "org_name", "author_name", "quarter", "eps"]
    rc = pd.concat([pd.read_parquet(RC_DIR / f"report_rc_{y}.parquet", columns=cols)
                    for y in years if (RC_DIR / f"report_rc_{y}.parquet").exists()], ignore_index=True)
    rc["report_date"] = pd.to_datetime(rc["report_date"], format="%Y%m%d", errors="coerce")
    rc["eps"] = pd.to_numeric(rc["eps"], errors="coerce")
    rc = rc.dropna(subset=["report_date"])
    cal = pd.read_parquet(TRADE_CAL)
    open_cal = pd.DatetimeIndex(
        pd.to_datetime(cal.loc[cal["is_open"] == 1, "cal_date"], format="%Y%m%d")).sort_values()
    rc["effective_date"] = strictly_next_open_trade_day(rc["report_date"], open_cal)
    rc["org_author"] = rc["org_name"].astype(str) + "|" + rc["author_name"].astype(str)
    return rc.sort_values("report_date").reset_index(drop=True)


def daily_close_mv(asof: pd.Timestamp) -> pd.DataFrame:
    f = DAILY_DIR / str(asof.year) / f"daily_{asof.strftime('%Y%m%d')}.parquet"
    if not f.exists():
        return pd.DataFrame()
    return pd.read_parquet(f, columns=["ts_code", "close", "total_mv"])


def consensus_ep_at(rc: pd.DataFrame, asof: pd.Timestamp, px: pd.DataFrame) -> pd.DataFrame:
    """Per-stock consensus FY1 E/P (report_date+1 anchor) at asof, for whole market."""
    fy1 = f"{asof.year}Q4"
    lo = asof - pd.Timedelta(days=MAX_AGE_DAYS)
    vis = rc[(rc["effective_date"] <= asof) & (rc["report_date"] >= lo)
             & (rc["quarter"].astype(str) == fy1)].dropna(subset=["eps"])
    if vis.empty:
        return pd.DataFrame()
    latest = vis.drop_duplicates(subset=["ts_code", "org_author"], keep="last")
    cons = latest.groupby("ts_code")["eps"].mean().rename("cons_eps").reset_index()
    m = cons.merge(px, on="ts_code", how="inner")
    m = m[m["close"] > 0]
    m["ts_ep"] = m["cons_eps"] / m["close"]
    m["asof"] = asof
    return m[["asof", "ts_code", "ts_ep", "total_mv"]]


def live_codes_recent() -> set:
    """ts_codes present in the most recent available daily files => still listed."""
    live = set()
    for y in (2026, 2025):
        yr = DAILY_DIR / str(y)
        if yr.is_dir():
            files = sorted(yr.glob("daily_*.parquet"))
            if files:
                live |= set(pd.read_parquet(files[-1], columns=["ts_code"])["ts_code"])
    return live


def main():
    if not JQ_BROAD.exists():
        print(f"!! {JQ_BROAD} not found.\n"
              f"   Run the JoinQuant notebook jq_pit_anchor_broad_pull.py first and download the CSV here.")
        return
    jq = pd.read_csv(JQ_BROAD)
    jq = jq[jq["factor"] == "predicted_earnings_to_price_ratio"].copy()
    jq["ts_code"] = jq["code"].map(jq_to_ts)
    jq["asof"] = pd.to_datetime(jq["asof"])
    jq = jq.rename(columns={"value": "jq_ep"})[["asof", "ts_code", "jq_ep"]].dropna()

    years = range(2012, 2022)
    rc = load_rc(years)
    cal = pd.read_parquet(TRADE_CAL)
    open_days = pd.DatetimeIndex(
        pd.to_datetime(cal.loc[cal["is_open"] == 1, "cal_date"], format="%Y%m%d")).sort_values()
    live = live_codes_recent()

    rows = []
    for asof in sorted(jq["asof"].unique()):
        asof = pd.Timestamp(asof)
        tday = open_days[open_days >= asof]
        if len(tday) == 0:
            continue
        tday = tday[0]
        px = daily_close_mv(tday)
        if px.empty:
            continue
        ts_ep = consensus_ep_at(rc, tday, px)
        if ts_ep.empty:
            continue
        ts_ep["asof"] = asof
        rows.append(ts_ep)
    ts_all = pd.concat(rows, ignore_index=True)

    merged = jq.merge(ts_all, on=["asof", "ts_code"], how="inner").dropna(subset=["jq_ep", "ts_ep"])
    merged["delisted"] = ~merged["ts_code"].isin(live)
    print(f"JQ broad rows: {len(jq)}   matched (both sides): {len(merged)}   "
          f"dates: {merged['asof'].nunique()}   stocks: {merged['ts_code'].nunique()}")
    print(f"later-delisted names in matched set: {merged['delisted'].sum()} "
          f"({merged.groupby('ts_code')['delisted'].first().mean()*100:.0f}% of distinct codes)")

    # per-date cross-sectional Spearman
    perdate = merged.groupby("asof").apply(
        lambda g: pd.Series({"n": len(g),
                             "spearman": g["jq_ep"].corr(g["ts_ep"], method="spearman"),
                             "ratio_med": (g["ts_ep"] / g["jq_ep"]).median()}))
    print("\n=== per-date cross-sectional agreement (report_date+1 vs JQ PIT) ===")
    print(perdate.round(3).to_string())
    print(f"\nmean per-date Spearman = {perdate['spearman'].mean():+.3f}")

    # pooled
    print(f"\npooled Pearson  = {merged['jq_ep'].corr(merged['ts_ep']):+.3f}")
    print(f"pooled Spearman = {merged['jq_ep'].corr(merged['ts_ep'], method='spearman'):+.3f}")

    # size-decile breakdown (is agreement maintained for small caps?)
    def _decile(s):
        if s.notna().sum() < 10:
            return pd.Series(np.nan, index=s.index)
        return pd.qcut(s.rank(method="first"), 10, labels=False) + 1
    merged["size_decile"] = merged.groupby("asof")["total_mv"].transform(_decile)
    dec = merged.dropna(subset=["size_decile"]).groupby("size_decile").apply(
        lambda g: pd.Series({"n": len(g), "spearman": g["jq_ep"].corr(g["ts_ep"], method="spearman")}))
    print("\n=== Spearman by size decile (1=small .. 10=large) — does it hold for small caps? ===")
    print(dec.round(3).to_string())

    # delisted subset (survivorship in the anchor's faithfulness)
    if merged["delisted"].any():
        d = merged[merged["delisted"]]
        print(f"\n=== later-delisted subset (n={len(d)}) ===")
        print(f"pooled Spearman (delisted only) = {d['jq_ep'].corr(d['ts_ep'], method='spearman'):+.3f}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    merged.to_csv(OUT_DIR / "report_rc_pit_anchor_broad.csv", index=False)
    print(f"\nwrote {OUT_DIR / 'report_rc_pit_anchor_broad.csv'}")


if __name__ == "__main__":
    main()
