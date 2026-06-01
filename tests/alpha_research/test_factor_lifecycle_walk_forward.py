"""Phase 4 slice 4 — the leakage-critical IS-only walk-forward validator.

These are the tests this whole phase exists for: the formal mode must NEVER load a factor
date OR a label-realization date past ``is_end`` (the forward-return label is future-
looking). Fixtures use a synthetic injected trading calendar — no Qlib.
"""

import unittest

import numpy as np
import pandas as pd

from src.alpha_research.walk_forward import TimeSplit, build_walk_forward_folds
from src.alpha_research.factor_lifecycle import walk_forward_validation as wf
from src.alpha_research.factor_lifecycle.walk_forward_validation import (
    IsWindowedPanel,
    IsEndLeakageError,
    NoHeldoutBlockError,
    build_is_windowed_panel,
    load_is_windowed_panel,
    realization_date,
    last_usable_factor_date,
    run_is_walk_forward,
)


def _weekly_calendar(start="2014-01-03", end="2020-12-25"):
    return pd.DatetimeIndex(pd.date_range(start, end, freq="W-FRI"))


def _panel(open_days, instruments=80, seed=0):
    insts = [f"{i:06d}_SZ" for i in range(instruments)]
    index = pd.MultiIndex.from_product([insts, open_days], names=["instrument", "datetime"])
    rng = np.random.default_rng(seed)
    # adjusted close as a positive random walk per instrument
    steps = rng.standard_normal(len(index)) * 0.02
    adj = pd.Series(10.0 * np.exp(steps.cumsum() % 3), index=index).sort_index()
    factor = pd.Series(rng.standard_normal(len(index)), index=index).sort_index()
    return pd.DataFrame({"f1": factor}), adj


class FoldConfigTests(unittest.TestCase):
    def test_default_5_2_1_folds_zero_for_is_window(self):
        # design-review must-fix #2 (pinned): the DEFAULT config cannot produce a test fold
        # for the 7-year 2014-2020 IS window.
        folds, holdout = build_walk_forward_folds("2014-01-01", "2020-12-31")
        self.assertEqual(folds, [])
        self.assertIsNone(holdout)

    def test_3_1_1_yields_multiple_folds(self):
        folds, _ = build_walk_forward_folds(
            "2014-01-01", "2020-12-31", train_years=3, validation_years=1, test_years=1,
        )
        self.assertGreaterEqual(len(folds), 2)  # 2018, 2019, 2020 test years
        for f in folds:
            self.assertLessEqual(pd.Timestamp(f.test_end), pd.Timestamp("2020-12-31"))


class TradingCalendarTests(unittest.TestCase):
    def test_realization_and_last_usable_are_trading_day_based(self):
        cal = _weekly_calendar()
        # realization of cal[10] at horizon 4 == cal[14]
        self.assertEqual(realization_date(cal[10], 4, cal), cal[14])
        # last usable factor date for is_end=cal[-1] horizon 4 == cal[-5]
        self.assertEqual(last_usable_factor_date(cal[-1], 4, cal), cal[-5])
        # past the calendar -> NaT
        self.assertTrue(pd.isna(realization_date(cal[-1], 4, cal)))


class IsWindowedPanelLeakageTests(unittest.TestCase):
    def test_rejects_factor_date_past_is_end(self):
        cal = _weekly_calendar()
        panel, adj = _panel(cal, instruments=10)
        label = (adj.groupby(level="instrument").shift(-4) / adj - 1).dropna()
        aligned = panel.loc[panel.index.intersection(label.index)]
        # is_end set BEFORE the panel's max date -> factor date past is_end
        bad_is_end = cal[-20]
        with self.assertRaises(IsEndLeakageError):
            IsWindowedPanel(factor_panel=aligned, label=label.loc[aligned.index],
                            is_end=bad_is_end, horizon=4, open_days=cal)

    def test_rejects_label_realizing_past_is_end(self):
        cal = _weekly_calendar()
        # factor dates up to is_end (== cal[k]); horizon 4 -> realization cal[k+4] > is_end
        k = len(cal) - 10
        is_end = cal[k]
        insts = [f"{i:06d}_SZ" for i in range(8)]
        dates = cal[: k + 1]  # max factor date == is_end
        idx = pd.MultiIndex.from_product([insts, dates], names=["instrument", "datetime"])
        panel = pd.DataFrame({"f1": np.arange(len(idx), dtype=float)}, index=idx)
        label = pd.Series(0.0, index=idx)
        with self.assertRaises(IsEndLeakageError):  # label realizes cal[k+4] > is_end
            IsWindowedPanel(factor_panel=panel, label=label, is_end=is_end, horizon=4, open_days=cal)

    def test_build_drops_late_dates_and_validates(self):
        cal = _weekly_calendar()
        panel, adj = _panel(cal, instruments=20)
        is_end = cal[-1]
        wp = build_is_windowed_panel(panel, adj, is_end=is_end, horizon=4, trade_cal=cal)
        # the last 4 weeks were dropped (label NaN) -> max factor date <= is_end - 4 weeks
        self.assertLessEqual(wp.max_factor_date, cal[-5])
        self.assertLessEqual(wp.max_label_realization_date, pd.Timestamp(is_end))


class LoadIsPanelSpyTests(unittest.TestCase):
    def test_load_uses_horizons_none_and_end_at_is_end(self):
        cal = _weekly_calendar()
        panel, adj = _panel(cal, instruments=20)
        ts = TimeSplit("2014-01-01", "2020-12-31", "2021-01-01", "2022-01-01")
        calls = []

        def spy_compute_factors(*, catalog, start_date, end_date, horizons, **kwargs):
            calls.append({"catalog": list(catalog), "start": start_date, "end": end_date, "horizons": horizons})
            if "adj_close" in catalog:
                return pd.DataFrame({"adj_close": adj}), None
            return panel, None

        wp = load_is_windowed_panel(
            {"f1": "Ref($close, 1)"}, ts, horizon=4, trade_cal=cal,
            compute_factors_fn=spy_compute_factors,
        )
        # belt 1: every compute call used horizons=None and ended at is_end (never OOS)
        self.assertTrue(calls)
        for c in calls:
            self.assertIsNone(c["horizons"])
            self.assertEqual(c["end"], "2020-12-31")
            self.assertNotIn("2021", str(c["end"]))
        self.assertLessEqual(wp.max_label_realization_date, pd.Timestamp("2020-12-31"))


class RunIsWalkForwardTests(unittest.TestCase):
    def _panel_for_folds(self):
        cal = _weekly_calendar()
        panel, adj = _panel(cal, instruments=80, seed=3)
        wp = build_is_windowed_panel(panel, adj, is_end="2020-12-31", horizon=4, trade_cal=cal)
        return wp

    def test_no_oos_field_and_evidence_kind_on_result_and_rows(self):
        ts = TimeSplit("2014-01-01", "2020-12-31", "2021-01-01", "2022-01-01")
        result = run_is_walk_forward(panel=self._panel_for_folds(), time_split=ts, horizon=4,
                                     factor_origin="generated")
        self.assertEqual(result.evidence_kind, "generated_heldout")
        self.assertGreaterEqual(result.n_heldout_blocks, 2)
        frame = result.to_frame()  # raises if any oos_* column exists
        self.assertNotIn("oos_rank_icir", frame.columns)
        self.assertTrue((frame["evidence_kind"] == "generated_heldout").all())
        self.assertLessEqual(result.effective_eval_end, pd.Timestamp("2020-12-31"))
        # status is candidate or draft only (IS-only rule never deprecates)
        self.assertTrue(set(frame["status"]).issubset({"candidate", "draft"}))

    def test_a_priori_origin_labels_distinctly(self):
        ts = TimeSplit("2014-01-01", "2020-12-31", "2021-01-01", "2022-01-01")
        result = run_is_walk_forward(panel=self._panel_for_folds(), time_split=ts, horizon=4,
                                     factor_origin="a_priori")
        self.assertEqual(result.evidence_kind, "a_priori")
        self.assertTrue((result.to_frame()["evidence_kind"] == "a_priori").all())

    def test_generated_fails_closed_without_heldout(self):
        # a too-short IS window cannot build a 3+1+1 fold -> generated factor RAISES
        cal = _weekly_calendar(start="2019-01-04", end="2020-12-25")
        panel, adj = _panel(cal, instruments=20, seed=4)
        wp = build_is_windowed_panel(panel, adj, is_end="2020-12-31", horizon=4, trade_cal=cal)
        ts = TimeSplit("2019-01-01", "2020-12-31", "2021-01-01", "2022-01-01")
        with self.assertRaises(NoHeldoutBlockError):
            run_is_walk_forward(panel=wp, time_split=ts, horizon=4, factor_origin="generated")


if __name__ == "__main__":
    unittest.main()
