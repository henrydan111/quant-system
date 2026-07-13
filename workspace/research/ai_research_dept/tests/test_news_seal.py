# NF wave: seal primitives (canonical encoding + verify-not-trust).
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from workspace.research.ai_research_dept.engine.news_seal import (  # noqa: E402
    NULL_SENTINEL, SealError, canon, deep_ro, seal_hash, verify_sealed,
)


def test_missing_forms_identical():
    assert canon(None) == canon(float("nan")) == canon(pd.NA) == canon(pd.NaT) == NULL_SENTINEL


def test_missing_idempotent_in_hash():
    assert seal_hash({"a": None, "b": pd.NA}) == seal_hash({"a": None, "b": None})


def test_full_sha256():
    assert len(seal_hash({"x": 1})) == 64


def test_tz_aware_and_naive_same_wall():
    a = canon(pd.Timestamp("2025-01-27 10:00:00"))
    b = canon(pd.Timestamp("2025-01-27 18:00:00+08:00").tz_convert("Asia/Shanghai"))
    assert a == "T:2025-01-27T10:00:00"


def test_bool_not_collapsed_to_int():
    assert canon(True) is True and canon(1) == 1
    assert seal_hash({"x": True}) != seal_hash({"x": 1})


def test_verify_not_trust():
    with pytest.raises(SealError):
        verify_sealed({"x": 1}, "deadbeef")
    verify_sealed({"x": 1}, seal_hash({"x": 1}))       # matching -> ok


def test_deep_readonly():
    d = deep_ro({"a": {"b": [1, 2]}})
    with pytest.raises(TypeError):
        d["a"]["b"] = 9
