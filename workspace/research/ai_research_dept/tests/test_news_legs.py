# NF seat wiring unit 2: two-leg execution state machine (M2‴/M3⁴ exhaustive matrix).
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from workspace.research.ai_research_dept.engine.news_cards import (  # noqa: E402
    assess_flash, build_attribute_bundle, render_news_flash_section,
)
from workspace.research.ai_research_dept.engine.news_decision import (  # noqa: E402
    record_decision,
)
from workspace.research.ai_research_dept.engine.news_evidence import (  # noqa: E402
    EvidenceRef, PayloadGateError, RegistryError,
)
from workspace.research.ai_research_dept.engine.news_ingest import (  # noqa: E402
    build_cluster_snapshots,
)
from workspace.research.ai_research_dept.engine.news_legs import (  # noqa: E402
    LegIntegrityError, NewsLegOutcome, penalty_eligible_records, run_news_two_legs,
)
from workspace.research.ai_research_dept.engine.news_seal import SealError  # noqa: E402

CUT = "2025-01-27 18:00:00"


def _stamp(rows, ingest_class="forward"):
    df = pd.DataFrame(rows)
    df["source_published_at"] = pd.to_datetime(df["datetime"])
    df["first_ingested_at"] = pd.to_datetime(df["datetime"]) + pd.Timedelta(minutes=1)
    df["decision_visible_at"] = df[["source_published_at", "first_ingested_at"]].max(axis=1)
    df["object_id_hash"] = df.apply(
        lambda r: "obj:" + str(r["src"]) + "|" + str(r["datetime"]) + "|" + str(r["content"]),
        axis=1)
    df["content_hash"] = df["content"].map(lambda c: "ch:" + str(c))
    df["ingest_class"] = ingest_class
    return df


def _cluster(content, dt="2025-01-27 10:00:00"):
    return build_cluster_snapshots(
        _stamp([{"src": "sina", "datetime": dt, "content": content}]), CUT)[0]


def _assessed(content, *, status="官方证实", rumor=False, importance=3,
              dt="2025-01-27 10:00:00"):
    typing = {"event_type": "订单合同" if not rumor else "传闻未证实",
              "verification_status": status, "content_kind": "事实",
              "direction": "利好", "importance": importance, "is_rumor": rumor}
    route = {"primary_route": "stock", "subject_codes": ["688981.SH"],
             "industry_tags": [], "concept_tags": [], "content": content}
    return assess_flash(_cluster(content, dt), typing, route)


def _artifact(*, with_penalty: bool, decision_id="d1"):
    assessed = [_assessed("重大订单甲", importance=5),
                _assessed("小事件乙", importance=3, dt="2025-01-27 09:00:00")]
    if with_penalty:
        assessed.append(_assessed("传闻将重组", status="传闻", rumor=True,
                                  dt="2025-01-27 08:00:00"))
    card, records, facts = render_news_flash_section(assessed, CUT)
    attrs = {"fact": "签订 12 亿订单", "economic_linkage": "年营收 15%"}
    if with_penalty:
        attrs["source_status"] = "公司公告官方证实"     # penalty-eligible D7 child
    split = {"base_record_id": "NFD01", "attributes": attrs}
    return build_attribute_bundle([split], facts, records, card=card,
                                  decision_id=decision_id, cutoff=CUT)


def _factor_ast(art):
    reg = art.final_registry
    return {"facts": [EvidenceRef(rid) for rid, r in sorted(reg.records.items())
                      if "factor_positive" in r.allowed_uses
                      and "news" in r.allowed_consumers]}


def _penalty_ast(art):
    return {"risks": [EvidenceRef(r.record_id)
                      for r in penalty_eligible_records(art)]}


_OK = lambda sp: None                                  # noqa: E731


def _fail(sp):
    raise RuntimeError("leg blew up")


# --------------------------------------------------- eligible derivation

class TestEligible:
    def test_no_penalty_records(self):
        assert penalty_eligible_records(_artifact(with_penalty=False)) == []

    def test_rumor_and_source_status_eligible(self):
        art = _artifact(with_penalty=True)
        ids = [r.record_id for r in penalty_eligible_records(art)]
        assert ids == ["NFD01.source_status", "NFR01"]  # sorted, deterministic


# --------------------------------------------------- the five matrix rows

class TestMatrix:
    def _run(self, tmp_path, *, with_penalty, output_mode="primary_horizon",
             factor_fn=_OK, penalty_fn=_OK, penalty_calls=None, did="d1"):
        art = _artifact(with_penalty=with_penalty, decision_id=did)
        record_decision(tmp_path, did, art)
        def counted_penalty(sp):
            if penalty_calls is not None:
                penalty_calls.append(sp)
            return penalty_fn(sp)
        return run_news_two_legs(
            art, ledger_dir=tmp_path, decision_id=did, output_mode=output_mode,
            factor_payload_ast=_factor_ast(art),
            penalty_payload_ast=_penalty_ast(art) if with_penalty else None,
            factor_leg_fn=factor_fn, penalty_leg_fn=counted_penalty)

    def test_row1_zero_eligible_empty_success_no_llm(self, tmp_path):
        calls = []
        out = self._run(tmp_path, with_penalty=False, penalty_calls=calls)
        assert calls == []                              # penalty LLM NEVER invoked
        assert out.penalty_leg_status == "empty_success"
        assert out.penalty_payload_hash is None
        assert out.news_status == "success" and out.binding_eligible is True

    def test_row2_penalty_success_publishable(self, tmp_path):
        calls = []
        out = self._run(tmp_path, with_penalty=True, penalty_calls=calls)
        assert len(calls) == 1
        assert out.penalty_eligible_count == 2
        assert out.news_status == "success" and out.binding_eligible is True
        assert out.penalty_payload_hash is not None

    def test_row3_penalty_failure_hard_fails_news(self, tmp_path):
        out = self._run(tmp_path, with_penalty=True, penalty_fn=_fail)
        assert out.penalty_leg_status == "failed"
        assert out.news_status == "hard_failed"
        assert out.decision_complete is False and out.binding_eligible is False

    def test_row4_factor_failure_short_circuits(self, tmp_path):
        calls = []
        out = self._run(tmp_path, with_penalty=True, factor_fn=_fail,
                        penalty_calls=calls)
        assert calls == []                              # penalty never ran
        assert out.factor_leg_status == "failed"
        assert out.penalty_leg_status == "not_run"
        assert out.news_status == "hard_failed" and out.binding_eligible is False

    def test_row5_integrity_violation_unconstructible(self):
        # penalty executed with ZERO eligible = M3⁴ row 5 — the terminal state
        # cannot even be constructed
        with pytest.raises(LegIntegrityError, match="第 5 行"):
            NewsLegOutcome(decision_id="d1", output_mode="primary_horizon",
                           factor_leg_status="success", penalty_eligible_count=0,
                           penalty_eligible_set_hash="0" * 64,
                           penalty_leg_status="success",   # ran despite 0 eligible
                           news_status="success", shadow_complete=False,
                           decision_complete=True, binding_eligible=True,
                           factor_payload_hash="f" * 64, penalty_payload_hash=None)

    def test_vector_only_never_binding_eligible(self, tmp_path):
        out = self._run(tmp_path, with_penalty=False, output_mode="vector_only")
        assert out.shadow_complete is True
        assert out.binding_eligible is False            # M2⁴: always false
        out2 = self._run(tmp_path, with_penalty=True, output_mode="vector_only",
                         penalty_fn=_fail, did="d2")
        assert out2.shadow_complete is False and out2.binding_eligible is False


# --------------------------------------------------- terminal-state integrity

class TestOutcomeSeal:
    def _outcome(self, tmp_path):
        art = _artifact(with_penalty=False)
        record_decision(tmp_path, "d1", art)
        return run_news_two_legs(
            art, ledger_dir=tmp_path, decision_id="d1",
            output_mode="primary_horizon", factor_payload_ast=_factor_ast(art),
            penalty_payload_ast=None, factor_leg_fn=_OK, penalty_leg_fn=_OK)

    def test_forged_terminal_fields_unconstructible(self, tmp_path):
        # declaring binding_eligible=True on a hard-failed run refuses
        with pytest.raises(LegIntegrityError, match="不符"):
            NewsLegOutcome(decision_id="d1", output_mode="primary_horizon",
                           factor_leg_status="failed", penalty_eligible_count=0,
                           penalty_eligible_set_hash="0" * 64,
                           penalty_leg_status="not_run",
                           news_status="success",          # forged
                           shadow_complete=False, decision_complete=True,
                           binding_eligible=True,          # forged
                           factor_payload_hash="f" * 64, penalty_payload_hash=None)

    def test_silent_empty_penalty_unconstructible(self):
        # eligible>0 recorded as empty_success = silent empty penalty — refused
        with pytest.raises(LegIntegrityError, match="静默空罚分"):
            NewsLegOutcome(decision_id="d1", output_mode="primary_horizon",
                           factor_leg_status="success", penalty_eligible_count=2,
                           penalty_eligible_set_hash="0" * 64,
                           penalty_leg_status="empty_success",
                           news_status="success", shadow_complete=False,
                           decision_complete=True, binding_eligible=True,
                           factor_payload_hash="f" * 64, penalty_payload_hash=None)

    def test_outcome_hash_forge_rejected(self, tmp_path):
        out = self._outcome(tmp_path)
        assert len(out.outcome_hash) == 64
        with pytest.raises(SealError):
            NewsLegOutcome(decision_id="EVIL", output_mode=out.output_mode,
                           factor_leg_status=out.factor_leg_status,
                           penalty_eligible_count=out.penalty_eligible_count,
                           penalty_eligible_set_hash=out.penalty_eligible_set_hash,
                           penalty_leg_status=out.penalty_leg_status,
                           news_status=out.news_status,
                           shadow_complete=out.shadow_complete,
                           decision_complete=out.decision_complete,
                           binding_eligible=out.binding_eligible,
                           factor_payload_hash=out.factor_payload_hash,
                           penalty_payload_hash=out.penalty_payload_hash,
                           outcome_hash=out.outcome_hash)


# --------------------------------------------------- leg payload isolation (M2‴)

class TestLegIsolation:
    def test_penalty_ref_in_factor_leg_refused(self, tmp_path):
        art = _artifact(with_penalty=True)
        record_decision(tmp_path, "d1", art)
        bad_factor = {"facts": [EvidenceRef("NFR01")]}   # penalty-only record
        with pytest.raises(PayloadGateError, match="NFR01"):
            run_news_two_legs(art, ledger_dir=tmp_path, decision_id="d1",
                              output_mode="primary_horizon",
                              factor_payload_ast=bad_factor,
                              penalty_payload_ast=_penalty_ast(art),
                              factor_leg_fn=_OK, penalty_leg_fn=_OK)

    def test_factor_ref_in_penalty_leg_refused(self, tmp_path):
        art = _artifact(with_penalty=True)
        record_decision(tmp_path, "d1", art)
        bad_penalty = {"risks": [EvidenceRef("NFD01.fact")]}   # factor-only record
        with pytest.raises(PayloadGateError, match="NFD01.fact"):
            run_news_two_legs(art, ledger_dir=tmp_path, decision_id="d1",
                              output_mode="primary_horizon",
                              factor_payload_ast=_factor_ast(art),
                              penalty_payload_ast=bad_penalty,
                              factor_leg_fn=_OK, penalty_leg_fn=_OK)

    def test_missing_penalty_payload_with_eligibles_refused(self, tmp_path):
        art = _artifact(with_penalty=True)
        record_decision(tmp_path, "d1", art)
        with pytest.raises(RegistryError, match="penalty 适格"):
            run_news_two_legs(art, ledger_dir=tmp_path, decision_id="d1",
                              output_mode="primary_horizon",
                              factor_payload_ast=_factor_ast(art),
                              penalty_payload_ast=None,
                              factor_leg_fn=_OK, penalty_leg_fn=_OK)

    def test_unrecorded_decision_refused(self, tmp_path):
        art = _artifact(with_penalty=False)              # not recorded
        with pytest.raises(RegistryError, match="未入账"):
            run_news_two_legs(art, ledger_dir=tmp_path, decision_id="d1",
                              output_mode="primary_horizon",
                              factor_payload_ast=_factor_ast(art),
                              penalty_payload_ast=None,
                              factor_leg_fn=_OK, penalty_leg_fn=_OK)


# --------------------------------------------------- prevalidation (re-review M3)

class TestPrevalidation:
    def test_invalid_output_mode_before_any_executor(self, tmp_path):
        art = _artifact(with_penalty=False)
        record_decision(tmp_path, "d1", art)
        calls = []
        with pytest.raises(RegistryError, match="output_mode"):
            run_news_two_legs(art, ledger_dir=tmp_path, decision_id="d1",
                              output_mode="EVIL",
                              factor_payload_ast=_factor_ast(art),
                              penalty_payload_ast=None,
                              factor_leg_fn=lambda sp: calls.append(sp),
                              penalty_leg_fn=_OK)
        assert calls == []                              # factor executor never ran

    def test_missing_penalty_payload_detected_before_factor(self, tmp_path):
        art = _artifact(with_penalty=True)
        record_decision(tmp_path, "d1", art)
        calls = []
        with pytest.raises(RegistryError, match="penalty 适格"):
            run_news_two_legs(art, ledger_dir=tmp_path, decision_id="d1",
                              output_mode="primary_horizon",
                              factor_payload_ast=_factor_ast(art),
                              penalty_payload_ast=None,
                              factor_leg_fn=lambda sp: calls.append(sp),
                              penalty_leg_fn=_OK)
        assert calls == []                              # config error precedes exec

    def test_penalty_payload_with_zero_eligible_refused(self, tmp_path):
        art = _artifact(with_penalty=False)
        record_decision(tmp_path, "d1", art)
        with pytest.raises(RegistryError, match="配置错误"):
            run_news_two_legs(art, ledger_dir=tmp_path, decision_id="d1",
                              output_mode="primary_horizon",
                              factor_payload_ast=_factor_ast(art),
                              penalty_payload_ast={"risks": []},
                              factor_leg_fn=_OK, penalty_leg_fn=_OK)

    def test_incomplete_factor_payload_before_executor(self, tmp_path):
        # re-review B1 at the leg level: a factor payload omitting available
        # positive records never reaches the executor
        art = _artifact(with_penalty=False)
        record_decision(tmp_path, "d1", art)
        calls = []
        with pytest.raises(RegistryError, match="完整性"):
            run_news_two_legs(art, ledger_dir=tmp_path, decision_id="d1",
                              output_mode="primary_horizon",
                              factor_payload_ast={"facts": []},   # empty
                              penalty_payload_ast=None,
                              factor_leg_fn=lambda sp: calls.append(sp),
                              penalty_leg_fn=_OK)
        assert calls == []


# --------------------------------------------------- strict terminal types (B3)

class TestStrictTerminalTypes:
    def _kw(self, **over):
        base = dict(decision_id="d1", output_mode="primary_horizon",
                    factor_leg_status="success", penalty_eligible_count=2,
                    penalty_eligible_set_hash="0" * 64,
                    penalty_leg_status="success", news_status="success",
                    shadow_complete=False, decision_complete=True,
                    binding_eligible=True, factor_payload_hash="f" * 64,
                    penalty_payload_hash="e" * 64)
        base.update(over)
        return base

    def test_valid_row2_constructs(self):
        assert NewsLegOutcome(**self._kw()).news_status == "success"

    def test_int_as_bool_rejected(self):
        # Python 1 == True would pass a loose matrix comparison — exact types
        with pytest.raises(RegistryError, match="恰 bool"):
            NewsLegOutcome(**self._kw(binding_eligible=1))

    def test_bool_as_count_rejected(self):
        with pytest.raises(RegistryError, match="非 bool"):
            NewsLegOutcome(**self._kw(penalty_eligible_count=True,
                                      penalty_leg_status="success"))

    def test_penalty_success_requires_hash(self):
        with pytest.raises(LegIntegrityError, match="必须携带"):
            NewsLegOutcome(**self._kw(penalty_payload_hash=None))

    def test_fake_short_hash_rejected(self):
        with pytest.raises(RegistryError, match="64 位小写 hex"):
            NewsLegOutcome(**self._kw(factor_payload_hash="deadbeef"))

    def test_uppercase_hash_rejected(self):
        with pytest.raises(LegIntegrityError, match="必须携带"):
            NewsLegOutcome(**self._kw(penalty_payload_hash="F" * 64))


# --------------------------------------------------- binding boundary (B3)

class TestBindingBoundary:
    def _run(self, tmp_path):
        from workspace.research.ai_research_dept.engine.news_decision import (
            build_sealed_payload,
        )
        art = _artifact(with_penalty=True)
        record_decision(tmp_path, "d1", art)
        f_ast, p_ast = _factor_ast(art), _penalty_ast(art)
        out = run_news_two_legs(art, ledger_dir=tmp_path, decision_id="d1",
                                output_mode="primary_horizon",
                                factor_payload_ast=f_ast, penalty_payload_ast=p_ast,
                                factor_leg_fn=_OK, penalty_leg_fn=_OK)
        # deterministic rebuild of the payloads (same ast + artifact -> same hash)
        fp = build_sealed_payload(f_ast, art, ledger_dir=tmp_path, decision_id="d1",
                                  consumer_seat="news", use="factor_positive")
        pp = build_sealed_payload(p_ast, art, ledger_dir=tmp_path, decision_id="d1",
                                  consumer_seat="news", use="penalty")
        return art, out, fp, pp

    def test_binding_boundary_recomputes_and_passes(self, tmp_path):
        from workspace.research.ai_research_dept.engine.news_legs import (
            verify_outcome_for_binding,
        )
        art, out, fp, pp = self._run(tmp_path)
        assert fp.payload_hash == out.factor_payload_hash    # deterministic rebuild
        assert verify_outcome_for_binding(
            out, art, fp, pp, ledger_dir=tmp_path,
            expected_output_mode="primary_horizon") is out

    def test_binding_boundary_rejects_foreign_artifact(self, tmp_path):
        from workspace.research.ai_research_dept.engine.news_legs import (
            verify_outcome_for_binding,
        )
        art, out, fp, pp = self._run(tmp_path)
        other = _artifact(with_penalty=False, decision_id="d2")   # different world
        with pytest.raises((RegistryError, LegIntegrityError)):
            verify_outcome_for_binding(out, other, fp, pp, ledger_dir=tmp_path,
                                       expected_output_mode="primary_horizon")

    def test_mode_replay_refused_at_binding(self, tmp_path):
        # re-review#2 B1: the frozen contract's expected mode is authoritative —
        # an outcome sealed under a different mode (vector->primary re-mint or
        # vice versa) refuses at the binding boundary
        from workspace.research.ai_research_dept.engine.news_legs import (
            verify_outcome_for_binding,
        )
        art, out, fp, pp = self._run(tmp_path)          # out is primary_horizon
        with pytest.raises(LegIntegrityError, match="模式重放"):
            verify_outcome_for_binding(out, art, fp, pp, ledger_dir=tmp_path,
                                       expected_output_mode="vector_only")

    def test_swapped_leg_payloads_refused_at_binding(self, tmp_path):
        # re-review#2 B1: the same penalty payload cannot satisfy both slots
        from workspace.research.ai_research_dept.engine.news_legs import (
            verify_outcome_for_binding,
        )
        art, out, fp, pp = self._run(tmp_path)
        with pytest.raises((RegistryError, LegIntegrityError)):
            verify_outcome_for_binding(out, art, pp, pp, ledger_dir=tmp_path,
                                       expected_output_mode="primary_horizon")


class TestExactTypePrevalidation:
    # re-review#2 M1: str subclasses must be refused BEFORE any executor runs
    def test_output_mode_subclass_before_executor(self, tmp_path):
        class S(str):
            pass
        art = _artifact(with_penalty=False)
        record_decision(tmp_path, "d1", art)
        calls = []
        with pytest.raises(RegistryError, match="output_mode"):
            run_news_two_legs(art, ledger_dir=tmp_path, decision_id="d1",
                              output_mode=S("primary_horizon"),
                              factor_payload_ast=_factor_ast(art),
                              penalty_payload_ast=None,
                              factor_leg_fn=lambda sp: calls.append(sp),
                              penalty_leg_fn=_OK)
        assert calls == []

    def test_decision_id_subclass_before_executor(self, tmp_path):
        class S(str):
            pass
        art = _artifact(with_penalty=False)
        record_decision(tmp_path, "d1", art)
        calls = []
        with pytest.raises(RegistryError, match="decision_id"):
            run_news_two_legs(art, ledger_dir=tmp_path, decision_id=S("d1"),
                              output_mode="primary_horizon",
                              factor_payload_ast=_factor_ast(art),
                              penalty_payload_ast=None,
                              factor_leg_fn=lambda sp: calls.append(sp),
                              penalty_leg_fn=_OK)
        assert calls == []
