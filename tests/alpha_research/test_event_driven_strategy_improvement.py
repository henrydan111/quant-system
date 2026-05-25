import unittest
from unittest.mock import patch

import pandas as pd

from workspace.research.alpha_mining.audit_benchmark_index import audit_benchmark_dataframe
from workspace.research.alpha_mining.event_driven_strategy_improvement import (
    apply_factor_family_caps,
    build_stock_weights,
    compute_stability_scores,
    filter_stability_pool_for_fold,
    parse_args,
    passes_variant_gate,
    sort_variant_summary,
)


class EventDrivenStrategyImprovementTests(unittest.TestCase):
    def test_parse_args_defaults_to_sse_benchmark(self):
        with patch(
            "sys.argv",
            [
                "event_driven_strategy_improvement.py",
                "--baseline-run-dir",
                "E:\\dummy",
            ],
        ):
            args = parse_args()

        self.assertEqual(args.benchmark, "000001.SH")
        self.assertEqual(args.baseline_run_dir, "E:\\dummy")

    def test_compute_stability_scores_prefers_more_stable_factor(self):
        decisions = pd.DataFrame(
            [
                {"factor": "a", "selected": True, "validation_pass": True, "val_rank_icir": 0.50, "marginal_rank_icir": 0.10, "max_abs_corr": 0.20},
                {"factor": "a", "selected": True, "validation_pass": True, "val_rank_icir": 0.45, "marginal_rank_icir": 0.08, "max_abs_corr": 0.25},
                {"factor": "b", "selected": False, "validation_pass": True, "val_rank_icir": 0.30, "marginal_rank_icir": 0.02, "max_abs_corr": 0.70},
                {"factor": "b", "selected": False, "validation_pass": False, "val_rank_icir": 0.10, "marginal_rank_icir": 0.00, "max_abs_corr": 0.75},
            ]
        )

        scores = compute_stability_scores(decisions)

        self.assertEqual(scores.iloc[0]["factor"], "a")
        self.assertGreater(scores.iloc[0]["stability_score"], scores.iloc[1]["stability_score"])

    def test_apply_factor_family_caps_keeps_sum_one_and_respects_bucket_cap(self):
        weights = pd.Series(
            {"liq_a": 0.25, "mom_a": 0.25, "risk_a": 0.25, "tech_a": 0.25},
            dtype=float,
        )
        family_map = {
            "liq_a": "Liquidity",
            "mom_a": "MomentumReversal",
            "risk_a": "Volatility",
            "tech_a": "Technical",
        }

        capped = apply_factor_family_caps(weights, family_map)

        self.assertAlmostEqual(float(capped.sum()), 1.0, places=10)
        self.assertLessEqual(float(capped[["liq_a"]].sum()), 0.30 + 1e-6)
        self.assertLessEqual(float(capped[["mom_a"]].sum()), 0.30 + 1e-6)
        self.assertLessEqual(float(capped[["risk_a"]].sum()), 0.25 + 1e-6)
        self.assertLessEqual(float(capped[["tech_a"]].sum()), 0.15 + 1e-6)

    def test_score_proportional_stock_weights_respect_single_name_cap(self):
        scores = pd.Series(
            {f"s{i:02d}": float(100 - i) for i in range(80)},
            dtype=float,
        )

        weights = build_stock_weights(scores, "score_proportional")

        self.assertAlmostEqual(float(weights.sum()), 1.0, places=10)
        self.assertLessEqual(float(weights.max()), 0.03 + 1e-9)

    def test_passes_variant_gate_ignores_turnover_and_blocked_ratio(self):
        promoted, reason = passes_variant_gate(
            {
                "stitched_relative_excess_return": 0.12,
                "positive_excess_folds": 5,
                "holdout_relative_excess_return": 0.01,
                "worst_max_drawdown": -0.25,
                "avg_turnover": 0.90,
                "avg_blocked_order_ratio": 0.50,
            }
        )

        self.assertTrue(promoted)
        self.assertEqual(reason, "ok")

    def test_filter_stability_pool_uses_validation_gate_not_test_strength(self):
        fold_rows = pd.DataFrame(
            [
                {"factor": "good", "validation_pass": True, "val_rank_icir": 0.20, "test_rank_icir": 0.05},
                {"factor": "bad", "validation_pass": False, "val_rank_icir": 0.01, "test_rank_icir": 9.99},
            ]
        )
        stability_scores = pd.DataFrame(
            [
                {"factor": "good", "stability_score": 0.60},
                {"factor": "bad", "stability_score": 0.95},
            ]
        )

        pool = filter_stability_pool_for_fold(fold_rows, stability_scores, top_n=12)

        self.assertEqual(pool["factor"].tolist(), ["good"])

    def test_benchmark_audit_flags_duplicates_and_bad_price_rows(self):
        df = pd.DataFrame(
            {
                "trade_date": ["20260105", "20260105", "20260106"],
                "open": [10.0, 10.0, 11.0],
                "high": [10.5, 9.0, 10.0],
                "low": [9.5, 9.5, 10.5],
                "close": [10.2, 9.2, 10.2],
                "pre_close": [9.8, 9.8, 10.2],
                "pct_chg": [4.0816, -6.1224, 0.0],
            }
        )
        trade_calendar = pd.DataFrame(
            {
                "cal_date": pd.to_datetime(["2026-01-05", "2026-01-06"]),
                "is_open": [1, 1],
            }
        )

        result = audit_benchmark_dataframe(df, trade_calendar, "000001.SH")

        self.assertFalse(result.passed)
        self.assertEqual(result.duplicate_trade_dates, 1)
        self.assertEqual(result.bad_high_low, 2)
        self.assertEqual(result.close_outside_range, 2)

    def test_sort_variant_summary_is_stable_when_rank_already_exists(self):
        raw = pd.DataFrame(
            [
                {
                    "stage": "A",
                    "variant_id": "v2",
                    "promoted": True,
                    "stitched_relative_excess_return": 0.12,
                    "positive_excess_folds": 5,
                    "holdout_relative_excess_return": 0.01,
                    "worst_max_drawdown": -0.20,
                    "avg_turnover": 0.50,
                    "avg_blocked_order_ratio": 0.10,
                    "avg_holding_cash_ratio": 0.05,
                },
                {
                    "stage": "A",
                    "variant_id": "v1",
                    "promoted": False,
                    "stitched_relative_excess_return": 0.03,
                    "positive_excess_folds": 2,
                    "holdout_relative_excess_return": -0.01,
                    "worst_max_drawdown": -0.35,
                    "avg_turnover": 0.20,
                    "avg_blocked_order_ratio": 0.02,
                    "avg_holding_cash_ratio": 0.01,
                },
            ]
        )

        first = sort_variant_summary(raw)
        second = sort_variant_summary(first)

        self.assertEqual(second.columns.tolist().count("rank"), 1)
        self.assertEqual(second["rank"].tolist(), [1, 2])
        self.assertEqual(second["variant_id"].tolist(), ["v2", "v1"])


if __name__ == "__main__":
    unittest.main()
