"""Tests for industry-relative composite factors (Layer 2).

Plan ref: vast-exploring-rabbit v8 phase C1.

Covers:
- Registry shape (`get_industry_relative_defs`)
- Per-kind compute correctness (industry_mean_subtract, size_industry_neutralize)
- Null industry handling (Codex review-3 finding I4 — must mask, not silently misclassify)
- Schema integration with `get_required_catalog` and `build_factor_meta`
- PIT safety inheritance through the parser test
"""
from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.alpha_research.factor_library import (
    add_industry_relative_composites,
    get_factor_catalog,
    get_industry_relative_defs,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _synthetic_factors_df(n_dates: int = 30, n_stocks: int = 60) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Build a synthetic factors_df + industry_series + market_cap fixture.

    Uses real Tushare ts_codes from data/reference/stock_basic.parquet so
    `build_industry_series_asof` returns valid SW2021 labels for every stock.
    """
    rng = np.random.default_rng(0)
    sb = pd.read_parquet(PROJECT_ROOT / "data" / "reference" / "stock_basic.parquet")
    sb = sb[sb["delist_date"].isna()].head(n_stocks)
    qlib_codes = sb["ts_code"].str.replace(".", "_", regex=False).str.upper().tolist()

    dates = pd.date_range("2024-01-02", periods=n_dates, freq="B")
    idx = pd.MultiIndex.from_product([dates, qlib_codes], names=["datetime", "instrument"])

    factors_df = pd.DataFrame(
        {
            "mom_return_20d": rng.standard_normal(len(idx)).astype(np.float32),
            "val_ep_ttm": rng.standard_normal(len(idx)).astype(np.float32),
            "val_bp": rng.standard_normal(len(idx)).astype(np.float32),
        },
        index=idx,
    )
    market_cap = pd.Series(
        rng.uniform(1e9, 1e12, len(idx)).astype(np.float32), index=idx, name="market_cap"
    )

    from src.data_infra.provider_metadata import build_industry_series_asof

    industry_series = build_industry_series_asof(idx, "L1")
    return factors_df, industry_series, market_cap


class RegistryTests(unittest.TestCase):
    def test_registry_has_4_defs(self):
        defs = get_industry_relative_defs()
        self.assertEqual(len(defs), 4)
        names = {d["name"] for d in defs}
        self.assertEqual(
            names,
            {"mom_industry_rel_20d", "mom_idio_20d", "val_ep_industry_rel", "val_bp_industry_rel"},
        )

    def test_registry_schema_complete(self):
        for d in get_industry_relative_defs():
            for key in ("name", "base", "kind", "requires_market_cap"):
                self.assertIn(key, d, f"def {d.get('name')} missing key {key}")
            self.assertIn(d["kind"], {"industry_mean_subtract", "size_industry_neutralize"})

    def test_size_industry_neutralize_uses_correct_helper(self):
        """Codex review-3 finding B2: mom_idio_20d MUST be size+industry, not industry-only."""
        defs = {d["name"]: d for d in get_industry_relative_defs()}
        self.assertEqual(defs["mom_idio_20d"]["kind"], "size_industry_neutralize")
        self.assertTrue(defs["mom_idio_20d"]["requires_market_cap"])

    def test_bases_are_in_factor_catalog(self):
        catalog = get_factor_catalog(include_new_data=True)
        for d in get_industry_relative_defs():
            self.assertIn(
                d["base"], catalog,
                f"base factor {d['base']} for {d['name']} not in catalog — would break compute_factor_inputs",
            )


class ComputeTests(unittest.TestCase):
    def test_emits_4_columns(self):
        factors_df, industry_series, market_cap = _synthetic_factors_df()
        out = add_industry_relative_composites(
            factors_df, industry_series, market_cap=market_cap, defs=get_industry_relative_defs()
        )
        for name in (
            "mom_industry_rel_20d",
            "val_ep_industry_rel",
            "val_bp_industry_rel",
        ):
            self.assertIn(name, out.columns)
        # mom_idio_20d may produce all-NaN if cross-section < min_obs (50);
        # still must be present as a column.
        self.assertIn("mom_idio_20d", out.columns)

    def test_industry_mean_subtract_zero_within_industry(self):
        """For each (date, industry), the industry-relative factor must average ~0.

        This is the definitional property of industry-mean-subtraction.
        """
        factors_df, industry_series, market_cap = _synthetic_factors_df()
        out = add_industry_relative_composites(
            factors_df, industry_series, market_cap=market_cap, defs=get_industry_relative_defs()
        )
        rel = out["mom_industry_rel_20d"]
        # Group by (date, industry); within each group mean should be ~0
        names = list(rel.index.names)
        dt_level = names.index("datetime")
        date_lvl = rel.index.get_level_values(dt_level)
        # For each (date, industry) bucket the within-bucket mean should be ~0
        df = pd.DataFrame({"rel": rel.values, "date": date_lvl, "ind": industry_series.values})
        df = df.dropna(subset=["rel", "ind"])
        bucket_means = df.groupby(["date", "ind"])["rel"].mean()
        # Allow tiny float epsilon
        self.assertLess(bucket_means.abs().max(), 1e-5)

    def test_null_industry_masked(self):
        """Codex review-3 finding I4: stocks with NaN industry produce NaN output,
        not zero, not silently mapped to the dropped reference category.
        """
        factors_df, industry_series, market_cap = _synthetic_factors_df()
        # Force a NaN industry on the first stock for the first 5 dates
        first_stock = factors_df.index.get_level_values(1)[0]
        first_dates = pd.unique(factors_df.index.get_level_values(0))[:5]
        mask = (factors_df.index.get_level_values(0).isin(first_dates) &
                (factors_df.index.get_level_values(1) == first_stock))
        industry_series_mut = industry_series.copy()
        industry_series_mut.loc[mask] = pd.NA

        out = add_industry_relative_composites(
            factors_df, industry_series_mut, market_cap=market_cap, defs=get_industry_relative_defs()
        )
        for name in ("mom_industry_rel_20d", "val_ep_industry_rel", "val_bp_industry_rel"):
            null_industry_outputs = out.loc[mask, name]
            self.assertTrue(
                null_industry_outputs.isna().all(),
                f"{name}: null industry stocks must produce NaN output, got: "
                f"{null_industry_outputs.dropna().head().tolist()}",
            )

    def test_skips_when_base_missing(self):
        """If the base factor isn't in factors_df, skip with warning — don't raise."""
        factors_df, industry_series, market_cap = _synthetic_factors_df()
        partial_df = factors_df.drop(columns=["val_ep_ttm"])
        out = add_industry_relative_composites(
            partial_df, industry_series, market_cap=market_cap, defs=get_industry_relative_defs()
        )
        # val_ep_industry_rel should not have been added
        self.assertNotIn("val_ep_industry_rel", out.columns)
        # val_bp_industry_rel should still be there
        self.assertIn("val_bp_industry_rel", out.columns)


class IntegrationTests(unittest.TestCase):
    def test_get_required_catalog_accepts_industry_rel(self):
        """Codex review-3 finding B3: candidate list with industry-rel must NOT raise KeyError."""
        from workspace.research.alpha_mining.event_driven_strategy_research import get_required_catalog

        cat, comp, comp_map, ind_rel = get_required_catalog(
            ["mom_industry_rel_20d", "val_ep_ttm"], include_new_data=True
        )
        self.assertEqual(len(ind_rel), 1)
        self.assertEqual(ind_rel[0]["name"], "mom_industry_rel_20d")
        self.assertIn("mom_return_20d", cat)  # base factor must be in trimmed catalog
        self.assertIn("val_ep_ttm", cat)

    def test_build_factor_meta_emits_industry_rel_entries(self):
        from workspace.research.alpha_mining.event_driven_strategy_research import build_factor_meta

        meta = build_factor_meta(
            ["mom_industry_rel_20d", "mom_idio_20d", "val_ep_ttm"], include_new_data=True
        )
        self.assertIn("mom_industry_rel_20d", meta)
        self.assertIn("mom_idio_20d", meta)
        self.assertTrue(
            meta["mom_industry_rel_20d"]["expression"].startswith("INDUSTRY_REL[")
        )
        self.assertIn("mom_return_20d", meta["mom_industry_rel_20d"]["expression"])


class PITSafetyTests(unittest.TestCase):
    """The 4 industry-relative factors are Layer 2 — they inherit PIT safety
    from their base factors via the catalog parser test. Verify the linkage."""

    def test_all_bases_pass_pit_parser(self):
        """Each base referenced by an industry-rel def must have a PIT-safe expression
        in the catalog — meaning the static parser's $field-Ref-wrap check has held.
        """
        from tests.alpha_research.test_factor_library_pit_safety import (
            find_unwrapped_field_references,
        )

        catalog = get_factor_catalog(include_new_data=True)
        for d in get_industry_relative_defs():
            base = d["base"]
            self.assertIn(base, catalog, f"{base} must be in catalog")
            expr = catalog[base]
            violations = find_unwrapped_field_references(expr)
            self.assertEqual(
                violations, [],
                f"PIT safety violation in base {base} (used by {d['name']}): {violations}",
            )


if __name__ == "__main__":
    unittest.main()
