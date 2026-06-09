"""Interpret Test A: is JoinQuant's as-of consensus a genuine forecast or hindsight-filled?

Decisive question is NOT the pooled median (mid-year forecasts of stable names are
naturally accurate); it's whether LARGE errors appear and are economically coherent
with the cyclical regime (over-optimism into a bust, under-estimation into a boom).
A hindsight-filled series would be ~0 every year for every name.
"""
import os
import pandas as pd

F = r"E:\量化系统\聚宽回测明细\jq_consensus_pit_test.csv"
df = pd.read_csv(F)
e = df["pred_over_actual_minus1"]

print("=== pooled ===")
print(f"n={len(e)}  median={e.median():+.1%}  mean={e.mean():+.1%}  std={e.std():.1%}  "
      f"min={e.min():+.1%}  max={e.max():+.1%}  |err|<5%={ (e.abs()<0.05).mean():.0%}  "
      f"|err|>20%={ (e.abs()>0.20).mean():.0%}")

print("\n=== per fiscal year: median / spread / share with big error ===")
g = df.groupby("fy")["pred_over_actual_minus1"]
per_yr = pd.DataFrame({
    "median": g.median(), "p10": g.quantile(.10), "p90": g.quantile(.90),
    "frac|err|>20%": g.apply(lambda s: (s.abs() > 0.20).mean()),
}).round(3)
print(per_yr.to_string())

print("\n=== cyclicals (coal/cement) vs staples-utilities (should differ sharply if PIT) ===")
names = {"601088.XSHG": "神华(coal)", "600585.XSHG": "海螺(cement)",
         "600900.XSHG": "长电(utility)", "600519.XSHG": "茅台(staple)",
         "600036.XSHG": "招行(bank)"}
piv = df[df["stock"].isin(names)].pivot(index="fy", columns="stock",
                                        values="pred_over_actual_minus1")
piv = piv.rename(columns=names)
print(piv.round(3).to_string())
