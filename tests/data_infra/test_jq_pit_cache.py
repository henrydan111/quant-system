"""Smoke + invariant tests for the JoinQuant PIT cache and the
``jqdata_local`` shim. Uses the migrated 中小综 (399101.XSHE) snapshots
already in ``data/external/jq_pit_cache/index_members/`` — no JoinQuant
network access required.
"""

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.data_infra.jq_pit_cache import (
    JoinQuantPITLoader, CacheMissError,
    jq_to_tushare, tushare_to_jq,
)


class CodeConversionTests(unittest.TestCase):
    def test_jq_to_tushare_roundtrip(self):
        for jq in ('002001.XSHE', '600519.XSHG'):
            self.assertEqual(tushare_to_jq(jq_to_tushare(jq)), jq)

    def test_tushare_to_jq_roundtrip(self):
        for ts in ('002001.SZ', '600519.SH'):
            self.assertEqual(jq_to_tushare(tushare_to_jq(ts)), ts)


class LoaderManifestTests(unittest.TestCase):
    def test_manifest_exists_and_lists_indices(self):
        loader = JoinQuantPITLoader()
        m = loader.manifest()
        self.assertIn('schema_version', m)
        self.assertIn('coverage', m)
        # The 399101.XSHE migration should be reflected in the manifest
        self.assertIn('399101.XSHE', m.get('indices_tracked', []))
        idx_cov = m['coverage']['index_members']['399101.XSHE']
        self.assertEqual(idx_cov['n_snapshots'], 597)
        self.assertEqual(idx_cov['start'], '2014-01-07')
        self.assertEqual(idx_cov['end'], '2026-02-24')


class IndexMembersTests(unittest.TestCase):
    def setUp(self):
        self.loader = JoinQuantPITLoader()

    def test_returns_tushare_format_codes(self):
        members = self.loader.get_index_stocks('399101.XSHE', '2024-01-09')
        self.assertGreater(len(members), 100)
        # All codes must be Tushare format (.SZ / .SH)
        for c in members[:20]:
            self.assertTrue(c.endswith('.SZ') or c.endswith('.SH'),
                            f"Expected Tushare format, got {c}")

    def test_known_membership_size_on_first_snapshot(self):
        # 2014-01-07 (the first migrated snapshot) had 701 members per the
        # original investigation. Locks the migration.
        members = self.loader.get_index_stocks('399101.XSHE', '2014-01-07')
        self.assertEqual(len(members), 701)

    def test_known_membership_size_on_2024_02_06(self):
        # The 2024-02-06 limit-down day we audited in the investigation
        members = self.loader.get_index_stocks('399101.XSHE', '2024-02-06')
        # 中小综 in early 2024 has ~950 members
        self.assertGreater(len(members), 900)
        self.assertLess(len(members), 1000)

    def test_forward_fill_on_non_snapshot_date(self):
        # Wednesday 2015-07-29 (no snapshot — snapshots are Tuesdays)
        # should forward-fill to Tuesday 2015-07-28's membership.
        wed = self.loader.get_index_stocks('399101.XSHE', '2015-07-29')
        tue = self.loader.get_index_stocks('399101.XSHE', '2015-07-28')
        self.assertEqual(wed, tue)

    def test_unknown_index_raises_cache_miss(self):
        with self.assertRaises(CacheMissError):
            self.loader.get_index_stocks('999999.XSHE', '2024-01-01')

    def test_date_before_earliest_with_no_forward_fill_raises(self):
        with self.assertRaises(CacheMissError):
            self.loader.get_index_stocks('399101.XSHE', '2013-01-01',
                                         forward_fill=False)

    def test_date_before_earliest_with_forward_fill_returns_earliest(self):
        # forward_fill=True is the default; falls back to earliest snapshot
        members = self.loader.get_index_stocks('399101.XSHE', '2013-01-01')
        first_snap = self.loader.get_index_stocks('399101.XSHE', '2014-01-07')
        self.assertEqual(members, first_snap)


class ValuationFlagsCacheMissTests(unittest.TestCase):
    """Valuation + flags haven't been exported yet — verify the loader
    surfaces a clean CacheMissError instead of silently returning bad data."""

    def setUp(self):
        self.loader = JoinQuantPITLoader()

    def test_valuation_snapshot_raises_when_missing(self):
        with self.assertRaises(CacheMissError):
            self.loader.get_valuation_snapshot('2024-01-09')

    def test_get_market_cap_raises_when_missing(self):
        with self.assertRaises(CacheMissError):
            self.loader.get_market_cap('000001.SZ', '2024-01-09')

    def test_is_st_safe_default_when_missing(self):
        # Missing flags row → False (documented fallback)
        self.assertFalse(self.loader.is_st('000001.SZ', '2024-01-09'))
        self.assertFalse(self.loader.is_paused('000001.SZ', '2024-01-09'))


class JqdataLocalShimTests(unittest.TestCase):
    """Verifies the compat-shim front door for ported JoinQuant strategies."""

    def setUp(self):
        from src.data_infra import jqdata_local
        # Reset context for each test
        jqdata_local._LOCAL_CTX.__dict__.clear()
        jqdata_local._current_data_proxy = None

    def test_get_index_stocks_requires_date_or_context(self):
        from src.data_infra.jqdata_local import get_index_stocks
        with self.assertRaises(ValueError):
            get_index_stocks('399101.XSHE')

    def test_get_index_stocks_with_date_returns_jq_format(self):
        from src.data_infra.jqdata_local import get_index_stocks
        members = get_index_stocks('399101.XSHE', date='2024-02-06')
        for c in members[:20]:
            self.assertTrue(c.endswith('.XSHE') or c.endswith('.XSHG'),
                            f"Expected JoinQuant format, got {c}")

    def test_get_index_stocks_with_context_date(self):
        from src.data_infra.jqdata_local import (
            get_index_stocks, set_context_date,
        )
        set_context_date('2024-02-06')
        members = get_index_stocks('399101.XSHE')
        self.assertGreater(len(members), 900)

    def test_get_index_stocks_tushare_format_opt_in(self):
        from src.data_infra.jqdata_local import get_index_stocks
        members = get_index_stocks('399101.XSHE', date='2024-02-06',
                                   return_format='tushare')
        for c in members[:20]:
            self.assertTrue(c.endswith('.SZ') or c.endswith('.SH'),
                            f"Expected Tushare format, got {c}")

    def test_current_data_returns_safe_defaults_when_no_quotes(self):
        from src.data_infra.jqdata_local import (
            get_current_data, set_context_date,
        )
        set_context_date('2024-02-06')
        cd = get_current_data()
        s = cd['002001.XSHE']
        # No injected day_quotes, no flags data → safe defaults
        self.assertFalse(s.is_st)
        self.assertFalse(s.paused)
        self.assertIsNone(s.day_open)
        self.assertIsNone(s.high_limit)


if __name__ == '__main__':
    unittest.main()
