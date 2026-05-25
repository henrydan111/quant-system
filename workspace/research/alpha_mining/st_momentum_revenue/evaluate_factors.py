"""
Per-factor evaluation on the ST universe for the 6 factors used in the
mom + market_cap + revenue strategy.

Factors: total_mv, revenue_q, mom_20d, mom_60d, mom_120d, mom_250d.
Universe: ST stocks (st_stocks.txt range form).
Window:   2014-01-01 to 2026-02-20.

Per-factor outputs (using the standard factor_eval toolkit):
  - IC summary at the canonical 5d horizon (mean_ic, mean_rank_ic, icir,
    rank_icir, hit_rate, positive_pct)
  - IC by year (regime stability)
  - Quintile (Q1-Q5) annualized return + Sharpe + monotonicity test
  - Long-short Q5-Q1 annualized return / Sharpe
  - IC decay across horizons [1, 2, 3, 5, 10, 20, 40, 60, 120, 250]
  - Lag-1 cross-sectional rank autocorrelation (turnover proxy:
    higher = stickier = lower trade frequency)

Cross-factor: 6x6 correlation matrix on raw factor values + on cs ranks.

Run dir: workspace/outputs/st_factor_eval_<ts>/
"""

from __future__ import annotations

import json
import logging
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3].parent  # E:\量化系统
sys.path.insert(0, str(PROJECT_ROOT))

from src.alpha_research.factor_eval import (  # noqa: E402
    compute_ic_series,
    compute_ic_summary,
    compute_ic_by_year,
    compute_quantile_returns,
    compute_quantile_summary,
    compute_long_short_returns,
    test_monotonicity,
    compute_ic_decay,
    find_optimal_horizon,
    compute_factor_correlation,
)
from src.alpha_research.factor_library import operators as op  # noqa: E402

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("st_eval")

QLIB_DIR = str(PROJECT_ROOT / "data" / "qlib_data")
ST_FILE = PROJECT_ROOT / "data" / "qlib_data" / "instruments" / "st_stocks.txt"

START_DATE = "2014-01-01"
END_DATE = "2026-02-20"

DECAY_HORIZONS = [1, 2, 3, 5, 10, 20, 40, 60, 120, 250]

RUN_TS = time.strftime("%Y%m%d_%H%M%S")
OUT_DIR = PROJECT_ROOT / "workspace" / "outputs" / f"st_factor_eval_{RUN_TS}"
(OUT_DIR / "per_factor").mkdir(parents=True, exist_ok=True)


def parse_st_ranges(path: Path) -> dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]]:
    ranges: dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]] = defaultdict(list)
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split("\t")
        if len(parts) < 3:
            continue
        ranges[parts[0].upper()].append((pd.Timestamp(parts[1]), pd.Timestamp(parts[2])))
    return dict(ranges)


def build_st_mask(index: pd.MultiIndex,
                  st_ranges: dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]]) -> pd.Series:
    instr_level = index.get_level_values("instrument")
    date_level = index.get_level_values("datetime")
    out = np.zeros(len(index), dtype=bool)
    by_instr: dict[str, list[int]] = defaultdict(list)
    for i, code in enumerate(instr_level):
        by_instr[code].append(i)
    for code, idxs in by_instr.items():
        ranges = st_ranges.get(code)
        if not ranges:
            continue
        positions = np.asarray(idxs)
        dates = date_level[positions].values
        flag = np.zeros(len(positions), dtype=bool)
        for start, end in ranges:
            flag |= (dates >= np.datetime64(start)) & (dates <= np.datetime64(end))
        out[positions] = flag
    return pd.Series(out, index=index)


def lag1_rank_autocorr(factor: pd.Series) -> float:
    """Mean per-stock lag-1 autocorrelation of cross-sectional rank.
    Higher = stickier factor (less turnover when used as a sort key)."""
    cs_rank = factor.groupby(level="datetime").rank(pct=True)
    by_stock = cs_rank.groupby(level="instrument")
    corrs = by_stock.apply(lambda s: s.autocorr(lag=1) if s.notna().sum() >= 30 else np.nan)
    return float(corrs.dropna().mean())


def evaluate_factor(name: str, factor: pd.Series, fwd_5d: pd.Series,
                    adj_close: pd.Series, expected_sign: int) -> dict:
    log.info("Evaluating %s (expected_sign=%+d)", name, expected_sign)

    # IC summary at 5d
    ic_series = compute_ic_series(factor, fwd_5d, min_obs=30)
    ic_sum = compute_ic_summary(ic_series)

    # IC by year
    yearly = compute_ic_by_year(ic_series)

    # Quantile (5 buckets)
    qret = compute_quantile_returns(factor, fwd_5d, n_quantiles=5, min_obs=30)
    qsum = compute_quantile_summary(qret)
    mono = test_monotonicity(qsum)

    # Long-short Q5 - Q1 (always Q5-Q1; sign interpretation depends on expected_sign)
    ls = compute_long_short_returns(qret, long_q=5, short_q=1)
    if len(ls) > 0:
        ls_ann_ret = float(ls.mean() * 252 / 5)  # /5 because fwd_ret is 5d cumulative
        ls_ann_vol = float(ls.std() * np.sqrt(252))
        ls_sharpe = ls_ann_ret / ls_ann_vol if ls_ann_vol > 0 else 0.0
    else:
        ls_ann_ret = ls_ann_vol = ls_sharpe = 0.0

    # IC decay
    decay = compute_ic_decay(factor, adj_close, horizons=DECAY_HORIZONS, min_obs=30)
    decay_opt = find_optimal_horizon(decay)

    # Lag-1 rank autocorrelation (factor stickiness / turnover proxy)
    autocorr_1d = lag1_rank_autocorr(factor)

    # Compose result
    return {
        "name": name,
        "expected_sign": expected_sign,
        "ic_5d": ic_sum,
        "yearly_ic": yearly,
        "quantile_summary": qsum,
        "monotonicity": mono,
        "long_short_q5_q1": {
            "ann_ret": ls_ann_ret,
            "ann_vol": ls_ann_vol,
            "sharpe": ls_sharpe,
            "n_days": len(ls),
        },
        "decay": decay,
        "decay_opt": decay_opt,
        "lag1_rank_autocorr": autocorr_1d,
    }


def write_factor_md(out_path: Path, result: dict) -> None:
    name = result["name"]
    sign = result["expected_sign"]
    ic = result["ic_5d"]
    mono = result["monotonicity"]
    ls = result["long_short_q5_q1"]
    auto = result["lag1_rank_autocorr"]
    decay_opt = result["decay_opt"]

    lines = [
        f"# Factor evaluation: `{name}` (expected_sign={sign:+d})",
        "",
        "## 5-day IC summary",
        "",
        f"- mean_ic        : {ic['mean_ic']:.4f}",
        f"- mean_rank_ic   : {ic['mean_rank_ic']:.4f}",
        f"- icir           : {ic['icir']:.4f}",
        f"- rank_icir      : {ic['rank_icir']:.4f}",
        f"- ic_hit_rate    : {ic['ic_hit_rate']:.4f}  (% of days IC has same sign as mean)",
        f"- ic_positive_pct: {ic['ic_positive_pct']:.4f}  (% of days IC > 0)",
        f"- n_days         : {ic['n_days']}",
        "",
        "## Quintile annualized returns (5d fwd ret)",
        "",
        result["quantile_summary"].to_markdown(floatfmt=".4f") if not result["quantile_summary"].empty else "(empty)",
        "",
        f"**Monotonicity**: spearman={mono['spearman_corr']:+.3f}, "
        f"p={mono['p_value']:.4f}, direction={mono['direction']}, "
        f"is_monotonic(|s|>=0.8)={mono['is_monotonic']}.",
        "",
        f"**Long-short Q5-Q1 (annualised)**: ann_ret={ls['ann_ret']:.4f}, "
        f"ann_vol={ls['ann_vol']:.4f}, sharpe={ls['sharpe']:+.3f}, n_days={ls['n_days']}.",
        "",
        "## IC decay across horizons (trading days)",
        "",
        result["decay"].to_markdown(floatfmt=".4f") if not result["decay"].empty else "(empty)",
        "",
        f"**Optimal horizon (by |ICIR|)**: h={decay_opt['best_horizon_icir']}, "
        f"peak_icir={decay_opt['peak_icir']:.4f}, half_life={decay_opt['half_life']}.",
        "",
        "## Yearly IC (regime stability)",
        "",
        result["yearly_ic"].to_markdown(floatfmt=".4f") if not result["yearly_ic"].empty else "(empty)",
        "",
        f"## Turnover proxy",
        "",
        f"- lag-1 cross-sectional rank autocorrelation (mean across stocks): **{auto:.4f}**",
        f"  (higher = stickier sort key = lower portfolio turnover when used naively)",
        "",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    log.info("Run dir: %s", OUT_DIR)

    log.info("Parsing ST ranges")
    st_ranges = parse_st_ranges(ST_FILE)
    universe = sorted(st_ranges.keys())
    log.info("Universe size (ever ST): %d", len(universe))

    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    try:
        qlib.init(provider_uri=QLIB_DIR, region=REG_CN, kernels=1)
    except Exception:
        pass

    fields = [
        "Ref($total_mv, 1)",
        "Ref($revenue_q, 1)",
        "Ref(($close * $adj_factor), 1)",
        op.momentum(20),
        op.momentum(60),
        op.momentum(120),
        op.momentum(250),
    ]
    field_names = ["total_mv", "revenue_q", "adj_close",
                   "mom_20d", "mom_60d", "mom_120d", "mom_250d"]
    factor_specs = [
        ("total_mv", -1),
        ("revenue_q", +1),
        ("mom_20d", +1),
        ("mom_60d", +1),
        ("mom_120d", +1),
        ("mom_250d", +1),
    ]

    log.info("Loading %d features for %d instruments (%s → %s)",
             len(fields), len(universe), START_DATE, END_DATE)
    t0 = time.time()
    df = D.features(universe, fields, start_time=START_DATE, end_time=END_DATE, freq="day")
    log.info("Loaded panel %s in %.1fs", df.shape, time.time() - t0)
    df.columns = field_names

    if df.index.names[0] == "instrument":
        df = df.swaplevel().sort_index()
    df.index.names = ["datetime", "instrument"]

    log.info("Building ST mask")
    st_mask = build_st_mask(df.index, st_ranges)
    log.info("ST mask: %d True / %d total (%.1f%%)",
             st_mask.sum(), len(st_mask), 100.0 * st_mask.mean())

    df_st = df.where(st_mask, other=np.nan)

    # 5-day forward return on ST-masked adj_close (PIT-correct; we use the
    # ST-masked panel so the realised return is only counted on ST days).
    log.info("Computing 5d forward return")
    fwd_5d = (
        df["adj_close"].groupby(level="instrument", group_keys=False)
        .transform(lambda x: x.shift(-5) / x - 1.0)
    )
    fwd_5d = fwd_5d.where(st_mask, other=np.nan)
    adj_close_st = df["adj_close"].where(st_mask, other=np.nan)

    # ── Per-factor evaluation ──────────────────────────────────────────────
    summary_rows: list[dict] = []
    decay_rows: list[dict] = []
    yearly_rows: list[dict] = []

    for name, sign in factor_specs:
        result = evaluate_factor(name, df_st[name], fwd_5d, adj_close_st, sign)

        write_factor_md(OUT_DIR / "per_factor" / f"{name}.md", result)

        ic = result["ic_5d"]
        ls = result["long_short_q5_q1"]
        mono = result["monotonicity"]
        decay_opt = result["decay_opt"]
        summary_rows.append({
            "factor": name,
            "exp_sign": sign,
            "mean_ic": ic["mean_ic"],
            "icir": ic["icir"],
            "rank_icir": ic["rank_icir"],
            "ic_hit": ic["ic_hit_rate"],
            "n_days": ic["n_days"],
            "Q5-Q1_ann_ret": ls["ann_ret"],
            "Q5-Q1_sharpe": ls["sharpe"],
            "monotonic": mono["is_monotonic"],
            "mono_corr": mono["spearman_corr"],
            "best_h_icir": decay_opt["best_horizon_icir"],
            "peak_|icir|": decay_opt["peak_icir"],
            "lag1_rank_autocorr": result["lag1_rank_autocorr"],
        })

        # Decay long format
        for h, row in result["decay"].iterrows():
            decay_rows.append({
                "factor": name, "horizon": h,
                "mean_ic": row["mean_ic"], "icir": row["icir"],
                "mean_rank_ic": row["mean_rank_ic"], "rank_icir": row["rank_icir"],
            })
        # Yearly IC long format
        for year, row in result["yearly_ic"].iterrows():
            yearly_rows.append({
                "factor": name, "year": year,
                "mean_ic": row["mean_ic"], "rank_icir": row["rank_icir"],
                "n_days": row["n_days"],
            })

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(OUT_DIR / "summary.csv", index=False)

    decay_df = pd.DataFrame(decay_rows)
    decay_df.to_csv(OUT_DIR / "ic_decay.csv", index=False)

    yearly_df = pd.DataFrame(yearly_rows)
    yearly_df.to_csv(OUT_DIR / "yearly_ic.csv", index=False)

    # ── Cross-factor correlation ──────────────────────────────────────────
    log.info("Computing cross-factor correlation (raw values + cs ranks)")
    factor_panel = pd.DataFrame({
        name: df_st[name] for name, _ in factor_specs
    })
    raw_corr = compute_factor_correlation(factor_panel)
    raw_corr.to_csv(OUT_DIR / "correlation_raw.csv")

    rank_panel = pd.DataFrame({
        name: df_st[name].groupby(level="datetime").rank(pct=True)
        for name, _ in factor_specs
    })
    rank_corr = compute_factor_correlation(rank_panel)
    rank_corr.to_csv(OUT_DIR / "correlation_rank.csv")

    # ── Top-level report ──────────────────────────────────────────────────
    log.info("Writing top-level summary")
    md = [
        "# ST single-factor evaluation",
        "",
        f"Run: `{RUN_TS}` | Window: {START_DATE} → {END_DATE} | Universe: ST stocks (`st_stocks.txt`).",
        "",
        "Per-factor: 5d forward IC, quintile annualised returns + monotonicity, ",
        "long-short Q5-Q1, IC decay across horizons, yearly IC, lag-1 rank autocorrelation.",
        "Cross-factor: pairwise Pearson correlation on raw values and cross-sectional ranks.",
        "",
        "## Headline summary table",
        "",
        summary_df.to_markdown(index=False, floatfmt=".4f"),
        "",
        "## Cross-factor correlation (cross-sectional ranks)",
        "",
        rank_corr.to_markdown(floatfmt=".3f"),
        "",
        "## Files",
        "- `summary.csv` — headline metrics per factor",
        "- `ic_decay.csv` — long-format IC across horizons",
        "- `yearly_ic.csv` — long-format yearly IC",
        "- `correlation_raw.csv` / `correlation_rank.csv` — pairwise corr matrices",
        "- `per_factor/<name>.md` — per-factor detailed evaluation",
    ]
    (OUT_DIR / "summary.md").write_text("\n".join(md), encoding="utf-8")

    log.info("Done → %s/summary.md", OUT_DIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
