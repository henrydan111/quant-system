"""v1.4 PR3 acceptance tests (post-R1-REWORK) — the book_seal_key claim path as a
persisted state machine, the in-context component diagnostics, the fail-closed
pre-declared bar, consume-once override authorizations, the atomic spend reservation,
and the canonical-artifact promotion gate.

Pins the GPT R1 adversarial probes:
- re-run of a COMPLETED evaluation refused (no verdict flip);
- changed-request resume refused; diagnostics-only resume never re-runs the backtest;
- empty/NaN component metrics -> diagnostics_failed, never healthy;
- foreign/tampered/edited-verdict artifacts refused at the promotion gate;
- invented override strings refused (authorizations are pre-recorded + consume-once);
- direct reproduce_sealed_oos on a virgin window refused without a real authorization;
- infinite metric refused by the bar; dryrun stores must be run-local.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pytest

from src.alpha_research.factor_eval_skill.book_seal import (
    BookSealDiagnosticsError,
    BookSealError,
    evaluate_pre_declared_bar,
    run_book_sealed_evaluation,
    run_component_diagnostics_in_book_context,
)
from src.alpha_research.factor_eval_skill.book_seal_stores import (
    BookSealArtifactStore,
    BookSealStoreError,
    OverrideAuthorizationStore,
    StrategyComponentDiagnosticStore,
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
BURNED_ID = f"{BURNED[0]}..{BURNED[1]}"


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
    # fac_a (held long) PASSES the reference bar; fac_b (held short, aligned ls +0.5 < 1.0)
    # FAILS it — both rows must appear, with finite metrics.
    return (
        {
            "fac_a": {"oos_rank_icir": 0.2, "oos_ls_sharpe": 1.4, "ls_sharpe_horizon": 5},
            "fac_b": {"oos_rank_icir": -0.1, "oos_ls_sharpe": -0.5, "ls_sharpe_horizon": 5},
        },
        "2026-02-27",
    )


def _passing_backtest():
    return {"net_sharpe": 0.95, "mdd": -0.28, "cagr": 0.21}


def _run(tmp_path: Path, *, window=BURNED, backtest=None, metrics_fn=_metrics_fn,
         step_id="s6", horizon=20, **overrides):
    run_dir = tmp_path / "run"
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
        # dryrun stores MUST be run-local (R1 Minor 1)
        seal_store_dir=run_dir / "seals",
        ledger_root=run_dir / "ledger",
        run_dir=str(run_dir), step_id=step_id,
        hypothesis_id="book_pr3", provider_build_id="pb_test", calendar_policy_id="cp_test",
        mode="dryrun", horizon=horizon,
        compute_metrics_fn=metrics_fn,
    )
    kwargs.update(overrides)
    return run_book_sealed_evaluation(**kwargs)


def _expected_key(window=BURNED) -> str:
    return BookSealIdentity.from_plan(
        _plan(), selected_set_hash="ssh_pr3", execution_envelope_hash="exec_jq_daily",
        eval_protocol_hash="proto_pr3", oos_window_id=f"{window[0]}..{window[1]}",
    ).book_seal_key


def _seals(tmp_path: Path) -> HoldoutSealStore:
    return HoldoutSealStore(tmp_path / "run" / "seals")


def _ledger(tmp_path: Path) -> OosWindowLedgerStore:
    return OosWindowLedgerStore(tmp_path / "run" / "ledger")


# ─────────────────────────────────────────────── pre-declared bar (fail-closed) ──

class TestEvaluatePreDeclaredBar:
    def test_min_max_semantics(self):
        assert evaluate_pre_declared_bar({"net_sharpe": 0.9, "turnover": 0.5},
                                         {"net_sharpe_min": 0.8, "turnover_max": 0.6}).bar_passed
        assert not evaluate_pre_declared_bar({"net_sharpe": 0.7, "turnover": 0.5},
                                             {"net_sharpe_min": 0.8, "turnover_max": 0.6}).bar_passed

    def test_mdd_max_is_a_magnitude_cap_under_negative_convention(self):
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

    def test_nan_inf_unknown_suffix_empty_bar_refused(self):
        with pytest.raises(BookSealError, match="non-finite"):
            evaluate_pre_declared_bar({"net_sharpe": float("nan")}, {"net_sharpe_min": 0.8})
        # R1 Major 1: infinity must never pass a bar
        with pytest.raises(BookSealError, match="non-finite"):
            evaluate_pre_declared_bar({"net_sharpe": float("inf")}, {"net_sharpe_min": 0.8})
        with pytest.raises(BookSealError, match="non-finite"):
            evaluate_pre_declared_bar({"net_sharpe": 0.9}, {"net_sharpe_min": float("inf")})
        with pytest.raises(BookSealError, match="explicit comparator"):
            evaluate_pre_declared_bar({"x": 1.0}, {"x": 1.0})
        with pytest.raises(BookSealError, match="empty"):
            evaluate_pre_declared_bar({"x": 1.0}, {})


# ───────────────────────────── component diagnostics (the amendment's 2 context tests) ──

class TestComponentDiagnosticsContext:
    def _seal_store_with_claim(self, tmp_path, key, run_dir):
        store = HoldoutSealStore(tmp_path / "seals")
        store.claim_holdout_access(design_hash="dh", hypothesis_id="h", structural_family="",
                                   profile_id="p", run_dir=str(run_dir), step_id="s",
                                   seal_key=key, request_hash="req_x")
        return store

    def _ctx(self, key, run_dir, *, claimed=True, window=BURNED):
        return ResearchAccessContext(
            run_id=str(Path(str(run_dir)).resolve()), step_id="s", stage="oos_test",
            design_hash="dh",
            allowed_start=pd.Timestamp(window[0]), allowed_end=pd.Timestamp(window[1]),
            provider_build_id="pb_test", calendar_policy_id="cp_test",
            holdout_seal_claimed=claimed, seal_key=key,
        )

    def _call(self, key, seal_store, window=BURNED, metrics_fn=_metrics_fn):
        return run_component_diagnostics_in_book_context(
            book_seal_key=key, book_plan_hash=_plan().plan_hash,
            frozen_set=_frozen_set(), factor_exprs={"fac_a": "$close", "fac_b": "$open"},
            oos_start=window[0], oos_end=window[1], qlib_dir="qlib",
            seal_store=seal_store, compute_metrics_fn=metrics_fn,
        )

    def test_component_diagnostics_refuses_bare_claim_false_without_book_context(self, tmp_path):
        key = _expected_key()
        assert get_research_access_context() is None
        with pytest.raises(BookSealError, match="ACTIVE claimed book"):
            self._call(key, None)
        with research_access_context(self._ctx(key, tmp_path / "run", claimed=False)):
            with pytest.raises(BookSealError, match="holdout_seal_claimed"):
                self._call(key, None)

    def test_fabricated_context_without_real_seal_event_refused(self, tmp_path):
        # R1 B4 probe: an in-process context claiming holdout_seal_claimed=True is NOT proof —
        # the REAL claim event must exist in the seal store.
        key = _expected_key()
        empty_store = HoldoutSealStore(tmp_path / "empty_seals")
        with research_access_context(self._ctx(key, tmp_path / "run")):
            with pytest.raises(BookSealError, match="no holdout seal event"):
                self._call(key, empty_store)

    def test_foreign_run_seal_event_refused(self, tmp_path):
        key = _expected_key()
        store = self._seal_store_with_claim(tmp_path, key, tmp_path / "other_run")
        with research_access_context(self._ctx(key, tmp_path / "run")):
            with pytest.raises(BookSealError, match="foreign-context reuse"):
                self._call(key, store)

    def test_component_diagnostics_refuses_foreign_seal_key(self, tmp_path):
        store = self._seal_store_with_claim(tmp_path, "some_other_key", tmp_path / "run")
        with research_access_context(self._ctx("some_other_key", tmp_path / "run")):
            with pytest.raises(BookSealError, match="!= book_seal_key"):
                self._call(_expected_key(), store)

    def test_component_diagnostics_preserves_active_book_research_access_context(self, tmp_path):
        key = _expected_key()
        store = self._seal_store_with_claim(tmp_path, key, tmp_path / "run")
        installed = self._ctx(key, tmp_path / "run")
        seen = {}

        def probe(**kw):
            seen["ctx"] = get_research_access_context()
            return _metrics_fn()

        with research_access_context(installed):
            out = self._call(key, store, metrics_fn=probe)
        assert seen["ctx"] is installed  # identity — no nested context was installed
        assert out["n_components"] == 2

    def test_nan_or_missing_component_metrics_refused(self, tmp_path):
        # R1 B4 probe: empty / NaN diagnostics must never read as healthy.
        key = _expected_key()
        store = self._seal_store_with_claim(tmp_path, key, tmp_path / "run")

        def nan_metrics(**kw):
            return ({"fac_a": {"oos_rank_icir": float("nan"), "oos_ls_sharpe": 1.0},
                     "fac_b": {"oos_rank_icir": 0.1, "oos_ls_sharpe": 1.0}}, "")

        def missing_member(**kw):
            return ({"fac_a": {"oos_rank_icir": 0.1, "oos_ls_sharpe": 1.0}}, "")

        with research_access_context(self._ctx(key, tmp_path / "run")):
            with pytest.raises(BookSealError, match="non-finite"):
                self._call(key, store, metrics_fn=nan_metrics)
            with pytest.raises(BookSealError, match="incomplete"):
                self._call(key, store, metrics_fn=missing_member)

    def test_rows_mint_no_status_and_carry_the_m3_flags(self, tmp_path):
        key = _expected_key()
        store = self._seal_store_with_claim(tmp_path, key, tmp_path / "run")
        with research_access_context(self._ctx(key, tmp_path / "run")):
            out = self._call(key, store)
        assert {r["component_factor_id"] for r in out["rows"]} == {"fac_a", "fac_b"}
        for row in out["rows"]:
            assert row["run_type"] == "book_component_diagnostic"
            assert row["spent_in_book_context"] is True
            assert row["fresh_oos_eligible"] is False
            assert row["promotion_eligible"] is False
        by_id = {r["component_factor_id"]: r for r in out["rows"]}
        assert by_id["fac_a"]["reference_pass"] is True
        assert by_id["fac_b"]["reference_pass"] is False


# ─────────────────────────────────────────────── the book sealed evaluation ──

class TestRunBookSealedEvaluation:
    def test_live_mode_refused_until_governed_runner(self, tmp_path):
        with pytest.raises(BookSealError, match="governed S6"):
            _run(tmp_path, mode="live")
        assert _seals(tmp_path).list_events().empty

    def test_dryrun_burned_window_produces_full_artifact_one_seal(self, tmp_path):
        art = _run(tmp_path)
        assert art["mode"] == "dryrun" and art["virgin_window"] is False
        assert art["book_seal_key"] == _expected_key()
        assert art["book_verdict"]["bar_passed"] is True
        assert art["component_diagnostics_ok"] is True
        assert art["component_diagnostics"]["n_components"] == 2
        assert art["promotion_eligible"] is False  # dryrun is NEVER promotable
        events = _seals(tmp_path).list_events()
        assert len(events) == 1
        assert events.iloc[0]["seal_key"] == _expected_key()
        assert events.iloc[0]["request_hash"] == art["request_hash"]
        # the canonical artifact is persisted, content-addressed, state=complete
        astore = BookSealArtifactStore(tmp_path / "run" / "ledger")
        assert astore.current(_expected_key())["state"] == "complete"
        canonical = astore.load_artifact(art["artifact_hash"])
        assert canonical["book_verdict"]["bar_passed"] is True
        # the spend was reserved with the disclosure fields (R1 Major 3)
        row = _ledger(tmp_path).latest(oos_window_id=BURNED_ID, book_seal_key=_expected_key())
        assert row["book_plan_hash"] == _plan().plan_hash
        assert row["request_hash"] == art["request_hash"]
        # durable diagnostic rows (R1 Major 2)
        drows = StrategyComponentDiagnosticStore(tmp_path / "run" / "ledger").list_all()
        assert len(drows) == 2
        assert art["component_diagnostics"]["diagnostic_record_ids"]

    def test_component_diagnostics_no_second_seal(self, tmp_path):
        art = _run(tmp_path)
        assert art["component_diagnostics"]["n_components"] == 2
        assert len(_seals(tmp_path).list_events()) == 1

    def test_dryrun_refuses_virgin_window_before_any_claim(self, tmp_path):
        with pytest.raises(BookSealError, match="dryrun REFUSED on a virgin"):
            _run(tmp_path, window=VIRGIN)
        assert _seals(tmp_path).list_events().empty

    def test_dryrun_refuses_non_run_local_stores(self, tmp_path):
        # R1 Minor 1: a dry run pointed at a global store path is structurally refused.
        with pytest.raises(BookSealError, match="run-local"):
            _run(tmp_path, seal_store_dir=tmp_path / "GLOBAL_seals")
        with pytest.raises(BookSealError, match="run-local"):
            _run(tmp_path, ledger_root=tmp_path / "GLOBAL_ledger")

    def test_completed_evaluation_can_never_be_rerun(self, tmp_path):
        # THE R1 B1 probe: first verdict persisted, a second identical call must refuse —
        # not re-execute until it passes.
        calls = {"n": 0}

        def counting_backtest():
            calls["n"] += 1
            return _passing_backtest()

        art = _run(tmp_path, backtest=counting_backtest)
        assert calls["n"] == 1 and art["book_verdict"]["bar_passed"] is True
        with pytest.raises(BookSealError, match="COMPLETE"):
            _run(tmp_path, backtest=counting_backtest)
        assert calls["n"] == 1  # the engine never ran again
        assert len(_seals(tmp_path).list_events()) == 1

    def test_failed_bar_is_persisted_and_immutable(self, tmp_path):
        # the verdict-flip probe: a failed bar completes as a FAILED artifact; re-running
        # with a "better" engine is refused — the first persisted verdict stands.
        art = _run(tmp_path, backtest=lambda: {"net_sharpe": 0.5, "mdd": -0.40})
        assert art["book_verdict"]["bar_passed"] is False
        with pytest.raises(BookSealError, match="COMPLETE"):
            _run(tmp_path, backtest=_passing_backtest)

    def test_changed_request_resume_refused(self, tmp_path):
        def boom(**kw):
            raise RuntimeError("diag down")

        with pytest.raises(BookSealDiagnosticsError):
            _run(tmp_path, metrics_fn=boom)
        # same book_seal_key, different evaluation request (horizon changed) -> refused
        with pytest.raises(BookSealError, match="changed evaluation request"):
            _run(tmp_path, horizon=60)

    def test_crash_before_verdict_resume_completes_once(self, tmp_path):
        calls = {"n": 0}

        def crash_once():
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("engine crashed mid-run")
            return _passing_backtest()

        with pytest.raises(RuntimeError, match="engine crashed"):
            _run(tmp_path, backtest=crash_once)
        # the seal is SPENT (spend-on-attempt), no verdict was ever persisted
        assert len(_seals(tmp_path).list_events()) == 1
        assert BookSealArtifactStore(tmp_path / "run" / "ledger").current(
            _expected_key())["state"] == "claimed"
        # resume: the backtest runs its FIRST completion (a persisted verdict never existed)
        art = _run(tmp_path, backtest=crash_once)
        assert calls["n"] == 2 and art["book_verdict"]["bar_passed"] is True
        assert len(_seals(tmp_path).list_events()) == 1

    def test_diagnostics_failure_persists_state_and_resume_never_reruns_backtest(self, tmp_path):
        # THE R1 B1 diagnostics rule: after the verdict is persisted, resume finishes ONLY
        # the diagnostics — book_backtest_fn is never called again.
        calls = {"n": 0}

        def counting_backtest():
            calls["n"] += 1
            return _passing_backtest()

        def broken_metrics(**kw):
            raise RuntimeError("diagnostics leg failed")

        with pytest.raises(BookSealDiagnosticsError, match="seal is SPENT"):
            _run(tmp_path, backtest=counting_backtest, metrics_fn=broken_metrics)
        astore = BookSealArtifactStore(tmp_path / "run" / "ledger")
        assert astore.current(_expected_key())["state"] == "diagnostics_failed"
        assert calls["n"] == 1
        art = _run(tmp_path, backtest=counting_backtest)  # good diagnostics now
        assert calls["n"] == 1  # NEVER re-ran the backtest
        assert art["book_verdict"]["bar_passed"] is True
        assert astore.current(_expected_key())["state"] == "complete"

    def test_blank_provider_ids_refused_before_claim(self, tmp_path):
        with pytest.raises(BookSealError, match="provider_build_id"):
            _run(tmp_path, provider_build_id="")
        assert _seals(tmp_path).list_events().empty


# ─────────────────────────────── atomic reservation + override authorizations ──

class TestSpendReservationAndOverrides:
    def test_reserve_recognizes_resume_not_pending_extra(self, tmp_path):
        ledger = OosWindowLedgerStore(tmp_path / "ledger")
        window = f"{VIRGIN[0]}..{VIRGIN[1]}"
        for i in range(4):
            ledger.record_book_spend(oos_window_id=window, book_seal_key=f"k{i}",
                                     frozen_set_hash=f"f{i}")
        first = ledger.reserve_book_spend(
            oos_window_id=window, book_seal_key="mine", frozen_set_hash="f",
            book_plan_hash="p", request_hash="req", virgin=True, multiplicity_ack=True,
        )
        assert first["resumed"] is False
        # R1 B5 probe: a RESUME of the same key at the hard threshold is recognized as
        # resume — never counted as a pending 6th spend and never refused.
        again = ledger.reserve_book_spend(
            oos_window_id=window, book_seal_key="mine", frozen_set_hash="f",
            book_plan_hash="p", request_hash="req", virgin=True,
        )
        assert again["resumed"] is True

    def test_reserve_changed_request_refused(self, tmp_path):
        ledger = OosWindowLedgerStore(tmp_path / "ledger")
        ledger.reserve_book_spend(oos_window_id="w", book_seal_key="k", frozen_set_hash="f",
                                  book_plan_hash="p", request_hash="req_1")
        with pytest.raises(ValueError, match="DIFFERENT request_hash"):
            ledger.reserve_book_spend(oos_window_id="w", book_seal_key="k", frozen_set_hash="f",
                                      book_plan_hash="p", request_hash="req_2")

    def test_hard_threshold_needs_consumed_authorization_not_boolean(self, tmp_path):
        ledger = OosWindowLedgerStore(tmp_path / "ledger")
        window = f"{VIRGIN[0]}..{VIRGIN[1]}"
        for i in range(5):
            ledger.record_book_spend(oos_window_id=window, book_seal_key=f"k{i}",
                                     frozen_set_hash=f"f{i}")
        with pytest.raises(ValueError, match="HARD STOP"):
            ledger.reserve_book_spend(oos_window_id=window, book_seal_key="k6",
                                      frozen_set_hash="f6", book_plan_hash="p",
                                      request_hash="r", virgin=True, multiplicity_ack=True)
        # a fabricated dict without action=consumed is not an authorization
        with pytest.raises(ValueError, match="HARD STOP"):
            ledger.reserve_book_spend(oos_window_id=window, book_seal_key="k6",
                                      frozen_set_hash="f6", book_plan_hash="p",
                                      request_hash="r", virgin=True,
                                      override_authorization={"override_id": "x"})
        # a REAL consumed a6 authorization admits the spend
        ostore = OverrideAuthorizationStore(tmp_path / "seals")
        ostore.record_authorization(kind="a6_multiplicity", override_id="ov6",
                                    oos_window_id=window, scope_key="k6",
                                    user_signoff="user@2026-07-13", reason="pilot",
                                    adjusted_stats_note="DSR/PBO reported in the artifact")
        auth = ostore.consume_authorization(kind="a6_multiplicity", override_id="ov6",
                                            oos_window_id=window, scope_key="k6")
        row = ledger.reserve_book_spend(oos_window_id=window, book_seal_key="k6",
                                        frozen_set_hash="f6", book_plan_hash="p",
                                        request_hash="r", virgin=True,
                                        override_authorization=auth)
        assert row["override_id"] == "ov6"

    def test_authorizations_are_prerecorded_scoped_and_consume_once(self, tmp_path):
        store = OverrideAuthorizationStore(tmp_path / "seals")
        # invented string -> refused (the R1 B3 probe)
        with pytest.raises(BookSealStoreError, match="never pre-recorded"):
            store.consume_authorization(kind="a5_fresh_window", override_id="made_up",
                                        oos_window_id="w", scope_key="fsh")
        with pytest.raises(BookSealStoreError, match="non-blank"):
            store.consume_authorization(kind="a5_fresh_window", override_id="  ",
                                        oos_window_id="w", scope_key="fsh")
        store.record_authorization(kind="a5_fresh_window", override_id="ov1",
                                   oos_window_id="w", scope_key="fsh",
                                   user_signoff="user", reason="burns w for books")
        # wrong window / wrong scope -> refused
        with pytest.raises(BookSealStoreError, match="bound to window"):
            store.consume_authorization(kind="a5_fresh_window", override_id="ov1",
                                        oos_window_id="OTHER", scope_key="fsh")
        with pytest.raises(BookSealStoreError, match="bound to scope"):
            store.consume_authorization(kind="a5_fresh_window", override_id="ov1",
                                        oos_window_id="w", scope_key="OTHER")
        first = store.consume_authorization(kind="a5_fresh_window", override_id="ov1",
                                            oos_window_id="w", scope_key="fsh")
        assert first["action"] == "consumed"
        with pytest.raises(BookSealStoreError, match="already consumed"):
            store.consume_authorization(kind="a5_fresh_window", override_id="ov1",
                                        oos_window_id="w", scope_key="fsh")

    def test_a6_authorization_requires_adjusted_stats_commitment(self, tmp_path):
        store = OverrideAuthorizationStore(tmp_path / "seals")
        with pytest.raises(BookSealStoreError, match="adjusted"):
            store.record_authorization(kind="a6_multiplicity", override_id="ov",
                                       oos_window_id="w", scope_key="k",
                                       user_signoff="u", reason="r")


# ───────────────────────────────────────── A5 fresh-window enforcement ──

class TestA5FreshWindowEnforcement:
    def test_run_sealed_oos_virgin_claim_requires_override_wrapper_failfast(self):
        from src.alpha_research.factor_eval_skill.sealed_oos import run_sealed_oos

        with pytest.raises(ValueError, match="v1.4_A5_fresh_window_override_required"):
            run_sealed_oos(frozen_set=None, factor_exprs={}, oos_start=VIRGIN[0], oos_end=VIRGIN[1],
                           qlib_dir="q", seal_root="s", run_dir="r", design_hash="d",
                           hypothesis_id="h", claim_seal=True)

    def test_reproduce_sealed_oos_virgin_enforced_at_lowest_claim_point(self, tmp_path):
        # THE R1 B3 probe: direct reproduce_sealed_oos on a virgin window must NOT claim
        # without a REAL pre-recorded authorization — an invented id refuses BEFORE the claim.
        from src.research_orchestrator.promotion_evidence import reproduce_sealed_oos

        prov = {"provider_build_id": "pb", "calendar_policy_id": "cp",
                "calendar_end": VIRGIN[1]}
        fs = _FrozenSet(selected=())
        common = dict(
            frozen_set=fs, factor_exprs={"f": "$close"}, oos_start=VIRGIN[0],
            oos_end=VIRGIN[1], qlib_dir="q", seal_root=str(tmp_path / "seals"),
            run_dir=str(tmp_path / "run"), design_hash="d", provider_provenance=prov,
        )
        with pytest.raises(BookSealStoreError, match="never pre-recorded"):
            reproduce_sealed_oos(**common, fresh_window_override_id="invented")
        with pytest.raises(BookSealStoreError, match="non-blank"):
            reproduce_sealed_oos(**common)
        assert HoldoutSealStore(tmp_path / "seals").list_events().empty  # nothing claimed
        # with a REAL authorization the guard passes; a sentinel compute proves we got past
        # the consume + the claim (and the authorization is now consumed).
        OverrideAuthorizationStore(tmp_path / "seals").record_authorization(
            kind="a5_fresh_window", override_id="ov_real",
            oos_window_id=f"{VIRGIN[0]}..{VIRGIN[1]}", scope_key=fs.frozen_set_hash,
            user_signoff="user", reason="burns the window for overlapping books")

        def sentinel(**kw):
            raise RuntimeError("SENTINEL_COMPUTE_REACHED")

        with pytest.raises(RuntimeError, match="SENTINEL_COMPUTE_REACHED"):
            reproduce_sealed_oos(**common, fresh_window_override_id="ov_real",
                                 compute_factors_fn=sentinel)
        assert not HoldoutSealStore(tmp_path / "seals").list_events().empty  # claim happened
        with pytest.raises(BookSealStoreError, match="already consumed"):
            OverrideAuthorizationStore(tmp_path / "seals").consume_authorization(
                kind="a5_fresh_window", override_id="ov_real",
                oos_window_id=f"{VIRGIN[0]}..{VIRGIN[1]}", scope_key=fs.frozen_set_hash)

    def test_cmd_seal_live_virgin_requires_override_before_any_oos_work(self, tmp_path):
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
        with pytest.raises(FactorEvalError, match="v1.4_A5_fresh_window_override_required"):
            cmd_seal(ctx, mode="live", oos_start=VIRGIN[0], oos_end=VIRGIN[1])
        assert HoldoutSealStore(ctx.holdout_seal_root).list_events().empty

        # with the override id, the spend is recorded as an A5 STUDY row (run_sealed_oos
        # mocked; the store-level consumption is pinned in the reproduce-level test above)
        import src.alpha_research.factor_eval_skill.sealed_oos as so

        class _V:
            n_pass, n_total, results = 1, 1, ({"factor": "tf", "pass": True},)

        orig = so.run_sealed_oos
        so.run_sealed_oos = lambda **kw: {"reproduction": {}, "verdict": _V()}
        try:
            out = cmd_seal(ctx, mode="live", oos_start=VIRGIN[0], oos_end=VIRGIN[1],
                           fresh_window_override_id="fresh_override_001")
        finally:
            so.run_sealed_oos = orig
        assert out["n_pass"] == 1
        # the GOVERNING report on a virgin window is the stricter A6 report (R1 Major 3)
        assert out["multiplicity"]["n_spent"] >= 1
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


def _diag_rows(key, plan_hash):
    base = {"run_type": "book_component_diagnostic", "book_plan_hash": plan_hash,
            "book_seal_key": key, "oos_window_id": BURNED_ID,
            "spent_in_book_context": True, "fresh_oos_eligible": False,
            "promotion_eligible": False}
    return [
        {**base, "component_factor_id": "fac_a", "component_side": "long",
         "component_weight": None, "oos_rank_icir": 0.2, "oos_ls_sharpe": 1.4,
         "aligned_rank_icir": 0.2, "aligned_ls_sharpe": 1.4, "reference_pass": True},
        {**base, "component_factor_id": "fac_b", "component_side": "short",
         "component_weight": None, "oos_rank_icir": -0.1, "oos_ls_sharpe": -0.5,
         "aligned_rank_icir": 0.1, "aligned_ls_sharpe": 0.5, "reference_pass": False},
    ]


def _seed_live_artifact(tmp_path, *, metrics=None, claim_bar_passed=None, mode="live",
                        diag_rows=None, run_tag="run"):
    """Simulate the FUTURE governed S6 runner's output: a real seal claim + a canonical
    complete artifact in the BookSealArtifactStore (live mode is refused in the public
    runner until that runner exists — the gate is tested against seeded canonicals)."""
    plan = _plan()
    identity = BookSealIdentity.from_plan(
        plan, selected_set_hash="ssh_pr3", execution_envelope_hash="exec_jq_daily",
        eval_protocol_hash="proto_pr3", oos_window_id=BURNED_ID)
    key = identity.book_seal_key
    request_hash = f"req_{key[:16]}"
    run_dir = str((tmp_path / run_tag).resolve())
    seal_store = HoldoutSealStore(tmp_path / "seals")
    event = seal_store.claim_holdout_access(
        design_hash=plan.plan_hash, hypothesis_id="h", structural_family="",
        profile_id="p", run_dir=run_dir, step_id="s6", seal_key=key,
        provider_build_id="pb_test", calendar_policy_id="cp_test", request_hash=request_hash)
    astore = BookSealArtifactStore(tmp_path / "book_artifacts")
    astore.open_claim(book_seal_key=key, request_hash=request_hash, run_dir=run_dir,
                      step_id="s6", mode=mode, oos_window_id=BURNED_ID,
                      provider_build_id="pb_test", calendar_policy_id="cp_test",
                      seal_event_id=str(event["event_id"]))
    metrics = metrics or {"net_sharpe": 0.95, "mdd": -0.28}
    verdict = evaluate_pre_declared_bar(metrics, plan.pre_declared_bar).to_dict()
    if claim_bar_passed is not None:
        verdict["bar_passed"] = claim_bar_passed  # tamper probe
    astore.persist_verdict(book_seal_key=key, request_hash=request_hash, verdict=verdict)
    artifact = {
        "schema_version": 2, "artifact_type": "book_sealed_evaluation", "mode": mode,
        "created_at": "2026-07-13 00:00:00", "book_seal_key": key,
        "request_hash": request_hash, "book_seal_identity": identity._payload(),
        "plan": plan._payload(), "oos_window_id": BURNED_ID, "virgin_window": False,
        "provider_build_id": "pb_test", "calendar_policy_id": "cp_test",
        "run_dir": run_dir, "step_id": "s6",
        "seal_event": {k: str(v) for k, v in dict(event).items()},
        "book_verdict": verdict,
        "component_diagnostics": {
            "rows": diag_rows if diag_rows is not None else _diag_rows(key, plan.plan_hash),
            "n_components": len(diag_rows) if diag_rows is not None else 2,
            "n_reference_pass": 1, "max_label_realization_date": "2026-02-27",
            "diagnostic_record_ids": ["d1", "d2"],
        },
        "component_diagnostics_ok": True, "component_diagnostics_error": "",
        "multiplicity": {"action": "disclose", "n_spent": 1},
        "promotion_eligible": bool(mode == "live" and verdict.get("bar_passed") is True),
    }
    completed = astore.complete(book_seal_key=key, request_hash=request_hash, artifact=artifact)
    return {"artifact_hash": str(completed["artifact_hash"]), "artifact_store": astore,
            "seal_store": seal_store, "key": key, "plan": plan}


class TestStrategyPromotionWiring:
    def _store(self, tmp_path):
        from src.research_orchestrator.registries.strategy_registry import StrategyRegistryStore

        return StrategyRegistryStore(tmp_path / "strategy_registry")

    def _publish(self, tmp_path, seeded, name="book_pr3"):
        from src.research_orchestrator.registries.strategy_registry import (
            publish_strategy_candidate,
        )

        store = self._store(tmp_path)
        publish_strategy_candidate(store, object_name=name,
                                   artifact_hash=seeded["artifact_hash"],
                                   artifact_store=seeded["artifact_store"],
                                   run_dir=tmp_path / "run")
        return store

    def _approve(self, tmp_path, store, seeded, **kw):
        args = dict(object_id="strategy_candidate::book_pr3", status="approved", reason="t",
                    promotion_evidence=_p11_fields(), current_git_sha="sha_pr3",
                    holdout_seal_dir=tmp_path / "seals",
                    book_artifact_dir=tmp_path / "book_artifacts")
        args.update(kw)
        return store.set_status(**args)

    def test_publish_and_full_valid_promotion(self, tmp_path):
        seeded = _seed_live_artifact(tmp_path)
        store = self._publish(tmp_path, seeded)
        row = store.find_current(object_type="strategy_candidate", object_name="book_pr3")
        assert len(row) == 1 and row.iloc[0]["definition_hash"] == seeded["key"]
        result = self._approve(tmp_path, store, seeded)
        assert result["new_status"] == "approved"

    def test_gate_ignores_caller_supplied_book_seal_dict(self, tmp_path):
        # THE R1 B2 probe: an edited bar_passed in caller-supplied evidence is worthless —
        # the gate loads the CANONICAL artifact; here the canonical one FAILED its bar.
        from src.research_orchestrator.release_gate import PromotionGateError

        seeded = _seed_live_artifact(tmp_path, metrics={"net_sharpe": 0.5, "mdd": -0.40})
        store = self._publish(tmp_path, seeded)
        forged = {"book_seal": {"book_verdict": {"bar_passed": True}}}
        with pytest.raises(PromotionGateError, match="RECOMPUTED pre-declared bar"):
            self._approve(tmp_path, store, seeded,
                          promotion_evidence={**_p11_fields(), **forged})

    def test_tampered_persisted_bar_boolean_refused_by_recompute(self, tmp_path):
        from src.research_orchestrator.release_gate import PromotionGateError

        seeded = _seed_live_artifact(tmp_path, metrics={"net_sharpe": 0.5, "mdd": -0.40},
                                     claim_bar_passed=True)  # verdict lies; metrics fail
        store = self._publish(tmp_path, seeded)
        with pytest.raises(PromotionGateError, match="RECOMPUTED pre-declared bar"):
            self._approve(tmp_path, store, seeded)

    def test_foreign_artifact_binding_refused(self, tmp_path):
        # THE R1 B2 probe: a registry row whose definition_hash does not match the
        # canonical artifact's book_seal_key is refused (cross-object evidence).
        from src.research_orchestrator.release_gate import PromotionGateError

        seeded = _seed_live_artifact(tmp_path)
        store = self._publish(tmp_path, seeded)
        idx = store.master[store.master["object_id"] == "strategy_candidate::book_pr3"].index[-1]
        store.master.at[idx, "definition_hash"] = "0" * 16  # tamper the row binding
        with pytest.raises(PromotionGateError, match="foreign evidence refused"):
            self._approve(tmp_path, store, seeded)

    def test_missing_seal_event_refused(self, tmp_path):
        from src.research_orchestrator.release_gate import PromotionGateError

        seeded = _seed_live_artifact(tmp_path)
        store = self._publish(tmp_path, seeded)
        with pytest.raises(PromotionGateError, match="no holdout seal event"):
            self._approve(tmp_path, store, seeded, holdout_seal_dir=tmp_path / "EMPTY")

    def test_dryrun_artifact_never_promotable(self, tmp_path):
        from src.research_orchestrator.release_gate import PromotionGateError

        seeded = _seed_live_artifact(tmp_path, mode="dryrun")
        store = self._publish(tmp_path, seeded)
        with pytest.raises(PromotionGateError, match="mode must be 'live'"):
            self._approve(tmp_path, store, seeded)

    def test_null_diagnostic_rows_refused(self, tmp_path):
        # NaN itself cannot even be SEEDED (canonical_json refuses non-JSON floats — the
        # store is structurally NaN-free); the gate must still refuse a null/absent metric
        # that survives a JSON round trip.
        from src.research_orchestrator.release_gate import PromotionGateError

        plan_hash = _plan().plan_hash
        rows = _diag_rows(_expected_key(), plan_hash)
        rows[1]["oos_rank_icir"] = None
        seeded = _seed_live_artifact(tmp_path, diag_rows=rows)
        store = self._publish(tmp_path, seeded)
        with pytest.raises(PromotionGateError, match="non-finite"):
            self._approve(tmp_path, store, seeded)

    def test_missing_stores_refused(self, tmp_path):
        from src.research_orchestrator.release_gate import PromotionGateError

        seeded = _seed_live_artifact(tmp_path)
        store = self._publish(tmp_path, seeded)
        with pytest.raises(PromotionGateError, match="holdout_seal_dir"):
            self._approve(tmp_path, store, seeded, holdout_seal_dir=None)
        with pytest.raises(PromotionGateError, match="book_artifact_dir"):
            self._approve(tmp_path, store, seeded, book_artifact_dir=None)

    def test_p11_layer_still_enforced_first(self, tmp_path):
        from src.research_orchestrator.release_gate import PromotionGateError

        seeded = _seed_live_artifact(tmp_path)
        store = self._publish(tmp_path, seeded)
        bad = _p11_fields()
        bad["unsafe_pit_dates_lint"] = "failed"
        with pytest.raises(PromotionGateError, match="unsafe_pit_dates_lint"):
            self._approve(tmp_path, store, seeded, promotion_evidence=bad)

    def test_same_key_republish_with_changed_payload_refused(self, tmp_path):
        # R1 B2: rows are immutable — no in-place update through republish.
        from src.research_orchestrator.registries.strategy_registry import (
            publish_strategy_candidate,
        )

        seeded = _seed_live_artifact(tmp_path)
        store = self._publish(tmp_path, seeded)
        idx = store.master[store.master["object_id"] == "strategy_candidate::book_pr3"].index[-1]
        store.master.at[idx, "definition_payload_json"] = "{\"mutated\": true}"
        with pytest.raises(ValueError, match="immutable"):
            publish_strategy_candidate(store, object_name="book_pr3",
                                       artifact_hash=seeded["artifact_hash"],
                                       artifact_store=seeded["artifact_store"],
                                       run_dir=tmp_path / "run")

    def test_non_privileged_transitions_unchanged(self, tmp_path):
        seeded = _seed_live_artifact(tmp_path)
        store = self._publish(tmp_path, seeded)
        out = store.set_status(object_id="strategy_candidate::book_pr3",
                               status="under_review", reason="triage")
        assert out["new_status"] == "under_review"


# ─────────────────────────────────────────── the artifact store state machine ──

class TestBookSealArtifactStore:
    def test_state_machine_transitions_and_immutability(self, tmp_path):
        store = BookSealArtifactStore(tmp_path / "a")
        kw = dict(book_seal_key="k", request_hash="r")
        store.open_claim(**kw, run_dir="rd", step_id="s", mode="dryrun", oos_window_id="w",
                         provider_build_id="pb", calendar_policy_id="cp", seal_event_id="e")
        with pytest.raises(BookSealStoreError, match="already has state"):
            store.open_claim(**kw, run_dir="rd", step_id="s", mode="dryrun", oos_window_id="w",
                             provider_build_id="pb", calendar_policy_id="cp", seal_event_id="e")
        with pytest.raises(BookSealStoreError, match="request_hash mismatch"):
            store.persist_verdict(book_seal_key="k", request_hash="OTHER", verdict={"x": 1})
        store.persist_verdict(**kw, verdict={"bar_passed": True})
        with pytest.raises(BookSealStoreError, match="illegal transition"):
            store.persist_verdict(**kw, verdict={"bar_passed": False})  # verdict is immutable
        store.complete(**kw, artifact={"a": 1})
        with pytest.raises(BookSealStoreError, match="illegal transition"):
            store.complete(**kw, artifact={"a": 2})
        assert store.current("k")["state"] == "complete"

    def test_load_artifact_content_addressed(self, tmp_path):
        store = BookSealArtifactStore(tmp_path / "a")
        kw = dict(book_seal_key="k", request_hash="r")
        store.open_claim(**kw, run_dir="rd", step_id="s", mode="live", oos_window_id="w",
                         provider_build_id="pb", calendar_policy_id="cp", seal_event_id="e")
        store.persist_verdict(**kw, verdict={"bar_passed": True})
        completed = store.complete(**kw, artifact={"payload": 42})
        loaded = store.load_artifact(str(completed["artifact_hash"]))
        assert loaded == {"payload": 42}
        with pytest.raises(BookSealStoreError, match="no complete artifact"):
            store.load_artifact("0" * 16)
