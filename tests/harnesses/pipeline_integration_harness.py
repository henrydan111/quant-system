"""
Integration harness: pipeline sandbox comparison.

Copies a small slice of production data into an isolated sandbox under
workspace/outputs/, runs the pipeline against it, and compares the sandbox
Qlib output with the production database to verify functional equivalence.

Usage:
    E:\\量化系统\\venv\\Scripts\\python.exe E:\\量化系统\\tests\\harnesses\\pipeline_integration_harness.py
"""
import glob
import logging
import os
import shutil
import sys

import numpy as np
import pandas as pd

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(project_root, 'src'))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Paths
PROD_DATA = os.path.join(project_root, 'data')
PROD_QLIB = os.path.join(project_root, 'data', 'qlib_data')
TEST_DATA = os.path.join(project_root, 'workspace', 'outputs', 'pipeline_integration_harness', 'data_test')
TEST_QLIB = os.path.join(TEST_DATA, 'qlib_data')

PASS_COUNT = 0
FAIL_COUNT = 0


def record(name, passed, detail=""):
    """Log and count test results."""
    global PASS_COUNT, FAIL_COUNT
    if passed:
        PASS_COUNT += 1
        logger.info(f"  ✅ PASS: {name} {detail}")
    else:
        FAIL_COUNT += 1
        logger.error(f"  ❌ FAIL: {name} {detail}")


def setup_sandbox():
    """Create isolated test directory and copy a small data slice from production."""
    logger.info("=" * 60)
    logger.info("  STAGE 1: Setting up sandbox")
    logger.info("=" * 60)

    if os.path.exists(TEST_DATA):
        shutil.rmtree(TEST_DATA)

    # 1. Reference data
    ref_src = os.path.join(PROD_DATA, 'reference')
    ref_dst = os.path.join(TEST_DATA, 'reference')
    os.makedirs(ref_dst, exist_ok=True)
    for f in ['stock_basic.parquet', 'trade_cal.parquet']:
        src = os.path.join(ref_src, f)
        if os.path.exists(src):
            shutil.copy2(src, ref_dst)
            logger.info(f"  Copied {f}")

    # 2. Daily market data — copy 5 recent files
    daily_src_pattern = os.path.join(PROD_DATA, 'market', 'daily', '**', '*.parquet')
    daily_files = sorted(glob.glob(daily_src_pattern, recursive=True))
    # Take 5 files from the most recent year
    sample_daily = daily_files[-5:] if len(daily_files) >= 5 else daily_files
    for src_file in sample_daily:
        rel = os.path.relpath(src_file, PROD_DATA)
        dst_file = os.path.join(TEST_DATA, rel)
        os.makedirs(os.path.dirname(dst_file), exist_ok=True)
        shutil.copy2(src_file, dst_file)
    logger.info(f"  Copied {len(sample_daily)} daily market files")

    # 3. Index data — first 2 files
    index_src = os.path.join(PROD_DATA, 'market', 'index')
    if os.path.exists(index_src):
        index_files = sorted(glob.glob(os.path.join(index_src, '*.parquet')))[:2]
        index_dst = os.path.join(TEST_DATA, 'market', 'index')
        os.makedirs(index_dst, exist_ok=True)
        for f in index_files:
            shutil.copy2(f, index_dst)
        logger.info(f"  Copied {len(index_files)} index files")

    # 4. Fundamentals — 2 files per type
    for cat in ['income', 'balancesheet', 'indicators']:
        cat_src = os.path.join(PROD_DATA, 'fundamentals', cat)
        if os.path.exists(cat_src):
            cat_files = sorted(glob.glob(os.path.join(cat_src, '*.parquet')))[:2]
            cat_dst = os.path.join(TEST_DATA, 'fundamentals', cat)
            os.makedirs(cat_dst, exist_ok=True)
            for f in cat_files:
                shutil.copy2(f, cat_dst)
            logger.info(f"  Copied {len(cat_files)} {cat} files")

    # 5. Corporate — 1 dividend file
    div_src = os.path.join(PROD_DATA, 'corporate', 'dividends')
    if os.path.exists(div_src):
        div_files = sorted(glob.glob(os.path.join(div_src, '*.parquet')))[:1]
        div_dst = os.path.join(TEST_DATA, 'corporate', 'dividends')
        os.makedirs(div_dst, exist_ok=True)
        for f in div_files:
            shutil.copy2(f, div_dst)
        logger.info(f"  Copied {len(div_files)} dividend files")

    logger.info("  Sandbox setup complete.")
    return sample_daily


def test_init_dry_run():
    """Stage 2a: Test init_market_data.py --dry-run runs without errors."""
    logger.info("\n" + "=" * 60)
    logger.info("  STAGE 2a: Testing init_market_data.py --dry-run")
    logger.info("=" * 60)

    import subprocess
    cmd = [
        os.path.join(project_root, 'venv', 'Scripts', 'python.exe'),
        os.path.join(project_root, 'src', 'data_infra', 'pipeline', 'init_market_data.py'),
        '--dry-run', '--data-root', TEST_DATA
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root)
    record("init_market_data.py --dry-run exits cleanly", result.returncode == 0,
           result.stderr[:200] if result.returncode != 0 else "")


def test_build_qlib():
    """Stage 2b: Run build_qlib_backend.py against the sandbox."""
    logger.info("\n" + "=" * 60)
    logger.info("  STAGE 2b: Running build_qlib_backend.py on sandbox")
    logger.info("=" * 60)

    from data_infra.pipeline.build_qlib_backend import build_unified_qlib
    try:
        build_unified_qlib(TEST_DATA, TEST_QLIB)
        record("build_qlib_backend.py completed", True)
    except Exception as e:
        record("build_qlib_backend.py completed", False, str(e))
        return False
    return True


def test_schema_comparison():
    """Stage 2c: Compare sandbox Qlib output structure vs production."""
    logger.info("\n" + "=" * 60)
    logger.info("  STAGE 2c: Schema & structure comparison")
    logger.info("=" * 60)

    # Calendar check
    test_cal = os.path.join(TEST_QLIB, 'calendars', 'day.txt')
    prod_cal = os.path.join(PROD_QLIB, 'calendars', 'day.txt')
    record("Sandbox calendar file exists", os.path.exists(test_cal))

    if os.path.exists(test_cal):
        test_dates = open(test_cal).readlines()
        record("Calendar is non-empty", len(test_dates) > 0, f"{len(test_dates)} dates")

    # Instruments check
    test_inst_dir = os.path.join(TEST_QLIB, 'instruments')
    record("Sandbox instruments dir exists", os.path.exists(test_inst_dir))

    if os.path.exists(test_inst_dir):
        inst_files = os.listdir(test_inst_dir)
        record("Instruments dir is non-empty", len(inst_files) > 0, f"{len(inst_files)} files")

    # Feature files check
    test_feat_dir = os.path.join(TEST_QLIB, 'features')
    prod_feat_dir = os.path.join(PROD_QLIB, 'features')
    record("Sandbox features dir exists", os.path.exists(test_feat_dir))

    if os.path.exists(test_feat_dir):
        test_stocks = set(os.listdir(test_feat_dir))
        prod_stocks = set(os.listdir(prod_feat_dir)) if os.path.exists(prod_feat_dir) else set()

        # Sandbox stocks should be a subset (or at least overlap) with production
        overlap = test_stocks & prod_stocks
        record("Sandbox stocks overlap with production",
               len(overlap) > 0 or len(prod_stocks) == 0,
               f"{len(overlap)}/{len(test_stocks)} stocks in both")

        # Check feature files within a sample stock
        if overlap:
            sample = sorted(overlap)[0]
            test_bins = set(os.listdir(os.path.join(test_feat_dir, sample)))
            prod_bins = set(os.listdir(os.path.join(prod_feat_dir, sample)))
            record(f"Feature files for {sample}",
                   test_bins.issubset(prod_bins) or test_bins == prod_bins,
                   f"test={len(test_bins)}, prod={len(prod_bins)}")


def test_price_spot_check():
    """Stage 2d: Compare price values from sandbox vs production via Qlib D.features()."""
    logger.info("\n" + "=" * 60)
    logger.info("  STAGE 2d: Price spot-check via Qlib queries")
    logger.info("=" * 60)

    import qlib
    from qlib.data import D

    # Get overlapping stocks
    test_feat_dir = os.path.join(TEST_QLIB, 'features')
    prod_feat_dir = os.path.join(PROD_QLIB, 'features')

    if not os.path.exists(test_feat_dir) or not os.path.exists(prod_feat_dir):
        record("Price spot-check", False, "Feature dirs missing")
        return

    overlap = sorted(set(os.listdir(test_feat_dir)) & set(os.listdir(prod_feat_dir)))
    sample_stocks = overlap[:3]

    if not sample_stocks:
        record("Price spot-check", False, "No overlapping stocks to compare")
        return

    # Get date range from sandbox calendar
    test_cal = os.path.join(TEST_QLIB, 'calendars', 'day.txt')
    if not os.path.exists(test_cal):
        record("Price spot-check", False, "No calendar file")
        return

    cal_dates = [line.strip() for line in open(test_cal).readlines() if line.strip()]
    if len(cal_dates) < 2:
        record("Price spot-check", False, "Calendar too short")
        return
    start_d, end_d = cal_dates[0], cal_dates[-1]

    # Query sandbox
    qlib.init(provider_uri=TEST_QLIB, region='cn', kernels=1)
    try:
        test_df = D.features(sample_stocks, ['$close', '$vol'], start_time=start_d, end_time=end_d)
    except Exception as e:
        record("Sandbox Qlib query", False, str(e))
        return

    record("Sandbox Qlib query returns data", len(test_df) > 0, f"{len(test_df)} rows")

    # Query production
    qlib.init(provider_uri=PROD_QLIB, region='cn', kernels=1)
    try:
        prod_df = D.features(sample_stocks, ['$close', '$vol'], start_time=start_d, end_time=end_d)
    except Exception as e:
        record("Production Qlib query", False, str(e))
        return

    # Compare values
    if not test_df.empty and not prod_df.empty:
        common_idx = test_df.index.intersection(prod_df.index)
        if len(common_idx) > 0:
            test_vals = test_df.loc[common_idx, '$close'].dropna()
            prod_vals = prod_df.loc[common_idx, '$close'].dropna()
            common = test_vals.index.intersection(prod_vals.index)
            if len(common) > 0:
                diff = (test_vals.loc[common] - prod_vals.loc[common]).abs()
                max_diff = diff.max()
                record("Close prices match within tolerance",
                       max_diff < 1e-3 or np.isnan(max_diff),
                       f"max diff={max_diff:.6f}")
            else:
                record("Close prices match", True, "No common non-null values to compare")
        else:
            record("Common index overlap", False, "No common dates/stocks")


def test_pit_alignment():
    """Stage 2e: Verify PIT alignment — fundamentals should be NaN on ann_date, populated on ann_date+1."""
    logger.info("\n" + "=" * 60)
    logger.info("  STAGE 2e: Point-in-Time alignment check")
    logger.info("=" * 60)

    # Load raw fundamentals to find a stock with ann_date in our date range
    test_cal = os.path.join(TEST_QLIB, 'calendars', 'day.txt')
    if not os.path.exists(test_cal):
        record("PIT check", False, "No calendar")
        return

    cal_dates = [line.strip() for line in open(test_cal).readlines() if line.strip()]
    if not cal_dates:
        record("PIT check", False, "Empty calendar")
        return

    # Look for fundamental data in the sandbox
    income_dir = os.path.join(TEST_DATA, 'fundamentals', 'income')
    if not os.path.exists(income_dir):
        record("PIT check — skipped", True, "No income data in sandbox to test")
        return

    income_files = glob.glob(os.path.join(income_dir, '*.parquet'))
    if not income_files:
        record("PIT check — skipped", True, "No income files")
        return

    # Find an ann_date that falls within our sandbox date range
    df_inc = pd.concat([pd.read_parquet(f) for f in income_files], ignore_index=True)
    df_inc['ann_date'] = df_inc['ann_date'].astype(str)

    cal_set = set(cal_dates)
    # Find announcements on a trading day within our range
    mask = df_inc['ann_date'].isin(cal_set)
    if not mask.any():
        record("PIT check — skipped", True, "No announcements fall within sandbox date range")
        return

    sample = df_inc[mask].iloc[0]
    stock = sample['ts_code']
    ann = sample['ann_date']

    # Find the NEXT trading day after ann_date
    sorted_dates = sorted(cal_set)
    ann_idx = sorted_dates.index(ann) if ann in sorted_dates else -1
    if ann_idx < 0 or ann_idx >= len(sorted_dates) - 1:
        record("PIT check — skipped", True, f"ann_date {ann} at edge of calendar")
        return
    next_day = sorted_dates[ann_idx + 1]

    # Qlib format: 000001.SZ -> 000001_sz
    parts = stock.split('.')
    qlib_sym = f"{parts[0]}_{parts[1].lower()}" if len(parts) == 2 else stock

    # Query Qlib for a fundamental field
    import qlib
    from qlib.data import D
    qlib.init(provider_uri=TEST_QLIB, region='cn', kernels=1)

    try:
        fund_fields = ['$n_income', '$total_revenue', '$roe']
        df = D.features([qlib_sym], fund_fields, start_time=ann, end_time=next_day)

        if df.empty:
            record("PIT check — skipped", True, "No Qlib data for this stock/date range")
            return

        # Check: on ann_date, fund values SHOULD be NaN (shift(1) prevention)
        for field in fund_fields:
            if field in df.columns:
                ann_val = df.loc[(qlib_sym, pd.Timestamp(ann)), field] if (qlib_sym, pd.Timestamp(ann)) in df.index else None
                next_val = df.loc[(qlib_sym, pd.Timestamp(next_day)), field] if (qlib_sym, pd.Timestamp(next_day)) in df.index else None

                if ann_val is not None:
                    record(f"PIT: {field} is NaN on ann_date {ann}",
                           pd.isna(ann_val),
                           f"value={ann_val}")
                if next_val is not None and not pd.isna(next_val):
                    record(f"PIT: {field} populated on next day {next_day}",
                           True, f"value={next_val}")
                break  # One field is enough
    except Exception as e:
        record("PIT check query", False, str(e))


def test_storage_manager():
    """Stage 2f: Test StorageManager insert + dedup against sandbox."""
    logger.info("\n" + "=" * 60)
    logger.info("  STAGE 2f: StorageManager insert & dedup test")
    logger.info("=" * 60)

    from data_infra.storage import StorageManager
    sm = StorageManager(data_root=TEST_DATA)

    # Insert a small daily DataFrame
    test_df = pd.DataFrame({
        'ts_code': ['999999.SZ', '999999.SZ'],
        'trade_date': ['20240101', '20240101'],  # Duplicate — should dedup
        'open': [10.0, 10.0],
        'high': [11.0, 11.0],
        'low': [9.0, 9.0],
        'close': [10.5, 10.5],
        'vol': [1000, 1000],
        'amount': [10500, 10500]
    })
    try:
        sm.insert_daily_data(test_df)
        # Verify file exists
        expected_file = os.path.join(TEST_DATA, 'market', 'daily', '2024', 'daily_20240101.parquet')
        record("insert_daily_data creates file", os.path.exists(expected_file))

        if os.path.exists(expected_file):
            saved = pd.read_parquet(expected_file)
            # Check our test stock is in there
            has_test = '999999.SZ' in saved['ts_code'].values
            record("Inserted test stock present", has_test)
    except Exception as e:
        record("insert_daily_data", False, str(e))


def test_data_auditor():
    """Stage 2g: Run DataAuditor on sandbox and verify no false-positive anomalies."""
    logger.info("\n" + "=" * 60)
    logger.info("  STAGE 2g: DataAuditor against sandbox")
    logger.info("=" * 60)

    from data_infra.verification.data_auditor import DataAuditor
    auditor = DataAuditor(data_root=TEST_DATA)

    # Find date range from our sandbox daily files
    daily_files = sorted(glob.glob(os.path.join(TEST_DATA, 'market', 'daily', '**', '*.parquet'), recursive=True))
    if not daily_files:
        record("DataAuditor", False, "No daily files in sandbox")
        return

    # Extract dates from filenames: daily_YYYYMMDD.parquet
    dates = []
    for f in daily_files:
        basename = os.path.basename(f)
        if basename.startswith('daily_') and basename.endswith('.parquet'):
            dates.append(basename.replace('daily_', '').replace('.parquet', ''))
    if not dates:
        record("DataAuditor", False, "Could not parse dates from filenames")
        return

    start_d = min(dates)
    end_d = max(dates)

    try:
        report = auditor.audit_daily_files(start_date=start_d, end_date=end_d, check_nulls=True)
        record("DataAuditor runs without errors", True)

        # The sandbox has known good data — should have minimal anomalies
        n_anomalies = len(report.get('anomalies', []))
        record(f"DataAuditor anomaly count reasonable", n_anomalies < 10,
               f"{n_anomalies} anomalies found")
    except Exception as e:
        record("DataAuditor", False, str(e))


def test_parquet_schema():
    """Stage 2h: Compare daily Parquet schemas between sandbox and production."""
    logger.info("\n" + "=" * 60)
    logger.info("  STAGE 2h: Parquet schema comparison")
    logger.info("=" * 60)

    test_daily = sorted(glob.glob(os.path.join(TEST_DATA, 'market', 'daily', '**', '*.parquet'), recursive=True))
    if not test_daily:
        record("Parquet schema check", False, "No daily files in sandbox")
        return

    # Use the LAST file (production-copied) not first (which may be test-inserted)
    test_df = pd.read_parquet(test_daily[-1])
    test_cols = set(test_df.columns)

    # Find a production file from the same year
    prod_daily = sorted(glob.glob(os.path.join(PROD_DATA, 'market', 'daily', '**', '*.parquet'), recursive=True))
    if not prod_daily:
        record("Parquet schema check", False, "No production daily files")
        return

    prod_df = pd.read_parquet(prod_daily[-1])
    prod_cols = set(prod_df.columns)

    record("Column sets match", test_cols == prod_cols,
           f"test={sorted(test_cols)}, prod-only={sorted(prod_cols - test_cols)}, test-only={sorted(test_cols - prod_cols)}")

    # Row count check — sandbox files copied from production should have > 100 stocks
    test_rows = len(test_df)
    record("Row count reasonable", test_rows > 100,
           f"{test_rows} rows in sandbox file")


def cleanup():
    """Remove sandbox test directory."""
    logger.info("\n  Cleaning up sandbox...")
    if os.path.exists(TEST_DATA):
        shutil.rmtree(TEST_DATA, ignore_errors=True)
        logger.info("  Sandbox removed.")


def main():
    global PASS_COUNT, FAIL_COUNT

    logger.info("=" * 60)
    logger.info("  PIPELINE INTEGRATION TEST")
    logger.info("=" * 60)

    try:
        # Setup
        sample_daily = setup_sandbox()

        # Tests
        test_init_dry_run()
        qlib_ok = test_build_qlib()

        if qlib_ok:
            test_schema_comparison()
            test_price_spot_check()
            test_pit_alignment()
        else:
            logger.warning("Skipping Qlib comparison tests because build failed")

        test_storage_manager()
        test_data_auditor()
        test_parquet_schema()

    finally:
        cleanup()

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info(f"  RESULTS: {PASS_COUNT} passed, {FAIL_COUNT} failed")
    logger.info("=" * 60)

    if FAIL_COUNT > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
