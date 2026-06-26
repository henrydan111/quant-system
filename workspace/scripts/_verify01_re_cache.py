"""Reverse-engineer ILLIQ + CoreProfitQGr vs 果仁's exported values (cache-only, fast).
ILLIQ: dump my-vs-theirs sample pairs + ratio (132729x => unit bug). CoreProfitQGr: 果仁 value
distribution (find their clip) + my outliers (near-zero-denominator explosions)."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "workspace" / "research" / "long_only_50cagr"))
sys.stdout.reconfigure(encoding="utf-8")
import research_utils as ru  # noqa: E402

CACHE = ROOT / "workspace" / "outputs" / "guorn_parity" / "verify01_cache"
XLSX = ROOT / "Knowledge" / "果仁回测结果" / "01_sm_01_成长动量.xlsx"


def _qcode(code):
    s = str(code).split(".")[0].zfill(6)
    return s + ("_SH" if s[0] in "69" else "_SZ")


def _lookup(fr, sub):
    out = []
    for pday, grp in sub.groupby("pday"):
        if pday in fr.index:
            out.append(grp["qc"].map(fr.loc[pday]).set_axis(grp.index))
        else:
            out.append(pd.Series(np.nan, index=grp.index))
    return pd.concat(out)


h = pd.read_excel(XLSX, sheet_name="各阶段持仓详单", header=0)
h["开始日期"] = pd.to_datetime(h["开始日期"]); h["qc"] = h["股票代码"].map(_qcode)
cal = ru.trading_calendar()
pos = cal.searchsorted(h["开始日期"].values)
h["pday"] = [cal[p - 1] if p > 0 else pd.NaT for p in pos]
h = h.dropna(subset=["pday"])

# ---- ILLIQ ----
illiq = pd.read_parquet(CACHE / "f_ILLIQ.parquet")
gcol = "股价振幅%当日成交额10日"
sub = h[["pday", "qc", gcol]].dropna(); sub = sub[sub["qc"].isin(illiq.columns)]
sub = sub.assign(mine=_lookup(illiq, sub))
sub["theirs"] = pd.to_numeric(sub[gcol], errors="coerce")
ok = sub.dropna(subset=["mine", "theirs"])
ok = ok[ok["theirs"].abs() > 0]
print("=== ILLIQ: my cached vs 果仁 (15 samples) ===")
print(ok[["mine", "theirs"]].head(15).assign(ratio=ok["mine"] / ok["theirs"]).to_string())
print(f"\n  median ratio mine/theirs = {(ok['mine']/ok['theirs']).median():.1f}")
print(f"  mine sign: +{(ok['mine']>0).mean():.0%} / theirs sign: +{(ok['theirs']>0).mean():.0%}")
print(f"  theirs range: {ok['theirs'].min():.3e} .. {ok['theirs'].median():.3e} .. {ok['theirs'].max():.3e}")

# ---- CoreProfitQGr ----
cpg = pd.read_parquet(CACHE / "f_CoreProfitQGr.parquet")
gcol = "CoreProfitQGr%PY"
sub = h[["pday", "qc", gcol]].dropna(); sub = sub[sub["qc"].isin(cpg.columns)]
sub = sub.assign(mine=_lookup(cpg, sub))
sub["theirs"] = pd.to_numeric(sub[gcol], errors="coerce")
ok = sub.dropna(subset=["mine", "theirs"])
qs = [0.0, 0.001, 0.01, 0.5, 0.99, 0.999, 1.0]
print("\n=== CoreProfitQGr: distributions (find 果仁's clip) ===")
print("  quantile   果仁(theirs)        mine")
for q in qs:
    print(f"  {q:<8}  {ok['theirs'].quantile(q):>14.3f}  {ok['mine'].quantile(q):>14.3f}")
big = ok[ok["mine"].abs() > 50]
print(f"\n  |mine|>50 outliers: {len(big)} ({len(big)/len(ok):.1%}); of those 果仁|.|>50: {(big['theirs'].abs()>50).mean():.0%}")
print(big[["mine", "theirs"]].head(10).to_string())
