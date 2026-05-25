"""Discovery-profile regression for the Part B selective relax of
``CacheManifestStore.assert_cache_reusable`` (plan
``snappy-buzzing-meerkat`` v5).

Two different design_hashes loading the SAME ``qlib_features`` cache_key
must BOTH pass without raising; mismatches on stage or window must STILL
raise; non-``qlib_features`` cache_types must STILL enforce design_hash
strictly so the generic guardrail is not weakened.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.research_orchestrator.cache_manifest import (
    CacheContext,
    CacheKeyMismatchError,
    CacheManifestStore,
)


CACHE_KEY = "qlib::day::deadbeefcafefeed"
WINDOW_START = "2021-01-04"
WINDOW_END = "2021-01-08"


def _seed_row(manifest_dir: Path, *, cache_type: str, design_hash: str,
              stage: str = "is_only",
              window_start: str = WINDOW_START,
              window_end: str = WINDOW_END) -> CacheManifestStore:
    manifest = CacheManifestStore(manifest_dir)
    manifest.record_cache_write(
        cache_type=cache_type,
        cache_key=CACHE_KEY,
        cache_path=CACHE_KEY,
        cache_context=CacheContext(design_hash=design_hash),
        stage=stage,
        window_start=window_start,
        window_end=window_end,
    )
    return manifest


def test_qlib_features_design_hash_mismatch_does_not_raise(tmp_path: Path):
    """Discovery profile (theme_strategy / event_driven_signal_research) and
    formal validation each load raw OHLCV under different design_hashes.
    Part B says both must succeed under cache_type='qlib_features'.
    """
    manifest = _seed_row(tmp_path, cache_type="qlib_features", design_hash="hyp_A")
    # Should NOT raise even though design_hash differs.
    manifest.assert_cache_reusable(
        cache_key=CACHE_KEY,
        cache_path=CACHE_KEY,
        cache_context=CacheContext(design_hash="hyp_B"),
        stage="is_only",
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        cache_type="qlib_features",
    )


def test_qlib_features_stage_mismatch_still_raises(tmp_path: Path):
    """Stage is NOT relaxed by Part B — IS row vs OOS read must trip."""
    manifest = _seed_row(
        tmp_path, cache_type="qlib_features", design_hash="hyp_A", stage="is_only",
    )
    with pytest.raises(CacheKeyMismatchError, match="stage"):
        manifest.assert_cache_reusable(
            cache_key=CACHE_KEY,
            cache_path=CACHE_KEY,
            cache_context=CacheContext(design_hash="hyp_A"),
            stage="oos_test",
            window_start=WINDOW_START,
            window_end=WINDOW_END,
            cache_type="qlib_features",
        )


def test_qlib_features_window_mismatch_still_raises(tmp_path: Path):
    """Window is NOT relaxed by Part B."""
    manifest = _seed_row(
        tmp_path, cache_type="qlib_features", design_hash="hyp_A",
    )
    with pytest.raises(CacheKeyMismatchError, match="window"):
        manifest.assert_cache_reusable(
            cache_key=CACHE_KEY,
            cache_path=CACHE_KEY,
            cache_context=CacheContext(design_hash="hyp_A"),
            stage="is_only",
            window_start="2022-01-04",
            window_end="2022-01-08",
            cache_type="qlib_features",
        )


def test_other_cache_type_design_hash_mismatch_still_raises(tmp_path: Path):
    """Generic guardrail intact: non-qlib_features cache_types preserve the
    legacy design_hash isolation. This protects future hypothesis-isolated
    caches (factor-screening intermediates, ML model checkpoints, etc.).
    """
    manifest = _seed_row(
        tmp_path, cache_type="ml_model_checkpoint", design_hash="hyp_A",
    )
    with pytest.raises(CacheKeyMismatchError, match="design_hash"):
        manifest.assert_cache_reusable(
            cache_key=CACHE_KEY,
            cache_path=CACHE_KEY,
            cache_context=CacheContext(design_hash="hyp_B"),
            stage="is_only",
            window_start=WINDOW_START,
            window_end=WINDOW_END,
            cache_type="ml_model_checkpoint",
        )


def test_default_cache_type_preserves_design_hash_check(tmp_path: Path):
    """Backward compatibility: callers that omit cache_type still get the
    legacy strict design_hash check.
    """
    manifest = _seed_row(
        tmp_path, cache_type="some_legacy_type", design_hash="hyp_A",
    )
    with pytest.raises(CacheKeyMismatchError, match="design_hash"):
        manifest.assert_cache_reusable(
            cache_key=CACHE_KEY,
            cache_path=CACHE_KEY,
            cache_context=CacheContext(design_hash="hyp_B"),
            stage="is_only",
            window_start=WINDOW_START,
            window_end=WINDOW_END,
            # cache_type omitted → defaults to "" → strict path
        )


def test_qlib_features_audit_trail_records_both_hypotheses(tmp_path: Path):
    """After Part B, BOTH design_hashes must appear in the manifest log
    after consecutive writes — audit trail intact.
    """
    manifest = CacheManifestStore(tmp_path)
    manifest.record_cache_write(
        cache_type="qlib_features",
        cache_key=CACHE_KEY,
        cache_path=CACHE_KEY,
        cache_context=CacheContext(design_hash="hyp_A"),
        stage="is_only",
        window_start=WINDOW_START,
        window_end=WINDOW_END,
    )
    manifest.record_cache_write(
        cache_type="qlib_features",
        cache_key=CACHE_KEY,
        cache_path=CACHE_KEY,
        cache_context=CacheContext(design_hash="hyp_B"),
        stage="is_only",
        window_start=WINDOW_START,
        window_end=WINDOW_END,
    )

    rows = manifest.list_events(cache_key=CACHE_KEY)
    assert len(rows) == 2
    assert set(rows["design_hash"].tolist()) == {"hyp_A", "hyp_B"}
