"""D3 extraction tests for marginal / sealed_oos / deployment.

Two layers per module: (1) synthetic unit tests of the pure logic; (2) the E-wave
bitwise/tolerance REGRESSION — the design's acceptance bar — proving the extracted
library reproduces the recorded E-wave result (selected set + 6/6 OOS verdict).
The regressions skip-guard on the cached artifacts so they are robust elsewhere.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.alpha_research.factor_eval_skill.deployment import (
    build_ranked_schedule,
    direction_aligned_composite,
)
from src.alpha_research.factor_eval_skill.marginal import select_marginal
from src.alpha_research.factor_eval_skill.sealed_oos import (
    direction_aligned_pass,
    evaluate_sealed_oos_bar,
)

ROOT = Path(__file__).resolve().parents[2]
CORR_CACHE = ROOT / "workspace" / "outputs" / "e_wave_selection_v2" / "exposure_corr.parquet"
EWAVE_V2 = ROOT / "workspace" / "research" / "cicc_replication" / "EWaveSelectedSet_v2.json"
EWAVE_OOS = ROOT / "workspace" / "research" / "cicc_replication" / "e_wave_v2_sealed_oos.json"


# ============================ marginal ============================

def test_marginal_prunes_redundant_family_member():
    pool = {"A": "x", "B": "x", "C": "y"}
    metrics = {
        "A": {"heldout_rank_icir": 0.50, "sign_consistency": 0.9},
        "B": {"heldout_rank_icir": 0.40, "sign_consistency": 0.9},
        "C": {"heldout_rank_icir": 0.30, "sign_consistency": 0.9},
    }
    corr = pd.DataFrame(
        [[1.0, 0.9, 0.1], [0.9, 1.0, 0.1], [0.1, 0.1, 1.0]],
        index=["A", "B", "C"], columns=["A", "B", "C"],
    )
    sel = select_marginal(pool=pool, metrics=metrics, corr=corr, caps={"x": 2, "y": 1}, floor=0.10)
    # A seeds (max quality); C beats B (B is 0.9-redundant with A); B then falls below floor
    assert sel.factor_ids == ["A", "C"]


def test_marginal_respects_family_caps():
    pool = {"A": "x", "B": "x", "C": "y"}
    metrics = {k: {"heldout_rank_icir": v, "sign_consistency": 0.9}
               for k, v in (("A", 0.5), ("B", 0.45), ("C", 0.3))}
    corr = pd.DataFrame(np.eye(3) * 0 + np.diag([1, 1, 1]), index=list("ABC"), columns=list("ABC"))
    sel = select_marginal(pool=pool, metrics=metrics, corr=corr, caps={"x": 1, "y": 1}, floor=0.10)
    # x capped at 1 -> only A from family x; then C; B is cap-blocked
    assert sel.factor_ids == ["A", "C"]


def test_marginal_reference_provides_redundancy_basis():
    pool = {"A": "x", "B": "y"}
    metrics = {"A": {"heldout_rank_icir": 0.5, "sign_consistency": 0.9},
               "B": {"heldout_rank_icir": 0.5, "sign_consistency": 0.9}}
    # B is redundant with the pre-existing reference R; A is not
    corr = pd.DataFrame(
        [[1.0, 0.0, 0.0], [0.0, 1.0, 0.95], [0.0, 0.95, 1.0]],
        index=["A", "B", "R"], columns=["A", "B", "R"],
    )
    sel = select_marginal(pool=pool, metrics=metrics, corr=corr, caps={"x": 2, "y": 2},
                          floor=0.10, references=["R"])
    assert sel.factor_ids[0] == "A"  # A seeds; B is discounted by its 0.95 corr to the reference


@pytest.mark.skipif(not (CORR_CACHE.exists() and EWAVE_V2.exists()),
                    reason="E-wave cached corr / recorded selection absent")
def test_marginal_reproduces_ewave_6core_regression():
    """Bitwise regression: the library greedy on the SAME E-wave inputs reproduces the
    recorded EWaveSelectedSet_v2 ordered selection."""
    from workspace.scripts import select_e_wave_marginal as ew

    pool = ew.load_pool()
    metrics = ew.load_inputA(pool)
    corr = pd.read_parquet(CORR_CACHE)
    sel = select_marginal(pool=pool, metrics=metrics, corr=corr,
                          caps=ew.CAPS_STYLE_AWARE, floor=0.10, references=ew.REFERENCES)
    recorded = [s["factor"] for s in json.loads(EWAVE_V2.read_text(encoding="utf-8"))["primary"]["selected"]]
    assert sel.factor_ids == recorded
    # the 6-core (the picks above the 0.27 marginal break) are the first six
    assert sel.head(6) == recorded[:6]


# ============================ sealed_oos bar ============================

def test_direction_aligned_pass_short_and_long():
    # a held-short factor with negative raw icir/sharpe aligns to positive
    ok, ri, ls = direction_aligned_pass("short", -0.61, -3.76)
    assert ok and ri > 0 and ls == pytest.approx(3.76)
    # a held-long factor with positive raw values aligns straight through
    ok, ri, ls = direction_aligned_pass("long", 0.51, 3.07)
    assert ok and ls == pytest.approx(3.07)


def test_direction_aligned_pass_floor_and_nan():
    assert direction_aligned_pass("long", 0.3, 1.0)[0] is False  # ls must be STRICTLY > 1.0
    assert direction_aligned_pass("long", 0.3, 1.0001)[0] is True
    assert direction_aligned_pass("long", float("nan"), 3.0)[0] is False  # NaN icir -> fail
    assert direction_aligned_pass("short", -0.3, float("nan"))[0] is False


def test_sides_from_frozen_set_derives_held_side():
    from src.alpha_research.factor_eval_skill.sealed_oos import sides_from_frozen_set
    from src.research_orchestrator.frozen_selection_set import FrozenSelectionSet, SelectedFactor

    fs = FrozenSelectionSet(
        selected=(SelectedFactor("a", 1, "da", "short"), SelectedFactor("b", 1, "db", "long")),
        candidate_pool_hash="p", selection_rule_hash="r", eval_protocol_hash="e",
        metric="rank_icir", portfolio_side="long_short", universe="u",
        time_split_window="w", rebalance="20d", neutralization="none",
    )
    # held side comes straight from the sealed set's expected_direction -> no separate sides arg
    assert sides_from_frozen_set(fs) == {"a": "short", "b": "long"}


@pytest.mark.skipif(not EWAVE_OOS.exists(), reason="E-wave recorded sealed-OOS verdict absent")
def test_sealed_oos_bar_reproduces_ewave_6of6_regression():
    """Replay the recorded per-factor OOS numbers through the bar -> the recorded 6/6."""
    recorded = json.loads(EWAVE_OOS.read_text(encoding="utf-8"))
    sides = {r["factor"]: r["side"] for r in recorded["results"]}
    per_factor = {r["factor"]: {"oos_rank_icir": r["oos_rank_icir"], "oos_ls_sharpe": r["oos_ls_sharpe"]}
                  for r in recorded["results"]}
    verdict = evaluate_sealed_oos_bar(sides, per_factor)
    assert verdict.n_pass == recorded["n_pass"] == 6
    by_factor = {x["factor"]: x for x in verdict.results}
    for r in recorded["results"]:
        assert by_factor[r["factor"]]["pass"] == r["pass"]
        assert by_factor[r["factor"]]["aligned_ls_sharpe"] == pytest.approx(r["aligned_ls_sharpe"], abs=1e-6)


# ============================ deployment composite ============================

def _synthetic_day(n=60, sign_member="F"):
    idx = pd.Index([f"{i:06d}.SZ" for i in range(n)], name="instrument")
    # F increases with i; held short (sign -1) so the LOWEST F should rank HIGHEST (long)
    return pd.DataFrame({
        sign_member: np.arange(n, dtype=float),
        "amt20": np.arange(n, 0, -1, dtype=float) * 1e6,  # all positive, descending
        "close": np.ones(n) * 10.0,
        "amount": np.ones(n) * 1e7,
    }, index=idx)


def test_composite_direction_alignment():
    day = _synthetic_day()
    ranked = direction_aligned_composite(day, [("F", -1)], liq_topn=300, min_factors=1, min_names=50)
    assert ranked is not None
    assert ranked.index[0] == "000000.SZ"  # lowest F -> highest composite (held short -> long the low end)
    assert ranked.index[-1] == "000059.SZ"


def test_composite_returns_none_when_too_thin():
    day = _synthetic_day(n=40)  # below min_names=50
    assert direction_aligned_composite(day, [("F", -1)], min_names=50) is None


def test_composite_excludes_st_and_untradeable():
    day = _synthetic_day(n=60)
    day.loc["000000.SZ", "amount"] = 0.0  # untradeable on rebal day -> dropped
    ranked = direction_aligned_composite(day, [("F", -1)], min_factors=1, st_codes=["000001.SZ"])
    assert "000000.SZ" not in ranked.index  # zero amount
    assert "000001.SZ" not in ranked.index  # ST


def test_build_ranked_schedule_two_dates():
    d1, d2 = pd.Timestamp("2021-01-29"), pd.Timestamp("2021-02-26")
    day = _synthetic_day(n=60)
    panel = pd.concat({d1: day, d2: day}, names=["datetime", "instrument"])
    sched, turnover = build_ranked_schedule(panel, [("F", -1)], [d1, d2], topk=10, min_factors=1)
    assert len(sched[d1]) == 30  # headroom = topk * 3
    assert turnover == pytest.approx(0.0)  # identical panels -> no membership churn
