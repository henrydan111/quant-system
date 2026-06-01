"""Phase 5 slice 1 — the factor_lifecycle profile is registered and its DAG is IS-ONLY.

The orchestrator-level mirror of the Phase-4 leakage guard: the compiled DAG must have NO
`oos_test` stage, NO OOS backtest, and (by construction) never claims a holdout seal — the
`candidate→approved` OOS spend is a SEPARATE frozen-set / promotion-gate path, never this
profile. The object_resolver step must be EXPLICIT (formal_requires_resolver does NOT
auto-inject it).
"""

import tempfile
import unittest
from pathlib import Path

from src.research_orchestrator import ResearchRequest, profile_registry

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_OUTPUTS = PROJECT_ROOT / "workspace" / "outputs"


class FactorLifecycleProfileTests(unittest.TestCase):
    def _compile(self):
        profile = profile_registry().get("factor_lifecycle")
        WORKSPACE_OUTPUTS.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="p5_profile_", dir=WORKSPACE_OUTPUTS) as d:
            request = ResearchRequest(
                profile_id="factor_lifecycle", mode="formal", inputs={"output_dir": d},
            )
            return profile, profile.dag_builder(request, list(profile.default_capabilities))

    def test_profile_registered_formal_only(self):
        profile = profile_registry().get("factor_lifecycle")
        self.assertEqual(profile.supported_modes, ("formal",))
        self.assertIn("factor", profile.consumes_types)
        self.assertEqual(profile.produces_types, ("factor",))
        self.assertEqual(profile.execution_model, "dag")

    def test_dag_is_is_only_no_oos_stage_or_backtest(self):
        _, dag = self._compile()
        steps = dag.steps
        stages = [s.config.get("stage") for s in steps]
        caps = [s.capability for s in steps]
        step_ids = [s.step_id for s in steps]
        # IS-ONLY: no oos_test stage, no OOS backtest leg, no oos-named step
        self.assertNotIn("oos_test", stages)
        self.assertNotIn("event_driven_backtest", caps)
        self.assertNotIn("vectorized_backtest", caps)
        self.assertFalse(any("oos" in str(sid).lower() for sid in step_ids), step_ids)

    def test_dag_has_explicit_resolver_gate_and_lifecycle_publish(self):
        _, dag = self._compile()
        handlers = [s.handler for s in dag.steps]
        # explicit lifecycle resolver (NOT auto-injected; NOT the generic/validation resolver)
        self.assertIn("factor_lifecycle_object_resolver", handlers)
        # the gate triplet is injected before publish
        self.assertIn("gate_evaluation", handlers)
        self.assertIn("gate_concern_scoring", handlers)
        self.assertIn("gate_review", handlers)
        # lifecycle-specific dataset/walk-forward/publish handlers
        self.assertIn("factor_lifecycle_dataset_build", handlers)
        self.assertIn("factor_lifecycle_walk_forward", handlers)
        self.assertIn("factor_lifecycle_registry_publish", handlers)
        # walk-forward must come BEFORE the gate; publish must come AFTER gate_review
        ids = [s.step_id for s in dag.steps]
        self.assertLess(ids.index("factor_lifecycle_walk_forward"), ids.index("gate_review"))
        self.assertLess(ids.index("gate_review"), ids.index("registry_publish"))


if __name__ == "__main__":
    unittest.main()
