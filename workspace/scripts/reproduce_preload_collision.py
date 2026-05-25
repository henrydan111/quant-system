"""Reproducer for the cache-manifest collision discovered while running the
``hypothesis_validation`` profile end-to-end (plan
``snappy-buzzing-meerkat`` v5).

The script DOES NOT touch the live ``data/hypothesis_cache_manifest/`` dir.
Instead it stages a colliding manifest row in a temporary directory and
calls ``QlibDataFeeder.preload_features`` directly while monkeypatching
``data_feeder.qlib_windowed_features`` so that the temp manifest dir flows
through to the real wrapper. This isolates the failure mechanism from any
other state on disk.

Outputs ``workspace/outputs/preload_collision_repro_<ts>.json`` with the
fields documented in the plan: preload_status, cache_df_populated,
cache_df_shape, cache_hit_count, direct_fallback_count, per_day_pace_seconds,
cache_key, colliding_manifest_row, conflicting_design_hashes.

USAGE
-----
    venv/Scripts/python.exe workspace/scripts/reproduce_preload_collision.py

Run BEFORE the v5 fix: expect ``preload_status == "swallowed_exception"`` and
``cache_df_populated == false`` (Bug 1 + Bug 2 active).

Run AFTER the v5 fix: expect ``preload_status == "success"`` and
``cache_df_populated == true`` for the default-strict path; toggling the
``--strict`` flag should produce ``preload_status == "raised"`` only when a
non-relaxed mismatch (stage / window) is in play.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.research_orchestrator.cache_manifest import (  # noqa: E402
    CacheContext,
    CacheManifestStore,
)
from src.research_orchestrator.qlib_windowed_features import (  # noqa: E402
    _deterministic_cache_path,
    qlib_windowed_features,
)


OUTPUT_DIR = PROJECT_ROOT / "workspace" / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OHLCV_FIELDS = [
    "$open", "$close", "$high", "$low",
    "$vol", "$amount", "$pre_close", "$adj_factor",
]
DEFAULT_START = "2013-12-31"
DEFAULT_END = "2021-12-31"
FREQ = "day"

LOGGER = logging.getLogger("reproduce_preload_collision")


def _stub_d_features(*_args, **_kwargs):
    """Tiny synthetic frame so the reproducer runs without a real Qlib provider.

    Schema mirrors what ``D.features`` returns: MultiIndex(instrument, datetime).
    """
    idx = pd.MultiIndex.from_product(
        [
            ["000001_SZ", "000002_SZ"],
            pd.date_range(DEFAULT_START, periods=5, freq="D"),
        ],
        names=("instrument", "datetime"),
    )
    return pd.DataFrame({f: 1.0 for f in OHLCV_FIELDS}, index=idx)


def _seed_collision(
    manifest_dir: Path, *, design_hash: str, stage: str,
    start: str, end: str,
) -> dict[str, Any]:
    cache_key = _deterministic_cache_path(FREQ, OHLCV_FIELDS, start, end)
    manifest = CacheManifestStore(manifest_dir)
    row = manifest.record_cache_write(
        cache_type="qlib_features",
        cache_key=cache_key,
        cache_path=cache_key,
        cache_context=CacheContext(design_hash=design_hash),
        stage=stage,
        window_start=start,
        window_end=end,
    )
    return row


def _run_repro(
    *,
    strict: bool,
    seed_stage: str,
    fresh_design_hash: str,
    seed_design_hash: str,
    start: str,
    end: str,
    manifest_dir: Path,
) -> dict[str, Any]:
    """Run ONE reproducer scenario; return a dict for the JSON report."""
    from src.backtest_engine.event_driven.data_feeder import QlibDataFeeder

    class _StubFeeder(QlibDataFeeder):
        def __init__(self, *, stage: str = "is_only"):
            self._cache_df = None
            self._latest_adj = {}
            self._stage = stage
            # Match instrumentation attrs added by the v5 instrumentation.
            self._preload_status = "not_attempted"
            self._preload_wall_seconds = 0.0
            self._cache_hit_count = 0
            self._direct_fallback_count = 0

    seed_row = _seed_collision(
        manifest_dir,
        design_hash=seed_design_hash,
        stage=seed_stage,
        start=start,
        end=end,
    )

    feeder = _StubFeeder(stage="is_only")

    def _routed(**kwargs):
        kwargs["cache_manifest_dir"] = manifest_dir
        # Override design_hash via thread-local cache context inheritance
        # so the new write also carries a non-empty design_hash like the
        # validation handler will after Part D lands.
        from src.research_orchestrator.cache_manifest import (
            set_cache_context, reset_cache_context,
        )
        token = set_cache_context(CacheContext(design_hash=fresh_design_hash))
        mock_D = MagicMock()
        mock_D.features.side_effect = _stub_d_features
        try:
            # Patch qlib.data.D directly: qlib_windowed_features does
            # `from qlib.data import D` inside the function body, so the
            # right patch target is the source module attribute.
            with patch("qlib.data.D", mock_D):
                return qlib_windowed_features(**kwargs)
        finally:
            reset_cache_context(token)

    preload_status = "success"
    raised_repr = ""
    t0 = time.perf_counter()
    with patch(
        "src.backtest_engine.event_driven.data_feeder.qlib_windowed_features",
        side_effect=_routed,
    ), patch(
        "src.backtest_engine.event_driven.data_feeder.D"
    ) as mock_d:
        mock_d.instruments.return_value = ["000001_SZ", "000002_SZ"]
        try:
            feeder.preload_features("all", OHLCV_FIELDS, start, end, strict=strict)
        except Exception as exc:  # noqa: BLE001
            preload_status = "raised"
            raised_repr = repr(exc)
    elapsed = time.perf_counter() - t0

    if preload_status == "success" and feeder._cache_df is None:
        # Failure was swallowed (legacy non-strict path).
        preload_status = "swallowed_exception"

    cache_key = _deterministic_cache_path(FREQ, OHLCV_FIELDS, start, end)
    manifest = CacheManifestStore(manifest_dir)
    rows = manifest.list_events(cache_key=cache_key)
    conflicting_hashes = sorted({str(h) for h in rows["design_hash"].tolist()})

    return {
        "scenario": {
            "strict": strict,
            "seed_stage": seed_stage,
            "seed_design_hash": seed_design_hash,
            "fresh_design_hash": fresh_design_hash,
            "window": [start, end],
        },
        "preload_status": preload_status,
        "raised_exception": raised_repr,
        "cache_df_populated": feeder._cache_df is not None,
        "cache_df_shape": (
            list(feeder._cache_df.shape) if feeder._cache_df is not None else None
        ),
        "preload_wall_seconds": round(elapsed, 6),
        "cache_key": cache_key,
        "colliding_manifest_row": {
            "design_hash": seed_row["design_hash"],
            "stage": seed_row["stage"],
            "window_start": seed_row["window_start"],
            "window_end": seed_row["window_end"],
            "recorded_at": seed_row["recorded_at"],
        },
        "conflicting_design_hashes": conflicting_hashes,
        # The reproducer is a single-call probe; per-day pace / fallback
        # counts are not meaningful here — the production rerun harness
        # fills those for the e2e gate.
        "cache_hit_count": None,
        "direct_fallback_count": None,
        "per_day_pace_seconds": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=DEFAULT_END)
    parser.add_argument(
        "--seed-design-hash", default="hyp_A_e8312f0bcafefeed",
        help="design_hash baked into the staged colliding manifest row",
    )
    parser.add_argument(
        "--fresh-design-hash", default="hyp_validation_7c2389c5deadbeef",
        help="design_hash the in-flight preload reports (post-Part D)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    ts = pd.Timestamp.utcnow().strftime("%Y%m%dT%H%M%S")
    report = {
        "tool": "reproduce_preload_collision.py",
        "timestamp_utc": ts,
        "scenarios": [],
    }

    # Each scenario runs in its OWN temp manifest dir so they don't interfere.
    scenarios = [
        # Scenario 1: design_hash mismatch only — Part B should make this PASS.
        ("design_hash_mismatch_strict", {
            "strict": True,
            "seed_stage": "is_only",
            "seed_design_hash": args.seed_design_hash,
            "fresh_design_hash": args.fresh_design_hash,
        }),
        ("design_hash_mismatch_nonstrict", {
            "strict": False,
            "seed_stage": "is_only",
            "seed_design_hash": args.seed_design_hash,
            "fresh_design_hash": args.fresh_design_hash,
        }),
        # Scenario 2: stage mismatch — Part B does NOT relax this. strict=True
        # raises; strict=False swallows (legacy behavior).
        ("stage_mismatch_strict", {
            "strict": True,
            "seed_stage": "oos_test",
            "seed_design_hash": args.seed_design_hash,
            "fresh_design_hash": args.fresh_design_hash,
        }),
        ("stage_mismatch_nonstrict", {
            "strict": False,
            "seed_stage": "oos_test",
            "seed_design_hash": args.seed_design_hash,
            "fresh_design_hash": args.fresh_design_hash,
        }),
    ]

    for name, kwargs in scenarios:
        with tempfile.TemporaryDirectory(prefix="cache_repro_") as tmp:
            manifest_dir = Path(tmp) / "manifest"
            outcome = _run_repro(
                **kwargs,
                start=args.start, end=args.end,
                manifest_dir=manifest_dir,
            )
            outcome["name"] = name
            report["scenarios"].append(outcome)
            LOGGER.info(
                "[%s] preload_status=%s cache_df_populated=%s wall=%.3fs",
                name,
                outcome["preload_status"],
                outcome["cache_df_populated"],
                outcome["preload_wall_seconds"],
            )

    output_path = OUTPUT_DIR / f"preload_collision_repro_{ts}.json"
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    LOGGER.info("Report written to %s", output_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
