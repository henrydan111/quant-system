"""Rung-3 Phase-1: validate the LOCAL 业绩预告 (forecast) event-PIT serving by
reproducing 果仁's forecast factor 业绩预告净利润QGr%PYQ_v1 at scale and matching it.

Formula (reverse-engineered + hand-verified, 5/5 to the decimal):
  Q, FY = quarter & fiscal-year of the latest forecast's period (end_date)
  mid   = (net_profit_min + net_profit_max)/2          # 万元, latest forecast as-of date
  single_q_fc = mid - income_cum[FY, Q-1]              # (mid alone if Q==1) = the forecast's last single quarter
  py_single   = income_cum[FY-1, Q] - income_cum[FY-1, Q-1]   # prior-year same single quarter
  growth = (single_q_fc - py_single) / abs(py_single)
All inputs are PIT (forecast effective_date; income effective_date <= the holding date).

This is the rung-3 equivalent of rung-2's net-profit penny-match: a high match rate
proves the local forecast + income serving reproduces what 果仁 saw. Reads the RAW
ledgers for the reverse-engineering/validation (the eventual materializer routes through
the provider). Saves rung3_forecast_validation.json.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8")
OUT = ROOT / "workspace" / "outputs" / "guorn_parity"
OUT.mkdir(parents=True, exist_ok=True)

# books whose holdings expose 公式(业绩预告净利润QGr%PYQ_v1)
BOOKS = ["01_sm_01_成长动量", "07_sm_大制造GARP_v3", "10_sm_双创研发强度_v1",
         "48_成长_高波@周期", "53_ST_大市值_v3"]
QMONTH = {3: 1, 6: 2, 9: 3, 12: 4}


def _prev_qend(year, q):
    """end_date of quarter q-1 in `year` (None if q==1)."""
    return None if q == 1 else pd.Timestamp(year, {2: 3, 3: 6, 4: 9}[q], {3: 31, 6: 30, 9: 30}[{2: 3, 3: 6, 4: 9}[q]])


def main():
    fc = pd.read_parquet(ROOT / "data/pit_ledger/forecast/forecast.parquet",
                         columns=["ts_code", "end_date", "effective_date", "net_profit_min",
                                  "net_profit_max", "disclosure_date", "ann_date", "first_ann_date"])
    inc = pd.read_parquet(ROOT / "data/pit_ledger/income/income.parquet",
                          columns=["ts_code", "end_date", "effective_date", "n_income"])
    for c in ("end_date", "effective_date", "disclosure_date", "ann_date", "first_ann_date"):
        if c in fc.columns:
            fc[c] = pd.to_datetime(fc[c], errors="coerce")
    for c in ("end_date", "effective_date"):
        inc[c] = pd.to_datetime(inc[c])
    # deterministic same-effective-date tie-break (GPT R1 Major-1), identical to the materializer
    fc = fc.dropna(subset=["end_date", "effective_date"]).sort_values(
        ["effective_date", "disclosure_date", "ann_date", "first_ann_date", "end_date"], kind="mergesort")
    inc = inc.dropna(subset=["end_date", "effective_date", "n_income"]).sort_values("effective_date")
    fc_by = {k: g for k, g in fc.groupby("ts_code")}
    inc_by = {k: g for k, g in inc.groupby("ts_code")}

    def inc_cum(ts, end, asof):
        """cumulative n_income (万元) for fiscal quarter-end `end`, visible as-of `asof`."""
        g = inc_by.get(ts)
        if g is None:
            return np.nan
        sub = g[(g["end_date"] == end) & (g["effective_date"] <= asof)]
        return sub["n_income"].iloc[-1] / 1e4 if len(sub) else np.nan

    def forecast_growth(ts, asof):
        g = fc_by.get(ts)
        if g is None:
            return np.nan
        sub = g[g["effective_date"] <= asof]
        if sub.empty:
            return np.nan
        r = sub.iloc[-1]
        end = r["end_date"]; q = QMONTH.get(end.month)
        if q is None:
            return np.nan
        mid = (r["net_profit_min"] + r["net_profit_max"]) / 2.0   # 万元
        fy = end.year
        prior_cum = 0.0 if q == 1 else inc_cum(ts, _prev_qend(fy, q), asof)
        py_cum_q = inc_cum(ts, pd.Timestamp(fy - 1, end.month, end.day), asof)
        py_cum_qm1 = 0.0 if q == 1 else inc_cum(ts, _prev_qend(fy - 1, q), asof)
        if not (np.isfinite(mid) and np.isfinite(prior_cum) and np.isfinite(py_cum_q) and np.isfinite(py_cum_qm1)):
            return np.nan
        single_q_fc = mid - prior_cum
        py_single = py_cum_q - py_cum_qm1
        if py_single == 0:
            return np.nan
        return (single_q_fc - py_single) / abs(py_single)

    recs = []
    for book in BOOKS:
        p = ROOT / "Knowledge" / "果仁回测结果" / f"{book}.xlsx"
        if not p.exists():
            continue
        g = pd.read_excel(p, sheet_name="各阶段持仓详单")
        col = next((c for c in g.columns if "业绩预告净利润QGr" in str(c)), None)
        if col is None:
            continue
        c6 = g["股票代码"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)
        g = g.assign(ts=c6 + np.where(c6.str[0].isin(["6", "9"]), ".SH", ".SZ"),
                     date=pd.to_datetime(g["开始日期"]), gf=pd.to_numeric(g[col], errors="coerce")).dropna(subset=["gf"])
        for _, r in g.iterrows():
            recs.append((r["ts"], r["date"], r["gf"], forecast_growth(r["ts"], r["date"])))
    cmp = pd.DataFrame(recs, columns=["ts", "date", "guorn", "local"])
    have = cmp.dropna(subset=["local"])
    rel = (have["local"] - have["guorn"]).abs() / have["guorn"].abs().clip(lower=0.05)
    sign_ok = (np.sign(have["local"]) == np.sign(have["guorn"])).mean()
    out = {
        "n_holdings": int(len(cmp)), "n_reproduced": int(len(have)),
        "coverage": float(len(have) / max(len(cmp), 1)),
        "median_relerr": float(rel.median()), "within_1pct": float((rel <= 0.01).mean()),
        "within_5pct": float((rel <= 0.05).mean()), "sign_match": float(sign_ok),
    }
    OUT.joinpath("rung3_forecast_validation.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("=== rung-3 forecast factor reproduction vs 果仁 (业绩预告净利润QGr%PYQ_v1) ===")
    for k, v in out.items():
        print(f"  {k}: {v}")
    print("\n  sample (guorn vs local):")
    for _, r in have.sample(min(8, len(have)), random_state=2).iterrows():
        print(f"    {r['ts']} {r['date'].date()}  果仁={r['guorn']:+.4f}  local={r['local']:+.4f}")


if __name__ == "__main__":
    main()
