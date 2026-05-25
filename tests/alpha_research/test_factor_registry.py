import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src.alpha_research.factor_registry import FactorRegistryStore

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_OUTPUTS = PROJECT_ROOT / "workspace" / "outputs"


class FactorRegistryTests(unittest.TestCase):
    def make_temp_dir(self, name: str):
        WORKSPACE_OUTPUTS.mkdir(parents=True, exist_ok=True)
        return tempfile.TemporaryDirectory(prefix=f"{name}_", dir=WORKSPACE_OUTPUTS)

    def test_sync_catalog_creates_expected_current_counts(self):
        # Updated 2026-04-27: catalog now includes 4 industry-relative factors
        # via get_industry_relative_defs() (plan vast-exploring-rabbit v8 phase B3),
        # bringing the total to 147 base + 20 composite + 4 industry_relative = 171.
        with self.make_temp_dir("factor_registry_sync") as temp_dir:
            store = FactorRegistryStore(temp_dir)
            result = store.sync_catalog(record_run=False, generated_at="2026-04-04 21:00:00")

            current_df = store.factor_master[store.factor_master["is_current"].fillna(False)].copy()

            self.assertEqual(result["current_factor_count"], 171)
            self.assertEqual(len(current_df), 171)
            self.assertEqual(int((current_df["factor_kind"] == "base").sum()), 147)
            self.assertEqual(int((current_df["factor_kind"] == "composite").sum()), 20)
            self.assertEqual(int((current_df["factor_kind"] == "industry_relative").sum()), 4)

            store.sync_catalog(record_run=False, generated_at="2026-04-04 21:05:00")
            current_df = store.factor_master[store.factor_master["is_current"].fillna(False)].copy()
            self.assertEqual(len(current_df), 171)
            self.assertEqual(current_df["factor_id"].nunique(), 171)

    def test_base_factor_definition_change_creates_new_version(self):
        with self.make_temp_dir("factor_registry_base_version") as temp_dir:
            store = FactorRegistryStore(temp_dir)
            with (
                patch(
                    "src.alpha_research.factor_registry.store.get_factor_catalog",
                    side_effect=[
                        {"toy_factor": "Ref($close, 1)"},
                        {"toy_factor": "Ref($close, 2)"},
                    ],
                ),
                patch(
                    "src.alpha_research.factor_registry.store.get_composite_defs",
                    return_value=[],
                ),
                patch(
                    "src.alpha_research.factor_registry.store.get_category_map",
                    return_value={"toy_factor": "Toy"},
                ),
            ):
                store.sync_catalog(record_run=False, generated_at="2026-04-04 21:00:00")
                store.sync_catalog(record_run=False, generated_at="2026-04-04 21:10:00")

            factor_rows = store.factor_master[store.factor_master["factor_id"] == "toy_factor"].sort_values("version")
            self.assertEqual(factor_rows["version"].tolist(), [1, 2])
            self.assertEqual(factor_rows["is_current"].tolist(), [False, True])
            self.assertEqual(factor_rows.iloc[-1]["status"], "draft")

    def test_composite_definition_change_creates_new_version(self):
        with self.make_temp_dir("factor_registry_composite_version") as temp_dir:
            store = FactorRegistryStore(temp_dir)
            with (
                patch(
                    "src.alpha_research.factor_registry.store.get_factor_catalog",
                    return_value={},
                ),
                patch(
                    "src.alpha_research.factor_registry.store.get_composite_defs",
                    side_effect=[
                        [{"name": "comp_toy", "components": ["a", "b"]}],
                        [{"name": "comp_toy", "components": ["a", "b"], "weights": [0.7, 0.3]}],
                    ],
                ),
                patch(
                    "src.alpha_research.factor_registry.store.get_category_map",
                    return_value={"comp_toy": "Composite"},
                ),
            ):
                store.sync_catalog(record_run=False, generated_at="2026-04-04 21:00:00")
                store.sync_catalog(record_run=False, generated_at="2026-04-04 21:10:00")

            factor_rows = store.factor_master[store.factor_master["factor_id"] == "comp_toy"].sort_values("version")
            self.assertEqual(factor_rows["version"].tolist(), [1, 2])
            self.assertEqual(factor_rows["is_current"].tolist(), [False, True])

    def test_set_status_updates_master_and_history(self):
        with self.make_temp_dir("factor_registry_status") as temp_dir:
            store = FactorRegistryStore(temp_dir)
            store.sync_catalog(record_run=False, generated_at="2026-04-04 21:00:00")

            result = store.set_status(
                factor_id="liq_vol_cv_20d",
                status="approved",
                reason="manual promotion",
            )

            current_row = store.factor_master[
                (store.factor_master["factor_id"] == "liq_vol_cv_20d")
                & (store.factor_master["is_current"].fillna(False))
            ].iloc[0]
            self.assertEqual(result["new_status"], "approved")
            self.assertEqual(current_row["status"], "approved")
            self.assertEqual(len(store.status_history), 1)
            self.assertEqual(store.status_history.iloc[0]["reason"], "manual promotion")

    def test_save_generates_human_readable_html_review(self):
        with self.make_temp_dir("factor_registry_html") as temp_dir:
            store = FactorRegistryStore(temp_dir)
            store.sync_catalog(record_run=False, generated_at="2026-04-04 21:00:00")
            store.save()

            html_path = Path(temp_dir) / "factor_registry_review.html"
            self.assertTrue(html_path.exists())
            html_text = html_path.read_text(encoding="utf-8")
            self.assertIn("Formal Factor Registry Review", html_text)
            self.assertIn("liq_vol_cv_20d", html_text)
            self.assertIn("All Current Factors", html_text)

    def test_import_screening_is_idempotent_and_marks_legacy_binding_without_hashes(self):
        with self.make_temp_dir("factor_registry_screening") as temp_dir:
            store = FactorRegistryStore(temp_dir)
            run_dir = Path(temp_dir) / "screening_run"
            run_dir.mkdir(parents=True, exist_ok=True)

            metadata = {
                "generated_at": "2026-04-04 21:00:00",
                "start_date": "2012-01-01",
                "end_date": "2025-12-31",
                "include_new_data": True,
                "requested_kernels": "qlib default",
                "effective_kernels": "qlib default",
            }
            report_df = pd.DataFrame(
                [
                    {
                        "factor": "liq_vol_cv_20d",
                        "grade": "A (Graduated)",
                        "mean_rank_ic_5d": -0.05,
                        "rank_icir_5d": -0.70,
                        "ic_hit_rate_5d": 0.73,
                        "monotonic": True,
                        "ls_ann_return": -1.17,
                    },
                    {
                        "factor": "comp_val_qual",
                        "grade": "B (Strong IC)",
                        "mean_rank_ic_5d": 0.03,
                        "rank_icir_5d": 0.42,
                        "ic_hit_rate_5d": 0.61,
                        "monotonic": False,
                        "ls_ann_return": 0.22,
                    },
                ]
            )
            (run_dir / "factor_screening_run_metadata.json").write_text(
                json.dumps(metadata, ensure_ascii=True, indent=2),
                encoding="utf-8",
            )
            report_df.to_csv(run_dir / "factor_screening_report.csv", index=False)

            store.import_screening(run_dir)
            store.import_screening(run_dir)

            screening_rows = store.factor_evidence[store.factor_evidence["run_type"] == "screening"]
            self.assertEqual(len(screening_rows), 2)

            liq_row = store.factor_master[
                (store.factor_master["factor_id"] == "liq_vol_cv_20d")
                & (store.factor_master["is_current"].fillna(False))
            ].iloc[0]
            self.assertEqual(liq_row["definition_binding"], "legacy_best_effort")
            self.assertEqual(liq_row["latest_screening_grade"], "A (Graduated)")
            self.assertEqual(liq_row["recommended_status"], "candidate")

    def test_import_research_aggregates_validation_and_selection_counts(self):
        with self.make_temp_dir("factor_registry_research") as temp_dir:
            store = FactorRegistryStore(temp_dir)
            run_dir = Path(temp_dir) / "research_run"
            run_dir.mkdir(parents=True, exist_ok=True)

            metadata = {
                "generated_at": "2026-04-04 21:00:00",
                "benchmark": "000905.SH",
                "folds": [
                    {
                        "train_start": "2012-01-01",
                        "train_end": "2016-12-31",
                        "validation_start": "2017-01-01",
                        "validation_end": "2018-12-31",
                        "test_start": "2019-01-01",
                        "test_end": "2019-12-31",
                    }
                ],
                "kernel_meta": {
                    "requested_kernels": "qlib default",
                    "effective_kernels": "1",
                },
            }
            metrics_df = pd.DataFrame(
                [
                    {
                        "factor": "liq_vol_cv_20d",
                        "grade": "A (Graduated)",
                        "category": "Liquidity",
                        "mean_rank_ic_5d": -0.05,
                        "rank_icir_5d": -0.93,
                        "ic_hit_rate_5d": 0.78,
                        "best_decay_horizon": 10,
                        "peak_decay_icir": 0.76,
                        "ls_ann_return": -0.70,
                        "monotonic": True,
                    },
                    {
                        "factor": "comp_val_qual",
                        "grade": "B (Strong IC)",
                        "category": "Composite",
                        "mean_rank_ic_5d": 0.03,
                        "rank_icir_5d": 0.35,
                        "ic_hit_rate_5d": 0.61,
                        "best_decay_horizon": 20,
                        "peak_decay_icir": 0.40,
                        "ls_ann_return": 0.15,
                        "monotonic": False,
                    },
                ]
            )
            decisions_df = pd.DataFrame(
                [
                    {"factor": "liq_vol_cv_20d", "fold_id": "fold_01", "val_rank_icir": -0.8, "validation_pass": True},
                    {"factor": "liq_vol_cv_20d", "fold_id": "fold_02", "val_rank_icir": -0.7, "validation_pass": True},
                    {"factor": "liq_vol_cv_20d", "fold_id": "fold_03", "val_rank_icir": -0.6, "validation_pass": True},
                    {"factor": "liq_vol_cv_20d", "fold_id": "fold_04", "val_rank_icir": -0.5, "validation_pass": True},
                    {"factor": "comp_val_qual", "fold_id": "fold_01", "val_rank_icir": 0.2, "validation_pass": True},
                ]
            )
            selected_df = pd.DataFrame(
                [
                    {"fold_id": "fold_01", "selection_rank": 1, "factor": "liq_vol_cv_20d"},
                    {"fold_id": "fold_02", "selection_rank": 1, "factor": "liq_vol_cv_20d"},
                    {"fold_id": "fold_03", "selection_rank": 1, "factor": "liq_vol_cv_20d"},
                    {"fold_id": "fold_04", "selection_rank": 1, "factor": "liq_vol_cv_20d"},
                ]
            )

            (run_dir / "run_metadata.json").write_text(
                json.dumps(metadata, ensure_ascii=True, indent=2),
                encoding="utf-8",
            )
            metrics_df.to_csv(run_dir / "factor_research_metrics.csv", index=False)
            decisions_df.to_csv(run_dir / "factor_selection_decisions.csv", index=False)
            selected_df.to_csv(run_dir / "selected_core_factors_by_fold.csv", index=False)

            store.import_research(run_dir)

            liq_row = store.factor_master[
                (store.factor_master["factor_id"] == "liq_vol_cv_20d")
                & (store.factor_master["is_current"].fillna(False))
            ].iloc[0]
            self.assertEqual(int(liq_row["latest_validation_pass_count"]), 4)
            self.assertEqual(int(liq_row["latest_selected_fold_count"]), 4)
            self.assertEqual(liq_row["recommended_status"], "approved")


class FactorRegistryIntegrationTests(unittest.TestCase):
    SCREENING_RUN_DIR = PROJECT_ROOT / "workspace" / "research" / "alpha_mining" / "latest_backend_screening_20260401_new_data"
    RESEARCH_RUN_DIR = PROJECT_ROOT / "workspace" / "research" / "alpha_mining" / "event_driven_strategy_research_full_20260401_main"

    def make_temp_dir(self, name: str):
        WORKSPACE_OUTPUTS.mkdir(parents=True, exist_ok=True)
        return tempfile.TemporaryDirectory(prefix=f"{name}_", dir=WORKSPACE_OUTPUTS)

    @unittest.skipUnless(
        SCREENING_RUN_DIR.exists() and RESEARCH_RUN_DIR.exists(),
        "real screening/research run dirs not present",
    )
    def test_real_screening_and_research_imports(self):
        with self.make_temp_dir("factor_registry_real") as temp_dir:
            store = FactorRegistryStore(temp_dir)
            store.sync_catalog(record_run=True, generated_at="2026-04-04 21:00:00")
            screening_result = store.import_screening(self.SCREENING_RUN_DIR)
            research_result = store.import_research(self.RESEARCH_RUN_DIR)

            self.assertEqual(screening_result["factor_count"], 149)
            self.assertEqual(research_result["factor_count"], 43)

            liq_row = store.factor_master[
                (store.factor_master["factor_id"] == "liq_vol_cv_20d")
                & (store.factor_master["is_current"].fillna(False))
            ].iloc[0]
            rev_row = store.factor_master[
                (store.factor_master["factor_id"] == "rev_max_return_20d")
                & (store.factor_master["is_current"].fillna(False))
            ].iloc[0]
            comp_row = store.factor_master[
                (store.factor_master["factor_id"] == "comp_defensive")
                & (store.factor_master["is_current"].fillna(False))
            ].iloc[0]

            self.assertEqual(liq_row["latest_screening_grade"], "A (Graduated)")
            self.assertGreaterEqual(int(liq_row["latest_validation_pass_count"]), 1)
            self.assertGreaterEqual(int(rev_row["latest_selected_fold_count"]), 1)
            self.assertNotEqual(comp_row["latest_screening_grade"], "")

            store.set_status(
                factor_id="liq_vol_cv_20d",
                status="approved",
                reason="integration export test",
            )
            export_path = Path(temp_dir) / "approved.csv"
            export_count = store.export_current(export_path, status="approved")
            export_df = pd.read_csv(export_path)

            self.assertEqual(export_count, len(export_df))
            self.assertTrue((export_df["status"] == "approved").all())


if __name__ == "__main__":
    unittest.main()
