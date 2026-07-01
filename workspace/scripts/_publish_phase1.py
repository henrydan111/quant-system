"""Publish the verified Phase-1 staged provider (indicators q_* + stk_holdertrade 高管) to live.

Atomic swap via StagedQlibBackendBuilder.publish(): backs up the current live provider to
data/qlib_data.bak_<build_id>, os.replace(staged -> data/qlib_data), emits a fresh
provider_build.json. GPT R2 = SHIP; staged build verified (0 warnings, byte-identical no-regression,
amount min_count fix confirmed). One-off.
"""
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from data_infra.pit_backend import StagedQlibBackendBuilder  # noqa: E402

BUILD_ID = "phase1_qfields_holdertrade_v2_20260624"

builder = StagedQlibBackendBuilder(build_id=BUILD_ID)
print("staged provider:", builder.paths.provider_dir)
print("target (live)  :", builder.paths.qlib_dir)
print("publishing (atomic swap + backup) ...", flush=True)
builder.publish()
print("PUBLISHED.", flush=True)

manifest = json.loads((Path(builder.paths.qlib_dir) / "metadata" / "provider_build.json").read_text(encoding="utf-8"))
print("new provider_build_id:", manifest.get("provider_build_id"))
print("calendar bounds:", manifest.get("calendar_start"), "->", manifest.get("calendar_end"))
