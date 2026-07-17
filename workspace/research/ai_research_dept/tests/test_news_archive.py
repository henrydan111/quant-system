# NF final-integration unit 1: archive boundary (joint tuple verify + head anchor).
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from workspace.research.ai_research_dept.engine.news_archive import (  # noqa: E402
    load_and_verify_decision_archive, seal_decision_archive,
    verify_execution_bundle,
)
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
    NewsScoringContract, execute_news_decision,
)
from workspace.research.ai_research_dept.engine.news_ingest import (  # noqa: E402
    build_cluster_snapshots,
)
from workspace.research.ai_research_dept.engine.news_seal import (  # noqa: E402
    SealError, seal_hash,
)

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
            "risk_flags": []}


def _call_fn():
    def fn(msgs):
        if "因子分析" in msgs[0]["content"]:
            return _Reply(json.dumps(_valid_factor_record(), ensure_ascii=False))
        return _Reply(json.dumps(_valid_penalty_record(), ensure_ascii=False))
    return fn


def _contract():
    return NewsScoringContract(schema_id="c16_news_horizon_v1",
                               output_mode="primary_horizon",
                               primary_decision_horizon="1-3d")


def _setup(tmp_path, *, art_fn=_artifact_full, decision_id="d1", call_fn=None):
    art = art_fn(decision_id)
    record_decision(tmp_path / "ledger", decision_id, art)
    bundle = execute_news_decision(
        art, ledger_dir=tmp_path / "ledger", prov_dir=tmp_path / "prov",
        decision_id=decision_id, contract=_contract(),
        call_fn=call_fn or _call_fn())
    return art, bundle


def _dirs(tmp_path):
    return dict(ledger_dir=tmp_path / "ledger", prov_dir=tmp_path / "prov",
                contract=_contract())


# --------------------------------------------------- happy paths

class TestSealAndVerify:
    def test_success_archive_round_trip(self, tmp_path):
        art, bundle = _setup(tmp_path)
        archive = seal_decision_archive(bundle, art, **_dirs(tmp_path),
                                        archive_dir=tmp_path / "arch")
        assert len(archive["archive_sha256"]) == 64
        assert archive["evaluation"]["news_final"] == 74.0
        loaded = load_and_verify_decision_archive(
            "d1", art, **_dirs(tmp_path), archive_dir=tmp_path / "arch")
        assert loaded["archive_sha256"] == archive["archive_sha256"]
        assert loaded["ledger_head_at_seal"] != "0" * 64   # anchored to real head

    def test_zero_population_archive_round_trip(self, tmp_path):
        # joint empty-penalty tuple sealed and re-verified
        art, bundle = _setup(tmp_path, art_fn=_artifact_context_only)
        seal_decision_archive(bundle, art, **_dirs(tmp_path),
                              archive_dir=tmp_path / "arch")
        loaded = load_and_verify_decision_archive(
            "d1", art, **_dirs(tmp_path), archive_dir=tmp_path / "arch")
        assert loaded["outcome"]["penalty_leg_status"] == "empty_success"
        assert loaded["selected_provenance"]["penalty"]["verdict"] == "empty_penalty"

    def test_hard_fail_archive_round_trip(self, tmp_path):
        def boom(msgs):
            raise ConnectionError("down")
        art, bundle = _setup(tmp_path, call_fn=boom)
        assert bundle["outcome"].news_status == "hard_failed"
        seal_decision_archive(bundle, art, **_dirs(tmp_path),
                              archive_dir=tmp_path / "arch")
        loaded = load_and_verify_decision_archive(
            "d1", art, **_dirs(tmp_path), archive_dir=tmp_path / "arch")
        assert loaded["evaluation"] is None
        assert loaded["selected_provenance"]["factor"]["verdict"] == "call_error"


# --------------------------------------------------- joint verification refusals

class TestJointRefusals:
    def test_evaluation_tamper_refused(self, tmp_path):
        art, bundle = _setup(tmp_path)
        bundle["evaluation"] = dict(bundle["evaluation"], news_final=99.0)
        with pytest.raises(RegistryError, match="重算不符"):
            verify_execution_bundle(bundle, art, **_dirs(tmp_path))

    def test_records_tamper_refused(self, tmp_path):
        art, bundle = _setup(tmp_path)
        bundle["records"]["factor"]["factor_scores"][0]["score_0_5"] = 1
        with pytest.raises(RegistryError, match="重算不符"):
            verify_execution_bundle(bundle, art, **_dirs(tmp_path))

    def test_selected_row_field_tamper_refused(self, tmp_path):
        art, bundle = _setup(tmp_path)
        bundle["selected_provenance"]["factor"]["raw_sha256"] = "a" * 64
        with pytest.raises(RegistryError, match="entry_hash 重算不符"):
            verify_execution_bundle(bundle, art, **_dirs(tmp_path))

    def test_self_sealed_row_not_on_disk_refused(self, tmp_path):
        # a self-consistent row (entry_hash recomputed) that was never persisted
        art, bundle = _setup(tmp_path)
        row = dict(bundle["selected_provenance"]["factor"])
        row["raw_sha256"] = "b" * 64
        body = {k: v for k, v in row.items() if k != "entry_hash"}
        row["entry_hash"] = seal_hash(body)             # self-sealed, valid shape
        bundle["selected_provenance"]["factor"] = row
        with pytest.raises(RegistryError, match="不在盘上出处文件"):
            verify_execution_bundle(bundle, art, **_dirs(tmp_path))

    def test_verdict_status_semantics_refused(self, tmp_path):
        # outcome says factor success, but the selected row claims call_error —
        # craft a persisted-looking row via a REAL persisted attempt row (wrong
        # verdict class) to isolate the semantic check
        art, bundle = _setup(tmp_path)
        from workspace.research.ai_research_dept.engine.news_executors import (
            persist_execution_provenance,
        )
        wrong = persist_execution_provenance(
            tmp_path / "prov", execution_id=bundle["execution_id"],
            decision_id="d1", leg="factor",
            payload_hash=bundle["selected_provenance"]["factor"]["payload_hash"],
            raw_sha256=None, verdict="call_error",
            schema_id="c16_news_horizon_v1")
        bundle["selected_provenance"]["factor"] = wrong
        with pytest.raises(RegistryError, match="语义不符"):
            verify_execution_bundle(bundle, art, **_dirs(tmp_path))

    def test_missing_selected_row_refused(self, tmp_path):
        art, bundle = _setup(tmp_path)
        bundle["selected_provenance"]["factor"] = None
        with pytest.raises(RegistryError, match="恰一终态"):
            verify_execution_bundle(bundle, art, **_dirs(tmp_path))

    def test_foreign_execution_id_refused(self, tmp_path):
        art, bundle = _setup(tmp_path)
        bundle["execution_id"] = "d1:deadbeefdeadbeef"   # not the rows' attempt
        with pytest.raises(RegistryError, match="身份不符"):
            verify_execution_bundle(bundle, art, **_dirs(tmp_path))


# --------------------------------------------------- archive integrity + anchor

class TestArchiveIntegrity:
    def test_archive_file_tamper_refused(self, tmp_path):
        art, bundle = _setup(tmp_path)
        seal_decision_archive(bundle, art, **_dirs(tmp_path),
                              archive_dir=tmp_path / "arch")
        p = next((tmp_path / "arch").glob("news_decision_*.json"))
        doc = json.loads(p.read_text(encoding="utf-8"))
        doc["evaluation"]["news_final"] = 99.0
        p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        with pytest.raises(SealError):
            load_and_verify_decision_archive("d1", art, **_dirs(tmp_path),
                                             archive_dir=tmp_path / "arch")

    def test_wholesale_ledger_replacement_caught(self, tmp_path):
        # BINDING #6: rewrite the ledger as a self-consistent chain that still
        # contains d1's FIELDS (require_recorded passes) but different entry
        # hashes. TWO tripwires exist: the rebuilt payload's sealed
        # ledger_entry_hash mismatches first (LegIntegrityError), and the
        # archived head-anchor is the backstop for any path that does not
        # rebuild payloads. Either refusal pins the property.
        from workspace.research.ai_research_dept.engine.news_legs import (
            LegIntegrityError,
        )
        art, bundle = _setup(tmp_path)
        seal_decision_archive(bundle, art, **_dirs(tmp_path),
                              archive_dir=tmp_path / "arch")
        (tmp_path / "ledger" / "decision_ledger.jsonl").unlink()
        other = _artifact_full("d0")                    # prepend a foreign decision
        record_decision(tmp_path / "ledger", "d0", other)
        record_decision(tmp_path / "ledger", "d1", art) # same fields, new chain
        with pytest.raises((RegistryError, LegIntegrityError)):
            load_and_verify_decision_archive("d1", art, **_dirs(tmp_path),
                                             archive_dir=tmp_path / "arch")

    def test_legitimate_chain_growth_still_verifies(self, tmp_path):
        # appending AFTER the seal keeps d1's row bytes and the archived head as
        # an ancestor — verification must still pass (anchor ≠ freeze)
        art, bundle = _setup(tmp_path)
        seal_decision_archive(bundle, art, **_dirs(tmp_path),
                              archive_dir=tmp_path / "arch")
        record_decision(tmp_path / "ledger", "d2", _artifact_full("d2"))
        loaded = load_and_verify_decision_archive(
            "d1", art, **_dirs(tmp_path), archive_dir=tmp_path / "arch")
        assert loaded["decision_id"] == "d1"

    def test_wrong_contract_refused(self, tmp_path):
        art, bundle = _setup(tmp_path)
        seal_decision_archive(bundle, art, **_dirs(tmp_path),
                              archive_dir=tmp_path / "arch")
        other = NewsScoringContract(schema_id="c16_news_horizon_v1",
                                    output_mode="primary_horizon",
                                    primary_decision_horizon="next_open")
        with pytest.raises(RegistryError, match="契约"):
            load_and_verify_decision_archive(
                "d1", art, ledger_dir=tmp_path / "ledger",
                prov_dir=tmp_path / "prov", contract=other,
                archive_dir=tmp_path / "arch")

    def test_missing_archive_refused(self, tmp_path):
        art, _ = _setup(tmp_path)
        with pytest.raises(RegistryError, match="档案缺失"):
            load_and_verify_decision_archive("d1", art, **_dirs(tmp_path),
                                             archive_dir=tmp_path / "arch")
