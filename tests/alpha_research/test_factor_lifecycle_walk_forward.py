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
    load_is_windowed_panel_with_layer2,
    realization_date,
    last_usable_factor_date,
    run_is_walk_forward,
    _expected_direction,
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

    def test_uncapped_adj_close_raises(self):
        # GPT P0: an adj-close extending past is_end must be rejected (belt 0) — the
        # reviewer's reproduction (a later OOS price would otherwise leak into the label).
        cal = pd.DatetimeIndex(["2020-01-03", "2020-01-10", "2020-01-17"])
        adj = pd.Series(
            [10.0, 99.0],
            index=pd.MultiIndex.from_tuples(
                [("000001_SZ", pd.Timestamp("2020-01-03")), ("000001_SZ", pd.Timestamp("2020-01-17"))],
                names=["instrument", "datetime"],
            ),
        )
        fac = pd.DataFrame({"f1": [0.5]}, index=pd.MultiIndex.from_tuples(
            [("000001_SZ", pd.Timestamp("2020-01-03"))], names=["instrument", "datetime"]))
        with self.assertRaises(IsEndLeakageError):
            build_is_windowed_panel(fac, adj, is_end="2020-01-10", horizon=1, trade_cal=cal)

    def test_sparse_adj_drops_not_substitutes_later_row(self):
        # GPT P0: a capped-but-sparse adj-close (missing the EXACT r(t) row) must DROP that
        # factor date, never substitute a later available row (the shift(-h)-over-rows bug).
        cal = pd.DatetimeIndex(["2020-01-03", "2020-01-10", "2020-01-17", "2020-01-24"])
        insts = ["000001_SZ"]
        # adj has d0, d2, d3 (MISSING d1=Jan10); is_end=Jan24 so all rows are capped
        adj = pd.Series(
            [10.0, 12.0, 13.0],
            index=pd.MultiIndex.from_tuples(
                [("000001_SZ", pd.Timestamp(d)) for d in ["2020-01-03", "2020-01-17", "2020-01-24"]],
                names=["instrument", "datetime"]),
        )
        # factor at d0 (r(d0)=d1=Jan10, which is MISSING in adj) + d2 (r(d2)=d3=Jan24, present)
        fac = pd.DataFrame({"f1": [0.5, 0.6]}, index=pd.MultiIndex.from_tuples(
            [("000001_SZ", pd.Timestamp("2020-01-03")), ("000001_SZ", pd.Timestamp("2020-01-17"))],
            names=["instrument", "datetime"]))
        wp = build_is_windowed_panel(fac, adj, is_end="2020-01-24", horizon=1, trade_cal=cal)
        kept = wp.factor_panel.index.get_level_values("datetime")
        self.assertNotIn(pd.Timestamp("2020-01-03"), kept)  # r(d0)=Jan10 missing -> dropped
        self.assertIn(pd.Timestamp("2020-01-17"), kept)     # r(d2)=Jan24 present -> kept
        # the kept label used the EXACT Jan24 price (13/12-1), not a substitution
        self.assertAlmostEqual(float(wp.label.loc[("000001_SZ", pd.Timestamp("2020-01-17"))]), 13.0 / 12.0 - 1)

    def test_direct_constructor_rejects_misaligned_label(self):
        # GPT P0: a directly-constructed panel whose label index != factor index is rejected.
        cal = _weekly_calendar()
        idx = pd.MultiIndex.from_tuples(
            [("000001_SZ", cal[5]), ("000001_SZ", cal[6])], names=["instrument", "datetime"])
        panel = pd.DataFrame({"f1": [0.1, 0.2]}, index=idx)
        label = pd.Series([0.0], index=pd.MultiIndex.from_tuples(
            [("000001_SZ", cal[5])], names=["instrument", "datetime"]))  # shorter -> misaligned
        with self.assertRaises(IsEndLeakageError):
            IsWindowedPanel(factor_panel=panel, label=label, is_end=cal[10], horizon=4, open_days=cal)

    def test_build_is_multiindex_level_order_invariant(self):
        # REGRESSION (real-data dry-run 2026-06-01): compute_factors returns a
        # (datetime, instrument) panel, but build_is_windowed_panel hardcoded an
        # (instrument, datetime) future index, so the POSITIONAL reindex matched NOTHING ->
        # all-NaN label -> "empty factor panel / label" IsEndLeakageError. Every prior
        # fixture used (instrument, datetime), so the integration point was untested. The
        # builder must produce identical, correct labels for EITHER input level order.
        insts = ["000001_SZ", "000002_SZ"]
        cal = pd.bdate_range("2020-01-01", periods=10)
        open_days = list(cal)
        h = 2
        is_end = cal[-1]
        recs = []
        for d in cal:
            for inst in insts:
                base = 100.0 if inst == insts[0] else 200.0
                recs.append({"instrument": inst, "datetime": d,
                             "f1": float(open_days.index(d)), "adj": base + open_days.index(d)})
        long = pd.DataFrame(recs)

        def _build(order):
            idx = pd.MultiIndex.from_frame(long[list(order)])
            fp = long.set_index(idx)[["f1"]]
            ac = long.set_index(idx)["adj"]
            return build_is_windowed_panel(fp, ac, is_end=is_end, horizon=h, trade_cal=open_days)

        di = _build(("datetime", "instrument"))   # the REAL compute_factors order
        idd = _build(("instrument", "datetime"))   # the legacy fixture order

        # non-empty + correct boundary: last usable factor date is open_days[-1-h]
        self.assertFalse(di.factor_panel.empty)
        self.assertEqual(di.max_factor_date, cal[-1 - h])
        self.assertLessEqual(di.max_label_realization_date, pd.Timestamp(is_end))
        # concrete forward return: 000001_SZ at cal[0] (price 100) -> r=cal[2] (price 102)
        v = di.label.reset_index()
        v = v[(v["instrument"] == "000001_SZ") & (v["datetime"] == cal[0])]["label"].iloc[0]
        self.assertAlmostEqual(float(v), 102.0 / 100.0 - 1.0)
        # order invariance: identical label sets regardless of input level order
        la = di.label.reset_index()[["instrument", "datetime", "label"]] \
            .sort_values(["instrument", "datetime"]).reset_index(drop=True)
        lb = idd.label.reset_index()[["instrument", "datetime", "label"]] \
            .sort_values(["instrument", "datetime"]).reset_index(drop=True)
        pd.testing.assert_frame_equal(la, lb)


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

    def test_unknown_factor_origin_raises(self):
        # GPT P1: a typo'd factor_origin must NOT silently take the a_priori path.
        ts = TimeSplit("2014-01-01", "2020-12-31", "2021-01-01", "2022-01-01")
        with self.assertRaises(ValueError):
            run_is_walk_forward(panel=self._panel_for_folds(), time_split=ts, horizon=4,
                                factor_origin="generted")  # typo


class ExpectedDirectionTests(unittest.TestCase):
    def test_signed_icir_direction_label(self):
        self.assertEqual(_expected_direction(0.3), "positive")
        self.assertEqual(_expected_direction(-0.3), "inverse")   # admit inverse predictors
        self.assertEqual(_expected_direction(0.0), "undetermined")
        self.assertEqual(_expected_direction(float("nan")), "undetermined")


class Layer2PanelTests(unittest.TestCase):
    """Phase 7: the Layer-2 IS-only builder gates composites + industry-relative while
    inheriting the is_end belts and EXCLUDING dependency-only bases from verdict columns."""

    def _setup(self):
        cal = _weekly_calendar()  # 2014..2020 weekly
        insts = [f"{i:06d}_SZ" for i in range(6)]
        idx = pd.MultiIndex.from_product([cal, insts], names=["datetime", "instrument"])  # (dt, inst)
        rng = np.random.default_rng(11)
        base = pd.DataFrame({
            "mom_return_20d": rng.standard_normal(len(idx)),
            "size_ln_mcap": rng.standard_normal(len(idx)),
            "val_bp": rng.standard_normal(len(idx)),
        }, index=idx)
        adj = pd.DataFrame({"adj_close": 10 * np.exp((rng.standard_normal(len(idx)) * 0.02).cumsum() % 3)},
                           index=idx)
        # industry: 3 stocks "A", 3 stocks "B"
        industry = pd.Series(["A" if int(s[:6]) < 3 else "B" for s in idx.get_level_values("instrument")],
                             index=idx)

        def fake_cf(catalog, start_date, end_date, horizons, **kw):
            keys = set(catalog)
            if "adj_close" in keys:
                return adj, None
            if "market_cap" in keys:
                return pd.DataFrame({"market_cap": np.abs(rng.standard_normal(len(idx))) + 1}, index=idx), None
            return base[[c for c in catalog if c in base.columns]], None

        ts = TimeSplit("2014-01-01", "2020-12-31", "2021-01-01", "2022-01-01")
        return cal, base, industry, fake_cf, ts

    def test_gates_composite_and_industry_excludes_dependency_only_bases(self):
        cal, base, industry, fake_cf, ts = self._setup()
        comp = {"name": "comp_small_value", "components": ["size_ln_mcap", "val_bp"], "negate": [True, False]}
        ind = {"name": "val_bp_industry_rel", "base": "val_bp", "kind": "industry_mean_subtract",
               "requires_market_cap": False}
        wp = load_is_windowed_panel_with_layer2(
            gated_base=["mom_return_20d"], gated_composite_defs=[comp], gated_industry_defs=[ind],
            time_split=ts, horizon=4, trade_cal=cal,
            compute_factors_fn=fake_cf, industry_series_fn=lambda ix: industry.reindex(ix),
        )
        cols = set(wp.factor_panel.columns)
        # gated columns present; dependency-only bases (size_ln_mcap, val_bp) EXCLUDED
        self.assertEqual(cols, {"mom_return_20d", "comp_small_value", "val_bp_industry_rel"})
        self.assertNotIn("size_ln_mcap", cols)
        self.assertNotIn("val_bp", cols)
        # is_end belt holds (label realizes <= is_end)
        self.assertLessEqual(wp.max_label_realization_date, pd.Timestamp("2020-12-31"))
        # composite is a rank-average -> within [0, 1]; computed (not all-NaN)
        cv = wp.factor_panel["comp_small_value"].dropna()
        self.assertTrue(len(cv) > 0)
        self.assertTrue(((cv >= 0) & (cv <= 1)).all())
        # industry-relative column computed (not all-NaN)
        self.assertTrue(wp.factor_panel["val_bp_industry_rel"].notna().any())

    def test_base_only_equivalent_to_load_is_windowed_panel(self):
        cal, base, industry, fake_cf, ts = self._setup()
        layer2 = load_is_windowed_panel_with_layer2(
            gated_base=["mom_return_20d", "val_bp"], gated_composite_defs=[], gated_industry_defs=[],
            time_split=ts, horizon=4, trade_cal=cal, compute_factors_fn=fake_cf,
        )

        def cf_base(catalog, start_date, end_date, horizons, **kw):
            keys = set(catalog)
            if "adj_close" in keys:
                return fake_cf(catalog, start_date, end_date, horizons, **kw)
            return base[[c for c in catalog if c in base.columns]], None

        direct = load_is_windowed_panel(
            {"mom_return_20d": "x", "val_bp": "x"}, ts, horizon=4, trade_cal=cal, compute_factors_fn=cf_base,
        )
        self.assertEqual(set(layer2.factor_panel.columns), set(direct.factor_panel.columns))
        self.assertEqual(len(layer2.label), len(direct.label))
        self.assertEqual(layer2.max_label_realization_date, direct.max_label_realization_date)

    def test_wrong_order_base_panel_fails_closed_before_layer2(self):
        # belt-and-suspenders: an (instrument, datetime) base panel must fail loudly before
        # the formal Layer-2 compute (even though cs_rank is now name-based).
        cal, base, industry, fake_cf, ts = self._setup()
        base_swapped = base.swaplevel(0, 1).sort_index()  # (instrument, datetime)

        def cf_swapped(catalog, start_date, end_date, horizons, **kw):
            keys = set(catalog)
            if "adj_close" in keys:
                a = fake_cf(catalog, start_date, end_date, horizons, **kw)[0]
                return a, None
            return base_swapped[[c for c in catalog if c in base_swapped.columns]], None

        comp = {"name": "comp_small_value", "components": ["size_ln_mcap", "val_bp"], "negate": [True, False]}
        with self.assertRaises(IsEndLeakageError):
            load_is_windowed_panel_with_layer2(
                gated_base=["mom_return_20d"], gated_composite_defs=[comp], gated_industry_defs=[],
                time_split=ts, horizon=4, trade_cal=cal, compute_factors_fn=cf_swapped,
            )


if __name__ == "__main__":
    unittest.main()
