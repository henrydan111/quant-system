"""Reverse-engineer ROETTMDiffPQ (净资产收益率 − RefQ(净资产收益率,1)) vs 果仁's EXPORTED column.
Try candidate ROE definitions (vendor roe variants + my TTM end/avg-equity) -> QoQ diff -> compare to
果仁's ROETTMDiffPQ over held names. Best sign%/rel-err = the right 净资产收益率."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "workspace" / "research" / "long_only_50cagr"))
sys.stdout.reconfigure(encoding="utf-8")
import research_utils as ru  # noqa: E402

XLSX = ROOT / "Knowledge" / "果仁回测结果" / "01_sm_01_成长动量.xlsx"
VENDOR = ["roe", "roe_waa", "roe_avg", "q_roe", "roe_dt", "roe_yearly"]


def _qc(code):
    s = str(code).split(".")[0].zfill(6)
    return s + ("_SH" if s[0] in "69" else "_SZ")


def main():
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=str(ROOT / "data" / "qlib_data"), region=REG_CN, kernels=1)

    h = pd.read_excel(XLSX, sheet_name="各阶段持仓详单", header=0)
    h["开始日期"] = pd.to_datetime(h["开始日期"]); h["qc"] = h["股票代码"].map(_qc)
    h["theirs"] = pd.to_numeric(h["ROETTMDiffPQ"], errors="coerce")
    cal = ru.trading_calendar()
    pos = cal.searchsorted(h["开始日期"].values)
    h["pday"] = [cal[p - 1] if p > 0 else pd.NaT for p in pos]
    h = h.dropna(subset=["pday", "theirs"])
    insts = sorted(h["qc"].unique())
    print(f"[roe-re] {len(h)} holdings, {len(insts)} unique names", flush=True)

    fields = []
    for v in VENDOR:
        fields += [f"${v}_q0", f"${v}_q1"]
    fields += [f"$n_income_attr_p_sq_q{i}" for i in range(5)]
    fields += ["$total_hldr_eqy_exc_min_int_q0", "$total_hldr_eqy_exc_min_int_q1", "$total_hldr_eqy_exc_min_int_q4"]
    s, e = h["pday"].min().strftime("%Y-%m-%d"), h["pday"].max().strftime("%Y-%m-%d")
    P = {}
    for k in range(0, len(fields), 6):
        b = fields[k:k + 6]
        try:
            df = D.features(insts, b, start_time=s, end_time=e, freq="day")
            for c in b:
                P[c.replace("$", "")] = df[c].unstack(level=0).sort_index().ffill()
        except Exception as ex:
            print(f"  (skip {b}: {ex})")
    EPS = 1e-9

    def lookup(fr):
        out = []
        for pday, grp in h.groupby("pday"):
            out.append(grp["qc"].map(fr.loc[pday]).set_axis(grp.index) if pday in fr.index else pd.Series(np.nan, index=grp.index))
        return pd.concat(out)

    cand = {}
    for v in VENDOR:
        if f"{v}_q0" in P and f"{v}_q1" in P:
            cand[f"vendor:{v}"] = lookup(P[f"{v}_q0"]) - lookup(P[f"{v}_q1"])
            cand[f"vendor:{v}/100"] = (lookup(P[f"{v}_q0"]) - lookup(P[f"{v}_q1"])) / 100.0
    if all(f"n_income_attr_p_sq_q{i}" in P for i in range(5)):
        ni = {i: lookup(P[f"n_income_attr_p_sq_q{i}"]) for i in range(5)}
        eq0, eq1 = lookup(P["total_hldr_eqy_exc_min_int_q0"]), lookup(P["total_hldr_eqy_exc_min_int_q1"])
        eq4 = lookup(P["total_hldr_eqy_exc_min_int_q4"])
        ttm0, ttm1 = ni[0] + ni[1] + ni[2] + ni[3], ni[1] + ni[2] + ni[3] + ni[4]
        cand["mine:TTM/end_eq"] = ttm0 / eq0.where(eq0.abs() > EPS) - ttm1 / eq1.where(eq1.abs() > EPS)
        avg0 = (eq0 + eq4) / 2.0
        cand["mine:TTM/avg_eq(q0,q4)"] = ttm0 / avg0.where(avg0.abs() > EPS) - ttm1 / eq1.where(eq1.abs() > EPS)

    th = h["theirs"]
    print(f"\n{'candidate':28} {'n':>6} {'med_relerr':>10} {'sign%':>6} {'corr':>6}")
    print("-" * 64)
    best = []
    for name, series in cand.items():
        ok = pd.DataFrame({"m": series, "t": th}).dropna()
        ok = ok[ok["t"].abs() > 1e-6]
        if len(ok) < 100:
            continue
        rel = (ok["m"] - ok["t"]).abs() / ok["t"].abs().clip(lower=1e-6)
        sign = (np.sign(ok["m"]) == np.sign(ok["t"])).mean()
        corr = ok["m"].corr(ok["t"])
        best.append((name, rel.median(), sign, corr, len(ok)))
    for name, med, sign, corr, n in sorted(best, key=lambda x: (-x[2], x[1])):
        print(f"{name:28} {n:>6} {med:>10.3f} {sign:>6.1%} {corr:>6.2f}")


if __name__ == "__main__":
    main()
