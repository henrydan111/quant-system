# Unit tests for the BUILD-0 TC PoC pure logic (no cache needed): weight construction + concentration
# cap, the fail-CLOSED screen gate, the TC IC-scalar-washes-out algebra, and residual<=total sigma.
# Reproducibility guard requested by the GPT §10 REWORK (2026-07-11).
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "workspace" / "scripts"))
import build0_tc_poc as b0  # noqa: E402


def _synth(n=30, seed=0):
    rng = np.random.default_rng(seed)
    idx = [f"{i:06d}_SZ" for i in range(n)]
    comp = pd.Series(np.sort(rng.normal(size=n))[::-1], index=idx)
    comp = comp - comp.mean() + 1.5                       # shift so the top-K z are positive
    sigma = pd.Series(rng.uniform(0.01, 0.05, n), index=idx)
    circ = pd.Series(rng.uniform(1e6, 1e8, n), index=idx)
    return comp, sigma, circ


class TestConcentrationCap:
    def test_cap_simplex_respects_cap_sums_one_longonly(self):
        w = pd.Series([0.5, 0.3, 0.15, 0.05], index=list("abcd"))
        capped = b0._cap_simplex(w, 0.30)
        assert abs(capped.sum() - 1.0) < 1e-9
        assert (capped <= 0.30 + 1e-9).all()
        assert (capped >= 0.0).all()

    def test_cap_simplex_infeasible_falls_back_uniform(self):
        w = pd.Series([0.6, 0.4], index=list("ab"))       # 2 * 0.10 < 1 -> infeasible
        capped = b0._cap_simplex(w, 0.10)
        assert abs(capped.sum() - 1.0) < 1e-9
        assert np.allclose(capped.values, 0.5)

    def test_uncapped_is_noop_normalize(self):
        w = pd.Series([2.0, 1.0, 1.0], index=list("abc"))
        out = b0._cap_simplex(w, 1.0)
        assert np.allclose(out.values, [0.5, 0.25, 0.25])


class TestWeightVectors:
    def test_same_name_set_sum_one_longonly(self):
        comp, sigma, circ = _synth()
        wv = b0._weight_vectors(comp, sigma, circ, max_weight=1.0)
        base = set(comp.index)
        assert set(wv) == set(b0.CONSTRUCTIONS)
        for name, w in wv.items():
            assert set(w.index) == base, f"{name} changed the name set (four-layer violation)"
            assert abs(w.sum() - 1.0) < 1e-9, name
            assert (w >= -1e-12).all(), name

    def test_cap_enforced(self):
        comp, sigma, circ = _synth()
        wv = b0._weight_vectors(comp, sigma, circ, max_weight=0.05)
        for name, w in wv.items():
            assert (w <= 0.05 + 1e-9).all(), name

    def test_eqw_is_uniform(self):
        comp, sigma, circ = _synth()
        wv = b0._weight_vectors(comp, sigma, circ, max_weight=1.0)
        assert np.allclose(wv["eqw"].values, 1.0 / len(comp))


class TestScreenFailClosed:
    """The gate must NEVER pass on missing statistical evidence, and must require a meaningful Sharpe
    margin AND an MDD guard (not CAGR-only) — the two Blockers the first-cut verdict violated."""

    def _inputs(self, tail_mass, d_sharpe=0.20, d_mdd=+0.01):
        rows = {"eqw": {"sharpe": 1.0, "mdd": -0.40, "cagr": 0.20},
                "alpha": {"sharpe": 1.0 + d_sharpe, "mdd": -0.40 + d_mdd, "cagr": 0.25},
                "sigcomp": {"sharpe": 1.0, "mdd": -0.40, "cagr": 0.20},
                "invvol": {"sharpe": 1.0, "mdd": -0.40, "cagr": 0.20}}
        tc = {"tc": {k: {"full_calib": 0.30} for k in rows}}
        boot = {"alpha": {"tail_mass_le_0": tail_mass},
                "sigcomp": {"tail_mass_le_0": 0.50}, "invvol": {"tail_mass_le_0": 0.50}}
        return rows, tc, boot

    def test_nan_tailmass_never_passes(self):
        rows, tc, boot = self._inputs(np.nan)
        v = b0._verdict(rows, tc, boot)
        assert v["per_construction"]["alpha"]["screen_passed"] is False
        assert v["screen_passed"] is False

    def test_high_tailmass_never_passes(self):
        rows, tc, boot = self._inputs(0.20)              # >= FWER_ALPHA (0.10)
        v = b0._verdict(rows, tc, boot)
        assert v["per_construction"]["alpha"]["screen_passed"] is False

    def test_small_sharpe_never_passes(self):
        rows, tc, boot = self._inputs(0.02, d_sharpe=0.05)   # below +0.10 margin
        v = b0._verdict(rows, tc, boot)
        assert v["per_construction"]["alpha"]["screen_passed"] is False

    def test_worse_mdd_never_passes(self):
        rows, tc, boot = self._inputs(0.02, d_sharpe=0.20, d_mdd=-0.05)  # MDD 5pp worse
        v = b0._verdict(rows, tc, boot)
        assert v["per_construction"]["alpha"]["screen_passed"] is False

    def test_all_conditions_met_passes(self):
        rows, tc, boot = self._inputs(0.02, d_sharpe=0.20, d_mdd=+0.01)
        v = b0._verdict(rows, tc, boot)
        assert v["per_construction"]["alpha"]["screen_passed"] is True
        assert v["screen_passed"] is True

    def test_status_is_inconclusive_when_none_pass(self):
        rows, tc, boot = self._inputs(0.50, d_sharpe=0.0)
        v = b0._verdict(rows, tc, boot)
        assert v["status"] == "INCONCLUSIVE_no_greenlight"


class TestTCAlgebra:
    def test_ic_scalar_washes_out(self):
        rng = np.random.default_rng(1)
        z = pd.Series(rng.normal(size=300))
        x = pd.Series(rng.normal(size=300))
        assert abs(b0._tc_pair(z, x) - b0._tc_pair(5.0 * z, x)) < 1e-9

    def test_degenerate_returns_nan(self):
        z = pd.Series([1.0] * 50)                          # zero variance
        x = pd.Series(np.arange(50, dtype=float))
        assert np.isnan(b0._tc_pair(z, x))


class TestResidualSigma:
    def test_residual_le_total(self):
        rng = np.random.default_rng(2)
        cols = [f"{i:06d}_SZ" for i in range(20)]
        idx = pd.date_range("2019-01-01", periods=80, freq="B")
        mkt_base = pd.Series(rng.normal(0, 0.012, 80), index=idx)
        ret = pd.DataFrame({c: 0.8 * mkt_base + pd.Series(rng.normal(0, 0.01, 80), index=idx)
                            for c in cols})
        mkt = ret.mean(axis=1)
        pday = idx[-1]
        tot = b0._sigma_asof(ret, mkt, pday, cols, "total")
        res = b0._sigma_asof(ret, mkt, pday, cols, "residual")
        both = pd.concat([tot.rename("t"), res.rename("r")], axis=1).dropna()
        assert len(both) > 0
        assert (both["r"] <= both["t"] + 1e-12).all()      # residual vol never exceeds total vol


class TestAprioriSigns:
    def test_low_vol_is_short_high_vol(self):
        assert b0.APRIORI_SIGNS["risk_vol_20d"] == -1.0    # low-volatility anomaly
        assert all(v == 1.0 for f, v in b0.APRIORI_SIGNS.items() if f != "risk_vol_20d")
