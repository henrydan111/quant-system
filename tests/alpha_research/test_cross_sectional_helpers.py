"""Phase 7 — PIT-safety hardening of the cross-sectional Layer-1 helpers.

`cs_rank`/`cs_zscore`/`cs_demean`/`winsorize` previously grouped by POSITIONAL level 0. On an
`(instrument, datetime)` panel that ranks each stock ACROSS TIME, so the value at factor date
`t` absorbs that stock's values at `t+1 … end` — a lookahead leak inside the IS window (GPT
Phase-7 review: this is a PIT leak, not merely a correctness bug). The helpers now group by the
DATE level by NAME (dtype fallback; fail-closed when no datetime level). These tests pin
order-invariance, the no-future-dependence leakage property, and the fail-closed contract.
"""

import unittest

import numpy as np
import pandas as pd

from src.alpha_research.factor_library.operators import (
    cs_rank,
    cs_zscore,
    cs_demean,
    winsorize,
    _date_level_key,
)


def _panel(order):
    """3 stocks × 4 dates; value = stock_idx + 10*date_idx so the per-DATE ordering and the
    per-STOCK (time-series) ordering are DIFFERENT — the two groupings give distinct results."""
    insts = ["000001_SZ", "000002_SZ", "000003_SZ"]
    dates = pd.to_datetime(["2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07"])
    recs = []
    for d_i, d in enumerate(dates):
        for s_i, s in enumerate(insts):
            recs.append({"instrument": s, "datetime": d, "v": float(s_i + 10 * d_i)})
    long = pd.DataFrame(recs)
    idx = pd.MultiIndex.from_frame(long[list(order)])
    return long.set_index(idx)["v"]


def _canon(series):
    return (series.rename("v").reset_index()[["datetime", "instrument", "v"]]
            .sort_values(["datetime", "instrument"]).reset_index(drop=True))


class CrossSectionalOrderInvarianceTests(unittest.TestCase):
    def _assert_order_invariant(self, fn):
        a = fn(_panel(("datetime", "instrument")))   # the compute_factors order
        b = fn(_panel(("instrument", "datetime")))    # the legacy/other order
        pd.testing.assert_frame_equal(_canon(a), _canon(b))

    def test_cs_rank_order_invariant(self):
        self._assert_order_invariant(cs_rank)

    def test_cs_zscore_order_invariant(self):
        self._assert_order_invariant(cs_zscore)

    def test_cs_demean_order_invariant(self):
        self._assert_order_invariant(cs_demean)

    def test_winsorize_order_invariant(self):
        self._assert_order_invariant(lambda s: winsorize(s, 0.1, 0.9))

    def test_cs_rank_is_per_date_not_per_stock(self):
        # On an (instrument, datetime) panel the OLD groupby(level=0) ranked per STOCK; the
        # hardened helper ranks per DATE. Pin that it equals the per-date rank and DIFFERS from
        # the per-stock (leaky) rank.
        s = _panel(("instrument", "datetime"))
        got = cs_rank(s).sort_index()
        per_date = s.groupby(s.index.get_level_values("datetime")).rank(pct=True).sort_index()
        per_stock = s.groupby(s.index.get_level_values("instrument")).rank(pct=True).sort_index()
        pd.testing.assert_series_equal(got, per_date, check_names=False)
        self.assertFalse(got.equals(per_stock))

    def test_cs_zscore_preserves_zero_std_nan(self):
        # GPT must-keep: a constant cross-section -> std 0 -> NaN (not inf).
        dates = pd.to_datetime(["2020-01-02", "2020-01-02"])
        idx = pd.MultiIndex.from_arrays([dates, ["x", "y"]], names=["datetime", "instrument"])
        s = pd.Series([5.0, 5.0], index=idx)  # constant on the date
        out = cs_zscore(s)
        self.assertTrue(out.isna().all())
        self.assertFalse(np.isinf(out.to_numpy()).any())


class NoFutureDependenceLeakageTests(unittest.TestCase):
    def test_mutating_future_value_does_not_change_current_rank(self):
        # The strongest leakage check: cs_rank[t] must NOT depend on value[t+k]. On the
        # (instrument, datetime) panel the OLD per-stock grouping WOULD propagate a future
        # mutation into the stock's earlier-date rank.
        s = _panel(("instrument", "datetime")).copy()
        r0 = cs_rank(s)
        last_date = s.index.get_level_values("datetime").max()
        # mutate a FUTURE row for stock 0 to a value that REORDERS its time-series (below its
        # first-date value) — a per-STOCK grouping (the old leak) would shift the stock's
        # EARLIER-date rank; a per-DATE grouping leaves the first date's cross-section untouched.
        s.loc[("000001_SZ", last_date)] = -999.0
        r1 = cs_rank(s)
        first_date = s.index.get_level_values("datetime").min()
        pd.testing.assert_series_equal(
            r0.xs(first_date, level="datetime").sort_index(),
            r1.xs(first_date, level="datetime").sort_index(),
        )


class DateLevelKeyContractTests(unittest.TestCase):
    def test_prefers_datetime_name_either_order(self):
        di = _panel(("datetime", "instrument"))
        idd = _panel(("instrument", "datetime"))
        self.assertEqual(_date_level_key(di), "datetime")
        self.assertEqual(_date_level_key(idd), "datetime")

    def test_dtype_fallback_when_unnamed(self):
        dates = pd.to_datetime(["2020-01-02", "2020-01-02", "2020-01-03", "2020-01-03"])
        idx = pd.MultiIndex.from_arrays([["x", "y", "x", "y"], dates])  # names=None, dt at lvl 1
        s = pd.Series([1.0, 2.0, 3.0, 4.0], index=idx)
        self.assertEqual(_date_level_key(s), 1)

    def test_fails_closed_without_any_datetime_level(self):
        idx = pd.MultiIndex.from_tuples([("a", "x"), ("a", "y")], names=["foo", "bar"])
        s = pd.Series([1.0, 2.0], index=idx)
        with self.assertRaises(ValueError):
            _date_level_key(s)
        with self.assertRaises(ValueError):
            cs_rank(s)


if __name__ == "__main__":
    unittest.main()
