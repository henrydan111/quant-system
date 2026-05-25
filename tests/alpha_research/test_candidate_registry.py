import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

import src.alpha_research.theme_strategy.cli as theme_cli
from src.alpha_research.candidate_registry import CandidateRegistryStore
from src.research_orchestrator.registries import SignalRegistryStore


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_OUTPUTS = PROJECT_ROOT / "workspace" / "outputs"


class CandidateRegistryTests(unittest.TestCase):
    def make_temp_dir(self, name: str):
        WORKSPACE_OUTPUTS.mkdir(parents=True, exist_ok=True)
        return tempfile.TemporaryDirectory(prefix=f"{name}_", dir=WORKSPACE_OUTPUTS)

    def _write_theme_run(self, run_dir: Path) -> None:
        theme_dir = run_dir / "small_cap"
        theme_dir.mkdir(parents=True, exist_ok=True)
        component_registry = pd.DataFrame(
            [
                {
                    "component_id": "small_cap_total_mv_small_rank",
                    "theme_id": "small_cap",
                    "source_fields": "('total_mv',)",
                    "source_type": "field_transform",
                    "transform_family": "level_rank",
                    "transform_params": "{'mode': 'direct'}",
                    "expected_sign": -1,
                    "economic_role": "core_thesis",
                    "coverage_tier": "A",
                    "notes": "size core",
                },
                {
                    "component_id": "small_cap_low_vol_20d",
                    "theme_id": "small_cap",
                    "source_fields": "('close','adj_factor')",
                    "source_type": "field_transform",
                    "transform_family": "stability",
                    "transform_params": "{'mode': 'rolling_vol', 'window': 20}",
                    "expected_sign": -1,
                    "economic_role": "execution_guardrail",
                    "coverage_tier": "A",
                    "notes": "defensive",
                },
            ]
        )
        component_card = pd.DataFrame(
            [
                {
                    "component_id": "small_cap_total_mv_small_rank",
                    "theme_id": "small_cap",
                    "coverage_ratio": 0.99,
                    "coverage_tier": "A",
                    "mean_rank_ic": 0.03,
                    "rank_icir": 1.8,
                    "positive_validation_folds": 6,
                    "total_validation_folds": 7,
                    "direction_consistent": True,
                    "max_abs_corr": 0.25,
                    "marginal_rank_icir": 0.6,
                    "cluster_id": "cluster_01",
                    "selection_score": 2.4,
                    "selected_for_recipe": True,
                    "rejection_reason": "",
                    "universe_id": "sc_u4",
                }
            ]
        )
        recipe_summary = pd.DataFrame(
            [
                {
                    "theme_id": "small_cap",
                    "universe_id": "sc_u4",
                    "recipe_id": "size_only",
                    "topk": 10,
                    "rebalance_days": 5,
                    "stitched_relative_excess_return": 0.12,
                    "positive_excess_folds": 5,
                    "holdout_relative_excess_return": 0.06,
                    "worst_max_drawdown": -0.18,
                    "avg_turnover": 0.2,
                    "component_ids": "small_cap_total_mv_small_rank",
                    "weights": "1.0",
                    "construction_rule": "equal_weight_seed",
                    "selection_note": "seed",
                }
            ]
        )
        event_summary = pd.DataFrame(
            [
                {
                    "theme_id": "small_cap",
                    "universe_id": "sc_u4",
                    "recipe_id": "size_only",
                    "topk": 10,
                    "rebalance_days": 5,
                    "relative_excess_return": 0.04,
                    "max_drawdown": -0.12,
                    "avg_turnover": 0.18,
                    "trade_count": 9,
                }
            ]
        )
        component_registry.to_csv(theme_dir / "component_registry.csv", index=False)
        component_card.to_csv(theme_dir / "component_card.csv", index=False)
        recipe_summary.to_csv(theme_dir / "signal_recipe_summary.csv", index=False)
        event_summary.to_csv(theme_dir / "event_driven_variant_summary.csv", index=False)
        (run_dir / "run_metadata.json").write_text(
            json.dumps(
                {
                    "generated_at": "2026-04-06 14:00:00",
                    "theme": "small_cap",
                    "stage": "event_driven",
                    "status": "completed",
                    "artifact_count": 4,
                },
                ensure_ascii=True,
                indent=2,
            ),
            encoding="utf-8",
        )

    def test_import_theme_run_creates_component_candidates_only_by_default(self):
        with self.make_temp_dir("candidate_registry_import") as temp_dir:
            run_dir = Path(temp_dir) / "theme_run"
            run_dir.mkdir(parents=True, exist_ok=True)
            self._write_theme_run(run_dir)

            store = CandidateRegistryStore(Path(temp_dir) / "candidate_registry")
            result = store.import_theme_strategy_run(run_dir)
            store.save()

            current_df = store.candidate_master[store.candidate_master["is_current"].fillna(False)].copy()
            self.assertEqual(result["candidate_count"], 2)
            self.assertEqual(len(current_df), 2)
            self.assertEqual(int((current_df["object_type"] == "theme_component").sum()), 2)
            self.assertEqual(int((current_df["object_type"] == "theme_recipe").sum()), 0)

            component_row = current_df[current_df["object_name"] == "small_cap_total_mv_small_rank"].iloc[0]
            self.assertEqual(component_row["recommended_status"], "candidate")

            html_path = Path(temp_dir) / "candidate_registry" / "candidate_registry_review.html"
            self.assertTrue(html_path.exists())
            html_text = html_path.read_text(encoding="utf-8")
            self.assertIn("Candidate Registry Review", html_text)
            self.assertIn("small_cap_total_mv_small_rank", html_text)

    def test_signal_registry_imports_theme_recipes(self):
        with self.make_temp_dir("signal_registry_import") as temp_dir:
            run_dir = Path(temp_dir) / "theme_run"
            run_dir.mkdir(parents=True, exist_ok=True)
            self._write_theme_run(run_dir)

            store = SignalRegistryStore(Path(temp_dir) / "signal_registry")
            result = store.import_theme_strategy_run(run_dir)
            store.save()

            current_df = store.master[store.master["is_current"].fillna(False)].copy()
            self.assertEqual(result["signal_count"], 1)
            self.assertEqual(len(current_df), 1)
            self.assertEqual(current_df.iloc[0]["object_type"], "signal")
            self.assertEqual(current_df.iloc[0]["object_name"], "size_only")
            self.assertTrue((Path(temp_dir) / "signal_registry" / "signal_registry_review.html").exists())

    def test_definition_change_creates_new_version(self):
        with self.make_temp_dir("candidate_registry_version") as temp_dir:
            registry_dir = Path(temp_dir) / "candidate_registry"
            store = CandidateRegistryStore(registry_dir)
            run_dir = Path(temp_dir) / "theme_run"
            run_dir.mkdir(parents=True, exist_ok=True)
            self._write_theme_run(run_dir)
            store.import_theme_strategy_run(run_dir)

            component_registry = pd.read_csv(run_dir / "small_cap" / "component_registry.csv")
            component_registry.loc[0, "transform_params"] = "{'mode': 'log'}"
            component_registry.to_csv(run_dir / "small_cap" / "component_registry.csv", index=False)
            (run_dir / "run_metadata.json").write_text(
                json.dumps(
                    {
                        "generated_at": "2026-04-06 15:00:00",
                        "theme": "small_cap",
                        "stage": "event_driven",
                        "status": "completed",
                        "artifact_count": 4,
                    },
                    ensure_ascii=True,
                    indent=2,
                ),
                encoding="utf-8",
            )

            store.import_theme_strategy_run(run_dir)
            rows = store.candidate_master[
                store.candidate_master["candidate_id"] == "theme_component::small_cap_total_mv_small_rank"
            ].sort_values("version")
            self.assertEqual(rows["version"].tolist(), [1, 2])
            self.assertEqual(rows["is_current"].tolist(), [False, True])


class ThemeStrategyCandidatePublishTests(unittest.TestCase):
    def test_theme_cli_delegates_sandbox_run_to_orchestrator(self):
        with tempfile.TemporaryDirectory(dir=str(WORKSPACE_OUTPUTS)) as tmpdir:
            temp_root = Path(tmpdir)
            run_dir = temp_root / "theme_strategy_small_cap_recipe_test"
            registry_dir = temp_root / "candidate_registry"

            with patch.object(theme_cli, "DEFAULT_RUNS_ROOT", temp_root), patch.object(
                theme_cli,
                "DEFAULT_CANDIDATE_REGISTRY_DIR",
                registry_dir,
            ), patch(
                "src.research_orchestrator.engine.run_research",
                return_value=SimpleNamespace(run_dir=str(run_dir)),
            ) as run_research:
                result = theme_cli.main(
                    [
                        "--theme",
                        "small_cap",
                        "--stage",
                        "event_driven",
                        "--mode",
                        "sandbox",
                        "--output-dir",
                        str(run_dir),
                    ]
                )

            self.assertEqual(result, run_dir)
            request = run_research.call_args.args[0]
            self.assertEqual(request.profile_id, "theme_strategy")
            self.assertEqual(request.mode, "sandbox")
            self.assertEqual(request.inputs["theme"], "small_cap")
            self.assertEqual(request.inputs["stage"], "event_driven")
            self.assertEqual(Path(request.inputs["output_dir"]), run_dir.resolve())
            self.assertEqual(Path(request.run_context["candidate_registry_dir"]), registry_dir.resolve())
