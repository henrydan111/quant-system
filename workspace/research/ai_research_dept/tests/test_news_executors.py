# NF chain unit sub-block 2: real executors + attempt-bound provenance (review folded).
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


def _execute(tmp_path, art=None, decision_id="d1", mode="primary_horizon",
             primary="1-3d", factor_reply=None, penalty_reply=None, calls=None,
             prov_sub="prov"):
    art = art or _artifact_full(decision_id)
    try:
        record_decision(tmp_path / "ledger", decision_id, art)
    except RegistryError:
        pass                                            # already recorded (retry)
    calls = calls if calls is not None else []
    return execute_news_decision(
        art, ledger_dir=tmp_path / "ledger", prov_dir=tmp_path / prov_sub,
        decision_id=decision_id, contract=_contract(mode, primary),
        call_fn=_call_fn(
            factor_reply or json.dumps(_valid_factor_record(), ensure_ascii=False),
            penalty_reply or json.dumps(_valid_penalty_record(), ensure_ascii=False),
            calls)), calls


# --------------------------------------------------- frozen contract slice

class TestContract:
    def test_valid_primary(self):
        assert len(_contract().contract_hash) == 64

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


# --------------------------------------------------- content-bearing payloads (Blocker)

class TestPayloadContent:
    def test_factor_message_carries_evidence_text(self, tmp_path):
        out, calls = _execute(tmp_path)
        factor_msg = [m for m in calls if "因子分析" in m[0]["content"]][0]
        user = factor_msg[1]["content"]
        # the LLM SEES the evidence text, not just ids (review Blocker)
        assert "签订 12 亿订单" in user                  # D7 fact child text
        assert "年营收 15%" in user                      # D7 linkage child text
        assert "小事件乙" in user                        # NFD02 card-line content
        # D7 child replacement: the demoted broad parent's line is EXCLUDED
        assert "重大订单甲" not in user
        # cross-leg exclusion: rumor/risk text never enters the factor leg
        assert "传闻将重组" not in user and "公司公告官方证实" not in user
        # exact-once ids
        assert user.count("[NFD01.fact]") == 1 and user.count("[NFD02]") == 1

    def test_penalty_message_carries_risk_text(self, tmp_path):
        out, calls = _execute(tmp_path)
        pen_msg = [m for m in calls if "风险罚分" in m[0]["content"]][0]
        user = pen_msg[1]["content"]
        assert "传闻将重组" in user                      # NFR01 card-line content
        assert "公司公告官方证实" in user                # source_status child text
        assert "签订 12 亿订单" not in user              # factor evidence excluded
        assert user.count("[NFR01]") == 1

    def test_noncanonical_payload_never_reaches_executor(self, tmp_path):
        # bare id-list payloads are refused at the leg boundary (byte-compare)
        from workspace.research.ai_research_dept.engine.news_decision import (
            build_leg_payload_ast,
        )
        from workspace.research.ai_research_dept.engine.news_evidence import EvidenceRef
        from workspace.research.ai_research_dept.engine.news_legs import (
            run_news_two_legs,
        )
        art = _artifact_full()
        record_decision(tmp_path / "ledger", "d1", art)
        got = []
        bare = {"facts": [EvidenceRef(rid) for rid, r in
                          sorted(art.final_registry.records.items())
                          if "factor_positive" in r.allowed_uses
                          and "news" in r.allowed_consumers]}
        with pytest.raises(RegistryError, match="canonical"):
            run_news_two_legs(art, ledger_dir=tmp_path / "ledger", decision_id="d1",
                              output_mode="primary_horizon",
                              factor_payload_ast=bare,
                              penalty_payload_ast=build_leg_payload_ast(
                                  art, use="penalty", consumer_seat="news"),
                              factor_leg_fn=lambda v: got.append(v),
                              penalty_leg_fn=lambda v: None)
        assert got == []


# --------------------------------------------------- happy path + finals

class TestHappyPath:
    def test_success_finals_and_binding(self, tmp_path):
        out, calls = _execute(tmp_path)
        assert out["outcome"].news_status == "success"
        assert out["outcome"].binding_eligible is True
        assert out["evaluation"]["news_final_by_horizon"] == {
            "next_open": 74.0, "1-3d": 74.0, "5-20d": 74.0}
        assert out["evaluation"]["news_final"] == 74.0
        assert len(calls) == 2

    def test_vector_only_no_scalar_no_binding(self, tmp_path):
        out, _ = _execute(tmp_path, mode="vector_only", primary=None)
        assert out["outcome"].binding_eligible is False
        assert out["evaluation"]["news_final"] is None


# --------------------------------------------------- attempt-bound provenance (Major)

class TestProvenance:
    def test_attempt_rows_and_selected_binding(self, tmp_path):
        out, _ = _execute(tmp_path)
        rows = read_execution_provenance(tmp_path / "prov")
        assert [(e["leg"], e["verdict"]) for e in rows] == [
            ("factor", "attempt_started"), ("factor", "valid"),
            ("penalty", "attempt_started"), ("penalty", "valid")]
        assert all(e["execution_id"] == out["execution_id"] for e in rows)
        assert all(len(e["entry_hash"]) == 64 for e in rows)
        sel = out["selected_provenance"]
        assert sel["factor"]["verdict"] == "valid"
        assert sel["penalty"]["verdict"] == "valid"
        assert out["selected_entry_hashes"]["factor"] == sel["factor"]["entry_hash"]

    def test_call_error_typed_terminal(self, tmp_path):
        def boom(msgs):
            raise ConnectionError("transport down")
        art = _artifact_full()
        record_decision(tmp_path / "ledger", "d1", art)
        out = execute_news_decision(
            art, ledger_dir=tmp_path / "ledger", prov_dir=tmp_path / "prov",
            decision_id="d1", contract=_contract(), call_fn=boom)
        assert out["outcome"].news_status == "hard_failed"
        rows = read_execution_provenance(tmp_path / "prov")
        assert [(e["leg"], e["verdict"]) for e in rows] == [
            ("factor", "attempt_started"), ("factor", "call_error")]
        assert rows[1]["raw_sha256"] is None            # no raw bytes existed
        assert out["selected_provenance"]["factor"]["verdict"] == "call_error"

    def test_shared_directory_two_decisions_disambiguated(self, tmp_path):
        out1, _ = _execute(tmp_path, decision_id="d1", prov_sub="prov")
        art2 = _artifact_full("d2")
        out2, _ = _execute(tmp_path, art=art2, decision_id="d2", prov_sub="prov")
        # the FILE holds both decisions' rows...
        rows = read_execution_provenance(tmp_path / "prov")
        assert len(rows) == 8
        # ...but each bundle binds ONLY its own attempt's selected rows
        assert out1["selected_provenance"]["factor"]["decision_id"] == "d1"
        assert out2["selected_provenance"]["factor"]["decision_id"] == "d2"
        assert out1["execution_id"] != out2["execution_id"]

    def test_retry_binds_own_attempt(self, tmp_path):
        # crash/retry ambiguity: two runs of the SAME decision leave multiple
        # valid rows in the file, but each bundle binds its own execution_id rows
        out1, _ = _execute(tmp_path, decision_id="d1")
        out2, _ = _execute(tmp_path, decision_id="d1")   # idempotent ledger, rerun
        rows = read_execution_provenance(tmp_path / "prov")
        valid_factor_rows = [e for e in rows
                             if e["leg"] == "factor" and e["verdict"] == "valid"]
        assert len(valid_factor_rows) == 2               # ambiguity exists in file
        assert out2["selected_provenance"]["factor"]["execution_id"] \
            == out2["execution_id"]                      # binding resolves it
        assert out1["selected_provenance"]["factor"]["entry_hash"] \
            != out2["selected_provenance"]["factor"]["entry_hash"]

    def test_invalid_output_persists_before_raise(self, tmp_path):
        bad = _valid_factor_record()
        bad["horizon_factor_scores"] = bad["horizon_factor_scores"][:2]
        out, calls = _execute(tmp_path,
                              factor_reply=json.dumps(bad, ensure_ascii=False))
        assert out["outcome"].news_status == "hard_failed"
        assert out["evaluation"] is None
        assert len(calls) == 1                           # penalty LLM never called
        rows = read_execution_provenance(tmp_path / "prov")
        assert [(e["leg"], e["verdict"]) for e in rows] == [
            ("factor", "attempt_started"), ("factor", "invalid")]
        assert len(rows[1]["raw_sha256"]) == 64          # raw bytes preserved


# --------------------------------------------------- empty-content lock (rr#2 M1)

class TestEmptyContentLock:
    def _try_split(self, fact_text):
        card, records, facts = render_news_flash_section(
            [_assessed("重大订单甲", importance=5)], CUT)
        split = {"base_record_id": "NFD01", "attributes": {"fact": fact_text}}
        return build_attribute_bundle([split], facts, records, card=card,
                                      decision_id="d1", cutoff=CUT)

    def test_control_chars_only_refused(self):
        # the round-2 probe: "\0\t " sanitizes to "" and could ground a 5
        with pytest.raises(RegistryError, match="实质性"):
            self._try_split("\0\t ")

    def test_whitespace_only_refused(self):
        with pytest.raises(RegistryError, match="实质性"):
            self._try_split("   ")

    def test_none_refused(self):
        with pytest.raises(RegistryError, match="恰 str"):
            self._try_split(None)

    def test_direct_attribute_row_empty_refused(self):
        from workspace.research.ai_research_dept.engine.news_cards import AttributeRow
        with pytest.raises(RegistryError, match="实质性"):
            AttributeRow(row_id="NFD01.fact", claim_id="c", fact_cluster_id="f",
                         evidence_group_id="c:attrs", attribute_type="fact",
                         text="  ")

    # executor-review#3 Major: Unicode default-ignorable-only content is
    # semantically empty — the shared substantive-text predicate refuses it
    @pytest.mark.parametrize("invisible", ["️", "͏", "️͏ "])
    def test_default_ignorable_only_refused_at_factory(self, invisible):
        with pytest.raises(RegistryError, match="实质性"):
            self._try_split(invisible)

    @pytest.mark.parametrize("invisible", ["️", "͏"])
    def test_default_ignorable_only_refused_direct_row(self, invisible):
        from workspace.research.ai_research_dept.engine.news_cards import AttributeRow
        with pytest.raises(RegistryError, match="实质性"):
            AttributeRow(row_id="NFD01.fact", claim_id="c", fact_cluster_id="f",
                         evidence_group_id="c:attrs", attribute_type="fact",
                         text=invisible)

    # executor-review#4 Major: visually blank Lo/So codepoints are semantically
    # empty — the named version-pinned blank set refuses every member
    @pytest.mark.parametrize("cp", [0x115F, 0x1160, 0x3164, 0xFFA0, 0x2800,
                                    0x13441, 0x13442])
    def test_named_blank_codepoints_refused_at_factory(self, cp):
        # end-to-end no-grounding: the factory refuses, so no artifact — and
        # therefore no payload, no executor, no grounding — can ever exist
        with pytest.raises(RegistryError, match="实质性"):
            self._try_split(chr(cp))

    @pytest.mark.parametrize("cp", [0x3164, 0x2800, 0x13441])
    def test_named_blank_codepoints_refused_direct_row(self, cp):
        from workspace.research.ai_research_dept.engine.news_cards import AttributeRow
        with pytest.raises(RegistryError, match="实质性"):
            AttributeRow(row_id="NFD01.fact", claim_id="c", fact_cluster_id="f",
                         evidence_group_id="c:attrs", attribute_type="fact",
                         text=chr(cp))

    def test_emoji_control_passes(self):
        # ⚠ is category So — real content with emoji must NOT be refused
        from workspace.research.ai_research_dept.engine.news_cards import (
            has_substantive_text,
        )
        assert has_substantive_text("⚠️产能预警") is True
        assert has_substantive_text("⚠️") is True   # So codepoint alone
        assert has_substantive_text(chr(0x2801)) is True   # braille dot-1 = content
        assert has_substantive_text("汉̀字") is True  # CJK + combining mark
        assert has_substantive_text("️") is False
        assert has_substantive_text("͏") is False
        assert has_substantive_text(chr(0x3164)) is False  # Hangul filler
        assert has_substantive_text(chr(0x2800)) is False  # braille blank
        assert has_substantive_text(None) is False
        # end-to-end control: an emoji-bearing fact splits fine
        art = self._try_split("⚠️产能利用率预警")
        assert "NFD01.fact" in art.final_registry.records


# --------------------------------------------------- malformed envelope (rr#2 M2)

class TestMalformedEnvelope:
    def _run_with_reply(self, tmp_path, reply_obj):
        art = _artifact_full()
        record_decision(tmp_path / "ledger", "d1", art)
        return execute_news_decision(
            art, ledger_dir=tmp_path / "ledger", prov_dir=tmp_path / "prov",
            decision_id="d1", contract=_contract(), call_fn=lambda m: reply_obj)

    def test_none_text_gets_call_error_terminal(self, tmp_path):
        # the round-2 probe: .text=None must yield a typed terminal, not a
        # terminal-less attempt
        out = self._run_with_reply(tmp_path, _Reply(None))
        assert out["outcome"].news_status == "hard_failed"
        assert out["selected_provenance"]["factor"]["verdict"] == "call_error"
        rows = read_execution_provenance(tmp_path / "prov")
        assert [(e["leg"], e["verdict"]) for e in rows] == [
            ("factor", "attempt_started"), ("factor", "call_error")]

    def test_bytes_text_gets_call_error(self, tmp_path):
        out = self._run_with_reply(tmp_path, _Reply(b"{}"))
        assert out["selected_provenance"]["factor"]["verdict"] == "call_error"

    def test_unencodable_text_gets_call_error(self, tmp_path):
        out = self._run_with_reply(tmp_path, _Reply("\ud800"))   # lone surrogate
        assert out["selected_provenance"]["factor"]["verdict"] == "call_error"

    def test_terminal_write_failure_refuses_bundle(self, tmp_path, monkeypatch):
        # attempt began, terminal write fails -> execute must RAISE, never return
        import workspace.research.ai_research_dept.engine.news_executors as mod
        art = _artifact_full()
        record_decision(tmp_path / "ledger", "d1", art)
        real = mod._persist_execution_provenance

        def flaky(*a, **kw):
            if kw.get("verdict") == "call_error":
                raise OSError("disk full")
            return real(*a, **kw)
        monkeypatch.setattr(mod, "_persist_execution_provenance", flaky)
        with pytest.raises(RegistryError, match="完整性违规"):
            mod.execute_news_decision(
                art, ledger_dir=tmp_path / "ledger", prov_dir=tmp_path / "prov",
                decision_id="d1", contract=_contract(),
                call_fn=lambda m: _Reply(None))

    def test_writer_computes_hashes_non_str_raw_refused(self, tmp_path):
        # archive-re-review#2 Blocker: the writer takes the ACTUAL raw text and
        # computes the hash internally — caller-supplied hashes are gone; a
        # non-str raw is refused before any state is touched
        from workspace.research.ai_research_dept.engine.news_executors import (
            _persist_execution_provenance,
        )
        for bad in (b"bytes", 123, None):
            with pytest.raises(RegistryError):
                _persist_execution_provenance(
                    tmp_path, execution_id="e", decision_id="d", leg="factor",
                    payload_hash="0" * 64, verdict="valid",
                    schema_id="c16_news_horizon_v1", raw=bad,
                    parsed_record={"a": 1})

    def test_parsed_record_rules(self, tmp_path):
        # record-bearing verdicts REQUIRE the actual parsed dict (hash computed
        # internally); record-free verdicts must NOT carry one
        from workspace.research.ai_research_dept.engine.news_executors import (
            _persist_execution_provenance,
        )
        with pytest.raises(RegistryError, match="解析记录"):
            _persist_execution_provenance(
                tmp_path, execution_id="e", decision_id="d", leg="factor",
                payload_hash="0" * 64, verdict="valid",
                schema_id="c16_news_horizon_v1", raw="{}")   # missing record
        with pytest.raises(RegistryError, match="不得携带解析记录"):
            _persist_execution_provenance(
                tmp_path, execution_id="e", decision_id="d", leg="factor",
                payload_hash="0" * 64, verdict="attempt_started",
                schema_id="c16_news_horizon_v1", parsed_record={"a": 1})

    def test_state_machine_second_terminal_refused(self, tmp_path):
        # archive-re-review#2 Blocker (the reviewer's probe, first kill door):
        # appending a SECOND terminal for the same (execution, leg) through the
        # writer is refused outright — one attempt, exactly one terminal
        from workspace.research.ai_research_dept.engine.news_executors import (
            _persist_execution_provenance,
        )
        _persist_execution_provenance(
            tmp_path, execution_id="e", decision_id="d", leg="factor",
            payload_hash="0" * 64, verdict="attempt_started",
            schema_id="c16_news_horizon_v1")
        _persist_execution_provenance(
            tmp_path, execution_id="e", decision_id="d", leg="factor",
            payload_hash="0" * 64, verdict="valid",
            schema_id="c16_news_horizon_v1", raw="{}", parsed_record={"a": 1})
        with pytest.raises(RegistryError, match="恰一终态"):
            _persist_execution_provenance(
                tmp_path, execution_id="e", decision_id="d", leg="factor",
                payload_hash="0" * 64, verdict="valid",
                schema_id="c16_news_horizon_v1", raw="{}",
                parsed_record={"b": 2})

    def test_state_machine_llm_terminal_needs_attempt(self, tmp_path):
        # an LLM terminal without its same-payload attempt_started row is a
        # broken state machine — refused at write
        from workspace.research.ai_research_dept.engine.news_executors import (
            _persist_execution_provenance,
        )
        with pytest.raises(RegistryError, match="状态机"):
            _persist_execution_provenance(
                tmp_path, execution_id="e", decision_id="d", leg="factor",
                payload_hash="0" * 64, verdict="valid",
                schema_id="c16_news_horizon_v1", raw="{}", parsed_record={"a": 1})

    def test_state_machine_deterministic_terminal_no_attempt(self, tmp_path):
        # deterministic terminals are the no-LLM path: an attempt_started row
        # for the same key means someone is splicing paths — refused
        from workspace.research.ai_research_dept.engine.news_executors import (
            _persist_execution_provenance,
        )
        _persist_execution_provenance(
            tmp_path, execution_id="e", decision_id="d", leg="factor",
            payload_hash="0" * 64, verdict="attempt_started",
            schema_id="c16_news_horizon_v1")
        with pytest.raises(RegistryError, match="状态机"):
            _persist_execution_provenance(
                tmp_path, execution_id="e", decision_id="d", leg="factor",
                payload_hash="0" * 64, verdict="deterministic_zero",
                schema_id="c16_news_horizon_v1", raw="{}", parsed_record={"a": 1})


# --------------------------------------------------- zero path + input contract

class TestZeroAndInput:
    def test_zero_population_no_llm(self, tmp_path):
        art = _artifact_context_only()
        out, calls = _execute(tmp_path, art=art)
        assert calls == []
        assert out["outcome"].news_status == "success"
        assert out["evaluation"]["news_final_by_horizon"] == {
            h: 0.0 for h in ("next_open", "1-3d", "5-20d")}
        sel = out["selected_provenance"]
        assert sel["factor"]["verdict"] == "deterministic_zero"
        assert sel["penalty"]["verdict"] == "empty_penalty"

    def test_contract_required(self, tmp_path):
        art = _artifact_full()
        with pytest.raises(RegistryError, match="NewsScoringContract"):
            execute_news_decision(art, ledger_dir=tmp_path, prov_dir=tmp_path,
                                  decision_id="d1", contract={"output_mode": "x"},
                                  call_fn=lambda m: _Reply("{}"))
