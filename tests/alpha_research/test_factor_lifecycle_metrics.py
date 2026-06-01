"""Phase 4 slices 1+2 — metrics parity + split status-rule tests.

`metrics.py` ports the legacy revalidation scripts' formulas VERBATIM; these tests pin
that the port reproduces the inline script formulas on a synthetic panel (so a future
edit to metrics.py that drifts from the scripts fails here). `status_rules.py` splits the
legacy oos-based rule from the formal IS-only candidate rule.
"""

import unittest

import numpy as np
import pandas as pd

from src.alpha_research.factor_lifecycle import metrics
from src.alpha_research.factor_lifecycle.status_rules import (
    assign_historical_status,
    assign_candidate_status,
)
from src.alpha_research.factor_eval.ic_analysis import compute_ic_summary, compute_ic_by_year
from src.alpha_research.factor_eval.quantile_analysis import compute_quantile_returns


def _synthetic_panel(seed: int = 0):
    instruments = [f"{i:06d}_SZ" for i in range(100)]
    # 60 monthly dates (2016-2020): >=50 so the long-only excess series clears min_obs=50,
    # and 5 yearly folds for sign-consistency.
    dates = pd.date_range("2016-01-31", periods=60, freq="ME")
    index = pd.MultiIndex.from_product([instruments, dates], names=["instrument", "datetime"])
    rng = np.random.default_rng(seed)
    fvals = rng.standard_normal(len(index))
    fwdvals = 0.5 * fvals + 0.5 * rng.standard_normal(len(index))  # positive relationship
    return pd.Series(fvals, index=index), pd.Series(fwdvals, index=index)


class MetricsParityTests(unittest.TestCase):
    def test_rank_icir_matches_factor_eval(self):
        factor, fwd = _synthetic_panel()
        ic = metrics.factor_ic(factor, fwd)
        self.assertFalse(ic.empty)
        self.assertEqual(metrics.rank_icir(ic), compute_ic_summary(ic)["rank_icir"])
        self.assertTrue(np.isnan(metrics.rank_icir(ic.iloc[0:0])))  # empty -> NaN

    def test_yearly_sign_consistency_matches_script_formula(self):
        factor, fwd = _synthetic_panel()
        ic = metrics.factor_ic(factor, fwd)
        full = metrics.rank_icir(ic)
        # inline replication of revalidate_catalog_walkforward.main lines 130-135
        yearly = compute_ic_by_year(ic)
        expected = float((np.sign(yearly["mean_rank_ic"]) == np.sign(full)).sum()) / float(len(yearly))
        self.assertEqual(metrics.yearly_sign_consistency(ic, full), expected)
        self.assertEqual(metrics.yearly_fold_count(ic), len(yearly))

    def test_long_only_topbucket_matches_script_formula(self):
        factor, fwd = _synthetic_panel()
        ic = metrics.factor_ic(factor, fwd)
        sign = float(np.sign(metrics.rank_icir(ic)))
        got = metrics.long_only_topbucket(factor, fwd, sign, horizon=20)

        # inline replication of revalidate_derived_factors.long_only_topbucket (unrounded)
        ann = 252.0 / 20
        qdf = compute_quantile_returns(factor, fwd, n_quantiles=10, min_obs=50)
        self.assertFalse(qdf.empty)
        uni = (qdf.assign(w=qdf["mean_return"] * qdf["count"]).groupby("date")
               .apply(lambda g: g["w"].sum() / g["count"].sum()))
        good_q = int(qdf["quantile"].max()) if sign > 0 else int(qdf["quantile"].min())
        good = qdf[qdf["quantile"] == good_q].set_index("date")["mean_return"]
        excess = (good - uni).dropna()
        mu, sd = excess.mean(), excess.std()
        self.assertAlmostEqual(got["lo_excess_ann"], float(mu * ann), places=10)
        self.assertAlmostEqual(got["lo_sharpe"], float(mu / sd * np.sqrt(ann)), places=10)
        self.assertAlmostEqual(got["lo_hit"], float((excess > 0).mean()), places=10)

    def test_long_only_topbucket_zero_sign_is_nan(self):
        factor, fwd = _synthetic_panel()
        lo = metrics.long_only_topbucket(factor, fwd, 0.0)
        self.assertTrue(all(np.isnan(v) for v in lo.values()))


class HistoricalStatusRuleTests(unittest.TestCase):
    def test_field_ineligible_capped_draft(self):
        self.assertEqual(assign_historical_status(False, 0.3, 0.3, 1.0)[0], "draft")

    def test_collapsed_oos_deprecated(self):
        self.assertEqual(assign_historical_status(True, 0.3, 0.01, 1.0)[0], "deprecated")

    def test_sign_flip_deprecated(self):
        self.assertEqual(assign_historical_status(True, 0.30, -0.15, 1.0)[0], "deprecated")

    def test_walk_forward_stable_candidate(self):
        self.assertEqual(assign_historical_status(True, 0.20, 0.15, 0.80)[0], "candidate")

    def test_marginal_draft(self):
        self.assertEqual(assign_historical_status(True, 0.05, 0.05, 0.50)[0], "draft")

    def test_nan_insufficient_draft(self):
        self.assertEqual(assign_historical_status(True, float("nan"), 0.2, 0.8)[0], "draft")


class CandidateStatusRuleTests(unittest.TestCase):
    def test_is_only_rule_promotes_candidate(self):
        status, reason = assign_candidate_status(True, 0.15, 0.80, evidence_kind="generated_heldout")
        self.assertEqual(status, "candidate")
        self.assertIn("generated_heldout", reason)

    def test_marginal_stays_draft(self):
        self.assertEqual(assign_candidate_status(True, 0.05, 0.80)[0], "draft")
        self.assertEqual(assign_candidate_status(True, 0.15, 0.50)[0], "draft")

    def test_field_ineligible_and_missing_fail_closed(self):
        self.assertEqual(assign_candidate_status(False, 0.30, 0.90)[0], "draft")
        self.assertEqual(assign_candidate_status(True, float("nan"), 0.90)[0], "draft")
        self.assertEqual(assign_candidate_status(True, 0.30, float("nan"))[0], "draft")

    def test_candidate_rule_never_deprecates_and_takes_no_oos(self):
        import inspect
        # IS-only: the signature must not accept an oos argument
        params = set(inspect.signature(assign_candidate_status).parameters)
        self.assertNotIn("oos_icir", params)
        # exhaustively: the rule only ever yields candidate or draft
        for heldout in (-0.5, -0.1, 0.0, 0.05, 0.1, 0.5, float("nan")):
            for sc in (0.0, 0.5, 0.7, 1.0, float("nan")):
                self.assertIn(assign_candidate_status(True, heldout, sc)[0], {"candidate", "draft"})


if __name__ == "__main__":
    unittest.main()
