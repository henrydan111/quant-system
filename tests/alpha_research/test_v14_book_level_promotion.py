"""v1.4 book-level-promotion amendment — pass-1 acceptance tests.

Covers the §5 matrix items implementable before PR3:
- test_book_seal_key_distinctness (round-2 N2): changes to construction, execution
  envelope, evaluation protocol, OOS window, or pass/fail bar each produce a DISTINCT
  ``book_seal_key``; two plans sharing a frozen set cannot share a key.
- test_book_multiplicity_budget (round-1 M3 / round-3 R3-M2): D6 counts distinct
  ``book_seal_key`` spends per window (``book_plan_hash`` grouping is disclosure-only);
  virgin-window warn-3 / hard-5 with refuse_without_override.
- ledger spend-unit semantics: two plans sharing a frozen set are TWO recorded spends;
  the legacy frozen-set path stays idempotent.

(The A3 writer-gate matrix lives in test_factor_registry.py; the A7 scope gate in
tests/research_orchestrator/test_pr9_validation_field_gate.py. The two component-
diagnostics context tests land with the PR3-stage helper per the amendment §5.)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.alpha_research.factor_eval_skill.identity import (
    BookSealIdentity,
    DeploymentFrozenPlan,
)
from src.alpha_research.factor_eval_skill.multiplicity import (
    ACTION_ACKNOWLEDGE,
    ACTION_DISCLOSE,
    ACTION_REFUSE,
    ACTION_REQUIRE,
    is_virgin_window,
    virgin_window_multiplicity,
)
from src.alpha_research.factor_eval_skill.stores import OosWindowLedgerStore


def _plan(**overrides) -> DeploymentFrozenPlan:
    base = dict(
        frozen_set_hash="fsh_1",
        envelope_hash="env_1",
        target_universe_declaration_hash="tud_1",
        deployment_universe="univ_liquid_top300",
        portfolio_side="long_only",
        construction={"score_to_weight": "topk_equal", "topk": 30},
        pre_declared_bar={"net_sharpe_min": 0.8, "mdd_max": -0.35},
    )
    base.update(overrides)
    return DeploymentFrozenPlan(**base)


def _identity(plan: DeploymentFrozenPlan, **overrides) -> BookSealIdentity:
    kwargs = dict(
        selected_set_hash="ssh_1",
        execution_envelope_hash="exec_profile_jq_daily",
        eval_protocol_hash="proto_1",
        oos_window_id="2026-03-01..2026-09-30",
    )
    kwargs.update(overrides)
    return BookSealIdentity.from_plan(plan, **kwargs)


class TestBookSealKeyDistinctness:
    def test_book_seal_key_distinctness(self):
        base = _identity(_plan())
        # Construction change flows through plan_hash.
        diff_construction = _identity(_plan(construction={"score_to_weight": "optimizer", "topk": 30}))
        # Bar change flows through plan_hash AND the explicit bar hash.
        diff_bar = _identity(_plan(pre_declared_bar={"net_sharpe_min": 1.0, "mdd_max": -0.30}))
        # Envelope / protocol / window changes are key material even with an
        # IDENTICAL plan (the round-2 N2 gap: plan_hash alone omits these).
        diff_envelope = _identity(_plan(), execution_envelope_hash="exec_profile_stress")
        diff_protocol = _identity(_plan(), eval_protocol_hash="proto_2")
        diff_window = _identity(_plan(), oos_window_id="2026-03-01..2026-12-31")

        keys = {
            "base": base.book_seal_key,
            "construction": diff_construction.book_seal_key,
            "bar": diff_bar.book_seal_key,
            "envelope": diff_envelope.book_seal_key,
            "protocol": diff_protocol.book_seal_key,
            "window": diff_window.book_seal_key,
        }
        assert len(set(keys.values())) == len(keys), f"colliding book_seal_keys: {keys}"

        # Two plans sharing a frozen set but differing in construction share
        # frozen_set_hash yet have distinct seal keys.
        assert base.frozen_set_hash == diff_construction.frozen_set_hash
        assert base.book_seal_key != diff_construction.book_seal_key

        # Determinism: same inputs -> same key.
        assert base.book_seal_key == _identity(_plan()).book_seal_key


class TestBookMultiplicityBudget:
    def _ledger(self, tmp_path: Path) -> OosWindowLedgerStore:
        return OosWindowLedgerStore(tmp_path / "skill_store")

    def test_two_plans_sharing_a_frozen_set_are_two_spends(self, tmp_path: Path):
        ledger = self._ledger(tmp_path)
        window = "2026-03-01..2026-09-30"
        a = _identity(_plan())
        b = _identity(_plan(construction={"score_to_weight": "optimizer", "topk": 30}))
        ledger.record_book_spend(oos_window_id=window, book_seal_key=a.book_seal_key,
                                 frozen_set_hash=a.frozen_set_hash)
        ledger.record_book_spend(oos_window_id=window, book_seal_key=b.book_seal_key,
                                 frozen_set_hash=b.frozen_set_hash)
        # Same frozen set, two seal keys -> TWO spend units (the old frozen-set
        # idempotency would have swallowed the second).
        assert len(ledger.distinct_spend_keys(window)) == 2
        # Book-spend idempotency is on (window, book_seal_key).
        ledger.record_book_spend(oos_window_id=window, book_seal_key=a.book_seal_key,
                                 frozen_set_hash=a.frozen_set_hash)
        assert len(ledger.distinct_spend_keys(window)) == 2

    def test_book_multiplicity_budget(self, tmp_path: Path):
        ledger = self._ledger(tmp_path)
        window = "2026-03-01..2026-09-30"

        # 0-2 spends: disclose. 3-4: acknowledge. >=5: refuse without override.
        report = virgin_window_multiplicity(ledger, window, pending_self=True)
        assert report.action == ACTION_DISCLOSE

        protocols = [f"proto_{i}" for i in range(5)]
        for i, proto in enumerate(protocols[:3]):
            ident = _identity(_plan(), eval_protocol_hash=proto)
            ledger.record_book_spend(oos_window_id=window, book_seal_key=ident.book_seal_key,
                                     frozen_set_hash=ident.frozen_set_hash)
        assert virgin_window_multiplicity(ledger, window).action == ACTION_ACKNOWLEDGE

        for proto in protocols[3:]:
            ident = _identity(_plan(), eval_protocol_hash=proto)
            ledger.record_book_spend(oos_window_id=window, book_seal_key=ident.book_seal_key,
                                     frozen_set_hash=ident.frozen_set_hash)
        report = virgin_window_multiplicity(ledger, window)
        assert report.n_spent == 5
        assert report.action == ACTION_REFUSE

        # A user-signed override recorded BEFORE the spend downgrades the refusal to
        # require_adjusted_or_override (the artifact must then report adjusted stats).
        report = virgin_window_multiplicity(ledger, window, override_recorded=True)
        assert report.action == ACTION_REQUIRE

    def test_a5_study_spends_count_against_the_budget(self, tmp_path: Path):
        ledger = self._ledger(tmp_path)
        window = "2026-03-01..2026-09-30"
        ledger.record_study_spend(oos_window_id=window, frozen_set_hash="study_fsh_1",
                                  override_id="fresh_window_override_001")
        ident = _identity(_plan())
        ledger.record_book_spend(oos_window_id=window, book_seal_key=ident.book_seal_key,
                                 frozen_set_hash=ident.frozen_set_hash)
        assert len(ledger.distinct_spend_keys(window)) == 2
        rows = ledger.list_all()
        assert set(rows["spend_unit_type"].dropna()) == {"a5_signal_replication_study", "book_seal"}

    def test_legacy_frozen_set_rows_still_count_and_stay_idempotent(self, tmp_path: Path):
        ledger = self._ledger(tmp_path)
        window = "2021-01-01..2026-02-27"
        ledger.record_spend(oos_window_id=window, frozen_set_hash="legacy_fsh")
        ledger.record_spend(oos_window_id=window, frozen_set_hash="legacy_fsh")
        assert ledger.distinct_spend_keys(window) == ["legacy_fsh"]


class TestVirginWindowDetection:
    def test_is_virgin_window(self):
        assert not is_virgin_window("2026-02-27")
        assert not is_virgin_window("2026-01-31")
        assert is_virgin_window("2026-02-28")
        assert is_virgin_window("2026-09-30")


class TestBookSealKeyRefusesBlankKey:
    def test_record_book_spend_requires_key(self, tmp_path: Path):
        ledger = OosWindowLedgerStore(tmp_path / "skill_store")
        with pytest.raises(ValueError, match=r"book_seal_key"):
            ledger.record_book_spend(oos_window_id="w", book_seal_key="  ",
                                     frozen_set_hash="fsh")
