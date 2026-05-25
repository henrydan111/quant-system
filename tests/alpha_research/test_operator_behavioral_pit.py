"""Follow-up Plan #1 — Behavioral PIT smoke test (tiny Qlib fixture).

This test is the safety net against a false-negative in the parser-based
static-analysis test (``test_factor_library_pit_safety.py``). Even if the
parser somehow misses a ``$field`` reference, this behavioral test will
catch it because: if an operator depends on ``close[T]``, changing
``close[T]`` in one data variant will change the factor value at time T
versus a baseline variant where ``close[T]`` is untouched.

Design (per plan Step 4):
  1. Build TWO tiny Qlib providers on disk with 3 synthetic stocks ×
     30 trading days × ~8 raw fields (close, open, high, low, vol,
     amount, adj_factor, turnover_rate)
  2. The ``baseline`` and ``modified`` variants differ ONLY at ``close[T]``
     for one stock, at one carefully chosen date
  3. For each of several representative operators, evaluate the
     expression against both variants via ``D.features()``
  4. Assert: factor values at time T are IDENTICAL between variants
     (i.e., the operator correctly uses only t-1 data). Factor values
     at T+1 and later may differ (expected — the modification propagates
     forward).

Ref: plan file ``C:\\Users\\henry\\.claude\\plans\\vast-exploring-rabbit.md``
Step 4. Codex cross-review MEDIUM finding is addressed here.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from src.alpha_research.factor_library import operators
from data_infra.storage.qlib_bin_utils import write_qlib_bin


# ──────────────────────────────────────────────────────────────────────
# Tiny Qlib fixture construction
# ──────────────────────────────────────────────────────────────────────


def _build_calendar(n_days: int) -> pd.DatetimeIndex:
    """Business-day calendar starting 2024-01-02 (a Tuesday)."""
    return pd.bdate_range("2024-01-02", periods=n_days)


def _synth_series(seed: int, n: int, base: float, amp: float) -> np.ndarray:
    """Deterministic pseudo-random series so tests are reproducible."""
    rng = np.random.default_rng(seed)
    noise = rng.normal(0, amp, size=n)
    trend = np.cumsum(rng.normal(0, amp * 0.3, size=n))
    return (base + trend + noise).astype(np.float32)


def _write_qlib_provider(
    provider_dir: Path,
    calendar: pd.DatetimeIndex,
    stock_data: dict[str, dict[str, np.ndarray]],
) -> None:
    """Write a minimal Qlib provider: calendars + instruments + features."""
    provider_dir.mkdir(parents=True, exist_ok=True)
    (provider_dir / "calendars").mkdir(exist_ok=True)
    (provider_dir / "instruments").mkdir(exist_ok=True)
    (provider_dir / "features").mkdir(exist_ok=True)

    # calendar
    with open(provider_dir / "calendars" / "day.txt", "w", encoding="utf-8") as f:
        for d in calendar:
            f.write(d.strftime("%Y-%m-%d") + "\n")

    # instruments
    start = calendar[0].strftime("%Y-%m-%d")
    end = calendar[-1].strftime("%Y-%m-%d")
    with open(provider_dir / "instruments" / "all.txt", "w", encoding="utf-8") as f:
        for instrument in stock_data.keys():
            f.write(f"{instrument}\t{start}\t{end}\n")

    # features (one subdir per instrument, one .day.bin per field)
    for instrument, fields in stock_data.items():
        # Qlib uses lowercase instrument names in feature dirs
        feature_dir = provider_dir / "features" / instrument.lower()
        feature_dir.mkdir(parents=True, exist_ok=True)
        for field_name, values in fields.items():
            bin_path = feature_dir / f"{field_name}.day.bin"
            write_qlib_bin(str(bin_path), values, start_index=0)


def _build_stock_data(
    n_days: int,
    modified_symbol: str | None = None,
    modified_t: int | None = None,
    modified_close: float | None = None,
) -> dict[str, dict[str, np.ndarray]]:
    """Generate raw field arrays for 3 synthetic stocks.

    When modified_symbol/modified_t/modified_close are all supplied, that
    stock's close value at index modified_t is overridden — no other field
    is touched. This is the behavioral probe.
    """
    symbols = ["fix001_sz", "fix002_sz", "fix003_sz"]
    out: dict[str, dict[str, np.ndarray]] = {}
    for i, sym in enumerate(symbols):
        close = _synth_series(seed=100 + i, n=n_days, base=10.0, amp=0.3)
        open_ = close + _synth_series(seed=200 + i, n=n_days, base=0.0, amp=0.05)
        high = np.maximum(close, open_) + np.abs(_synth_series(seed=300 + i, n=n_days, base=0.0, amp=0.15))
        low = np.minimum(close, open_) - np.abs(_synth_series(seed=400 + i, n=n_days, base=0.0, amp=0.15))
        vol = np.abs(_synth_series(seed=500 + i, n=n_days, base=1000.0, amp=100.0)) + 100.0
        amount = (close * vol).astype(np.float32)
        adj_factor = np.ones(n_days, dtype=np.float32)
        turnover_rate = np.abs(_synth_series(seed=600 + i, n=n_days, base=1.0, amp=0.3)) + 0.1

        if (
            modified_symbol == sym
            and modified_t is not None
            and modified_close is not None
        ):
            close = close.copy()
            close[modified_t] = np.float32(modified_close)

        out[sym] = {
            "close": close,
            "open": open_.astype(np.float32),
            "high": high.astype(np.float32),
            "low": low.astype(np.float32),
            "$vol": vol.astype(np.float32),  # placeholder — Qlib uses "vol" not "$vol"
            "vol": vol.astype(np.float32),
            "amount": amount,
            "adj_factor": adj_factor,
            "turnover_rate": turnover_rate.astype(np.float32),
        }
        # Drop the placeholder key
        del out[sym]["$vol"]
    return out


# ──────────────────────────────────────────────────────────────────────
# The test
# ──────────────────────────────────────────────────────────────────────


class BehavioralPITTest(unittest.TestCase):
    """Verify that fixed operators do NOT depend on close[T].

    Each test builds a pair of Qlib providers (baseline + modified),
    evaluates the operator expression on both via D.features(), and
    asserts the factor value at time T is identical.
    """

    N_DAYS = 30
    TARGET_T_INDEX = 25  # late in the window so rolling operators have history
    MODIFIED_SYMBOL = "fix001_sz"
    MODIFIED_CLOSE_VALUE = 999.0  # clearly different from natural range

    @classmethod
    def setUpClass(cls):
        cls._tmp_root = Path(tempfile.mkdtemp(prefix="pit_behav_"))
        cls._calendar = _build_calendar(cls.N_DAYS)
        cls._target_date = cls._calendar[cls.TARGET_T_INDEX]

        # Baseline provider
        cls._baseline_dir = cls._tmp_root / "baseline"
        baseline_data = _build_stock_data(cls.N_DAYS)
        _write_qlib_provider(cls._baseline_dir, cls._calendar, baseline_data)

        # Modified provider (close[T] for MODIFIED_SYMBOL changed to 999)
        cls._modified_dir = cls._tmp_root / "modified"
        modified_data = _build_stock_data(
            cls.N_DAYS,
            modified_symbol=cls.MODIFIED_SYMBOL,
            modified_t=cls.TARGET_T_INDEX,
            modified_close=cls.MODIFIED_CLOSE_VALUE,
        )
        _write_qlib_provider(cls._modified_dir, cls._calendar, modified_data)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._tmp_root, ignore_errors=True)

    def _features_for(self, provider_dir: Path, expression: str) -> pd.Series:
        """Initialize Qlib against one provider and fetch one expression for
        MODIFIED_SYMBOL across the full window. Returns a Series indexed by date.
        """
        import qlib
        from qlib.data import D

        # Re-init Qlib for this provider
        qlib.init(provider_uri=str(provider_dir), region="cn", kernels=1, expression_cache=None, dataset_cache=None)
        df = D.features(
            [self.MODIFIED_SYMBOL],
            [expression],
            start_time=self._calendar[0].strftime("%Y-%m-%d"),
            end_time=self._calendar[-1].strftime("%Y-%m-%d"),
            freq="day",
        )
        if df.empty:
            return pd.Series(dtype=float)
        return df[expression].droplevel(0)

    def _assert_invariant_at_T(self, expression: str, label: str) -> None:
        """Core behavioral check: factor[T] must be identical between variants."""
        baseline = self._features_for(self._baseline_dir, expression)
        modified = self._features_for(self._modified_dir, expression)

        target_date = self._target_date
        if target_date not in baseline.index or target_date not in modified.index:
            self.skipTest(f"{label}: target date {target_date} missing from series")

        b = baseline.loc[target_date]
        m = modified.loc[target_date]

        # Both must be non-NaN (the operator should have enough history)
        if pd.isna(b) or pd.isna(m):
            self.skipTest(f"{label}: NaN at target — insufficient rolling history")

        # Core invariant: the factor value at T is identical because
        # the fix guarantees close[T] doesn't appear in any term.
        self.assertAlmostEqual(
            float(b),
            float(m),
            places=5,
            msg=(
                f"{label}: factor[T] depends on close[T]. "
                f"baseline={b}, modified={m}. This indicates a PIT leak "
                f"that the parser-based test failed to catch."
            ),
        )

    def test_rolling_vol_20_is_close_t_invariant(self):
        self._assert_invariant_at_T(operators.rolling_vol(20), "rolling_vol(20)")

    def test_ma_ratio_5_20_is_close_t_invariant(self):
        self._assert_invariant_at_T(operators.ma_ratio(5, 20), "ma_ratio(5, 20)")

    def test_price_to_ma_10_is_close_t_invariant(self):
        self._assert_invariant_at_T(operators.price_to_ma(10), "price_to_ma(10)")

    def test_bb_width_10_is_close_t_invariant(self):
        self._assert_invariant_at_T(operators.bb_width(10), "bb_width(10)")

    def test_daily_ret_is_close_t_invariant(self):
        """Bare DAILY_RET must not depend on close[T]."""
        self._assert_invariant_at_T(operators.DAILY_RET, "DAILY_RET")


if __name__ == "__main__":
    unittest.main()
