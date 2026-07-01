# -*- coding: utf-8 -*-
"""Spot-check: local xlsx 收益统计 (本策略) vs values read live off guorn web端."""
import openpyxl
from pathlib import Path

DL = Path(r"E:\量化系统\Knowledge\果仁回测结果")

# web readings captured live (总收益%, 年化%, 夏普, 最大回撤%, 波动率%)
web = {
    "01_sm_01_成长动量":            (27936.96, 57.21, 1.68, 47.87, 31.68),
    "12_sm_value":                  (88877.52, 72.49, 2.15, 34.90, 31.90),
    "18_sm_BJ_纯市值_v1":           (4008.34, 160.05, 2.51, 38.19, 62.13),
    "40_index_纳指ETF":             (868.67,  20.00, 0.74, 28.57, 21.62),
    "63_Comp_FCF":                  (3840.29, 34.30, 1.12, 46.60, 27.14),
    "16_sm_noc_纯市值正盈利_v4":     (34803.22, 60.00, 1.71, 35.49, 32.82),  # @千分之三
}

def local_row(fn):
    wb = openpyxl.load_workbook(DL / (fn + ".xlsx"), read_only=True, data_only=True)
    s = [list(r) for r in wb.worksheets[0].iter_rows(min_row=2, max_row=2, values_only=True)][0]
    wb.close()
    # s[1]=总收益(ratio) s[2]=年化 s[3]=夏普 s[4]=回撤 s[5]=波动
    return (round(s[1]*100, 2), round(s[2]*100, 2), round(float(s[3]), 2), round(s[4]*100, 2), round(s[5]*100, 2))

labels = ["总收益%", "年化%", "夏普", "回撤%", "波动%"]
allok = True
for fn, w in web.items():
    loc = local_row(fn)
    ok = all(abs(a - b) < 0.01 for a, b in zip(loc, w))
    allok &= ok
    print(("OK  " if ok else "DIFF") + "  " + fn)
    print("     web  :", dict(zip(labels, w)))
    print("     local:", dict(zip(labels, loc)))
    if not ok:
        print("     >>> mismatch:", [(labels[i], w[i], loc[i]) for i in range(5) if abs(loc[i]-w[i]) >= 0.01])
print()
print("ALL 6 SPOT-CHECKS MATCH" if allok else "SOME MISMATCH")
