"""B7/B4: forward cycle outputs are APPEND-ONLY — an existing cycle dir refuses
the run; publication is one atomic rename; a decision can never be silently
overwritten or re-made under the same cycle id."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

SCRIPT = (PROJECT_ROOT / "workspace" / "research" / "mvp_pool_book"
          / "run_forward_cycle.py")


@pytest.fixture(scope="module")
def fwd():
    spec = importlib.util.spec_from_file_location("run_forward_cycle_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_existing_cycle_dir_refused(fwd, tmp_path):
    (tmp_path / "202608").mkdir()
    with pytest.raises(fwd.ForwardGateError, match="append-only"):
        fwd.ensure_cycle_dir_free(tmp_path, "202608")


def test_fresh_cycle_dir_allowed_and_publish_is_atomic(fwd, tmp_path):
    final = fwd.ensure_cycle_dir_free(tmp_path, "202609")
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "decision.json").write_text("{}", encoding="utf-8")
    fwd.atomic_publish(staging, final)
    assert (final / "decision.json").exists()
    assert not staging.exists()                       # renamed, not copied


def test_publish_refuses_if_final_appeared_meanwhile(fwd, tmp_path):
    final = tmp_path / "202610"
    staging = tmp_path / "staging2"
    staging.mkdir()
    final.mkdir()                                     # concurrent publisher won
    with pytest.raises(fwd.ForwardGateError):
        fwd.atomic_publish(staging, final)


def test_decision_id_derivation_is_pinned(fwd):
    a = fwd.compute_decision_id("202608", "2026-08-03T20:45:00", "abcd1234", "deadbeef")
    b = fwd.compute_decision_id("202608", "2026-08-03T20:45:00", "abcd1234", "deadbeef")
    c = fwd.compute_decision_id("202608", "2026-08-03T20:45:01", "abcd1234", "deadbeef")
    assert a == b and a != c and len(a) == 16
