# -*- coding: utf-8 -*-
"""GPT sign-off HOLD MAJOR — fina_mainbz downstream dedup must key on bz_code.

The corrected fina_mainbz vendor_record_key (raw_recovery_coordinator.py) keys segment rows on the
OUTPUT column `bz_code` (P按产品 / D按地区 / I按行业). The auxiliary PIT ledger builder
(scripts/build_aux_pit_ledgers.py) previously deduplicated on (ts_code, end_date, bz_item) only, which
COLLAPSES two distinct breakdown rows whose `bz_item` text happens to match across P/D/I. This pins the
fix: with bz_code in the key the two rows survive; the old key would have merged them.
"""
import importlib.util
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location(
        "build_aux_pit_ledgers", ROOT / "scripts" / "build_aux_pit_ledgers.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["build_aux_pit_ledgers"] = mod
    spec.loader.exec_module(mod)
    return mod


def _two_rows_differing_only_by_bz_code():
    # identical (ts_code, end_date, bz_item) — differ ONLY in the breakdown dimension bz_code
    return pd.DataFrame({
        "ts_code": ["000001.SZ", "000001.SZ"],
        "end_date": ["20231231", "20231231"],
        "bz_item": ["综合", "综合"],       # SAME item label under two different breakdowns
        "bz_code": ["P", "I"],            # P按产品 vs I按行业 — distinct segment rows
        "ann_date": ["20240401", "20240401"],
        "bz_sales": [100.0, 250.0],
    })


def test_dedup_key_contains_bz_code():
    mod = _load()
    assert "bz_code" in mod.DEDUP_KEYS["fina_mainbz"], \
        "fina_mainbz dedup key must include bz_code (P/D/I breakdown identity)"


def test_bz_code_rows_are_not_collapsed_by_the_current_key():
    mod = _load()
    df = _two_rows_differing_only_by_bz_code()
    keys = mod.DEDUP_KEYS["fina_mainbz"]
    kept = df.sort_values("ann_date").drop_duplicates(subset=keys, keep="last")
    assert len(kept) == 2, "P and I breakdown rows must both survive under the corrected key"


def test_old_key_would_have_collapsed_them():
    # the pre-fix key — proves this is a real regression guard, not a tautology
    df = _two_rows_differing_only_by_bz_code()
    collapsed = df.sort_values("ann_date").drop_duplicates(
        subset=["ts_code", "end_date", "bz_item"], keep="last")
    assert len(collapsed) == 1
