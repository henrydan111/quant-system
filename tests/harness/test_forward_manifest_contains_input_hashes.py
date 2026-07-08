"""B7/B4 + R2-B3 + R3-B2: the manifest must pin EVERY decision input AND every
attempted LLM artifact (success, violation, parse failure, no-text) by content
hash — completeness is CODE-enforced; artifact hashing works by DIRECTORY
SCAN, never by trusting the success path."""
from __future__ import annotations

import hashlib
import importlib.util
import json
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
    "dossier_hash_by_ts_code", "llm_artifact_hash_by_ts_code",
    "validated_scorecard_hash_by_ts_code",
    "overlay_audit_hash", "decision_json_hash", "scorecards_parquet_hash",
    "latest_allowed_asof",
    # R3/R5: coverage payload persisted + pinned, migration provenance
    "text_coverage_record_hash", "text_coverage_record_path",
    "text_coverage_window", "text_coverage_required_sources",
    "text_store_migration_manifest_hash", "text_store_migration_id",
}


@pytest.fixture(scope="module")
def fwd():
    spec = importlib.util.spec_from_file_location("run_forward_cycle_under_test2", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _full_fields(fwd):
    return {k: ({"x": "y"} if k.endswith(("_by_ts_code", "_by_source", "hashes",
                                          "model_ids", "window"))
                else ["f"] if k.endswith(("factor_list", "required_sources"))
                else True if k == "git_worktree_clean"
                else 2 if k == "calendar_staleness_trading_days"
                else "v")
            for k in fwd.REQUIRED_MANIFEST_FIELDS}


def test_required_set_covers_evidence_grade_contract(fwd):
    missing = EVIDENCE_GRADE_FIELDS - fwd.REQUIRED_MANIFEST_FIELDS
    assert not missing, f"evidence-grade fields dropped from the contract: {missing}"
    # the success-path-only field is retired; scan-based field replaces it
    assert "raw_llm_response_hash_by_ts_code" not in fwd.REQUIRED_MANIFEST_FIELDS


def test_manifest_refuses_missing_required_field(fwd):
    fields = _full_fields(fwd)
    fields.pop("llm_artifact_hash_by_ts_code")
    with pytest.raises(fwd.ForwardGateError, match="missing required"):
        fwd.build_manifest(fields)


def test_manifest_refuses_blank_required_field(fwd):
    fields = _full_fields(fwd)
    fields["quant_scores_hash"] = ""
    with pytest.raises(fwd.ForwardGateError, match="blank required"):
        fwd.build_manifest(fields)


def test_full_manifest_builds_and_preserves_fields(fwd):
    m = fwd.build_manifest(_full_fields(fwd))
    assert set(m) >= fwd.REQUIRED_MANIFEST_FIELDS


def test_sha256_file_is_real_content_hash(fwd, tmp_path):
    p = tmp_path / "f.bin"
    p.write_bytes(b"evidence")
    assert fwd.sha256_file(p) == hashlib.sha256(b"evidence").hexdigest()
    assert fwd.sha256_text("evidence") == hashlib.sha256(b"evidence").hexdigest()


# ------------------------- R3 Blocker-2: artifact scan -----------------------

_OK_SET = ("extract_request.json", "extract_response_raw.json",
           "score_request.json", "score_response_raw.json",
           "validated_scorecard.json")


def _mk_name_dir(names_dir: Path, qcode: str, files: tuple[str, ...]):
    d = names_dir / qcode
    d.mkdir(parents=True)
    for fn in files:
        (d / fn).write_text(json.dumps({"f": fn}), encoding="utf-8")


def test_artifact_scan_pins_success_failure_partial_and_no_text(fwd, tmp_path):
    names = tmp_path / "names"
    _mk_name_dir(names, "000001_SZ", _OK_SET)                          # success
    _mk_name_dir(names, "000002_SZ", ("extract_request.json",
                                      "extract_response_raw.json",
                                      "failure.json"))                 # parse fail
    _mk_name_dir(names, "000003_SZ", ("extract_request.json",
                                      "extract_response_raw.json",
                                      "score_request.json",
                                      "score_response_raw.json",
                                      "failure.json"))                 # violation
    status = {"000001.SZ": "ok", "000002.SZ": "fail:ArkClientError",
              "000003.SZ": "fail:ScorecardViolation", "000004.SZ": "no_text"}
    dirs = {"000001.SZ": "000001_SZ", "000002.SZ": "000002_SZ",
            "000003.SZ": "000003_SZ", "000004.SZ": "000004_SZ"}
    out = fwd.collect_llm_artifact_hashes(names, status, dirs)
    assert set(out["000001.SZ"]["artifacts"]) == set(_OK_SET)
    # PARTIAL spend is pinned: the raw extract/score responses of failures too
    assert "extract_response_raw.json" in out["000002.SZ"]["artifacts"]
    assert "score_response_raw.json" in out["000003.SZ"]["artifacts"]
    assert out["000004.SZ"] == {"status": "no_text", "llm_attempted": False}
    # hashes are real file hashes
    p = names / "000001_SZ" / "validated_scorecard.json"
    assert out["000001.SZ"]["artifacts"]["validated_scorecard.json"] == \
        hashlib.sha256(p.read_bytes()).hexdigest()


def test_artifact_scan_refuses_unpinned_spend(fwd, tmp_path):
    names = tmp_path / "names"
    # ok status but scorecard artifact missing -> refuse
    _mk_name_dir(names, "000001_SZ", _OK_SET[:-1])
    with pytest.raises(fwd.ForwardGateError, match="missing artifact hashes"):
        fwd.collect_llm_artifact_hashes(names, {"000001.SZ": "ok"},
                                        {"000001.SZ": "000001_SZ"})
    # failure status without failure.json -> refuse
    _mk_name_dir(names, "000002_SZ", ("extract_request.json",))
    with pytest.raises(fwd.ForwardGateError, match="missing artifact hashes"):
        fwd.collect_llm_artifact_hashes(names, {"000002.SZ": "fail:ArkClientError"},
                                        {"000002.SZ": "000002_SZ"})
    # attempted name whose dir vanished -> refuse
    with pytest.raises(fwd.ForwardGateError, match="missing per-name artifact dir"):
        fwd.collect_llm_artifact_hashes(names, {"000009.SZ": "ok"},
                                        {"000009.SZ": "000009_SZ"})
