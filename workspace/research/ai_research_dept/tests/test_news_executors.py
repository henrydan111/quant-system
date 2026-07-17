# NF chain unit sub-block 2: real leg executors + provenance + orchestration.
import json
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
    RegistryError,
)
from workspace.research.ai_research_dept.engine.news_executors import (  # noqa: E402
    NewsScoringContract, execute_news_decision, read_execution_provenance,
)
from workspace.research.ai_research_dept.engine.news_ingest import (  # noqa: E402
    build_cluster_snapshots,
)
from workspace.research.ai_research_dept.engine.news_seal import SealError  # noqa: E402

CUT = "2025-01-27 18:00:00"


def _stamp(rows):
    df = pd.DataFrame(rows)
    df["source_published_at"] = pd.to_datetime(df["datetime"])
    df["first_ingested_at"] = df["source_published_at"] + pd.Timedelta(minutes=1)
    df["decision_visible_at"] = df["first_ingested_at"]
    df["object_id_hash"] = "obj:" + df["content"]
    df["content_hash"] = "ch:" + df["content"]
    df["ingest_class"] = "forward"
    return df


def _cluster(content, dt="2025-01-27 10:00:00"):
    return build_cluster_snapshots(
        _stamp([{"src": "sina", "datetime": dt, "content": content}]), CUT)[0]


def _assessed(content, *, status="官方证实", kind="事实", rumor=False, importance=3,
              dt="2025-01-27 10:00:00"):
    typing = {"event_type": "订单合同" if not rumor else "传闻未证实",
              "verification_status": status, "content_kind": kind,
              "direction": "利好", "importance": importance, "is_rumor": rumor}
    route = {"primary_route": "stock", "subject_codes": ["688981.SH"],
             "industry_tags": [], "concept_tags": [], "content": content}
    return assess_flash(_cluster(content, dt), typing, route)


def _artifact_full(decision_id="d1"):
    """NFD01(imp5, split w/ source_status) + NFD02(imp3) + NFR01(rumor)."""
    card, records, facts = render_news_flash_section(
        [_assessed("重大订单甲", importance=5),
         _assessed("小事件乙", importance=3, dt="2025-01-27 09:00:00"),
         _assessed("传闻将重组", status="传闻", rumor=True,
                   dt="2025-01-27 08:00:00")], CUT)
    split = {"base_record_id": "NFD01",
             "attributes": {"fact": "签订 12 亿订单", "economic_linkage": "年营收 15%",
                            "source_status": "公司公告官方证实"}}
    return build_attribute_bundle([split], facts, records, card=card,
                                  decision_id=decision_id, cutoff=CUT)


def _artifact_context_only(decision_id="d1"):
    """news_context-only rows -> zero factor population AND zero penalty eligibles."""
    card, records, facts = render_news_flash_section(
        [_assessed("盘面点评甲", kind="评论"),
         _assessed("盘面点评乙", kind="评论", dt="2025-01-27 09:00:00")], CUT)
    return build_attribute_bundle([], facts, records, card=card,
                                  decision_id=decision_id, cutoff=CUT)


class _Reply:
    def __init__(self, text):
        self.text = text


def _valid_factor_record():
    return {"factor_scores": [
                {"name": "event_materiality", "score_0_5": 5,
                 "citations": ["NFD01.fact"]},
                {"name": "fundamental_link", "score_0_5": 5,
                 "citations": ["NFD01.economic_linkage"]},
                {"name": "novelty", "score_0_5": 5, "citations": ["NFD02"]}],
            "horizon_factor_scores": [
                {"name": "tradeability_at_horizon", "horizon": h,
                 "score_0_5": 0, "citations": []} for h in ("next_open", "1-3d", "5-20d")],
            "horizon_theses": []}


def _valid_penalty_record():
    return {"penalty_scores": [
                {"name": "manipulation_risk", "score_0_5": 2, "citations": ["NFR01"]},
                {"name": "confidence_cap", "score_0_5": 1,
                 "citations": ["NFD01.source_status"]}],
            "risk_flags": ["传闻未证实待观察"]}


def _call_fn(factor_reply, penalty_reply, calls):
    def fn(msgs):
        calls.append(msgs)
        if "因子分析" in msgs[0]["content"]:
            return _Reply(factor_reply)
        return _Reply(penalty_reply)
    return fn


def _contract(mode="primary_horizon", primary="1-3d"):
    return NewsScoringContract(schema_id="c16_news_horizon_v1", output_mode=mode,
                               primary_decision_horizon=primary)


# --------------------------------------------------- frozen contract slice

class TestContract:
    def test_valid_primary(self):
        c = _contract()
        assert len(c.contract_hash) == 64

    def test_vector_only_valid(self):
        assert _contract(mode="vector_only", primary=None).output_mode == "vector_only"

    def test_bad_schema_refused(self):
        with pytest.raises(RegistryError, match="schema_id"):
            NewsScoringContract(schema_id="c16_v1", output_mode="primary_horizon",
                                primary_decision_horizon="1-3d")

    def test_vector_with_pinned_refused(self):
        with pytest.raises(RegistryError, match="vector_only"):
            _contract(mode="vector_only", primary="1-3d")

    def test_primary_without_pinned_refused(self):
        with pytest.raises(RegistryError, match="primary_decision_horizon"):
            _contract(primary=None)

    def test_forged_contract_hash_rejected(self):
        c = _contract()
        with pytest.raises(SealError):
            NewsScoringContract(schema_id=c.schema_id, output_mode=c.output_mode,
                                primary_decision_horizon="5-20d",
                                contract_hash=c.contract_hash)


# --------------------------------------------------- happy path

class TestHappyPath:
    def _run(self, tmp_path, mode="primary_horizon", primary="1-3d"):
        art = _artifact_full()
        record_decision(tmp_path / "ledger", "d1", art)
        calls = []
        out = execute_news_decision(
            art, ledger_dir=tmp_path / "ledger", prov_dir=tmp_path / "prov",
            decision_id="d1", contract=_contract(mode, primary),
            call_fn=_call_fn(json.dumps(_valid_factor_record(), ensure_ascii=False),
                             json.dumps(_valid_penalty_record(), ensure_ascii=False),
                             calls))
        return out, calls

    def test_success_finals_and_binding(self, tmp_path):
        out, calls = self._run(tmp_path)
        assert out["outcome"].news_status == "success"
        assert out["outcome"].binding_eligible is True
        # raw 80 (trade NO-SCORE 0) − 2·(2+1) = 74.0, every horizon
        assert out["evaluation"]["news_final_by_horizon"] == {
            "next_open": 74.0, "1-3d": 74.0, "5-20d": 74.0}
        assert out["evaluation"]["news_final"] == 74.0      # contract-pinned 1-3d
        assert len(calls) == 2                              # one LLM call per leg

    def test_provenance_persisted_both_legs(self, tmp_path):
        out, _ = self._run(tmp_path)
        prov = out["provenance"]
        assert [(e["leg"], e["verdict"]) for e in prov] == [
            ("factor", "valid"), ("penalty", "valid")]
        assert all(len(e["raw_sha256"]) == 64 for e in prov)
        assert prov[0]["payload_hash"] != prov[1]["payload_hash"]

    def test_vector_only_no_scalar_no_binding(self, tmp_path):
        out, _ = self._run(tmp_path, mode="vector_only", primary=None)
        assert out["outcome"].binding_eligible is False
        assert out["evaluation"]["news_final"] is None
        assert out["evaluation"]["news_final_by_horizon"]["1-3d"] == 74.0


# --------------------------------------------------- failure + zero paths

class TestFailureAndZero:
    def test_invalid_factor_output_hard_fails_and_persists(self, tmp_path):
        art = _artifact_full()
        record_decision(tmp_path / "ledger", "d1", art)
        bad = _valid_factor_record()
        bad["horizon_factor_scores"] = bad["horizon_factor_scores"][:2]   # missing pair
        calls = []
        out = execute_news_decision(
            art, ledger_dir=tmp_path / "ledger", prov_dir=tmp_path / "prov",
            decision_id="d1", contract=_contract(),
            call_fn=_call_fn(json.dumps(bad, ensure_ascii=False),
                             json.dumps(_valid_penalty_record(), ensure_ascii=False),
                             calls))
        assert out["outcome"].news_status == "hard_failed"
        assert out["outcome"].penalty_leg_status == "not_run"
        assert out["evaluation"] is None
        assert len(calls) == 1                              # penalty LLM never called
        prov = out["provenance"]
        assert [(e["leg"], e["verdict"]) for e in prov] == [("factor", "invalid")]

    def test_penalty_failure_hard_fails(self, tmp_path):
        art = _artifact_full()
        record_decision(tmp_path / "ledger", "d1", art)
        out = execute_news_decision(
            art, ledger_dir=tmp_path / "ledger", prov_dir=tmp_path / "prov",
            decision_id="d1", contract=_contract(),
            call_fn=_call_fn(json.dumps(_valid_factor_record(), ensure_ascii=False),
                             "NOT JSON AT ALL", []))
        assert out["outcome"].news_status == "hard_failed"
        assert out["outcome"].penalty_leg_status == "failed"
        verdicts = [(e["leg"], e["verdict"]) for e in out["provenance"]]
        assert ("penalty", "invalid") in verdicts

    def test_zero_population_no_llm(self, tmp_path):
        # BINDING #4 (runner-owned): context-only artifact -> both legs
        # deterministic, ZERO LLM calls, all-zero finals
        art = _artifact_context_only()
        record_decision(tmp_path / "ledger", "d1", art)
        calls = []
        out = execute_news_decision(
            art, ledger_dir=tmp_path / "ledger", prov_dir=tmp_path / "prov",
            decision_id="d1", contract=_contract(),
            call_fn=_call_fn("{}", "{}", calls))
        assert calls == []                                  # no LLM at all
        assert out["outcome"].news_status == "success"
        assert out["outcome"].penalty_leg_status == "empty_success"
        assert out["evaluation"]["news_final_by_horizon"] == {
            h: 0.0 for h in ("next_open", "1-3d", "5-20d")}
        verdicts = [(e["leg"], e["verdict"]) for e in out["provenance"]]
        assert verdicts == [("factor", "deterministic_zero"),
                            ("penalty", "empty_penalty")]


# --------------------------------------------------- executor input contract

class TestExecutorInput:
    def test_executor_refuses_non_view(self, tmp_path):
        from workspace.research.ai_research_dept.engine.news_executors import (
            make_factor_executor,
        )
        art = _artifact_full()
        ex = make_factor_executor(lambda m: _Reply("{}"), _contract(),
                                  art.final_registry,
                                  prov_dir=tmp_path, results={})
        with pytest.raises(RegistryError, match="ExecutionView"):
            ex("裸字符串 payload")

    def test_contract_required(self, tmp_path):
        art = _artifact_full()
        with pytest.raises(RegistryError, match="NewsScoringContract"):
            execute_news_decision(art, ledger_dir=tmp_path, prov_dir=tmp_path,
                                  decision_id="d1", contract={"output_mode": "primary"},
                                  call_fn=lambda m: _Reply("{}"))
