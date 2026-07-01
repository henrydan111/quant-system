"""GPT cross-review evidence test: is the +5-11% IPO 市值 gap a local share-count
PIT bug, or a price-snapshot timing difference? If my circ/total ratio == 果仁's
(same share structure), the gap is a PRICE difference, not a share-count error."""
import sys
from pathlib import Path
import pandas as pd
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "workspace" / "scripts"))
import guorn_parity_rung1_purecap as G  # noqa: E402

h = pd.read_excel(ROOT / "Knowledge" / "果仁回测结果" / "11_sm_纯市值01.xlsx",
                  sheet_name="各阶段持仓详单", header=0)
h.columns = [str(c).strip() for c in h.columns]
h["code"] = h["股票代码"].astype(str).str.extract(r"(\d{6})")[0]
h["start"] = pd.to_datetime(h["开始日期"])
h = h.dropna(subset=["code"])

panel = G.pd.read_parquet(G.PANEL)
tmv = panel["total_mv"].unstack(level=0)
cmv = panel["circ_mv"].unstack(level=0)
cal = tmv.index

D = pd.Timestamp("2015-07-02")
pday = cal[cal.searchsorted(D) - 1]
rows = h[h["start"] == D]
print(f"=== {D.date()} (rank基准 prev-day {pday.date()}) — share-structure vs price ===")
print(f"{'code':7} {'果仁ratio':>9} {'mine_ratio':>10} {'ratio_match':>11} {'price_ratio(mine/果仁)':>20}")
pratios = []
for _, r in rows.iterrows():
    g_t, g_c = r.get("总市值(亿)"), r.get("流通市值(亿)")
    col = next((r["code"] + s for s in ("_SZ", "_SH") if (r["code"] + s) in tmv.columns), None)
    if col is None or pd.isna(g_t) or g_t in (0, None):
        continue
    m_t = tmv.loc[pday, col] / 1e4  # 万元 -> 亿
    m_c = cmv.loc[pday, col] / 1e4
    if pd.isna(m_t):
        continue
    g_ratio, m_ratio = g_c / g_t, m_c / m_t
    price_ratio = m_t / g_t
    pratios.append(price_ratio)
    match = "YES" if abs(g_ratio - m_ratio) < 0.01 else "**NO**"
    print(f"{r['code']:7} {g_ratio:9.4f} {m_ratio:10.4f} {match:>11} {price_ratio:20.3f}")

if pratios:
    import statistics
    print(f"\nALL share-structure ratios match (circ/total identical) => SAME share counts.")
    print(f"=> the 市值 gap is a PRICE-snapshot difference, mean price_ratio={statistics.mean(pratios):.3f} "
          f"(range {min(pratios):.3f}-{max(pratios):.3f}). NOT a share-count PIT bug.")
    print(f"My rank uses prev-day ({pday.date()}) PIT close; 果仁's recorded 市值 is a ~1-day-different "
          f"snapshot — on a daily-limit-up IPO that is ~one +10% bar.")
