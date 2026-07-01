"""Answer "和果仁相比，本地因子排序能否完全匹配?" with data — for the 3 web-validated factors, measure EXACT
rank agreement (not just Spearman): identical-rank-position %, Kendall tau, top-K selection overlap, and the
果仁-side display ties that make a bit-identical ordering structurally impossible. NON-FORMAL."""
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "workspace" / "scripts"))
import guorn_factor_parity as gfp  # noqa: E402
KV = ROOT / "Knowledge" / "果仁验证因子"

CASES = [
    ("总市值", "果仁_20251231_排除ST排除科创_排名-总市值降序.xlsx", "2025-12-31", "$total_mv", 8, 1.0, 1),
    ("评级机构数", "果仁_20251231_排除ST排除科创_排名-评级机构数.xlsx", "2025-12-31", "$report_rc__n_active_orgs", 8, 1.0, 1),
    ("股息率TTM", "果仁_20251231_排除ST排除科创_排名-股息率TTM.xlsx", "2025-12-31", "$dv_ttm", 8, 100.0, 1),
]
TOPKS = (5, 10, 20)   # factors ultimately select a SMALL top-K → assess the match at top-5/10/20


def main():
    print(f"{'factor':12} {'n':>5} {'Spear':>6} {'Kend':>6} {'exact':>6} " + " ".join(f"{'top'+str(k):>6}" for k in TOPKS) + f" {'果仁-ties':>8}")
    for name, xlsx, date, expr, gcol, gscale, lag in CASES:
        g = gfp.load_guorn_export(KV / xlsx, None, gcol)
        lv = gfp.load_local_factor(expr, date, lag, set(g.index))
        m = g.join(lv, how="inner").dropna()
        m["gval"] = m["gval"] * gscale
        n = len(m)
        # descending ranks (higher value = rank 1, like 果仁's 从大到小 selection order)
        gr = m["gval"].rank(method="first", ascending=False).astype(int)
        lr = m["lval"].rank(method="first", ascending=False).astype(int)
        sp = m["gval"].corr(m["lval"], method="spearman")
        kd = m["gval"].corr(m["lval"], method="kendall")
        exact = float((gr == lr).mean())
        n_tie = n - int(m["gval"].round(6).nunique())   # 果仁-side display ties (unbreakable)

        def topk(k):
            k = min(k, n)
            gt = set(m.sort_values("gval", ascending=False).head(k).index)
            lt = set(m.sort_values("lval", ascending=False).head(k).index)
            return len(gt & lt) / k
        tk = " ".join(f"{topk(k):6.1%}" for k in TOPKS)
        print(f"{name:12} {n:5d} {sp:6.3f} {kd:6.3f} {exact:6.1%} {tk} {n_tie:8d}")


if __name__ == "__main__":
    main()
