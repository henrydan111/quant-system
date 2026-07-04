"""Phase 5-B / GPT B3: range- and year-safety of the reused fundamentals catch-up script.

The monthly freeze-bump REUSES workspace/scripts/catchup_fundamentals_range.py every bump, so
its month iteration must derive from the window (not a hardcoded 2026 span), cross a year
boundary (a report_rc TTL halo reaches into the prior year), and its resume state must be
scoped per bump so a new window is never skipped by a prior bump's `done` keys."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd

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


def test_report_rc_first_seen_dedup_nan_wins_for_identical_bootstrap():
    # m1: locks the Stage E dedup semantic. A pre-instrumentation bootstrap row (NaN raw_fetch_ts)
    # keeps its earliest-possible first-seen over a today re-fetch of IDENTICAL content; CHANGED
    # content is a DISTINCT row that keeps the new stamp; a bootstrap-only row survives.
    old = pd.DataFrame({"ts_code": ["A", "B"], "eps": [1.0, 2.0],
                        "raw_fetch_ts": [float("nan"), float("nan")]})
    new = pd.DataFrame({"ts_code": ["A", "C"], "eps": [1.0, 3.0],
                        "raw_fetch_ts": ["2026-08-31 10:00:00", "2026-08-31 10:00:00"]})
    combined = pd.concat([old, new], ignore_index=True)
    content = [c for c in combined.columns if c != "raw_fetch_ts"]
    out = (combined.sort_values("raw_fetch_ts", kind="mergesort", na_position="first")
           .drop_duplicates(subset=content, keep="first").reset_index(drop=True))
    a = out[out["ts_code"] == "A"].iloc[0]
    assert pd.isna(a["raw_fetch_ts"]), "identical bootstrap content keeps its NaN first-seen"
    c = out[out["ts_code"] == "C"].iloc[0]
    assert c["raw_fetch_ts"] == "2026-08-31 10:00:00", "changed content keeps today's stamp"
    assert (out["ts_code"] == "B").any(), "bootstrap-only row survives"


def test_stage_e_fails_closed_on_zero_month(tmp_path, monkeypatch):
    # M2: a zero-row MONTH inside an otherwise non-empty halo must fail closed. Stage E work()
    # raises -> _run_key records it failed (runner.failed non-empty -> main() would exit 1).
    monkeypatch.setattr(cfr, "PROJECT_ROOT", str(tmp_path))
    monkeypatch.setattr(cfr.TushareFetcher, "__init__", lambda self, **k: None)
    monkeypatch.setattr(cfr.StorageManager, "__init__", lambda self, *a, **k: None)
    monkeypatch.setattr(cfr, "load_state", lambda p: {})
    monkeypatch.setattr(cfr, "save_state", lambda p, s: None)
    r = cfr.Runner("20260101", "20260228", dry=False,
                   report_rc_start="20260101", report_rc_end="20260228")

    class FakePro:
        report_rc = staticmethod(lambda **k: None)

    def fake_paginated(fn, limit, start_date, end_date):
        if start_date[:6] == "202602":            # 202602 throttled -> zero rows
            return pd.DataFrame()
        return pd.DataFrame({"ts_code": ["A"], "report_date": [start_date],
                             "eps": [1.0], "op_rt": [1.0], "np": [1.0], "rating": ["buy"]})

    r.fetcher.pro = FakePro()
    r.fetcher._fetch_paginated = fake_paginated
    r.stage_e()
    assert any("report_rc" in k for k in r.failed), r.failed
    key = next(k for k in r.state if k.startswith("E:report_rc"))
    assert r.state[key]["status"] == "failed" and "ZERO-row month" in r.state[key]["error"], r.state[key]


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
