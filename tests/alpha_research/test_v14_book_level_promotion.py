"""v1.4 book-level-promotion amendment — pass-1 acceptance tests.

Covers the §5 matrix items implementable before PR3:
- test_book_seal_key_distinctness (round-2 N2): changes to construction, execution
  envelope, evaluation protocol, OOS window, or pass/fail bar each produce a DISTINCT
  ``book_seal_key``; two plans sharing a frozen set cannot share a key.
- test_book_multiplicity_budget (round-1 M3 / round-3 R3-M2): D6 counts distinct
  ``book_seal_key`` spends per window (``book_plan_hash`` grouping is disclosure-only);
  virgin-window warn-3 / hard-5 with refuse_without_override.
- ledger spend-unit semantics: two plans sharing a frozen set are TWO recorded spends;
  the legacy frozen-set path stays idempotent.

(The A3 writer-gate matrix lives in test_factor_registry.py; the A7 scope gate in
tests/research_orchestrator/test_pr9_validation_field_gate.py. The two component-
diagnostics context tests land with the PR3-stage helper per the amendment §5.)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.alpha_research.factor_eval_skill.identity import (
    BookSealIdentity,
    DeploymentFrozenPlan,
)
from src.alpha_research.factor_eval_skill.multiplicity import (
    ACTION_ACKNOWLEDGE,
    ACTION_DISCLOSE,
    ACTION_REFUSE,
    ACTION_REQUIRE,
    is_virgin_window,
    virgin_window_multiplicity,
)
from src.alpha_research.factor_eval_skill.stores import OosWindowLedgerStore


def _plan(**overrides) -> DeploymentFrozenPlan:
    base = dict(
        frozen_set_hash="fsh_1",
        envelope_hash="env_1",
        target_universe_declaration_hash="tud_1",
        deployment_universe="univ_liquid_top300",
        portfolio_side="long_only",
        construction={"score_to_weight": "topk_equal", "topk": 30},
        pre_declared_bar={"net_sharpe_min": 0.8, "mdd_max": -0.35},
    )
    base.update(overrides)
    return DeploymentFrozenPlan(**base)


def _identity(plan: DeploymentFrozenPlan, **overrides) -> BookSealIdentity:
    kwargs = dict(
        selected_set_hash="ssh_1",
        execution_envelope_hash="exec_profile_jq_daily",
        eval_protocol_hash="proto_1",
        oos_window_id="2026-03-01..2026-09-30",
    )
    kwargs.update(overrides)
    return BookSealIdentity.from_plan(plan, **kwargs)


class TestBookSealKeyDistinctness:
    def test_book_seal_key_distinctness(self):
        base = _identity(_plan())
        # Construction change flows through plan_hash.
        diff_construction = _identity(_plan(construction={"score_to_weight": "optimizer", "topk": 30}))
        # Bar change flows through plan_hash AND the explicit bar hash.
        diff_bar = _identity(_plan(pre_declared_bar={"net_sharpe_min": 1.0, "mdd_max": -0.30}))
        # Envelope / protocol / window changes are key material even with an
        # IDENTICAL plan (the round-2 N2 gap: plan_hash alone omits these).
        diff_envelope = _identity(_plan(), execution_envelope_hash="exec_profile_stress")
        diff_protocol = _identity(_plan(), eval_protocol_hash="proto_2")
        diff_window = _identity(_plan(), oos_window_id="2026-03-01..2026-12-31")

        keys = {
            "base": base.book_seal_key,
            "construction": diff_construction.book_seal_key,
            "bar": diff_bar.book_seal_key,
            "envelope": diff_envelope.book_seal_key,
            "protocol": diff_protocol.book_seal_key,
            "window": diff_window.book_seal_key,
        }
        assert len(set(keys.values())) == len(keys), f"colliding book_seal_keys: {keys}"

        # Two plans sharing a frozen set but differing in construction share
        # frozen_set_hash yet have distinct seal keys.
        assert base.frozen_set_hash == diff_construction.frozen_set_hash
        assert base.book_seal_key != diff_construction.book_seal_key

        # Determinism: same inputs -> same key.
        assert base.book_seal_key == _identity(_plan()).book_seal_key


class TestBookMultiplicityBudget:
    def _ledger(self, tmp_path: Path) -> OosWindowLedgerStore:
        return OosWindowLedgerStore(tmp_path / "skill_store")

    def test_two_plans_sharing_a_frozen_set_are_two_spends(self, tmp_path: Path):
        ledger = self._ledger(tmp_path)
        window = "2026-03-01..2026-09-30"
        a = _identity(_plan())
        b = _identity(_plan(construction={"score_to_weight": "optimizer", "topk": 30}))
        ledger.record_book_spend(oos_window_id=window, book_seal_key=a.book_seal_key,
                                 frozen_set_hash=a.frozen_set_hash)
        ledger.record_book_spend(oos_window_id=window, book_seal_key=b.book_seal_key,
                                 frozen_set_hash=b.frozen_set_hash)
        # Same frozen set, two seal keys -> TWO spend units (the old frozen-set
        # idempotency would have swallowed the second).
        assert len(ledger.distinct_spend_keys(window)) == 2
        # Book-spend idempotency is on (window, book_seal_key).
        ledger.record_book_spend(oos_window_id=window, book_seal_key=a.book_seal_key,
                                 frozen_set_hash=a.frozen_set_hash)
        assert len(ledger.distinct_spend_keys(window)) == 2

    def test_book_multiplicity_budget(self, tmp_path: Path):
        ledger = self._ledger(tmp_path)
        window = "2026-03-01..2026-09-30"

        # 0-2 spends: disclose. 3-4: acknowledge. >=5: refuse without override.
        report = virgin_window_multiplicity(ledger, window, pending_self=True)
        assert report.action == ACTION_DISCLOSE

        protocols = [f"proto_{i}" for i in range(5)]
        for i, proto in enumerate(protocols[:3]):
            ident = _identity(_plan(), eval_protocol_hash=proto)
            ledger.record_book_spend(oos_window_id=window, book_seal_key=ident.book_seal_key,
                                     frozen_set_hash=ident.frozen_set_hash)
        assert virgin_window_multiplicity(ledger, window).action == ACTION_ACKNOWLEDGE

        for proto in protocols[3:]:
            ident = _identity(_plan(), eval_protocol_hash=proto)
            ledger.record_book_spend(oos_window_id=window, book_seal_key=ident.book_seal_key,
                                     frozen_set_hash=ident.frozen_set_hash)
        report = virgin_window_multiplicity(ledger, window)
        assert report.n_spent == 5
        assert report.action == ACTION_REFUSE

        # A user-signed override recorded BEFORE the spend downgrades the refusal to
        # require_adjusted_or_override (the artifact must then report adjusted stats).
        report = virgin_window_multiplicity(ledger, window, override_recorded=True)
        assert report.action == ACTION_REQUIRE

    def test_a5_study_spends_count_against_the_budget(self, tmp_path: Path):
        ledger = self._ledger(tmp_path)
        window = "2026-03-01..2026-09-30"
        ledger.record_study_spend(oos_window_id=window, frozen_set_hash="study_fsh_1",
                                  override_id="fresh_window_override_001")
        ident = _identity(_plan())
        ledger.record_book_spend(oos_window_id=window, book_seal_key=ident.book_seal_key,
                                 frozen_set_hash=ident.frozen_set_hash)
        assert len(ledger.distinct_spend_keys(window)) == 2
        rows = ledger.list_all()
        assert set(rows["spend_unit_type"].dropna()) == {"a5_signal_replication_study", "book_seal"}

    def test_legacy_frozen_set_rows_still_count_and_stay_idempotent(self, tmp_path: Path):
        ledger = self._ledger(tmp_path)
        window = "2021-01-01..2026-02-27"
        ledger.record_spend(oos_window_id=window, frozen_set_hash="legacy_fsh")
        ledger.record_spend(oos_window_id=window, frozen_set_hash="legacy_fsh")
        assert ledger.distinct_spend_keys(window) == ["legacy_fsh"]


class TestVirginWindowDetection:
    def test_is_virgin_window(self):
        assert not is_virgin_window("2026-02-27")
        assert not is_virgin_window("2026-01-31")
        assert is_virgin_window("2026-02-28")
        assert is_virgin_window("2026-09-30")


class TestBookSealKeyRefusesBlankKey:
    def test_record_book_spend_requires_key(self, tmp_path: Path):
        ledger = OosWindowLedgerStore(tmp_path / "skill_store")
        with pytest.raises(ValueError, match=r"book_seal_key"):
            ledger.record_book_spend(oos_window_id="w", book_seal_key="  ",
                                     frozen_set_hash="fsh")


class TestSpendUnitIdempotencyIsolation:
    def test_book_first_then_a5_study_same_frozen_set_counts_two_spends(self, tmp_path: Path):
        # Implementation-review Blocker 2: a pre-existing BOOK row on (window, fsh) must
        # not swallow a later A5 study's spend record (order-dependent undercount).
        ledger = OosWindowLedgerStore(tmp_path / "skill_store")
        window = "2026-03-01..2026-09-30"
        ident = _identity(_plan(frozen_set_hash="fsh_shared"))
        ledger.record_book_spend(oos_window_id=window, book_seal_key=ident.book_seal_key,
                                 frozen_set_hash="fsh_shared")
        ledger.record_study_spend(oos_window_id=window, frozen_set_hash="fsh_shared",
                                  override_id="fresh_window_override_002")
        rows = ledger.list_all()
        assert set(rows["spend_unit_type"].dropna()) == {"book_seal", "a5_signal_replication_study"}
        assert len(ledger.distinct_spend_keys(window)) == 2
        # And the reverse order (study-first) still records both + stays idempotent.
        ledger.record_study_spend(oos_window_id=window, frozen_set_hash="fsh_shared")
        ledger.record_book_spend(oos_window_id=window, book_seal_key=ident.book_seal_key,
                                 frozen_set_hash="fsh_shared")
        assert len(ledger.list_all()) == 2

    def test_legacy_record_spend_not_masked_by_book_row(self, tmp_path: Path):
        ledger = OosWindowLedgerStore(tmp_path / "skill_store")
        window = "2021-01-01..2026-02-27"
        ident = _identity(_plan(frozen_set_hash="fsh_legacy"))
        ledger.record_book_spend(oos_window_id=window, book_seal_key=ident.book_seal_key,
                                 frozen_set_hash="fsh_legacy")
        ledger.record_spend(oos_window_id=window, frozen_set_hash="fsh_legacy")
        assert len(ledger.list_all()) == 2


class TestTudAliasFullPayload:
    """Implementation-review Blocker 3: the migration alias must carry the FULL payload —
    factor_version + real data/calendar policy identifiers — or refuse."""

    def _fields(self, **overrides):
        base = dict(
            alias_id="alias_x", alias_version="1", created_at="2026-07-03",
            recorded_before_stage7_freeze=True, factor_id="qual_roe", factor_version="1",
            definition_hash="dh", source_evidence_id="ev1", stage5_methodology_hash="m5",
            evidence_window="2014..2020", target_universe_id="theme:tuc",
            universe_definition_filters_json="{}", eligibility_policy="p", asof_policy="p",
            data_policy_ids_json='{"provider_build_id": "pb_1", "calendar_policy_id": "cp_1"}',
        )
        base.update(overrides)
        return base

    def test_full_payload_accepted(self, tmp_path: Path):
        from src.alpha_research.factor_eval_skill.stores import TudEquivalenceAliasStore

        row = TudEquivalenceAliasStore(tmp_path / "s").record_alias(**self._fields())
        assert row["alias_payload_hash"]

    def test_tud_alias_missing_factor_version_refused(self, tmp_path: Path):
        from src.alpha_research.factor_eval_skill.stores import TudEquivalenceAliasStore

        with pytest.raises(ValueError, match=r"factor_version"):
            TudEquivalenceAliasStore(tmp_path / "s").record_alias(
                **self._fields(factor_version="")
            )

    def test_tud_alias_missing_or_empty_data_policy_ids_refused(self, tmp_path: Path):
        from src.alpha_research.factor_eval_skill.stores import TudEquivalenceAliasStore

        store = TudEquivalenceAliasStore(tmp_path / "s")
        with pytest.raises(ValueError, match=r"data_policy_ids_json"):
            store.record_alias(**self._fields(data_policy_ids_json=""))
        with pytest.raises(ValueError, match=r"provider_build_id"):
            store.record_alias(**self._fields(data_policy_ids_json="{}"))
        with pytest.raises(ValueError, match=r"provider_build_id"):
            store.record_alias(**self._fields(
                data_policy_ids_json='{"provider_build_id": "", "calendar_policy_id": "cp"}'
            ))
        with pytest.raises(ValueError, match=r"canonical JSON"):
            store.record_alias(**self._fields(data_policy_ids_json="not json"))


class TestA8VirginWindowChokepoint:
    """Implementation-review Blocker 1: the orchestrator's universal design_hash seal-claim
    chokepoint refuses VIRGIN (post-2026-02-27) OOS windows until the PR3 book_seal_key
    path exists; already-burned windows still pass (the dry-run pilot path)."""

    def _context(self, tmp_path: Path, oos_end: str):
        from unittest.mock import MagicMock

        context = MagicMock()
        context.step.config = {"stage": "oos_test"}
        context.step.step_id = "oos_step"
        context.run_dir = tmp_path / "run"
        context.resumed = False
        context.profile.profile_id = "hypothesis_validation"
        context.registry_dirs = {"holdout_seal_dir": str(tmp_path / "seals")}
        hyp = context.request.hypothesis
        hyp.time_split.oos_start = "2021-01-01"
        hyp.time_split.oos_end = oos_end
        hyp.time_split.to_dict.return_value = {
            "is_start": "2014-01-01", "is_end": "2020-12-31",
            "oos_start": "2021-01-01", "oos_end": oos_end,
        }
        hyp.design_hash.return_value = "dh_a8_test"
        hyp.hypothesis_id = "hyp_a8"
        hyp.structural_family.return_value = "fam_a8"
        hyp.prescription = None
        return context

    def test_a8_legacy_design_hash_oos_handler_refuses_virgin_window(self, tmp_path: Path):
        from unittest.mock import patch

        from src.research_orchestrator.steps import _claim_holdout_access_if_needed

        context = self._context(tmp_path, oos_end="2026-09-30")
        with patch("src.research_orchestrator.steps._assert_cicc_oos_quarantine"):
            with pytest.raises(RuntimeError, match=r"v1.4_A8_virgin_window_legacy_path_blocked"):
                _claim_holdout_access_if_needed(context)

    def test_burned_window_still_reaches_the_legacy_claim(self, tmp_path: Path):
        from unittest.mock import patch

        from src.research_orchestrator.holdout_seal import HoldoutSealStore
        from src.research_orchestrator.steps import _claim_holdout_access_if_needed

        context = self._context(tmp_path, oos_end="2026-02-27")
        with patch("src.research_orchestrator.steps._assert_cicc_oos_quarantine"):
            _claim_holdout_access_if_needed(context)  # must NOT raise the A8 guard
        events = HoldoutSealStore(tmp_path / "seals").list_events()
        assert not events.empty  # the burned-window claim was recorded (pilot path alive)


class TestA8SealedBacktestRunner:
    """Implementation-review round-2 Blocker 1: SealedBacktestRunner._claim_if_oos is a
    SECOND legacy claim path (direct HoldoutSealStore claim, effective_seal_key falls
    back to design_hash) — the shared A8 guard must refuse virgin windows THERE too,
    before any seal row is written, on every public runner entry."""

    @pytest.fixture(autouse=True)
    def _canonical_at_tmp(self, tmp_path, monkeypatch):
        # PR3 R6 Blocker 1: HoldoutContext has NO seal_store_dir — the runner claims
        # against the configured canonical root. Pin it to THIS class's expected dir
        # (applied after the global conftest quarantine fixture, so this wins).
        import src.research_orchestrator.holdout_seal as hs_mod

        monkeypatch.setattr(hs_mod, "resolve_configured_global_holdout_root",
                            lambda: tmp_path / "seals")

    def _runner(self, tmp_path: Path):
        from src.research_orchestrator.sealed_backtest_runner import (
            HoldoutContext,
            SealedBacktestRunner,
        )

        ctx = HoldoutContext(
            design_hash="dh_a8_runner", hypothesis_id="hyp_a8_runner",
            structural_family="fam_a8", run_dir=str(tmp_path / "run"),
            step_id="oos_step", stage="oos_test", allow_same_run=False,
        )
        return SealedBacktestRunner(ctx)

    def _no_seal_written(self, tmp_path: Path) -> bool:
        from src.research_orchestrator.holdout_seal import HoldoutSealStore

        return HoldoutSealStore(tmp_path / "seals").list_events().empty

    def test_a8_sealed_backtest_runner_refuses_virgin_window_before_claim(self, tmp_path: Path):
        runner = self._runner(tmp_path)
        with pytest.raises(RuntimeError, match=r"v1.4_A8_virgin_window_legacy_path_blocked"):
            runner._claim_if_oos({"stage": "oos_test", "oos_start": "2026-03-01",
                                  "oos_end": "2026-09-30"})
        assert self._no_seal_written(tmp_path)

    def test_a8_event_backtest_handler_refuses_virgin_window_through_runner_and_writes_no_seal(
        self, tmp_path: Path
    ):
        from unittest.mock import MagicMock

        runner = self._runner(tmp_path)
        backtester = MagicMock()
        with pytest.raises(RuntimeError, match=r"v1.4_A8_virgin_window_legacy_path_blocked"):
            runner.run_event_driven(
                time_split={"stage": "oos_test", "oos_end": "2026-06-30"},
                backtester=backtester,
            )
        backtester.run.assert_not_called()
        assert self._no_seal_written(tmp_path)

    def test_a8_vectorized_oos_handler_refuses_virgin_window_through_runner_and_writes_no_seal(
        self, tmp_path: Path
    ):
        from unittest.mock import MagicMock

        runner = self._runner(tmp_path)
        backtester = MagicMock()
        with pytest.raises(RuntimeError, match=r"v1.4_A8_virgin_window_legacy_path_blocked"):
            runner.run_vectorized(
                time_split={"stage": "oos_test", "oos_end": "2026-06-30"},
                backtester=backtester,
            )
        backtester.run.assert_not_called()
        assert self._no_seal_written(tmp_path)

    def test_runner_burned_window_still_claims(self, tmp_path: Path):
        from src.research_orchestrator.holdout_seal import HoldoutSealStore

        runner = self._runner(tmp_path)
        runner._claim_if_oos({"stage": "oos_test", "oos_start": "2021-01-01",
                              "oos_end": "2026-02-27"})  # must NOT raise
        assert not HoldoutSealStore(tmp_path / "seals").list_events().empty

    def test_runner_missing_oos_end_fails_closed(self, tmp_path: Path):
        runner = self._runner(tmp_path)
        with pytest.raises(RuntimeError, match=r"unable_to_determine_oos_end"):
            runner._claim_if_oos({"stage": "oos_test"})
        assert self._no_seal_written(tmp_path)

    # ── round-3 Blocker 1: the claim decision is CONTEXT-driven, not payload-driven ──

    def test_runner_oos_context_missing_stage_still_claims_or_refuses_virgin_window(
        self, tmp_path: Path
    ):
        from src.research_orchestrator.holdout_seal import HoldoutSealStore

        # ctx.stage == "oos_test" + a payload WITHOUT "stage": previously this skipped
        # claim AND guard entirely (the round-3 bypass). Now: virgin window -> A8 refusal…
        runner = self._runner(tmp_path)
        with pytest.raises(RuntimeError, match=r"v1.4_A8_virgin_window_legacy_path_blocked"):
            runner._claim_if_oos({"oos_start": "2026-03-01", "oos_end": "2026-09-30"})
        assert self._no_seal_written(tmp_path)
        # …and a burned window CLAIMS (the seal is spent, not silently skipped).
        runner._claim_if_oos({"oos_start": "2021-01-01", "oos_end": "2026-02-27"})
        assert not HoldoutSealStore(tmp_path / "seals").list_events().empty

    def test_runner_stage_mismatch_refuses_before_claim(self, tmp_path: Path):
        runner = self._runner(tmp_path)
        with pytest.raises(ValueError, match=r"stage mismatch"):
            runner._claim_if_oos({"stage": "is_only", "oos_start": "2021-01-01",
                                  "oos_end": "2026-02-27"})
        assert self._no_seal_written(tmp_path)

    def test_workspace_pipeline_oos_context_missing_stage_cannot_install_claimed_context_without_claim(
        self, tmp_path: Path
    ):
        from unittest.mock import MagicMock

        from src.research_orchestrator.holdout_seal import HoldoutSealStore

        # Virgin window + stage-less payload through the PUBLIC pipeline entry: the A8
        # guard fires via the context-driven claim path — the pipeline never runs and no
        # ResearchAccessContext with holdout_seal_claimed=True can be installed.
        runner = self._runner(tmp_path)
        pipeline_fn = MagicMock(return_value="ok")
        with pytest.raises(RuntimeError, match=r"v1.4_A8_virgin_window_legacy_path_blocked"):
            runner.run_workspace_pipeline(
                pipeline_fn=pipeline_fn,
                time_split={"oos_start": "2026-03-01", "oos_end": "2026-09-30"},
                pipeline_args={},
                provider_build_id="pb_test",
                calendar_policy_id="cp_test",
            )
        pipeline_fn.assert_not_called()
        assert self._no_seal_written(tmp_path)
        # Burned window: the claim happens BEFORE the claimed-context install — the seal
        # event must exist by the time the pipeline runs (the flag is now truthful).
        seen = {}

        def probe(*args, **kwargs):
            seen["seal_recorded"] = not HoldoutSealStore(tmp_path / "seals").list_events().empty
            return "ok"

        runner.run_workspace_pipeline(
            pipeline_fn=probe,
            time_split={"is_start": "2014-01-01", "is_end": "2020-12-31",
                        "oos_start": "2021-01-01", "oos_end": "2026-02-27"},
            pipeline_args={},
            provider_build_id="pb_test",
            calendar_policy_id="cp_test",
        )
        assert seen.get("seal_recorded") is True
