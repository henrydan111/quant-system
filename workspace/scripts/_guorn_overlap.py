"""Generic 果仁 selection-faithfulness check: my schedule top-N ∩ 果仁 held names / 果仁, by year.

Reads the 果仁 xlsx sheet `各阶段持仓详单` (per-period holdings: 开始日期 + 股票代码) and the local
schedule JSON, and reports yearly + overall name overlap. High overlap (~#59's 36%) => selection faithful
=> any return gap is execution (turnover/churn/cost); low overlap => selection issue (factor/composite/mask).

Reusable across the 成长 cluster. Run: venv/Scripts/python.exe workspace/scripts/_guorn_overlap.py 02
"""
import argparse, json, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8")
OUT = ROOT / "workspace" / "outputs" / "guorn_parity"

# book -> (xlsx filename, schedule json, top-N tiers to score)
BOOKS = {
    "01": ("01_sm_01_成长动量.xlsx", "verify01_schedule.json", (10, 20)),
    "02": ("05_sm_01_成长_v1.xlsx", "verify02_schedule.json", (10, 20)),
    "06": ("06_sm_01_成长高贝塔@TMT_v1.xlsx", "verify06_schedule.json", (7, 15)),
}


def _qc(code):
    s = str(code).split(".")[0].zfill(6)
    return s + ("_SH" if s[0] in "69" else "_SZ")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("book", choices=sorted(BOOKS))
    args = ap.parse_args()
    xlsx_name, sched_name, topns = BOOKS[args.book]
    XLSX = ROOT / "Knowledge" / "果仁回测结果" / xlsx_name
    sched = {pd.Timestamp(k): [c.replace(".", "_") for c in v]
             for k, v in json.loads((OUT / sched_name).read_text(encoding="utf-8")).items()}
    h = pd.read_excel(XLSX, sheet_name="各阶段持仓详单", header=0)
    h["开始日期"] = pd.to_datetime(h["开始日期"]); h["qc"] = h["股票代码"].map(_qc)
    g_by_date = {d: set(grp["qc"]) for d, grp in h.groupby("开始日期")}

    rows = []
    for d, gset in g_by_date.items():
        mine = sched.get(pd.Timestamp(d))
        if not mine:
            continue
        for topn in topns:
            rows.append((d.year, topn, len(set(mine[:topn]) & gset), len(gset)))
    df = pd.DataFrame(rows, columns=["yr", "topn", "inter", "g"])
    print(f"=== #{args.book} holdings overlap (my topN ∩ 果仁 / 果仁) — {len(g_by_date)} 果仁 periods ===")
    for topn in topns:
        sub = df[df["topn"] == topn]
        if sub.empty:
            continue
        by = sub.groupby("yr").agg(periods=("inter", "size"), ov=("inter", "sum"), g=("g", "sum"))
        by["pct"] = (by["ov"] / by["g"]).round(3)
        tot = sub["inter"].sum() / max(sub["g"].sum(), 1)
        print(f"\n--- my top{topn} ---")
        print(by[["periods", "pct"]].to_string())
        print(f"OVERALL top{topn} overlap = {tot:.1%}")


if __name__ == "__main__":
    main()
