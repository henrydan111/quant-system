"""PR P1.4 — FrozenSelectionSet hash identity + seal_key migration back-compat."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from src.research_orchestrator.frozen_selection_set import (
    FrozenSelectionSet,
    SelectedFactor,
)
from src.research_orchestrator.holdout_seal import HoldoutSealStore

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _set(**overrides) -> FrozenSelectionSet:
    base = dict(
        selected=(
            SelectedFactor("qual_roe", 1, "h_roe", "long"),
            SelectedFactor("mom_20d", 2, "h_mom", "short"),
        ),
        candidate_pool_hash="pool_a",
        selection_rule_hash="rule_a",
        eval_protocol_hash="proto_a",
        metric="rank_icir",
        portfolio_side="long_short",
        universe="csi300",
        time_split_window="2014-01-01:2020-12-31",
        rebalance="monthly",
        neutralization="industry",
    )
    base.update(overrides)
    return FrozenSelectionSet(**base)


class TestFrozenSelectionSetHash:
    def test_hash_is_64_hex_and_stable(self) -> None:
        a, b = _set(), _set()
        assert a.frozen_set_hash == b.frozen_set_hash
        assert len(a.frozen_set_hash) == 64
        int(a.frozen_set_hash, 16)  # valid hex

    def test_hash_is_order_independent_over_selected(self) -> None:
        a = _set()
        b = _set(selected=tuple(reversed(a.selected)))
        assert a.frozen_set_hash == b.frozen_set_hash

    def test_enum_case_and_whitespace_do_not_change_hash(self) -> None:
        # "editing wording" / cosmetic enum case must NOT change the frozen identity.
        a = _set()
        b = _set(metric=" Rank_ICIR ", portfolio_side="LONG_SHORT", neutralization="Industry")
        assert a.frozen_set_hash == b.frozen_set_hash

    @pytest.mark.parametrize(
        "field,value",
        [
            ("candidate_pool_hash", "pool_B"),
            ("selection_rule_hash", "rule_B"),
            ("eval_protocol_hash", "proto_B"),
            ("metric", "sharpe"),
            ("portfolio_side", "long_only"),
            ("universe", "csi500"),
            ("time_split_window", "2015-01-01:2020-12-31"),
            ("rebalance", "weekly"),
            ("neutralization", "none"),
        ],
    )
    def test_changing_a_hashed_field_changes_hash(self, field: str, value: str) -> None:
        assert _set().frozen_set_hash != _set(**{field: value}).frozen_set_hash

    def test_changing_expected_direction_changes_hash(self) -> None:
        a = _set()
        flipped = (SelectedFactor("qual_roe", 1, "h_roe", "short"), a.selected[1])
        assert a.frozen_set_hash != _set(selected=flipped).frozen_set_hash

    def test_changing_a_member_definition_hash_changes_hash(self) -> None:
        a = _set()
        changed = (SelectedFactor("qual_roe", 1, "h_roe_v2", "long"), a.selected[1])
        assert a.frozen_set_hash != _set(selected=changed).frozen_set_hash

    def test_hash_order_independent_for_same_id_different_direction(self) -> None:
        # GPT cross-review hardening: two members sharing (factor_id, version,
        # definition_hash) but differing in expected_direction must hash identically
        # regardless of insertion order (the sort key now includes direction).
        members = (
            SelectedFactor("x", 1, "h", "long"),
            SelectedFactor("x", 1, "h", "short"),
        )
        a = _set(selected=members)
        b = _set(selected=tuple(reversed(members)))
        assert a.frozen_set_hash == b.frozen_set_hash


class TestSealKeyMigration:
    def test_two_claims_same_frozen_set_hash_one_wins(self, tmp_path: Path) -> None:
        store = HoldoutSealStore(tmp_path)
        key = _set().frozen_set_hash
        store.claim_holdout_access(
            design_hash="dh1", hypothesis_id="h1", structural_family="fam",
            profile_id="p", run_dir=str(tmp_path / "r1"), step_id="s1", seal_key=key,
        )
        # Same seal_key, DIFFERENT design_hash -> still sealed (seal is keyed by seal_key).
        with pytest.raises(ValueError, match="Holdout sealed"):
            store.claim_holdout_access(
                design_hash="dh2", hypothesis_id="h2", structural_family="fam",
                profile_id="p", run_dir=str(tmp_path / "r2"), step_id="s2", seal_key=key,
            )
        assert len(store.list_events(seal_key=key)) == 1

    def test_default_seal_key_is_design_hash_backcompat(self, tmp_path: Path) -> None:
        store = HoldoutSealStore(tmp_path)
        # claim WITHOUT seal_key -> seal_key defaults to design_hash
        store.claim_holdout_access(
            design_hash="dhX", hypothesis_id="h1", structural_family="fam",
            profile_id="p", run_dir=str(tmp_path / "r1"), step_id="s1",
        )
        with pytest.raises(ValueError, match="Holdout sealed"):
            store.claim_holdout_access(
                design_hash="dhX", hypothesis_id="h2", structural_family="fam",
                profile_id="p", run_dir=str(tmp_path / "r2"), step_id="s2",
            )
        rows = store.list_events(seal_key="dhX")
        assert len(rows) == 1
        assert rows.iloc[0]["design_hash"] == "dhX"

    def test_different_seal_keys_same_design_hash_are_independent(self, tmp_path: Path) -> None:
        store = HoldoutSealStore(tmp_path)
        store.claim_holdout_access(
            design_hash="dh", hypothesis_id="h1", structural_family="fam",
            profile_id="p", run_dir=str(tmp_path / "r1"), step_id="s1", seal_key="k_a",
        )
        # different seal_key -> independent budget, succeeds despite the same design_hash
        store.claim_holdout_access(
            design_hash="dh", hypothesis_id="h2", structural_family="fam",
            profile_id="p", run_dir=str(tmp_path / "r2"), step_id="s2", seal_key="k_b",
        )
        assert len(store.list_events(design_hash="dh")) == 2
        assert len(store.list_events(seal_key="k_a")) == 1
        assert len(store.list_events(seal_key="k_b")) == 1

    def test_old_design_hash_only_row_backfills_seal_key(self, tmp_path: Path) -> None:
        # A pre-P1.4 seal row written WITHOUT a seal_key column.
        store = HoldoutSealStore(tmp_path)
        legacy = pd.DataFrame([{
            "event_id": "old1", "recorded_at": "2025-01-01 00:00:00",
            "design_hash": "legacy_dh", "hypothesis_id": "h", "structural_family": "fam",
            "profile_id": "p", "run_dir": str(tmp_path / "r"), "step_id": "s", "stage": "oos_test",
        }])
        legacy.to_parquet(store.log_path, index=False)
        # _load backfills seal_key = design_hash, so a default-key re-claim is blocked.
        with pytest.raises(ValueError, match="Holdout sealed"):
            store.claim_holdout_access(
                design_hash="legacy_dh", hypothesis_id="h2", structural_family="fam",
                profile_id="p", run_dir=str(tmp_path / "r2"), step_id="s2",
            )
        assert len(store.list_events(seal_key="legacy_dh")) == 1


class TestVerifySealCLI:
    def test_verify_seal_resolves_by_design_hash_and_by_seal_key(self, tmp_path: Path, monkeypatch) -> None:
        # PR3 R6 Blocker 1: --seal-dir is REMOVED — verify-seal reads the ONE configured
        # canonical root; the test runs main() in-process with the resolver monkeypatched
        # (the seal world is never caller-selectable, not even for a read tool).
        import src.research_orchestrator.holdout_seal as hs_mod
        from workspace.scripts import hypothesis_cli

        monkeypatch.setattr(hs_mod, "resolve_configured_global_holdout_root",
                            lambda: tmp_path)
        store = HoldoutSealStore(tmp_path)
        design_hash, seal_key = "b" * 64, "a" * 64
        store.claim_holdout_access(
            design_hash=design_hash, hypothesis_id="h", structural_family="fam",
            profile_id="p", run_dir=str(tmp_path / "r"), step_id="s",
            stage="oos_test", seal_key=seal_key,
        )
        assert hypothesis_cli.main(
            ["verify-seal", "--seal-key", seal_key, "--expect-claims", "1"]
        ) == 0
        assert hypothesis_cli.main(
            ["verify-seal", design_hash, "--expect-claims", "1"]
        ) == 0
        # exit 1 = the OOS window was already touched (one claim exists, expecting none
        # would be a mismatch is covered elsewhere; here assert the malformed-hash path)
        assert hypothesis_cli.main(["verify-seal", "not-a-hash"]) == 2
