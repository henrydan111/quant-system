"""Phase 5 slice 2 — factor_lifecycle_object_resolver (draft-accepting + P1.3 + per-factor field gate)."""

import tempfile
import unittest
from pathlib import Path

from src.research_orchestrator import ResearchRequest, profile_registry
from src.research_orchestrator.dag import StepExecutionContext
from src.research_orchestrator.schema import AssetRef
from src.research_orchestrator.factor_lifecycle_steps import (
    handle_factor_lifecycle_object_resolver,
    per_factor_field_eligible,
)
from src.alpha_research.factor_registry import FactorRegistryStore
from src.alpha_research.factor_library.catalog import get_factor_catalog

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_OUTPUTS = PROJECT_ROOT / "workspace" / "outputs"


class FactorLifecycleResolverTests(unittest.TestCase):
    def _temp(self):
        WORKSPACE_OUTPUTS.mkdir(parents=True, exist_ok=True)
        return tempfile.TemporaryDirectory(prefix="p5_resolver_", dir=WORKSPACE_OUTPUTS)

    def _context(self, root: Path, factor_names):
        registry_dirs = {
            "factor_registry_dir": root / "factor_registry",
            "candidate_registry_dir": root / "candidate_registry",
            "signal_registry_dir": root / "signal_registry",
            "model_registry_dir": root / "model_registry",
            "strategy_registry_dir": root / "strategy_registry",
        }
        for p in registry_dirs.values():
            p.mkdir(parents=True, exist_ok=True)
        store = FactorRegistryStore(registry_dirs["factor_registry_dir"])
        store.sync_catalog(record_run=False, generated_at="2026-04-04 21:00:00")
        store.save()  # all 171 rows are `draft`

        consumes = [AssetRef(object_type="factor", object_name=n) for n in factor_names]
        request = ResearchRequest(
            profile_id="factor_lifecycle", mode="formal", consumes=consumes,
            inputs={"output_dir": str(root)},
        )
        profile = profile_registry().get("factor_lifecycle")
        dag = profile.dag_builder(request, list(profile.default_capabilities))
        step = next(s for s in dag.steps if s.handler == "factor_lifecycle_object_resolver")
        step_dir = root / "step"
        step_dir.mkdir(parents=True, exist_ok=True)
        return StepExecutionContext(
            request=request, profile=profile, dag=dag, step=step, run_dir=root,
            step_dir=step_dir, registry_dirs=registry_dirs,
            effective_capabilities=list(profile.default_capabilities),
            effective_capability_metadata=[], state={},
        )

    def test_resolver_accepts_draft_factors_and_runs_p13(self):
        with self._temp() as d:
            ctx = self._context(Path(d), ["mom_return_5d", "val_bp", "qual_roe"])
            result = handle_factor_lifecycle_object_resolver(ctx)
            self.assertEqual(result.status, "completed")
            # draft factors accepted (resolved, not rejected)
            self.assertEqual(set(result.outputs["field_eligible"]), {"mom_return_5d", "val_bp", "qual_roe"})
            # these three reference only approved fields -> eligible
            self.assertTrue(all(result.outputs["field_eligible"].values()))
            self.assertIn("definition_binding_report", result.outputs)  # P1.3 ran

    def test_per_factor_field_eligibility_partitions_the_catalog(self):
        # the 36 new-data alpha factors (flow_*/north_*/margin_*) touch quarantined fields
        # -> field-ineligible; the rest are eligible. Per-factor partition must be MIXED
        # (proves we exclude-and-continue rather than batch-raise).
        names = list(get_factor_catalog(include_new_data=True))
        elig = per_factor_field_eligible(names, stage="formal_validation")
        self.assertEqual(set(elig), set(names))
        self.assertTrue(any(elig.values()))        # some eligible
        self.assertFalse(all(elig.values()))       # some NOT eligible (quarantined-field factors)
        self.assertTrue(elig["mom_return_5d"])     # spot-check an obviously-eligible one

    def test_resolver_rejects_unknown_factor(self):
        with self._temp() as d:
            ctx = self._context(Path(d), ["mom_return_5d", "totally_unknown_factor_xyz"])
            with self.assertRaises(ValueError):
                handle_factor_lifecycle_object_resolver(ctx)


class FactorLifecycleDatasetBuildTests(unittest.TestCase):
    def _temp(self):
        WORKSPACE_OUTPUTS.mkdir(parents=True, exist_ok=True)
        return tempfile.TemporaryDirectory(prefix="p5_dataset_", dir=WORKSPACE_OUTPUTS)

    def _context(self, root: Path):
        request = ResearchRequest(
            profile_id="factor_lifecycle", mode="formal",
            inputs={
                "output_dir": str(root),
                "time_split": {"is_start": "2014-01-01", "is_end": "2020-12-31",
                               "oos_start": "2021-01-01", "oos_end": "2022-01-01"},
                "horizon": 20,
            },
        )
        profile = profile_registry().get("factor_lifecycle")
        dag = profile.dag_builder(request, list(profile.default_capabilities))
        step = next(s for s in dag.steps if s.handler == "factor_lifecycle_dataset_build")
        step_dir = root / "step"
        step_dir.mkdir(parents=True, exist_ok=True)
        return StepExecutionContext(
            request=request, profile=profile, dag=dag, step=step, run_dir=root,
            step_dir=step_dir, registry_dirs={}, effective_capabilities=[],
            effective_capability_metadata=[], state={},
        )

    def test_dataset_build_excludes_field_ineligible_from_compute(self):
        import types
        from unittest.mock import patch
        import pandas as pd
        from src.research_orchestrator import factor_lifecycle_steps as fls

        with self._temp() as d:
            ctx = self._context(Path(d))
            # resolver output: 2 eligible base factors + 1 field-INELIGIBLE base factor
            ctx.state["step_outputs"] = {
                "factor_lifecycle_object_resolver": {
                    "field_eligible": {"mom_return_5d": True, "val_bp": True, "qual_roe": False},
                }
            }
            captured = {}

            def spy(catalog, time_split, *, horizon=20, qlib_dir=None, **kw):
                captured["catalog"] = dict(catalog)
                captured["horizon"] = horizon
                return types.SimpleNamespace(max_label_realization_date=pd.Timestamp("2020-12-01"))

            with patch.object(fls, "load_is_windowed_panel", spy):
                result = fls.handle_factor_lifecycle_dataset_build(ctx)

            # the field-ineligible factor NEVER reaches the compute catalog
            self.assertIn("mom_return_5d", captured["catalog"])
            self.assertIn("val_bp", captured["catalog"])
            self.assertNotIn("qual_roe", captured["catalog"])
            self.assertEqual(captured["horizon"], 20)
            self.assertEqual(result.outputs["field_ineligible_factors"], ["qual_roe"])
            self.assertEqual(set(result.outputs["gated_base_factors"]), {"mom_return_5d", "val_bp"})
            # the panel is passed to the walk-forward step via state
            self.assertIn("panel", ctx.state["factor_lifecycle"])

    def test_dataset_build_raises_if_no_eligible_base(self):
        from src.research_orchestrator import factor_lifecycle_steps as fls
        with self._temp() as d:
            ctx = self._context(Path(d))
            ctx.state["step_outputs"] = {
                "factor_lifecycle_object_resolver": {"field_eligible": {"mom_return_5d": False}}
            }
            with self.assertRaises(ValueError):
                fls.handle_factor_lifecycle_dataset_build(ctx)


if __name__ == "__main__":
    unittest.main()
