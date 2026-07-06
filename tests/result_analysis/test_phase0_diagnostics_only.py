"""C9 test_stub: Phase-0 reporting discipline — diagnostics ONLY, fail-closed.

Contract (CONTRACTS.md C9): Phase 0 reports IC/RankIC/ICIR/monotonicity/
turnover/quantile-spread as research diagnostics only. NO deployable
performance claim (CAGR/Sharpe/MDD/annual return) until the Phase-1
event-driven total-return backtest. The report builder enforces this with a
metric-key ALLOWLIST (fail-closed) and an immutable diagnostics envelope.
"""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from result_analysis.phase0_report import (  # noqa: E402
    Phase0DisciplineError,
    assert_phase0_report,
    build_phase0_report,
)

OK_METRICS = {
    "rank_ic_mean": 0.021,
    "rank_icir": 0.31,
    "ic_mean": 0.018,
    "monotonicity": 0.8,
    "turnover_mean": 0.45,
    "quantile_spread_q10_q1": 0.004,
    "coverage": 0.97,
    "n_obs": 65,
}


def test_allowed_diagnostics_pass_and_envelope_is_stamped():
    rpt = build_phase0_report(OK_METRICS, universe="golden_stock_pool", window="2020-07..2026-01")
    assert rpt["evidence_class"] == "research_diagnostics_only"
    assert rpt["deployable_claim"] is False
    assert rpt["phase"] == "phase0"
    assert rpt["metrics"]["rank_icir"] == 0.31
    assert_phase0_report(rpt)  # round-trips clean


@pytest.mark.parametrize(
    "bad_key", ["cagr", "sharpe", "annualized_return", "max_drawdown", "net_return"]
)
def test_deployable_metrics_fail_closed(bad_key):
    metrics = dict(OK_METRICS)
    metrics[bad_key] = 0.2
    with pytest.raises(Phase0DisciplineError):
        build_phase0_report(metrics, universe="u", window="w")


def test_nested_breakdowns_are_validated_recursively():
    metrics = {"rank_icir": 0.3, "by_year": {"2024": {"sharpe": 1.9}}}
    with pytest.raises(Phase0DisciplineError):
        build_phase0_report(metrics, universe="u", window="w")
    # allowed nested breakdown passes
    ok = {"rank_icir": 0.3, "by_year": {"2024": {"rank_ic_mean": 0.02}}}
    rpt = build_phase0_report(ok, universe="u", window="w")
    assert rpt["metrics"]["by_year"]["2024"]["rank_ic_mean"] == 0.02


def test_tampered_report_rejected():
    rpt = build_phase0_report(OK_METRICS, universe="u", window="w")
    rpt["deployable_claim"] = True
    with pytest.raises(Phase0DisciplineError):
        assert_phase0_report(rpt)
