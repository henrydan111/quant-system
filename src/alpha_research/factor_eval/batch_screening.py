"""
Internal batch-screening engines for factor evaluation.

This module keeps the existing helper-based screening path available as the
semantic reference while providing an optimized batch engine for the batch
screening script. The optimized path is intentionally internal until it has
cleared the parity harness on representative and production windows.
"""

import logging
import time

import numpy as np
import pandas as pd

from src.alpha_research.factor_eval._utils import _normalize_multiindex
from src.alpha_research.factor_eval.ic_analysis import (
    compute_ic_series,
    compute_ic_summary,
)
from src.alpha_research.factor_eval.quantile_analysis import (
    compute_quantile_returns,
    compute_quantile_summary,
    compute_long_short_returns,
    test_monotonicity,
)

logger = logging.getLogger(__name__)

#: Unified group count (2026-06-11 directive): ALL evaluation paths use 10 groups
#: (deciles), matching factor_lifecycle's DEFAULT_N_QUANTILES and the CICC手册 protocol.
#: HISTORICAL NOTE: evidence registered before 2026-06-11 (incl. the Round-6 sealed-OOS
#: winners) was produced with quintiles — pass ``n_quantiles=5`` to reproduce it
#: bit-for-bit. Decile-based ls_sharpe (Q10−Q1) is NOT comparable to the historical
#: quintile-based numbers (a more extreme spread on fewer names).
DEFAULT_SCREENING_QUANTILES = 10


def _prepare_inputs(factors_df: pd.DataFrame, fwd_df: pd.DataFrame):
    factors_df = _normalize_multiindex(factors_df)
    fwd_df = _normalize_multiindex(fwd_df)

    if not factors_df.index.equals(fwd_df.index):
        common_index = factors_df.index.intersection(fwd_df.index)
        factors_df = factors_df.loc[common_index]
        fwd_df = fwd_df.loc[common_index]

    if not factors_df.index.is_monotonic_increasing:
        factors_df = factors_df.sort_index()
        fwd_df = fwd_df.loc[factors_df.index]

    return factors_df, fwd_df


def _build_date_slices(index: pd.MultiIndex):
    if not isinstance(index, pd.MultiIndex) or index.nlevels != 2:
        raise ValueError("Batch screening expects a 2-level MultiIndex")

    if len(index) == 0:
        return []

    date_values = index.get_level_values(0).to_numpy()
    starts = [0]
    for i in range(1, len(date_values)):
        if date_values[i] != date_values[i - 1]:
            starts.append(i)
    ends = starts[1:] + [len(date_values)]

    return [
        (date_values[start], int(start), int(end))
        for start, end in zip(starts, ends)
    ]


def _empty_details():
    return {
        "ic_series": {},
        "quantile_returns": pd.DataFrame(
            columns=["date", "quantile", "mean_return", "count"]
        ),
        "long_short": pd.Series(dtype=float),
        "monotonicity": {
            "is_monotonic": False,
            "spearman_corr": 0.0,
            "p_value": 1.0,
            "direction": "unknown",
        },
    }


def _should_log(i: int, total: int, progress_every: int):
    return (
        i == 1 or
        i == total or
        (progress_every and progress_every > 0 and i % progress_every == 0)
    )


def _log_progress(
    prefix: str,
    i: int,
    total: int,
    name: str,
    started_at: float,
    progress_every: int,
    log,
):
    if not _should_log(i, total, progress_every):
        return
    elapsed = time.time() - started_at
    rate = i / elapsed if elapsed > 0 else 0.0
    eta = (total - i) / rate if rate > 0 else float("nan")
    log.info(
        f"  {prefix} {i}/{total}: {name} "
        f"(elapsed {elapsed:.1f}s, ETA {eta:.1f}s)"
    )


def _normalize_existing_results(existing_results, factor_cols):
    if existing_results is None or len(existing_results) == 0:
        return pd.DataFrame()

    if "factor" in existing_results.columns and existing_results.index.name != "factor":
        existing_results = existing_results.set_index("factor")

    existing_results = existing_results.copy()
    existing_results = existing_results[~existing_results.index.duplicated(keep="last")]
    keep_names = [name for name in factor_cols if name in existing_results.index]
    if not keep_names:
        return pd.DataFrame()
    return existing_results.loc[keep_names]


def _assemble_results_df(factor_cols, existing_df, new_rows):
    frames = []
    if existing_df is not None and not existing_df.empty:
        frames.append(existing_df)
    if new_rows:
        frames.append(pd.DataFrame(new_rows).set_index("factor"))

    if not frames:
        return pd.DataFrame(index=pd.Index([], name="factor"))

    df = pd.concat(frames, axis=0)
    df = df[~df.index.duplicated(keep="last")]
    ordered = [name for name in factor_cols if name in df.index]
    return df.loc[ordered]


def _append_ic_metrics(row, ic, horizon):
    ic_days = int(ic["IC"].dropna().shape[0]) if "IC" in ic.columns else 0
    rankic_days = int(ic["RankIC"].dropna().shape[0]) if "RankIC" in ic.columns else 0
    row[f"n_days_{horizon}d"] = ic_days
    row[f"rankic_days_{horizon}d"] = rankic_days
    row[f"constant_xs_days_{horizon}d"] = max(rankic_days - ic_days, 0)

    if ic.empty:
        return

    summary = compute_ic_summary(ic)
    row[f"mean_rank_ic_{horizon}d"] = summary["mean_rank_ic"]
    row[f"rank_icir_{horizon}d"] = summary["rank_icir"]
    row[f"ic_hit_rate_{horizon}d"] = summary["ic_hit_rate"]


def _append_quantile_metrics(row, q_ret, primary_h):
    row[f"quantile_days_{primary_h}d"] = 0
    row[f"quantile_min_buckets_{primary_h}d"] = 0
    row[f"quantile_max_buckets_{primary_h}d"] = 0
    row[f"reduced_quantile_dates_{primary_h}d"] = 0

    if q_ret.empty:
        return

    bucket_counts = q_ret.groupby("date")["quantile"].nunique()
    row[f"quantile_days_{primary_h}d"] = int(bucket_counts.shape[0])
    row[f"quantile_min_buckets_{primary_h}d"] = int(bucket_counts.min())
    row[f"quantile_max_buckets_{primary_h}d"] = int(bucket_counts.max())
    row[f"reduced_quantile_dates_{primary_h}d"] = int((bucket_counts < 5).sum())


def run_reference_batch_screening(
    factors_df: pd.DataFrame,
    fwd_df: pd.DataFrame,
    horizons=(5, 10, 20),
    progress_every: int = 5,
    return_details: bool = False,
    existing_results: pd.DataFrame = None,
    checkpoint_every: int = 0,
    checkpoint_callback=None,
    log=None,
    n_quantiles: int = DEFAULT_SCREENING_QUANTILES,
):
    """Reference helper-based screening path."""
    log = log or logger
    factors_df, fwd_df = _prepare_inputs(factors_df, fwd_df)

    factor_cols = sorted(factors_df.columns.tolist())
    existing_df = _normalize_existing_results(existing_results, factor_cols)
    completed_count = len(existing_df)
    pending_factor_cols = [name for name in factor_cols if name not in existing_df.index]
    if completed_count:
        log.info(
            f"  Resuming screening from cache: {completed_count}/{len(factor_cols)} "
            f"factors already completed"
        )

    results = []
    details = {} if return_details else None
    primary_h = horizons[0]
    started_at = time.time()

    if return_details and not existing_df.empty:
        raise ValueError("Detailed screening resume is not supported")

    if not pending_factor_cols:
        final_df = existing_df
        return (final_df, details) if return_details else final_df

    for i, name in enumerate(pending_factor_cols, start=completed_count + 1):
        factor = factors_df[name]
        row = {"factor": name}
        detail = _empty_details() if return_details else None

        for h in horizons:
            fwd_col = f"fwd_{h}d"
            if fwd_col not in fwd_df.columns:
                continue
            try:
                ic = compute_ic_series(factor, fwd_df[fwd_col], min_obs=50)
                if return_details:
                    detail["ic_series"][h] = ic
                _append_ic_metrics(row, ic, h)
            except Exception as exc:
                log.warning(f"  SKIP {name} h={h}: {exc}")

        fwd_col = f"fwd_{primary_h}d"
        if fwd_col in fwd_df.columns:
            try:
                q_ret = compute_quantile_returns(
                    factor,
                    fwd_df[fwd_col],
                    n_quantiles=n_quantiles,
                    min_obs=100,
                )
                q_summary = compute_quantile_summary(q_ret)
                ls = compute_long_short_returns(q_ret)
                mono = test_monotonicity(q_summary)

                if return_details:
                    detail["quantile_returns"] = q_ret
                    detail["long_short"] = ls
                    detail["monotonicity"] = mono

                _append_quantile_metrics(row, q_ret, primary_h)
                if not q_ret.empty:
                    row["monotonic"] = mono["is_monotonic"]
                    row["mono_corr"] = mono["spearman_corr"]
                    row["mono_p_value"] = mono["p_value"]
                    row["ls_ann_return"] = ls.mean() * 252
                    row["ls_sharpe"] = (
                        np.sqrt(252) * ls.mean() / ls.std()
                        if ls.std() > 0 else 0
                    )
                    row["ls_max_dd"] = (
                        ls.cumsum().cummax() - ls.cumsum()
                    ).max()
            except Exception as exc:
                log.warning(f"  SKIP quantile {name}: {exc}")

        results.append(row)
        if return_details:
            details[name] = detail
        _log_progress("Screening", i, len(factor_cols), name, started_at, progress_every, log)
        if checkpoint_callback and checkpoint_every and checkpoint_every > 0:
            processed_new = len(results)
            if processed_new % checkpoint_every == 0 or i == len(factor_cols):
                current_df = _assemble_results_df(factor_cols, existing_df, results)
                checkpoint_callback(current_df, complete=(i == len(factor_cols)))

    df = _assemble_results_df(factor_cols, existing_df, results)
    return (df, details) if return_details else df


def _compute_ic_series_fast(factor_values, fwd_values, date_slices, min_obs):
    ic_dates = []
    ic_values = []
    rank_dates = []
    rank_values = []

    for date, start, end in date_slices:
        factor_slice = factor_values[start:end]
        fwd_slice = fwd_values[start:end]
        valid_mask = ~(pd.isna(factor_slice) | pd.isna(fwd_slice))
        if int(valid_mask.sum()) < min_obs:
            continue

        factor_valid = pd.Series(factor_slice[valid_mask])
        fwd_valid = pd.Series(fwd_slice[valid_mask])

        ic = factor_valid.corr(fwd_valid)
        rank_ic = factor_valid.corr(fwd_valid, method="spearman")

        if pd.notna(ic):
            ic_dates.append(date)
            ic_values.append(ic)
        if pd.notna(rank_ic):
            rank_dates.append(date)
            rank_values.append(rank_ic)

    if not ic_values and not rank_values:
        return pd.DataFrame(columns=["IC", "RankIC"])

    return pd.DataFrame(
        {
            "IC": pd.Series(ic_values, index=ic_dates, dtype=float),
            "RankIC": pd.Series(rank_values, index=rank_dates, dtype=float),
        }
    ).sort_index()


def _compute_quantile_returns_fast(
    factor_values,
    fwd_values,
    date_slices,
    n_quantiles,
    min_obs,
):
    rows = []

    for date, start, end in date_slices:
        factor_slice = factor_values[start:end]
        fwd_slice = fwd_values[start:end]
        valid_mask = ~(pd.isna(factor_slice) | pd.isna(fwd_slice))
        if int(valid_mask.sum()) < min_obs:
            continue

        factor_valid = factor_slice[valid_mask]
        fwd_valid = fwd_slice[valid_mask]

        try:
            labels = pd.qcut(
                pd.Series(factor_valid),
                n_quantiles,
                labels=False,
                duplicates="drop",
            )
        except ValueError:
            continue

        actual_n = labels.nunique()
        if actual_n == 0:
            continue

        label_values = labels.to_numpy()
        for q in range(actual_n):
            q_mask = label_values == q
            rows.append(
                {
                    "date": date,
                    "quantile": q + 1,
                    "mean_return": pd.Series(fwd_valid[q_mask]).mean(),
                    "count": int(q_mask.sum()),
                }
            )

    if not rows:
        return pd.DataFrame(columns=["date", "quantile", "mean_return", "count"])

    return pd.DataFrame(rows)


def run_optimized_batch_screening(
    factors_df: pd.DataFrame,
    fwd_df: pd.DataFrame,
    horizons=(5, 10, 20),
    progress_every: int = 5,
    return_details: bool = False,
    existing_results: pd.DataFrame = None,
    checkpoint_every: int = 0,
    checkpoint_callback=None,
    log=None,
    n_quantiles: int = DEFAULT_SCREENING_QUANTILES,
):
    """Optimized screening path for the batch script.

    This path preserves the public helper semantics but reduces repeated
    frame construction by:
    - normalizing inputs once
    - precomputing date slices once
    - operating on aligned column arrays inside the factor loop
    """
    log = log or logger
    factors_df, fwd_df = _prepare_inputs(factors_df, fwd_df)
    date_slices = _build_date_slices(factors_df.index)
    factor_cols = sorted(factors_df.columns.tolist())
    existing_df = _normalize_existing_results(existing_results, factor_cols)
    completed_count = len(existing_df)
    pending_factor_cols = [name for name in factor_cols if name not in existing_df.index]
    if completed_count:
        log.info(
            f"  Resuming screening from cache: {completed_count}/{len(factor_cols)} "
            f"factors already completed"
        )
    primary_h = horizons[0]
    started_at = time.time()

    fwd_arrays = {}
    for h in horizons:
        fwd_col = f"fwd_{h}d"
        if fwd_col in fwd_df.columns:
            fwd_arrays[h] = fwd_df[fwd_col].to_numpy(copy=False)

    primary_fwd = fwd_arrays.get(primary_h)
    results = []
    details = {} if return_details else None

    if return_details and not existing_df.empty:
        raise ValueError("Detailed screening resume is not supported")

    if not pending_factor_cols:
        final_df = existing_df
        return (final_df, details) if return_details else final_df

    for i, name in enumerate(pending_factor_cols, start=completed_count + 1):
        factor_values = factors_df[name].to_numpy(copy=False)
        row = {"factor": name}
        detail = _empty_details() if return_details else None

        for h in horizons:
            if h not in fwd_arrays:
                continue
            ic = _compute_ic_series_fast(
                factor_values,
                fwd_arrays[h],
                date_slices,
                min_obs=50,
            )
            if return_details:
                detail["ic_series"][h] = ic
            _append_ic_metrics(row, ic, h)

        if primary_fwd is not None:
            q_ret = _compute_quantile_returns_fast(
                factor_values,
                primary_fwd,
                date_slices,
                n_quantiles=n_quantiles,
                min_obs=100,
            )
            q_summary = compute_quantile_summary(q_ret)
            ls = compute_long_short_returns(q_ret)
            mono = test_monotonicity(q_summary)

            if return_details:
                detail["quantile_returns"] = q_ret
                detail["long_short"] = ls
                detail["monotonicity"] = mono

            _append_quantile_metrics(row, q_ret, primary_h)
            if not q_ret.empty:
                row["monotonic"] = mono["is_monotonic"]
                row["mono_corr"] = mono["spearman_corr"]
                row["mono_p_value"] = mono["p_value"]
                row["ls_ann_return"] = ls.mean() * 252
                row["ls_sharpe"] = (
                    np.sqrt(252) * ls.mean() / ls.std()
                    if ls.std() > 0 else 0
                )
                row["ls_max_dd"] = (
                    ls.cumsum().cummax() - ls.cumsum()
                ).max()

        results.append(row)
        if return_details:
            details[name] = detail
        _log_progress("Screening", i, len(factor_cols), name, started_at, progress_every, log)
        if checkpoint_callback and checkpoint_every and checkpoint_every > 0:
            processed_new = len(results)
            if processed_new % checkpoint_every == 0 or i == len(factor_cols):
                current_df = _assemble_results_df(factor_cols, existing_df, results)
                checkpoint_callback(current_df, complete=(i == len(factor_cols)))

    df = _assemble_results_df(factor_cols, existing_df, results)
    return (df, details) if return_details else df


def run_batch_screening(
    factors_df: pd.DataFrame,
    fwd_df: pd.DataFrame,
    horizons=(5, 10, 20),
    progress_every: int = 5,
    engine: str = "reference",
    return_details: bool = False,
    existing_results: pd.DataFrame = None,
    checkpoint_every: int = 0,
    checkpoint_callback=None,
    log=None,
    n_quantiles: int = DEFAULT_SCREENING_QUANTILES,
):
    """Dispatch to the requested screening engine.

    ``n_quantiles`` defaults to the unified 10-group standard; pass ``5`` only to
    reproduce pre-2026-06-11 registered evidence (see DEFAULT_SCREENING_QUANTILES).
    """
    if engine == "reference":
        return run_reference_batch_screening(
            factors_df,
            fwd_df,
            horizons=horizons,
            progress_every=progress_every,
            return_details=return_details,
            existing_results=existing_results,
            checkpoint_every=checkpoint_every,
            checkpoint_callback=checkpoint_callback,
            log=log,
            n_quantiles=n_quantiles,
        )
    if engine == "batch":
        return run_optimized_batch_screening(
            factors_df,
            fwd_df,
            horizons=horizons,
            progress_every=progress_every,
            return_details=return_details,
            existing_results=existing_results,
            checkpoint_every=checkpoint_every,
            checkpoint_callback=checkpoint_callback,
            log=log,
            n_quantiles=n_quantiles,
        )
    raise ValueError(f"Unknown screening engine: {engine}")
