"""Fix the all-NaN industry frame in the 果仁 verify01_cache (used by #1/#2/#6 mktcap_ind w=2 term).

ROOT CAUSE: guorn_verify_01_growth.build pulled `$sw2021_l1` from the provider, but SW industry is NOT a
Qlib feature bin — it lives in data/universe/industry_sw2021_members/. So the read returned all-NaN, and
`astype("str")` turned it into the literal string "nan" → groupby("nan") forms ONE group → the 一级行业内
(within-L1) market-cap term silently became a SECOND GLOBAL market-cap rank (magnitude w=5 preserved, but
the industry-relative dimension lost). This characterizes that exactly, then rebuilds industry.parquet with
the canonical PIT-safe resolver provider_metadata.build_industry_series_asof (time-varying L1 as-of each day).

NON-FORMAL parity tooling. Run: venv/Scripts/python.exe workspace/scripts/_fix_industry_cache.py
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
from src.data_infra.provider_metadata import build_industry_series_asof   # noqa: E402

CACHE = ROOT / "workspace" / "outputs" / "guorn_parity" / "verify01_cache"


def _score(row: pd.Series, indrow: pd.Series, ascending: bool) -> pd.Series:
    """Reproduce _composite_row's per-factor 排名分 for the WITHIN-GROUP market-cap term."""
    rnk = row.groupby(indrow).rank(method="min", ascending=ascending, na_option="bottom")
    gN = indrow.map(indrow.value_counts())
    return (gN - rnk + 1) / gN * 100.0


def _global_score(row: pd.Series, ascending: bool) -> pd.Series:
    rnk = row.rank(method="min", ascending=ascending, na_option="bottom")
    N = len(row)
    return (N - rnk + 1) / N * 100.0


def main():
    close = pd.read_parquet(CACHE / "e_close_raw.parquet")     # datetime index × instrument cols
    mktcap = pd.read_parquet(CACHE / "f_mktcap_x.parquet")
    grid_dates = close.index
    insts = list(close.columns)
    print(f"grid {len(grid_dates)} dates × {len(insts)} insts", flush=True)

    old = pd.read_parquet(CACHE / "industry.parquet")
    # --- characterize the CURRENT (broken) behavior on 3 sample days ---
    sample = [grid_dates[len(grid_dates) // 4], grid_dates[len(grid_dates) // 2], grid_dates[-30]]
    print("\n[characterize] current mktcap_ind (all-'nan' industry) vs a pure GLOBAL market-cap rank:")
    for d in sample:
        cur_ind = old.loc[d]                                   # all the string 'nan'
        mc = mktcap.loc[d]
        cur = _score(mc, cur_ind, ascending=True)              # 从小到大 (small better)
        glob = _global_score(mc, ascending=True)
        corr = cur.corr(glob)
        print(f"  {d.date()}  corr(mktcap_ind_current, global_rank) = {corr:.4f}  (≈1.0 ⇒ it WAS global)")

    # --- build the PROPER time-varying L1 industry frame (yearly chunks; resolver is vectorized merge_asof) ---
    print("\n[build] resolving SW2021 L1 as-of each grid day via build_industry_series_asof ...", flush=True)
    frames = []
    for yr, sub in close.groupby(close.index.year):
        mi = pd.MultiIndex.from_product([sub.index, insts], names=["datetime", "instrument"])
        ser = build_industry_series_asof(mi, level="L1")
        fr = ser.unstack(level="instrument").reindex(columns=insts)
        frames.append(fr)
        print(f"    {yr}: cov={fr.notna().mean().mean():.3f}", flush=True)
    ind = pd.concat(frames).sort_index().reindex(grid_dates).reindex(columns=insts)

    flat = ind.values.ravel()
    dist = pd.unique(flat[pd.notna(flat)])
    print(f"\n[build] distinct L1 codes = {len(dist)} ; overall coverage = {ind.notna().mean().mean():.3f}")

    # --- characterize the FIXED behavior on the same days (should now DIFFER from global) ---
    print("\n[characterize] proper within-L1 mktcap_ind vs global rank (corr<1 ⇒ industry-relativity restored):")
    for d in sample:
        mc = mktcap.loc[d]
        fixed = _score(mc, ind.loc[d], ascending=True)
        glob = _global_score(mc, ascending=True)
        print(f"  {d.date()}  corr(mktcap_ind_fixed, global_rank) = {fixed.corr(glob):.4f}  "
              f"(classified frac {ind.loc[d].notna().mean():.3f})")

    bak = CACHE / "industry_allnan_backup.parquet"
    if not bak.exists():
        old.to_parquet(bak)
        print(f"\n[save] backed up old all-NaN industry → {bak.name}")
    ind.astype("str").to_parquet(CACHE / "industry.parquet")
    print(f"[save] wrote proper industry.parquet  ({ind.shape[0]}×{ind.shape[1]})")
    print("\nNON-FORMAL — re-run #1/#2 --schedule --run to measure the industry-relativity impact.")


if __name__ == "__main__":
    main()
