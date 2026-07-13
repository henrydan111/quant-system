"""Phase 5-B B3.2: the provider raw-input attestation gate.

The monthly atomic publish binds every new build to its raw-input cut
(provider_build.json.raw_input_manifest_root). These tests pin the enforcement side:

  * CalendarPolicy parses ``require_raw_input_attestation`` (strict-bool, default False).
  * release_gate.assert_provider_raw_attestation fails a formal run whose policy requires
    the attestation when the live manifest lacks (or carries a malformed) root — and
    SKIPS cleanly for legacy policies, so pre-thaw providers keep working.
  * The formal-run chokepoint (event_driven._validate_provider_at_runtime) actually
    invokes the gate — a policy-flagged run against an unattested manifest raises.
"""
from __future__ import annotations

import pytest

from src.data_infra.provider_manifest import ProviderManifest
from src.research_orchestrator.calendar_policy import CalendarPolicy
from src.research_orchestrator.release_gate import (
    ProviderAttestationError,
    assert_provider_raw_attestation,
    evaluate_provider_raw_attestation,
)

_ROOT = "cd" * 32


def _policy(require: bool, **overrides) -> CalendarPolicy:
    payload = {
        "policy_id": "frozen_20990101_thaw_stepN",
        "policy_schema_version": 1,
        "calendar_start_date": "2008-01-02",
        "calendar_end_date": "2099-01-01",
        "data_end_date": "2099-01-01",
        "frozen": True,
        "reason": "test",
        "established_at": "2099-01-01",
        "spent_oos_end": "2026-02-27",
        "fresh_holdout_start": "2026-02-28",
        "allowed_modes": ["formal", "oos_test"],
        "default_formal_behavior": "require_explicit_policy",
    }
    if require:
        payload["require_raw_input_attestation"] = True
    payload.update(overrides)
    return CalendarPolicy.from_dict(payload)


def _manifest(**overrides) -> ProviderManifest:
    payload = {
        "schema_version": 1,
        "provider_build_id": "thaw_20990101_120000",
        "provider_published_at": "2099-01-01T00:00:00",
        "calendar_policy_id": "frozen_20990101_thaw_stepN",
        "provider": {
            "path": "data/qlib_data", "region": "REG_CN",
            "calendar_start_date": "2008-01-02", "calendar_end_date": "2099-01-01",
            "data_end_date": "2099-01-01",
        },
        "event_endpoint_namespacing": {
            "status": "enforced",
            "affected_datasets": ["top_list", "top_inst", "block_trade", "cyq_perf"],
            "prefix_rule": "{dataset}__{column}",
            "canonical_kline_fields_protected": ["$open", "$high", "$low", "$close", "$vol", "$amount"],
        },
    }
    payload.update(overrides)
    return ProviderManifest.from_dict(payload)


# ── policy flag parsing ───────────────────────────────────────────────────────
def test_policy_flag_defaults_false_and_parses_strict_bool():
    assert _policy(require=False).require_raw_input_attestation is False
    assert _policy(require=True).require_raw_input_attestation is True


def test_policy_flag_non_bool_fails_closed():
    # GPT re-review Major 1: a truthy-but-non-bool value (the quoted YAML string "true")
    # previously read as False — silently DISABLING a load-bearing enforcement flag. It
    # must refuse to load instead.
    from src.research_orchestrator.calendar_policy import CalendarPolicyError
    for bad in ("true", 1, "yes"):
        with pytest.raises(CalendarPolicyError, match="require_raw_input_attestation"):
            _policy(require=False, require_raw_input_attestation=bad)


# ── the gate itself ──────────────────────────────────────────────────────────
def test_gate_passes_when_policy_requires_and_root_present():
    result = assert_provider_raw_attestation(
        manifest=_manifest(raw_input_manifest_root=_ROOT, parent_provider_build_id="p"),
        policy=_policy(require=True))
    assert result.eligible and result.required
    assert result.raw_input_manifest_root == _ROOT


def test_gate_blocks_missing_root_when_required():
    with pytest.raises(ProviderAttestationError, match="raw_input_manifest_root"):
        assert_provider_raw_attestation(manifest=_manifest(), policy=_policy(require=True))


def test_gate_blocks_malformed_root_when_required():
    # bypass the loader (which would already refuse) by evaluating a raw mapping — the
    # gate must not trust its input to have been loader-validated.
    result = evaluate_provider_raw_attestation(
        manifest={"provider_build_id": "b", "raw_input_manifest_root": "zz"},
        policy=_policy(require=True))
    assert not result.eligible and any("sha256" in r for r in result.reasons)


def test_gate_skips_for_legacy_policy():
    # Pre-thaw policies never set the flag: an unattested manifest stays eligible.
    result = evaluate_provider_raw_attestation(manifest=_manifest(), policy=_policy(require=False))
    assert result.eligible and not result.required


# ── formal-run chokepoint wiring ─────────────────────────────────────────────
def _wire_runtime_validation(tmp_path, monkeypatch, policy):
    """Drive event_driven._validate_provider_at_runtime against a synthetic provider
    dir + injected policy (the loader is patched at its source module, which the
    chokepoint imports at call time)."""
    from src.research_orchestrator import calendar_policy as cp
    monkeypatch.setattr(cp, "load_calendar_policy", lambda pid: policy)
    (tmp_path / "calendars").mkdir(parents=True)
    (tmp_path / "calendars" / "day.txt").write_text("2008-01-02\n2099-01-01\n", encoding="utf-8")


def _write_state(tmp_path, state: str, build_id: str = "thaw_20990101_120000") -> None:
    import json
    meta = tmp_path / "metadata"
    meta.mkdir(parents=True, exist_ok=True)
    (meta / "publish_state.json").write_text(
        json.dumps({"state": state, "provider_build_id": build_id}), encoding="utf-8")


def test_formal_runtime_validation_enforces_attestation(tmp_path, monkeypatch):
    from src.backtest_engine.event_driven import _validate_provider_at_runtime

    _wire_runtime_validation(tmp_path, monkeypatch, _policy(require=True))
    _write_state(tmp_path, "ready")
    with pytest.raises(ProviderAttestationError, match="raw_input_manifest_root"):
        _validate_provider_at_runtime(
            manifest=_manifest(), calendar_policy_id="frozen_20990101_thaw_stepN",
            run_mode="formal", qlib_dir=tmp_path)
    # same run with an attested manifest + ready state passes
    _validate_provider_at_runtime(
        manifest=_manifest(raw_input_manifest_root=_ROOT, parent_provider_build_id="p"),
        calendar_policy_id="frozen_20990101_thaw_stepN", run_mode="formal", qlib_dir=tmp_path)


def test_formal_runtime_validation_legacy_policy_unaffected(tmp_path, monkeypatch):
    from src.backtest_engine.event_driven import _validate_provider_at_runtime

    _wire_runtime_validation(tmp_path, monkeypatch, _policy(require=False))
    _validate_provider_at_runtime(
        manifest=_manifest(), calendar_policy_id="frozen_20990101_thaw_stepN",
        run_mode="formal", qlib_dir=tmp_path)


# ── publish-state (QA quarantine) gate — GPT re-review Blocker 6 ─────────────
def test_publish_state_gate_quarantines_until_ready(tmp_path):
    from src.research_orchestrator.release_gate import (
        assert_provider_publish_state,
        evaluate_provider_publish_state,
    )
    flagged, legacy = _policy(require=True), _policy(require=False)
    m = _manifest(raw_input_manifest_root=_ROOT)
    # required + ABSENT marker -> refuse (the build skipped the attested transaction)
    assert not evaluate_provider_publish_state(qlib_dir=tmp_path, policy=flagged, manifest=m).eligible
    # legacy + absent -> eligible (pre-5B providers never had one)
    assert evaluate_provider_publish_state(qlib_dir=tmp_path, policy=legacy, manifest=m).eligible
    # a PRESENT non-ready marker quarantines EVEN under a legacy policy
    _write_state(tmp_path, "pending_qa")
    for pol in (flagged, legacy):
        with pytest.raises(ProviderAttestationError, match="pending_qa"):
            assert_provider_publish_state(qlib_dir=tmp_path, policy=pol, manifest=m)
    _write_state(tmp_path, "qa_failed")
    assert not evaluate_provider_publish_state(qlib_dir=tmp_path, policy=flagged, manifest=m).eligible
    _write_state(tmp_path, "suspect")  # tamper quarantine (re-review #3) — refused everywhere
    for pol in (flagged, legacy):
        assert not evaluate_provider_publish_state(qlib_dir=tmp_path, policy=pol, manifest=m).eligible
    _write_state(tmp_path, "ready")
    assert evaluate_provider_publish_state(qlib_dir=tmp_path, policy=flagged, manifest=m).eligible
    # a marker naming a DIFFERENT build is stale/foreign -> refuse
    _write_state(tmp_path, "ready", build_id="someone_else")
    assert not evaluate_provider_publish_state(qlib_dir=tmp_path, policy=flagged, manifest=m).eligible
    # GPT re-review #2 P0: a bare {"state": "ready"} with NO provider_build_id must refuse
    # — an unbound certification cannot clear any build (even with no manifest supplied).
    import json as _j
    (tmp_path / "metadata" / "publish_state.json").write_text(
        _j.dumps({"state": "ready"}), encoding="utf-8")
    unbound = evaluate_provider_publish_state(qlib_dir=tmp_path, policy=legacy, manifest=None)
    assert not unbound.eligible and any("provider_build_id" in r for r in unbound.reasons)


def test_formal_runtime_validation_refuses_quarantined_provider(tmp_path, monkeypatch):
    from src.backtest_engine.event_driven import _validate_provider_at_runtime

    _wire_runtime_validation(tmp_path, monkeypatch, _policy(require=True))
    _write_state(tmp_path, "qa_failed")
    with pytest.raises(ProviderAttestationError, match="qa_failed"):
        _validate_provider_at_runtime(
            manifest=_manifest(raw_input_manifest_root=_ROOT, parent_provider_build_id="p"),
            calendar_policy_id="frozen_20990101_thaw_stepN", run_mode="formal", qlib_dir=tmp_path)


# ── provider_context chokepoint — GPT re-review Blocker 5 ────────────────────
def _wire_provider_context(tmp_path, monkeypatch, policy):
    """Point the shared live-provider resolution (every sanctioned data door) at a tmp
    provider + injected policy."""
    import json
    from src.data_infra import provider_context as pc
    from src.research_orchestrator import calendar_policy as cp

    (tmp_path / "calendars").mkdir(parents=True, exist_ok=True)
    (tmp_path / "calendars" / "day.txt").write_text("2008-01-02\n2099-01-01\n", encoding="utf-8")

    def write_manifest(**overrides):
        payload = _manifest(**overrides).to_dict()
        meta = tmp_path / "metadata"
        meta.mkdir(parents=True, exist_ok=True)
        (meta / "provider_build.json").write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(pc, "_qlib_dir", lambda: tmp_path)
    monkeypatch.setattr(cp, "load_calendar_policy", lambda pid, root=None: policy)
    pc.refresh_live_provider_context()
    return pc, write_manifest


def test_provider_context_enforces_attestation_and_state(tmp_path, monkeypatch):
    # The formal Qlib read door (qlib_windowed_features) and the sandbox loader BOTH
    # resolve through provider_context._resolve — an unattested or quarantined provider
    # must refuse there, not only at the event-driven runtime validator.
    pc, write_manifest = _wire_provider_context(tmp_path, monkeypatch, _policy(require=True))
    write_manifest()  # no raw_input_manifest_root
    with pytest.raises(pc.ProviderContextError, match="raw_input_manifest_root"):
        pc.live_provider_ids()
    write_manifest(raw_input_manifest_root=_ROOT, parent_provider_build_id="p")
    with pytest.raises(pc.ProviderContextError, match="publish-state|publish_state"):
        pc.live_provider_ids()  # attested but NO marker -> still refused
    _write_state(tmp_path, "pending_qa")
    with pytest.raises(pc.ProviderContextError, match="pending_qa"):
        pc.live_provider_ids()
    _write_state(tmp_path, "ready")
    build, policy_id = pc.live_provider_ids()  # the state flip re-keys the cache — no stale verdict
    assert build == "thaw_20990101_120000" and policy_id == "frozen_20990101_thaw_stepN"


def test_provider_context_legacy_policy_still_resolves(tmp_path, monkeypatch):
    pc, write_manifest = _wire_provider_context(tmp_path, monkeypatch, _policy(require=False))
    write_manifest()
    build, _ = pc.live_provider_ids()
    assert build == "thaw_20990101_120000"
