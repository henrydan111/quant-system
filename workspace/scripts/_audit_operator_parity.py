"""Qlib-vs-pandas operator parity probe (factor audit, 2026-05-30).

For each Qlib operator used by the factor library, compute it via the sanctioned
compute_factors path AND re-derive the identical formula in pandas on the same
t-1 close/high/low/vol series, then compare. Catches silent operator bugs like
the confirmed Count() defect (Count ignores its condition, returns N).

Light: 3 stocks, ~1y window. Read-only.
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import numpy as np, pandas as pd
from src.alpha_research.factor_library import operators as op

# Base inputs (all t-1, raw) we will also reconstruct in pandas.
CAT = {
    "px":   "Ref($close, 1)",
    "hi":   "Ref($high, 1)",
    "lo":   "Ref($low, 1)",
    "vl":   "Ref($vol, 1)",
    # operator tests on px:
    "Mean5":   "Mean(Ref($close, 1), 5)",
    "Std5":    "Std(Ref($close, 1), 5)",
    "Sum5":    "Sum(Ref($close, 1), 5)",
    "Max5":    "Max(Ref($close, 1), 5)",
    "Min5":    "Min(Ref($close, 1), 5)",
    "Med5":    "Med(Ref($close, 1), 5)",
    "Skew10":  "Skew(Ref($close, 1), 10)",
    "Kurt10":  "Kurt(Ref($close, 1), 10)",
    "Quant5":  "Quantile(Ref($close, 1), 5, 0.5)",
    "Delta3":  "Delta(Ref($close, 1), 3)",
    "EMA5":    "EMA(Ref($close, 1), 5)",
    "WMA5":    "WMA(Ref($close, 1), 5)",
    "IdxMax5": "IdxMax(Ref($close, 1), 5)",
    "IdxMin5": "IdxMin(Ref($close, 1), 5)",
    "CountPos5": "Count(Ref($close, 1) > 0, 5)",        # known broken
    "SumIfPos5": "Sum(If(Ref($close, 1) > 0, 1, 0), 5)",  # correct comparator
    "Corr5":   "Corr(Ref($close, 1), Ref($vol, 1), 5)",
    "Cov5":    "Cov(Ref($close, 1), Ref($vol, 1), 5)",
    "Slope5":  "Slope(Ref($close, 1), 5)",
}

f, _ = op.compute_factors(catalog=CAT, start_date="2018-01-01", end_date="2019-06-30",
                          horizons=[5], qlib_dir=str(ROOT/"data"/"qlib_data"),
                          kernels=1, stage="is_only")
# f index: (datetime, instrument) after swaplevel in compute_factors -> (instrument? ) ; normalize
# compute_factors returns swaplevel().sort_index() -> (datetime, instrument)? guide says it swaps to (instrument? ) — just group by instrument level.
names = f.index.names
inst_level = 1 if names[0] == "datetime" else 0
px = f["px"]; hi = f["hi"]; lo = f["lo"]; vl = f["vl"]


def g(s):
    return s.groupby(level=inst_level, group_keys=False)


def report(label, qlib_col, pandas_series, note=""):
    a = f[qlib_col]
    b = pandas_series.reindex(a.index)
    m = a.notna() & b.notna()
    n = int(m.sum())
    if n < 50:
        print(f"  {label:11s} INSUFFICIENT n={n}"); return
    aa, bb = a[m].to_numpy(float), b[m].to_numpy(float)
    corr = np.corrcoef(aa, bb)[0, 1]
    denom = np.maximum(np.abs(bb), 1e-9)
    mad = float(np.max(np.abs(aa - bb) / denom))
    verdict = "PASS" if corr > 0.9999 and mad < 1e-3 else ("CORR-OK/scale" if corr > 0.999 else "FAIL")
    print(f"  {label:11s} corr={corr:.5f} maxRelDiff={mad:.3e} -> {verdict} {note}")


print("=== rolling stats ===")
report("Mean5",  "Mean5", g(px).apply(lambda s: s.rolling(5).mean()))
report("Std5(d1)","Std5", g(px).apply(lambda s: s.rolling(5).std(ddof=1)), "ddof=1")
report("Std5(d0)","Std5", g(px).apply(lambda s: s.rolling(5).std(ddof=0)), "ddof=0")
report("Sum5",   "Sum5", g(px).apply(lambda s: s.rolling(5).sum()))
report("Max5",   "Max5", g(px).apply(lambda s: s.rolling(5).max()))
report("Min5",   "Min5", g(px).apply(lambda s: s.rolling(5).min()))
report("Med5",   "Med5", g(px).apply(lambda s: s.rolling(5).median()))
report("Skew10", "Skew10", g(px).apply(lambda s: s.rolling(10).skew()))
report("Kurt10", "Kurt10", g(px).apply(lambda s: s.rolling(10).kurt()))
report("Quant5", "Quant5", g(px).apply(lambda s: s.rolling(5).quantile(0.5)))
report("Delta3", "Delta3", g(px).apply(lambda s: s - s.shift(3)))

print("=== moving averages ===")
report("EMA5", "EMA5", g(px).apply(lambda s: s.ewm(span=5, adjust=False).mean()), "span/adjust may differ")
def wma(s, n):
    w = np.arange(1, n+1)
    return s.rolling(n).apply(lambda x: np.dot(x, w)/w.sum(), raw=True)
report("WMA5", "WMA5", g(px).apply(lambda s: wma(s, 5)), "linear-weight assumption")

print("=== index positions (IdxMax/IdxMin = 'days since extreme') ===")
def days_since_max(s, n):
    return s.rolling(n).apply(lambda x: n - 1 - int(np.argmax(x)), raw=True)
def days_since_min(s, n):
    return s.rolling(n).apply(lambda x: n - 1 - int(np.argmin(x)), raw=True)
report("IdxMax5(a)", "IdxMax5", g(px).apply(lambda s: days_since_max(s, 5)), "n-1-argmax")
report("IdxMin5(a)", "IdxMin5", g(px).apply(lambda s: days_since_min(s, 5)), "n-1-argmin")

print("=== conditional counts (THE bug) ===")
report("CountPos5", "CountPos5", g(px).apply(lambda s: (s > 0).rolling(5).sum()), "expect FAIL")
report("SumIfPos5", "SumIfPos5", g(px).apply(lambda s: (s > 0).rolling(5).sum()), "expect PASS")

print("=== cross-series ===")
both = pd.DataFrame({"px": px, "vl": vl})
def roll_corr(df, n):
    return df.groupby(level=inst_level, group_keys=False).apply(
        lambda x: x["px"].rolling(n).corr(x["vl"]))
def roll_cov(df, n):
    return df.groupby(level=inst_level, group_keys=False).apply(
        lambda x: x["px"].rolling(n).cov(x["vl"]))
report("Corr5", "Corr5", roll_corr(both, 5))
report("Cov5",  "Cov5",  roll_cov(both, 5))
def roll_slope(s, n):
    t = np.arange(n)
    def _sl(x):
        return np.polyfit(t, x, 1)[0]
    return s.rolling(n).apply(_sl, raw=True)
report("Slope5", "Slope5", g(px).apply(lambda s: roll_slope(s, 5)), "OLS slope vs time")
print("DONE")
