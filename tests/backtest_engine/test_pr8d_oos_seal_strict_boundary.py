"""PR 8d negative-test suite — OOS seal claim + strict-cache boundary fixup.

Covers each of the 2 blockers GPT 5.5 Pro flagged in the PR 8c review:

  Blocker 1 — handle_validation_event_backtest_oos must claim the holdout
              seal BEFORE invoking run_event_driven_window. Without this
              the EventDrivenBacktester OOS backstop refuses the run.
  Blocker 2 — the strict_cache_only try/finally must wrap benchmark load +
              warmup + strategy.initialize as well, not just the day loop.
              Pre-PR-8d an exception inside initialize leaked strict mode.

Plus the medium fix:

  Medium 1 — daily-QA test now exercises scripts.run_daily_qa.
             _provider_manifest_check() against a temp Qlib layout, not
             just the underlying validator helper.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


# ─────────────────────────────────────────────────────────────────────────
# Blocker 1: OOS handler claims seal before invoking run_event_driven_window
# ─────────────────────────────────────────────────────────────────────────


class TestBlocker1OOSHandlerClaimsSeal:
    def test_oos_handler_source_calls_claim_holdout_access_if_needed(self) -> None:
        """Source-reflection: the OOS handler body must reference
        _claim_holdout_access_if_needed BEFORE the run_event_driven_window
        call. This is the most reliable check: a full mock-driven
        invocation of the handler requires a real StepExecutionContext
        with hypothesis + prescription + step_dir which is heavy to set up.
        """
        src = Path("src/research_orchestrator/validation_steps.py").read_text(
            encoding="utf-8"
        )
        oos_start = src.index("def handle_validation_event_backtest_oos")
        next_def_idx = src.find(
            "\ndef handle_validation_performance_diagnostics", oos_start,
        )
        oos_body = src[oos_start:next_def_idx if next_def_idx > 0 else len(src)]

        claim_idx = oos_body.find("_claim_holdout_access_if_needed(context)")
        run_idx = oos_body.find("run_event_driven_window")
        assert claim_idx > 0, (
            "OOS handler missing _claim_holdout_access_if_needed(context). "
            "Without this, the EventDrivenBacktester OOS backstop refuses the run."
        )
        # The first reference to run_event_driven_window is the import; the
        # actual invocation comes later. Find both occurrences.
        first_run = oos_body.find("run_event_driven_window")
        second_run = oos_body.find("run_event_driven_window", first_run + 1)
        # Whichever occurrence is the invocation — claim must precede it.
        invocation_idx = second_run if second_run > 0 else first_run
        assert claim_idx < invocation_idx, (
            "_claim_holdout_access_if_needed must be called BEFORE "
            "run_event_driven_window in the OOS handler body."
        )

    def test_oos_handler_import_includes_claim_helper(self) -> None:
        """The handler must import _claim_holdout_access_if_needed."""
        src = Path("src/research_orchestrator/validation_steps.py").read_text(
            encoding="utf-8"
        )
        oos_start = src.index("def handle_validation_event_backtest_oos")
        next_def_idx = src.find(
            "\ndef handle_validation_performance_diagnostics", oos_start,
        )
        oos_body = src[oos_start:next_def_idx if next_def_idx > 0 else len(src)]
        assert "_claim_holdout_access_if_needed" in oos_body, (
            "OOS handler must import _claim_holdout_access_if_needed from steps."
        )

    def test_claim_helper_uses_matching_identifiers(self) -> None:
        """The _claim_holdout_access_if_needed helper must use
        design_hash + run_dir + step_id identifiers that the
        EventDrivenBacktester OOS backstop later checks against."""
        src = Path("src/research_orchestrator/steps.py").read_text(encoding="utf-8")
        helper_idx = src.index("def _claim_holdout_access_if_needed")
        # Find the function body up to the next def.
        next_def = src.find("\ndef ", helper_idx + 1)
        helper_body = src[helper_idx:next_def if next_def > 0 else len(src)]
        # The helper must claim with design_hash, run_dir, step_id.
        for needle in (
            "design_hash=hypothesis.design_hash()",
            "run_dir=str(context.run_dir)",
            "step_id=context.step.step_id",
        ):
            assert needle in helper_body, (
                f"_claim_holdout_access_if_needed missing {needle!r} — "
                "EventDrivenBacktester OOS backstop matches on these exact "
                "fields so the helper must use them."
            )

    def test_claim_helper_only_fires_for_oos_stage(self) -> None:
        """The helper must short-circuit for non-OOS stages so non-OOS
        runs are not blocked by a seal contract."""
        src = Path("src/research_orchestrator/steps.py").read_text(encoding="utf-8")
        helper_idx = src.index("def _claim_holdout_access_if_needed")
        next_def = src.find("\ndef ", helper_idx + 1)
        helper_body = src[helper_idx:next_def if next_def > 0 else len(src)]
        assert '_gate_stage(context) != "oos_test"' in helper_body, (
            "_claim_holdout_access_if_needed must check stage == oos_test "
            "before claiming the seal."
        )


# ─────────────────────────────────────────────────────────────────────────
# Blocker 2: strict_cache_only try/finally covers warmup + initialize
# ─────────────────────────────────────────────────────────────────────────


class TestBlocker2StrictModeTryFinallyScope:
    def test_engine_try_block_includes_benchmark_load(self) -> None:
        """The try: in BacktestEngine.run must start BEFORE the benchmark
        load, so an exception during _load_benchmark restores strict_cache_only.
        """
        src = Path("src/backtest_engine/event_driven/engine.py").read_text(
            encoding="utf-8"
        )
        try_idx = src.index("try:", src.index("set_strict_cache_only(True)"))
        bench_idx = src.index("self._benchmark_returns = self._load_benchmark(")
        finally_idx = src.index("finally:", try_idx)
        assert try_idx < bench_idx < finally_idx, (
            "try: must wrap the _load_benchmark call so a benchmark-load "
            "exception triggers strict_cache_only restoration."
        )

    def test_engine_try_block_includes_warmup_fetch(self) -> None:
        src = Path("src/backtest_engine/event_driven/engine.py").read_text(
            encoding="utf-8"
        )
        try_idx = src.index("try:", src.index("set_strict_cache_only(True)"))
        warmup_idx = src.index("self._fetch_day_data(prev_date)", try_idx)
        finally_idx = src.index("finally:", try_idx)
        assert try_idx < warmup_idx < finally_idx, (
            "try: must wrap the warmup _fetch_day_data(prev_date) call so a "
            "warmup-time PreloadCoverageError triggers strict_cache_only "
            "restoration."
        )

    def test_engine_try_block_includes_strategy_initialize(self) -> None:
        src = Path("src/backtest_engine/event_driven/engine.py").read_text(
            encoding="utf-8"
        )
        try_idx = src.index("try:", src.index("set_strict_cache_only(True)"))
        init_idx = src.index("self.strategy.initialize(", try_idx)
        finally_idx = src.index("finally:", try_idx)
        assert try_idx < init_idx < finally_idx, (
            "try: must wrap the strategy.initialize call so an init-time "
            "exception triggers strict_cache_only restoration."
        )

    def test_engine_finally_restores_strict_cache_only(self) -> None:
        src = Path("src/backtest_engine/event_driven/engine.py").read_text(
            encoding="utf-8"
        )
        finally_idx = src.index(
            "finally:", src.index("set_strict_cache_only(True)"),
        )
        restore_idx = src.index(
            "set_strict_cache_only(_prev_strict_cache_only)", finally_idx,
        )
        # Restoration must be inside the finally block — i.e. after `finally:`
        # but before the next top-level statement after the try/except/finally.
        assert restore_idx > finally_idx, (
            "set_strict_cache_only(_prev_strict_cache_only) must be inside "
            "the finally: block."
        )


# ─────────────────────────────────────────────────────────────────────────
# Medium 1: behavioral daily-QA _provider_manifest_check invocation
# ─────────────────────────────────────────────────────────────────────────


class TestMedium1DailyQABehavioralInvocation:
    """Invoke scripts.run_daily_qa._provider_manifest_check() directly with
    monkeypatched PROJECT_ROOT + config.yaml, not just the underlying
    helper."""

    def _build_temp_layout(
        self,
        tmp_path: Path,
        live_calendar_end: str,
        manifest_calendar_end: str,
    ) -> Path:
        """Build a temp project layout with config.yaml + qlib_data tree."""
        # config.yaml at the temp project root.
        cfg = tmp_path / "config.yaml"
        qlib_dir = tmp_path / "data" / "qlib_data"
        cfg.write_text(
            "storage:\n"
            f"  qlib_data_dir: \"{str(qlib_dir).replace(chr(92), '/')}\"\n",
            encoding="utf-8",
        )
        (qlib_dir / "calendars").mkdir(parents=True)
        (qlib_dir / "metadata").mkdir(parents=True)
        (qlib_dir / "calendars" / "day.txt").write_text(
            "2026-01-01\n2026-02-01\n" + live_calendar_end + "\n",
            encoding="utf-8",
        )
        manifest_payload = {
            "schema_version": 1,
            "provider_build_id": "prod_test_pr8d",
            "provider_published_at": "2026-04-21T00:00:00",
            "calendar_policy_id": "frozen_20260227_system_build",
            "provider": {
                "path": str(qlib_dir).replace("\\", "/"),
                "region": "REG_CN",
                "calendar_start_date": "2008-01-02",
                "calendar_end_date": manifest_calendar_end,
                "data_end_date": manifest_calendar_end,
            },
            "event_endpoint_namespacing": {
                "status": "enforced",
                "affected_datasets": ["top_list"],
                "prefix_rule": "{dataset}__{column}",
                "canonical_kline_fields_protected": ["$close"],
            },
            "retroactive_manifest": False,
        }
        (qlib_dir / "metadata" / "provider_build.json").write_text(
            json.dumps(manifest_payload), encoding="utf-8",
        )
        return tmp_path

    def _invoke_provider_manifest_check(self, project_root: Path) -> dict:
        """Run ``scripts.run_daily_qa._provider_manifest_check()`` in a
        subprocess so its sys.path manipulation, module-level state, and
        any import-cache effects are fully isolated from the rest of the
        test suite.

        Why subprocess: in-process invocation pollutes sys.modules with
        ``research_orchestrator.*`` references that confuse subsequent
        test orderings. A subprocess starts with a clean interpreter
        and exercises the exact same code path the operator runs daily.
        """
        import subprocess
        import textwrap
        real_root = Path(".").resolve()
        runner = textwrap.dedent(
            f"""
            import json, sys
            from pathlib import Path
            sys.path.insert(0, {str(real_root / "scripts")!r})
            sys.path.insert(0, {str(real_root / "src")!r})
            sys.path.insert(0, {str(real_root)!r})
            import run_daily_qa
            run_daily_qa.PROJECT_ROOT = Path({str(project_root)!r})
            result = run_daily_qa._provider_manifest_check()
            print("__PR8D_RESULT__" + json.dumps(result, default=str))
            """
        )
        completed = subprocess.run(
            [sys.executable, "-c", runner],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"Subprocess invocation failed (exit {completed.returncode}):\n"
                f"stdout: {completed.stdout}\nstderr: {completed.stderr}"
            )
        marker = "__PR8D_RESULT__"
        for line in completed.stdout.splitlines():
            if line.startswith(marker):
                return json.loads(line[len(marker):])
        raise RuntimeError(
            f"Subprocess produced no result marker. stdout: {completed.stdout}"
        )

    def test_mismatched_calendar_returns_not_ok(self, tmp_path: Path) -> None:
        project_root = self._build_temp_layout(
            tmp_path,
            live_calendar_end="2026-03-15",       # live ends 03-15
            manifest_calendar_end="2026-02-27",   # manifest claims 02-27
        )
        result = self._invoke_provider_manifest_check(project_root)
        assert result["ok"] is False, f"Expected ok=False, got: {result}"
        assert result["exit_code"] == 1
        # The error message should reference the mismatch.
        assert "error" in result

    def test_matched_calendar_returns_ok(self, tmp_path: Path) -> None:
        project_root = self._build_temp_layout(
            tmp_path,
            live_calendar_end="2026-02-27",
            manifest_calendar_end="2026-02-27",
        )
        result = self._invoke_provider_manifest_check(project_root)
        assert result["ok"] is True, f"Expected ok=True, got: {result}"
        assert result["exit_code"] == 0
        assert result["live_calendar_end"] == "2026-02-27"
