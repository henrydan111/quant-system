"""report_rc `report_date+1` PIT-anchor validation against JoinQuant genuine-PIT consensus.

Question (user, 2026-06-08): the prior session ruled report_rc pre-2022-05 UNUSABLE
because `create_time` is a May-2022 bulk-backfill stamp. But `create_time` only tells
us when Tushare *ingested* the row, not whether `report_date` (the analyst publication
date) is faithful. If `report_date` is faithful, then anchoring visibility at
`report_date + 1` (= strictly_next_open_trade_day) would be PIT-correct even for the
backfilled deep history. CAN WE PROVE report_date+1 is PIT?

Oracle: JoinQuant's 朝阳永续 consensus is GENUINELY point-in-time (prior Test A: the
forecast-vs-realized error shows real cyclical regime sign-flips that a hindsight-fill
cannot manufacture). `jq_consensus_pit_test.csv` holds JQ's PIT
`pred_over_actual_minus1` for 15 large caps x fy 2013-2019, measured as-of mid-FY
(June 30 of year Y) for FY-Y annual EPS.

DECISIVE TEST (forecast-error parity):
  Rebuild the SAME quantity from Tushare report_rc, filtering visibility by the
  report_date+1 anchor (effective = strictly_next_open_trade_day(report_date) <= asof),
  i.e. the as-of-mid-Y consensus FY-Y EPS forecast / realized FY-Y actual basic_eps - 1.
  Then compare cell-by-cell to JQ.

  * If Tushare REPRODUCES JQ's real errors -- especially the big positive cyclical
    errors in 2015 (神华/海螺 over-optimism into the bust) that flip negative into the
    2017 boom -- then report_date+1 reconstructs the genuine PIT consensus -> the
    report_date timestamps are faithful -> report_date+1 is a VALIDATED PIT anchor.
  * If Tushare shows SMALL errors where JQ had BIG ones (it "knew" the bust early),
    report_date+1 leaks -> forward-only verdict stands.

SCOPE (honest): this validates report_date+1 as a faithful anchor for the consensus
LEVEL/error the JQ oracle can see. It does NOT by itself prove the per-analyst
revision-BREADTH (eps_diffusion) deep history is uncorrupted (a backfill could preserve
levels yet drop/restate individual revisions). That residual is the restatement-canary's
job. But a pass here is strong, direct evidence the deep-history timestamps are real.

Sandbox; reads raw data/ only; touches no OOS, writes only a JSON/CSV under
workspace/outputs/.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
from data_infra.pit_backend import strictly_next_open_trade_day  # noqa: E402

RC_DIR = PROJECT_ROOT / "data" / "analyst" / "report_rc"
INCOME_DIR = PROJECT_ROOT / "data" / "fundamentals" / "income"
TRADE_CAL = PROJECT_ROOT / "data" / "reference" / "trade_cal.parquet"
JQ_PIT = PROJECT_ROOT / "聚宽回测明细" / "jq_consensus_pit_test.csv"
OUT_DIR = PROJECT_ROOT / "workspace" / "outputs"

MAX_AGE_DAYS = 400  # forecast-age expiry (matches report_rc_consensus.py)

# JQ stock code (.XSHG/.XSHE) -> Tushare (.SH/.SZ)
JQ2TS = {".XSHG": ".SH", ".XSHE": ".SZ"}
NAME = {
    "600519.SH": "茅台", "000858.SZ": "五粮液", "600036.SH": "招行",
    "000001.SZ": "平安银行", "601318.SH": "中国平安", "600276.SH": "恒瑞",
    "600887.SH": "伊利", "002415.SZ": "海康", "600030.SH": "中信证券",
    "601166.SH": "兴业银行", "000651.SZ": "格力", "600585.SH": "海螺(cement)",
    "601088.SH": "神华(coal)", "600009.SH": "上海机场", "600900.SH": "长电",
}
CYCLICALS = {"600585.SH", "601088.SH"}  # the regime-sign-flip canaries


def jq_to_ts(code: str) -> str:
    for k, v in JQ2TS.items():
        if code.endswith(k):
            return code.replace(k, v)
    return code


def load_rc(stocks, years) -> pd.DataFrame:
    cols = ["ts_code", "report_date", "org_name", "author_name", "quarter", "eps", "create_time"]
    frames = []
    for y in years:
        f = RC_DIR / f"report_rc_{y}.parquet"
        if f.exists():
            df = pd.read_parquet(f, columns=cols)
            frames.append(df[df["ts_code"].isin(stocks)])
    rc = pd.concat(frames, ignore_index=True)
    rc["report_date"] = pd.to_datetime(rc["report_date"], format="%Y%m%d", errors="coerce")
    rc = rc[rc["report_date"].notna()].copy()
    rc["eps"] = pd.to_numeric(rc["eps"], errors="coerce")
    cal = pd.read_parquet(TRADE_CAL)
    open_cal = pd.DatetimeIndex(
        pd.to_datetime(cal.loc[cal["is_open"] == 1, "cal_date"], format="%Y%m%d")).sort_values()
    rc["effective_date"] = strictly_next_open_trade_day(rc["report_date"], open_cal)  # report_date+1 anchor
    rc = rc[rc["effective_date"].notna()].copy()
    rc["org_author"] = rc["org_name"].astype(str) + "|" + rc["author_name"].astype(str)
    return rc.sort_values("report_date").reset_index(drop=True)


def load_actual_eps(stocks) -> dict:
    """Realized FY annual basic_eps, as ORIGINALLY reported (min ann_date per end_date).

    Keyed by (ts_code, fiscal_year:int) -> basic_eps. PIT-consistent 'actual' = the
    first-reported annual number (what was realized/known at disclosure, not a later
    restatement).
    """
    frames = []
    for f in sorted(INCOME_DIR.glob("*.parquet")):
        df = pd.read_parquet(f, columns=["ts_code", "ann_date", "end_date", "report_type", "basic_eps"])
        frames.append(df[df["ts_code"].isin(stocks)])
    inc = pd.concat(frames, ignore_index=True)
    # end_date is raw YYYYMMDD; use numeric ops (NOT astype(str) — PIT001 lint) to
    # select the annual (Dec-31) consolidated rows and extract the fiscal year.
    end_num = pd.to_numeric(inc["end_date"], errors="coerce")
    inc = inc[(inc["report_type"].astype(str) == "1") & (end_num % 10000 == 1231)]
    inc["basic_eps"] = pd.to_numeric(inc["basic_eps"], errors="coerce")
    inc = inc.dropna(subset=["basic_eps"])
    inc["ann_date"] = pd.to_numeric(inc["ann_date"], errors="coerce")
    inc = inc.sort_values("ann_date").drop_duplicates(subset=["ts_code", "end_date"], keep="first")
    inc["fy"] = (pd.to_numeric(inc["end_date"], errors="coerce") // 10000).astype(int)
    return {(r.ts_code, r.fy): r.basic_eps for r in inc.itertuples(index=False)}


def consensus_fy_eps(rc: pd.DataFrame, ts_code: str, fy: int, asof: pd.Timestamp) -> tuple:
    """As-of `asof` consensus FY-`fy` annual EPS forecast (report_date+1 anchor).

    quarter == f'{fy}Q4'; visible iff effective<=asof and report_date within MAX_AGE;
    one (latest) vote per analyst; mean across analysts.
    """
    lo = asof - pd.Timedelta(days=MAX_AGE_DAYS)
    vis = rc[(rc["ts_code"] == ts_code) & (rc["effective_date"] <= asof)
             & (rc["report_date"] >= lo) & (rc["quarter"].astype(str) == f"{fy}Q4")]
    vis = vis.dropna(subset=["eps"])
    if vis.empty:
        return np.nan, 0
    latest = vis.drop_duplicates(subset=["org_author"], keep="last")  # rc sorted by report_date asc
    return float(latest["eps"].mean()), int(latest["org_author"].nunique())


def main():
    jq = pd.read_csv(JQ_PIT)
    jq["ts_code"] = jq["stock"].map(jq_to_ts)
    stocks = sorted(jq["ts_code"].unique())
    years = range(2010, 2021)
    rc = load_rc(stocks, years)
    actual = load_actual_eps(stocks)
    cal = pd.read_parquet(TRADE_CAL)
    open_days = pd.DatetimeIndex(
        pd.to_datetime(cal.loc[cal["is_open"] == 1, "cal_date"], format="%Y%m%d")).sort_values()

    rows = []
    for r in jq.itertuples(index=False):
        fy = int(r.fy)
        ts = r.ts_code
        # as-of mid-FY = first trading day on/after June 30 of year fy
        asof_cal = pd.Timestamp(f"{fy}-06-30")
        asof = open_days[open_days >= asof_cal][0]
        pred, n = consensus_fy_eps(rc, ts, fy, asof)
        act = actual.get((ts, fy), np.nan)
        ts_err = pred / act - 1 if (pred == pred and act == act and abs(act) > 1e-9) else np.nan
        rows.append({
            "fy": fy, "ts_code": ts, "name": NAME.get(ts, ts),
            "jq_err": float(r.pred_over_actual_minus1),
            "ts_pred_eps": pred, "ts_actual_eps": act, "ts_n_analysts": n,
            "ts_err": ts_err, "cyclical": ts in CYCLICALS,
        })
    res = pd.DataFrame(rows)
    paired = res.dropna(subset=["jq_err", "ts_err"]).copy()

    print(f"\nreport_rc rows loaded: {len(rc):,} ({rc['ts_code'].nunique()} stocks)")
    print(f"JQ cells: {len(res)}   paired (both errors present): {len(paired)}")
    print(f"Tushare coverage: {res['ts_err'].notna().mean()*100:.0f}% of JQ cells reconstructed")

    if len(paired) >= 5:
        pear = paired["jq_err"].corr(paired["ts_err"])
        spear = paired["jq_err"].corr(paired["ts_err"], method="spearman")
        mae = (paired["jq_err"] - paired["ts_err"]).abs().mean()
        # the lookahead discriminator: is Tushare systematically MORE accurate (smaller |err|) than PIT JQ?
        d_absdiff = paired["ts_err"].abs().mean() - paired["jq_err"].abs().mean()
        print(f"\n=== forecast-error parity (n={len(paired)}) ===")
        print(f"  Pearson  corr(jq_err, ts_err) = {pear:+.3f}")
        print(f"  Spearman corr               = {spear:+.3f}")
        print(f"  mean |jq_err - ts_err|       = {mae:.3f}")
        print(f"  mean|ts_err| - mean|jq_err|  = {d_absdiff:+.3f}   "
              f"(<<0 => Tushare suspiciously accurate => LOOKAHEAD; ~0 => equally blind => PIT-faithful)")

    print("\n=== CYCLICAL REGIME CANARIES (the decisive cells) ===")
    can = res[res["cyclical"]].sort_values(["name", "fy"])
    print(can[["fy", "name", "jq_err", "ts_err", "ts_pred_eps", "ts_actual_eps", "ts_n_analysts"]]
          .to_string(index=False))

    print("\n=== full per-cell table ===")
    show = res.sort_values(["fy", "name"])[["fy", "name", "jq_err", "ts_err", "ts_n_analysts"]]
    print(show.to_string(index=False))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    res.to_csv(OUT_DIR / "report_rc_pit_anchor_validation.csv", index=False)
    summary = {
        "n_jq_cells": int(len(res)),
        "n_paired": int(len(paired)),
        "tushare_reconstruct_coverage": float(res["ts_err"].notna().mean()),
        "pearson": float(paired["jq_err"].corr(paired["ts_err"])) if len(paired) >= 5 else None,
        "spearman": float(paired["jq_err"].corr(paired["ts_err"], method="spearman")) if len(paired) >= 5 else None,
        "mae": float((paired["jq_err"] - paired["ts_err"]).abs().mean()) if len(paired) >= 5 else None,
        "mean_abs_ts_minus_jq": float(paired["ts_err"].abs().mean() - paired["jq_err"].abs().mean()) if len(paired) >= 5 else None,
    }
    (OUT_DIR / "report_rc_pit_anchor_validation.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT_DIR / 'report_rc_pit_anchor_validation.csv'}")


if __name__ == "__main__":
    main()
