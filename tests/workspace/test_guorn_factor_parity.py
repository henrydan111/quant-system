"""Locks the GPT-review hardening of the NON-FORMAL 果仁 parity comparator (guorn_factor_parity.py):
Blocker-1 coverage gate, Blocker-2 pointwise-only guard, the non-trading-date fail-closed, and the M6
board-snapshot-vs-board_of() drift check. Pure-Python (no qlib): report()/assert_pointwise()/
validate_trading_date() don't touch the provider."""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "workspace" / "scripts"))
import guorn_factor_parity as gfp  # noqa: E402


def test_low_coverage_cannot_green(capsys):
    """B1: a partial matched panel that is PERFECT on the matched rows must NOT return ✅ — coverage gates it."""
    n = 100
    g = pd.DataFrame({"gval": [float(i + 1) for i in range(n)]}, index=[f"{i:06d}" for i in range(n)])
    lv = pd.Series({f"{i:06d}": float(i + 1) for i in range(50)}, name="lval")   # 50% cov, EXACT on matched
    gfp.report(g, lv, kind="value", gscale=1.0, min_coverage=0.98, label="t")
    out = capsys.readouterr().out
    assert "coverage gap" in out          # forced verdict
    assert "✅" not in out                 # the green metric-verdict is overridden, never printed
    # and a full-coverage exact panel DOES go green (the gate doesn't block legitimate parity)
    gfp.report(g, pd.Series({f"{i:06d}": float(i + 1) for i in range(n)}, name="lval"),
               kind="value", gscale=1.0, min_coverage=0.98, label="t")
    assert "✅" in capsys.readouterr().out


def test_cross_sectional_expr_refuses_subset_fetch():
    """B2: cross-sectional/group/neutralized exprs change with the instrument set → refused (export-codes-only)."""
    for expr in ("cs_rank($total_mv)", "HAVG($pe_ttm,1)", "HNeutralize($bp)", "cs_zscore($roe)"):
        with pytest.raises(SystemExit):
            gfp.assert_pointwise(expr)
    for expr in ("$total_mv/1e4", "($revenue_sq_q0-$oper_cost_sq_q0)/$total_assets_q0",
                 "$report_rc__n_active_orgs", "Ref($close,1)/Ref($close,21)-1"):
        gfp.assert_pointwise(expr)        # pointwise exprs (incl. time-series ops) pass


def test_non_trading_date_fails_closed():
    """Minor-2: a non-trading day must NOT silently fall back to the prior session; > calendar-max must refuse."""
    cal = pd.DatetimeIndex(pd.to_datetime(["2025-12-29", "2025-12-30", "2025-12-31"]))   # Mon–Wed
    with pytest.raises(SystemExit):
        gfp.validate_trading_date("2025-12-27", cal)      # Saturday, not in cal
    with pytest.raises(SystemExit):
        gfp.validate_trading_date("2026-06-26", cal)      # beyond the calendar max
    assert gfp.validate_trading_date("2025-12-31", cal) == pd.Timestamp("2025-12-31")


def test_board_of_is_canonical_and_prefix_drift_is_bounded():
    """M6: board_of() is the canonical board classifier (the skill makes it canonical over the bare prefix
    snapshot). This locks board_of's classification AND proves WHY: the MAIN_PREFIXES snapshot (300/301) has
    DRIFTED — 302xxx ChiNext codes exist that board_of correctly catches but the prefix list misses. The test
    bounds that drift to ChiNext 30xxxx (board_of handles it) so a NEW kind of drift (a real misclassification)
    fails loudly."""
    jq = ROOT / "workspace" / "research" / "jq_replication"
    insts = ROOT / "data" / "qlib_data" / "instruments" / "all_stocks.txt"
    if not (jq / "jq_rep_utils.py").exists():
        pytest.skip("jq_rep_utils not available")
    sys.path.insert(0, str(jq))
    from jq_rep_utils import board_of  # noqa: E402

    # canonical classifier is correct on every board, incl. the recent 302xxx ChiNext block + BSE 920
    assert board_of("302132_SZ") == "chinext"
    assert board_of("300750_SZ") == "chinext"
    assert board_of("688981_SH") == "star"
    assert board_of("920145_BJ") == "bse"
    assert board_of("600000_SH") == "main"
    assert board_of("000001_SZ") == "main"

    if not insts.exists():
        pytest.skip("frozen provider universe not available")
    MAIN_PREFIXES = ("600", "601", "603", "605", "000", "001", "002", "003", "300", "301")
    codes = pd.read_csv(insts, sep="\t", header=None, usecols=[0], names=["code"])["code"].astype(str)
    drift = [c for c in codes
             if (c.split("_")[0][:3] in MAIN_PREFIXES) != (board_of(c) in ("main", "chinext"))]
    # every drift must be a ChiNext 30xxxx name board_of CORRECTLY catches — never a misclassification.
    # (drift != ∅ on the current provider, e.g. 302132_SZ — the documented reason board_of is canonical.)
    bad = [c for c in drift if not (c.split("_")[0][:2] == "30" and board_of(c) == "chinext")]
    assert not bad, f"unexpected board drift {bad[:8]} — board_of() is canonical; investigate the snapshot"
