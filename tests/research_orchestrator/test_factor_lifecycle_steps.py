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
                 "sign_consistency": 0.8, "n_heldout_blocks": 3,
                 "expected_direction": "positive"} for f in candidates]
        rows += [{"factor": f, "status": "draft", "heldout_rank_icir": 0.04,
                  "sign_consistency": 0.5, "n_heldout_blocks": 3,
                  "expected_direction": "positive"} for f in drafts]
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

    def test_publish_persists_expected_direction_metadata(self):
        # GPT Phase-7 impl-review must-fix: on promotion, factor_master.expected_direction MUST
        # be populated (the future FrozenSelectionSet hash consumes it). Metadata-only: status
        # stays candidate; an INVERSE-ICIR factor records "inverse" (not implied long-only-positive).
        with self._temp() as d:
            ctx, rd = self._ctx(Path(d), "approved", ["mom_return_5d"])
            ctx.state["factor_lifecycle"]["walk_forward_rows"][0]["heldout_rank_icir"] = -0.25
            ctx.state["factor_lifecycle"]["walk_forward_rows"][0]["expected_direction"] = "inverse"
            handle_factor_lifecycle_registry_publish(ctx)
            store = FactorRegistryStore(rd["factor_registry_dir"])
            cur = store.factor_master[store.factor_master["is_current"].fillna(False)]
            row = cur[cur["factor_id"] == "mom_return_5d"].iloc[0]
            self.assertEqual(str(row["expected_direction"]), "inverse")  # durable direction persisted
            self.assertEqual(str(row["status"]), "candidate")            # metadata-only: status unchanged

    def test_set_expected_direction_enum_validated_fail_closed(self):
        # GPT Phase-7 re-confirm note: the setter enum-validates (only positive/inverse/
        # undetermined); a stray value fails closed, blank is a no-op.
        with self._temp() as d:
            _, rd = self._ctx(Path(d), "approved", ["mom_return_5d"])
            store = FactorRegistryStore(rd["factor_registry_dir"])
            with self.assertRaises(ValueError):
                store.set_expected_direction(factor_id="mom_return_5d", expected_direction="bogus")
            store.set_expected_direction(factor_id="mom_return_5d", expected_direction="")  # no-op, no raise
            for ed in ("positive", "inverse", "undetermined"):
                store.set_expected_direction(factor_id="mom_return_5d", expected_direction=ed)

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

    def _synth_manifest(self, rows):
        from src.alpha_research.factor_registry.replication_governance import (
            CohortFactorRow, CohortManifest,
        )
        return CohortManifest(
            source_cohort_id="cicc_test_cohort", handbook_label_window_end="2022-12-31",
            denominators={"source": 3, "daily_replicability": 2, "formalization_candidate": 2},
            factor_rows=[CohortFactorRow(**r) for r in rows])

    def test_pgate_refuses_cohort_below_candidate_and_failclosed(self):
        # P-GATE/F3 (GPT-hardened): cohort factors below candidate are REFUSED. With no matrix
        # evidence + no claim in this temp registry, even an exact_certified row caps at
        # evidence_only (F8 availability_audit_missing / F6 missing_domain_claim) — absence is a
        # cap, never a silent pass. A not_replicable row is blocked. The NON-cohort factor promotes.
        from unittest.mock import patch
        from src.research_orchestrator import factor_lifecycle_steps as fls
        with self._temp() as d:
            ctx, rd = self._ctx(Path(d), "approved", ["mom_return_5d", "val_bp", "qual_roe"])
            synth = self._synth_manifest([
                dict(factor_name_original="X", catalog_factor_id="mom_return_5d",
                     replication_tier_planned="not_replicable", oos_eligibility="pending"),
                dict(factor_name_original="Y", catalog_factor_id="val_bp",
                     replication_tier_planned="exact_certified", oos_eligibility="pending"),
            ])
            with patch.object(fls, "_load_cohort_manifests", lambda: [synth]):
                result = handle_factor_lifecycle_registry_publish(ctx)
            # both cohort factors refused (different reasons); only the non-cohort promotes
            self.assertEqual(result.outputs["promoted_to_candidate"], ["qual_roe"])
            self.assertEqual(self._status_of(rd, "mom_return_5d"), "draft")
            self.assertEqual(self._status_of(rd, "val_bp"), "draft")
            gov = {g["factor"]: g for g in result.outputs["replication_governance"]}
            self.assertEqual(gov["mom_return_5d"]["status_ceiling"], "blocked")
            self.assertEqual(gov["val_bp"]["status_ceiling"], "evidence_only")  # F8: missing matrix evidence
            self.assertIn("availability_audit_missing", gov["val_bp"]["blocking_reasons"])
            self.assertFalse(gov["val_bp"]["promoted"])
            # GPT R2 Finding-4 output split: val_bp lacks the matrix prerequisite; mom_return_5d
            # is a true governance cap (not_replicable -> blocked).
            self.assertIn("val_bp", result.outputs["refused_by_missing_prerequisite"])
            self.assertIn("mom_return_5d", result.outputs["refused_by_true_governance_cap"])
            self.assertNotIn("val_bp", result.outputs["refused_by_true_governance_cap"])

    def test_pgate_promotes_cohort_at_candidate_ceiling(self):
        # routing: when _cohort_ceiling yields candidate_ceiling, the cohort factor promotes
        # AND a governance record is persisted (the resolver composition itself is unit-tested
        # in test_replication_governance).
        from unittest.mock import patch
        from src.research_orchestrator import factor_lifecycle_steps as fls
        from src.alpha_research.factor_registry.replication_governance import ReplicationCeilingDecision
        dec = ReplicationCeilingDecision(
            status_ceiling="candidate_ceiling", blocking_reasons=("short_oos_power_floor_fail",),
            nonblocking_missing_certs=(), next_actions=(),
            active_cap_reasons=("short_oos_power_floor_fail",),
            oos_eligible_gates_met=("denominator_frozen", "coverage_pass"))
        row = self._synth_manifest([dict(factor_name_original="Y", catalog_factor_id="val_bp",
                                         replication_tier_planned="exact_certified")]).factor_rows[0]
        fake = {"decision": dec, "cohort_id": "cicc_test_cohort", "row": row, "claim_id": "",
                "oos_quarantine_start": "2023-02-01"}
        with self._temp() as d:
            ctx, rd = self._ctx(Path(d), "approved", ["val_bp", "qual_roe"])
            with patch.object(fls, "_load_cohort_manifests", lambda: [object()]), \
                 patch.object(fls, "_cohort_ceiling",
                              lambda fid, u, **kw: fake if fid == "val_bp" else None):
                result = handle_factor_lifecycle_registry_publish(ctx)
            self.assertIn("val_bp", result.outputs["promoted_to_candidate"])      # candidate_ceiling promotes
            self.assertEqual(self._status_of(rd, "val_bp"), "candidate")
            gov = {g["factor"]: g for g in result.outputs["replication_governance"]}
            self.assertEqual(gov["val_bp"]["status_ceiling"], "candidate_ceiling")
            self.assertTrue(gov["val_bp"]["promoted"])

    def test_pgate_failclosed_on_adjudication_error(self):
        # GPT F1: an exception from _cohort_ceiling means a COHORT factor whose adjudication
        # failed → REFUSE it (fail-closed), never fall back to non-cohort promotion.
        from unittest.mock import patch
        from src.research_orchestrator import factor_lifecycle_steps as fls

        def boom(fid, u, **kw):
            if fid == "val_bp":
                raise RuntimeError("synthetic adjudication failure")
            return None
        with self._temp() as d:
            ctx, rd = self._ctx(Path(d), "approved", ["val_bp", "qual_roe"])
            with patch.object(fls, "_load_cohort_manifests", lambda: [object()]), \
                 patch.object(fls, "_cohort_ceiling", boom):
                result = handle_factor_lifecycle_registry_publish(ctx)
            self.assertNotIn("val_bp", result.outputs["promoted_to_candidate"])   # refused, not fail-open
            self.assertEqual(self._status_of(rd, "val_bp"), "draft")
            self.assertIn("val_bp", result.outputs["refused_by_adjudication_error"])
            self.assertIn("qual_roe", result.outputs["promoted_to_candidate"])    # non-cohort unaffected

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


class CohortCeilingUnitTests(unittest.TestCase):
    """Unit tests for `_cohort_ceiling` — the GPT R2 cheap-hardening behaviors."""

    def _mani(self, rows, handbook="2022-12-31"):
        from src.alpha_research.factor_registry.replication_governance import (
            CohortFactorRow, CohortManifest,
        )
        return CohortManifest(
            source_cohort_id="c", handbook_label_window_end=handbook,
            denominators={"source": 2, "daily_replicability": 2, "formalization_candidate": 1},
            factor_rows=[CohortFactorRow(**r) for r in rows])

    def _claims(self, rows):
        import types
        import pandas as pd
        cols = ["factor_id", "universe_id", "status", "claim_class", "claim_id"]
        return types.SimpleNamespace(claims=lambda: pd.DataFrame(rows, columns=cols))

    def _ev(self, rows):
        import pandas as pd
        cols = ["factor_id", "run_type", "universe_id", "evidence_time",
                "coverage_tier", "unified_metrics_json", "source_hash"]
        return pd.DataFrame(rows, columns=cols)

    def test_stale_matrix_evidence_does_not_satisfy_coverage(self):
        # GPT R2 Cond-1b: matrix evidence counts only when source_hash == current definition_hash.
        from src.research_orchestrator import factor_lifecycle_steps as fls
        m = self._mani([dict(factor_name_original="P", catalog_factor_id="comp_x",
                             replication_tier_planned="exact_certified",
                             truth_table_label_end="2022-12-31")])
        claims = self._claims([dict(factor_id="comp_x", universe_id="univ_all", status="draft_claim",
                                    claim_class="clean_singleton_primary", claim_id="cl1")])
        ev = self._ev([dict(factor_id="comp_x", run_type="factor_lifecycle_auto", universe_id="univ_all",
                            evidence_time="2026-06-13", coverage_tier="full",
                            unified_metrics_json='{"effective_ic_days": 2654}', source_hash="HASH_OLD")])
        fresh = fls._cohort_ceiling("comp_x", "univ_all", manifests=[m], evidence_df=ev,
                                    claim_store=claims, current_definition_hash="HASH_OLD")
        self.assertEqual(fresh["decision"].status_ceiling, "candidate_ceiling")  # fresh coverage
        stale = fls._cohort_ceiling("comp_x", "univ_all", manifests=[m], evidence_df=ev,
                                    claim_store=claims, current_definition_hash="HASH_NEW")
        self.assertEqual(stale["decision"].status_ceiling, "evidence_only")       # stale -> ignored
        self.assertIn("availability_audit_missing", stale["decision"].blocking_reasons)

    def test_multiple_active_claims_fail_closed(self):
        # GPT R2 Cond-2: >1 active claim for the universe is ambiguous -> fail closed.
        from src.research_orchestrator import factor_lifecycle_steps as fls
        m = self._mani([dict(factor_name_original="P", catalog_factor_id="comp_x",
                             replication_tier_planned="exact_certified")])
        claims = self._claims([
            dict(factor_id="comp_x", universe_id="univ_all", status="draft_claim",
                 claim_class="clean_singleton_primary", claim_id="cl1"),
            dict(factor_id="comp_x", universe_id="univ_all", status="candidate_claim",
                 claim_class="tainted_post_hoc_max_stat", claim_id="cl2"),
        ])
        with self.assertRaises(ValueError):
            fls._cohort_ceiling("comp_x", "univ_all", manifests=[m], evidence_df=self._ev([]),
                                claim_store=claims, current_definition_hash="H")

    def test_composite_inherits_component_truth_observation(self):
        # GPT R2 Cond-4 (F5-lite): comp_cicc_profit's own row omits truth + handbook is blank,
        # but a component (qual_cfoa_ttm) is truth-observed -> the composite inherits it -> the
        # short-OOS cap fires (composite cannot reach eligible_for_oos despite observed members).
        from src.research_orchestrator import factor_lifecycle_steps as fls
        m = self._mani([
            dict(factor_name_original="Profit", catalog_factor_id="comp_cicc_profit",
                 replication_tier_planned="formula_equivalent_pending"),
            dict(factor_name_original="CFOA", catalog_factor_id="qual_cfoa_ttm",
                 replication_tier_planned="exact_certified", truth_table_label_end="2022-12-31"),
        ], handbook="")  # blank handbook so the composite's OWN row is not truth-observed
        claims = self._claims([dict(factor_id="comp_cicc_profit", universe_id="univ_all",
                                    status="draft_claim", claim_class="clean_singleton_primary", claim_id="cl1")])
        ev = self._ev([dict(factor_id="comp_cicc_profit", run_type="factor_lifecycle_auto",
                            universe_id="univ_all", evidence_time="2026-06-13", coverage_tier="full",
                            unified_metrics_json='{"effective_ic_days": 2654}', source_hash="H")])
        d = fls._cohort_ceiling("comp_cicc_profit", "univ_all", manifests=[m], evidence_df=ev,
                                claim_store=claims, current_definition_hash="H")
        self.assertIn("short_oos_power_floor_fail", d["decision"].active_cap_reasons)
        self.assertEqual(d["decision"].status_ceiling, "candidate_ceiling")

    def test_f3_linked_factor_zero_manifest_match_fails_closed(self):
        # R1 F3: a factor carrying a cohort link but resolving to 0 manifest rows is a dropped/
        # forgotten link → fail closed; an UNLINKED factor with 0 matches is genuinely non-cohort.
        from src.research_orchestrator import factor_lifecycle_steps as fls
        m = self._mani([dict(factor_name_original="P", catalog_factor_id="other_factor",
                             replication_tier_planned="exact_certified")])
        claims = self._claims([])
        self.assertIsNone(fls._cohort_ceiling(
            "ghost", "univ_all", manifests=[m], evidence_df=self._ev([]), claim_store=claims,
            current_definition_hash="H", is_cohort_linked=False))            # non-cohort → unchanged
        with self.assertRaises(ValueError):                                  # linked + 0 match → closed
            fls._cohort_ceiling("ghost", "univ_all", manifests=[m], evidence_df=self._ev([]),
                                claim_store=claims, current_definition_hash="H", is_cohort_linked=True)

    def test_f9_full_adjudicates_non_univ_all_domain(self):
        # R1 F9-full: a non-univ_all universe is now ADJUDICATED (no longer a hard refuse). With a
        # matching csi300 claim but no csi300 matrix evidence → evidence_only (coverage missing),
        # using the csi300 claim (not missing_domain_claim).
        from src.research_orchestrator import factor_lifecycle_steps as fls
        m = self._mani([dict(factor_name_original="ROED", catalog_factor_id="qual_roed",
                             replication_tier_planned="proxy_approx",
                             truth_table_label_end="2022-12-31")])  # primary defaults to univ_all
        claims = self._claims([dict(factor_id="qual_roed", universe_id="csi300", status="draft_claim",
                                    claim_class="clean_singleton_primary", claim_id="cl_csi300")])
        info = fls._cohort_ceiling("qual_roed", "csi300", manifests=[m], evidence_df=self._ev([]),
                                   claim_store=claims, current_definition_hash="H")
        self.assertIsNotNone(info)                                           # adjudicated, did NOT raise
        self.assertEqual(info["claim_id"], "cl_csi300")                      # used the csi300 claim
        self.assertNotIn("missing_domain_claim", info["decision"].active_cap_reasons)
        self.assertIn("availability_audit_missing", info["decision"].active_cap_reasons)

    def test_f11_definition_drift_fails_closed(self):
        # GPT scale-review #3: an active linkage bound at definition_hash H1, but the factor's
        # current definition_hash is H2 → stale linkage (definition drifted) → fail closed.
        from src.research_orchestrator import factor_lifecycle_steps as fls
        m = self._mani([dict(factor_name_original="P", catalog_factor_id="comp_x",
                             replication_tier_planned="exact_certified",
                             truth_table_label_end="2022-12-31")])
        claims = self._claims([dict(factor_id="comp_x", universe_id="univ_all", status="draft_claim",
                                    claim_class="clean_singleton_primary", claim_id="cl1")])
        with self.assertRaises(ValueError):
            fls._cohort_ceiling("comp_x", "univ_all", manifests=[m], evidence_df=self._ev([]),
                                claim_store=claims, current_definition_hash="H2",
                                linked_definition_hash="H1")                 # drift → raise
        info = fls._cohort_ceiling("comp_x", "univ_all", manifests=[m], evidence_df=self._ev([]),
                                   claim_store=claims, current_definition_hash="H1",
                                   linked_definition_hash="H1")               # same hash → no drift
        self.assertIsNotNone(info)


if __name__ == "__main__":
    unittest.main()
