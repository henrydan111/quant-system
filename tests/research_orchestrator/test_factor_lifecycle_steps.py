"""Phase 5 slice 2 — factor_lifecycle_object_resolver (draft-accepting + P1.3 + per-factor field gate)."""

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.research_orchestrator import ResearchRequest, profile_registry
from src.research_orchestrator.dag import StepExecutionContext
from src.research_orchestrator.schema import AssetRef
from src.research_orchestrator.factor_lifecycle_steps import (
    handle_factor_lifecycle_object_resolver,
    handle_factor_lifecycle_walk_forward,
    handle_factor_lifecycle_registry_publish,
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

    def test_dataset_build_gates_base_composite_industry_excludes_ineligible(self):
        # Phase 7: dataset_build splits eligible into base / composite / industry-relative and
        # feeds the unified Layer-2 builder; field-ineligible factors never reach compute.
        import types
        from unittest.mock import patch
        import pandas as pd
        from src.research_orchestrator import factor_lifecycle_steps as fls

        with self._temp() as d:
            ctx = self._context(Path(d))
            ctx.state["step_outputs"] = {
                "factor_lifecycle_object_resolver": {
                    "field_eligible": {
                        "mom_return_5d": True, "val_bp": True,      # base
                        "comp_small_value": True,                   # composite
                        "val_bp_industry_rel": True,                # industry-relative
                        "qual_roe": False,                          # field-INELIGIBLE
                    },
                }
            }
            captured = {}

            def spy(*, gated_base, gated_composite_defs, gated_industry_defs, time_split,
                    horizon=20, qlib_dir=None, **kw):
                captured["base"] = list(gated_base)
                captured["composite"] = [x["name"] for x in gated_composite_defs]
                captured["industry"] = [x["name"] for x in gated_industry_defs]
                captured["horizon"] = horizon
                return types.SimpleNamespace(max_label_realization_date=pd.Timestamp("2020-12-01"))

            with patch.object(fls, "load_is_windowed_panel_with_layer2", spy):
                result = fls.handle_factor_lifecycle_dataset_build(ctx)

            self.assertEqual(set(captured["base"]), {"mom_return_5d", "val_bp"})
            self.assertEqual(captured["composite"], ["comp_small_value"])
            self.assertEqual(captured["industry"], ["val_bp_industry_rel"])
            self.assertNotIn("qual_roe", captured["base"])     # field-ineligible never computed
            self.assertEqual(captured["horizon"], 20)
            self.assertEqual(result.outputs["field_ineligible_factors"], ["qual_roe"])
            self.assertEqual(set(result.outputs["gated_base_factors"]), {"mom_return_5d", "val_bp"})
            self.assertEqual(result.outputs["gated_composite_factors"], ["comp_small_value"])
            self.assertEqual(result.outputs["gated_industry_relative_factors"], ["val_bp_industry_rel"])
            self.assertIn("panel", ctx.state["factor_lifecycle"])

    def test_dataset_build_raises_on_unknown_factor(self):
        import types
        from unittest.mock import patch
        import pandas as pd
        from src.research_orchestrator import factor_lifecycle_steps as fls
        with self._temp() as d:
            ctx = self._context(Path(d))
            ctx.state["step_outputs"] = {
                "factor_lifecycle_object_resolver": {
                    "field_eligible": {"mom_return_5d": True, "not_a_real_factor": True},
                }
            }
            def spy(**kw):
                return types.SimpleNamespace(max_label_realization_date=pd.Timestamp("2020-12-01"))
            with patch.object(fls, "load_is_windowed_panel_with_layer2", spy):
                with self.assertRaises(ValueError):
                    fls.handle_factor_lifecycle_dataset_build(ctx)

    def test_dataset_build_raises_if_no_eligible_base(self):
        from src.research_orchestrator import factor_lifecycle_steps as fls
        with self._temp() as d:
            ctx = self._context(Path(d))
            ctx.state["step_outputs"] = {
                "factor_lifecycle_object_resolver": {"field_eligible": {"mom_return_5d": False}}
            }
            with self.assertRaises(ValueError):
                fls.handle_factor_lifecycle_dataset_build(ctx)


class FactorLifecycleWalkForwardTests(unittest.TestCase):
    def _temp(self):
        WORKSPACE_OUTPUTS.mkdir(parents=True, exist_ok=True)
        return tempfile.TemporaryDirectory(prefix="p5_wf_", dir=WORKSPACE_OUTPUTS)

    def _panel(self):
        import numpy as np
        import pandas as pd
        from src.alpha_research.factor_lifecycle.walk_forward_validation import build_is_windowed_panel
        cal = pd.DatetimeIndex(pd.date_range("2014-01-03", "2020-12-25", freq="W-FRI"))
        insts = [f"{i:06d}_SZ" for i in range(60)]
        idx = pd.MultiIndex.from_product([insts, cal], names=["instrument", "datetime"])
        rng = np.random.default_rng(5)
        adj = pd.Series(10 * np.exp((rng.standard_normal(len(idx)) * 0.02).cumsum() % 3), index=idx).sort_index()
        panel = pd.DataFrame(
            {"mom_return_5d": rng.standard_normal(len(idx)), "val_bp": rng.standard_normal(len(idx))},
            index=idx,
        ).sort_index()
        return build_is_windowed_panel(panel, adj, is_end="2020-12-31", horizon=4, trade_cal=cal)

    def _context(self, root: Path):
        ts = {"is_start": "2014-01-01", "is_end": "2020-12-31", "oos_start": "2021-01-01", "oos_end": "2022-01-01"}
        request = ResearchRequest(
            profile_id="factor_lifecycle", mode="formal",
            inputs={"output_dir": str(root), "time_split": ts, "horizon": 4, "factor_origin": "a_priori"},
        )
        profile = profile_registry().get("factor_lifecycle")
        dag = profile.dag_builder(request, list(profile.default_capabilities))
        step = next(s for s in dag.steps if s.handler == "factor_lifecycle_walk_forward")
        step_dir = root / "step"
        step_dir.mkdir(parents=True, exist_ok=True)
        (root / "testing_ledger").mkdir(parents=True, exist_ok=True)
        ctx = StepExecutionContext(
            request=request, profile=profile, dag=dag, step=step, run_dir=root, step_dir=step_dir,
            registry_dirs={"testing_ledger_dir": root / "testing_ledger"},
            effective_capabilities=[], effective_capability_metadata=[], state={},
        )
        ctx.state["factor_lifecycle"] = {"panel": self._panel(), "excluded_factors": ["some_excluded"]}
        return ctx

    def test_walk_forward_emits_verdicts_no_oos_and_records_ledger(self):
        with self._temp() as d:
            ctx = self._context(Path(d))
            result = handle_factor_lifecycle_walk_forward(ctx)
            self.assertEqual(result.status, "completed")
            verdicts = result.outputs["factor_verdicts"]
            self.assertEqual({v["factor"] for v in verdicts}, {"mom_return_5d", "val_bp"})
            self.assertTrue(all(v["status"] in ("candidate", "draft") for v in verdicts))
            # IS-only: no oos_* field anywhere in the verdict rows
            self.assertFalse(any(k.startswith("oos") for v in verdicts for k in v))
            self.assertEqual(result.outputs["evidence_kind"], "a_priori")
            # ledger: 2 per-factor measurements + 1 batch effective-trials = 3
            self.assertEqual(result.outputs["ledger"]["recorded"], 3)

    def test_unknown_factor_origin_raises_fail_closed(self):
        with self._temp() as d:
            ctx = self._context(Path(d))
            ctx.request.inputs["factor_origin"] = "generted"  # typo
            with self.assertRaises(ValueError):
                handle_factor_lifecycle_walk_forward(ctx)

    def test_missing_panel_raises(self):
        with self._temp() as d:
            ctx = self._context(Path(d))
            ctx.state["factor_lifecycle"]["panel"] = None
            with self.assertRaises(ValueError):
                handle_factor_lifecycle_walk_forward(ctx)


class FactorLifecycleGateMetricsTests(unittest.TestCase):
    def test_collect_measured_values_branch_is_nonempty_and_maps_rank_icir(self):
        # GPT slice-1 risk: an unknown profile returns {} so the gate has no rule table.
        # The factor_lifecycle branch must return non-empty metrics with rank_icir mapped
        # from the max |heldout ICIR| so the standard rank_icir criterion auto-fires.
        from src.research_orchestrator.steps import _collect_measured_values
        from src.research_orchestrator import ResearchRequest, profile_registry

        profile = profile_registry().get("factor_lifecycle")
        request = ResearchRequest(profile_id="factor_lifecycle", mode="formal", inputs={"output_dir": "x"})
        ctx = StepExecutionContext(
            request=request, profile=profile, dag=None, step=None, run_dir=Path("."),
            step_dir=Path("."), registry_dirs={}, effective_capabilities=[],
            effective_capability_metadata=[],
            state={"step_outputs": {"factor_lifecycle_walk_forward": {
                "candidate_count": 2, "tested_count": 5, "field_ineligible_count": 1,
                "factor_verdicts": [
                    {"factor": "a", "heldout_rank_icir": 0.15, "status": "candidate"},
                    {"factor": "b", "heldout_rank_icir": -0.05, "status": "draft"},
                    {"factor": "c", "heldout_rank_icir": None, "status": "draft"},
                ],
            }}},
        )
        mv = _collect_measured_values(ctx)
        self.assertTrue(mv)  # NOT {} (the empty-gate hole)
        self.assertAlmostEqual(mv["rank_icir"], 0.15)         # max |heldout ICIR| -> rank_icir
        self.assertEqual(mv["candidate_count"], 2)
        self.assertEqual(mv["tested_count"], 5)
        self.assertEqual(mv["effective_trials"], 6)           # tested 5 + field-ineligible 1


class FactorLifecyclePublishTests(unittest.TestCase):
    def _temp(self):
        WORKSPACE_OUTPUTS.mkdir(parents=True, exist_ok=True)
        return tempfile.TemporaryDirectory(prefix="p5_publish_", dir=WORKSPACE_OUTPUTS)

    def _ctx(self, root: Path, decision: str, candidates, drafts=()):
        registry_dirs = {
            "factor_registry_dir": root / "factor_registry",
            "candidate_registry_dir": root / "candidate_registry",
        }
        registry_dirs["factor_registry_dir"].mkdir(parents=True, exist_ok=True)
        if not (registry_dirs["factor_registry_dir"] / "factor_master.parquet").exists():
            store = FactorRegistryStore(registry_dirs["factor_registry_dir"])
            store.sync_catalog(record_run=False, generated_at="2026-04-04 21:00:00")
            store.save()
        request = ResearchRequest(profile_id="factor_lifecycle", mode="formal", inputs={"output_dir": str(root)})
        profile = profile_registry().get("factor_lifecycle")
        dag = profile.dag_builder(request, list(profile.default_capabilities))
        step = next(s for s in dag.steps if s.handler == "factor_lifecycle_registry_publish")
        step_dir = root / "step"
        step_dir.mkdir(parents=True, exist_ok=True)
        rows = [{"factor": f, "status": "candidate", "heldout_rank_icir": 0.15,
                 "sign_consistency": 0.8, "n_heldout_blocks": 3} for f in candidates]
        rows += [{"factor": f, "status": "draft", "heldout_rank_icir": 0.04,
                  "sign_consistency": 0.5, "n_heldout_blocks": 3} for f in drafts]
        state = {
            "factor_lifecycle": {"walk_forward_rows": rows, "evidence_kind": "a_priori"},
            "step_outputs": {"gate_review": {"decision": decision}},
        }
        return StepExecutionContext(
            request=request, profile=profile, dag=dag, step=step, run_dir=root, step_dir=step_dir,
            registry_dirs=registry_dirs, effective_capabilities=[], effective_capability_metadata=[], state=state,
        ), registry_dirs

    def _status_of(self, registry_dirs, factor_id):
        store = FactorRegistryStore(registry_dirs["factor_registry_dir"])
        cur = store.factor_master[store.factor_master["is_current"].fillna(False)]
        return str(cur[cur["factor_id"] == factor_id].iloc[0]["status"])

    def test_approved_promotes_candidates_writes_formal_evidence_never_approved(self):
        with self._temp() as d:
            ctx, rd = self._ctx(Path(d), "approved", ["mom_return_5d", "val_bp"], drafts=["qual_roe"])
            result = handle_factor_lifecycle_registry_publish(ctx)
            self.assertEqual(set(result.outputs["promoted_to_candidate"]), {"mom_return_5d", "val_bp"})
            self.assertEqual(self._status_of(rd, "mom_return_5d"), "candidate")
            self.assertEqual(self._status_of(rd, "qual_roe"), "draft")  # draft verdict NOT promoted
            store = FactorRegistryStore(rd["factor_registry_dir"])
            cur = store.factor_master[store.factor_master["is_current"].fillna(False)]
            self.assertNotIn("approved", set(cur["status"]))  # NEVER approved from this handler
            ev = store.factor_evidence[
                (store.factor_evidence["factor_id"] == "mom_return_5d")
                & (store.factor_evidence["run_type"] == "factor_lifecycle")
            ]
            self.assertEqual(len(ev), 1)
            self.assertTrue(bool(ev.iloc[0]["formal_evidence_eligible"]))  # FORMAL evidence
            self.assertTrue(pd.isna(ev.iloc[0]["oos_rank_icir"]))          # IS-only, no oos
            self.assertTrue(str(ev.iloc[0]["source_hash"]))                # definition-bound
            self.assertEqual(int(ev.iloc[0]["selected_fold_count"]), 3)    # n_heldout_blocks mapped
            # produced_objects for lineage (GPT PR-#34), recorded at status candidate
            po = result.outputs["produced_objects"]
            self.assertEqual({o["object_id"] for o in po}, {"mom_return_5d", "val_bp"})
            self.assertTrue(all(o["status"] == "candidate" and o["registry"] == "factor_registry" for o in po))

    def test_publish_reads_verdicts_from_persisted_step_outputs_on_resume(self):
        # RESUME-SAFETY regression (real orchestrator run, 2026-06-01): the gate pauses
        # (gate_concern_scoring/gate_review) split the run across processes, and
        # reconstruct_state_from_completed_steps restores ONLY step_outputs on resume — the
        # in-memory context.state["factor_lifecycle"] dict (walk_forward_rows) does NOT
        # survive. Publish must read the verdicts from the PERSISTED walk_forward
        # step_outputs. Pre-fix (in-memory only) -> promotes NOTHING on a resumed run.
        with self._temp() as d:
            ctx, rd = self._ctx(Path(d), "approved", ["mom_return_5d", "val_bp"], drafts=["qual_roe"])
            # simulate resume: the in-memory factor_lifecycle dict is GONE; verdicts live
            # only in the restored walk_forward step_outputs.
            verdicts = list(ctx.state["factor_lifecycle"]["walk_forward_rows"])
            ev_kind = ctx.state["factor_lifecycle"]["evidence_kind"]
            ctx.state.pop("factor_lifecycle")
            ctx.state["step_outputs"]["factor_lifecycle_walk_forward"] = {
                "factor_verdicts": verdicts, "evidence_kind": ev_kind,
            }
            result = handle_factor_lifecycle_registry_publish(ctx)
            self.assertEqual(set(result.outputs["promoted_to_candidate"]), {"mom_return_5d", "val_bp"})
            self.assertEqual(self._status_of(rd, "mom_return_5d"), "candidate")
            self.assertEqual(self._status_of(rd, "qual_roe"), "draft")  # draft verdict NOT promoted

    def test_evidence_skips_drifted_factor_fail_closed(self):
        # GPT PR-#34: record_lifecycle_evidence is itself a formal-evidence writer and must
        # independently fail-closed on definition drift (not rely on the resolver's P1.3).
        with self._temp() as d:
            ctx, rd = self._ctx(Path(d), "approved", ["mom_return_5d"])
            store = FactorRegistryStore(rd["factor_registry_dir"])
            idx = store.factor_master.index[
                (store.factor_master["factor_id"] == "mom_return_5d")
                & (store.factor_master["is_current"].fillna(False))
            ][0]
            store.factor_master.at[idx, "definition_hash"] = "dead" * 16  # drift vs catalog
            store.save()
            result = handle_factor_lifecycle_registry_publish(ctx)
            self.assertEqual(result.outputs["promoted_to_candidate"], [])   # drift -> not promoted
            self.assertIn("mom_return_5d", result.outputs["skipped_drift"])
            self.assertEqual(self._status_of(rd, "mom_return_5d"), "draft")  # status unchanged

    def test_non_approved_decisions_write_nothing(self):
        for decision in ("rejected", "quarantined", ""):
            with self._temp() as d:
                ctx, rd = self._ctx(Path(d), decision, ["mom_return_5d"])
                result = handle_factor_lifecycle_registry_publish(ctx)
                self.assertEqual(result.outputs["published"], 0)
                self.assertEqual(self._status_of(rd, "mom_return_5d"), "draft")  # unchanged

    def test_evidence_idempotent_on_reapprove(self):
        with self._temp() as d:
            root = Path(d)
            ctx1, rd = self._ctx(root, "approved", ["mom_return_5d"])
            handle_factor_lifecycle_registry_publish(ctx1)
            ctx2, _ = self._ctx(root, "approved", ["mom_return_5d"])  # same root -> same run_id
            handle_factor_lifecycle_registry_publish(ctx2)
            store = FactorRegistryStore(rd["factor_registry_dir"])
            ev = store.factor_evidence[
                (store.factor_evidence["factor_id"] == "mom_return_5d")
                & (store.factor_evidence["run_type"] == "factor_lifecycle")
            ]
            self.assertEqual(len(ev), 1)  # idempotent by (run_id, factor_id, version)


if __name__ == "__main__":
    unittest.main()
