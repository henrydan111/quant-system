import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd

import workspace.research.alpha_mining.event_driven_strategy_ml_research as ml_research
from src.alpha_research.model_zoo import ElasticNetModel
from workspace.research.alpha_mining.event_driven_strategy_ml_research import (
    FoldDataset,
    LiquidityScenario,
    MLVariantSpec,
    build_model_variant_artifacts,
    build_prediction_schedule,
    choose_adoption_recommendation,
    compute_train_factor_directions,
    parse_args,
    parse_model_variants,
)
from workspace.research.alpha_mining.event_driven_strategy_research import write_series_parquet


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def make_series(values_by_date, name="value"):
    rows = []
    for date_str, mapping in values_by_date.items():
        date = pd.Timestamp(date_str)
        for instrument, value in mapping.items():
            rows.append((date, instrument, value))
    df = pd.DataFrame(rows, columns=["datetime", "instrument", name])
    df = df.set_index(["datetime", "instrument"]).sort_index()
    return df[name].astype(np.float32)


def make_context(date_str: str, adv_values: dict[str, float]):
    date = pd.Timestamp(date_str)
    aux_df = pd.DataFrame(
        {
            "adv20_median_rmb": pd.Series(adv_values, dtype=float),
        }
    )
    aux_df.index = pd.MultiIndex.from_product([[date], list(adv_values.keys())], names=["datetime", "instrument"])
    stock_basic_map = pd.DataFrame(
        {
            "list_idx": [0] * len(adv_values),
            "delist_date": [pd.NaT] * len(adv_values),
        },
        index=pd.Index(list(adv_values.keys()), name="instrument"),
    )
    return SimpleNamespace(
        aux_df=aux_df,
        stock_basic_map=stock_basic_map,
        trade_pos_by_date={date: 100},
        st_ranges={},
    )


class ElasticNetModelTests(unittest.TestCase):
    def test_fit_predict_save_and_load(self):
        X = pd.DataFrame(
            {
                "f1": [0.0, 1.0, 2.0, 3.0],
                "f2": [3.0, 2.0, 1.0, 0.0],
            }
        )
        y = pd.Series([0.0, 1.0, 2.0, 3.0], dtype=float)
        model = ElasticNetModel(alpha=0.001, l1_ratio=0.5)
        model.fit(X, y)
        preds = model.predict(X)
        self.assertEqual(len(preds), len(X))
        self.assertEqual(model.coefficients().index.tolist(), ["f1", "f2"])

        with tempfile.TemporaryDirectory(dir=str(PROJECT_ROOT / "workspace" / "outputs")) as tmpdir:
            path = Path(tmpdir) / "elasticnet.pkl"
            model.save(str(path))
            loaded = ElasticNetModel.load(str(path))
            loaded_preds = loaded.predict(X)

        pd.testing.assert_series_equal(preds, loaded_preds)


class EventDrivenStrategyMLResearchTests(unittest.TestCase):
    def test_parse_args_defaults_disable_mlflow(self):
        with patch(
            "sys.argv",
            [
                "event_driven_strategy_ml_research.py",
                "--baseline-run-dir",
                "E:\\baseline",
                "--screening-run-dir",
                "E:\\screening",
            ],
        ):
            args = parse_args()

        self.assertTrue(args.disable_mlflow)
        self.assertEqual(args.benchmark, "000001.SH")
        self.assertEqual(args.label_horizon, 10)
        self.assertEqual(args.rebalance_days, 10)

    def test_parse_model_variants_deduplicates(self):
        self.assertEqual(parse_model_variants("linear, lightgbm,linear"), ["linear", "lightgbm"])
        with self.assertRaises(ValueError):
            parse_model_variants("linear,unknown")

    def test_compute_train_factor_directions_uses_train_window_only(self):
        factor_a = make_series(
            {
                "2026-01-05": {"AAA_SH": 1.0, "BBB_SH": 2.0},
                "2026-01-10": {"AAA_SH": 1.2, "BBB_SH": 2.2},
                "2026-01-15": {"AAA_SH": 1.5, "BBB_SH": 2.5},
                "2026-02-05": {"AAA_SH": 5.0, "BBB_SH": 1.0},
            }
        )
        factor_b = make_series(
            {
                "2026-01-05": {"AAA_SH": 3.0, "BBB_SH": 1.0},
                "2026-01-10": {"AAA_SH": 4.0, "BBB_SH": 2.0},
                "2026-01-15": {"AAA_SH": 5.0, "BBB_SH": 3.0},
                "2026-02-05": {"AAA_SH": 1.0, "BBB_SH": 5.0},
            }
        )
        forward = make_series(
            {
                "2026-01-05": {"AAA_SH": 0.02, "BBB_SH": 0.04},
                "2026-01-10": {"AAA_SH": 0.01, "BBB_SH": 0.03},
                "2026-01-15": {"AAA_SH": 0.01, "BBB_SH": 0.03},
                "2026-02-05": {"AAA_SH": 0.05, "BBB_SH": 0.01},
            }
        )
        series_map = {"factor_a": factor_a.rename("factor_a"), "factor_b": factor_b.rename("factor_b")}

        def fake_read_series(path):
            return series_map[Path(path).stem]

        def fake_compute_ic_series(factor_slice, label_slice):
            self.assertLessEqual(
                factor_slice.index.get_level_values("datetime").max(),
                pd.Timestamp("2026-01-31"),
            )
            value = 1.0 if factor_slice.name == "factor_a" else -1.0
            return pd.Series([value], index=[pd.Timestamp("2026-01-31")], name="rank_ic")

        def fake_compute_ic_summary(ic_series):
            return {"mean_rank_ic": float(ic_series.iloc[0])}

        with tempfile.TemporaryDirectory(dir=str(PROJECT_ROOT / "workspace" / "outputs")) as tmpdir:
            tmp = Path(tmpdir)
            path_a = tmp / "factor_a.parquet"
            path_b = tmp / "factor_b.parquet"
            write_series_parquet(factor_a, path_a)
            write_series_parquet(factor_b, path_b)
            with patch.object(ml_research, "read_series_parquet", side_effect=fake_read_series), patch.object(
                ml_research,
                "compute_ic_series",
                side_effect=fake_compute_ic_series,
            ), patch.object(
                ml_research,
                "compute_ic_summary",
                side_effect=fake_compute_ic_summary,
            ):
                directions = compute_train_factor_directions(
                    ["factor_a", "factor_b"],
                    {"factor_a": path_a, "factor_b": path_b},
                    forward,
                    "2026-01-01",
                    "2026-01-31",
                )

        self.assertEqual(directions["factor_a"], 1)
        self.assertEqual(directions["factor_b"], -1)

    def test_build_prediction_schedule_applies_liquidity_and_equal_weight(self):
        predictions = make_series(
            {
                "2026-01-05": {
                    "AAA_SH": 0.9,
                    "BBB_SH": 0.8,
                    "CCC_SH": 0.7,
                }
            }
        )
        context = make_context(
            "2026-01-05",
            {
                "AAA_SH": 10_000_000.0,
                "BBB_SH": 4_000_000.0,
                "CCC_SH": 8_000_000.0,
            },
        )
        scenario = LiquidityScenario(
            name="adv_floor_plus_participation",
            adv_floor=5_000_000.0,
            participation_cap=0.02,
            bottom_pct=None,
        )

        schedule, prediction_df, signal_df, diag_df = build_prediction_schedule(
            predictions=predictions,
            context=context,
            scenario=scenario,
            topk=2,
            capital=40_000.0,
            variant_id="elasticnet",
            fold_id="fold_01",
            window_type="test",
        )

        self.assertEqual(len(prediction_df), 3)
        self.assertEqual(sorted(schedule[pd.Timestamp("2026-01-05")].keys()), ["AAA.SH", "CCC.SH"])
        self.assertTrue((signal_df["target_weight"] == 0.5).all())
        self.assertEqual(int(diag_df.iloc[0]["n_selected"]), 2)

    def test_choose_adoption_recommendation(self):
        self.assertEqual(
            choose_adoption_recommendation(
                {
                    "stitched_relative_excess_return": 0.12,
                    "holdout_relative_excess_return": 0.02,
                },
                {
                    "stitched_relative_excess_return": 0.05,
                    "holdout_relative_excess_return": 0.01,
                },
            ),
            "adopt",
        )
        self.assertEqual(
            choose_adoption_recommendation(
                {
                    "stitched_relative_excess_return": 0.03,
                    "holdout_relative_excess_return": -0.01,
                },
                {
                    "stitched_relative_excess_return": 0.05,
                    "holdout_relative_excess_return": 0.01,
                },
            ),
            "reject",
        )

    def test_build_model_variant_artifacts_handles_all_empty_optional_frames(self):
        spec = MLVariantSpec(
            variant_id="linear",
            model_kind="linear",
            display_name="ElasticNet",
        )
        artifacts = build_model_variant_artifacts(
            spec=spec,
            oos_rows=[
                {
                    "variant_id": "linear",
                    "fold_id": "fold_01",
                    "window_type": "test",
                    "cumulative_return": 0.05,
                    "benchmark_total_return": 0.02,
                    "relative_excess_return": 0.03,
                    "max_drawdown": -0.04,
                    "turnover_mean": 0.10,
                    "blocked_order_ratio": 0.01,
                    "holding_cash_ratio": 0.05,
                }
            ],
            event_reports=[pd.DataFrame()],
            signal_frames=[pd.DataFrame()],
            signal_diag_frames=[pd.DataFrame()],
            prediction_frames=[pd.DataFrame()],
            metric_frames=[pd.DataFrame()],
            linear_weight_frames=[pd.DataFrame()],
            importance_frames=[pd.DataFrame()],
        )

        self.assertFalse(artifacts.oos_performance.empty)
        self.assertTrue(artifacts.event_report.empty)
        self.assertTrue(artifacts.linear_weights.empty)
        self.assertTrue(artifacts.feature_importance.empty)
        self.assertEqual(artifacts.summary["variant_id"], "linear")

    def test_run_lightgbm_for_window_produces_importance_table(self):
        index = pd.MultiIndex.from_tuples(
            [
                (pd.Timestamp("2026-01-05"), "AAA_SH"),
                (pd.Timestamp("2026-01-05"), "BBB_SH"),
                (pd.Timestamp("2026-01-15"), "AAA_SH"),
                (pd.Timestamp("2026-01-15"), "BBB_SH"),
            ],
            names=["datetime", "instrument"],
        )
        dataset = FoldDataset(
            fold_id="fold_01",
            window_type="test",
            factor_directions={"f1": 1, "f2": 1},
            train_dates=[pd.Timestamp("2026-01-05")],
            validation_dates=[pd.Timestamp("2026-01-15")],
            test_dates=[pd.Timestamp("2026-01-15")],
            X_train=pd.DataFrame({"f1": [0.0, 1.0], "f2": [1.0, 0.0]}, index=index[:2]),
            y_train=pd.Series([0.01, 0.02], index=index[:2]),
            X_validation=pd.DataFrame({"f1": [0.5, 1.5], "f2": [1.5, 0.5]}, index=index[2:]),
            y_validation=pd.Series([0.015, 0.025], index=index[2:]),
            X_test=pd.DataFrame({"f1": [0.5, 1.5], "f2": [1.5, 0.5]}, index=index[2:]),
            y_test=pd.Series([0.015, 0.025], index=index[2:]),
        )
        context = make_context(
            "2026-01-15",
            {
                "AAA_SH": 10_000_000.0,
                "BBB_SH": 12_000_000.0,
            },
        )
        scenario = LiquidityScenario(
            name="adv_floor_plus_participation",
            adv_floor=5_000_000.0,
            participation_cap=0.02,
            bottom_pct=None,
        )

        fake_perf = {
            "cumulative_return": 0.01,
            "benchmark_total_return": 0.0,
            "relative_excess_return": 0.01,
            "max_drawdown": -0.01,
            "prediction_rank_icir": 0.5,
        }
        fake_report = pd.DataFrame({"date": [pd.Timestamp("2026-01-15")], "return": [0.01], "bench": [0.0]})
        fake_signal = pd.DataFrame({"date": [pd.Timestamp("2026-01-15")], "instrument": ["AAA.SH"], "target_weight": [1.0]})
        fake_diag = pd.DataFrame({"date": [pd.Timestamp("2026-01-15")], "n_selected": [1]})
        fake_pred = pd.DataFrame({"date": [pd.Timestamp("2026-01-15")], "instrument": ["AAA.SH"], "score": [0.1]})

        with patch.object(
            ml_research,
            "LIGHTGBM_PARAMS",
            {
                "num_leaves": 8,
                "max_depth": 3,
                "learning_rate": 0.1,
                "feature_fraction": 1.0,
                "bagging_fraction": 1.0,
                "bagging_freq": 0,
                "lambda_l1": 0.0,
                "lambda_l2": 0.0,
                "min_data_in_leaf": 1,
            },
        ), patch.object(ml_research, "LIGHTGBM_NUM_BOOST_ROUND", 10), patch.object(
            ml_research,
            "LIGHTGBM_EARLY_STOPPING_ROUNDS",
            3,
        ), patch.object(
            ml_research,
            "evaluate_prediction_window",
            return_value=(fake_perf, fake_report, fake_signal, fake_diag, fake_pred),
        ):
            result = ml_research.run_lightgbm_for_window(
                dataset=dataset,
                context=context,
                scenario=scenario,
                benchmark="000001.SH",
                topk=2,
                capital=40_000.0,
            )

        self.assertEqual(result["oos_row"]["variant_id"], "lightgbm")
        self.assertFalse(result["feature_importance"].empty)
        self.assertIn("gain_importance", result["feature_importance"].columns)


if __name__ == "__main__":
    unittest.main()
