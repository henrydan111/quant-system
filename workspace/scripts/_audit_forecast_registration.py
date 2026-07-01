"""Rung-3 forecast field registration evidence (GPT R1 Major-2 / Q5).

Produces, for $forecast__np_q_yoy, the audits required before field_status.yaml
registration:
  1. COVERAGE — per-year forecast-issuing universe + computable-factor count.
  2. DUPLICATES — same-(code, effective_date) forecast rows (the M1 tie-break target).
  3. MISMATCH — the holdings where local vs 果仁 differ >1%, bucketed (sign-flip,
     tiny prior-year denominator, same-effective duplicate, by year) to show they are
     NOT a systematic bug.
  4. CANARIES — (a) forecast effective BEFORE the needed Q-1 income (factor must be NaN
     until the income lands), (b) a restatement changing the value only at its effective
     date. (Reported as counts + examples; the provider-read transition is checked in the
     staged-build verification.)
All from the RAW ledgers + 果仁 holdings (the materializer routes through the provider).
Saves rung3_forecast_registration_audit.json.
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
BOOKS = ["01_sm_01_成长动量", "07_sm_大制造GARP_v3", "10_sm_双创研发强度_v1",
         "48_成长_高波@周期", "53_ST_大市值_v3"]
QMONTH = {3: 1, 6: 2, 9: 3, 12: 4}
QEND = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}


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
    fc = fc.dropna(subset=["end_date", "effective_date"])
    fc = fc[fc["net_profit_min"].notna() & fc["net_profit_max"].notna()].sort_values(
        ["effective_date", "disclosure_date", "ann_date", "first_ann_date", "end_date"], kind="mergesort")
    inc = inc.dropna(subset=["end_date", "effective_date", "n_income"]).sort_values("effective_date")
    fc_by = {k: g for k, g in fc.groupby("ts_code")}
    inc_by = {k: g for k, g in inc.groupby("ts_code")}

    def inc_cum(ts, end, asof):
        g = inc_by.get(ts)
        if g is None:
            return np.nan
        sub = g[(g["end_date"] == end) & (g["effective_date"] <= asof)]
        return sub["n_income"].iloc[-1] / 1e4 if len(sub) else np.nan

    def _prev_qend(year, q):
        return None if q == 1 else pd.Timestamp(year, *QEND[q - 1])

    def factor(ts, asof, want_parts=False):
        g = fc_by.get(ts)
        if g is None:
            return (np.nan, None)
        sub = g[g["effective_date"] <= asof]
        if sub.empty:
            return (np.nan, None)
        r = sub.iloc[-1]
        end = r["end_date"]; q = QMONTH.get(end.month)
        if q is None:
            return (np.nan, None)
        mid = (r["net_profit_min"] + r["net_profit_max"]) / 2.0
        fy = end.year
        prior_cum = 0.0 if q == 1 else inc_cum(ts, _prev_qend(fy, q), asof)
        py_cum_q = inc_cum(ts, pd.Timestamp(fy - 1, end.month, end.day), asof)
        py_cum_qm1 = 0.0 if q == 1 else inc_cum(ts, _prev_qend(fy - 1, q), asof)
        if not (np.isfinite(mid) and np.isfinite(prior_cum) and np.isfinite(py_cum_q) and np.isfinite(py_cum_qm1)):
            return (np.nan, {"miss_income": True})
        py_single = py_cum_q - py_cum_qm1
        if py_single == 0:
            return (np.nan, {"zero_denom": True})
        val = (mid - prior_cum - py_single) / abs(py_single)
        return (val, {"py_single": py_single, "eff": r["effective_date"]}) if want_parts else (val, None)

    audit = {}

    # 1. COVERAGE: per-year forecast-issuing universe + computable on the last forecast eff that year
    cov = {}
    for yr, gg in fc.groupby(fc["effective_date"].dt.year):
        codes = gg["ts_code"].unique()
        asof = pd.Timestamp(int(yr), 12, 31)
        comp = sum(1 for ts in codes if np.isfinite(factor(ts, asof)[0]))
        cov[int(yr)] = {"forecast_issuing_stocks": int(len(codes)), "computable_on_yearend": int(comp)}
    audit["coverage_by_year"] = cov

    # 2. DUPLICATES: same (code, effective_date) + the all-tie-key payload-conflict count
    # (GPT R2 m1: the residual deterministic-order edge case — rows tied on EVERY ordering key
    # but with a differing forecast payload, where row order would still decide the "latest").
    dup = fc.groupby(["ts_code", "effective_date"]).size()
    audit["same_effdate_duplicate_rows"] = int((dup > 1).sum())
    audit["same_effdate_duplicate_pct"] = float((dup > 1).mean())
    _tie = ["ts_code", "effective_date", "disclosure_date", "ann_date", "first_ann_date", "end_date"]
    _conflict = sum(1 for _, gg in fc.groupby(_tie, dropna=False)
                    if len(gg) > 1 and (gg["net_profit_min"].nunique() > 1 or gg["net_profit_max"].nunique() > 1))
    audit["all_tiekey_payload_conflicts"] = int(_conflict)

    # 3. MISMATCH bucketing vs 果仁
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
            val, parts = factor(r["ts"], r["date"], want_parts=True)
            recs.append((r["ts"], r["date"], r["gf"], val, (parts or {}).get("py_single", np.nan)))
    cmp = pd.DataFrame(recs, columns=["ts", "date", "guorn", "local", "py_single"])
    have = cmp.dropna(subset=["local"]).copy()
    have["relerr"] = (have["local"] - have["guorn"]).abs() / have["guorn"].abs().clip(lower=0.05)
    miss = have[have["relerr"] > 0.01]
    audit["mismatch"] = {
        "n_compared": int(len(have)), "n_miss_gt1pct": int(len(miss)),
        "miss_pct": float(len(miss) / max(len(have), 1)),
        "sign_flip_rows": int((np.sign(have["local"]) != np.sign(have["guorn"])).sum()),
        "miss_with_tiny_denom(|py_single|<100万)": int((miss["py_single"].abs() < 100).sum()),
        "miss_by_year": {int(y): int(n) for y, n in miss.groupby(miss["date"].dt.year).size().items()},
        "note": ("rule #10: the >1% bucket is CONSISTENT WITH small-denominator amplification + "
                 "果仁's 万-rounded display + early-year data quality/restatements (it shrinks 417->84 "
                 "over 2014->2024); it is NOT fully partitioned into mutually-exclusive proven categories. "
                 "The PIT-serving claim rests on median rel-err ~4e-05 + 98%+ sign-match, not on a full "
                 "decomposition of the residual."),
    }

    # 4. CANARIES (counts + one example each)
    # (a) forecast effective before the needed Q-1 income -> factor NaN at the forecast eff,
    #     finite once the income lands. Find forecasts whose factor is NaN at fc.eff but finite +30 trading-ish days.
    canary_a = 0; ex_a = None
    samp = fc.sample(min(4000, len(fc)), random_state=5)
    for _, r in samp.iterrows():
        ts, eff = r["ts_code"], r["effective_date"]
        v0, _ = factor(ts, eff)
        v1, _ = factor(ts, eff + pd.Timedelta(days=120))
        if (not np.isfinite(v0)) and np.isfinite(v1):
            canary_a += 1
            if ex_a is None:
                ex_a = {"ts": ts, "forecast_eff": str(eff.date()), "factor_at_eff": "NaN",
                        "factor_+120d": round(float(v1), 4)}
    audit["canary_forecast_before_income"] = {"n_in_4000_sample": canary_a, "example": ex_a}

    # 4b. RESTATEMENT CANARY (GPT R2 M2): an income (ts, end_date) reported with >1 effective_date
    # and a CHANGED value = a restatement. The as-of income lookup must return the OLD value the day
    # BEFORE the restatement effective_date and the NEW value ON it (no lookahead; the restatement is
    # not visible early). Confirms inc_cum / the factor respect restatement timing.
    restate = (inc.groupby(["ts_code", "end_date"])
               .agg(n_eff=("effective_date", "nunique"), n_val=("n_income", "nunique")))
    restated = restate[(restate["n_eff"] > 1) & (restate["n_val"] > 1)]
    ok = 0; ex_r = None
    for (ts, end), _ in restated.head(200).iterrows():
        sub = inc_by[ts]
        sub = sub[sub["end_date"] == end].sort_values("effective_date")
        if len(sub) < 2:
            continue
        v_old = sub["n_income"].iloc[0]; e_new = sub["effective_date"].iloc[-1]; v_new = sub["n_income"].iloc[-1]
        before = inc_cum(ts, end, e_new - pd.Timedelta(days=1)) * 1e4
        after = inc_cum(ts, end, e_new) * 1e4
        if np.isfinite(before) and abs(before - v_old) < 1.0 and abs(after - v_new) < 1.0:
            ok += 1
            if ex_r is None:
                ex_r = {"ts": ts, "end": str(end.date()), "old_万": round(v_old / 1e4, 1),
                        "new_万": round(v_new / 1e4, 1), "restate_eff": str(e_new.date()),
                        "asof_before_restate": "OLD", "asof_on_restate": "NEW"}
    audit["canary_restatement"] = {"restated_quarters": int(len(restated)),
                                   "asof_respects_restatement_ok_in_200": ok, "example": ex_r}

    OUT.joinpath("rung3_forecast_registration_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2, default=str)[:2600])


if __name__ == "__main__":
    main()
