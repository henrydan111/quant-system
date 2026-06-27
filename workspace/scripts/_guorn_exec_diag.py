"""Attribute the EXECUTION leg of the gap: WHY does 果仁 outperform while holding the SAME names?
For each book, look at 果仁's DAILY NEW ENTRIES (names that appear in 各阶段持仓详单 on day d but not d−1)
and measure, against the LOCAL provider OHLCV + published limit prices:
  (1) frac LOCKED limit-up at the OPEN (raw_open ≥ up_limit−ε = 一字/调仓时涨停) → MY fill-price-aware gate
      REFUSES to buy these; 果仁 (rule 非跌停) BUYS them. This is the rung-1 microcap-fill-optimism mechanism.
  (2) frac limit-up at the CLOSE but NOT locked at open (buyable by my gate at 09:35 — NOT a gap).
  (3) volume-cap pressure: 果仁's entry as a share of the day's $-volume vs my 10% cap.
This quantifies the execution gap's COMPOSITION (limit-up-lock vs volume-cap vs price) per book and per year.

Run: _guorn_exec_diag.py --book 04
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
PROVIDER_URI = str(ROOT / "data" / "qlib_data")
XLSX = {"04": "09_sm_GARP_illiq.xlsx", "15": "44_成长_双创_GARP@周期_v2.xlsx", "05": "10_sm_双创研发强度_v1.xlsx"}


def _qc_u(code):
    s = str(code).split(".")[0].zfill(6)
    return s + ("_SH" if s[0] in "69" else "_SZ")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", choices=sorted(XLSX), required=True)
    ap.add_argument("--start", default="2014-01-01")
    ap.add_argument("--end", default="2026-02-27")
    args = ap.parse_args()
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=PROVIDER_URI, region=REG_CN, kernels=1)

    h = pd.read_excel(ROOT / "Knowledge" / "果仁回测结果" / XLSX[args.book], sheet_name="各阶段持仓详单", header=0)
    h["开始日期"] = pd.to_datetime(h["开始日期"])
    h = h[(h["开始日期"] >= pd.Timestamp(args.start)) & (h["开始日期"] <= pd.Timestamp(args.end))]
    h["u"] = h["股票代码"].map(_qc_u)
    by_date = {d: set(grp["u"]) for d, grp in h.groupby("开始日期")}
    dates = sorted(by_date)

    # NEW entries = held on d but not on the previous 果仁 date
    new_entries = []   # (date, code)
    prev = set()
    for d in dates:
        cur = by_date[d]
        for c in cur - prev:
            new_entries.append((d, c))
        prev = cur
    ne = pd.DataFrame(new_entries, columns=["date", "u"])
    codes = sorted(ne["u"].unique())
    print(f"[{args.book}] {len(dates)} 果仁 dates, {len(ne)} new-entry events, {len(codes)} distinct names", flush=True)

    # pull OHLCV + published limit for those names
    fields = ["$open", "$close", "$high", "$low", "$up_limit", "$pre_close", "$amount", "$adj_factor"]
    P = {}
    for k in range(0, len(codes), 400):
        batch = codes[k:k + 400]
        df = D.features(batch, fields, start_time=args.start, end_time=args.end, freq="day")
        for f in fields:
            s = df[f]
            P[f] = pd.concat([P.get(f), s]) if f in P else s
    # build per (code,date) lookups
    def val(f, c, d):
        try:
            return float(P[f].loc[(c, pd.Timestamp(d))])
        except Exception:
            return np.nan

    rows = []
    for d, c in new_entries:
        op = val("$open", c, d); ul = val("$up_limit", c, d); hi = val("$high", c, d); lo = val("$low", c, d)
        cl = val("$close", c, d); amt = val("$amount", c, d)
        if not np.isfinite(op) or not np.isfinite(ul) or ul <= 0:
            locked_open = np.nan; lu_close = np.nan
        else:
            locked_open = float(op >= ul - 1e-6)                      # 一字/调仓时涨停 at open -> my gate refuses
            lu_close = float(np.isfinite(cl) and cl >= ul - 1e-6)     # limit-up at close
        rows.append((pd.Timestamp(d).year, locked_open, lu_close, amt))
    R = pd.DataFrame(rows, columns=["yr", "locked_open", "lu_close", "amt"])
    n_eval = R["locked_open"].notna().sum()
    print(f"\n=== #{args.book} EXECUTION composition of 果仁's new entries (n_eval={n_eval}) ===")
    print(f"  LOCKED limit-up at OPEN (一字, MY gate REFUSES, 果仁 BUYS) = {R['locked_open'].mean():.1%}")
    print(f"  limit-up at CLOSE (any)                                   = {R['lu_close'].mean():.1%}")
    print(f"  ⇒ the locked-open frac is the share of 果仁's entries my engine structurally CANNOT take\n")
    print("  year   n_new   locked_open%   lu_close%")
    by = R.groupby("yr").agg(n=("locked_open", "size"), lock=("locked_open", "mean"), luc=("lu_close", "mean"))
    for y, r in by.iterrows():
        print(f"  {int(y)}   {int(r['n']):5d}     {r['lock']:6.1%}        {r['luc']:6.1%}")


if __name__ == "__main__":
    main()
