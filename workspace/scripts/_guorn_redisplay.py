"""Re-display a 果仁 verify book's yearly LOCAL-vs-果仁 table from the SAVED net (no backtest re-run).

Used after the _read_guorn_yearly decimal-parse fix (果仁 年度收益统计 stores DECIMALS: 0.8445=84%,
3.4035=340% — the old `/100 if abs(v)>3` heuristic wrongly divided >300% years). Reads verifyNN_net.parquet
+ the 果仁 xlsx and prints the corrected per-year comparison. Run: _guorn_redisplay.py 02
"""
import argparse, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "workspace" / "research" / "long_only_50cagr"))
sys.stdout.reconfigure(encoding="utf-8")
import research_utils as ru   # noqa: E402

OUT = ROOT / "workspace" / "outputs" / "guorn_parity"
BOOKS = {
    "01": ("01_sm_01_成长动量.xlsx", "verify01_net.parquet",
           dict(annual=0.5721, sharpe=1.68, mdd=0.4787, vol=0.3168), "sm_01_成长动量"),
    "02": ("05_sm_01_成长_v1.xlsx", "verify02_net.parquet",
           dict(annual=0.5820, sharpe=1.58, mdd=0.5004, vol=0.3438), "sm_01_成长_v1 (业绩快报 OMITTED)"),
    "06": ("06_sm_01_成长高贝塔@TMT_v1.xlsx", "verify06_net.parquet",
           dict(annual=0.6032, sharpe=1.44, mdd=0.5188, vol=0.392), "sm_01_成长高贝塔@TMT_v1 (预期营收+快报 OMITTED)"),
    "04": ("09_sm_GARP_illiq.xlsx", "verify04_net.parquet",
           dict(annual=0.4959, sharpe=1.54, mdd=0.4245, vol=0.296), "sm_GARP_illiq (12/23 weight OMITTED)"),
    "15": ("44_成长_双创_GARP@周期_v2.xlsx", "verify15_net.parquet",
           dict(annual=0.4339, sharpe=1.13, mdd=0.4655, vol=0.3492), "成长_双创_GARP@周期_v2 (12/24 weight OMITTED)"),
    "05": ("10_sm_双创研发强度_v1.xlsx", "verify05_net.parquet",
           dict(annual=0.6267, sharpe=1.54, mdd=0.6095, vol=0.3805), "sm_双创研发强度_v1 (9/16 weight OMITTED)"),
}


def gy_corrected(xlsx):
    df = pd.read_excel(xlsx, sheet_name="年度收益统计", header=0)
    out = {}
    for _, r in df.iterrows():
        try:
            y = int(str(r.iloc[0])[:4])
        except Exception:
            continue
        v = pd.to_numeric(r.iloc[1], errors="coerce")
        if pd.notna(v):
            out[y] = float(v)   # decimals; never /100
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("book", choices=sorted(BOOKS))
    a = ap.parse_args()
    xlsx_name, net_name, GR, label = BOOKS[a.book]
    net = pd.read_parquet(OUT / net_name)["net"].astype(float)
    net.index = pd.to_datetime(net.index)
    m = ru.goal_metrics(net); m["sharpe_rf4"] = ru.sharpe(net, rf=0.04)
    yr = net.groupby(net.index.year).apply(lambda r: (1 + r).prod() - 1)
    gy = gy_corrected(ROOT / "Knowledge" / "果仁回测结果" / xlsx_name)
    print(f"=== #{a.book} {label} — CORRECTED yearly (果仁 decimals) ===")
    print(f"  LOCAL  annual≈{m['cagr']:+.2%}  Sharpe(rf4%)={m['sharpe_rf4']:.2f}  MDD={m['mdd']:+.2%}  vol={m['ann_vol']:.2%}")
    print(f"  果仁   annual={GR['annual']:+.2%}  Sharpe={GR['sharpe']:.2f}  MDD={-GR['mdd']:+.2%}  vol={GR['vol']:.2%}")
    print("  year     LOCAL      果仁     diff")
    for y in sorted(yr.index):
        lv = float(yr[y]); g = gy.get(int(y))
        gt = f"{g:+8.1%}" if g is not None else "   n/a  "
        dt = f"{lv - g:+7.1%}" if g is not None else ""
        print(f"  {int(y)}   {lv:+8.1%}  {gt}  {dt}")


if __name__ == "__main__":
    main()
