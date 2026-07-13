"""v1.4 PR3 acceptance tests — the book_seal_key claim path, the in-context component
diagnostics (the two amendment-named context tests), the fail-closed pre-declared bar,
the A5 fresh-window enforcement, and the A8 strategy-promotion wiring.

Amendment §5 required tests landed here:
- test_component_diagnostics_no_second_seal
- test_component_diagnostics_preserves_active_book_research_access_context
- test_component_diagnostics_refuses_bare_claim_false_without_book_context
(plus the book-runner spend semantics, the promotion-gate matrix, and cmd_seal A5.)
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pytest

from src.alpha_research.factor_eval_skill.book_seal import (
    BookSealError,
    evaluate_pre_declared_bar,
    run_book_sealed_evaluation,
    run_component_diagnostics_in_book_context,
)
from src.alpha_research.factor_eval_skill.identity import BookSealIdentity, DeploymentFrozenPlan
from src.alpha_research.factor_eval_skill.stores import OosWindowLedgerStore
from src.research_orchestrator.holdout_seal import HoldoutSealStore
from src.research_orchestrator.research_access_context import (
    ResearchAccessContext,
    get_research_access_context,
    research_access_context,
)

BURNED = ("2021-01-01", "2026-02-27")
VIRGIN = ("2026-03-01", "2026-06-30")


# ───────────────────────────────────────────────────────────── fixtures ──

@dataclass(frozen=True)
class _Member:
    factor_id: str
    expected_direction: str


@dataclass(frozen=True)
class _FrozenSet:
    selected: tuple
    frozen_set_hash: str = "fsh_pr3"


def _frozen_set():
    return _FrozenSet(selected=(_Member("fac_a", "long"), _Member("fac_b", "short")))


def _plan(**overrides) -> DeploymentFrozenPlan:
    base = dict(
        frozen_set_hash="fsh_pr3",
        envelope_hash="env_pr3",
        target_universe_declaration_hash="tud_pr3",
        deployment_universe="univ_liquid_top300",
        portfolio_side="long_only",
        construction={"score_to_weight": "topk_equal", "topk": 30},
        pre_declared_bar={"net_sharpe_min": 0.8, "mdd_max": -0.35},
    )
    base.update(overrides)
    return DeploymentFrozenPlan(**base)


def _metrics_fn(**_kw):
    # fac_a (held long, +icir, ls>1) PASSES the reference bar; fac_b (held short,
    # aligned ls = +0.5 < 1.0 floor) FAILS it — the diagnostics must show both.
    return (
        {
            "fac_a": {"oos_rank_icir": 0.2, "oos_ls_sharpe": 1.4, "ls_sharpe_horizon": 5},
            "fac_b": {"oos_rank_icir": -0.1, "oos_ls_sharpe": -0.5, "ls_sharpe_horizon": 5},
        },
        "2026-02-27",
    )


def _passing_backtest():
    return {"net_sharpe": 0.95, "mdd": -0.28, "cagr": 0.21}


def _run(tmp_path: Path, *, mode="dryrun", window=BURNED, backtest=None, metrics_fn=_metrics_fn,
         allow_same_run=False, step_id="s6", seal_dir=None, ledger_dir=None, **overrides):
    kwargs = dict(
        plan=_plan(),
        selected_set_hash="ssh_pr3",
        execution_envelope_hash="exec_jq_daily",
        eval_protocol_hash="proto_pr3",
        oos_start=window[0], oos_end=window[1],
        book_backtest_fn=backtest or _passing_backtest,
        frozen_set=_frozen_set(),
        factor_exprs={"fac_a": "$close", "fac_b": "$open"},
        qlib_dir=str(tmp_path / "qlib"),
        seal_store_dir=seal_dir or (tmp_path / "seals"),
        ledger_root=ledger_dir or (tmp_path / "ledger"),
        run_dir=str(tmp_path / "run"), step_id=step_id,
        hypothesis_id="book_pr3", provider_build_id="pb_test", calendar_policy_id="cp_test",
        mode=mode, allow_same_run=allow_same_run,
        compute_metrics_fn=metrics_fn,
    )
    kwargs.update(overrides)
    return run_book_sealed_evaluation(**kwargs)


def _expected_key(window=BURNED) -> str:
    return BookSealIdentity.from_plan(
        _plan(), selected_set_hash="ssh_pr3", execution_envelope_hash="exec_jq_daily",
        eval_protocol_hash="proto_pr3", oos_window_id=f"{window[0]}..{window[1]}",
    ).book_seal_key


def _book_ctx(seal_key: str, window=BURNED, *, claimed=True, stage="oos_test") -> ResearchAccessContext:
    return ResearchAccessContext(
        run_id="r", step_id="s", stage=stage, design_hash="dh",
        allowed_start=pd.Timestamp(window[0]), allowed_end=pd.Timestamp(window[1]),
        provider_build_id="pb_test", calendar_policy_id="cp_test",
        holdout_seal_claimed=claimed, seal_key=seal_key,
    )


# ─────────────────────────────────────────────── pre-declared bar (fail-closed) ──

class TestEvaluatePreDeclaredBar:
    def test_min_max_semantics(self):
        v = evaluate_pre_declared_bar({"net_sharpe": 0.9, "turnover": 0.5},
                                      {"net_sharpe_min": 0.8, "turnover_max": 0.6})
        assert v.bar_passed is True
        v = evaluate_pre_declared_bar({"net_sharpe": 0.7, "turnover": 0.5},
                                      {"net_sharpe_min": 0.8, "turnover_max": 0.6})
        assert v.bar_passed is False

    def test_mdd_max_is_a_magnitude_cap_under_negative_convention(self):
        # repo convention: mdd is NEGATIVE. mdd_max=-0.35 == "no deeper than 35%".
        assert evaluate_pre_declared_bar({"mdd": -0.30}, {"mdd_max": -0.35}).bar_passed is True
        assert evaluate_pre_declared_bar({"mdd": -0.40}, {"mdd_max": -0.35}).bar_passed is False

    def test_ambiguous_drawdown_sign_refused(self):
        with pytest.raises(BookSealError, match="ambiguous drawdown sign"):
            evaluate_pre_declared_bar({"mdd": 0.30}, {"mdd_max": -0.35})
        with pytest.raises(BookSealError, match="ambiguous drawdown sign"):
            evaluate_pre_declared_bar({"mdd": -0.30}, {"mdd_max": 0.35})

    def test_missing_metric_never_passes(self):
        with pytest.raises(BookSealError, match="missing"):
            evaluate_pre_declared_bar({"net_sharpe": 0.9}, {"mdd_max": -0.35})

    def test_nan_and_unknown_suffix_and_empty_bar_refused(self):
        with pytest.raises(BookSealError, match="NaN"):
            evaluate_pre_declared_bar({"net_sharpe": float("nan")}, {"net_sharpe_min": 0.8})
        with pytest.raises(BookSealError, match="_min.*_max|explicit comparator"):
            evaluate_pre_declared_bar({"x": 1.0}, {"x": 1.0})
        with pytest.raises(BookSealError, match="empty"):
            evaluate_pre_declared_bar({"x": 1.0}, {})


# ───────────────────────────── component diagnostics (the amendment's 2 context tests) ──

class TestComponentDiagnosticsContext:
    def _call(self, key=None, window=BURNED, metrics_fn=_metrics_fn):
        return run_component_diagnostics_in_book_context(
            book_seal_key=key or _expected_key(window), book_plan_hash=_plan().plan_hash,
            frozen_set=_frozen_set(), factor_exprs={"fac_a": "$close", "fac_b": "$open"},
            oos_start=window[0], oos_end=window[1], qlib_dir="qlib",
            compute_metrics_fn=metrics_fn,
        )

    def test_component_diagnostics_refuses_bare_claim_false_without_book_context(self):
        # no active context at all -> refused (a bare no-seal call is NOT a reuse path)
        assert get_research_access_context() is None
        with pytest.raises(BookSealError, match="ACTIVE claimed book"):
            self._call()
        # an active but UNCLAIMED context -> refused (the N3 no-seal-context door)
        with research_access_context(_book_ctx(_expected_key(), claimed=False)):
            with pytest.raises(BookSealError, match="holdout_seal_claimed"):
                self._call()

    def test_component_diagnostics_refuses_foreign_seal_key(self):
        with research_access_context(_book_ctx("some_other_key")):
            with pytest.raises(BookSealError, match="!= book_seal_key"):
                self._call()

    def test_component_diagnostics_refuses_window_not_covered(self):
        with research_access_context(_book_ctx(_expected_key(), window=("2021-01-01", "2024-12-31"))):
            with pytest.raises(BookSealError, match="not covered"):
                self._call()

    def test_component_diagnostics_preserves_active_book_research_access_context(self):
        # the metric computation runs under the SAME context object — no nested install
        installed = _book_ctx(_expected_key())
        seen = {}

        def probe(**kw):
            seen["ctx"] = get_research_access_context()
            return _metrics_fn()

        with research_access_context(installed):
            out = self._call(metrics_fn=probe)
        assert seen["ctx"] is installed  # identity, not equality: no nested context was installed
        assert out["n_components"] == 2

    def test_rows_mint_no_status_and_carry_the_m3_flags(self):
        with research_access_context(_book_ctx(_expected_key())):
            out = self._call()
        assert {r["component_factor_id"] for r in out["rows"]} == {"fac_a", "fac_b"}
        for row in out["rows"]:
            assert row["run_type"] == "book_component_diagnostic"
            assert row["spent_in_book_context"] is True
            assert row["fresh_oos_eligible"] is False
            assert row["promotion_eligible"] is False
            assert row["book_plan_hash"] == _plan().plan_hash
        # the retired factor-level bar is a REFERENCE line: fac_a passes it, fac_b fails
        by_id = {r["component_factor_id"]: r for r in out["rows"]}
        assert by_id["fac_a"]["reference_pass"] is True
        assert by_id["fac_b"]["reference_pass"] is False


# ─────────────────────────────────────────────── the book sealed evaluation ──

class TestRunBookSealedEvaluation:
    def test_dryrun_burned_window_produces_full_artifact_one_seal(self, tmp_path):
        art = _run(tmp_path)
        assert art["mode"] == "dryrun" and art["virgin_window"] is False
        assert art["book_seal_key"] == _expected_key()
        assert art["book_verdict"]["bar_passed"] is True
        assert art["component_diagnostics_ok"] is True
        assert art["component_diagnostics"]["n_components"] == 2
        assert art["promotion_eligible"] is False  # dryrun is NEVER promotable
        # exactly ONE seal event, keyed by book_seal_key with plan_hash as the audit design_hash
        events = HoldoutSealStore(tmp_path / "seals").list_events()
        assert len(events) == 1
        assert events.iloc[0]["seal_key"] == _expected_key()
        assert events.iloc[0]["design_hash"] == _plan().plan_hash
        # ledger recorded the BOOK spend unit
        ledger = OosWindowLedgerStore(tmp_path / "ledger")
        assert ledger.distinct_spend_keys(f"{BURNED[0]}..{BURNED[1]}") == [_expected_key()]

    def test_component_diagnostics_no_second_seal(self, tmp_path):
        # the diagnostics leg ran (2 components) and the seal store holds EXACTLY one event
        art = _run(tmp_path)
        assert art["component_diagnostics"]["n_components"] == 2
        assert len(HoldoutSealStore(tmp_path / "seals").list_events()) == 1

    def test_dryrun_refuses_virgin_window_before_any_claim(self, tmp_path):
        with pytest.raises(BookSealError, match="dryrun REFUSED on a virgin"):
            _run(tmp_path, window=VIRGIN)
        assert HoldoutSealStore(tmp_path / "seals").list_events().empty

    def test_live_one_shot_and_same_run_resume(self, tmp_path):
        art = _run(tmp_path, mode="live")
        assert art["promotion_eligible"] is True
        # a SECOND spend of the same book_seal_key is refused (one-shot)
        with pytest.raises(ValueError, match="Holdout sealed"):
            _run(tmp_path, mode="live")
        # crash-resume: same run_dir + step_id with allow_same_run returns (no new event)
        art2 = _run(tmp_path, mode="live", allow_same_run=True)
        assert art2["book_seal_key"] == art["book_seal_key"]
        assert len(HoldoutSealStore(tmp_path / "seals").list_events()) == 1

    def test_spend_on_attempt_backtest_failure_consumes_the_seal(self, tmp_path):
        def boom():
            raise RuntimeError("engine crashed")

        with pytest.raises(RuntimeError, match="engine crashed"):
            _run(tmp_path, backtest=boom)
        # the slot is SPENT even though the run failed (spend-on-attempt)
        assert len(HoldoutSealStore(tmp_path / "seals").list_events()) == 1
        # recovery is same-run resume only
        art = _run(tmp_path, allow_same_run=True)
        assert art["book_verdict"]["bar_passed"] is True

    def test_diagnostics_failure_recorded_blocks_promotion_but_keeps_verdict(self, tmp_path):
        def broken_metrics(**kw):
            raise RuntimeError("diagnostics leg failed")

        art = _run(tmp_path, mode="live", metrics_fn=broken_metrics)
        assert art["book_verdict"]["bar_passed"] is True          # the book leg survived
        assert art["component_diagnostics_ok"] is False
        assert "diagnostics leg failed" in art["component_diagnostics_error"]
        assert art["promotion_eligible"] is False

    def test_blank_provider_ids_refused_before_claim(self, tmp_path):
        with pytest.raises(BookSealError, match="provider_build_id"):
            _run(tmp_path, provider_build_id="")
        assert HoldoutSealStore(tmp_path / "seals").list_events().empty

    def test_live_virgin_hard_budget_refuses_before_claim(self, tmp_path):
        ledger = OosWindowLedgerStore(tmp_path / "ledger")
        window_id = f"{VIRGIN[0]}..{VIRGIN[1]}"
        for i in range(5):
            ledger.record_book_spend(oos_window_id=window_id, book_seal_key=f"k{i}",
                                     frozen_set_hash=f"f{i}")
        with pytest.raises(BookSealError, match="HARD STOP"):
            _run(tmp_path, mode="live", window=VIRGIN)
        assert HoldoutSealStore(tmp_path / "seals").list_events().empty

    def test_failed_bar_yields_not_promotion_eligible(self, tmp_path):
        art = _run(tmp_path, mode="live", backtest=lambda: {"net_sharpe": 0.5, "mdd": -0.40})
        assert art["book_verdict"]["bar_passed"] is False
        assert art["promotion_eligible"] is False


# ───────────────────────────────────────── A5 fresh-window enforcement ──

class TestA5FreshWindowEnforcement:
    def test_run_sealed_oos_virgin_claim_requires_override(self):
        from src.alpha_research.factor_eval_skill.sealed_oos import run_sealed_oos

        with pytest.raises(ValueError, match="v1.4_A5_fresh_window_override_required"):
            run_sealed_oos(frozen_set=None, factor_exprs={}, oos_start=VIRGIN[0], oos_end=VIRGIN[1],
                           qlib_dir="q", seal_root="s", run_dir="r", design_hash="d",
                           hypothesis_id="h", claim_seal=True)

    def test_cmd_seal_live_virgin_requires_override_before_any_oos_work(self, tmp_path):
        import json

        from src.alpha_research.factor_eval_skill.orchestration import (
            FactorEvalContext,
            FactorEvalError,
            FactorIdentity,
            cmd_characterize,
            cmd_declare_target,
            cmd_gate,
            cmd_register,
            cmd_seal,
            cmd_select,
        )
        from src.alpha_research.factor_eval_skill.stage3_reader import ALL_UNIVERSES

        rows = [{"factor": "tf", "universe_id": u, "heldout_rank_icir": 0.45,
                 "mean_rank_ic": 0.045, "sign_consistency": 1.0, "coverage_tier": "broad",
                 "effective_ic_days": 2600, "field_eligible": True,
                 "layer1_methodology_hash": "l1hash"} for u in ALL_UNIVERSES]
        matrix = tmp_path / "m.jsonl"
        matrix.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
        ctx = FactorEvalContext.create(
            run_dir=tmp_path / "run", store_root=tmp_path / "store", registry_root=tmp_path / "reg",
            resolve_factor=lambda fid: FactorIdentity(fid, f"def_{fid}", 2, "", "$close"),
        )
        ctx.holdout_seal_root = tmp_path / "holdout"
        cmd_register(ctx, factor_id="tf", mode="deployment_bound", evidence_tier="theory_a_priori",
                     direction_source="theory", role="ranking", role_direction="long")
        cmd_declare_target(ctx, target_universe_id="univ_liquid_top300", eligibility_policy="l",
                           asof_policy="pit_lag_1")
        cmd_characterize(ctx, matrix_path=matrix)
        cmd_gate(ctx)
        cmd_select(ctx, matrix_path=matrix, pool={"tf": "x"}, caps={"x": 1}, floor=0.10)
        # live on a VIRGIN window without the A5 override id -> refused before any OOS access
        with pytest.raises(FactorEvalError, match="v1.4_A5_fresh_window_override_required"):
            cmd_seal(ctx, mode="live", oos_start=VIRGIN[0], oos_end=VIRGIN[1])
        assert HoldoutSealStore(ctx.holdout_seal_root).list_events().empty
        assert OosWindowLedgerStore(ctx.store_root).distinct_spend_keys(
            f"{VIRGIN[0]}..{VIRGIN[1]}") == []

        # with the override id, the spend is recorded as an A5 STUDY row (run_sealed_oos mocked)
        import src.alpha_research.factor_eval_skill.orchestration as orch

        class _V:
            n_pass, n_total, results = 1, 1, ({"factor": "tf", "pass": True},)

        real = orch.run_sealed_oos if hasattr(orch, "run_sealed_oos") else None
        import src.alpha_research.factor_eval_skill.sealed_oos as so
        orig = so.run_sealed_oos
        so.run_sealed_oos = lambda **kw: {"reproduction": {}, "verdict": _V()}
        try:
            out = cmd_seal(ctx, mode="live", oos_start=VIRGIN[0], oos_end=VIRGIN[1],
                           fresh_window_override_id="fresh_override_001")
        finally:
            so.run_sealed_oos = orig
        assert out["n_pass"] == 1
        ledger_rows = OosWindowLedgerStore(ctx.store_root).list_all()
        window_rows = ledger_rows[ledger_rows["oos_window_id"] == f"{VIRGIN[0]}..{VIRGIN[1]}"]
        assert set(window_rows["spend_unit_type"].dropna()) == {"a5_signal_replication_study"}


# ───────────────────────────────────── A8 strategy-promotion wiring ──

def _p11_fields(sha="sha_pr3"):
    return {
        "independent_reproduction": {"source": "qlib_windowed_features"},
        "unsafe_pit_dates_lint": "passed",
        "synthetic_lookahead_canary": "passed",
        "restatement_canary": "passed",
        "q0_canary_multiperiod": "passed",
        "q0_canary_stateful_restatement": "passed",
        "q0_canary_missing_field": "passed",
        "availability_assertion": "passed",
        "live_provider_parity": "passed",
        "dirty_tree": False,
        "git_sha": sha,
    }


class TestStrategyPromotionWiring:
    def _store(self, tmp_path):
        from src.research_orchestrator.registries.strategy_registry import StrategyRegistryStore

        return StrategyRegistryStore(tmp_path / "strategy_registry")

    def _published(self, tmp_path, art):
        from src.research_orchestrator.registries.strategy_registry import (
            publish_strategy_candidate,
        )

        store = self._store(tmp_path)
        publish_strategy_candidate(store, object_name="book_pr3", artifact=art,
                                   run_dir=tmp_path / "run")
        return store

    def test_publish_and_full_valid_promotion(self, tmp_path):
        art = _run(tmp_path, mode="live")
        store = self._published(tmp_path, art)
        row = store.find_current(object_type="strategy_candidate", object_name="book_pr3")
        assert len(row) == 1 and row.iloc[0]["definition_hash"] == art["book_seal_key"]
        result = store.set_status(
            object_id="strategy_candidate::book_pr3", status="approved", reason="test",
            promotion_evidence={**_p11_fields(), "book_seal": art},
            current_git_sha="sha_pr3", holdout_seal_dir=tmp_path / "seals",
        )
        assert result["new_status"] == "approved"

    def test_approved_requires_book_seal_section(self, tmp_path):
        from src.research_orchestrator.release_gate import PromotionGateError

        art = _run(tmp_path, mode="live")
        store = self._published(tmp_path, art)
        with pytest.raises(PromotionGateError, match="book_seal"):
            store.set_status(object_id="strategy_candidate::book_pr3", status="approved",
                             reason="t", promotion_evidence=_p11_fields(),
                             current_git_sha="sha_pr3", holdout_seal_dir=tmp_path / "seals")

    def test_approved_requires_seal_store_dir(self, tmp_path):
        from src.research_orchestrator.release_gate import PromotionGateError

        art = _run(tmp_path, mode="live")
        store = self._published(tmp_path, art)
        with pytest.raises(PromotionGateError, match="holdout_seal_dir"):
            store.set_status(object_id="strategy_candidate::book_pr3", status="approved",
                             reason="t", promotion_evidence={**_p11_fields(), "book_seal": art},
                             current_git_sha="sha_pr3")

    def test_tampered_key_refused(self, tmp_path):
        from src.research_orchestrator.release_gate import PromotionGateError

        art = _run(tmp_path, mode="live")
        store = self._published(tmp_path, art)
        bad = dict(art)
        bad["book_seal_key"] = "0" * 64
        with pytest.raises(PromotionGateError, match="does not recompute"):
            store.set_status(object_id="strategy_candidate::book_pr3", status="approved",
                             reason="t", promotion_evidence={**_p11_fields(), "book_seal": bad},
                             current_git_sha="sha_pr3", holdout_seal_dir=tmp_path / "seals")

    def test_missing_seal_event_refused(self, tmp_path):
        from src.research_orchestrator.release_gate import PromotionGateError

        art = _run(tmp_path, mode="live")
        store = self._published(tmp_path, art)
        with pytest.raises(PromotionGateError, match="no holdout seal event"):
            store.set_status(object_id="strategy_candidate::book_pr3", status="approved",
                             reason="t", promotion_evidence={**_p11_fields(), "book_seal": art},
                             current_git_sha="sha_pr3",
                             holdout_seal_dir=tmp_path / "EMPTY_seals")

    def test_dryrun_artifact_never_promotable(self, tmp_path):
        from src.research_orchestrator.release_gate import PromotionGateError

        art = _run(tmp_path, mode="dryrun")
        store = self._published(tmp_path, art)
        with pytest.raises(PromotionGateError, match="mode must be 'live'"):
            store.set_status(object_id="strategy_candidate::book_pr3", status="approved",
                             reason="t", promotion_evidence={**_p11_fields(), "book_seal": art},
                             current_git_sha="sha_pr3", holdout_seal_dir=tmp_path / "seals")

    def test_failed_bar_refused(self, tmp_path):
        from src.research_orchestrator.release_gate import PromotionGateError

        art = _run(tmp_path, mode="live", backtest=lambda: {"net_sharpe": 0.5, "mdd": -0.40})
        store = self._published(tmp_path, art)
        with pytest.raises(PromotionGateError, match="bar_passed"):
            store.set_status(object_id="strategy_candidate::book_pr3", status="approved",
                             reason="t", promotion_evidence={**_p11_fields(), "book_seal": art},
                             current_git_sha="sha_pr3", holdout_seal_dir=tmp_path / "seals")

    def test_broken_diagnostics_refused(self, tmp_path):
        from src.research_orchestrator.release_gate import PromotionGateError

        def broken_metrics(**kw):
            raise RuntimeError("boom")

        art = _run(tmp_path, mode="live", metrics_fn=broken_metrics)
        store = self._published(tmp_path, art)
        with pytest.raises(PromotionGateError, match="component_diagnostics_ok"):
            store.set_status(object_id="strategy_candidate::book_pr3", status="approved",
                             reason="t", promotion_evidence={**_p11_fields(), "book_seal": art},
                             current_git_sha="sha_pr3", holdout_seal_dir=tmp_path / "seals")

    def test_non_privileged_transitions_unchanged(self, tmp_path):
        art = _run(tmp_path, mode="dryrun")
        store = self._published(tmp_path, art)
        out = store.set_status(object_id="strategy_candidate::book_pr3", status="under_review",
                               reason="triage")
        assert out["new_status"] == "under_review"

    def test_publish_refuses_wrong_artifact_type(self, tmp_path):
        from src.research_orchestrator.registries.strategy_registry import (
            publish_strategy_candidate,
        )

        with pytest.raises(ValueError, match="book_sealed_evaluation"):
            publish_strategy_candidate(self._store(tmp_path), object_name="x",
                                       artifact={"artifact_type": "something_else"},
                                       run_dir=tmp_path)
