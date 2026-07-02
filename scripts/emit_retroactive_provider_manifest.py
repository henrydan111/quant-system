"""Bootstrap script: emit a retroactive provider manifest for the existing
2026-04-21 Qlib provider build.

This script is intended to be run ONCE on each host that holds the
already-published provider. After PR 1 lands, future provider builds will
emit a fresh (non-retroactive) manifest from the builder's ``publish()`` path.

The retroactive manifest carries ``retroactive_manifest=true`` plus an
evidence array so future auditors can trace the attestation back to its
sources (README status snapshot, project_state revalidation note, namespace
tests).

Usage
=====

    venv/Scripts/python.exe scripts/emit_retroactive_provider_manifest.py

Optional flags:

    --qlib-dir <path>            Override Qlib provider directory.
    --compute-kline-hash         Compute the sentinel canonical_kline_hash
                                 (requires a working Qlib provider).
    --dry-run                    Print the manifest payload but do not write.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data_infra.provider_manifest import (  # noqa: E402
    compute_canonical_kline_hash,
    emit_retroactive_manifest,
    manifest_path_for,
)

DEFAULT_QLIB_DIR = PROJECT_ROOT / "data" / "qlib_data"
CALENDAR_POLICY_ID = "frozen_20260227_system_build"  # noqa: global-calendar-policy — retroactive-manifest tool: stamping the LEGACY id on the pre-attestation provider IS its purpose (D1 old-artifact exemption)

EVIDENCE = (
    "README.md status snapshot (line 13): 'Live Qlib provider rebuilt 2026-04-21.'",
    "project_state.md: 'downstream re-validation completed on 2026-04-23 against the rebuilt, namespace-correct provider.'",
    "tests/data_infra/test_event_like_daily_namespace.py — namespacing fix regression test",
    "tests/data_infra/test_event_like_provider_contract.py — provider contract regression test",
    "tests/data_infra/test_pit_live_provider.py — PIT live-provider regression",
)


def _resolve_git_commit() -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(PROJECT_ROOT), text=True
        ).strip()
        return out or None
    except (OSError, subprocess.CalledProcessError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qlib-dir", default=str(DEFAULT_QLIB_DIR))
    parser.add_argument("--compute-kline-hash", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(message)s")
    logger = logging.getLogger("emit_retroactive_provider_manifest")

    qlib_dir = Path(args.qlib_dir).resolve()
    if not qlib_dir.exists():
        logger.error("Qlib provider directory not found: %s", qlib_dir)
        return 1

    kline_hash = None
    if args.compute_kline_hash:
        logger.info("Computing canonical_kline_hash (initializing Qlib...)")
        try:
            kline_hash = compute_canonical_kline_hash(
                sentinel_instruments=("000001_SZ", "600000_SH", "300001_SZ"),
                sentinel_dates=("2014-01-02", "2020-08-24", "2024-12-31"),
                qlib_dir=qlib_dir,
            )
            logger.info("canonical_kline_hash sha256=%s", kline_hash["sha256"])
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("kline hash computation failed: %s", exc)

    payload = dict(
        qlib_dir=str(qlib_dir),
        provider_build_id="prod_full_20260421_namespace_v1",
        provider_published_at="2026-04-21T00:00:00",
        downstream_revalidated_at="2026-04-23T00:00:00",
        calendar_policy_id=CALENDAR_POLICY_ID,
        calendar_start_date="2008-01-02",
        calendar_end_date="2026-02-27",
        data_end_date="2026-02-27",
        evidence=EVIDENCE,
        canonical_kline_hash=kline_hash,
        validation={
            "namespace_tests_passed": True,
            "provider_boundary_tests_passed": True,
            "pit_live_provider_tests_passed": True,
            "daily_qa_passed": None,
        },
        source_git_commit=_resolve_git_commit(),
    )

    target = manifest_path_for(qlib_dir)
    if args.dry_run:
        logger.info("Dry run — would write %s with payload:", target)
        print(json.dumps(payload, indent=2, default=str))
        return 0

    if target.exists():
        logger.warning("Existing manifest found at %s — will overwrite atomically.", target)

    written = emit_retroactive_manifest(**payload)
    logger.info("Manifest written: %s (%d bytes)", written, os.path.getsize(written))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
