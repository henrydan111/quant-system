import json
import logging
import shutil
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

import src.alpha_research.theme_strategy.cli as theme_cli
from src.alpha_research.theme_strategy.components import (
    ComponentEngine,
    build_seed_recipes_for_theme,
    generate_component_specs,
    rank_component_within_universe,
)
from src.alpha_research.theme_strategy.data import ProjectPaths, ResearchSupport
from src.alpha_research.theme_strategy.pipeline import ThemeStrategyPipeline, sort_event_summary_frame
from src.alpha_research.theme_strategy.registry import get_field_definitions, get_theme_spec
from src.alpha_research.theme_strategy.schema import FieldInventoryRow


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@contextmanager
def temp_output_dir(name: str):
    root = PROJECT_ROOT / "workspace" / "outputs"
    root.mkdir(parents=True, exist_ok=True)
    temp_root = root / f"{name}_{uuid.uuid4().hex[:8]}"
    if temp_root.exists():
        shutil.rmtree(temp_root, ignore_errors=True)
    temp_root.mkdir(parents=True, exist_ok=True)
    try:
        yield temp_root
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def make_series(dates, instruments, values_fn, name):
    rows = []
    for di, date in enumerate(dates):
        for ii, instrument in enumerate(instruments):
            rows.append((date, instrument, float(values_fn(di, ii))))
    df = pd.DataFrame(rows, columns=["datetime", "instrument", name]).set_index(["datetime", "instrument"]).sort_index()
    return df[name].astype(np.float32)


class FakeIndexMembershipStore:
    def __init__(self, mapping):
        self.mapping = mapping

    def members_on(self, index_code, date):
        return set(self.mapping.get(index_code, set()))


class FakeProvider:
    def __init__(self, raw_fields):
        self.raw_fields = raw_fields
        self.qlib_dir = Path.cwd()

    def audit_fields(self, field_defs, start_date, end_date, **kwargs):
        inventory = []
        filtered = {}
        for field_def in field_defs:
            if field_def.field_name not in self.raw_fields:
                continue
            series = self.raw_fields[field_def.field_name]
            valid = series.dropna()
            dates = valid.index.get_level_values("datetime")
            coverage_ratio = float(valid.notna().mean()) if not series.empty else 0.0
            inventory.append(
                FieldInventoryRow(
                    field_name=field_def.field_name,
                    field_family=field_def.field_family,
                    provider_source=field_def.provider_source,
                    coverage_start=pd.Timestamp(dates.min()).strftime("%Y-%m-%d") if len(valid) else "",
                    coverage_end=pd.Timestamp(dates.max()).strftime("%Y-%m-%d") if len(valid) else "",
                    coverage_ratio=coverage_ratio,
                    freq_type=field_def.freq_type,
                    pit_safe=field_def.pit_safe,
                    theme_tags=field_def.theme_tags,
                )
            )
            filtered[field_def.field_name] = series
        return inventory, filtered


def build_fake_support():
    dates = pd.date_range("2012-01-31", "2026-02-28", freq="ME")
    instruments = ["000001_SZ", "000002_SZ", "000003_SZ", "000004_SZ", "000005_SZ"]
    benchmark_close = pd.Series(np.linspace(100, 180, len(dates)), index=dates, dtype=float, name="000852.SH")
    stock_basic = pd.DataFrame(
        {
            "qlib_code": instruments,
            "ts_code": [code.replace("_", ".") for code in instruments],
            "market": ["主板", "主板", "主板", "创业板", "主板"],
            "list_date": pd.to_datetime(["2010-01-01"] * len(instruments)),
            "delist_date": [pd.NaT] * len(instruments),
        }
    )
    return ResearchSupport(
        project_paths=ProjectPaths(PROJECT_ROOT / "data", PROJECT_ROOT / "data", PROJECT_ROOT / "data" / "dummy_st.txt"),
        trade_calendar=list(dates),
        trade_calendar_index=pd.DatetimeIndex(dates),
        trade_pos_by_date={pd.Timestamp(date): idx for idx, date in enumerate(dates)},
        stock_basic=stock_basic,
        stock_basic_map=stock_basic.set_index("qlib_code"),
        benchmark_returns=benchmark_close.pct_change().dropna(),
        benchmark_close=benchmark_close,
        st_ranges={"000002_SZ": [(pd.Timestamp("2018-01-31"), pd.Timestamp("2026-02-28"))]},
        index_membership_store=FakeIndexMembershipStore(
            {
                "000852.SH": set(["000001_SZ", "000002_SZ", "000003_SZ"]),
                "000300.SH": set(["000001_SZ", "000002_SZ", "000005_SZ"]),
                "000905.SH": set(["000001_SZ", "000002_SZ", "000003_SZ", "000005_SZ"]),
            }
        ),
    )


def build_fake_raw_fields():
    support = build_fake_support()
    dates = support.trade_calendar
    instruments = support.stock_basic["qlib_code"].tolist()
    return {
        "close": make_series(dates, instruments, lambda di, ii: 10 + ii + di * (0.4 - ii * 0.03), "close"),
        "adj_factor": make_series(dates, instruments, lambda di, ii: 1.0, "adj_factor"),
        "amount": make_series(dates, instruments, lambda di, ii: 12000 + 500 * (5 - ii), "amount"),
        "total_mv": make_series(dates, instruments, lambda di, ii: [2e9, 4e9, 7e9, 25e9, 9e9][ii], "total_mv"),
        "circ_mv": make_series(dates, instruments, lambda di, ii: [1.5e9, 3e9, 5e9, 18e9, 7e9][ii], "circ_mv"),
        "free_share": make_series(dates, instruments, lambda di, ii: [1e8, 2e8, 3e8, 6e8, 2.5e8][ii], "free_share"),
        "pb": make_series(dates, instruments, lambda di, ii: [1.1, 1.3, 2.0, 4.0, 1.8][ii], "pb"),
        "pe_ttm": make_series(dates, instruments, lambda di, ii: [12, 15, 25, 60, 20][ii], "pe_ttm"),
        "ps_ttm": make_series(dates, instruments, lambda di, ii: [0.9, 1.2, 1.8, 4.0, 1.5][ii], "ps_ttm"),
        "dv_ttm": make_series(dates, instruments, lambda di, ii: [3.0, 2.0, 1.0, 0.2, 1.5][ii], "dv_ttm"),
        "roe": make_series(dates, instruments, lambda di, ii: [18, 15, 10, 4, 12][ii], "roe"),
        "roa": make_series(dates, instruments, lambda di, ii: [8, 7, 4, 1, 5][ii], "roa"),
        "roic": make_series(dates, instruments, lambda di, ii: [14, 12, 8, 3, 10][ii], "roic"),
        "grossprofit_margin": make_series(dates, instruments, lambda di, ii: [30, 28, 22, 10, 25][ii], "grossprofit_margin"),
        "netprofit_margin": make_series(dates, instruments, lambda di, ii: [15, 13, 8, 1, 10][ii], "netprofit_margin"),
        "debt_to_assets": make_series(dates, instruments, lambda di, ii: [40, 45, 50, 70, 48][ii], "debt_to_assets"),
        "current_ratio": make_series(dates, instruments, lambda di, ii: [1.8, 1.6, 1.2, 0.8, 1.3][ii], "current_ratio"),
        "quick_ratio": make_series(dates, instruments, lambda di, ii: [1.4, 1.2, 0.9, 0.5, 1.0][ii], "quick_ratio"),
        "n_income_attr_p": make_series(dates, instruments, lambda di, ii: [5e8, 4e8, 2e8, -1e8, 3e8][ii], "n_income_attr_p"),
        "revenue_q": make_series(dates, instruments, lambda di, ii: [2e8, 2.5e8, 1.5e8, 0.5e8, 1.8e8][ii], "revenue_q"),
        "turnover_rate": make_series(dates, instruments, lambda di, ii: [2.0, 3.0, 4.0, 8.0, 3.5][ii], "turnover_rate"),
        "pit_q_sales_yoy": make_series(dates, instruments, lambda di, ii: [20, 15, 8, -5, 10][ii], "pit_q_sales_yoy"),
        "pit_netprofit_yoy": make_series(dates, instruments, lambda di, ii: [25, 20, 6, -15, 12][ii], "pit_netprofit_yoy"),
        "pit_basic_eps_yoy": make_series(dates, instruments, lambda di, ii: [18, 12, 5, -20, 8][ii], "pit_basic_eps_yoy"),
        "pit_ocf_yoy": make_series(dates, instruments, lambda di, ii: [16, 10, 4, -10, 7][ii], "pit_ocf_yoy"),
        "ratio": make_series(dates, instruments, lambda di, ii: [2.0, 1.8, np.nan, np.nan, 1.0][ii], "ratio"),
        "net_mf_amount": make_series(dates, instruments, lambda di, ii: [200, 180, 90, 20, 110][ii], "net_mf_amount"),
        "buy_lg_amount": make_series(dates, instruments, lambda di, ii: [300, 260, 140, 30, 150][ii], "buy_lg_amount"),
        "sell_lg_amount": make_series(dates, instruments, lambda di, ii: [100, 120, 110, 40, 90][ii], "sell_lg_amount"),
        "buy_sm_amount": make_series(dates, instruments, lambda di, ii: [80, 90, 100, 60, 90][ii], "buy_sm_amount"),
        "sell_sm_amount": make_series(dates, instruments, lambda di, ii: [100, 110, 120, 80, 95][ii], "sell_sm_amount"),
        "rzye": make_series(dates, instruments, lambda di, ii: [8e8, 7e8, 5e8, 2e8, 4e8][ii], "rzye"),
        "rqye": make_series(dates, instruments, lambda di, ii: [1e8, 1.2e8, 1.5e8, 1.8e8, 1.3e8][ii], "rqye"),
        "rzmre": make_series(dates, instruments, lambda di, ii: [50e6, 45e6, 30e6, 10e6, 25e6][ii], "rzmre"),
        "rzche": make_series(dates, instruments, lambda di, ii: [30e6, 28e6, 25e6, 12e6, 20e6][ii], "rzche"),
        "up_limit": make_series(dates, instruments, lambda di, ii: 12 + ii, "up_limit"),
        "down_limit": make_series(dates, instruments, lambda di, ii: 8 + ii, "down_limit"),
        "core_profit_q": make_series(dates, instruments, lambda di, ii: [1e8, 0.8e8, 0.2e8, -0.5e8, 0.4e8][ii], "core_profit_q"),
        "pit_q_op_qoq": make_series(dates, instruments, lambda di, ii: [10, 8, 3, -5, 4][ii], "pit_q_op_qoq"),
        "p_change_min": make_series(dates, instruments, lambda di, ii: [50, 30, 5, -20, 8][ii], "p_change_min"),
        "p_change_max": make_series(dates, instruments, lambda di, ii: [80, 40, 10, -10, 12][ii], "p_change_max"),
        "holder_num": make_series(dates, instruments, lambda di, ii: [20000 - di * 3, 25000 - di * 2, 28000, 35000 + di, 26000 - di][ii], "holder_num"),
    }


class ThemeStrategyTests(unittest.TestCase):
    def test_generate_component_specs_is_rich_but_bounded(self):
        raw_fields = build_fake_raw_fields()
        provider = FakeProvider(raw_fields)
        theme = get_theme_spec("small_cap")
        inventory, _ = provider.audit_fields(
            [item for item in get_field_definitions() if theme.theme_id in item.theme_tags],
            theme.data_start,
            "2026-02-28",
        )
        specs = generate_component_specs("small_cap", inventory)
        component_ids = {spec.component_id for spec in specs}

        self.assertIn("small_cap_total_mv_small_rank", component_ids)
        self.assertIn("small_cap_pb_value_rank", component_ids)
        self.assertIn("small_cap_low_vol_20d", component_ids)
        self.assertEqual(len(component_ids), len(specs))
        self.assertLess(len(specs), 30)

    def test_st_universe_uses_full_market_ret250_percentile_before_filtering(self):
        raw_fields = build_fake_raw_fields()
        provider = FakeProvider(raw_fields)
        support = build_fake_support()
        pipeline = ThemeStrategyPipeline(provider=provider, output_root=PROJECT_ROOT / "workspace" / "outputs" / "theme_strategy" / "test_tmp")
        theme = get_theme_spec("st")
        with patch("src.alpha_research.theme_strategy.pipeline.build_support", return_value=support):
            artifacts = pipeline.prepare_theme(theme)
        universe = next(item for item in theme.universe_candidates if item.candidate_id == "st_u3")
        dates = [support.trade_calendar[-2], support.trade_calendar[-1]]
        eligible_map = pipeline._build_universe_eligible_map(artifacts, universe, dates)

        self.assertIn("000002_SZ", eligible_map[dates[0]])
        self.assertNotIn("000001_SZ", eligible_map[dates[0]])

    def test_rank_component_within_universe_and_seed_recipes(self):
        raw_fields = build_fake_raw_fields()
        provider = FakeProvider(raw_fields)
        theme = get_theme_spec("small_cap")
        inventory, filtered = provider.audit_fields(
            [item for item in get_field_definitions() if theme.theme_id in item.theme_tags],
            theme.data_start,
            "2026-02-28",
        )
        specs = generate_component_specs("small_cap", inventory)
        spec_map = {spec.component_id: spec for spec in specs}
        engine = ComponentEngine(filtered)
        sample_dates = pd.date_range("2025-10-31", "2026-02-28", freq="ME")
        eligible_map = {date: {"000001_SZ", "000002_SZ", "000003_SZ"} for date in sample_dates}
        ranked = rank_component_within_universe(
            engine.get_series(spec_map["small_cap_total_mv_small_rank"]),
            eligible_map,
            spec_map["small_cap_total_mv_small_rank"].expected_sign,
        )
        recipes = build_seed_recipes_for_theme("small_cap", set(spec_map))

        self.assertFalse(ranked.empty)
        self.assertTrue(all(len(recipe.component_ids) <= 3 for recipe in recipes))
        self.assertIn("size_only", {recipe.recipe_id for recipe in recipes})

    def test_pipeline_smoke_run_theme_with_fake_provider(self):
        raw_fields = build_fake_raw_fields()
        provider = FakeProvider(raw_fields)
        support = build_fake_support()
        with temp_output_dir("theme_pipeline_smoke") as output_dir:
            pipeline = ThemeStrategyPipeline(provider=provider, output_root=output_dir)
            with patch("src.alpha_research.theme_strategy.pipeline.build_support", return_value=support), patch.object(
                ThemeStrategyPipeline,
                "_run_event_driven_confirmation",
                return_value=pd.DataFrame(
                    [
                        {
                            "theme_id": "small_cap",
                            "universe_id": "sc_u1",
                            "recipe_id": "size_only",
                            "topk": 4,
                            "rebalance_days": 5,
                            "relative_excess_return": 0.05,
                            "max_drawdown": -0.10,
                            "avg_turnover": 0.20,
                            "trade_count": 10,
                        }
                    ]
                ),
            ):
                result = pipeline.run(theme="small_cap", stage="all")

            self.assertTrue((result / "small_cap" / "field_inventory.csv").exists())
            self.assertTrue((result / "small_cap" / "component_registry.csv").exists())
            self.assertTrue((result / "small_cap" / "component_card.csv").exists())
            self.assertTrue((result / "small_cap" / "signal_recipe_summary.csv").exists())
            self.assertTrue((result / "small_cap" / "event_driven_variant_summary.csv").exists())
            self.assertTrue((result / "theme_opportunity_ranking.csv").exists())
            universe_md = (result / "small_cap" / "universe_selection_rationale_zh.md").read_text(encoding="utf-8")
            market_md = (result / "market_opportunity_summary_zh.md").read_text(encoding="utf-8")
            component_md = (result / "small_cap" / "component_selection_rationale_zh.md").read_text(encoding="utf-8")
            signal_md = (result / "small_cap" / "signal_selection_rationale_zh.md").read_text(encoding="utf-8")
            review_md = (result / "small_cap" / "theme_review_zh.md").read_text(encoding="utf-8")
            self.assertIn("候选 Universe 定义", universe_md)
            self.assertIn("排序结果", universe_md)
            self.assertIn("sc_u1", universe_md)
            self.assertIn("当前最优 Universe", market_md)
            self.assertIn("component diagnostics", market_md)
            self.assertIn("## sc_u1", component_md)
            self.assertIn("主要淘汰原因", component_md)
            self.assertTrue("前十名配方" in signal_md or "当前没有可写入的 recipe 排名结果" in signal_md)
            self.assertTrue("最优向量化结果" in review_md or "Event-Driven 确认" in review_md)
            self.assertIn("Event-Driven 确认", review_md)

    def test_pipeline_event_driven_quick_mode_reuses_recipe_outputs(self):
        raw_fields = build_fake_raw_fields()
        provider = FakeProvider(raw_fields)
        support = build_fake_support()
        with temp_output_dir("theme_quick_mode") as temp_root:
            output_dir = temp_root / "quick_output"
            source_dir = temp_root / "recipe_source" / "small_cap"
            source_dir.mkdir(parents=True, exist_ok=True)

            pd.DataFrame(
                [
                    {
                        "rank": 1,
                        "theme_id": "small_cap",
                        "universe_id": "sc_u4",
                        "median_stitched_relative_excess_return": 9.19,
                        "median_positive_excess_folds": 7,
                        "median_holdout_relative_excess_return": 0.13,
                        "median_worst_max_drawdown": -0.32,
                        "median_avg_turnover": 0.31,
                    },
                    {
                        "rank": 2,
                        "theme_id": "small_cap",
                        "universe_id": "sc_u5",
                        "median_stitched_relative_excess_return": 7.72,
                        "median_positive_excess_folds": 7,
                        "median_holdout_relative_excess_return": 0.10,
                        "median_worst_max_drawdown": -0.30,
                        "median_avg_turnover": 0.28,
                    },
                ]
            ).to_csv(source_dir / "universe_search_summary.csv", index=False, encoding="utf-8-sig")
            pd.DataFrame(
                [
                    {
                        "universe_id": "sc_u4",
                        "component_id": "small_cap_total_mv_small_rank",
                        "theme_id": "small_cap",
                        "coverage_ratio": 1.0,
                        "coverage_tier": "A",
                        "mean_rank_ic": 0.12,
                        "rank_icir": 1.8,
                        "positive_validation_folds": 6,
                        "total_validation_folds": 7,
                        "direction_consistent": True,
                        "max_abs_corr": 0.0,
                        "marginal_rank_icir": 0.2,
                        "cluster_id": "cluster_01",
                        "selection_score": 2.3,
                        "selected_for_recipe": True,
                        "rejection_reason": "",
                    },
                    {
                        "universe_id": "sc_u5",
                        "component_id": "small_cap_dividend_rank",
                        "theme_id": "small_cap",
                        "coverage_ratio": 1.0,
                        "coverage_tier": "A",
                        "mean_rank_ic": 0.08,
                        "rank_icir": 1.2,
                        "positive_validation_folds": 5,
                        "total_validation_folds": 7,
                        "direction_consistent": True,
                        "max_abs_corr": 0.1,
                        "marginal_rank_icir": 0.1,
                        "cluster_id": "cluster_02",
                        "selection_score": 1.7,
                        "selected_for_recipe": True,
                        "rejection_reason": "",
                    },
                ]
            ).to_csv(source_dir / "component_card.csv", index=False, encoding="utf-8-sig")
            pd.DataFrame(
                [
                    {"universe_id": "sc_u4", "component_id": "small_cap_total_mv_small_rank", "cluster_id": "cluster_01"},
                    {"universe_id": "sc_u5", "component_id": "small_cap_dividend_rank", "cluster_id": "cluster_02"},
                ]
            ).to_csv(source_dir / "component_cluster_map.csv", index=False, encoding="utf-8-sig")
            pd.DataFrame(
                [
                    {
                        "rank": 1,
                        "theme_id": "small_cap",
                        "stage": "recipe",
                        "universe_id": "sc_u4",
                        "recipe_id": "size_only",
                        "topk": 4,
                        "rebalance_days": 5,
                        "stitched_relative_excess_return": 2.6,
                        "positive_excess_folds": 7,
                        "holdout_relative_excess_return": 0.13,
                        "worst_max_drawdown": -0.33,
                        "avg_turnover": 0.31,
                        "component_ids": "small_cap_total_mv_small_rank",
                        "weights": "1.0",
                        "construction_rule": "seed",
                        "selection_note": "seed recipe",
                    }
                ]
            ).to_csv(source_dir / "signal_recipe_summary.csv", index=False, encoding="utf-8-sig")

            pipeline = ThemeStrategyPipeline(provider=provider, output_root=output_dir)
            with patch("src.alpha_research.theme_strategy.pipeline.build_support", return_value=support), patch.object(
                ThemeStrategyPipeline,
                "evaluate_recipe_variant",
                side_effect=AssertionError("quick mode should not rerun vectorized recipe search"),
            ), patch.object(
                ThemeStrategyPipeline,
                "_run_event_driven_confirmation",
                return_value=pd.DataFrame(
                    [
                        {
                            "theme_id": "small_cap",
                            "universe_id": "sc_u4",
                            "recipe_id": "size_only",
                            "topk": 4,
                            "rebalance_days": 5,
                            "relative_excess_return": 0.08,
                            "max_drawdown": -0.12,
                            "avg_turnover": 0.22,
                            "trade_count": 12,
                        }
                    ]
                ),
            ):
                result = pipeline.run(
                    theme="small_cap",
                    stage="event_driven",
                    recipe_source_run_dir=source_dir.parent,
                )

            self.assertTrue((result / "small_cap" / "signal_recipe_summary.csv").exists())
            self.assertTrue((result / "small_cap" / "event_driven_variant_summary.csv").exists())
            self.assertTrue((result / "small_cap" / "theme_review_zh.md").exists())
            signal_summary = pd.read_csv(result / "small_cap" / "signal_recipe_summary.csv")
            self.assertEqual(signal_summary.iloc[0]["recipe_id"], "size_only")

    def test_sort_event_summary_frame(self):
        frame = pd.DataFrame(
            [
                {"recipe_id": "b", "relative_excess_return": 0.05, "max_drawdown": -0.20, "avg_turnover": 0.10, "trade_count": 5},
                {"recipe_id": "a", "relative_excess_return": 0.08, "max_drawdown": -0.25, "avg_turnover": 0.12, "trade_count": 4},
                {"recipe_id": "c", "relative_excess_return": 0.08, "max_drawdown": -0.15, "avg_turnover": 0.15, "trade_count": 7},
            ]
        )
        sorted_frame = sort_event_summary_frame(frame)
        self.assertEqual(sorted_frame.iloc[0]["recipe_id"], "c")
        self.assertEqual(sorted_frame.iloc[1]["recipe_id"], "a")
        self.assertEqual(sorted_frame.iloc[0]["rank"], 1)

    def test_theme_strategy_pipeline_writes_run_metadata_and_latest_index(self):
        with temp_output_dir("theme_run_metadata") as temp_root:
            run_dir = temp_root / "theme_strategy_small_cap_recipe_test"
            (run_dir / "small_cap").mkdir(parents=True, exist_ok=True)
            (run_dir / "small_cap" / "field_inventory.csv").write_text("field_name\nclose\n", encoding="utf-8")
            (run_dir / "small_cap" / "component_registry.csv").write_text(
                "component_id,theme_id,source_fields,source_type,transform_family,transform_params,expected_sign,economic_role,coverage_tier,notes\n"
                "small_cap_total_mv_small_rank,small_cap,\"('total_mv',)\",field_transform,level_rank,\"{'mode': 'direct'}\",-1,core_thesis,A,size core\n",
                encoding="utf-8",
            )

            with patch.object(theme_cli, "DEFAULT_RUNS_ROOT", temp_root), patch.object(
                theme_cli,
                "DEFAULT_CANDIDATE_REGISTRY_DIR",
                temp_root / "candidate_registry",
            ), patch.object(
                theme_cli.ThemeStrategyPipeline,
                "run",
                return_value=run_dir,
            ):
                result = theme_cli.run_theme_strategy_pipeline(
                    theme_cli.parse_args(
                        [
                            "--theme",
                            "small_cap",
                            "--stage",
                            "recipe",
                            "--output-dir",
                            str(run_dir),
                        ]
                    )
                )

            self.assertEqual(result, run_dir)
            metadata = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
            manifest = json.loads((run_dir / "artifact_manifest.json").read_text(encoding="utf-8"))
            latest = json.loads((temp_root / "latest_runs.json").read_text(encoding="utf-8"))

            self.assertEqual(metadata["status"], "completed")
            self.assertEqual(metadata["theme"], "small_cap")
            self.assertEqual(metadata["stage"], "recipe")
            self.assertGreaterEqual(int(metadata["artifact_count"]), 1)
            self.assertEqual(metadata["execution_mode"], "full_pipeline")
            self.assertTrue(any(item["path"] == "small_cap/field_inventory.csv" for item in manifest["files"]))
            self.assertEqual(latest["by_theme"]["small_cap"]["stages"]["recipe"], str(run_dir))
            self.assertEqual(latest["latest_run_dir"], str(run_dir))

    def test_theme_strategy_cli_default_run_name_includes_theme_and_stage(self):
        with patch.object(theme_cli, "DEFAULT_RUNS_ROOT", PROJECT_ROOT / "workspace" / "outputs" / "theme_strategy_test"):
            resolved = theme_cli.resolve_output_dir(None, "small_cap", "event_driven")

        self.assertTrue(resolved.name.startswith("theme_strategy_small_cap_event_driven_"))

    def test_theme_strategy_configure_logging_replaces_handlers_cleanly(self):
        with temp_output_dir("theme_logging") as temp_root:
            output_dir = temp_root / "logs"
            theme_cli.configure_logging(output_dir)
            first_handlers = list(logging.getLogger().handlers)
            self.assertEqual(len(first_handlers), 2)
            self.assertTrue(any(getattr(handler, "baseFilename", "").endswith("run_console.log") for handler in first_handlers))

            theme_cli.configure_logging(output_dir)
            second_handlers = list(logging.getLogger().handlers)
            self.assertEqual(len(second_handlers), 2)
            self.assertNotEqual(id(first_handlers[0]), id(second_handlers[0]))
            self.assertTrue(all(getattr(handler, "stream", None) is None or not getattr(handler.stream, "closed", False) for handler in second_handlers))

            logging.shutdown()
            root_logger = logging.getLogger()
            for handler in list(root_logger.handlers):
                root_logger.removeHandler(handler)
                try:
                    handler.close()
                except Exception:
                    pass


class QlibFieldProviderStageThreadingTests(unittest.TestCase):
    """Gate 0 regression (jolly-seeking-lollipop):
    QlibFieldProvider.load_named_expressions must thread the stage parameter
    through to qlib_windowed_features. Default is is_only (backward compat);
    explicit oos_test must propagate.
    """

    def test_load_named_expressions_threads_stage_kwarg(self):
        # Verify the function signature accepts stage and that the body uses
        # the parameter (not a hardcoded literal) by inspecting source.
        # This avoids pyarrow extension collisions caused by importing qlib.data
        # in a test environment that other tests also mock.
        from src.alpha_research.theme_strategy import data as theme_data
        import inspect

        sig = inspect.signature(theme_data.QlibFieldProvider.load_named_expressions)
        self.assertIn("stage", sig.parameters)
        self.assertEqual(sig.parameters["stage"].default, "is_only")

        src = inspect.getsource(theme_data.QlibFieldProvider.load_named_expressions)
        # The call to qlib_windowed_features must use the parameter, not a
        # hardcoded "is_only" literal (the bug we are fixing). Signature
        # default value of 'is_only' is fine.
        self.assertIn("stage=stage", src)


if __name__ == "__main__":
    unittest.main()
