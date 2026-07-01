"""Deep-history (pre-2022) PIT buffer sweep for report_rc — from EXISTING data only.

Question (user, 2026-06-14): can we establish the report_rc ingestion-lag buffer for the
PRE-2022-05 deep history WITHOUT live forward measurement? create_time is the real per-row
ingestion stamp only for 2022-05+ (frozen at the 2022-05 backfill before that). So for the deep
history we validate the buffer against the JoinQuant 朝阳永续 consensus, which DID hold the data
contemporaneously (genuinely PIT) — the same oracle the level anchor was validated against.

This generalizes report_rc_pit_anchor_broad_compare.py (which fixed the anchor at report_date+1)
to sweep report_date + {1,2,3} trading-day buffers and report, per buffer, the cross-sectional
agreement with the JQ PIT consensus (per-date Spearman + median ratio + pooled). Reading:
  * agreement high & stable across buffers, ratio≈1  => the anchor reconstructs the PIT consensus
    and the choice of buffer in this range is robust;
  * a SMALLER buffer that 'leads' JQ (ratio systematically >1 / higher agreement with the NEXT
    JQ date) would signal lookahead — i.e. Tushare seeing reports JQ couldn't yet.
Combine with the 2022-05+ create_time-measured lag (p50=1, p99=2, max≈4 calendar days) to pick the
minimal defensible deep-history buffer. NO Tushare pull — Tushare raw on disk + JQ CSV only.

Run: venv/Scripts/python.exe workspace/research/data_expansion/report_rc_pit_buffer_sweep.py
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RC_DIR = PROJECT_ROOT / "data" / "analyst" / "report_rc"
DAILY_DIR = PROJECT_ROOT / "data" / "market" / "daily"
TRADE_CAL = PROJECT_ROOT / "data" / "reference" / "trade_cal.parquet"
JQ_BROAD = PROJECT_ROOT / "聚宽回测明细" / "jq_consensus_pit_broad.csv"
OUT_DIR = PROJECT_ROOT / "workspace" / "outputs"
MAX_AGE_DAYS = 400
BUFFERS = [1, 2, 3]          # report_date + k trading days


def jq_to_ts(code: str) -> str:
    if code.endswith(".XSHG"):
        return code[:-5] + ".SH"
    if code.endswith(".XSHE"):
        return code[:-5] + ".SZ"
    return code


def load_rc(years, open_cal: pd.DatetimeIndex) -> pd.DataFrame:
    cols = ["ts_code", "report_date", "org_name", "author_name", "quarter", "eps"]
    rc = pd.concat([pd.read_parquet(RC_DIR / f"report_rc_{y}.parquet", columns=cols)
                    for y in years if (RC_DIR / f"report_rc_{y}.parquet").exists()], ignore_index=True)
    rc["report_date"] = pd.to_datetime(rc["report_date"], format="%Y%m%d", errors="coerce")
    rc["eps"] = pd.to_numeric(rc["eps"], errors="coerce")
    rc = rc.dropna(subset=["report_date"])
    rc["org_author"] = rc["org_name"].astype(str) + "|" + rc["author_name"].astype(str)
    # base position = first open day STRICTLY after report_date (= the +1 trading-day anchor)
    base = np.searchsorted(open_cal.values, rc["report_date"].values, side="right")
    for k in BUFFERS:
        idx = np.clip(base + (k - 1), 0, len(open_cal) - 1)
        rc[f"eff_{k}"] = open_cal.values[idx]
    return rc.sort_values("report_date").reset_index(drop=True)


def daily_close_mv(asof: pd.Timestamp) -> pd.DataFrame:
    f = DAILY_DIR / str(asof.year) / f"daily_{asof.strftime('%Y%m%d')}.parquet"
    if not f.exists():
        return pd.DataFrame()
    return pd.read_parquet(f, columns=["ts_code", "close", "total_mv"])


def consensus_ep_at(rc: pd.DataFrame, asof: pd.Timestamp, px: pd.DataFrame, eff_col: str) -> pd.DataFrame:
    fy1 = f"{asof.year}Q4"
    lo = asof - pd.Timedelta(days=MAX_AGE_DAYS)
    vis = rc[(rc[eff_col] <= asof) & (rc["report_date"] >= lo)
             & (rc["quarter"].astype(str) == fy1)].dropna(subset=["eps"])
    if vis.empty:
        return pd.DataFrame()
    latest = vis.drop_duplicates(subset=["ts_code", "org_author"], keep="last")
    cons = latest.groupby("ts_code")["eps"].mean().rename("cons_eps").reset_index()
    m = cons.merge(px, on="ts_code", how="inner")
    m = m[m["close"] > 0]
    m["ts_ep"] = m["cons_eps"] / m["close"]
    return m[["ts_code", "ts_ep"]]


def main():
    if not JQ_BROAD.exists():
        print(f"!! {JQ_BROAD} not found."); return
    jq = pd.read_csv(JQ_BROAD)
    jq = jq[jq["factor"] == "predicted_earnings_to_price_ratio"].copy()
    jq["ts_code"] = jq["code"].map(jq_to_ts)
    jq["asof"] = pd.to_datetime(jq["asof"])
    jq = jq.rename(columns={"value": "jq_ep"})[["asof", "ts_code", "jq_ep"]].dropna()

    cal = pd.read_parquet(TRADE_CAL)
    open_days = pd.DatetimeIndex(
        pd.to_datetime(cal.loc[cal["is_open"] == 1, "cal_date"], format="%Y%m%d")).sort_values()
    rc = load_rc(range(2012, 2022), open_days)

    # one merged frame per buffer
    per_buf = {k: [] for k in BUFFERS}
    asofs = sorted(jq["asof"].unique())
    for asof in asofs:
        asof = pd.Timestamp(asof)
        tday = open_days[open_days >= asof]
        if len(tday) == 0:
            continue
        tday = tday[0]
        px = daily_close_mv(tday)         # loaded ONCE, reused across buffers
        if px.empty:
            continue
        jq_d = jq[jq["asof"] == asof][["ts_code", "jq_ep"]]
        for k in BUFFERS:
            ts_ep = consensus_ep_at(rc, tday, px, f"eff_{k}")
            if ts_ep.empty:
                continue
            mg = jq_d.merge(ts_ep, on="ts_code", how="inner").dropna()
            if len(mg) >= 10:
                per_buf[k].append((asof, mg))

    print(f"JQ deep-history as-of dates: {len(asofs)}  (window {asofs[0]} .. {asofs[-1]})")
    print("\n=== report_date + k trading-day buffer vs JQ PIT consensus (pre-2022 deep history) ===")
    print(f"{'buffer':>8} {'dates':>6} {'pooled_n':>9} {'mean_perdate_spearman':>22} {'pooled_spearman':>16} {'median_ratio(ts/jq)':>20}")
    summary = {}
    for k in BUFFERS:
        if not per_buf[k]:
            print(f"  +{k} td   (no data)"); continue
        sp = [g["jq_ep"].corr(g["ts_ep"], method="spearman") for _, g in per_buf[k]]
        allg = pd.concat([g for _, g in per_buf[k]], ignore_index=True)
        ratio = (allg["ts_ep"] / allg["jq_ep"]).replace([np.inf, -np.inf], np.nan).median()
        pooled = allg["jq_ep"].corr(allg["ts_ep"], method="spearman")
        summary[k] = (np.nanmean(sp), pooled, ratio)
        print(f"  +{k:>2} td  {len(per_buf[k]):>6} {len(allg):>9} {np.nanmean(sp):>22.3f} {pooled:>16.3f} {ratio:>20.3f}")
    print("\nInterpretation: high & stable agreement with ratio≈1 across buffers => the anchor "
          "reconstructs the genuine PIT consensus on the deep history and the buffer is robust; the "
          "minimal safe buffer is the smallest k that keeps agreement without a >1 'leading' ratio. "
          "Cross-check with the 2022-05+ create_time lag (p99=2 cal days) → a +2 td deep-history buffer "
          "comfortably covers it. NOTE: JQ is consensus-LEVEL — this validates arrival/level visibility, "
          "NOT per-report breadth (restatement-cleanliness remains the separate residual).")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"buffer_td": k, "mean_perdate_spearman": v[0], "pooled_spearman": v[1],
                   "median_ratio_ts_over_jq": v[2]} for k, v in summary.items()]).to_csv(
        OUT_DIR / "report_rc_pit_buffer_sweep.csv", index=False)
    print(f"\nwrote {OUT_DIR / 'report_rc_pit_buffer_sweep.csv'}")


if __name__ == "__main__":
    main()
