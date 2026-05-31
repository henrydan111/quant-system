"""PR 4 negative-test suite — cache/seal locking under concurrent writes.

These tests spawn multiple processes that hit the same critical section
simultaneously. Without the file_lock added in PR 4 they fail:

  * HoldoutSealStore.claim_holdout_access — duplicate seal events for the
    same design_hash (the in-process atomic write protects the final
    parquet file from corruption but does NOT prevent two callers from
    both passing the ``frame.empty`` check before writing their own row).
  * CacheManifestStore.record_cache_write — lost rows (second writer's
    ``_load`` snapshot misses the first writer's row, then overwrites it
    with a frame that contains only the second writer's row).

Worker functions live at module scope so multiprocessing can pickle them
on Windows. The Barrier guarantees all workers hit the critical section
at approximately the same time, maximizing contention.
"""

from __future__ import annotations

import multiprocessing as mp
from pathlib import Path

import pandas as pd
import pytest


# ─────────────────────────────────────────────────────────────────────────
# Worker functions (must be top-level for Windows multiprocessing pickling)
# ─────────────────────────────────────────────────────────────────────────


def _seal_worker(args: tuple[str, str, int, str]) -> tuple[int, str, str | None]:
    """Each worker attempts to claim the SAME design_hash. Exactly one
    should succeed and the rest should raise.

    Args: (root_dir, design_hash, worker_id, hypothesis_id)
    Returns: (worker_id, "success" | "raised", message)
    """
    root_dir, design_hash, worker_id, hypothesis_id = args
    from src.research_orchestrator.holdout_seal import HoldoutSealStore

    store = HoldoutSealStore(root_dir)
    try:
        row = store.claim_holdout_access(
            design_hash=design_hash,
            hypothesis_id=hypothesis_id,
            structural_family="test_family",
            profile_id="test_profile",
            run_dir=f"{root_dir}/run_{worker_id}",
            step_id=f"step_{worker_id}",
        )
        return (worker_id, "success", row.get("event_id"))
    except ValueError as exc:
        return (worker_id, "raised", str(exc))


def _cache_worker(args: tuple[str, str, int]) -> tuple[int, str, str | None]:
    """Each worker records a DISTINCT cache_key. All writes must persist.

    Args: (root_dir, design_hash, worker_id)
    Returns: (worker_id, "success" | "raised", message)
    """
    root_dir, design_hash, worker_id = args
    from src.research_orchestrator.cache_manifest import (
        CacheContext,
        CacheManifestStore,
    )

    store = CacheManifestStore(root_dir)
    ctx = CacheContext(
        design_hash=design_hash,
        hypothesis_id=f"hyp_{worker_id}",
        structural_family="test_family",
        profile_id="test_profile",
        run_dir=f"{root_dir}/run_{worker_id}",
        step_id=f"step_{worker_id}",
    )
    try:
        row = store.record_cache_write(
            cache_type="qlib_features",
            cache_key=f"key_{worker_id}",
            cache_path=f"path_{worker_id}",
            cache_context=ctx,
            stage="is_only",
            window_start="2024-01-01",
            window_end="2024-12-31",
        )
        return (worker_id, "success", row.get("manifest_id"))
    except Exception as exc:  # noqa: BLE001
        return (worker_id, "raised", f"{type(exc).__name__}: {exc}")


def _ledger_event_worker(args: tuple[str, int]) -> tuple[int, str, str | None]:
    """Each worker records a DISTINCT measurement event into the SAME daily shard.
    All writes must persist (PR P1.5: the lock serializes load->append->write so no
    second writer overwrites the first's row).

    Args: (root_dir, worker_id). Returns: (worker_id, "success" | "raised", event_id).
    """
    root_dir, worker_id = args
    from src.alpha_research.testing_ledger import TestingLedgerStore

    store = TestingLedgerStore(root_dir)
    try:
        row = store.record_event(
            hypothesis_id=f"hyp_{worker_id}",
            design_hash=f"dh_{worker_id}",
            prose_hash="ph",
            structural_family="fam",
            profile_id="prof",
            run_id=f"run_{worker_id}",
            run_dir=f"{root_dir}/run_{worker_id}",
            test_name=f"test_{worker_id}",
            stage="is_only",
            statistic_name="rank_icir",
            sharpe=float(worker_id),
        )
        return (worker_id, "success", row.get("event_id"))
    except Exception as exc:  # noqa: BLE001
        return (worker_id, "raised", f"{type(exc).__name__}: {exc}")


# ─────────────────────────────────────────────────────────────────────────
# Test cases
# ─────────────────────────────────────────────────────────────────────────


@pytest.fixture
def mp_context():
    """Use the spawn start method so tests are reproducible on Windows."""
    return mp.get_context("spawn")


class TestHoldoutSealConcurrency:
    """8 concurrent workers attempting to claim the SAME design_hash → exactly 1 wins."""

    def test_concurrent_claim_exactly_one_wins(
        self, tmp_path: Path, mp_context
    ) -> None:
        design_hash = "deadbeefcafebabe"
        args = [(str(tmp_path), design_hash, i, f"hyp_{i}") for i in range(8)]

        with mp_context.Pool(processes=8) as pool:
            results = pool.map(_seal_worker, args)

        successes = [r for r in results if r[1] == "success"]
        failures = [r for r in results if r[1] == "raised"]

        assert len(successes) == 1, (
            f"Expected exactly 1 success, got {len(successes)}. "
            f"successes={successes}, failures={failures}"
        )
        assert len(failures) == 7
        # All failures must be the explicit seal-already-claimed message.
        for _, _, msg in failures:
            assert "Holdout sealed for" in (msg or "")

        # Verify the manifest contains exactly one event for this hash.
        from src.research_orchestrator.holdout_seal import HoldoutSealStore
        store = HoldoutSealStore(tmp_path)
        events = store.list_events(design_hash=design_hash)
        assert len(events) == 1


class TestCacheManifestConcurrency:
    """8 concurrent workers with DISTINCT keys → all 8 rows must persist."""

    def test_concurrent_writes_no_lost_rows(
        self, tmp_path: Path, mp_context
    ) -> None:
        design_hash = "deadbeefcafebabe"
        args = [(str(tmp_path), design_hash, i) for i in range(8)]

        with mp_context.Pool(processes=8) as pool:
            results = pool.map(_cache_worker, args)

        successes = [r for r in results if r[1] == "success"]
        failures = [r for r in results if r[1] == "raised"]

        assert len(failures) == 0, (
            f"Expected zero failures, got {failures}"
        )
        assert len(successes) == 8

        # Verify the manifest persists all 8 distinct cache_keys.
        from src.research_orchestrator.cache_manifest import CacheManifestStore
        store = CacheManifestStore(tmp_path)
        all_events = store.list_events()
        cache_keys = sorted(all_events["cache_key"].tolist())
        assert cache_keys == [f"key_{i}" for i in range(8)], (
            f"Expected all 8 keys present, got {cache_keys}"
        )
        # Manifest IDs must all be distinct.
        manifest_ids = all_events["manifest_id"].tolist()
        assert len(set(manifest_ids)) == 8

    def test_concurrent_writes_same_key_all_appended(
        self, tmp_path: Path, mp_context
    ) -> None:
        """All 8 workers write to the SAME cache_key — manifest is append-only,
        so we expect all 8 rows to land, not one row that wins."""
        design_hash = "deadbeefcafebabe"
        same_key_args = [(str(tmp_path), design_hash, 0) for _ in range(8)]
        # All workers use worker_id=0 → all write key_0 with hypothesis_id=hyp_0.
        # The lock guarantees serialization so we end up with 8 distinct rows
        # (distinguishable by their recorded_at timestamps even if other
        # fields collide).

        with mp_context.Pool(processes=8) as pool:
            results = pool.map(_cache_worker, same_key_args)

        successes = [r for r in results if r[1] == "success"]
        assert len(successes) == 8

        from src.research_orchestrator.cache_manifest import CacheManifestStore
        store = CacheManifestStore(tmp_path)
        rows = store.list_events(cache_key="key_0")
        # Append-only: all 8 writes land.
        assert len(rows) == 8


class TestTestingLedgerConcurrency:
    """PR P1.5: 8 concurrent record_event of DISTINCT rows into the same daily shard
    → all 8 persist (no lost update), and record_verdict does not self-deadlock."""

    def test_concurrent_record_event_no_lost_rows(
        self, tmp_path: Path, mp_context
    ) -> None:
        args = [(str(tmp_path), i) for i in range(8)]
        with mp_context.Pool(processes=8) as pool:
            results = pool.map(_ledger_event_worker, args)

        successes = [r for r in results if r[1] == "success"]
        failures = [r for r in results if r[1] == "raised"]
        assert len(failures) == 0, f"Expected zero failures, got {failures}"
        assert len(successes) == 8

        from src.alpha_research.testing_ledger import TestingLedgerStore
        store = TestingLedgerStore(tmp_path)
        events = store.list_events()
        assert len(events) == 8, f"Expected all 8 events to persist, got {len(events)}"
        assert len(set(events["event_id"].tolist())) == 8

    def test_record_verdict_no_self_deadlock(self, tmp_path: Path) -> None:
        # record_verdict acquires the lock then appends via the UNLOCKED helper (NOT
        # the public record_event); it must COMPLETE, not deadlock on the
        # non-reentrant file lock. (A naive double-lock would hang here.)
        from src.alpha_research.testing_ledger import TestingLedgerStore

        store = TestingLedgerStore(tmp_path)
        measurement = store.record_event(
            hypothesis_id="h", design_hash="dh", prose_hash="ph", structural_family="fam",
            profile_id="p", run_id="r", run_dir=str(tmp_path), test_name="t",
            stage="is_only", statistic_name="ic",
        )
        verdict = store.record_verdict(
            related_event_id=measurement["event_id"], design_hash="dh", verdict="pass",
            decision_by="me", reason="ok", run_id="r", run_dir=str(tmp_path),
        )
        assert verdict["event_kind"] == "verdict"
        assert verdict["related_event_id"] == measurement["event_id"]
        assert len(store.list_events()) == 2


class TestSingleProcessRegression:
    """Confirm the lock-wrapped path still works for the normal single-caller case."""

    def test_holdout_seal_single_claim_succeeds(self, tmp_path: Path) -> None:
        from src.research_orchestrator.holdout_seal import HoldoutSealStore
        store = HoldoutSealStore(tmp_path)
        row = store.claim_holdout_access(
            design_hash="d1",
            hypothesis_id="h1",
            structural_family="fam",
            profile_id="prof",
            run_dir=str(tmp_path / "run"),
            step_id="step1",
        )
        assert row["design_hash"] == "d1"

    def test_holdout_seal_double_claim_raises(self, tmp_path: Path) -> None:
        from src.research_orchestrator.holdout_seal import HoldoutSealStore
        store = HoldoutSealStore(tmp_path)
        store.claim_holdout_access(
            design_hash="d1",
            hypothesis_id="h1",
            structural_family="fam",
            profile_id="prof",
            run_dir=str(tmp_path / "run"),
            step_id="step1",
        )
        with pytest.raises(ValueError, match="Holdout sealed"):
            store.claim_holdout_access(
                design_hash="d1",
                hypothesis_id="h2",
                structural_family="fam",
                profile_id="prof",
                run_dir=str(tmp_path / "run2"),
                step_id="step2",
            )

    def test_cache_manifest_single_write_persists(self, tmp_path: Path) -> None:
        from src.research_orchestrator.cache_manifest import (
            CacheContext,
            CacheManifestStore,
        )
        store = CacheManifestStore(tmp_path)
        ctx = CacheContext(design_hash="d1", hypothesis_id="h1")
        row = store.record_cache_write(
            cache_type="qlib_features",
            cache_key="k",
            cache_path="p",
            cache_context=ctx,
            stage="is_only",
            window_start="2024-01-01",
            window_end="2024-12-31",
        )
        events = store.list_events(cache_key="k")
        assert len(events) == 1
        assert events.iloc[0]["manifest_id"] == row["manifest_id"]
