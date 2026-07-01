"""
Validate batch factor screening metrics against an independent pandas oracle.

This script is the Workstream 0 correctness gate for batch-screening
optimizations. It compares:

1. The current helper-based screening semantics used by the batch script
2. An independent pandas/scipy oracle implementation

Outputs:
  workspace/outputs/factor_screening_parity_reference.csv
  workspace/outputs/factor_screening_parity_oracle.csv
  workspace/outputs/factor_screening_parity_report.csv
  workspace/outputs/factor_screening_parity_summary.md

Usage:
    py -3.12 workspace/scripts/validate_factor_screening_parity.py
    py -3.12 workspace/scripts/validate_factor_screening_parity.py --sample all-existing-base --start 2024-01-01 --end 2024-12-31
    py -3.12 workspace/scripts/validate_factor_screening_parity.py --factors mom_intraday_20d qual_roe --composites comp_size_quality
"""

import argparse
import logging
from logging.handlers import RotatingFileHandler
import math
import os
import sys
import time
import warnings

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore")

# Logging setup
log_dir = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        RotatingFileHandler(
            os.path.join(log_dir, "factor_screening_parity.log"),
            maxBytes=10 * 1024 * 1024,
            backupCount=3,
        ),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


DEFAULT_BASE_FACTORS = [
    "mom_intraday_20d",
    "rev_return_5d",
    "val_sp_ttm",
    "qual_roe",
    "grow_netprofit_yoy",
    "size_ln_free_float",
    "risk_skew_60d",
    "liq_vol_cv_20d",
    "tech_rsi_14",
    "lev_current_ratio",
]

DEFAULT_COMPOSITES = [
    "comp_rev_low_turn",
    "comp_size_quality",
]


def _normalize_multiindex_independent(obj):
    """Normalize to MultiIndex(datetime, instrument) without using factor_eval helpers."""
    if not isinstance(obj.index, pd.MultiIndex):
        return obj
    if obj.index.nlevels != 2:
        return obj

    level_0 = obj.index.get_level_values(0)
    level_1 = obj.index.get_level_values(1)
    l0_is_datetime = pd.api.types.is_datetime64_any_dtype(level_0)
    l1_is_datetime = pd.api.types.is_datetime64_any_dtype(level_1)

    if l0_is_datetime and not l1_is_datetime:
        return obj.sort_index()
    if l1_is_datetime and not l0_is_datetime:
        return obj.swaplevel().sort_index()

    names = [str(name).lower() if name is not None else "" for name in obj.index.names]
    if any(kw in names[1] for kw in ("datetime", "date", "time")) and not any(
        kw in names[0] for kw in ("datetime", "date", "time")
    ):
        return obj.swaplevel().sort_index()

    return obj.sort_index()


def oracle_ic_series(factor, forward_return, min_obs=30):
    """Independent pandas IC / RankIC series."""
    factor = _normalize_multiindex_independent(factor)
    forward_return = _normalize_multiindex_independent(forward_return)
    df = pd.DataFrame({"factor": factor, "fwd": forward_return}).dropna()

    if df.empty:
        return pd.DataFrame(columns=["IC", "RankIC"])

    ic_values = {}
    rankic_values = {}
    for date, group in df.groupby(level=0, group_keys=False):
        if len(group) < min_obs:
            continue
        ic = group["factor"].corr(group["fwd"])
        rankic = group["factor"].corr(group["fwd"], method="spearman")

        # Match qlib.calc_ic(dropna=True): IC and RankIC are dropped
        # independently, so a date can survive in one column but not the other.
        if pd.notna(ic):
            ic_values[date] = ic
        if pd.notna(rankic):
            rankic_values[date] = rankic

    if not ic_values and not rankic_values:
        return pd.DataFrame(columns=["IC", "RankIC"])

    return pd.DataFrame(
        {
            "IC": pd.Series(ic_values, dtype=float),
            "RankIC": pd.Series(rankic_values, dtype=float),
        }
    ).sort_index()


def oracle_ic_summary(ic_series):
    """Independent IC summary matching current report semantics."""
    ic = ic_series["IC"].dropna()
    ric = ic_series["RankIC"].dropna()

    mean_ic = ic.mean()
    std_ic = ic.std()
    mean_ric = ric.mean()
    std_ric = ric.std()
    expected_sign = np.sign(mean_ic) if mean_ic != 0 else 1.0

    return {
        "mean_ic": mean_ic,
        "mean_rank_ic": mean_ric,
        "std_ic": std_ic,
        "std_rank_ic": std_ric,
        "icir": mean_ic / std_ic if std_ic > 0 else 0.0,
        "rank_icir": mean_ric / std_ric if std_ric > 0 else 0.0,
        "ic_hit_rate": (np.sign(ic) == expected_sign).mean() if len(ic) > 0 else 0.0,
        "ic_positive_pct": (ic > 0).mean() if len(ic) > 0 else 0.0,
        "n_days": len(ic),
    }


def oracle_quantile_returns(factor, forward_return, n_quantiles=10, min_obs=50):
    """Independent quantile return table using pandas qcut."""
    factor = _normalize_multiindex_independent(factor)
    forward_return = _normalize_multiindex_independent(forward_return)
    df = pd.DataFrame({"factor": factor, "fwd": forward_return}).dropna()

    if df.empty:
        return pd.DataFrame(columns=["date", "quantile", "mean_return", "count"])

    rows = []
    for date, group in df.groupby(level=0, group_keys=False):
        if len(group) < min_obs:
            continue
        try:
            labels = pd.qcut(
                group["factor"], n_quantiles, labels=False, duplicates="drop"
            )
        except ValueError:
            continue

        actual_n = labels.nunique()
        for q in range(actual_n):
            mask = labels == q
            rows.append(
                {
                    "date": date,
                    "quantile": q + 1,
                    "mean_return": group.loc[mask, "fwd"].mean(),
                    "count": int(mask.sum()),
                }
            )

    return pd.DataFrame(rows)


def oracle_quantile_summary(quantile_df, annual_factor=252):
    """Independent quantile summary."""
    if quantile_df.empty:
        return pd.DataFrame()

    rows = []
    for quantile, group in quantile_df.groupby("quantile"):
        daily_r = group["mean_return"]
        mean_r = daily_r.mean()
        std_r = daily_r.std()
        rows.append(
            {
                "quantile": quantile,
                "mean_daily_return": mean_r,
                "annualized_return": mean_r * annual_factor,
                "volatility": std_r * np.sqrt(annual_factor) if std_r > 0 else 0.0,
                "sharpe": np.sqrt(annual_factor) * mean_r / std_r if std_r > 0 else 0.0,
                "n_days": len(daily_r),
            }
        )

    return pd.DataFrame(rows).set_index("quantile")


def oracle_long_short_returns(quantile_df, long_q=None, short_q=1):
    """Independent long-short daily series."""
    if quantile_df.empty:
        return pd.Series(dtype=float)

    if long_q is None:
        long_q = quantile_df["quantile"].max()

    long_returns = (
        quantile_df[quantile_df["quantile"] == long_q]
        .set_index("date")["mean_return"]
    )
    short_returns = (
        quantile_df[quantile_df["quantile"] == short_q]
        .set_index("date")["mean_return"]
    )

    ls = (long_returns - short_returns).dropna()
    ls.name = f"long_short_Q{long_q}_Q{short_q}"
    return ls


def oracle_monotonicity(quantile_summary):
    """Independent monotonicity check."""
    if quantile_summary.empty or len(quantile_summary) < 3:
        return {
            "is_monotonic": False,
            "spearman_corr": 0.0,
            "p_value": 1.0,
            "direction": "unknown",
        }

    q_ranks = quantile_summary.index.values
    returns = quantile_summary["annualized_return"].values
    corr, p_value = stats.spearmanr(q_ranks, returns)
    direction = "ascending" if corr > 0 else "descending"

    return {
        "is_monotonic": abs(corr) >= 0.8,
        "spearman_corr": corr,
        "p_value": p_value,
        "direction": direction,
    }


def classify_results(df, primary_h=5):
    """Apply current grading semantics without importing report-generation code."""
    icir_col = f"rank_icir_{primary_h}d"
    df = df.copy()
    df["abs_icir"] = df[icir_col].abs()
    conditions = [
        (df["abs_icir"] >= 0.3) & (df.get("monotonic", False) == True),
        (df["abs_icir"] >= 0.3),
        (df["abs_icir"] >= 0.1),
    ]
    choices = ["A (Graduated)", "B (Strong IC)", "C (Moderate)"]
    df["grade"] = np.select(conditions, choices, default="D (Weak)")
    return df.sort_values("abs_icir", ascending=False)


def evaluate_reference(factors_df, fwd_df, horizons, progress_every=5, engine="reference"):
    """Evaluate the requested screening engine and collect comparison details."""
    from workspace.scripts.batch_factor_screening import run_batch_screening

    results, details = run_batch_screening(
        factors_df,
        fwd_df,
        horizons=horizons,
        progress_every=progress_every,
        engine=engine,
        return_details=True,
    )
    return classify_results(results, primary_h=horizons[0]), details


def evaluate_oracle(factors_df, fwd_df, horizons, progress_every=5):
    """Independent pandas oracle."""
    factor_cols = sorted(factors_df.columns)
    results = []
    details = {}
    primary_h = horizons[0]
    start_time = time.time()

    for i, factor_name in enumerate(factor_cols, start=1):
        factor = factors_df[factor_name]
        row = {"factor": factor_name}
        ic_details = {}

        for horizon in horizons:
            fwd_col = f"fwd_{horizon}d"
            if fwd_col not in fwd_df.columns:
                continue
            ic_series = oracle_ic_series(factor, fwd_df[fwd_col], min_obs=50)
            ic_details[horizon] = ic_series
            if ic_series.empty:
                row[f"n_days_{horizon}d"] = 0
                continue
            summary = oracle_ic_summary(ic_series)
            row[f"mean_rank_ic_{horizon}d"] = summary["mean_rank_ic"]
            row[f"rank_icir_{horizon}d"] = summary["rank_icir"]
            row[f"ic_hit_rate_{horizon}d"] = summary["ic_hit_rate"]
            row[f"n_days_{horizon}d"] = summary["n_days"]

        q_ret = oracle_quantile_returns(
            factor,
            fwd_df[f"fwd_{primary_h}d"],
            n_quantiles=10,
            min_obs=100,
        )
        if not q_ret.empty:
            q_summary = oracle_quantile_summary(q_ret)
            ls = oracle_long_short_returns(q_ret)
            mono = oracle_monotonicity(q_summary)
            row["monotonic"] = mono["is_monotonic"]
            row["mono_corr"] = mono["spearman_corr"]
            row["mono_p_value"] = mono["p_value"]
            row["ls_ann_return"] = ls.mean() * 252
            row["ls_sharpe"] = np.sqrt(252) * ls.mean() / ls.std() if ls.std() > 0 else 0.0
            row["ls_max_dd"] = (ls.cumsum().cummax() - ls.cumsum()).max()
        else:
            mono = {
                "is_monotonic": False,
                "spearman_corr": 0.0,
                "p_value": 1.0,
                "direction": "unknown",
            }
            ls = pd.Series(dtype=float)

        details[factor_name] = {
            "ic_series": ic_details,
            "quantile_returns": q_ret,
            "long_short": ls,
            "monotonicity": mono,
        }
        results.append(row)

        should_log = (
            i == 1 or
            i == len(factor_cols) or
            (progress_every and progress_every > 0 and i % progress_every == 0)
        )
        if should_log:
            elapsed = time.time() - start_time
            rate = i / elapsed if elapsed > 0 else 0
            eta = (len(factor_cols) - i) / rate if rate > 0 else float("nan")
            logger.info(
                f"  Oracle {i}/{len(factor_cols)}: {factor_name} "
                f"(elapsed {elapsed:.1f}s, ETA {eta:.1f}s)"
            )

    df = pd.DataFrame(results).set_index("factor")
    return classify_results(df, primary_h=primary_h), details


def _aligned_series_diff_max(left, right):
    if left.empty and right.empty:
        return 0.0
    aligned = pd.concat([left.rename("left"), right.rename("right")], axis=1)
    if aligned.empty:
        return 0.0

    one_sided_missing = aligned["left"].isna() ^ aligned["right"].isna()
    if bool(one_sided_missing.any()):
        return float("inf")

    diff = (aligned["left"] - aligned["right"]).abs().dropna()
    if diff.empty:
        return 0.0
    return float(diff.max())


def _series_match(left, right, tol):
    if left.empty and right.empty:
        return True
    aligned = pd.concat([left.rename("left"), right.rename("right")], axis=1)
    diff = (aligned["left"] - aligned["right"]).abs()
    if diff.dropna().empty:
        return True
    return bool((diff.dropna() <= tol).all())


def _safe_abs_diff(left, right):
    if pd.isna(left) and pd.isna(right):
        return 0.0
    if pd.isna(left) or pd.isna(right):
        return float("inf")
    return float(abs(left - right))


def _safe_equal(left, right):
    if pd.isna(left) and pd.isna(right):
        return True
    if pd.isna(left) or pd.isna(right):
        return False
    return bool(left == right)


def compare_results(reference_df, oracle_df, reference_details, oracle_details, horizons, metric_tol, series_tol):
    """Build per-factor comparison table."""
    rows = []
    primary_h = horizons[0]
    for factor_name in sorted(reference_df.index.union(oracle_df.index)):
        ref_row = reference_df.loc[factor_name] if factor_name in reference_df.index else pd.Series(dtype=float)
        oracle_row = oracle_df.loc[factor_name] if factor_name in oracle_df.index else pd.Series(dtype=float)

        row = {
            "factor": factor_name,
            "reference_grade": ref_row.get("grade"),
            "oracle_grade": oracle_row.get("grade"),
            "grade_match": _safe_equal(ref_row.get("grade"), oracle_row.get("grade")),
        }

        metric_pass = True
        for horizon in horizons:
            ref_ic = reference_details[factor_name]["ic_series"].get(horizon, pd.DataFrame(columns=["IC", "RankIC"]))
            oracle_ic = oracle_details[factor_name]["ic_series"].get(horizon, pd.DataFrame(columns=["IC", "RankIC"]))

            row[f"mean_rank_ic_{horizon}d_ref"] = ref_row.get(f"mean_rank_ic_{horizon}d")
            row[f"mean_rank_ic_{horizon}d_oracle"] = oracle_row.get(f"mean_rank_ic_{horizon}d")
            row[f"mean_rank_ic_{horizon}d_diff"] = _safe_abs_diff(
                ref_row.get(f"mean_rank_ic_{horizon}d"), oracle_row.get(f"mean_rank_ic_{horizon}d")
            )
            row[f"rank_icir_{horizon}d_ref"] = ref_row.get(f"rank_icir_{horizon}d")
            row[f"rank_icir_{horizon}d_oracle"] = oracle_row.get(f"rank_icir_{horizon}d")
            row[f"rank_icir_{horizon}d_diff"] = _safe_abs_diff(
                ref_row.get(f"rank_icir_{horizon}d"), oracle_row.get(f"rank_icir_{horizon}d")
            )
            row[f"ic_hit_rate_{horizon}d_diff"] = _safe_abs_diff(
                ref_row.get(f"ic_hit_rate_{horizon}d"), oracle_row.get(f"ic_hit_rate_{horizon}d")
            )
            row[f"n_days_{horizon}d_ref"] = ref_row.get(f"n_days_{horizon}d")
            row[f"n_days_{horizon}d_oracle"] = oracle_row.get(f"n_days_{horizon}d")
            row[f"n_days_{horizon}d_match"] = _safe_equal(
                ref_row.get(f"n_days_{horizon}d"), oracle_row.get(f"n_days_{horizon}d")
            )
            row[f"daily_ic_max_diff_{horizon}d"] = _aligned_series_diff_max(ref_ic.get("IC", pd.Series(dtype=float)), oracle_ic.get("IC", pd.Series(dtype=float)))
            row[f"daily_rankic_max_diff_{horizon}d"] = _aligned_series_diff_max(
                ref_ic.get("RankIC", pd.Series(dtype=float)), oracle_ic.get("RankIC", pd.Series(dtype=float))
            )

            metric_pass = metric_pass and row[f"mean_rank_ic_{horizon}d_diff"] <= metric_tol
            metric_pass = metric_pass and row[f"rank_icir_{horizon}d_diff"] <= metric_tol
            metric_pass = metric_pass and row[f"ic_hit_rate_{horizon}d_diff"] <= metric_tol
            metric_pass = metric_pass and bool(row[f"n_days_{horizon}d_match"])
            metric_pass = metric_pass and row[f"daily_ic_max_diff_{horizon}d"] <= series_tol
            metric_pass = metric_pass and row[f"daily_rankic_max_diff_{horizon}d"] <= series_tol

        ref_q = reference_details[factor_name]["quantile_returns"]
        oracle_q = oracle_details[factor_name]["quantile_returns"]
        ref_ls = reference_details[factor_name]["long_short"]
        oracle_ls = oracle_details[factor_name]["long_short"]
        ref_mono = reference_details[factor_name]["monotonicity"]
        oracle_mono = oracle_details[factor_name]["monotonicity"]

        row["quantile_rows_ref"] = len(ref_q)
        row["quantile_rows_oracle"] = len(oracle_q)
        row["quantile_rows_match"] = len(ref_q) == len(oracle_q)

        if not ref_q.empty or not oracle_q.empty:
            ref_q_cmp = ref_q.set_index(["date", "quantile"]).sort_index()["mean_return"]
            oracle_q_cmp = oracle_q.set_index(["date", "quantile"]).sort_index()["mean_return"]
            row["quantile_mean_return_max_diff"] = _aligned_series_diff_max(ref_q_cmp, oracle_q_cmp)
        else:
            row["quantile_mean_return_max_diff"] = 0.0

        row["ls_max_diff"] = _aligned_series_diff_max(ref_ls.sort_index(), oracle_ls.sort_index())
        row["monotonic_match"] = _safe_equal(ref_row.get("monotonic"), oracle_row.get("monotonic"))
        row["mono_corr_diff"] = _safe_abs_diff(ref_row.get("mono_corr"), oracle_row.get("mono_corr"))
        row["mono_p_value_diff"] = _safe_abs_diff(ref_row.get("mono_p_value"), oracle_row.get("mono_p_value"))
        row["ls_ann_return_diff"] = _safe_abs_diff(ref_row.get("ls_ann_return"), oracle_row.get("ls_ann_return"))
        row["ls_sharpe_diff"] = _safe_abs_diff(ref_row.get("ls_sharpe"), oracle_row.get("ls_sharpe"))
        row["ls_max_dd_diff"] = _safe_abs_diff(ref_row.get("ls_max_dd"), oracle_row.get("ls_max_dd"))
        row["mono_direction_match"] = _safe_equal(ref_mono.get("direction"), oracle_mono.get("direction"))

        metric_pass = metric_pass and bool(row["quantile_rows_match"])
        metric_pass = metric_pass and row["quantile_mean_return_max_diff"] <= series_tol
        metric_pass = metric_pass and row["ls_max_diff"] <= series_tol
        metric_pass = metric_pass and bool(row["monotonic_match"])
        metric_pass = metric_pass and row["mono_corr_diff"] <= metric_tol
        metric_pass = metric_pass and row["mono_p_value_diff"] <= metric_tol
        metric_pass = metric_pass and row["ls_ann_return_diff"] <= metric_tol
        metric_pass = metric_pass and row["ls_sharpe_diff"] <= metric_tol
        metric_pass = metric_pass and row["ls_max_dd_diff"] <= metric_tol
        metric_pass = metric_pass and bool(row["mono_direction_match"])
        metric_pass = metric_pass and bool(row["grade_match"])

        row["all_checks_pass"] = metric_pass
        rows.append(row)

    return pd.DataFrame(rows).set_index("factor")


def default_factor_selection(sample):
    if sample == "representative":
        return list(DEFAULT_BASE_FACTORS), list(DEFAULT_COMPOSITES)
    if sample == "representative-base":
        return list(DEFAULT_BASE_FACTORS), []
    raise ValueError(f"Unknown sample mode: {sample}")


def resolve_requested_factors(args):
    from src.alpha_research.factor_library import get_factor_catalog
    from src.alpha_research.factor_library.catalog import get_composite_defs

    catalog = get_factor_catalog(include_new_data=args.include_new_data)
    composite_defs = get_composite_defs()
    composite_map = {cdef["name"]: cdef for cdef in composite_defs}

    if args.sample.startswith("all-existing"):
        requested_base = list(catalog.keys())
        requested_composites = list(composite_map.keys()) if args.sample.endswith("with-composites") else []
        selection_mode = args.sample
    elif args.factors or args.composites:
        requested_base = list(args.factors or [])
        requested_composites = list(args.composites or [])
        selection_mode = "explicit"
    else:
        requested_base, requested_composites = default_factor_selection(args.sample)
        selection_mode = args.sample

    missing_base = [name for name in requested_base if name not in catalog]
    if missing_base:
        raise ValueError(f"Requested base factors not found in catalog: {missing_base}")

    missing_composites = [name for name in requested_composites if name not in composite_map]
    if missing_composites:
        raise ValueError(f"Requested composites not found: {missing_composites}")

    required_base = set(requested_base)
    required_composite_defs = []
    for name in requested_composites:
        cdef = composite_map[name]
        required_composite_defs.append(cdef)
        required_base.update(cdef["components"])

    base_catalog = {name: catalog[name] for name in catalog if name in required_base}
    requested_names = requested_base + requested_composites
    return base_catalog, required_composite_defs, requested_names, selection_mode


def write_summary(summary_path, comparison_df, args, reference_df, oracle_df, selection_mode, requested_names):
    total = len(comparison_df)
    passed = int(comparison_df["all_checks_pass"].sum())
    failed = total - passed
    failed_factors = comparison_df[~comparison_df["all_checks_pass"]]

    lines = [
        "# Factor Screening Parity Summary",
        "",
        f"- Window: `{args.start}` to `{args.end}`",
        f"- Horizons: `{args.horizon}`",
        f"- Screening engine: `{args.engine}`",
        f"- Selection mode: `{selection_mode}`",
        f"- Factor count checked: `{total}`",
        f"- Kernels: `{args.kernels}`",
        f"- Metric tolerance: `{args.metric_tol}`",
        f"- Series tolerance: `{args.series_tol}`",
        "",
        "## Result",
        "",
        f"- Passed: `{passed}`",
        f"- Failed: `{failed}`",
        "",
        "## Grade Counts",
        "",
        "Reference:",
    ]

    if len(requested_names) <= 25:
        lines.insert(9, f"- Requested names: `{requested_names}`")
        lines.insert(10, "")

    ref_grades = reference_df["grade"].value_counts()
    for grade in ["A (Graduated)", "B (Strong IC)", "C (Moderate)", "D (Weak)"]:
        lines.append(f"- {grade}: `{ref_grades.get(grade, 0)}`")

    lines.append("")
    lines.append("Oracle:")
    oracle_grades = oracle_df["grade"].value_counts()
    for grade in ["A (Graduated)", "B (Strong IC)", "C (Moderate)", "D (Weak)"]:
        lines.append(f"- {grade}: `{oracle_grades.get(grade, 0)}`")

    lines.append("")
    lines.append("## Failures")
    lines.append("")
    if failed_factors.empty:
        lines.append("- None")
    else:
        for factor_name, row in failed_factors.iterrows():
            issues = []
            if not row["grade_match"]:
                issues.append("grade")
            if not row["quantile_rows_match"]:
                issues.append("quantile_rows")
            if not row["monotonic_match"]:
                issues.append("monotonic")
            for horizon in args.horizon:
                if not row[f"n_days_{horizon}d_match"]:
                    issues.append(f"n_days_{horizon}d")
                if row[f"mean_rank_ic_{horizon}d_diff"] > args.metric_tol:
                    issues.append(f"mean_rank_ic_{horizon}d")
                if row[f"rank_icir_{horizon}d_diff"] > args.metric_tol:
                    issues.append(f"rank_icir_{horizon}d")
                if row[f"daily_rankic_max_diff_{horizon}d"] > args.series_tol:
                    issues.append(f"daily_rankic_{horizon}d")
            lines.append(f"- `{factor_name}`: {', '.join(issues)}")

    with open(summary_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(
        description="Validate factor screening metrics against an independent oracle"
    )
    parser.add_argument("--start", type=str, default="2024-01-01")
    parser.add_argument("--end", type=str, default="2024-12-31")
    parser.add_argument("--horizon", type=int, nargs="+", default=[5, 10, 20])
    parser.add_argument(
        "--sample",
        type=str,
        default="representative",
        choices=[
            "representative",
            "representative-base",
            "all-existing-base",
            "all-existing-with-composites",
        ],
    )
    parser.add_argument("--factors", type=str, nargs="*", default=None)
    parser.add_argument("--composites", type=str, nargs="*", default=None)
    parser.add_argument("--include-new-data", action="store_true")
    parser.add_argument("--kernels", type=int, default=1)
    parser.add_argument(
        "--engine",
        type=str,
        default="reference",
        choices=["reference", "batch"],
    )
    parser.add_argument("--progress-interval", type=int, default=30)
    parser.add_argument("--progress-every", type=int, default=5)
    parser.add_argument("--metric-tol", type=float, default=1e-12)
    parser.add_argument("--series-tol", type=float, default=1e-12)
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("  Factor Screening Parity Validation")
    logger.info(f"  Date range: {args.start} to {args.end}")
    logger.info(f"  Horizons: {args.horizon}")
    logger.info(f"  Sample: {args.sample}")
    logger.info(f"  Kernels: {args.kernels}")
    logger.info(f"  Screening engine: {args.engine}")
    logger.info("=" * 60)

    from src.alpha_research.factor_library import compute_factors, add_composites
    from src.alpha_research.factor_library.catalog import get_category_map

    base_catalog, composite_defs, requested_names, selection_mode = resolve_requested_factors(args)
    logger.info(
        f"Resolved {len(base_catalog)} base factors and {len(composite_defs)} composites "
        f"for {len(requested_names)} requested names (mode={selection_mode})"
    )

    factors_df, fwd_df = compute_factors(
        base_catalog,
        args.start,
        args.end,
        horizons=args.horizon,
        kernels=args.kernels,
        progress_interval=args.progress_interval,
    )
    if composite_defs:
        factors_df = add_composites(
            factors_df,
            composite_defs=composite_defs,
            progress_every=args.progress_every,
        )

    factors_df = factors_df[requested_names]
    logger.info("Running helper-based reference evaluation...")
    reference_df, reference_details = evaluate_reference(
        factors_df,
        fwd_df,
        horizons=args.horizon,
        progress_every=args.progress_every,
        engine=args.engine,
    )

    logger.info("Running independent oracle evaluation...")
    oracle_df, oracle_details = evaluate_oracle(
        factors_df,
        fwd_df,
        horizons=args.horizon,
        progress_every=args.progress_every,
    )

    comparison_df = compare_results(
        reference_df,
        oracle_df,
        reference_details,
        oracle_details,
        horizons=args.horizon,
        metric_tol=args.metric_tol,
        series_tol=args.series_tol,
    )

    category_map = get_category_map()
    comparison_df.insert(0, "category", [category_map.get(name, "Composite") for name in comparison_df.index])

    output_dir = os.path.join(PROJECT_ROOT, "workspace", "outputs")
    os.makedirs(output_dir, exist_ok=True)
    reference_path = os.path.join(output_dir, "factor_screening_parity_reference.csv")
    oracle_path = os.path.join(output_dir, "factor_screening_parity_oracle.csv")
    report_path = os.path.join(output_dir, "factor_screening_parity_report.csv")
    summary_path = os.path.join(output_dir, "factor_screening_parity_summary.md")

    reference_df.to_csv(reference_path)
    oracle_df.to_csv(oracle_path)
    comparison_df.to_csv(report_path)
    write_summary(
        summary_path,
        comparison_df,
        args,
        reference_df,
        oracle_df,
        selection_mode,
        requested_names,
    )

    passed = int(comparison_df["all_checks_pass"].sum())
    total = len(comparison_df)
    logger.info(f"Parity complete: {passed}/{total} factors passed all checks")
    logger.info(f"Saved outputs to {output_dir}")


if __name__ == "__main__":
    main()
