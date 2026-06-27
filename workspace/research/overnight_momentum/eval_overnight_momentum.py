"""Sandbox test of the overnight-momentum factor (隔夜动量因子).

Factor logic (user spec):
    Over the past 60 trading days, EXCLUDING limit-up (涨停) days, accumulate ONLY
    the overnight return (yesterday-close -> today-open gap).

This is a SANDBOX factor test (no catalog registration, no formal orchestrator run).
It computes the factor via the sanctioned compute_factors() path (Qlib expression
engine through qlib_windowed_features), then reports the standard factor-evaluation
suite (IC / RankIC / ICIR across horizons, decile spread + monotonicity, long-short
Sharpe, top-bucket turnover, yearly stability, and the size confound).

PIT safety: every $field is wrapped in Ref(..., >=1). Factor[t] uses data through
t-1; the forward return realizes from t -> t+h. No lookahead.

Price basis:
  - overnight gap uses ADJUSTED prices (cross-day comparison): adj_open[s]/adj_close[s-1]-1
  - limit-up detection uses RAW same-day prices: close[s] >= up_limit[s]
    (published Tushare $up_limit auto-adapts to +10% / +20% board / +5% ST regimes)
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(r"E:\量化系统")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.alpha_research.factor_library.operators import forward_return
from src.research_orchestrator.qlib_windowed_features import qlib_windowed_features
from src.research_orchestrator.cache_manifest import CacheContext
from src.alpha_research.factor_eval.ic_analysis import compute_ic_series, compute_ic_summary
from src.alpha_research.factor_eval.quantile_analysis import (
    compute_quantile_returns,
    compute_quantile_summary,
    compute_long_short_returns,
    test_monotonicity,
)
from src.alpha_research.factor_eval.unified_eval import one_way_turnover

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("overnight_mom")

OUT_DIR = PROJECT_ROOT / "workspace" / "outputs" / "overnight_momentum"
OUT_DIR.mkdir(parents=True, exist_ok=True)

START = "2016-01-01"
END = "2026-02-27"          # frozen calendar end
WINDOW = 60                  # lookback in trading days
HORIZONS = [1, 5, 10, 20]    # forward-return horizons to scan

# ── factor expressions ───────────────────────────────────────────────────────
# overnight gap for the lagged day s=t-1:  adj_open[t-1] / adj_close[t-2] - 1
ON_RET = "Ref(($open * $adj_factor), 1) / Ref(($close * $adj_factor), 2) - 1"
# NOT limit-up on day t-1 (raw, same day):  close[t-1] < up_limit[t-1]
NOT_LIMIT = "Ref($close, 1) < Ref($up_limit, 1)"

CATALOG = {
    # PRIMARY — the user's factor: cumulative 60d overnight return, limit-up days zeroed
    "on_mom_excl60": f"Sum(If({NOT_LIMIT}, {ON_RET}, 0), {WINDOW})",
    # BASELINE — no limit-up exclusion (to isolate the exclusion's marginal value)
    "on_mom_raw60": f"Sum({ON_RET}, {WINDOW})",
    # MEAN variant — average overnight return over INCLUDED (non-limit-up) days only
    "on_mom_excl_avg60": (
        f"Sum(If({NOT_LIMIT}, {ON_RET}, 0), {WINDOW}) "
        f"/ Sum(If({NOT_LIMIT}, 1, 0), {WINDOW})"
    ),
    # size confound — lagged log market cap (NOT a tradable factor; for correlation only)
    "size_ln": "Log(Ref($total_mv, 1))",
}

FACTOR_NAMES = ["on_mom_excl60", "on_mom_raw60", "on_mom_excl_avg60"]
PRIMARY = "on_mom_excl60"


def _clean(s: pd.Series) -> pd.Series:
    """inf -> NaN (the mean variant can divide by a tiny count)."""
    return s.replace([np.inf, -np.inf], np.nan)


def _load_hs_universe() -> list[str]:
    """沪深A股 instrument list: all_stocks minus 北交所 (_BJ) and index pseudo-codes.

    Indices (399xxx_SZ, 000xxx_SH) have no $up_limit bin -> a comparison against
    $up_limit hard-fails on a length-0 series. 北交所 (BJ) runs a separate ±30%
    limit regime, is tiny/illiquid, post-2021 only, and is excluded by standard
    A-share factor studies. Within SH/SZ the stk_limit bins exist for the whole
    2008-2026 span, so $up_limit aligns to $close (no length-0 mismatch).
    """
    path = PROJECT_ROOT / "data" / "qlib_data" / "instruments" / "all_stocks.txt"
    codes = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        code = line.split("\t")[0].strip()
        if code.endswith("_BJ"):
            continue
        if code.startswith("399") and code.endswith("_SZ"):   # SZ indices
            continue
        if code.startswith("000") and code.endswith("_SH"):   # SH indices (no 000xxx_SH stocks)
            continue
        codes.append(code)
    return sorted(set(codes))


def _compute(catalog: dict, instruments: list[str], start: str, end: str, horizons: list[int]):
    """Mirror operators.compute_factors but over an EXPLICIT instrument list.

    Uses the sanctioned qlib_windowed_features chokepoint (compute_factors itself
    just wraps it); sandbox stage, no ResearchAccessContext active. Returns
    (factors_df, fwd_df), both MultiIndex(datetime, instrument).
    """
    import qlib
    from qlib.config import REG_CN
    qlib.init(provider_uri=str(PROJECT_ROOT / "data" / "qlib_data"), region=REG_CN, kernels=1)
    fields, names = [], []
    for nm, expr in catalog.items():
        fields.append(expr)
        names.append(nm)
    for h in horizons:
        fields.append(forward_return(h))
        names.append(f"fwd_{h}d")
    log.info("qlib_windowed_features: %d instruments x %d fields", len(instruments), len(fields))
    df = qlib_windowed_features(instruments=instruments, fields=fields,
                                start_time=start, end_time=end,
                                cache_context=CacheContext(), stage="is_only")
    df.columns = names
    df = df.swaplevel().sort_index()
    fwd_cols = [c for c in df.columns if c.startswith("fwd_")]
    fac_cols = [c for c in df.columns if not c.startswith("fwd_")]
    return df[fac_cols], df[fwd_cols]


def main():
    universe = _load_hs_universe()
    fac_cache = OUT_DIR / f"panel_factors_{START}_{END}_w{WINDOW}.parquet"
    fwd_cache = OUT_DIR / f"panel_fwd_{START}_{END}.parquet"
    if fac_cache.exists() and fwd_cache.exists():
        log.info("loading cached panel: %s", fac_cache.name)
        factors_df = pd.read_parquet(fac_cache)
        fwd_df = pd.read_parquet(fwd_cache)
    else:
        log.info("Computing factors %s over %s..%s (window=%d), 沪深A股 n=%d",
                 list(CATALOG), START, END, WINDOW, len(universe))
        factors_df, fwd_df = _compute(CATALOG, universe, START, END, HORIZONS)
        factors_df.to_parquet(fac_cache)
        fwd_df.to_parquet(fwd_cache)
        log.info("cached panel -> %s, %s", fac_cache.name, fwd_cache.name)
    for c in FACTOR_NAMES + ["size_ln"]:
        factors_df[c] = _clean(factors_df[c])

    n_dates = factors_df.index.get_level_values(0).nunique()
    n_stocks = factors_df.index.get_level_values(1).nunique()
    log.info("panel: %d dates x %d stocks, %d rows", n_dates, n_stocks, len(factors_df))

    report: dict = {"window": WINDOW, "start": START, "end": END,
                    "n_dates": int(n_dates), "n_stocks": int(n_stocks),
                    "panel_rows": int(len(factors_df))}

    # ── coverage diagnostics (per year, non-null fraction) ───────────────────
    cov = {}
    yr = factors_df.index.get_level_values(0).year
    for c in FACTOR_NAMES:
        per_yr = factors_df[c].groupby(yr).apply(lambda s: float(s.notna().mean()))
        cov[c] = {int(k): round(v, 3) for k, v in per_yr.items()}
    report["coverage_by_year"] = cov
    log.info("coverage (overall non-null): %s",
             {c: round(float(factors_df[c].notna().mean()), 3) for c in FACTOR_NAMES})

    # ── IC / RankIC / ICIR across factors x horizons ─────────────────────────
    ic_table = {}
    for fac in FACTOR_NAMES:
        ic_table[fac] = {}
        for h in HORIZONS:
            ic = compute_ic_series(factors_df[fac], fwd_df[f"fwd_{h}d"], min_obs=30)
            summ = compute_ic_summary(ic)
            ic_table[fac][f"h{h}"] = {
                "mean_rank_ic": round(float(summ["mean_rank_ic"]), 4),
                "rank_icir": round(float(summ["rank_icir"]), 4),
                "mean_ic": round(float(summ["mean_ic"]), 4),
                "icir": round(float(summ["icir"]), 4),
                "ic_hit_rate": round(float(summ.get("ic_hit_rate", float("nan"))), 4),
                "n_days": int(summ["n_days"]),
            }
    report["ic"] = ic_table

    # ── primary factor: decile spread + monotonicity + long-short, per horizon ─
    qper = {}
    for h in HORIZONS:
        qdf = compute_quantile_returns(factors_df[PRIMARY], fwd_df[f"fwd_{h}d"],
                                       n_quantiles=10, min_obs=50)
        qsumm = compute_quantile_summary(qdf, annual_factor=252)
        mono = test_monotonicity(qsumm)
        ls = compute_long_short_returns(qdf)            # Q10 - Q1 daily series
        ls = ls.dropna()
        # non-overlapping rebalance at horizon h -> annualize daily LS by sqrt(252)
        ls_sharpe = float(ls.mean() / ls.std() * np.sqrt(252)) if ls.std() > 0 else float("nan")
        ann_by_q = {int(q): round(float(r["annualized_return"]), 4)
                    for q, r in qsumm.iterrows()} if not qsumm.empty else {}
        qper[f"h{h}"] = {
            "annualized_return_by_decile": ann_by_q,
            "monotonic_spearman": round(float(mono["spearman_corr"]), 4),
            "is_monotonic": bool(mono["is_monotonic"]),
            "direction": mono["direction"],
            "ls_q10_minus_q1_daily_mean": round(float(ls.mean()), 6),
            "ls_sharpe_ann": round(ls_sharpe, 3),
            "ls_n_days": int(len(ls)),
        }
    report["primary_quantile"] = qper

    # ── primary factor: top-decile (top 10%) one-way turnover at a few rebal freqs ─
    turn = {}
    for rb in [5, 10, 20]:
        t = one_way_turnover(factors_df[PRIMARY], rebalance_days=rb, top_q=0.1,
                             trading_days=252, min_names=5)
        turn[f"rebal_{rb}d"] = {
            "turnover_ann": round(float(t["turnover_ann"]), 3),
            "n_rebalances": int(t["n_rebalances_used"]),
        }
    report["primary_turnover_top10pct"] = turn

    # ── primary factor: yearly RankIC stability (h=10) ───────────────────────
    ic10 = compute_ic_series(factors_df[PRIMARY], fwd_df["fwd_10d"], min_obs=30)
    ric = ic10["RankIC"].dropna()
    yearly = ric.groupby(ric.index.year).agg(["mean", "std", "count"])
    report["primary_yearly_rankic_h10"] = {
        int(y): {"mean_rank_ic": round(float(r["mean"]), 4),
                 "rank_icir": round(float(r["mean"] / r["std"]), 4) if r["std"] > 0 else None,
                 "n_days": int(r["count"])}
        for y, r in yearly.iterrows()
    }

    # ── size confound: avg cross-sectional Spearman corr(primary, ln_mcap) ───
    df_sz = pd.DataFrame({"f": factors_df[PRIMARY], "sz": factors_df["size_ln"]}).dropna()
    if not df_sz.empty:
        corr_by_date = df_sz.groupby(level=0).apply(
            lambda g: g["f"].corr(g["sz"], method="spearman") if len(g) > 5 else np.nan)
        report["size_spearman_corr_mean"] = round(float(corr_by_date.dropna().mean()), 4)

    # ── persist + print ──────────────────────────────────────────────────────
    out = OUT_DIR / "overnight_momentum_eval.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("wrote %s", out)

    print("\n" + "=" * 78)
    print("OVERNIGHT MOMENTUM FACTOR — sandbox eval  (沪深A股 excl BJ, %s..%s)" % (START, END))
    print("=" * 78)
    print(f"panel: {n_dates} dates x {n_stocks} stocks")
    print(f"\nRankIC / RankICIR  (factor x horizon):")
    print(f"{'factor':<20}" + "".join(f"  h{h:<2} RankIC  ICIR " for h in HORIZONS))
    for fac in FACTOR_NAMES:
        row = f"{fac:<20}"
        for h in HORIZONS:
            c = ic_table[fac][f"h{h}"]
            row += f"  {c['mean_rank_ic']:+.3f} {c['rank_icir']:+.2f}"
        print(row)
    print(f"\nPRIMARY ({PRIMARY}) decile spread + LS Sharpe (Q10-Q1):")
    for h in HORIZONS:
        q = qper[f"h{h}"]
        print(f"  h{h:<2}: mono_spearman={q['monotonic_spearman']:+.2f} "
              f"dir={q['direction']:<10} LS_Sharpe={q['ls_sharpe_ann']:+.2f}")
    print(f"\nPRIMARY top-10% turnover (annualized): "
          + ", ".join(f"{k}={v['turnover_ann']:.1f}x" for k, v in turn.items()))
    print(f"size Spearman corr (primary vs ln_mcap): "
          f"{report.get('size_spearman_corr_mean')}")
    print("=" * 78)


if __name__ == "__main__":
    main()
