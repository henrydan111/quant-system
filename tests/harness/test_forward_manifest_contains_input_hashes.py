"""B7/B4: the forward manifest must pin EVERY input the decision depended on by
content hash — provider build, config, pool parquet, per-source text stores,
pull manifest, git commit — so any later dispute is resolvable byte-for-byte."""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

SCRIPT = (PROJECT_ROOT / "workspace" / "research" / "mvp_pool_book"
          / "run_forward_cycle.py")


@pytest.fixture(scope="module")
def fwd():
    spec = importlib.util.spec_from_file_location("run_forward_cycle_under_test2", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_manifest_contains_all_input_hashes(fwd, tmp_path):
    pool = tmp_path / "broker_recommend_202608.parquet"
    pd.DataFrame({"ts_code": ["000001.SZ"]}).to_parquet(pool, index=False)
    store = tmp_path / "text_anns_d.parquet"
    pd.DataFrame({"title": ["t"]}).to_parquet(store, index=False)

    decision_time = pd.Timestamp("2026-08-03 20:45:00")
    m = fwd.build_manifest(
        cycle="202608", decision_time=decision_time, config_hash="cfg123",
        git_commit="deadbeef", staleness_days=2,
        provider_manifest={"provider_build_id": "b1", "calendar_policy_id": "p1"},
        calendar_end="2026-08-01",
        pool_path=pool, text_store_paths={"anns_d": store},
        pull_manifest={"ok": True, "run_ts": "2026-08-03T20:35:00"})

    assert m["decision_id"] == fwd.compute_decision_id(
        "202608", decision_time.isoformat(), "cfg123", "deadbeef")
    assert m["provider_build_id"] == "b1" and m["calendar_policy_id"] == "p1"
    assert m["git_commit"] == "deadbeef" and m["config_hash"] == "cfg123"
    # content hashes are REAL sha256 of the files
    assert m["input_hashes"]["pool_parquet"]["sha256"] == hashlib.sha256(
        pool.read_bytes()).hexdigest()
    assert m["input_hashes"]["text_stores"]["anns_d"]["sha256"] == hashlib.sha256(
        store.read_bytes()).hexdigest()
    assert m["text_pull_manifest"]["ok"] is True
    assert m["strategy_version"] == "mvp_pool_rerank_v2"
