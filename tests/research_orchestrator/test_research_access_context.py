"""PR 6 negative-test suite — ResearchAccessContext + qlib_windowed_features enforcement.

Covers:
  1. get_research_access_context() returns None outside any context.
  2. set/reset round-trips correctly.
  3. context manager set/reset works.
  4. validate_read passes inside the allowed window.
  5. HoldoutWindowViolation on start < allowed_start.
  6. HoldoutWindowViolation on end > allowed_end.
  7. HoldoutSealViolation when stage='oos_test' and not seal_claimed.
  8. FieldAccessViolation when fields ⊄ allowed_fields.
  9. allowed_fields=None means no field constraint.
  10. from_split correctly maps time_split→allowed window per stage.
  11. qlib_windowed_features with an active context validates reads.
  12. qlib_windowed_features with no context behaves unchanged.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from src.research_orchestrator.research_access_context import (
    FieldAccessViolation,
    HoldoutSealViolation,
    HoldoutWindowViolation,
    ResearchAccessContext,
    get_research_access_context,
    research_access_context,
    reset_research_access_context,
    set_research_access_context,
)


def _ctx(**overrides) -> ResearchAccessContext:
    base = dict(
        run_id="run_001",
        step_id="step_001",
        stage="is_only",
        design_hash="abc123",
        allowed_start=pd.Timestamp("2020-01-01"),
        allowed_end=pd.Timestamp("2022-12-31"),
        provider_build_id="prod_test",
        calendar_policy_id="frozen_20260227_system_build",
        holdout_seal_claimed=False,
    )
    base.update(overrides)
    return ResearchAccessContext(**base)


class TestContextvarPlumbing:
    def test_get_returns_none_by_default(self) -> None:
        # Importing the module above can leave context state from other tests;
        # explicitly reset for hygiene.
        token = set_research_access_context(None)
        try:
            assert get_research_access_context() is None
        finally:
            reset_research_access_context(token)

    def test_set_then_reset_roundtrip(self) -> None:
        ctx = _ctx()
        token = set_research_access_context(ctx)
        try:
            assert get_research_access_context() is ctx
        finally:
            reset_research_access_context(token)
        assert get_research_access_context() is None

    def test_context_manager_clears_on_exit(self) -> None:
        ctx = _ctx()
        with research_access_context(ctx) as yielded:
            assert yielded is ctx
            assert get_research_access_context() is ctx
        assert get_research_access_context() is None

    def test_context_manager_clears_on_exception(self) -> None:
        ctx = _ctx()
        with pytest.raises(RuntimeError, match="boom"):
            with research_access_context(ctx):
                assert get_research_access_context() is ctx
                raise RuntimeError("boom")
        assert get_research_access_context() is None

    def test_context_manager_with_none_is_noop(self) -> None:
        with research_access_context(None):
            assert get_research_access_context() is None


class TestValidateRead:
    def test_read_inside_window_passes(self) -> None:
        ctx = _ctx()
        # No exception
        ctx.validate_read(
            start_time="2020-02-01", end_time="2020-03-01", fields=["$close"],
        )

    def test_start_before_allowed_raises(self) -> None:
        ctx = _ctx()
        with pytest.raises(HoldoutWindowViolation, match="before allowed window"):
            ctx.validate_read(start_time="2019-12-31", end_time="2020-03-01")

    def test_end_after_allowed_raises(self) -> None:
        ctx = _ctx()
        with pytest.raises(HoldoutWindowViolation, match="after allowed window"):
            ctx.validate_read(start_time="2020-01-01", end_time="2023-01-01")

    def test_oos_without_seal_raises(self) -> None:
        ctx = _ctx(stage="oos_test", holdout_seal_claimed=False)
        with pytest.raises(HoldoutSealViolation, match="without"):
            ctx.validate_read(start_time="2020-02-01", end_time="2020-03-01")

    def test_oos_with_seal_passes(self) -> None:
        ctx = _ctx(stage="oos_test", holdout_seal_claimed=True)
        ctx.validate_read(start_time="2020-02-01", end_time="2020-03-01")

    def test_allowed_fields_constraint_blocks_unlisted(self) -> None:
        ctx = _ctx(allowed_fields=frozenset({"$close", "$open"}))
        with pytest.raises(FieldAccessViolation, match=r"\$pe_ttm"):
            ctx.validate_read(
                start_time="2020-02-01",
                end_time="2020-03-01",
                fields=["$close", "$pe_ttm"],
            )

    def test_allowed_fields_none_permits_all(self) -> None:
        ctx = _ctx(allowed_fields=None)
        # Should not raise on any field.
        ctx.validate_read(
            start_time="2020-02-01", end_time="2020-03-01",
            fields=["$close", "$pe_ttm", "$top_list__amount"],
        )

    def test_allowed_fields_exact_match_passes(self) -> None:
        ctx = _ctx(allowed_fields=frozenset({"$close", "$open"}))
        ctx.validate_read(
            start_time="2020-02-01", end_time="2020-03-01",
            fields=["$close"],
        )


class TestFromSplit:
    def test_oos_test_maps_to_oos_window(self) -> None:
        ctx = ResearchAccessContext.from_split(
            run_id="r", step_id="s", stage="oos_test", design_hash="h",
            time_split={"is_start": "2018-01-01", "is_end": "2022-12-31",
                        "oos_start": "2023-01-01", "oos_end": "2024-12-31"},
            provider_build_id="prod", calendar_policy_id="policy",
            holdout_seal_claimed=True,
        )
        assert ctx.allowed_start == pd.Timestamp("2023-01-01")
        assert ctx.allowed_end == pd.Timestamp("2024-12-31")

    def test_is_only_maps_to_is_window(self) -> None:
        ctx = ResearchAccessContext.from_split(
            run_id="r", step_id="s", stage="is_only", design_hash="h",
            time_split={"is_start": "2018-01-01", "is_end": "2022-12-31",
                        "oos_start": "2023-01-01", "oos_end": "2024-12-31"},
            provider_build_id="prod", calendar_policy_id="policy",
        )
        assert ctx.allowed_start == pd.Timestamp("2018-01-01")
        assert ctx.allowed_end == pd.Timestamp("2022-12-31")

    def test_missing_split_keys_raises(self) -> None:
        with pytest.raises(ValueError, match="time_split missing"):
            ResearchAccessContext.from_split(
                run_id="r", step_id="s", stage="oos_test", design_hash="h",
                time_split={},  # missing oos_start/oos_end
                provider_build_id="prod", calendar_policy_id="policy",
            )


class TestQlibWindowedFeaturesEnforcement:
    """qlib_windowed_features must invoke validate_read when context is active."""

    def test_no_context_skips_validation(self, tmp_path) -> None:
        # When no context is set, qlib_windowed_features behaves exactly as
        # before — it calls D.features and the cache manifest without
        # invoking ResearchAccessContext.validate_read.
        from src.research_orchestrator import qlib_windowed_features as qwf
        from src.research_orchestrator.cache_manifest import CacheContext

        mock_frame = pd.DataFrame({"$close": [1.0]}, index=pd.MultiIndex.from_tuples(
            [("000001_SZ", pd.Timestamp("2020-02-01"))],
            names=["instrument", "datetime"],
        ))
        with patch("qlib.data.D") as mock_d:
            mock_d.features.return_value = mock_frame
            # No context active — call should succeed without raising.
            qwf.qlib_windowed_features(
                instruments=["000001_SZ"],
                fields=["$close"],
                start_time="2020-02-01",
                end_time="2020-02-01",
                cache_context=CacheContext(),
                stage="is_only",
                # tmp dir, NOT the persistent data/_test_cache: rows recorded
                # there before the M4 provider-generation binding carry "" ids
                # and are (correctly) refused against the live ids.
                cache_manifest_dir=tmp_path / "manifest",
            )

    def test_window_violation_raises_before_d_features(self, tmp_path: Path) -> None:
        from src.research_orchestrator import qlib_windowed_features as qwf
        from src.research_orchestrator.cache_manifest import CacheContext

        ctx = _ctx()
        with patch("qlib.data.D") as mock_d:
            mock_d.features.side_effect = RuntimeError(
                "D.features should NOT be reached on a window violation"
            )
            with research_access_context(ctx):
                with pytest.raises(HoldoutWindowViolation):
                    qwf.qlib_windowed_features(
                        instruments=["000001_SZ"],
                        fields=["$close"],
                        start_time="2019-12-01",  # before allowed_start
                        end_time="2020-01-15",
                        cache_context=CacheContext(),
                        stage="is_only",
                        cache_manifest_dir=str(tmp_path),
                    )

    def test_oos_without_seal_raises_before_d_features(self, tmp_path: Path) -> None:
        from src.research_orchestrator import qlib_windowed_features as qwf
        from src.research_orchestrator.cache_manifest import CacheContext

        ctx = _ctx(stage="oos_test", holdout_seal_claimed=False)
        with patch("qlib.data.D") as mock_d:
            mock_d.features.side_effect = RuntimeError("should not reach")
            with research_access_context(ctx):
                with pytest.raises(HoldoutSealViolation):
                    qwf.qlib_windowed_features(
                        instruments=["000001_SZ"],
                        fields=["$close"],
                        start_time="2020-02-01",
                        end_time="2020-03-01",
                        cache_context=CacheContext(),
                        stage="oos_test",
                        cache_manifest_dir=str(tmp_path),
                    )

    def test_field_access_violation_raises(self, tmp_path: Path) -> None:
        from src.research_orchestrator import qlib_windowed_features as qwf
        from src.research_orchestrator.cache_manifest import CacheContext

        ctx = _ctx(allowed_fields=frozenset({"$close"}))
        with patch("qlib.data.D") as mock_d:
            mock_d.features.side_effect = RuntimeError("should not reach")
            with research_access_context(ctx):
                with pytest.raises(FieldAccessViolation, match=r"\$pe_ttm"):
                    qwf.qlib_windowed_features(
                        instruments=["000001_SZ"],
                        fields=["$close", "$pe_ttm"],
                        start_time="2020-02-01",
                        end_time="2020-03-01",
                        cache_context=CacheContext(),
                        stage="is_only",
                        cache_manifest_dir=str(tmp_path),
                    )

    def test_valid_read_with_context_proceeds(self, tmp_path: Path) -> None:
        from src.research_orchestrator import qlib_windowed_features as qwf
        from src.research_orchestrator.cache_manifest import CacheContext

        ctx = _ctx()
        mock_frame = pd.DataFrame(
            {"$close": [1.0]},
            index=pd.MultiIndex.from_tuples(
                [("000001_SZ", pd.Timestamp("2020-02-01"))],
                names=["instrument", "datetime"],
            ),
        )
        with patch("qlib.data.D") as mock_d:
            mock_d.features.return_value = mock_frame
            with research_access_context(ctx):
                out = qwf.qlib_windowed_features(
                    instruments=["000001_SZ"],
                    fields=["$close"],
                    start_time="2020-02-01",
                    end_time="2020-02-01",
                    cache_context=CacheContext(),
                    stage="is_only",
                    cache_manifest_dir=str(tmp_path),
                )
        assert not out.empty
