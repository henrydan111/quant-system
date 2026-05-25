import unittest
from unittest.mock import patch

import pandas as pd

from workspace.research.alpha_mining.event_driven_strategy_research import (
    LiquidityScenario,
    apply_liquidity_rules,
    assign_corr_clusters,
    build_rebalance_dates,
    build_walk_forward_folds,
    parse_args,
    resolve_mlflow_status,
)


class EventDrivenStrategyResearchHelpersTests(unittest.TestCase):
    def test_build_walk_forward_folds_and_holdout(self):
        folds, holdout = build_walk_forward_folds("2012-01-01", "2026-02-27")

        self.assertEqual(len(folds), 7)
        self.assertEqual(folds[0].train_start, "2012-01-01")
        self.assertEqual(folds[0].validation_start, "2017-01-01")
        self.assertEqual(folds[0].test_start, "2019-01-01")
        self.assertEqual(folds[-1].fold_id, "fold_07_2025")
        self.assertEqual(folds[-1].test_end, "2025-12-31")
        self.assertIsNotNone(holdout)
        self.assertEqual(holdout.start, "2026-01-01")
        self.assertEqual(holdout.end, "2026-02-27")

    def test_assign_corr_clusters_uses_connected_components(self):
        corr = pd.DataFrame(
            [
                [1.0, 0.70, 0.10, 0.00],
                [0.70, 1.0, 0.65, 0.05],
                [0.10, 0.65, 1.0, 0.20],
                [0.00, 0.05, 0.20, 1.0],
            ],
            index=["a", "b", "c", "d"],
            columns=["a", "b", "c", "d"],
        )

        clusters = assign_corr_clusters(corr, threshold=0.60)

        self.assertEqual(clusters["a"], clusters["b"])
        self.assertEqual(clusters["b"], clusters["c"])
        self.assertNotEqual(clusters["a"], clusters["d"])

    def test_apply_liquidity_rules_respects_floor_and_participation(self):
        scores = pd.Series(
            [0.9, 0.8, 0.7],
            index=["000001_SZ", "000002_SZ", "000003_SZ"],
            dtype=float,
        )
        adv = pd.Series(
            [10_000_000.0, 4_000_000.0, 3_000_000.0],
            index=scores.index,
            dtype=float,
        )
        scenario = LiquidityScenario(
            name="default",
            adv_floor=5_000_000.0,
            participation_cap=0.02,
            bottom_pct=None,
        )

        selected = apply_liquidity_rules(
            scores,
            adv,
            topk=3,
            target_value=40_000.0,
            scenario=scenario,
        )

        self.assertEqual(selected.index.tolist(), ["000001_SZ"])

    def test_apply_liquidity_rules_bottom_percentile_filter(self):
        scores = pd.Series(
            [0.9, 0.8, 0.7, 0.6, 0.5],
            index=["a", "b", "c", "d", "e"],
            dtype=float,
        )
        adv = pd.Series(
            [100.0, 90.0, 80.0, 20.0, 10.0],
            index=scores.index,
            dtype=float,
        )
        scenario = LiquidityScenario(
            name="bottom20",
            adv_floor=None,
            participation_cap=None,
            bottom_pct=0.20,
        )

        selected = apply_liquidity_rules(
            scores,
            adv,
            topk=5,
            target_value=1.0,
            scenario=scenario,
        )

        self.assertNotIn("e", selected.index.tolist())
        self.assertEqual(selected.index.tolist(), ["a", "b", "c", "d"])

    def test_build_rebalance_dates_every_n_days(self):
        calendar = pd.to_datetime(
            ["2026-01-02", "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09"]
        ).tolist()

        dates = build_rebalance_dates(calendar, rebalance_days=2)

        self.assertEqual(
            dates,
            pd.to_datetime(["2026-01-02", "2026-01-06", "2026-01-08"]).tolist(),
        )

    def test_parse_args_supports_disable_mlflow_flag(self):
        with patch(
            "sys.argv",
            [
                "event_driven_strategy_research.py",
                "--screening-run-dir",
                "E:\\dummy",
                "--disable-mlflow",
            ],
        ):
            args = parse_args()

        self.assertTrue(args.disable_mlflow)
        self.assertEqual(args.screening_run_dir, "E:\\dummy")

    def test_resolve_mlflow_status_reports_disabled(self):
        status = resolve_mlflow_status(None, disabled=True)

        self.assertEqual(status["mlflow_status"], "disabled")
        self.assertIn("mlflow_tracking_uri", status)


if __name__ == "__main__":
    unittest.main()
