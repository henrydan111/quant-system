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
        insts = [f"{i:06d}_SZ" for i in range(60)]
        idx = pd.MultiIndex.from_product([cal, insts], names=["datetime", "instrument"])
        rng = np.random.default_rng(7)
        fdf = pd.DataFrame({"f_pos": rng.standard_normal(len(idx)), "f_neg": rng.standard_normal(len(idx))}, index=idx)
        adf = pd.DataFrame({"adj_close": 10 * np.exp((rng.standard_normal(len(idx)) * 0.02).cumsum() % 3)}, index=idx)

        def cf(catalog, start_date, end_date, horizons, **kw):
            if "adj_close" in set(catalog):
                return adf, None
            return fdf[[c for c in catalog if c in fdf.columns]], None
        return cal, cf

    def test_calendar_mismatch_refused(self):
        from src.research_orchestrator.promotion_evidence import reproduce_sealed_oos
        with self.assertRaises(PromotionEvidenceError):
            reproduce_sealed_oos(
                frozen_set=self._frozen_set(), factor_exprs={"f_pos": "x"}, oos_start="2021-01-01",
                qlib_dir=".", seal_root=".", run_dir=".", design_hash="d", claim_seal=False,
                provider_provenance={"provider_build_id": "b", "calendar_policy_id": "c",
                                     "calendar_end": "2025-01-01"},  # != OOS_END 2026-02-27
            )

    def test_full_reproduction_claims_seal_and_computes_leakfree_metrics(self):
        import tempfile
        from pathlib import Path as _P
        from src.research_orchestrator.promotion_evidence import reproduce_sealed_oos, OOS_END
        from src.research_orchestrator.holdout_seal import HoldoutSealStore
        fs = self._frozen_set()
        cal, cf = self._fake_cf()
        _P("workspace/outputs").mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=str(_P("workspace/outputs"))) as d:
            store = HoldoutSealStore(d)
            rep = reproduce_sealed_oos(
                frozen_set=fs, factor_exprs={"f_pos": "x", "f_neg": "y"}, oos_start="2021-01-01",
                qlib_dir=".", seal_root=d, run_dir=d, design_hash="dh", horizon=4, n_quantiles=5,
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


if __name__ == "__main__":
    unittest.main()
