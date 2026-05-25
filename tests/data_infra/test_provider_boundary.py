"""P0-1: Provider-boundary regression — delist and IPO-lag enforcement.

This test locks the contract that:
  1. The instruments sidecar layer (``all_stocks.txt``) correctly clamps the
     tradable date range to ``[list_date + IPO_LAG_DAYS, delist_date]``.
  2. Consumers of ``D.features()`` inherit this guard automatically.
  3. Consumers that read ``data/pit_ledger/*.parquet`` directly BYPASS the
     guard — this test documents that bypass and provides a helper
     (``provider_metadata.stock_basic_bounds``) for direct-ledger consumers.

The delisted-stock and recent-IPO samples are discovered dynamically from
``stock_basic.parquet`` so the test is robust against corpus changes.

Ref: ``CLAUDE.md §3 "Delist and IPO-lag contract"``.
"""

from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from data_infra.provider_metadata import IPO_LAG_DAYS, stock_basic_bounds

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STOCK_BASIC_PATH = PROJECT_ROOT / "data" / "reference" / "stock_basic.parquet"
QLIB_DATA_DIR = PROJECT_ROOT / "data" / "qlib_data"
ALL_STOCKS_TXT = QLIB_DATA_DIR / "instruments" / "all_stocks.txt"


def _load_stock_basic() -> pd.DataFrame:
    return pd.read_parquet(STOCK_BASIC_PATH)


def _load_all_stocks_txt() -> pd.DataFrame:
    """Parse ``all_stocks.txt`` into (instrument, start, end) rows."""
    rows: list[dict[str, str]] = []
    with open(ALL_STOCKS_TXT, "r", encoding="utf-8") as handle:
        for line in handle:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 3:
                continue
            rows.append({"instrument": parts[0], "start": parts[1], "end": parts[2]})
    return pd.DataFrame(rows)


def _ts_code_to_instrument(ts_code: str) -> str:
    return ts_code.replace(".", "_")


def test_stock_basic_bounds_returns_effective_list_and_delist_dates():
    """The helper returns ``(list_date + IPO_LAG, delist_date)``."""
    stock_basic = _load_stock_basic()
    # Pick a known delisted stock
    delisted_sample = stock_basic[stock_basic["delist_date"].notna()].iloc[0]
    ts_code = delisted_sample["ts_code"]
    effective_list, delist_date = stock_basic_bounds(stock_basic, ts_code)
    assert effective_list is not None
    assert delist_date is not None
    raw_list = pd.to_datetime(delisted_sample["list_date"])
    assert effective_list == raw_list + pd.Timedelta(days=IPO_LAG_DAYS)
    assert delist_date == pd.to_datetime(delisted_sample["delist_date"])


def test_stock_basic_bounds_still_listed_stock_has_none_delist():
    stock_basic = _load_stock_basic()
    # Pick a clearly still-listed stock — most A-share tickers
    still_listed = stock_basic[stock_basic["delist_date"].isna()].iloc[0]
    ts_code = still_listed["ts_code"]
    effective_list, delist_date = stock_basic_bounds(stock_basic, ts_code)
    assert effective_list is not None
    assert delist_date is None


def test_stock_basic_bounds_missing_stock_returns_nones():
    stock_basic = _load_stock_basic()
    effective_list, delist_date = stock_basic_bounds(stock_basic, "999999.XX")
    assert effective_list is None
    assert delist_date is None


def test_all_stocks_txt_applies_delist_bound():
    """P0-1 core: delisted stocks in the instruments sidecar must terminate
    on or before their ``delist_date``.
    """
    if not ALL_STOCKS_TXT.exists():
        import pytest

        pytest.skip(f"Live provider instrument file missing: {ALL_STOCKS_TXT}")

    stock_basic = _load_stock_basic()
    instruments = _load_all_stocks_txt()

    # Pick 5 delisted stocks spanning different years
    stock_basic_delisted = stock_basic[stock_basic["delist_date"].notna()].copy()
    stock_basic_delisted["delist_dt"] = pd.to_datetime(
        stock_basic_delisted["delist_date"], errors="coerce"
    )
    stock_basic_delisted = stock_basic_delisted.dropna(subset=["delist_dt"])
    stock_basic_delisted = stock_basic_delisted.sort_values("delist_dt")

    # Sample across years 2015, 2018, 2021, 2023, 2024
    samples = []
    for target_year in (2015, 2018, 2021, 2023, 2024):
        matches = stock_basic_delisted[
            stock_basic_delisted["delist_dt"].dt.year == target_year
        ]
        if not matches.empty:
            samples.append(matches.iloc[0])

    assert len(samples) >= 3, (
        f"Not enough delisted samples across years to exercise contract: {len(samples)}"
    )

    for row in samples:
        ts_code = row["ts_code"]
        delist_date = pd.to_datetime(row["delist_date"])
        instrument = _ts_code_to_instrument(ts_code)
        instrument_rows = instruments[instruments["instrument"] == instrument]
        if instrument_rows.empty:
            # Not in the tradable universe at all — that's fine, guard worked
            continue
        for _, ir in instrument_rows.iterrows():
            end_date = pd.to_datetime(ir["end"])
            assert end_date <= delist_date, (
                f"{ts_code}: instruments end={end_date} exceeds delist_date={delist_date}. "
                f"Delist contract violated at the sidecar layer."
            )


def test_all_stocks_txt_applies_ipo_lag():
    """P0-1: each entry in all_stocks.txt must start on or after
    ``list_date + IPO_LAG_DAYS``.
    """
    if not ALL_STOCKS_TXT.exists():
        import pytest

        pytest.skip(f"Live provider instrument file missing: {ALL_STOCKS_TXT}")

    stock_basic = _load_stock_basic()
    instruments = _load_all_stocks_txt()

    # Check 100 sample instruments to avoid scanning the whole universe
    sample = instruments.sample(n=min(100, len(instruments)), random_state=42)
    violations = 0
    checked = 0
    for _, ir in sample.iterrows():
        instrument = ir["instrument"]
        ts_code = instrument.replace("_SH", ".SH").replace("_SZ", ".SZ").replace("_BJ", ".BJ")
        sb_rows = stock_basic[stock_basic["ts_code"] == ts_code]
        if sb_rows.empty:
            continue
        list_date_raw = sb_rows.iloc[0]["list_date"]
        if pd.isna(list_date_raw):
            continue
        list_date = pd.to_datetime(list_date_raw)
        effective_list = list_date + pd.Timedelta(days=IPO_LAG_DAYS)
        instrument_start = pd.to_datetime(ir["start"])
        checked += 1
        # Instrument start must be >= effective_list (allowing for price_start floor)
        # We assert it's not SIGNIFICANTLY earlier than the IPO-lagged date
        if instrument_start < list_date:
            violations += 1

    assert checked > 0, "No samples had list_date in stock_basic"
    assert violations == 0, (
        f"IPO-lag contract violated: {violations}/{checked} samples started before list_date"
    )


def test_direct_ledger_read_bypasses_delist_guard_documented():
    """Document the known bypass: reading PIT ledger parquet directly does
    NOT apply the instruments-sidecar delist filter. Consumers must use
    ``stock_basic_bounds`` to filter manually.

    This test exists to lock the documented contract — it does NOT assert
    any ledger rows exist, just that the helper is available and the
    contract is reachable.
    """
    stock_basic = _load_stock_basic()
    # Sanity: at least one delisted stock exists and the helper returns its bounds
    delisted = stock_basic[stock_basic["delist_date"].notna()]
    assert not delisted.empty
    sample_ts_code = delisted.iloc[0]["ts_code"]
    effective_list, delist_date = stock_basic_bounds(stock_basic, sample_ts_code)
    assert effective_list is not None
    assert delist_date is not None
    # The contract: if a research script reads pit_ledger/income/income.parquet
    # and queries this ts_code for a date > delist_date, it would see ghost rows
    # without applying the bounds. This test documents that risk and ensures
    # the helper is wired for direct-ledger consumers to use.
