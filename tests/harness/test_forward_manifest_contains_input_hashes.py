"""B7/B4 + R2 Blocker-3/Major-5: the manifest must pin EVERY decision input by
content hash — completeness is CODE-enforced (build_manifest refuses missing or
blank required fields), and the required set covers the evidence-grade fields
(raw LLM responses, quant scores, prompts/models, worktree cleanliness), not
just the easy-to-hash files."""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

SCRIPT = (PROJECT_ROOT / "workspace" / "research" / "mvp_pool_book"
          / "run_forward_cycle.py")

#: the evidence-grade contract — if any of these leaves REQUIRED_MANIFEST_FIELDS,
#: this test must break (Major-5: tests cover the research-validity contract).
EVIDENCE_GRADE_FIELDS = {
    "git_commit", "git_worktree_clean",
    "provider_manifest_sha256", "trade_cal_sha256", "qlib_calendar_sha256",
    "factor_registry_sha256", "factor_expression_hashes", "factor_list",
    "golden_stock_events_hash", "pool_parquet_hash", "industry_map_hash",
    "quant_scores_hash", "config_hash", "prompt_hashes", "model_ids",
    "text_store_hash_by_required_source", "input_row_hashes_by_source",
    "dossier_hash_by_ts_code", "raw_llm_response_hash_by_ts_code",
    "validated_scorecard_hash_by_ts_code",
    "overlay_audit_hash", "decision_json_hash", "scorecards_parquet_hash",
    "latest_allowed_asof",
}


@pytest.fixture(scope="module")
def fwd():
    spec = importlib.util.spec_from_file_location("run_forward_cycle_under_test2", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _full_fields(fwd):
    return {k: ({"x": "y"} if k.endswith(("_by_ts_code", "_by_source", "hashes",
                                          "model_ids"))
                else ["f"] if k == "factor_list"
                else True if k == "git_worktree_clean"
                else 2 if k == "calendar_staleness_trading_days"
                else "v")
            for k in fwd.REQUIRED_MANIFEST_FIELDS}


def test_required_set_covers_evidence_grade_contract(fwd):
    missing = EVIDENCE_GRADE_FIELDS - fwd.REQUIRED_MANIFEST_FIELDS
    assert not missing, f"evidence-grade fields dropped from the contract: {missing}"


def test_manifest_refuses_missing_required_field(fwd):
    fields = _full_fields(fwd)
    fields.pop("raw_llm_response_hash_by_ts_code")
    with pytest.raises(fwd.ForwardGateError, match="missing required"):
        fwd.build_manifest(fields)


def test_manifest_refuses_blank_required_field(fwd):
    fields = _full_fields(fwd)
    fields["quant_scores_hash"] = ""
    with pytest.raises(fwd.ForwardGateError, match="blank required"):
        fwd.build_manifest(fields)


def test_full_manifest_builds_and_preserves_fields(fwd):
    fields = _full_fields(fwd)
    m = fwd.build_manifest(fields)
    assert set(m) >= fwd.REQUIRED_MANIFEST_FIELDS


def test_sha256_file_is_real_content_hash(fwd, tmp_path):
    p = tmp_path / "f.bin"
    p.write_bytes(b"evidence")
    assert fwd.sha256_file(p) == hashlib.sha256(b"evidence").hexdigest()
    assert fwd.sha256_text("evidence") == hashlib.sha256(b"evidence").hexdigest()
