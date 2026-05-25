"""
Alpha-mining wrapper for batch factor screening on the live PIT backend.

This keeps the core implementation in workspace/scripts/batch_factor_screening.py
while pinning research-friendly defaults for the current alpha_mining workspace.
"""

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from workspace.scripts.batch_factor_screening import main as shared_main


def build_default_args():
    script_dir = Path(__file__).resolve().parent
    run_root = script_dir / "latest_backend_screening"
    cache_root = run_root / "cache"
    qlib_dir = PROJECT_ROOT / "data" / "qlib_data"

    return [
        "--start", "2012-01-01",
        "--end", "auto",
        "--engine", "batch",
        "--cache-mode", "resume",
        "--kernels", "0",
        "--qlib-dir", str(qlib_dir),
        "--output-dir", str(run_root),
        "--cache-dir", str(cache_root),
    ]


if __name__ == "__main__":
    shared_main(build_default_args() + sys.argv[1:])
