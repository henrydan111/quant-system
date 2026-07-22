# -*- coding: utf-8 -*-
"""The canonical 3-leg daily merge is ONE function shared by the production pipeline and the raw-store
recovery (adapter design v4, F9 rider).

Two implementations of the same merge is the shape that lets recovered history and live history drift
apart silently — and they HAD drifted: each side carried a check the other lacked. These tests pin the
union so neither caller can regress to being the weaker one.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT / "src"), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from data_infra.daily_merge import DailyMergeError, merge_daily_legs  # noqa: E402

DATE = "20260702"


def _legs(*, basic_payload_null: bool = False, n: int = 10):
    codes = [f"{i:06d}.SZ" for i in range(n)]
    daily = pd.DataFrame({"ts_code": codes, "trade_date": [DATE] * n,
                          "open": 10.0, "high": 11.0, "low": 9.0, "close": 10.5,
                          "vol": 1000.0, "amount": 10500.0})
    basic = pd.DataFrame({"ts_code": codes, "trade_date": [DATE] * n,
                          "close": 10.5,                      # auxiliary copy — must be dropped
                          "turnover_rate": [None] * n if basic_payload_null else [1.5] * n,
                          "pe": [None] * n if basic_payload_null else [12.0] * n})
    adj = pd.DataFrame({"ts_code": codes, "trade_date": [DATE] * n, "adj_factor": [1.25] * n})
    return daily, basic, adj


def test_happy_path_merges_and_keeps_the_canonical_close():
    daily, basic, adj = _legs()
    out = merge_daily_legs(daily, basic, adj, DATE)
    assert len(out) == len(daily)
    assert out["close"].eq(10.5).all()                 # daily's close, not shadowed by the aux copy
    assert "close_x" not in out.columns and "close_y" not in out.columns
    assert out["adj_factor"].notna().all()
    assert out["turnover_rate"].notna().all()


def test_daily_basic_present_but_all_payload_null_is_REFUSED():
    """THE GAP the consolidation found. The recovery merger checked daily_basic CODE coverage, which a
    degenerate response with the right keys and empty values passes at 100% — so an all-NULL
    daily_basic would have been written into the recovered store. Production had the post-merge payload
    check; recovery did not. Now both do."""
    daily, basic, adj = _legs(basic_payload_null=True)
    with pytest.raises(DailyMergeError, match="payload coverage"):
        merge_daily_legs(daily, basic, adj, DATE)


def test_duplicate_aux_keys_are_refused_not_row_multiplied():
    """`validate='one_to_one'` — production's plain merge would have silently DUPLICATED base rows."""
    daily, basic, adj = _legs()
    basic = pd.concat([basic, basic.iloc[[0]]], ignore_index=True)
    with pytest.raises(Exception):                     # pandas MergeError or DailyMergeError
        merge_daily_legs(daily, basic, adj, DATE)


def test_a_leg_carrying_another_date_is_refused():
    daily, basic, adj = _legs()
    basic.loc[0, "trade_date"] = "20260701"
    with pytest.raises(DailyMergeError, match="ANOTHER date"):
        merge_daily_legs(daily, basic, adj, DATE)


def test_missing_positive_adj_factor_is_refused():
    daily, basic, adj = _legs()
    adj.loc[0, "adj_factor"] = 0.0
    with pytest.raises(DailyMergeError, match="positive adj_factor"):
        merge_daily_legs(daily, basic, adj, DATE)


@pytest.mark.parametrize("leg", ["daily", "daily_basic", "adj_factor"])
def test_every_leg_is_required(leg):
    daily, basic, adj = _legs()
    frames = {"daily": daily, "daily_basic": basic, "adj_factor": adj}
    frames[leg] = frames[leg].iloc[0:0]
    with pytest.raises(DailyMergeError):
        merge_daily_legs(frames["daily"], frames["daily_basic"], frames["adj_factor"], DATE)


def test_both_callers_use_the_SAME_function_object():
    """Not 'both have a merge' — the same callable. A copy would drift again."""
    import recovery_adapters as ra
    import data_infra.daily_merge as canonical

    calls = {}
    real = canonical.merge_daily_legs

    def _spy(*a, **kw):
        calls["hit"] = True
        return real(*a, **kw)

    canonical.merge_daily_legs = _spy
    try:
        daily, basic, adj = _legs()
        ra.merge_daily_legs(daily, basic, adj, DATE)     # the recovery entry point
    finally:
        canonical.merge_daily_legs = real
    assert calls.get("hit"), "recovery_adapters.merge_daily_legs did not delegate to the canonical one"

    src = (ROOT / "src" / "data_infra" / "pipeline" / "update_daily_data.py").read_text(encoding="utf-8")
    assert "from data_infra.daily_merge import" in src, "the production pipeline lost the shared import"
    assert "merge_daily_legs(df_daily, df_basic, df_adj, target_date)" in src
    # and it must not have grown its own merge back
    assert "pd.merge(df_merged" not in src, "update_daily_data re-introduced an inline merge"


def test_the_shared_merger_is_in_the_recovery_bundle_hash():
    """It decides what a recovered market/daily file CONTAINS, so editing it must invalidate the frozen
    plan exactly like editing a recipe does."""
    import recovery_adapters as ra
    assert "src/data_infra/daily_merge.py" in ra._BUNDLE_FILES
    assert "src/data_infra/daily_merge.py" in ra.compute_bundle_manifest()["files"]
