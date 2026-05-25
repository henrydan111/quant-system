"""Phase 3 integrity gate for the staged PIT backend."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from data_infra.pit_backend import StagedQlibBackendBuilder

PHASE3_DATASETS = ["cashflow", "forecast", "holder_number", "moneyflow", "northbound", "margin", "stk_limit"]
OUTPUT_PATH = os.path.join(PROJECT_ROOT, "workspace", "outputs", "phase3_verification_report.json")


def main() -> None:
    builder = StagedQlibBackendBuilder(include_phase3=True, allow_exceptions=True)
    profiles = builder.profile_datasets(PHASE3_DATASETS)
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "build_id": builder.build_id,
        "datasets": {name: profile.__dict__ for name, profile in profiles.items()},
    }
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, default=str)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
