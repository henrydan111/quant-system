"""Discovery-profile regression for the Part B selective relax of
``CacheManifestStore.assert_cache_reusable`` (plan
``snappy-buzzing-meerkat`` v5).

Two different design_hashes loading the SAME ``qlib_features`` cache_key
must BOTH pass without raising; mismatches on stage or window must STILL
raise; non-``qlib_features`` cache_types must STILL enforce design_hash
strictly so the generic guardrail is not weakened.

R4-M4 (calendar unfreeze): every call now carries the REQUIRED non-blank
provider-generation ids.
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
BUILD_ID = "test_build"
POLICY_ID = "test_policy"
GEN = {"provider_build_id": BUILD_ID, "calendar_policy_id": POLICY_ID}


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
        **GEN,
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
        **GEN,
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
            **GEN,
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
            **GEN,
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
            **GEN,
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
            **GEN,
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
        **GEN,
    )
    manifest.record_cache_write(
        cache_type="qlib_features",
        cache_key=CACHE_KEY,
        cache_path=CACHE_KEY,
        cache_context=CacheContext(design_hash="hyp_B"),
        stage="is_only",
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        **GEN,
    )

    rows = manifest.list_events(cache_key=CACHE_KEY)
    assert len(rows) == 2
    assert set(rows["design_hash"].tolist()) == {"hyp_A", "hyp_B"}


class TestGenerationBindingFailClosed:
    """R4-M4/M5: blank generation ids fail closed; cross-generation reuse refused."""

    def test_record_with_blank_ids_fails(self, tmp_path: Path):
        manifest = CacheManifestStore(tmp_path)
        for bad in ("", "   "):
            with pytest.raises(CacheKeyMismatchError, match="non-blank provider_build_id"):
                manifest.record_cache_write(
                    cache_type="qlib_features", cache_key=CACHE_KEY, cache_path=CACHE_KEY,
                    cache_context=CacheContext(design_hash="h"), stage="is_only",
                    window_start=WINDOW_START, window_end=WINDOW_END,
                    provider_build_id=bad, calendar_policy_id=POLICY_ID,
                )

    def test_assert_with_blank_ids_fails(self, tmp_path: Path):
        manifest = _seed_row(tmp_path, cache_type="qlib_features", design_hash="h")
        with pytest.raises(CacheKeyMismatchError, match="non-blank calendar_policy_id"):
            manifest.assert_cache_reusable(
                cache_key=CACHE_KEY, cache_path=CACHE_KEY,
                cache_context=CacheContext(design_hash="h"), stage="is_only",
                window_start=WINDOW_START, window_end=WINDOW_END,
                cache_type="qlib_features",
                provider_build_id=BUILD_ID, calendar_policy_id="",
            )

    def test_cross_generation_reuse_refused(self, tmp_path: Path):
        manifest = _seed_row(tmp_path, cache_type="qlib_features", design_hash="h")
        with pytest.raises(CacheKeyMismatchError, match="provider rotation"):
            manifest.assert_cache_reusable(
                cache_key=CACHE_KEY, cache_path=CACHE_KEY,
                cache_context=CacheContext(design_hash="h"), stage="is_only",
                window_start=WINDOW_START, window_end=WINDOW_END,
                cache_type="qlib_features",
                provider_build_id="rotated_build", calendar_policy_id=POLICY_ID,
            )

    def test_legacy_blank_row_refused_against_real_ids(self, tmp_path: Path):
        # Simulate a pre-binding legacy row by writing the parquet directly.
        manifest = _seed_row(tmp_path, cache_type="qlib_features", design_hash="h")
        import pandas as pd

        frame = pd.read_parquet(manifest.log_path)
        frame["provider_build_id"] = ""
        frame["calendar_policy_id"] = ""
        frame.to_parquet(manifest.log_path, index=False)
        with pytest.raises(CacheKeyMismatchError, match="provider rotation"):
            manifest.assert_cache_reusable(
                cache_key=CACHE_KEY, cache_path=CACHE_KEY,
                cache_context=CacheContext(design_hash="h"), stage="is_only",
                window_start=WINDOW_START, window_end=WINDOW_END,
                cache_type="qlib_features", **GEN,
            )
