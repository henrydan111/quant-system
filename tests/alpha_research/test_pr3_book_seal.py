"""v1.4 PR3 acceptance tests (post-R2-REWORK) — the book_seal_key claim path as a
request-bound state machine, claim-bound component diagnostics fed by the SEALED
manifest, consume-once store-verified overrides, atomic spend reservations (book + A5),
and the canonical-artifact promotion gate with governed-runner fail-closed.

Pins the GPT R1+R2 adversarial probes:
- re-run / verdict-flip of a completed evaluation refused; changed-request refused;
  diagnostics-only resume never re-runs the backtest; the one-execution guarantee is
  ATOMIC in the store (run_or_load_verdict);
- a foreign frozen_set / mismatched plan hash cannot ride a book's seal (B2);
- diagnostics observe ONLY the sealed manifest, bound to the canonical claim + real
  seal event (run/step/request) (B3);
- a direct reproduce_sealed_oos virgin claim consumes a REAL authorization AND lands
  in the A6 ledger (B4);
- the a6 hard-stop override is verified FROM the store — invented ids and shaped dicts
  refuse; blank-request legacy reservations are quarantined (B5/M2);
- live artifacts fail closed at the governed-runner check until S6 registers (M1);
  dangling diagnostic record ids refuse (M3); infinite metrics refuse; dryrun stores
  must be run-local.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.alpha_research.factor_eval_skill._hashing import payload_hash
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
from src.research_orchestrator.frozen_selection_set import FrozenSelectionSet, SelectedFactor
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

def _frozen_set() -> FrozenSelectionSet:
    return FrozenSelectionSet(
        selected=(
            SelectedFactor("fac_a", 1, "def_a", "long"),
            SelectedFactor("fac_b", 1, "def_b", "short"),
        ),
        candidate_pool_hash="pool_pr3",
        selection_rule_hash="rule_pr3",
        eval_protocol_hash="proto_pr3",
        metric="rank_icir",
        portfolio_side="long_short",
        universe="univ_liquid_top300",
        time_split_window=BURNED_ID,
        rebalance="20d",
        neutralization="none",
    )


FS = _frozen_set()
EXPRS = {"fac_a": "$close", "fac_b": "$open"}


def _plan(**overrides) -> DeploymentFrozenPlan:
    base = dict(
        frozen_set_hash=FS.frozen_set_hash,
        envelope_hash="env_pr3",
        target_universe_declaration_hash="tud_pr3",
        deployment_universe="univ_liquid_top300",
        portfolio_side="long_only",
        construction={"score_to_weight": "topk_equal", "topk": 30},
        pre_declared_bar={"net_sharpe_min": 0.8, "mdd_max": -0.35},
    )
    base.update(overrides)
    return DeploymentFrozenPlan(**base)


def _manifest() -> dict:
    return {
        "components": {
            "fac_a": {"version": 1, "definition_hash": "def_a", "side": "long", "expr": "$close"},
            "fac_b": {"version": 1, "definition_hash": "def_b", "side": "short", "expr": "$open"},
        }
    }


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
        frozen_set=FS,
        factor_exprs=dict(EXPRS),
        qlib_dir=str(tmp_path / "qlib"),
        seal_store_dir=run_dir / "seals",       # dryrun stores MUST be run-local (R1 m1)
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

    def test_missing_metric_never_passes(self):
        with pytest.raises(BookSealError, match="missing"):
            evaluate_pre_declared_bar({"net_sharpe": 0.9}, {"mdd_max": -0.35})

    def test_nan_inf_unknown_suffix_empty_bar_refused(self):
        with pytest.raises(BookSealError, match="non-finite"):
            evaluate_pre_declared_bar({"net_sharpe": float("nan")}, {"net_sharpe_min": 0.8})
        with pytest.raises(BookSealError, match="non-finite"):
            evaluate_pre_declared_bar({"net_sharpe": float("inf")}, {"net_sharpe_min": 0.8})
        with pytest.raises(BookSealError, match="non-finite"):
            evaluate_pre_declared_bar({"net_sharpe": 0.9}, {"net_sharpe_min": float("inf")})
        with pytest.raises(BookSealError, match="explicit comparator"):
            evaluate_pre_declared_bar({"x": 1.0}, {"x": 1.0})
        with pytest.raises(BookSealError, match="empty"):
            evaluate_pre_declared_bar({"x": 1.0}, {})


# ───────────────────────────── component diagnostics (claim-bound, manifest-fed) ──

def _diag_env(tmp_path: Path, *, req="req_diag", window=BURNED, step_id="s",
              manifest=None, plan_hash=None):
    """A canonical claim (with sealed manifest) + a matching real seal event + the
    matching active-context ingredients — the ONLY constellation diagnostics accept."""
    key = _expected_key(window)
    run_dir = str((tmp_path / "run").resolve())
    seal_store = HoldoutSealStore(tmp_path / "seals")
    event = seal_store.claim_holdout_access(
        design_hash="dh", hypothesis_id="h", structural_family="", profile_id="p",
        run_dir=run_dir, step_id=step_id, seal_key=key,
        provider_build_id="pb_test", calendar_policy_id="cp_test", request_hash=req)
    astore = BookSealArtifactStore(tmp_path / "ledger")
    astore.open_claim(
        book_seal_key=key, request_hash=req, run_dir=run_dir, step_id=step_id,
        mode="dryrun", oos_window_id=f"{window[0]}..{window[1]}",
        provider_build_id="pb_test", calendar_policy_id="cp_test",
        seal_event_id=str(event["event_id"]),
        book_plan_hash=plan_hash or _plan().plan_hash,
        component_manifest=manifest if manifest is not None else _manifest())
    ctx = ResearchAccessContext(
        run_id=run_dir, step_id=step_id, stage="oos_test", design_hash="dh",
        allowed_start=pd.Timestamp(window[0]), allowed_end=pd.Timestamp(window[1]),
        provider_build_id="pb_test", calendar_policy_id="cp_test",
        holdout_seal_claimed=True, seal_key=key, request_hash=req)
    return {"key": key, "req": req, "astore": astore, "seal_store": seal_store,
            "ctx": ctx, "run_dir": run_dir, "window": window}


def _call_diag(env, *, metrics_fn=_metrics_fn, key=None, req=None):
    return run_component_diagnostics_in_book_context(
        book_seal_key=key or env["key"], request_hash=req or env["req"],
        artifact_store=env["astore"], seal_store=env["seal_store"],
        oos_start=env["window"][0], oos_end=env["window"][1], qlib_dir="qlib",
        compute_metrics_fn=metrics_fn)


class TestComponentDiagnosticsContext:
    def test_component_diagnostics_refuses_bare_claim_false_without_book_context(self, tmp_path):
        env = _diag_env(tmp_path)
        assert get_research_access_context() is None
        with pytest.raises(BookSealError, match="ACTIVE claimed book"):
            _call_diag(env)
        unclaimed = ResearchAccessContext(
            run_id=env["run_dir"], step_id="s", stage="oos_test", design_hash="dh",
            allowed_start=pd.Timestamp(BURNED[0]), allowed_end=pd.Timestamp(BURNED[1]),
            provider_build_id="pb_test", calendar_policy_id="cp_test",
            holdout_seal_claimed=False, seal_key=env["key"], request_hash=env["req"])
        with research_access_context(unclaimed):
            with pytest.raises(BookSealError, match="holdout_seal_claimed"):
                _call_diag(env)

    def test_fabricated_context_without_real_seal_event_refused(self, tmp_path):
        # a context + claim exist, but the seal store holds NO event -> refused
        env = _diag_env(tmp_path)
        empty = HoldoutSealStore(tmp_path / "EMPTY_seals")
        with research_access_context(env["ctx"]):
            with pytest.raises(BookSealError, match="no holdout seal event"):
                run_component_diagnostics_in_book_context(
                    book_seal_key=env["key"], request_hash=env["req"],
                    artifact_store=env["astore"], seal_store=empty,
                    oos_start=BURNED[0], oos_end=BURNED[1], qlib_dir="q",
                    compute_metrics_fn=_metrics_fn)

    def test_borrowed_seal_with_wrong_step_or_request_refused(self, tmp_path):
        # THE R2 B3 probe: a real claim exists, but a context for a DIFFERENT step or a
        # DIFFERENT request cannot borrow it to run diagnostics.
        env = _diag_env(tmp_path, step_id="s6")
        wrong_step_ctx = ResearchAccessContext(
            run_id=env["run_dir"], step_id="FORGED_STEP", stage="oos_test", design_hash="dh",
            allowed_start=pd.Timestamp(BURNED[0]), allowed_end=pd.Timestamp(BURNED[1]),
            provider_build_id="pb_test", calendar_policy_id="cp_test",
            holdout_seal_claimed=True, seal_key=env["key"], request_hash=env["req"])
        with research_access_context(wrong_step_ctx):
            with pytest.raises(BookSealError, match="step_id"):
                _call_diag(env)
        with research_access_context(env["ctx"]):
            with pytest.raises(BookSealError, match="request_hash"):
                _call_diag(env, req="FORGED_REQUEST")

    def test_diagnostics_observe_only_the_sealed_manifest(self, tmp_path):
        # THE R2 B2/B3 probe: caller-supplied factors are GONE from the API — the metric
        # computation receives exactly the sealed manifest's expressions.
        env = _diag_env(tmp_path)
        seen = {}

        def probe(**kw):
            seen["exprs"] = dict(kw["factor_exprs"])
            return _metrics_fn()

        with research_access_context(env["ctx"]):
            out = _call_diag(env, metrics_fn=probe)
        assert seen["exprs"] == EXPRS          # the manifest's expressions, nothing else
        assert out["n_components"] == 2
        by_id = {r["component_factor_id"]: r for r in out["rows"]}
        assert by_id["fac_a"]["reference_pass"] is True
        assert by_id["fac_b"]["reference_pass"] is False
        for row in out["rows"]:
            assert row["spent_in_book_context"] is True
            assert row["fresh_oos_eligible"] is False
            assert row["promotion_eligible"] is False

    def test_component_diagnostics_preserves_active_book_research_access_context(self, tmp_path):
        env = _diag_env(tmp_path)
        seen = {}

        def probe(**kw):
            seen["ctx"] = get_research_access_context()
            return _metrics_fn()

        with research_access_context(env["ctx"]):
            _call_diag(env, metrics_fn=probe)
        assert seen["ctx"] is env["ctx"]       # identity — no nested context installed

    def test_nan_or_missing_component_metrics_refused(self, tmp_path):
        env = _diag_env(tmp_path)

        def nan_metrics(**kw):
            return ({"fac_a": {"oos_rank_icir": float("nan"), "oos_ls_sharpe": 1.0},
                     "fac_b": {"oos_rank_icir": 0.1, "oos_ls_sharpe": 1.0}}, "")

        def missing_member(**kw):
            return ({"fac_a": {"oos_rank_icir": 0.1, "oos_ls_sharpe": 1.0}}, "")

        with research_access_context(env["ctx"]):
            with pytest.raises(BookSealError, match="non-finite"):
                _call_diag(env, metrics_fn=nan_metrics)
            with pytest.raises(BookSealError, match="incomplete"):
                _call_diag(env, metrics_fn=missing_member)

    def test_pre_r2_claim_without_manifest_refused(self, tmp_path):
        env = _diag_env(tmp_path, manifest={})
        with research_access_context(env["ctx"]):
            with pytest.raises(BookSealStoreError, match="no component manifest"):
                _call_diag(env)


# ─────────────────────────────────────────────── the book sealed evaluation ──

class TestRunBookSealedEvaluation:
    def test_live_mode_refused_until_governed_runner(self, tmp_path):
        with pytest.raises(BookSealError, match="governed S6"):
            _run(tmp_path, mode="live")
        assert _seals(tmp_path).list_events().empty

    def test_plan_frozen_set_binding_enforced(self, tmp_path):
        # THE R2 B2 probe: a plan naming one frozen set + a DIFFERENT observed set refuses.
        with pytest.raises(BookSealError, match="must be the same book"):
            _run(tmp_path, plan=_plan(frozen_set_hash="PLAN_FROZEN_SET"))
        # a look-alike object is refused outright
        class _Fake:
            frozen_set_hash = FS.frozen_set_hash
            selected = FS.selected
        with pytest.raises(BookSealError, match="FrozenSelectionSet"):
            _run(tmp_path, frozen_set=_Fake())
        # expressions must cover the selected members EXACTLY
        with pytest.raises(BookSealError, match="EXACTLY"):
            _run(tmp_path, factor_exprs={"fac_a": "$close", "foreign_x": "$open"})
        assert _seals(tmp_path).list_events().empty

    def test_dryrun_burned_window_produces_full_artifact_one_seal(self, tmp_path):
        art = _run(tmp_path)
        assert art["book_seal_key"] == _expected_key()
        assert art["book_verdict"]["bar_passed"] is True
        assert art["component_diagnostics_ok"] is True
        assert art["promotion_eligible"] is False   # dryrun is NEVER promotable
        events = _seals(tmp_path).list_events()
        assert len(events) == 1
        assert events.iloc[0]["request_hash"] == art["request_hash"]
        astore = BookSealArtifactStore(tmp_path / "run" / "ledger")
        assert astore.current(_expected_key())["state"] == "complete"
        drows = StrategyComponentDiagnosticStore(tmp_path / "run" / "ledger").list_all()
        assert len(drows) == 2
        assert art["component_diagnostics"]["diagnostic_record_ids"]

    def test_dryrun_refuses_virgin_window_and_non_run_local_stores(self, tmp_path):
        with pytest.raises(BookSealError, match="dryrun REFUSED on a virgin"):
            _run(tmp_path, window=VIRGIN)
        with pytest.raises(BookSealError, match="run-local"):
            _run(tmp_path, seal_store_dir=tmp_path / "GLOBAL_seals")
        assert _seals(tmp_path).list_events().empty

    def test_completed_evaluation_can_never_be_rerun(self, tmp_path):
        calls = {"n": 0}

        def counting_backtest():
            calls["n"] += 1
            return _passing_backtest()

        _run(tmp_path, backtest=counting_backtest)
        assert calls["n"] == 1
        with pytest.raises(BookSealError, match="COMPLETE"):
            _run(tmp_path, backtest=counting_backtest)
        assert calls["n"] == 1
        assert len(_seals(tmp_path).list_events()) == 1

    def test_failed_bar_is_persisted_and_immutable(self, tmp_path):
        art = _run(tmp_path, backtest=lambda: {"net_sharpe": 0.5, "mdd": -0.40})
        assert art["book_verdict"]["bar_passed"] is False
        with pytest.raises(BookSealError, match="COMPLETE"):
            _run(tmp_path, backtest=_passing_backtest)

    def test_changed_request_resume_refused(self, tmp_path):
        def boom(**kw):
            raise RuntimeError("diag down")

        with pytest.raises(BookSealDiagnosticsError):
            _run(tmp_path, metrics_fn=boom)
        with pytest.raises(BookSealError, match="changed evaluation request"):
            _run(tmp_path, horizon=60)

    def test_diagnostics_failure_resume_never_reruns_backtest(self, tmp_path):
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
        art = _run(tmp_path, backtest=counting_backtest)   # good diagnostics now
        assert calls["n"] == 1                              # backtest NEVER re-ran
        assert art["book_verdict"]["bar_passed"] is True

    def test_crash_before_verdict_resume_completes_once(self, tmp_path):
        calls = {"n": 0}

        def crash_once():
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("engine crashed mid-run")
            return _passing_backtest()

        with pytest.raises(RuntimeError, match="engine crashed"):
            _run(tmp_path, backtest=crash_once)
        assert len(_seals(tmp_path).list_events()) == 1     # spend-on-attempt
        art = _run(tmp_path, backtest=crash_once)           # no verdict existed -> first completion
        assert calls["n"] == 2 and art["book_verdict"]["bar_passed"] is True

    def test_blank_provider_ids_refused_before_claim(self, tmp_path):
        with pytest.raises(BookSealError, match="provider_build_id"):
            _run(tmp_path, provider_build_id="")
        assert _seals(tmp_path).list_events().empty


class TestRunOrLoadVerdictAtomicity:
    def test_one_execution_guarantee(self, tmp_path):
        # R2 B1: after the verdict is persisted, run_or_load_verdict NEVER calls the
        # evaluator again — the read-evaluate-persist runs under the per-key lock.
        store = BookSealArtifactStore(tmp_path / "a")
        store.open_claim(book_seal_key="k", request_hash="r", run_dir="rd", step_id="s",
                         mode="dryrun", oos_window_id="w", provider_build_id="pb",
                         calendar_policy_id="cp", seal_event_id="e")
        calls = {"n": 0}

        def evaluator():
            calls["n"] += 1
            return {"net_sharpe": 1.0}

        make = lambda m: {"bar_passed": True, "metrics": dict(m)}  # noqa: E731
        v1 = store.run_or_load_verdict(book_seal_key="k", request_hash="r",
                                       evaluator=evaluator, make_verdict=make)
        v2 = store.run_or_load_verdict(book_seal_key="k", request_hash="r",
                                       evaluator=evaluator, make_verdict=make)
        assert calls["n"] == 1 and v1 == v2
        with pytest.raises(BookSealStoreError, match="request_hash mismatch"):
            store.run_or_load_verdict(book_seal_key="k", request_hash="OTHER",
                                      evaluator=evaluator, make_verdict=make)


# ─────────────────────────────── atomic reservations + override authorizations ──

class TestSpendReservationAndOverrides:
    def test_blank_request_legacy_reservation_is_quarantined(self, tmp_path):
        # THE R2 M2 probe: a legacy row with a blank request_hash must not resume ANY request.
        ledger = OosWindowLedgerStore(tmp_path / "ledger")
        ledger.record_book_spend(oos_window_id="w", book_seal_key="k", frozen_set_hash="f")
        for req in ("req_1", "req_2"):
            with pytest.raises(ValueError, match="cannot resume"):
                ledger.reserve_book_spend(oos_window_id="w", book_seal_key="k",
                                          frozen_set_hash="f", book_plan_hash="p",
                                          request_hash=req)

    def test_reserve_recognizes_resume_and_refuses_changed_request(self, tmp_path):
        ledger = OosWindowLedgerStore(tmp_path / "ledger")
        window = f"{VIRGIN[0]}..{VIRGIN[1]}"
        ledger.record_book_spend(oos_window_id=window, book_seal_key="k0",
                                 frozen_set_hash="f0")
        first = ledger.reserve_book_spend(oos_window_id=window, book_seal_key="mine",
                                          frozen_set_hash="f", book_plan_hash="p",
                                          request_hash="req", virgin=True)
        assert first["resumed"] is False
        again = ledger.reserve_book_spend(oos_window_id=window, book_seal_key="mine",
                                          frozen_set_hash="f", book_plan_hash="p",
                                          request_hash="req", virgin=True)
        assert again["resumed"] is True
        with pytest.raises(ValueError, match="cannot resume"):
            ledger.reserve_book_spend(oos_window_id=window, book_seal_key="mine",
                                      frozen_set_hash="f", book_plan_hash="p",
                                      request_hash="req_changed", virgin=True)

    def test_a6_boundaries_are_inclusive(self, tmp_path):
        # THE R3 Blocker 1 probes: 2 existing -> the THIRD spend requires acknowledgement;
        # 4 existing -> the FIFTH spend requires a consumed a6 authorization (not merely
        # the sixth — `>` was an off-by-one that let the 5th through).
        window = f"{VIRGIN[0]}..{VIRGIN[1]}"
        ledger3 = OosWindowLedgerStore(tmp_path / "l3")
        for i in range(2):
            ledger3.record_book_spend(oos_window_id=window, book_seal_key=f"k{i}",
                                      frozen_set_hash=f"f{i}")
        with pytest.raises(ValueError, match="acknowledge band"):
            ledger3.reserve_book_spend(oos_window_id=window, book_seal_key="third",
                                       frozen_set_hash="f", book_plan_hash="p",
                                       request_hash="r", virgin=True)
        ledger3.reserve_book_spend(oos_window_id=window, book_seal_key="third",
                                   frozen_set_hash="f", book_plan_hash="p",
                                   request_hash="r", virgin=True, multiplicity_ack=True)
        ledger5 = OosWindowLedgerStore(tmp_path / "l5")
        for i in range(4):
            ledger5.record_book_spend(oos_window_id=window, book_seal_key=f"k{i}",
                                      frozen_set_hash=f"f{i}")
        with pytest.raises(ValueError, match="HARD STOP"):
            ledger5.reserve_book_spend(oos_window_id=window, book_seal_key="fifth",
                                       frozen_set_hash="f", book_plan_hash="p",
                                       request_hash="r", virgin=True, multiplicity_ack=True)

    def test_hard_threshold_verified_from_the_store_never_caller_input(self, tmp_path):
        # THE R2 B5 probe: no parameter accepts a caller-shaped dict any more; the id is
        # re-read FROM the OverrideAuthorizationStore, request-bound.
        ledger = OosWindowLedgerStore(tmp_path / "ledger")
        ostore = OverrideAuthorizationStore(tmp_path / "seals")
        window = f"{VIRGIN[0]}..{VIRGIN[1]}"
        for i in range(5):
            ledger.record_book_spend(oos_window_id=window, book_seal_key=f"k{i}",
                                     frozen_set_hash=f"f{i}")
        common = dict(oos_window_id=window, book_seal_key="k6", frozen_set_hash="f6",
                      book_plan_hash="p", request_hash="req6", virgin=True)
        with pytest.raises(ValueError, match="HARD STOP"):
            ledger.reserve_book_spend(**common, multiplicity_ack=True)
        with pytest.raises(BookSealStoreError, match="no CONSUMED"):
            ledger.reserve_book_spend(**common, override_store=ostore,
                                      multiplicity_override_id="invented")
        ostore.record_authorization(kind="a6_multiplicity", override_id="ov6",
                                    oos_window_id=window, scope_key="k6",
                                    user_signoff="user@2026-07-13", reason="pilot",
                                    adjusted_stats_note="DSR/PBO reported in the artifact")
        # consumed under a DIFFERENT request -> the request binding refuses
        ostore.consume_authorization(kind="a6_multiplicity", override_id="ov6",
                                     oos_window_id=window, scope_key="k6",
                                     consumed_by_request_hash="req_OTHER")
        with pytest.raises(BookSealStoreError, match="consumed by request"):
            ledger.reserve_book_spend(**common, override_store=ostore,
                                      multiplicity_override_id="ov6")
        # a fresh authorization consumed under THIS request admits the spend
        ostore.record_authorization(kind="a6_multiplicity", override_id="ov7",
                                    oos_window_id=window, scope_key="k6",
                                    user_signoff="user@2026-07-13", reason="pilot",
                                    adjusted_stats_note="DSR/PBO reported")
        ostore.consume_authorization(kind="a6_multiplicity", override_id="ov7",
                                     oos_window_id=window, scope_key="k6",
                                     consumed_by_request_hash="req6")
        row = ledger.reserve_book_spend(**common, override_store=ostore,
                                        multiplicity_override_id="ov7")
        assert row["override_id"] == "ov7"

    def test_authorizations_are_prerecorded_scoped_and_consume_once(self, tmp_path):
        store = OverrideAuthorizationStore(tmp_path / "seals")
        with pytest.raises(BookSealStoreError, match="never pre-recorded"):
            store.consume_authorization(kind="a5_fresh_window", override_id="made_up",
                                        oos_window_id="w", scope_key="fsh")
        store.record_authorization(kind="a5_fresh_window", override_id="ov1",
                                   oos_window_id="w", scope_key="fsh",
                                   user_signoff="user", reason="burns w for books")
        with pytest.raises(BookSealStoreError, match="bound to window"):
            store.consume_authorization(kind="a5_fresh_window", override_id="ov1",
                                        oos_window_id="OTHER", scope_key="fsh")
        first = store.consume_authorization(kind="a5_fresh_window", override_id="ov1",
                                            oos_window_id="w", scope_key="fsh")
        assert first["action"] == "consumed"
        with pytest.raises(BookSealStoreError, match="already consumed"):
            store.consume_authorization(kind="a5_fresh_window", override_id="ov1",
                                        oos_window_id="w", scope_key="fsh")


# ───────────────────────────────────────── A5 fresh-window enforcement ──

def _patch_sealed_world(monkeypatch, tmp_path, exprs=None):
    """R4 B1/B3 test seams: monkeypatch the configured-root RESOLVER (never pass a store
    path into a claim entry point) and the catalog-expression resolver (the fake test
    factors are not in the live catalog)."""
    import src.research_orchestrator.holdout_seal as hs_mod
    import src.research_orchestrator.promotion_evidence as pe

    root = tmp_path / "configured_holdout"
    monkeypatch.setattr(hs_mod, "resolve_configured_global_holdout_root", lambda: root)
    holder = {"exprs": dict(exprs or EXPRS)}
    monkeypatch.setattr(pe, "resolve_frozen_catalog_expressions",
                        lambda frozen_set, **kw: dict(holder["exprs"]))
    return root, holder


class TestA5FreshWindowEnforcement:
    def test_run_sealed_oos_virgin_claim_requires_override_wrapper_failfast(self):
        from src.alpha_research.factor_eval_skill.sealed_oos import run_sealed_oos

        with pytest.raises(ValueError, match="v1.4_A5_fresh_window_override_required"):
            run_sealed_oos(frozen_set=None, oos_start=VIRGIN[0], oos_end=VIRGIN[1],
                           qlib_dir="q", run_dir="r", design_hash="d",
                           hypothesis_id="h", claim_seal=True)

    def test_reproduce_sealed_oos_virgin_authorizes_ledgers_then_claims(self, tmp_path, monkeypatch):
        # R2 B4 + R3 B2 + R4 B1: no caller seal_root/factor_exprs exist; everything
        # derives from the CONFIGURED root; the A5 spend lands in the canonical ledger
        # BEFORE the claim.
        import inspect

        from src.research_orchestrator import promotion_evidence as pe
        from src.research_orchestrator.promotion_evidence import reproduce_sealed_oos

        sig = inspect.signature(pe.reproduce_sealed_oos)
        assert "seal_root" not in sig.parameters and "factor_exprs" not in sig.parameters
        root, _ = _patch_sealed_world(monkeypatch, tmp_path)
        prov = {"provider_build_id": "pb", "calendar_policy_id": "cp", "calendar_end": VIRGIN[1]}
        window_id = f"{VIRGIN[0]}..{VIRGIN[1]}"
        common = dict(
            frozen_set=FS, oos_start=VIRGIN[0], oos_end=VIRGIN[1], qlib_dir="q",
            run_dir=str(tmp_path / "run"), design_hash="d", provider_provenance=prov,
        )
        with pytest.raises(BookSealStoreError, match="never pre-recorded"):
            reproduce_sealed_oos(**common, fresh_window_override_id="invented")
        assert HoldoutSealStore(root).list_events().empty
        OverrideAuthorizationStore(root).record_authorization(
            kind="a5_fresh_window", override_id="ov_real", oos_window_id=window_id,
            scope_key=FS.frozen_set_hash, user_signoff="user",
            reason="burns the window for overlapping books")

        def sentinel(**kw):
            raise RuntimeError("SENTINEL_COMPUTE_REACHED")

        with pytest.raises(RuntimeError, match="SENTINEL_COMPUTE_REACHED"):
            reproduce_sealed_oos(**common, fresh_window_override_id="ov_real",
                                 compute_factors_fn=sentinel)
        assert not HoldoutSealStore(root).list_events().empty
        ledger = OosWindowLedgerStore(root)
        assert ledger.distinct_spend_keys(window_id) == [FS.frozen_set_hash]
        rows = ledger.list_all()
        assert set(rows["spend_unit_type"].dropna()) == {"a5_signal_replication_study"}
        assert rows.iloc[-1]["request_hash"]          # recipe-bound (R3 B3)

    def test_completed_a5_reproduction_is_never_recomputed(self, tmp_path, monkeypatch):
        # THE R4 B2 probe: after a SUCCESSFUL computation, a second identical call
        # returns the PERSISTED result — metric_compute_calls stays 1.
        import src.research_orchestrator.promotion_evidence as pe
        from src.research_orchestrator.promotion_evidence import reproduce_sealed_oos

        root, _ = _patch_sealed_world(monkeypatch, tmp_path)
        calls = {"n": 0}

        def fake_metrics(**kw):
            calls["n"] += 1
            return ({"fac_a": {"oos_rank_icir": 0.1, "oos_ls_sharpe": 1.2,
                               "ls_sharpe_horizon": 5},
                     "fac_b": {"oos_rank_icir": 0.2, "oos_ls_sharpe": 1.3,
                               "ls_sharpe_horizon": 5}}, "2026-06-30")

        monkeypatch.setattr(pe, "_compute_oos_per_factor_metrics", fake_metrics)
        window_id = f"{VIRGIN[0]}..{VIRGIN[1]}"
        OverrideAuthorizationStore(root).record_authorization(
            kind="a5_fresh_window", override_id="ov_c", oos_window_id=window_id,
            scope_key=FS.frozen_set_hash, user_signoff="user", reason="burn stmt")
        prov = {"provider_build_id": "pb", "calendar_policy_id": "cp", "calendar_end": VIRGIN[1]}
        common = dict(frozen_set=FS, oos_start=VIRGIN[0], oos_end=VIRGIN[1], qlib_dir="q",
                      run_dir=str(tmp_path / "run"), design_hash="d",
                      provider_provenance=prov, allow_same_run=True)
        first = reproduce_sealed_oos(**common, fresh_window_override_id="ov_c")
        assert calls["n"] == 1
        assert "fac_a" in first["independent_reproduction"]["per_factor"]
        # identical request again: persisted result returned, NEVER recomputed
        second = reproduce_sealed_oos(**common, fresh_window_override_id="ov_c")
        assert calls["n"] == 1
        assert second == first

    def test_direct_a5_changed_recipe_cannot_reuse_the_spend(self, tmp_path, monkeypatch):
        # THE R3 B3 probe under R4 plumbing: the recipe now changes via the CATALOG
        # resolution (monkeypatched holder), not caller args — a changed recipe refuses
        # at the request-bound reservation before any claim/compute.
        from src.research_orchestrator.promotion_evidence import reproduce_sealed_oos

        root, holder = _patch_sealed_world(monkeypatch, tmp_path)
        prov = {"provider_build_id": "pb", "calendar_policy_id": "cp", "calendar_end": VIRGIN[1]}
        window_id = f"{VIRGIN[0]}..{VIRGIN[1]}"
        store = OverrideAuthorizationStore(root)
        for ov in ("ov_1", "ov_2", "ov_3"):
            store.record_authorization(kind="a5_fresh_window", override_id=ov,
                                       oos_window_id=window_id, scope_key=FS.frozen_set_hash,
                                       user_signoff="user", reason="burn stmt")
        common = dict(
            frozen_set=FS, oos_start=VIRGIN[0], oos_end=VIRGIN[1], qlib_dir="q",
            run_dir=str(tmp_path / "run"), design_hash="d", provider_provenance=prov,
            allow_same_run=True,
        )

        def sentinel(**kw):
            raise RuntimeError("SENTINEL_COMPUTE_REACHED")

        with pytest.raises(RuntimeError, match="SENTINEL_COMPUTE_REACHED"):
            reproduce_sealed_oos(**common, fresh_window_override_id="ov_1",
                                 compute_factors_fn=sentinel)
        holder["exprs"] = {"fac_a": "$high", "fac_b": "$low"}    # the catalog "changed"
        # the completion state machine (keyed by seal_key with request binding) is the
        # authoritative one-recipe-per-seal guard — a changed recipe refuses there,
        # before any consume/reserve/claim/compute.
        with pytest.raises(BookSealStoreError, match="changed recipe.*can never resume"):
            reproduce_sealed_oos(**common, fresh_window_override_id="ov_2",
                                 compute_factors_fn=sentinel)
        holder["exprs"] = dict(EXPRS)                            # identical recipe resumes
        with pytest.raises(RuntimeError, match="SENTINEL_COMPUTE_REACHED"):
            reproduce_sealed_oos(**common, fresh_window_override_id="ov_3",
                                 compute_factors_fn=sentinel)

    def test_direct_a5_hard_band_consumes_request_bound_a6(self, tmp_path, monkeypatch):
        # R3 B2 + R4 Major 1: 4 prior spends -> the 5th direct A5 claim refuses without
        # an a6 authorization; WITH one, the reservation CONSUMES it bound to THIS
        # request (an authorization consumed for another recipe can never admit it).
        from src.research_orchestrator.promotion_evidence import reproduce_sealed_oos

        root, _ = _patch_sealed_world(monkeypatch, tmp_path)
        prov = {"provider_build_id": "pb", "calendar_policy_id": "cp", "calendar_end": VIRGIN[1]}
        window_id = f"{VIRGIN[0]}..{VIRGIN[1]}"
        ledger = OosWindowLedgerStore(root)
        for i in range(4):
            ledger.record_book_spend(oos_window_id=window_id, book_seal_key=f"k{i}",
                                     frozen_set_hash=f"f{i}")
        OverrideAuthorizationStore(root).record_authorization(
            kind="a5_fresh_window", override_id="ov5", oos_window_id=window_id,
            scope_key=FS.frozen_set_hash, user_signoff="user", reason="burn stmt")
        common = dict(frozen_set=FS, oos_start=VIRGIN[0], oos_end=VIRGIN[1], qlib_dir="q",
                      run_dir=str(tmp_path / "run"), design_hash="d",
                      provider_provenance=prov)
        with pytest.raises(ValueError, match="A5 budget HARD STOP"):
            reproduce_sealed_oos(**common, fresh_window_override_id="ov5",
                                 multiplicity_ack=True)
        assert HoldoutSealStore(root).list_events().empty
        # with a pre-recorded a6 authorization, the spend is admitted and the a6 record
        # is CONSUMED bound to the A5 request hash
        OverrideAuthorizationStore(root).record_authorization(
            kind="a5_fresh_window", override_id="ov5b", oos_window_id=window_id,
            scope_key=FS.frozen_set_hash, user_signoff="user", reason="burn stmt")
        OverrideAuthorizationStore(root).record_authorization(
            kind="a6_multiplicity", override_id="a6_ov", oos_window_id=window_id,
            scope_key=FS.frozen_set_hash, user_signoff="user", reason="pilot",
            adjusted_stats_note="DSR/PBO reported")

        def sentinel(**kw):
            raise RuntimeError("SENTINEL_COMPUTE_REACHED")

        with pytest.raises(RuntimeError, match="SENTINEL_COMPUTE_REACHED"):
            reproduce_sealed_oos(**common, fresh_window_override_id="ov5b",
                                 a6_multiplicity_override_id="a6_ov",
                                 compute_factors_fn=sentinel)
        rows = OverrideAuthorizationStore(root).list_all()
        consumed = rows[(rows["override_id"] == "a6_ov") & (rows["action"] == "consumed")]
        assert len(consumed) == 1
        assert str(consumed.iloc[0]["consumed_by_request_hash"]).strip() != ""

    def test_cmd_seal_live_virgin_requires_override_and_ledgers_via_reproduce(
        self, tmp_path, monkeypatch
    ):
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

        root, _ = _patch_sealed_world(monkeypatch, tmp_path)
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
        cmd_register(ctx, factor_id="tf", mode="deployment_bound", evidence_tier="theory_a_priori",
                     direction_source="theory", role="ranking", role_direction="long")
        cmd_declare_target(ctx, target_universe_id="univ_liquid_top300", eligibility_policy="l",
                           asof_policy="pit_lag_1")
        cmd_characterize(ctx, matrix_path=matrix)
        cmd_gate(ctx)
        cmd_select(ctx, matrix_path=matrix, pool={"tf": "x"}, caps={"x": 1}, floor=0.10)
        with pytest.raises(FactorEvalError, match="v1.4_A5_fresh_window_override_required"):
            cmd_seal(ctx, mode="live", oos_start=VIRGIN[0], oos_end=VIRGIN[1])
        assert HoldoutSealStore(root).list_events().empty

        # the mock stands in for run_sealed_oos but performs the REAL A5 reservation in
        # the CANONICAL (resolver-derived) ledger — pinning the wiring.
        import src.alpha_research.factor_eval_skill.sealed_oos as so

        class _V:
            n_pass, n_total, results = 1, 1, ({"factor": "tf", "pass": True},)

        def fake_run_sealed_oos(**kw):
            OosWindowLedgerStore(root).reserve_a5_study_spend(
                oos_window_id=f"{kw['oos_start']}..{kw['oos_end']}",
                frozen_set_hash=kw["frozen_set"].frozen_set_hash,
                override_id=kw["fresh_window_override_id"],
                request_hash="mock_request")
            return {"reproduction": {}, "verdict": _V()}

        orig = so.run_sealed_oos
        so.run_sealed_oos = fake_run_sealed_oos
        try:
            out = cmd_seal(ctx, mode="live", oos_start=VIRGIN[0], oos_end=VIRGIN[1],
                           fresh_window_override_id="fresh_override_001")
        finally:
            so.run_sealed_oos = orig
        assert out["n_pass"] == 1
        assert out["multiplicity"]["n_spent"] >= 1      # virgin GOVERNING report (canonical)
        ledger_rows = OosWindowLedgerStore(root).list_all()
        window_rows = ledger_rows[ledger_rows["oos_window_id"] == f"{VIRGIN[0]}..{VIRGIN[1]}"]
        assert set(window_rows["spend_unit_type"].dropna()) == {"a5_signal_replication_study"}

    def test_cmd_seal_show_previews_canonical_virgin_budget(self, tmp_path, monkeypatch):
        # R4 Minor 2: show-mode on a VIRGIN window previews the A6 budget over the
        # CANONICAL ledger — 4 canonical spends + this pending one => refuse preview.
        from src.alpha_research.factor_eval_skill.orchestration import (
            FactorEvalContext,
            FactorIdentity,
            cmd_characterize,
            cmd_declare_target,
            cmd_gate,
            cmd_register,
            cmd_seal,
            cmd_select,
        )
        from src.alpha_research.factor_eval_skill.stage3_reader import ALL_UNIVERSES

        root, _ = _patch_sealed_world(monkeypatch, tmp_path)
        ledger = OosWindowLedgerStore(root)
        for i in range(4):
            ledger.record_book_spend(oos_window_id=f"{VIRGIN[0]}..{VIRGIN[1]}",
                                     book_seal_key=f"k{i}", frozen_set_hash=f"f{i}")
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
        cmd_register(ctx, factor_id="tf", mode="deployment_bound", evidence_tier="theory_a_priori",
                     direction_source="theory", role="ranking", role_direction="long")
        cmd_declare_target(ctx, target_universe_id="univ_liquid_top300", eligibility_policy="l",
                           asof_policy="pit_lag_1")
        cmd_characterize(ctx, matrix_path=matrix)
        cmd_gate(ctx)
        cmd_select(ctx, matrix_path=matrix, pool={"tf": "x"}, caps={"x": 1}, floor=0.10)
        out = cmd_seal(ctx, mode="show", oos_start=VIRGIN[0], oos_end=VIRGIN[1])
        assert out["multiplicity"]["n_spent"] == 5
        assert out["multiplicity"]["action"] == "refuse_without_override"


class TestCatalogExpressionResolution:
    def _resolve(self, **kw):
        from src.research_orchestrator.promotion_evidence import (
            resolve_frozen_catalog_expressions,
        )

        return resolve_frozen_catalog_expressions(FS, **kw)

    def test_exact_ids_and_hash_verification(self):
        catalog = {"fac_a": "$close", "fac_b": "$open", "unselected": "$high"}
        hashes = {"fac_a": "def_a", "fac_b": "def_b", "unselected": "def_u"}
        exprs = self._resolve(catalog=catalog, definition_hashes=hashes)
        assert exprs == EXPRS                       # exactly the selected ids — nothing more

    def test_definition_drift_refused(self):
        from src.research_orchestrator.promotion_evidence import PromotionEvidenceError

        catalog = {"fac_a": "$close", "fac_b": "$open"}
        hashes = {"fac_a": "def_a", "fac_b": "DRIFTED"}
        with pytest.raises(PromotionEvidenceError, match="definition drift"):
            self._resolve(catalog=catalog, definition_hashes=hashes)

    def test_missing_factor_refused(self):
        from src.research_orchestrator.promotion_evidence import PromotionEvidenceError

        with pytest.raises(PromotionEvidenceError, match="not in the current catalog"):
            self._resolve(catalog={"fac_a": "$close"},
                          definition_hashes={"fac_a": "def_a"})


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


def _diag_rows(key, plan_hash, req):
    base = {"run_type": "book_component_diagnostic", "book_plan_hash": plan_hash,
            "book_seal_key": key, "request_hash": req, "oos_window_id": BURNED_ID,
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
                        null_metric=False, drop_durable_rows=False, governed="valid"):
    """Simulate a would-be governed runner's output: real seal claim + canonical complete
    artifact + durable diagnostic rows. NOTE (R2 M1): even a fully-consistent seeded LIVE
    artifact now FAILS CLOSED at the governed-runner check (the registry is empty until
    the S6 PR) — the gate tests pin exactly that."""
    plan = _plan()
    identity = BookSealIdentity.from_plan(
        plan, selected_set_hash="ssh_pr3", execution_envelope_hash="exec_jq_daily",
        eval_protocol_hash="proto_pr3", oos_window_id=BURNED_ID)
    key = identity.book_seal_key
    request_hash = f"req_{key[:16]}"
    run_dir = str((tmp_path / "run").resolve())
    seal_store = HoldoutSealStore(tmp_path / "seals")
    event = seal_store.claim_holdout_access(
        design_hash=plan.plan_hash, hypothesis_id="h", structural_family="",
        profile_id="p", run_dir=run_dir, step_id="s6", seal_key=key,
        provider_build_id="pb_test", calendar_policy_id="cp_test", request_hash=request_hash)
    astore = BookSealArtifactStore(tmp_path / "book_artifacts")
    astore.open_claim(book_seal_key=key, request_hash=request_hash, run_dir=run_dir,
                      step_id="s6", mode=mode, oos_window_id=BURNED_ID,
                      provider_build_id="pb_test", calendar_policy_id="cp_test",
                      seal_event_id=str(event["event_id"]), book_plan_hash=plan.plan_hash,
                      component_manifest=_manifest())
    metrics = metrics or {"net_sharpe": 0.95, "mdd": -0.28}
    verdict = evaluate_pre_declared_bar(metrics, plan.pre_declared_bar).to_dict()
    if claim_bar_passed is not None:
        verdict["bar_passed"] = claim_bar_passed
    astore.persist_verdict(book_seal_key=key, request_hash=request_hash, verdict=verdict)
    rows = _diag_rows(key, plan.plan_hash, request_hash)
    if null_metric:
        rows[1]["oos_rank_icir"] = None
    dstore = StrategyComponentDiagnosticStore(tmp_path / "book_artifacts")
    if drop_durable_rows:
        ids = ["dangling_1", "dangling_2"]
    else:
        ids = dstore.append_rows(rows)
    governed_section = None
    if governed in ("valid", "unknown_profile"):
        if governed == "valid":
            from src.backtest_engine.execution_profiles import get_profile

            profile = get_profile("joinquant_daily_sim")
            profile_id, profile_hash = profile.profile_id, profile.profile_hash
        else:
            profile_id, profile_hash = "exec_jq_daily", "eph"   # the R3 forged attestation
        governed_section = {
            "runner_id": "seeded_test_runner", "runner_version": "0",
            "execution_profile_id": profile_id, "execution_profile_hash": profile_hash,
            "allowed_for_formal": True, "return_type": "total_return",
            "max_gross_exposure": 1.0,
            "result_hash": payload_hash({str(k): v for k, v in verdict["metrics"].items()}),
        }
    artifact = {
        "schema_version": 2, "artifact_type": "book_sealed_evaluation", "mode": mode,
        "created_at": "2026-07-13 00:00:00", "book_seal_key": key,
        "request_hash": request_hash, "book_seal_identity": identity._payload(),
        "plan": plan._payload(), "oos_window_id": BURNED_ID, "virgin_window": False,
        "provider_build_id": "pb_test", "calendar_policy_id": "cp_test",
        "run_dir": run_dir, "step_id": "s6",
        "seal_event": {k: str(v) for k, v in dict(event).items()},
        "book_verdict": verdict,
        "component_diagnostics": {"rows": rows, "n_components": len(rows),
                                  "n_reference_pass": 1,
                                  "max_label_realization_date": "2026-02-27",
                                  "diagnostic_record_ids": ids},
        "component_diagnostics_ok": True, "component_diagnostics_error": "",
        "multiplicity": {"action": "disclose", "n_spent": 1},
        "promotion_eligible": bool(mode == "live" and verdict.get("bar_passed") is True),
    }
    if governed_section is not None:
        artifact["governed_execution"] = governed_section
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

    def _approve(self, tmp_path, store, **kw):
        args = dict(object_id="strategy_candidate::book_pr3", status="approved", reason="t",
                    promotion_evidence=_p11_fields(), current_git_sha="sha_pr3",
                    holdout_seal_dir=tmp_path / "seals",
                    book_artifact_dir=tmp_path / "book_artifacts")
        args.update(kw)
        return store.set_status(**args)

    def test_fully_consistent_live_artifact_fails_closed_at_governed_runner(self, tmp_path):
        # THE R2 M1 + R3 M1 pins, layer by layer:
        # (a) a FORGED attestation with an unknown profile id refuses at profile
        #     resolution (registering a runner name can never skip this — the R3 probe);
        # (b) a REAL profile + hash still refuses because no VERIFIER is registered;
        # (c) no attestation at all refuses with the no-attestation message.
        from src.research_orchestrator.release_gate import PromotionGateError

        forged = _seed_live_artifact(tmp_path, governed="unknown_profile")
        store = self._publish(tmp_path, forged)
        with pytest.raises(PromotionGateError, match="does not resolve"):
            self._approve(tmp_path, store)
        real = _seed_live_artifact(tmp_path / "b")
        store_b = self._publish(tmp_path / "b", real)
        with pytest.raises(PromotionGateError, match="no REGISTERED governed-runner VERIFIER"):
            self._approve(tmp_path / "b", store_b,
                          holdout_seal_dir=tmp_path / "b" / "seals",
                          book_artifact_dir=tmp_path / "b" / "book_artifacts")
        none = _seed_live_artifact(tmp_path / "c", governed=None)
        store_c = self._publish(tmp_path / "c", none)
        with pytest.raises(PromotionGateError, match="no governed_execution attestation"):
            self._approve(tmp_path / "c", store_c,
                          holdout_seal_dir=tmp_path / "c" / "seals",
                          book_artifact_dir=tmp_path / "c" / "book_artifacts")

    def test_registered_verifier_with_real_profile_completes_the_chain(self, tmp_path, monkeypatch):
        # the S6 simulation: registering a VERIFIER (not a name) + a real profile + hash
        # lets the full chain pass — this is exactly what the S6 runner PR will do.
        from src.research_orchestrator.registries import strategy_registry as sr

        seeded = _seed_live_artifact(tmp_path)
        store = self._publish(tmp_path, seeded)
        calls = {}

        def verifier(*, governed, artifact):
            calls["seen"] = (governed["runner_id"], artifact["book_seal_key"])

        monkeypatch.setitem(sr.REGISTERED_GOVERNED_RUNNER_VERIFIERS, "seeded_test_runner", verifier)
        result = self._approve(tmp_path, store)
        assert result["new_status"] == "approved"
        assert calls["seen"] == ("seeded_test_runner", seeded["key"])

    def test_gate_ignores_caller_supplied_book_seal_dict(self, tmp_path):
        from src.research_orchestrator.release_gate import PromotionGateError

        seeded = _seed_live_artifact(tmp_path, metrics={"net_sharpe": 0.5, "mdd": -0.40})
        store = self._publish(tmp_path, seeded)
        forged = {"book_seal": {"book_verdict": {"bar_passed": True}}}
        with pytest.raises(PromotionGateError, match="RECOMPUTED pre-declared bar"):
            self._approve(tmp_path, store, promotion_evidence={**_p11_fields(), **forged})

    def test_tampered_persisted_bar_boolean_refused_by_recompute(self, tmp_path):
        from src.research_orchestrator.release_gate import PromotionGateError

        seeded = _seed_live_artifact(tmp_path, metrics={"net_sharpe": 0.5, "mdd": -0.40},
                                     claim_bar_passed=True)
        store = self._publish(tmp_path, seeded)
        with pytest.raises(PromotionGateError, match="RECOMPUTED pre-declared bar"):
            self._approve(tmp_path, store)

    def test_foreign_artifact_binding_refused(self, tmp_path):
        from src.research_orchestrator.release_gate import PromotionGateError

        seeded = _seed_live_artifact(tmp_path)
        store = self._publish(tmp_path, seeded)
        idx = store.master[store.master["object_id"] == "strategy_candidate::book_pr3"].index[-1]
        store.master.at[idx, "definition_hash"] = "0" * 16
        with pytest.raises(PromotionGateError, match="foreign evidence refused"):
            self._approve(tmp_path, store)

    def test_dangling_diagnostic_record_ids_refused(self, tmp_path):
        # THE R2 M3 probe: artifact-embedded rows with ids that do NOT exist in the
        # durable StrategyComponentDiagnosticStore refuse.
        from src.research_orchestrator.release_gate import PromotionGateError

        seeded = _seed_live_artifact(tmp_path, drop_durable_rows=True)
        store = self._publish(tmp_path, seeded)
        with pytest.raises(PromotionGateError, match="does not exist in the"):
            self._approve(tmp_path, store)

    def test_null_diagnostic_rows_refused(self, tmp_path):
        from src.research_orchestrator.release_gate import PromotionGateError

        seeded = _seed_live_artifact(tmp_path, null_metric=True)
        store = self._publish(tmp_path, seeded)
        with pytest.raises(PromotionGateError, match="non-finite"):
            self._approve(tmp_path, store)

    def test_dryrun_artifact_never_promotable(self, tmp_path):
        from src.research_orchestrator.release_gate import PromotionGateError

        seeded = _seed_live_artifact(tmp_path, mode="dryrun")
        store = self._publish(tmp_path, seeded)
        with pytest.raises(PromotionGateError, match="mode must be 'live'"):
            self._approve(tmp_path, store)

    def test_missing_stores_refused(self, tmp_path):
        from src.research_orchestrator.release_gate import PromotionGateError

        seeded = _seed_live_artifact(tmp_path)
        store = self._publish(tmp_path, seeded)
        with pytest.raises(PromotionGateError, match="holdout_seal_dir"):
            self._approve(tmp_path, store, holdout_seal_dir=None)
        with pytest.raises(PromotionGateError, match="book_artifact_dir"):
            self._approve(tmp_path, store, book_artifact_dir=None)

    def test_same_key_republish_with_changed_payload_refused(self, tmp_path):
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
        store.persist_verdict(**kw, verdict={"bar_passed": True})
        with pytest.raises(BookSealStoreError, match="illegal transition"):
            store.persist_verdict(**kw, verdict={"bar_passed": False})
        store.complete(**kw, artifact={"a": 1})
        with pytest.raises(BookSealStoreError, match="illegal transition"):
            store.complete(**kw, artifact={"a": 2})
        assert store.current("k")["state"] == "complete"

    def test_append_rows_batch_idempotent_and_divergence_refused(self, tmp_path):
        # R3 Minor 1: a resume after a crash between append and complete re-uses ids
        # instead of duplicating; a divergent payload for the same logical key refuses.
        store = StrategyComponentDiagnosticStore(tmp_path / "d")
        rows = [{"book_seal_key": "k", "request_hash": "r", "component_factor_id": "fac_a",
                 "oos_rank_icir": "0.2", "run_type": "book_component_diagnostic"},
                {"book_seal_key": "k", "request_hash": "r", "component_factor_id": "fac_b",
                 "oos_rank_icir": "-0.1", "run_type": "book_component_diagnostic"}]
        ids1 = store.append_rows(rows)
        ids2 = store.append_rows(rows)              # crash-resume replay
        assert ids1 == ids2
        assert len(store.list_all()) == 2           # no duplicates
        divergent = [dict(rows[0], oos_rank_icir="0.9")]
        with pytest.raises(BookSealStoreError, match="DIVERGENT"):
            store.append_rows(divergent)

    def test_load_artifact_content_addressed(self, tmp_path):
        store = BookSealArtifactStore(tmp_path / "a")
        kw = dict(book_seal_key="k", request_hash="r")
        store.open_claim(**kw, run_dir="rd", step_id="s", mode="live", oos_window_id="w",
                         provider_build_id="pb", calendar_policy_id="cp", seal_event_id="e")
        store.persist_verdict(**kw, verdict={"bar_passed": True})
        completed = store.complete(**kw, artifact={"payload": 42})
        assert store.load_artifact(str(completed["artifact_hash"])) == {"payload": 42}
        with pytest.raises(BookSealStoreError, match="no complete artifact"):
            store.load_artifact("0" * 16)
