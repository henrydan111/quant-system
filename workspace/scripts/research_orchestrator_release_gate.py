from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import workspace.scripts.research_orchestrator_audit as orch_audit
from src.research_orchestrator.release_gate import run_release_gate


DEFAULT_GATE_ROOT = (PROJECT_ROOT / "workspace" / "outputs" / "orchestrator_release_gate").resolve()


def _timestamp_token() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Strict release gate for research_orchestrator.")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional explicit release-gate output directory. Default: workspace/outputs/orchestrator_release_gate/<timestamp>",
    )
    parser.add_argument(
        "--theme-run-dir",
        default=None,
        help="Optional existing real theme_strategy quick event-driven run directory to inspect during the embedded audit.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    gate_root = Path(args.output_dir).resolve() if args.output_dir else (DEFAULT_GATE_ROOT / _timestamp_token()).resolve()
    theme_run_dir = Path(args.theme_run_dir).resolve() if args.theme_run_dir else None
    result = run_release_gate(
        gate_root=gate_root,
        audit_runner=orch_audit.run_full_audit,
        theme_run_dir=theme_run_dir,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
