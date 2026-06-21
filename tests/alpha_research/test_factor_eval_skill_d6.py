"""D6 OOS-window multiplicity tests.

Covers: the seal-layer ledger (idempotent window-tagged spends, distinct counts, by-tier);
the report/approval-layer action thresholds (disclose -> acknowledge -> require); the
pending-self preview used by seal --mode show; and window isolation.
"""
from __future__ import annotations

from src.alpha_research.factor_eval_skill.multiplicity import (
    ACTION_ACKNOWLEDGE,
    ACTION_DISCLOSE,
    ACTION_REQUIRE,
    oos_window_multiplicity,
)
from src.alpha_research.factor_eval_skill.stores import OosWindowLedgerStore

W = "2021-01-01..2026-02-27"


def test_ledger_idempotent_distinct_and_tiers(tmp_path):
    led = OosWindowLedgerStore(tmp_path)
    led.record_spend(oos_window_id=W, frozen_set_hash="h1", evidence_tier="a_priori_is_informed", factor_ids=["a"])
    led.record_spend(oos_window_id=W, frozen_set_hash="h1", evidence_tier="a_priori_is_informed")  # idempotent
    led.record_spend(oos_window_id=W, frozen_set_hash="h2", evidence_tier="theory_a_priori")
    assert led.distinct_frozen_sets(W) == ["h1", "h2"]
    assert len(led.list_all()) == 2  # h1 recorded once
    assert led.tier_counts(W) == {"a_priori_is_informed": 1, "theory_a_priori": 1}


def test_multiplicity_action_thresholds(tmp_path):
    led = OosWindowLedgerStore(tmp_path)
    for i in range(4):
        led.record_spend(oos_window_id=W, frozen_set_hash=f"h{i}")
    r = oos_window_multiplicity(led, W, warn_threshold=5, hard_threshold=10)
    assert r.n_spent == 4 and r.action == ACTION_DISCLOSE
    for i in range(4, 7):
        led.record_spend(oos_window_id=W, frozen_set_hash=f"h{i}")
    r = oos_window_multiplicity(led, W, warn_threshold=5, hard_threshold=10)
    assert r.n_spent == 7 and r.action == ACTION_ACKNOWLEDGE
    for i in range(7, 12):
        led.record_spend(oos_window_id=W, frozen_set_hash=f"h{i}")
    r = oos_window_multiplicity(led, W, warn_threshold=5, hard_threshold=10)
    assert r.n_spent == 12 and r.action == ACTION_REQUIRE


def test_multiplicity_pending_self_preview(tmp_path):
    led = OosWindowLedgerStore(tmp_path)
    led.record_spend(oos_window_id=W, frozen_set_hash="h1")
    r = oos_window_multiplicity(led, W, pending_self=True)
    assert r.n_spent == 2  # 1 recorded + this pending spend
    assert "would be" in r.note


def test_multiplicity_window_isolation(tmp_path):
    led = OosWindowLedgerStore(tmp_path)
    led.record_spend(oos_window_id=W, frozen_set_hash="h1")
    led.record_spend(oos_window_id="2015-01-01..2020-12-31", frozen_set_hash="h2")
    assert oos_window_multiplicity(led, W).n_spent == 1
