import sys
from pathlib import Path
import pandas as pd
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
xlsx = ROOT / "Knowledge" / "果仁回测结果" / "11_sm_纯市值01.xlsx"
h = pd.read_excel(xlsx, sheet_name="各阶段持仓详单", header=0)
h.columns = [str(c).strip() for c in h.columns]
code = h["股票代码"].astype(str).str.extract(r"(\d{6})")[0].dropna()
h = h.loc[code.index]
h["code6"] = code
h["start"] = pd.to_datetime(h["开始日期"])
h["px3"] = h["code6"].str[:3]


def board(c):
    if c[:3] in ("688", "689"): return "科创板"
    if c[:3] in ("300", "301"): return "创业板"
    if c[0] in ("4", "8") or c[:3] == "920": return "北证/BSE"
    return "沪深主板"


h["board"] = h["code6"].map(board)
print("=== board distribution of 果仁 holdings (all periods) ===")
print(h["board"].value_counts().to_string())
print(f"\ntotal holding-rows={len(h)}  date range {h['start'].min().date()}..{h['start'].max().date()}")
bse = h[h["board"] == "北证/BSE"]
print(f"\n北证/BSE holdings: {len(bse)} rows")
if len(bse):
    print(bse[["start", "code6", "股票名"]].head(15).to_string())
print("\n=== holdings in 2022 (the divergence year): board mix ===")
h22 = h[(h["start"] >= "2022-01-01") & (h["start"] < "2023-01-01")]
print(h22["board"].value_counts().to_string())
print(f"2022 holding-rows={len(h22)}  unique stocks={h22['code6'].nunique()}")
print(f"2022 avg 总市值(亿)={pd.to_numeric(h22['总市值(亿)'],errors='coerce').mean():.1f}  "
      f"avg 5日成交额(亿)={pd.to_numeric(h22['5日平均成交额(亿)'],errors='coerce').mean():.3f}")
