# -*- coding: utf-8 -*-
"""Parse the 收益统计 sheet from each downloaded guorn backtest xlsx (01..65)
into one consolidated comparison CSV — the benchmark for local replication.
"""
import re
import csv
from pathlib import Path
import openpyxl

DL = Path(r"E:\量化系统\Knowledge\果仁回测结果")
OUT = DL / "_汇总_收益统计.csv"
OUT2 = Path(r"E:\量化系统\workspace\research\idea_sourcing\guorn\backtest_summary.csv")

def pct(v):
    try:
        return round(float(v) * 100, 2)
    except (TypeError, ValueError):
        return ""

def num(v):
    try:
        return round(float(v), 3)
    except (TypeError, ValueError):
        return ""

rows = []
files = sorted(DL.glob("[0-9][0-9]_*.xlsx"))
for p in files:
    m = re.match(r"^(\d+)_(.+)\.xlsx$", p.name)
    nn, name = m.group(1), m.group(2)
    wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
    ws = wb["收益统计"]
    data = [list(r) for r in ws.iter_rows(min_row=1, max_row=5, values_only=True)]
    wb.close()
    # row0 header, row1 本策略, row2 benchmark, row3 相对收益
    strat = data[1] if len(data) > 1 else [None]*9
    bench = data[2] if len(data) > 2 else [None]*9
    rel = data[3] if len(data) > 3 else [None]*9
    rows.append({
        "序号": nn, "策略": name,
        "总收益%": pct(strat[1]), "年化收益%": pct(strat[2]), "夏普": num(strat[3]),
        "最大回撤%": pct(strat[4]), "波动率%": pct(strat[5]), "信息比率": num(strat[6]),
        "Beta": num(strat[7]), "Alpha%": pct(strat[8]),
        "基准": (bench[0] or ""), "基准年化%": pct(bench[2]), "基准回撤%": pct(bench[4]),
        "超额年化%": pct(rel[2]),
    })

cols = ["序号","策略","总收益%","年化收益%","夏普","最大回撤%","波动率%","信息比率","Beta","Alpha%","基准","基准年化%","基准回撤%","超额年化%"]
for path in (OUT, OUT2):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

print(f"wrote {len(rows)} rows -> {OUT.name} and {OUT2}")
# quick sanity: print a few as ascii-safe
for r in rows[:3] + rows[-2:]:
    print(r["序号"], "ann%=", r["年化收益%"], "sharpe=", r["夏普"], "mdd%=", r["最大回撤%"], "bench_ann%=", r["基准年化%"])
empties = [r["序号"] for r in rows if r["年化收益%"] == ""]
print("rows with no 年化:", empties)
