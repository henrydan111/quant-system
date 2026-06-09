"""M3b — final fair tests of the literal 大小盘轮动 + clean de-risk overlay.

Reuses cached base books from m3_regime.py (no new backtests). Tests:
  (a) relative-strength rotation: always invested, hold small book when 中证1000
      is relatively stronger than 沪深300 (ratio>MA), else large book. The literal
      "大小盘轮动" — rotate to the relatively stronger style.
  (b) clean broad de-risk: best book (largeVL), to cash only when 沪深300<MA
      (the prior effort's overlay applied to the best book) — best-case MDD cut.

This closes out the regime family. No further config dredging (anti-overfit).
"""
from __future__ import annotations
import json
import numpy as np, pandas as pd
import jq_utils as J
import overlay as ov

IS_START, IS_END = "2014-01-01", "2020-12-31"
bdf = pd.read_parquet(J.OUT / "m3_base_books.parquet")
books = {c: bdf[c].dropna() for c in bdf.columns}

results = []
def rec(label, net):
    results.append(J.metrics_dict(label, net))
    print(J.summary_line(label, net))

print("=== base books ===")
for n, s in books.items():
    rec(f"base:{n}", s)

print("\n=== (a) relative-strength rotation small<->large (always invested) ===")
for ma in (60, 120, 200):
    small_rel = J.index_ratio_signal("000852.SH", "000300.SH", IS_START, IS_END, ma_window=ma)
    idx = small_rel.index
    sr = small_rel.reindex(idx).ffill().fillna(0.0)
    for agg in ["smallQV", "smallLV", "smallMom"]:
        if agg not in books:
            continue
        choice = pd.Series("largeVL", index=idx)
        choice[sr > 0] = agg                       # small relatively strong -> small book
        net = J.combine_regime({agg: books[agg], "largeVL": books["largeVL"]},
                               choice, switch_cost=0.0030)
        rec(f"M3b relstr[{agg}<->largeVL] MA{ma}", net)

print("\n=== (b) clean broad de-risk on best book (largeVL) ===")
for ma in (120, 200):
    trend = ov.trend_exposure("000300.SH", ma, IS_START, IS_END)  # 1 when 300>MA else 0
    idx = books["largeVL"].index.union(trend.index)
    t = trend.reindex(idx).ffill().fillna(1.0)
    choice = pd.Series("cash", index=idx)
    choice[t > 0] = "largeVL"
    net = J.combine_regime({"largeVL": books["largeVL"]}, choice, switch_cost=0.0030)
    rec(f"M3b largeVL+broadtrend MA{ma}", net)

print("\n=== yearly breakdown ===")
for r in results:
    ys = "  ".join(f"{y}:{v:+.1%}" for y, v in sorted(r["yearly"].items()))
    print(f"{r['label']:34s} {ys}")

with open(J.OUT / "m3b_results.json", "w", encoding="utf-8") as f:
    json.dump([{k: v for k, v in r.items() if not k.startswith("_")} for r in results],
              f, indent=2, default=float)
print(f"\nSaved -> {J.OUT/'m3b_results.json'}")
