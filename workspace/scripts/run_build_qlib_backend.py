from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    src_path = root / "src"
    script_path = src_path / "data_infra" / "pipeline" / "build_qlib_backend.py"
    os.environ.setdefault("PIT_DUMP_MAX_WORKERS", "1")
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    sys.argv = [str(script_path), *sys.argv[1:]]
    runpy.run_path(str(script_path), run_name="__main__")


if __name__ == "__main__":
    main()
