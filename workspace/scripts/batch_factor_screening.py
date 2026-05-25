"""
# Batch Factor Screening (Phase B)
Computes all factors using the factor_library operator system, then runs
IC/ICIR screening and quantile analysis for each factor.

Uses Qlib's native expression engine via the factor_library API for
fast computation (~100x faster than pandas groupby/lambda).

Saves results to:
  workspace/outputs/factor_screening_results.parquet
  workspace/outputs/factor_screening_report.csv
  workspace/outputs/factor_screening_summary.txt

Usage:
    python workspace/scripts/batch_factor_screening.py
    python workspace/scripts/batch_factor_screening.py --start 2012-01-01 --end 2025-12-31
    python workspace/scripts/batch_factor_screening.py --horizon 10
"""

import sys
import os
import argparse
import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
import time
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

# Logging setup
log_dir = os.path.join(PROJECT_ROOT, 'logs')
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(
            os.path.join(log_dir, 'batch_factor_screening.log'),
            maxBytes=10*1024*1024, backupCount=3
        ),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

CACHE_KEY_VERSION = 1


def _json_dumps(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _hash_object(payload):
    return hashlib.sha256(_json_dumps(payload).encode("utf-8")).hexdigest()


def _file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _dir_signature(root):
    root_path = Path(root).resolve()
    file_count = 0
    latest_mtime_ns = 0

    for dirpath, _, filenames in os.walk(root_path):
        for filename in filenames:
            file_count += 1
            try:
                stat = os.stat(os.path.join(dirpath, filename))
            except OSError:
                continue
            latest_mtime_ns = max(latest_mtime_ns, getattr(stat, "st_mtime_ns", 0))

    return {
        "path": str(root_path),
        "file_count": file_count,
        "latest_mtime_ns": latest_mtime_ns,
    }


def _resolve_latest_backend_end_date(qlib_dir):
    """Read the latest trading day directly from the published provider calendar."""
    calendar_path = Path(qlib_dir) / "calendars" / "day.txt"
    if not calendar_path.exists():
        raise FileNotFoundError(f"Qlib calendar not found: {calendar_path}")

    last_date = None
    with open(calendar_path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                last_date = line

    if not last_date:
        raise ValueError(f"No calendar dates found in {calendar_path}")
    return last_date


def _build_code_fingerprint():
    relevant_files = [
        Path(PROJECT_ROOT) / "workspace" / "scripts" / "batch_factor_screening.py",
        Path(PROJECT_ROOT) / "src" / "alpha_research" / "factor_library" / "operators.py",
        Path(PROJECT_ROOT) / "src" / "alpha_research" / "factor_library" / "catalog.py",
        Path(PROJECT_ROOT) / "src" / "alpha_research" / "factor_eval" / "batch_screening.py",
        Path(PROJECT_ROOT) / "src" / "alpha_research" / "factor_eval" / "ic_analysis.py",
        Path(PROJECT_ROOT) / "src" / "alpha_research" / "factor_eval" / "quantile_analysis.py",
    ]
    files = {}
    for path in relevant_files:
        if path.exists():
            files[str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")] = _file_sha256(path)

    return {
        "files": files,
        "hash": _hash_object(files),
    }


def _build_base_cache_context(args, kernels, catalog, composite_defs, qlib_dir):
    kernels_value = "qlib_default" if kernels is None else int(kernels)
    qlib_data_dir = Path(qlib_dir).resolve()

    return {
        "cache_key_version": CACHE_KEY_VERSION,
        "start_date": args.start,
        "end_date": args.end,
        "horizons": list(args.horizon),
        "kernels": kernels_value,
        "include_new_data": bool(args.include_new_data),
        "qlib_data_dir": str(qlib_data_dir),
        "qlib_data_signature": _dir_signature(qlib_data_dir),
        "catalog_names": sorted(catalog.keys()),
        "catalog_hash": _hash_object(catalog),
        "composite_names": [cdef["name"] for cdef in composite_defs],
        "composite_hash": _hash_object(composite_defs),
        "code_hash": _build_code_fingerprint()["hash"],
    }


def _build_stage_cache_key(base_context, stage, **extra):
    payload = dict(base_context)
    payload["stage"] = stage
    payload.update(extra)
    return payload


def _make_run_cache_dir(cache_root, base_context):
    run_hash = _hash_object(base_context)[:16]
    return Path(cache_root) / run_hash


def _make_temp_path(path):
    return path.with_name(f"{path.name}.tmp.{os.getpid()}.{time.time_ns()}")


def _atomic_write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = _make_temp_path(path)
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2, sort_keys=True, default=str)
    os.replace(temp_path, path)


def _atomic_write_parquet(df, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = _make_temp_path(path)
    df.to_parquet(temp_path)
    os.replace(temp_path, path)


def _load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _cache_key_diff(expected, actual):
    diff = []
    for key in sorted(set(expected) | set(actual)):
        if expected.get(key) != actual.get(key):
            diff.append(key)
    return diff


def _load_cache_payload(meta_path, expected_key, data_paths, stage_name):
    meta_path = Path(meta_path)
    data_paths = [Path(path) for path in data_paths]
    if not meta_path.exists():
        return None
    if any(not path.exists() for path in data_paths):
        logger.warning(f"Ignoring {stage_name} cache: missing data files")
        return None

    payload = _load_json(meta_path)
    actual_key = payload.get("cache_key", {})
    if actual_key != expected_key:
        mismatch = _cache_key_diff(expected_key, actual_key)
        logger.info(f"Ignoring {stage_name} cache: metadata mismatch in {mismatch}")
        return None
    return payload


def _write_stage_cache(meta_path, cache_key, state, data_writers):
    for writer in data_writers:
        writer()
    payload = {
        "cache_key": cache_key,
        "state": state,
    }
    _atomic_write_json(meta_path, payload)


def _screening_checkpoint_writer(results_path, meta_path, cache_key):
    def _writer(results_df, complete):
        state = {
            "complete": bool(complete),
            "row_count": int(len(results_df)),
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        _write_stage_cache(
            meta_path,
            cache_key,
            state,
            [lambda: _atomic_write_parquet(results_df, results_path)],
        )
    return _writer


# ─────────────────────────────────────────────────────────────────────
#  Batch IC Screening
# ─────────────────────────────────────────────────────────────────────

def run_batch_screening(factors_df, fwd_df, horizons=[5, 10, 20],
                        progress_every=5, engine="batch",
                        return_details=False, existing_results=None,
                        checkpoint_every=0, checkpoint_callback=None):
    """Run IC/ICIR screening for all factors.

    Args:
        factors_df: DataFrame with factor columns.
        fwd_df: DataFrame with forward return columns (fwd_5d, fwd_10d, etc.).
        horizons: Forward horizons to evaluate.
        progress_every: Log screening progress every N factors.
        engine: Screening engine ('batch' or 'reference').
        return_details: When True, return detail objects for parity checks.
        existing_results: Optional partial raw results DataFrame to resume from.
        checkpoint_every: Save checkpoint every N newly processed factors.
        checkpoint_callback: Callable receiving `(results_df, complete)`.

    Returns:
        DataFrame with screening results, or `(results, details)` when
        `return_details=True`.
    """
    from src.alpha_research.factor_eval.batch_screening import (
        run_batch_screening as run_batch_screening_engine,
    )
    return run_batch_screening_engine(
        factors_df,
        fwd_df,
        horizons=horizons,
        progress_every=progress_every,
        engine=engine,
        return_details=return_details,
        existing_results=existing_results,
        checkpoint_every=checkpoint_every,
        checkpoint_callback=checkpoint_callback,
        log=logger,
    )


# ─────────────────────────────────────────────────────────────────────
#  Report Generation
# ─────────────────────────────────────────────────────────────────────

def generate_report(df, primary_h=5):
    """Classify factors and generate summary report.

    Args:
        df: Screening results DataFrame.
        primary_h: Primary evaluation horizon.

    Returns:
        Tuple of (classified_df, summary_text).
    """
    icir_col = f'rank_icir_{primary_h}d'
    if icir_col not in df.columns:
        logger.error(f"Column {icir_col} not found")
        return df, ""

    df = df.copy()
    df['abs_icir'] = df[icir_col].abs()

    # Classification
    conditions = [
        (df['abs_icir'] >= 0.3) & (df.get('monotonic', False) == True),
        (df['abs_icir'] >= 0.3),
        (df['abs_icir'] >= 0.1),
    ]
    choices = ['A (Graduated)', 'B (Strong IC)', 'C (Moderate)']
    df['grade'] = np.select(conditions, choices, default='D (Weak)')
    df = df.sort_values('abs_icir', ascending=False)

    # Additive diagnostics only. Existing columns are left unchanged.
    available_icir_cols = [
        f'rank_icir_{h}d' for h in (5, 10, 20) if f'rank_icir_{h}d' in df.columns
    ]
    if available_icir_cols:
        icir_frame = df[available_icir_cols]
        df['horizon_abs_rank_icir_mean'] = icir_frame.abs().mean(axis=1)
        df['horizon_rank_icir_std'] = icir_frame.std(axis=1)

        def _sign_consistent(row):
            vals = row.dropna()
            vals = vals[vals != 0]
            if len(vals) <= 1:
                return True
            return bool((np.sign(vals) == np.sign(vals.iloc[0])).all())

        df['horizon_sign_consistent'] = icir_frame.apply(_sign_consistent, axis=1)

    n_days_col = f'n_days_{primary_h}d'
    rankic_days_col = f'rankic_days_{primary_h}d'
    constant_days_col = f'constant_xs_days_{primary_h}d'
    reduced_quantile_col = f'reduced_quantile_dates_{primary_h}d'

    max_n_days = float(df[n_days_col].max()) if n_days_col in df.columns and df[n_days_col].notna().any() else 0.0
    max_rankic_days = (
        float(df[rankic_days_col].max())
        if rankic_days_col in df.columns and df[rankic_days_col].notna().any()
        else 0.0
    )

    if n_days_col in df.columns:
        df['obs_coverage_primary'] = (
            df[n_days_col].fillna(0) / max_n_days if max_n_days > 0 else 0.0
        )
        df['warn_low_obs_primary'] = df['obs_coverage_primary'] < 0.10
    else:
        df['obs_coverage_primary'] = 0.0
        df['warn_low_obs_primary'] = False

    if rankic_days_col in df.columns:
        df['rankic_coverage_primary'] = (
            df[rankic_days_col].fillna(0) / max_rankic_days if max_rankic_days > 0 else 0.0
        )
    else:
        df['rankic_coverage_primary'] = 0.0

    df['warn_reduced_quantiles_primary'] = (
        df.get(reduced_quantile_col, 0).fillna(0) > 0
        if reduced_quantile_col in df.columns else False
    )
    df['warn_constant_xs_primary'] = (
        df.get(constant_days_col, 0).fillna(0) > 0
        if constant_days_col in df.columns else False
    )
    df['warn_extreme_rank_icir_primary'] = df[icir_col].abs().fillna(0) >= 2.0
    df['ls_ann_return_semantics'] = 'overlapping_forward_return_diagnostic'

    def _warning_flags(row):
        flags = []
        if row.get('warn_low_obs_primary', False):
            flags.append('low_obs')
        if row.get('warn_reduced_quantiles_primary', False):
            flags.append('reduced_quantiles')
        if row.get('warn_constant_xs_primary', False):
            flags.append('constant_xs')
        if row.get('warn_extreme_rank_icir_primary', False):
            flags.append('extreme_icir')
        return ','.join(flags)

    df['warning_flags'] = df.apply(_warning_flags, axis=1)

    # Summary text
    grades = df['grade'].value_counts()
    summary = [
        "=" * 60,
        "  FACTOR SCREENING SUMMARY",
        "=" * 60,
        f"  Total factors screened: {len(df)}",
        f"  Primary horizon: {primary_h}-day forward return",
        "",
    ]
    for grade in ['A (Graduated)', 'B (Strong IC)', 'C (Moderate)', 'D (Weak)']:
        count = grades.get(grade, 0)
        summary.append(f"  {grade}: {count}")
    summary.append("")
    summary.append("  TOP 20 FACTORS (by |RankICIR|):")
    summary.append("  " + "-" * 56)
    for _, row in df.head(20).iterrows():
        name = row.name
        icir = row.get(icir_col, 0)
        mono = "Y" if row.get('monotonic', False) else "N"
        grade = row.get('grade', '?')
        ls = row.get('ls_ann_return', 0)
        summary.append(
            f"  {name:40s} ICIR={icir:+.3f}  Mono={mono}  "
            f"L/S={ls:+.1%}  [{grade}]"
        )
    summary.append("")
    summary.append("  Note: L/S is an overlapping-forward-return diagnostic, not an investable return estimate.")
    summary.append("=" * 60)
    return df, "\n".join(summary)


# ─────────────────────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────────────────────

def run_factor_screening_pipeline(argv=None):
    parser = argparse.ArgumentParser(description="Batch Factor IC Screening")
    parser.add_argument('--start', type=str, default='2012-01-01',
                        help='Start date (default: 2012-01-01)')
    parser.add_argument('--end', type=str, default='2025-12-31',
                        help='End date (default: 2025-12-31, or use "auto" for latest provider date)')
    parser.add_argument('--horizon', type=int, nargs='+', default=[5, 10, 20],
                        help='Forward horizons in days (default: 5 10 20)')
    parser.add_argument('--kernels', type=int, default=0,
                        help='Qlib worker processes (default: 0 = Qlib default, with automatic fallback to 1 on worker-permission failures)')
    parser.add_argument('--engine', type=str, default='batch',
                        choices=['reference', 'batch'],
                        help='Screening engine (default: batch)')
    parser.add_argument('--include-new-data', action='store_true',
                        help='Include factors that depend on newly synced datasets')
    parser.add_argument('--cache-mode', type=str, default='off',
                        choices=['off', 'resume', 'refresh'],
                        help='Stage cache mode (default: off)')
    parser.add_argument('--cache-dir', type=str,
                        default=os.path.join('workspace', 'outputs', 'factor_screening_cache'),
                        help='Cache root directory for resumable runs')
    parser.add_argument('--qlib-dir', type=str,
                        default=os.path.join('data', 'qlib_data'),
                        help='Qlib provider directory (default: data/qlib_data)')
    parser.add_argument('--output-dir', type=str,
                        default=os.path.join('workspace', 'outputs'),
                        help='Directory for final report artifacts')
    parser.add_argument('--screen-checkpoint-every', type=int, default=5,
                        help='Checkpoint screening cache every N newly processed factors')
    parser.add_argument('--progress-interval', type=int, default=60,
                        help='Heartbeat interval in seconds for long steps')
    parser.add_argument('--screen-progress-every', type=int, default=5,
                        help='Log screening progress every N factors')
    parser.add_argument('--composite-progress-every', type=int, default=5,
                        help='Log composite progress every N composites')
    args = parser.parse_args(argv)
    kernels = None if args.kernels <= 0 else args.kernels
    requested_kernel_label = "qlib default" if kernels is None else str(kernels)
    qlib_dir = Path(PROJECT_ROOT) / args.qlib_dir
    qlib_dir = qlib_dir.resolve()
    if str(args.end).strip().lower() == 'auto':
        args.end = _resolve_latest_backend_end_date(qlib_dir)
    output_dir = Path(PROJECT_ROOT) / args.output_dir
    output_dir = output_dir.resolve()

    logger.info("=" * 60)
    logger.info("  Batch Factor Screening (Qlib Expression Engine)")
    logger.info(f"  Date range: {args.start} to {args.end}")
    logger.info(f"  Horizons: {args.horizon}")
    logger.info(
        f"  Kernels: {'qlib default' if kernels is None else kernels}"
    )
    logger.info(f"  Screening engine: {args.engine}")
    logger.info(f"  Qlib provider: {qlib_dir}")
    logger.info(f"  Final output dir: {output_dir}")
    logger.info("=" * 60)

    # Step 1: Load factor library
    from src.alpha_research.factor_library import (
        get_factor_catalog, compute_factors, add_composites
    )

    catalog = get_factor_catalog(include_new_data=args.include_new_data)
    logger.info(
        f"Factor catalog: {len(catalog)} factors "
        f"({'including new-data factors' if args.include_new_data else 'existing data only'})"
    )
    from src.alpha_research.factor_library.catalog import get_composite_defs
    composite_defs = get_composite_defs()

    base_cache_context = _build_base_cache_context(
        args, kernels, catalog, composite_defs, qlib_dir
    )
    cache_root = Path(PROJECT_ROOT) / args.cache_dir
    cache_root = cache_root.resolve()
    run_cache_dir = _make_run_cache_dir(cache_root, base_cache_context)
    factors_path = run_cache_dir / 'base_factors.parquet'
    fwd_path = run_cache_dir / 'forward_returns.parquet'
    factors_meta_path = run_cache_dir / 'base_data.meta.json'
    composites_path = run_cache_dir / 'factors_with_composites.parquet'
    composites_meta_path = run_cache_dir / 'composites.meta.json'
    screening_path = run_cache_dir / f'screening_{args.engine}.parquet'
    screening_meta_path = run_cache_dir / f'screening_{args.engine}.meta.json'

    logger.info(f"Cache mode: {args.cache_mode}")
    if args.cache_mode != 'off':
        logger.info(f"Cache directory: {run_cache_dir}")
        run_cache_dir.mkdir(parents=True, exist_ok=True)

    # Step 2: Compute all factors via Qlib engine
    factors_key = _build_stage_cache_key(base_cache_context, 'factors')
    factors_df = None
    fwd_df = None
    effective_kernel_label = None
    if args.cache_mode == 'resume':
        factors_payload = _load_cache_payload(
            factors_meta_path,
            factors_key,
            [factors_path, fwd_path],
            'factor/fwd',
        )
        if factors_payload is not None:
            logger.info("Loading base factor cache...")
            factors_df = pd.read_parquet(factors_path)
            fwd_df = pd.read_parquet(fwd_path)
            effective_kernel_label = (
                factors_payload.get("state", {}).get("effective_kernels") or "unknown"
            )

    if factors_df is None or fwd_df is None:
        factors_df, fwd_df = compute_factors(
            catalog,
            args.start,
            args.end,
            horizons=args.horizon,
            qlib_dir=str(qlib_dir),
            kernels=kernels,
            progress_interval=args.progress_interval,
        )
        effective_kernel_label = (
            factors_df.attrs.get("qlib_effective_kernels") or requested_kernel_label
        )
        if args.cache_mode != 'off':
            logger.info("Writing base factor cache...")
            _write_stage_cache(
                factors_meta_path,
                factors_key,
                {
                    "complete": True,
                    "factor_shape": list(factors_df.shape),
                    "fwd_shape": list(fwd_df.shape),
                    "requested_kernels": requested_kernel_label,
                    "effective_kernels": effective_kernel_label,
                    "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                },
                [
                    lambda: _atomic_write_parquet(factors_df, factors_path),
                    lambda: _atomic_write_parquet(fwd_df, fwd_path),
                ],
            )
    if effective_kernel_label is None:
        effective_kernel_label = requested_kernel_label
    logger.info(
        f"Factor compute kernels: requested={requested_kernel_label}, "
        f"effective={effective_kernel_label}"
    )

    # Step 3: Add composite factors (Layer 2)
    composites_key = _build_stage_cache_key(
        base_cache_context,
        'composites',
        input_factor_names=sorted(factors_df.columns.tolist()),
    )
    composite_factors_df = None
    if args.cache_mode == 'resume':
        composites_payload = _load_cache_payload(
            composites_meta_path,
            composites_key,
            [composites_path],
            'composites',
        )
        if composites_payload is not None:
            logger.info("Loading composite cache...")
            composite_factors_df = pd.read_parquet(composites_path)

    if composite_factors_df is None:
        composite_factors_df = add_composites(
            factors_df,
            composite_defs=composite_defs,
            progress_every=args.composite_progress_every,
        )
        if args.cache_mode != 'off':
            logger.info("Writing composite cache...")
            _write_stage_cache(
                composites_meta_path,
                composites_key,
                {
                    "complete": True,
                    "factor_shape": list(composite_factors_df.shape),
                    "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                },
                [lambda: _atomic_write_parquet(composite_factors_df, composites_path)],
            )

    factors_df = composite_factors_df
    logger.info(f"Total factors: {factors_df.shape[1]}")

    # Step 4: Run IC screening
    screening_key = _build_stage_cache_key(
        base_cache_context,
        'screening',
        engine=args.engine,
        factor_names=sorted(factors_df.columns.tolist()),
    )
    existing_results = None
    if args.cache_mode == 'resume':
        screening_payload = _load_cache_payload(
            screening_meta_path,
            screening_key,
            [screening_path],
            f'screening ({args.engine})',
        )
        if screening_payload is not None:
            existing_results = pd.read_parquet(screening_path)
            state = screening_payload.get("state", {})
            logger.info(
                f"Loaded screening cache: {state.get('row_count', len(existing_results))} "
                f"rows, complete={state.get('complete', False)}"
            )

    checkpoint_callback = None
    if args.cache_mode != 'off':
        checkpoint_callback = _screening_checkpoint_writer(
            screening_path,
            screening_meta_path,
            screening_key,
        )

    logger.info("Running IC screening...")
    t0 = time.time()
    results = run_batch_screening(
        factors_df,
        fwd_df,
        horizons=args.horizon,
        progress_every=args.screen_progress_every,
        engine=args.engine,
        existing_results=existing_results,
        checkpoint_every=args.screen_checkpoint_every if args.cache_mode != 'off' else 0,
        checkpoint_callback=checkpoint_callback,
    )
    logger.info(f"Screening completed in {time.time()-t0:.1f}s")
    if args.cache_mode != 'off':
        logger.info("Writing final screening cache...")
        checkpoint_callback(results, True)

    # Step 5: Report
    classified, summary = generate_report(results, primary_h=args.horizon[0])

    # Step 6: Save
    output_dir.mkdir(parents=True, exist_ok=True)

    parquet_path = output_dir / 'factor_screening_results.parquet'
    csv_path = output_dir / 'factor_screening_report.csv'
    txt_path = output_dir / 'factor_screening_summary.txt'
    metadata_path = output_dir / 'factor_screening_run_metadata.json'

    classified.to_parquet(parquet_path)
    classified.to_csv(csv_path)
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(summary)
    _atomic_write_json(
        metadata_path,
        {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "start_date": args.start,
            "end_date": args.end,
            "horizons": list(args.horizon),
            "engine": args.engine,
            "include_new_data": bool(args.include_new_data),
            "requested_kernels": requested_kernel_label,
            "effective_kernels": effective_kernel_label,
            "qlib_dir": str(qlib_dir),
            "catalog_hash": base_cache_context["catalog_hash"],
            "composite_hash": base_cache_context["composite_hash"],
            "cache_mode": args.cache_mode,
            "cache_dir": str(run_cache_dir) if args.cache_mode != 'off' else None,
            "output_dir": str(output_dir),
            "factor_count": int(len(classified)),
            "grade_counts": classified['grade'].value_counts().to_dict() if 'grade' in classified.columns else {},
        },
    )

    logger.info(f"Results saved to {output_dir}")
    print("\n" + summary)
    logger.info("Done.")
    return {
        "output_dir": str(output_dir.resolve()),
        "summary": summary,
        "factor_count": int(len(classified)),
        "metadata_path": str(metadata_path.resolve()),
    }


def main(argv=None):
    from src.research_orchestrator.engine import _build_factor_screening_request_from_args, run_research

    parser = argparse.ArgumentParser(description="Batch Factor IC Screening")
    parser.add_argument('--start', type=str, default='2012-01-01',
                        help='Start date (default: 2012-01-01)')
    parser.add_argument('--end', type=str, default='2025-12-31',
                        help='End date (default: 2025-12-31, or use "auto" for latest provider date)')
    parser.add_argument('--horizon', type=int, nargs='+', default=[5, 10, 20],
                        help='Forward horizons in trading days (default: 5 10 20)')
    parser.add_argument('--include-new-data', action='store_true', default=True,
                        help='Include newer Phase 3 datasets in the catalog (default: on)')
    parser.add_argument('--exclude-new-data', action='store_false', dest='include_new_data',
                        help='Exclude newer Phase 3 datasets from the catalog')
    parser.add_argument('--outdir', type=str, default='workspace/research/alpha_mining/latest_backend_screening',
                        help='Output directory')
    parser.add_argument('--engine', type=str, choices=['qlib', 'local'], default='qlib',
                        help='Computation backend')
    parser.add_argument('--kernels', type=int, default=None,
                        help='Requested qlib worker count')
    parser.add_argument('--cache-mode', type=str, choices=['off', 'reuse', 'refresh'], default='reuse',
                        help='Cache behavior')
    parser.add_argument('--cache-dir', type=str, default='workspace/research/alpha_mining/cache',
                        help='Directory for reusable screening caches')
    parser.add_argument('--screen-checkpoint-every', type=int, default=25,
                        help='Checkpoint every N factors when screening cache is enabled')
    parser.add_argument('--screen-progress-every', type=int, default=25,
                        help='Log screening progress every N factors')
    args = parser.parse_args(argv)
    request = _build_factor_screening_request_from_args(args)
    result = run_research(request)
    return result.to_dict()


if __name__ == "__main__":
    main()
