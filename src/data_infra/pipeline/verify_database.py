"""Integrity gate wrapper for the staged PIT backend."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, "..", "..", ".."))
sys.path.insert(0, os.path.join(project_root, "src"))

from data_infra.pit_backend import BuildGateError, StagedQlibBackendBuilder

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _run_pit_live_harness() -> tuple[int, int, int, list[str]]:
    """Run the P0-3 PIT live provider regression harness via pytest.

    Returns (passed, failed, skipped, failure_messages). Failures in this
    harness are publish-gate blockers — they indicate PIT correctness
    breakage on the published provider and must be investigated before
    any rebuild is promoted.
    """
    import subprocess

    test_path = os.path.join(
        project_root, "tests", "data_infra", "test_pit_live_provider.py"
    )
    test_boundary = os.path.join(
        project_root, "tests", "data_infra", "test_provider_boundary.py"
    )
    if not os.path.exists(test_path):
        return 0, 0, 0, [f"PIT live harness missing: {test_path}"]

    venv_python = os.path.join(project_root, "venv", "Scripts", "python.exe")
    if not os.path.exists(venv_python):
        venv_python = sys.executable

    result = subprocess.run(
        [venv_python, "-m", "pytest", test_path, test_boundary, "-q", "--tb=short"],
        capture_output=True,
        text=True,
        cwd=project_root,
    )
    # Parse the summary line: "N passed, N failed, N skipped" is at the end
    tail = result.stdout.splitlines()[-1] if result.stdout else ""
    passed = failed = skipped = 0
    for token in tail.split():
        token = token.strip(",")
        if token.isdigit():
            continue
    # Simpler: use return code + message extraction
    if result.returncode == 0:
        # Count by scanning tail for "N passed"
        import re

        m = re.search(r"(\d+) passed", result.stdout)
        passed = int(m.group(1)) if m else 0
        m = re.search(r"(\d+) skipped", result.stdout)
        skipped = int(m.group(1)) if m else 0
        return passed, 0, skipped, []
    # Failure path
    failure_messages: list[str] = []
    import re

    m = re.search(r"(\d+) failed", result.stdout)
    failed = int(m.group(1)) if m else 0
    m = re.search(r"(\d+) passed", result.stdout)
    passed = int(m.group(1)) if m else 0
    m = re.search(r"(\d+) skipped", result.stdout)
    skipped = int(m.group(1)) if m else 0
    for line in result.stdout.splitlines():
        if line.startswith("FAILED"):
            failure_messages.append(line.strip())
    return passed, failed, skipped, failure_messages


def main() -> None:
    # Raw-store quiescence (HARD pre-promotion integration gate): refuse to run while a
    # recovered family is being swapped into the live store — the tree may be half-replaced.
    from data_infra.recovery_quiescence import assert_no_active_recovery
    assert_no_active_recovery()
    parser = argparse.ArgumentParser(description="Profile and validate raw datasets for the staged PIT backend")
    parser.add_argument("--datasets", type=str, default=None, help="Comma-separated dataset subset")
    parser.add_argument("--exclude-phase3", action="store_true", help="Skip Phase 3 datasets")
    parser.add_argument("--allow-exceptions", action="store_true", help="Report issues without failing the process")
    parser.add_argument(
        "--skip-pit-live-harness",
        action="store_true",
        help="Skip the PIT live provider regression harness (P0-3). Use only for profiling-only runs.",
    )
    args = parser.parse_args()

    datasets = args.datasets.split(",") if args.datasets else None
    builder = StagedQlibBackendBuilder(
        include_phase3=not args.exclude_phase3,
        allow_exceptions=args.allow_exceptions,
    )
    profiles = builder.profile_datasets(datasets=datasets)
    errors = []
    warnings = []
    for name, profile in profiles.items():
        errors.extend([f"{name}: {message}" for message in profile.errors])
        warnings.extend([f"{name}: {message}" for message in profile.warnings])
        if profile.unexpected_missing_dates:
            message = f"{name}: missing {len(profile.unexpected_missing_dates)} expected dates"
            if args.allow_exceptions:
                warnings.append(message)
            else:
                errors.append(message)

    # P0-3 + P0-1: gate on the PIT live provider harness and provider boundary
    # regression. These prove "no same-day leakage" and "delist guard holds"
    # against the actual published provider at data/qlib_data/.
    pit_harness_result = None
    if not args.skip_pit_live_harness:
        logger.info("Running PIT live provider + boundary regression harness...")
        passed, failed, skipped, failures = _run_pit_live_harness()
        pit_harness_result = {
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
        }
        logger.info(
            "PIT live harness: %d passed, %d failed, %d skipped",
            passed,
            failed,
            skipped,
        )
        if failed > 0:
            for msg in failures:
                errors.append(f"PIT_HARNESS: {msg}")

    summary = {
        "build_id": builder.build_id,
        "datasets": list(profiles),
        "pit_harness": pit_harness_result,
        "errors": errors,
        "warnings": warnings,
    }
    logger.info("Profiled %d datasets", len(profiles))
    if warnings:
        logger.warning("Warnings (%d): %s", len(warnings), warnings[:10])
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if errors and not args.allow_exceptions:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
