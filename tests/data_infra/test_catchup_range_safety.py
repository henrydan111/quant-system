"""Phase 5-B / GPT B3: range- and year-safety of the reused fundamentals catch-up script.

The monthly freeze-bump REUSES workspace/scripts/catchup_fundamentals_range.py every bump, so
its month iteration must derive from the window (not a hardcoded 2026 span), cross a year
boundary (a report_rc TTL halo reaches into the prior year), and its resume state must be
scoped per bump so a new window is never skipped by a prior bump's `done` keys."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "catchup_fundamentals_range", ROOT / "workspace" / "scripts" / "catchup_fundamentals_range.py")
cfr = importlib.util.module_from_spec(_spec)
sys.modules["catchup_fundamentals_range"] = cfr
_spec.loader.exec_module(cfr)


def test_months_spanned_crosses_year_boundary():
    # a report_rc halo reaching from the prior year into the current one must enumerate BOTH
    # years' months in order (drives per-year output files report_rc_<year>.parquet).
    assert cfr.months_spanned("20251103", "20260215") == [
        "202511", "202512", "202601", "202602"]


def test_months_spanned_single_month():
    assert cfr.months_spanned("20260703", "20260731") == ["202607"]


def test_month_bounds_clips_and_defaults():
    # clipped to the window ends (report_rc fetch shouldn't reach outside the halo)...
    assert cfr.month_bounds("202602", "20260210", "20260220") == ("20260210", "20260220")
    # ...full-month when unclipped (index_weights monthly snapshot), incl. leap-Feb 2028.
    assert cfr.month_bounds("202607") == ("20260701", "20260731")
    assert cfr.month_bounds("202802") == ("20280201", "20280229")


def test_state_path_scoped_per_bump():
    # no suffix -> the shipped global file; a suffix -> a per-bump file (independent resume).
    base = cfr.state_path_for(None)
    tagged = cfr.state_path_for("20260831")
    assert base.endswith("catchup_fund_state.json")
    assert tagged.endswith("catchup_fund_state_20260831.json")
    assert base != tagged


def test_report_rc_window_defaults_to_start_end(monkeypatch):
    # Runner.__init__ must default the report_rc window to [start, end] when not given, and
    # honor an explicit halo window when it is. Construct without touching Tushare/storage.
    monkeypatch.setattr(cfr.TushareFetcher, "__init__", lambda self, **k: None)
    monkeypatch.setattr(cfr.StorageManager, "__init__", lambda self, *a, **k: None)
    monkeypatch.setattr(cfr, "load_state", lambda path: {})
    r = cfr.Runner("20260701", "20260731", dry=True)
    assert (r.report_rc_start, r.report_rc_end) == ("20260701", "20260731")
    r2 = cfr.Runner("20260701", "20260731", dry=True,
                    report_rc_start="20251101", report_rc_end="20260731", state_suffix="20260731")
    assert (r2.report_rc_start, r2.report_rc_end) == ("20251101", "20260731")
    assert r2.state_path.endswith("catchup_fund_state_20260731.json")
