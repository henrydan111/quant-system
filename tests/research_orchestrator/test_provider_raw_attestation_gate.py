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
    # strict bool: a YAML string "true" must NOT enable enforcement silently … but it
    # must not DISABLE fail-closed either — the gate treats only `is True` as required,
    # mirroring the binding_exempt discipline.
    sneaky = _policy(require=False, require_raw_input_attestation="true")
    assert sneaky.require_raw_input_attestation is False


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


def test_formal_runtime_validation_enforces_attestation(tmp_path, monkeypatch):
    from src.backtest_engine.event_driven import _validate_provider_at_runtime

    _wire_runtime_validation(tmp_path, monkeypatch, _policy(require=True))
    with pytest.raises(ProviderAttestationError, match="raw_input_manifest_root"):
        _validate_provider_at_runtime(
            manifest=_manifest(), calendar_policy_id="frozen_20990101_thaw_stepN",
            run_mode="formal", qlib_dir=tmp_path)
    # same run with an attested manifest passes
    _validate_provider_at_runtime(
        manifest=_manifest(raw_input_manifest_root=_ROOT, parent_provider_build_id="p"),
        calendar_policy_id="frozen_20990101_thaw_stepN", run_mode="formal", qlib_dir=tmp_path)


def test_formal_runtime_validation_legacy_policy_unaffected(tmp_path, monkeypatch):
    from src.backtest_engine.event_driven import _validate_provider_at_runtime

    _wire_runtime_validation(tmp_path, monkeypatch, _policy(require=False))
    _validate_provider_at_runtime(
        manifest=_manifest(), calendar_policy_id="frozen_20990101_thaw_stepN",
        run_mode="formal", qlib_dir=tmp_path)
