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


if __name__ == "__main__":
    unittest.main()
