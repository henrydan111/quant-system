"""Decisive selection test for #1: my top-10 (schedule) ∩ 果仁 held names / 果仁, by year.
High overlap (~#59's 36%) => selection faithful => the 17pp undershoot is EXECUTION (daily turnover/
churn/cost). Low overlap => selection broken (factor/composite). Uses verify01_schedule.json + the
果仁 holdings sheet."""
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8")
OUT = ROOT / "workspace" / "outputs" / "guorn_parity"
XLSX = ROOT / "Knowledge" / "果仁回测结果" / "01_sm_01_成长动量.xlsx"


def _qc(code):
    s = str(code).split(".")[0].zfill(6)
    return s + ("_SH" if s[0] in "69" else "_SZ")


sched = {pd.Timestamp(k): [c.replace(".", "_") for c in v]
         for k, v in json.loads((OUT / "verify01_schedule.json").read_text(encoding="utf-8")).items()}
h = pd.read_excel(XLSX, sheet_name="各阶段持仓详单", header=0)
h["开始日期"] = pd.to_datetime(h["开始日期"]); h["qc"] = h["股票代码"].map(_qc)
g_by_date = {d: set(grp["qc"]) for d, grp in h.groupby("开始日期")}

rows = []
for d, gset in g_by_date.items():
    mine = sched.get(pd.Timestamp(d))
    if not mine:
        continue
    for topn in (10, 20):
        mset = set(mine[:topn])
        rows.append((d.year, topn, len(mset & gset), len(gset)))
df = pd.DataFrame(rows, columns=["yr", "topn", "inter", "g"])
print("=== #1 holdings overlap (my topN ∩ 果仁 / 果仁) ===")
for topn in (10, 20):
    sub = df[df["topn"] == topn]
    by = sub.groupby("yr").agg(periods=("inter", "size"), ov=("inter", "sum"), g=("g", "sum"))
    by["pct"] = (by["ov"] / by["g"]).round(3)
    tot = sub["inter"].sum() / sub["g"].sum()
    print(f"\n--- my top{topn} ---")
    print(by[["periods", "pct"]].to_string())
    print(f"OVERALL top{topn} overlap = {tot:.1%}")
