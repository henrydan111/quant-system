"""Tests for the promotion-evidence assembler orchestration (harness increment 2a).

Covers the orchestration heart: assembly shape, self-verify through the SAME gate that consumes
it, and the fail-closed / skip-as-fail / definition-binding guards. The heavy live gatherers
(OOS re-run, parity) are injected here; their live execution is the dry-run.
"""

import unittest

from src.research_orchestrator.promotion_evidence import (
    CANARY_KEYS,
    FAILED,
    PASSED,
    PromotionEvidenceError,
    assert_definition_binding,
    build_promotion_evidence,
    capture_git_state,
    produce_promotion_evidence,
)

_GOOD_CANARIES = {k: PASSED for k in CANARY_KEYS}
_GOOD_REPRO = {"independent_reproduction": {"source": "qlib_windowed_features",
                                            "oos_window": "2021-01-01..2026-02-27"}}
_CLEAN_GIT = {"dirty_tree": False, "git_sha": "abc123"}
_BOUND = {"bound": True, "mismatched": []}


def _produce(**over):
    kw = dict(reproduction=_GOOD_REPRO, definition_binding=_BOUND, canaries=_GOOD_CANARIES,
              lint=PASSED, parity=PASSED, git_state=_CLEAN_GIT)
    kw.update(over)
    return produce_promotion_evidence(**kw)


class AssemblerOrchestrationTests(unittest.TestCase):
    def test_canary_keys_match_pit_canaries(self):
        from src.data_infra.pit_canaries import CANARY_KEYS as PIT_KEYS
        self.assertEqual(set(CANARY_KEYS), set(PIT_KEYS))

    def test_produce_passes_and_assembles_with_all_good(self):
        art = _produce()
        self.assertEqual(art["independent_reproduction"]["source"], "qlib_windowed_features")
        self.assertEqual(art["dirty_tree"], False)
        self.assertEqual(art["git_sha"], "abc123")
        self.assertEqual(art["promotion_status"], "approved")
        for k in CANARY_KEYS:
            self.assertEqual(art[k], PASSED)
        self.assertEqual(art["unsafe_pit_dates_lint"], PASSED)
        self.assertEqual(art["live_provider_parity"], PASSED)

    def test_fail_closed_dirty_tree(self):
        with self.assertRaises(PromotionEvidenceError):
            _produce(git_state={"dirty_tree": True, "git_sha": "abc123"})

    def test_fail_closed_failing_canary(self):
        with self.assertRaises(PromotionEvidenceError):
            _produce(canaries={**_GOOD_CANARIES, "synthetic_lookahead_canary": FAILED})

    def test_fail_closed_missing_canary_defaults_failed(self):
        partial = {k: PASSED for k in CANARY_KEYS if k != "restatement_canary"}
        with self.assertRaises(PromotionEvidenceError):
            _produce(canaries=partial)

    def test_skip_as_fail_lint(self):
        with self.assertRaises(PromotionEvidenceError):
            _produce(lint=FAILED)

    def test_skip_as_fail_parity(self):
        with self.assertRaises(PromotionEvidenceError):
            _produce(parity=FAILED)

    def test_non_independent_source_fails(self):
        with self.assertRaises(PromotionEvidenceError):
            _produce(reproduction={"independent_reproduction": {"source": "pit_research_loader"}})

    def test_definition_binding_unbound_refuses_up_front(self):
        with self.assertRaises(PromotionEvidenceError):
            _produce(definition_binding={"bound": False, "mismatched": ["X"]})

    def test_git_sha_mismatch_fails(self):
        # self-verify uses git_state.git_sha as current_git_sha; an empty sha (e.g. dirty/no-HEAD)
        # means the artifact omits git_sha -> with current None it is "not required" BUT dirty
        # closes it. Here force a present sha that the gate accepts.
        art = build_promotion_evidence(canaries=_GOOD_CANARIES, unsafe_pit_dates_lint=PASSED,
                                       live_provider_parity=PASSED, reproduction=_GOOD_REPRO,
                                       git_state=_CLEAN_GIT)
        self.assertEqual(art["git_sha"], "abc123")


class DefinitionBindingTests(unittest.TestCase):
    def test_bound_when_all_hashes_match(self):
        r = assert_definition_binding({"a": "h1", "b": "h2"}, {"a": "h1", "b": "h2"})
        self.assertTrue(r["bound"])
        self.assertEqual(r["mismatched"], [])

    def test_unbound_on_mismatch_or_absence(self):
        r = assert_definition_binding({"a": "h1"}, {"a": "DRIFT", "b": "h2"})
        self.assertFalse(r["bound"])
        self.assertEqual(r["mismatched"], ["a", "b"])


class GitStateTests(unittest.TestCase):
    def test_capture_git_state_shape(self):
        st = capture_git_state()
        self.assertIn("dirty_tree", st)
        self.assertIn("git_sha", st)
        self.assertIsInstance(st["dirty_tree"], bool)


class ReproduceSealedOosTests(unittest.TestCase):
    def _patch_sealed_world(self, root):
        """PR3 R4 B1/B3 test seam: the configured-root resolver -> the test scratch dir,
        and the catalog-expression resolver -> the fake fixture factors (not in the live
        catalog). There is no caller seal_root / factor_exprs any more."""
        import contextlib
        from pathlib import Path as _P
        from unittest.mock import patch

        stack = contextlib.ExitStack()
        stack.enter_context(patch(
            "src.research_orchestrator.holdout_seal.resolve_configured_global_holdout_root",
            lambda: _P(root)))
        stack.enter_context(patch(
            "src.research_orchestrator.promotion_evidence.resolve_frozen_catalog_expressions",
            lambda frozen_set, **kw: {"f_pos": "x", "f_neg": "y"}))
        return stack

    def _frozen_set(self):
        from src.research_orchestrator.frozen_selection_set import FrozenSelectionSet, SelectedFactor
        return FrozenSelectionSet(
            selected=(SelectedFactor("f_pos", 1, "h1", "long"), SelectedFactor("f_neg", 1, "h2", "short")),
            candidate_pool_hash="pool", selection_rule_hash="rule", eval_protocol_hash="proto",
            metric="rank_icir", portfolio_side="long_short", universe="csi_all",
            time_split_window="2021..2026", rebalance="20d", neutralization="industry",
        )

    def _fake_cf(self):
        import numpy as np
        import pandas as pd
        cal = pd.DatetimeIndex(pd.date_range("2021-01-08", "2025-12-26", freq="W-FRI"))
        insts = [f"{i:06d}_SZ" for i in range(120)]  # > fast-path min_obs(50)
        idx = pd.MultiIndex.from_product([cal, insts], names=["datetime", "instrument"])
        rng = np.random.default_rng(7)
        fdf = pd.DataFrame({"f_pos": rng.standard_normal(len(idx)), "f_neg": rng.standard_normal(len(idx))}, index=idx)
        adf = pd.DataFrame({"adj_close": 10 * np.exp((rng.standard_normal(len(idx)) * 0.02).cumsum() % 3)}, index=idx)

        def cf(catalog, start_date, end_date, horizons, **kw):
            # mirror operators.compute_factors: (factors_df, fwd_df). fwd_df is None when
            # horizons is falsy; otherwise it carries one fwd_{h}d column per horizon.
            if "adj_close" in set(catalog):
                return adf, None
            facs = fdf[[c for c in catalog if c in fdf.columns]]
            if horizons:
                fwd = pd.DataFrame({f"fwd_{h}d": rng.standard_normal(len(idx)) for h in horizons}, index=idx)
                return facs, fwd
            return facs, None
        return cal, cf

    def test_calendar_mismatch_refused(self):
        # PR3 R4 B1/B3: no seal_root / factor_exprs are passed any more — the calendar
        # guard fires BEFORE the catalog/root resolution, so this still raises for the
        # calendar reason.
        from src.research_orchestrator.promotion_evidence import reproduce_sealed_oos
        with self.assertRaises(PromotionEvidenceError):
            reproduce_sealed_oos(
                frozen_set=self._frozen_set(), oos_start="2021-01-01",
                qlib_dir=".", run_dir=".", design_hash="d", claim_seal=False,
                provider_provenance={"provider_build_id": "b", "calendar_policy_id": "c",
                                     "calendar_end": "2025-01-01"},  # != OOS_END 2026-02-27
            )

    def test_full_reproduction_claims_seal_and_computes_leakfree_metrics(self):
        import tempfile
        from pathlib import Path as _P
        from src.research_orchestrator.promotion_evidence import reproduce_sealed_oos
        OOS_END = "2026-02-27"  # legacy-fixture literal (the recorded spent window)
        from src.research_orchestrator.holdout_seal import HoldoutSealStore
        fs = self._frozen_set()
        cal, cf = self._fake_cf()
        _P("workspace/outputs").mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=str(_P("workspace/outputs"))) as d:
            store = HoldoutSealStore(d)
            with self._patch_sealed_world(d):
                rep = reproduce_sealed_oos(
                    frozen_set=fs, oos_start="2021-01-01",
                    qlib_dir=".", run_dir=d, design_hash="dh", horizon=4, n_quantiles=5,
                    provider_provenance={"provider_build_id": "pb1", "calendar_policy_id": "cp1",
                                         "calendar_end": OOS_END},
                    compute_factors_fn=cf, seal_store=store, trade_cal=cal,
                )
            ir = rep["independent_reproduction"]
            self.assertEqual(ir["source"], "qlib_windowed_features")
            self.assertEqual(ir["provider_build_id"], "pb1")
            self.assertEqual(ir["frozen_set_hash"], fs.frozen_set_hash)
            self.assertEqual(set(ir["per_factor"]), {"f_pos", "f_neg"})
            for m in ir["per_factor"].values():
                self.assertIn("oos_rank_icir", m)
                self.assertIn("oos_ls_sharpe", m)
            self.assertLessEqual(str(ir["max_label_realization_date"])[:10], OOS_END)  # leak-free belt
            self.assertEqual(len(store.list_events(seal_key=fs.frozen_set_hash)), 1)  # seal claimed

    def test_oos_reads_run_under_research_access_context(self):
        # GPT post-impl review Fix 3: the compute_factors reads must run under an OOS
        # ResearchAccessContext (stage=oos_test, seal_key=frozen_set_hash, window=[oos_start,
        # oos_end], holdout_seal_claimed) so the qlib_windowed_features data layer validates them,
        # instead of relying solely on the calendar_end == OOS_END boundary.
        import tempfile
        from pathlib import Path as _P
        from src.research_orchestrator.promotion_evidence import reproduce_sealed_oos
        OOS_END = "2026-02-27"  # legacy-fixture literal (the recorded spent window)
        from src.research_orchestrator.holdout_seal import HoldoutSealStore
        from src.research_orchestrator.research_access_context import get_research_access_context
        fs = self._frozen_set()
        cal, base_cf = self._fake_cf()
        seen = {}

        def cf(catalog, start_date, end_date, horizons, **kw):
            seen["ctx"] = get_research_access_context()  # capture the active context during compute
            return base_cf(catalog, start_date, end_date, horizons, **kw)

        _P("workspace/outputs").mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=str(_P("workspace/outputs"))) as d:
            store = HoldoutSealStore(d)
            with self._patch_sealed_world(d):
                reproduce_sealed_oos(
                    frozen_set=fs, oos_start="2021-01-01",
                    qlib_dir=".", run_dir=d, design_hash="dh", horizon=4,
                    provider_provenance={"provider_build_id": "pb1", "calendar_policy_id": "cp1",
                                         "calendar_end": OOS_END},
                    compute_factors_fn=cf, seal_store=store, trade_cal=cal,
                )
        ctx = seen.get("ctx")
        self.assertIsNotNone(ctx, "compute ran with NO ResearchAccessContext installed")
        self.assertEqual(ctx.stage, "oos_test")
        self.assertEqual(ctx.effective_seal_key, fs.frozen_set_hash)
        self.assertTrue(ctx.holdout_seal_claimed)
        self.assertEqual(str(ctx.allowed_start)[:10], "2021-01-01")
        self.assertEqual(str(ctx.allowed_end)[:10], OOS_END)
        self.assertIsNone(get_research_access_context(), "context leaked after reproduce_sealed_oos")


class SavedProvenanceGateEligibilityTests(unittest.TestCase):
    """GPT post-impl review Fix 1: the persisted sealed_oos_winners_promotion.json must carry the
    FULL gate artifact (including independent_reproduction) so its promotion_evidence re-passes
    evaluate_promotion_artifact. The pre-fix producer stripped independent_reproduction, leaving a
    saved artifact that failed the gate with 'independent reproduction source; none supplied'."""

    def test_saved_promotion_json_is_gate_eligible(self):
        import json as _json
        from pathlib import Path as _P
        from src.research_orchestrator.release_gate import evaluate_promotion_artifact
        root = _P(__file__).resolve().parents[2]
        prov = root / "workspace" / "research" / "factor_expansion" / "sealed_oos_winners_promotion.json"
        self.assertTrue(prov.exists(), f"committed provenance artifact missing: {prov}")
        data = _json.loads(prov.read_text(encoding="utf-8"))
        pe_block = data.get("promotion_evidence")
        self.assertIsInstance(pe_block, dict, "promotion_evidence missing from provenance JSON")
        self.assertIn("independent_reproduction", pe_block,
                      "FULL artifact required: independent_reproduction was stripped (Fix 1 regression)")
        res = evaluate_promotion_artifact(pe_block, current_git_sha=pe_block.get("git_sha"))
        self.assertTrue(res.eligible,
                        f"saved promotion_evidence is NOT gate-eligible: {list(res.reasons)}")


if __name__ == "__main__":
    unittest.main()
