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
from workspace.research.ai_research_dept.engine.news_horizon import (  # noqa: E402
    deterministic_zero_factor_record, evaluate_news_horizon,
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


_TERMINALS = {"valid", "invalid", "call_error", "deterministic_zero",
              "empty_penalty"}


def _prov_rows(tmp_path):
    p = tmp_path / "prov" / "execution_provenance.jsonl"
    return [json.loads(ln)
            for ln in p.read_text(encoding="utf-8").splitlines() if ln]


def _write_prov_rows(tmp_path, rows):
    """direct-file write BYPASSING the controlled writer (the attacker's move):
    re-seq + re-seal each row so every row stays individually self-consistent."""
    out = []
    for i, r in enumerate(rows):
        body = {k: v for k, v in r.items() if k not in ("entry_hash", "seq")}
        body["seq"] = i
        out.append({**body, "entry_hash": seal_hash(body)})
    (tmp_path / "prov" / "execution_provenance.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out),
        encoding="utf-8")
    return out


def _replace_terminal(tmp_path, execution_id, leg, drop_attempt=False,
                      **overrides):
    """replace the on-disk terminal for (execution_id, leg) with a forged
    self-consistent row; optionally drop its attempt_started row."""
    kept = []
    for r in _prov_rows(tmp_path):
        mine = r["execution_id"] == execution_id and r["leg"] == leg
        if mine and r["verdict"] in _TERMINALS:
            r = {**r, **overrides}
        if mine and drop_attempt and r["verdict"] == "attempt_started":
            continue
        kept.append(r)
    written = _write_prov_rows(tmp_path, kept)
    return next(r for r in written
                if r["execution_id"] == execution_id and r["leg"] == leg
                and r["verdict"] in _TERMINALS)


def _reeval(bundle, art, record):
    return evaluate_news_horizon(
        record, bundle["records"]["penalty"], art.final_registry,
        output_mode="primary_horizon", primary_decision_horizon="1-3d")


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
        # re-review#4: a hard-fail archive is a per-EXECUTION audit record —
        # it loads via the execution loader; the DECISION loader refuses
        # (no success commitment = no canonical decision archive)
        from workspace.research.ai_research_dept.engine.news_archive import (
            load_and_verify_execution_archive,
        )

        def boom(msgs):
            raise ConnectionError("down")
        art, bundle = _setup(tmp_path, call_fn=boom)
        assert bundle["outcome"].news_status == "hard_failed"
        seal_decision_archive(bundle, art, **_dirs(tmp_path),
                              archive_dir=tmp_path / "arch")
        loaded = load_and_verify_execution_archive(
            "d1", bundle["execution_id"], art, **_dirs(tmp_path),
            archive_dir=tmp_path / "arch")
        assert loaded["evaluation"] is None
        assert loaded["selected_provenance"]["factor"]["verdict"] == "call_error"
        with pytest.raises(RegistryError, match="无 success 执行承诺"):
            load_and_verify_decision_archive(
                "d1", art, **_dirs(tmp_path), archive_dir=tmp_path / "arch")


# --------------------------------------------------- joint verification refusals

class TestJointRefusals:
    def test_evaluation_tamper_refused(self, tmp_path):
        art, bundle = _setup(tmp_path)
        bundle["evaluation"] = dict(bundle["evaluation"], news_final=99.0)
        with pytest.raises(RegistryError, match="重算不符"):
            verify_execution_bundle(bundle, art, **_dirs(tmp_path))

    def test_records_tamper_refused(self, tmp_path):
        # dies at the record<->terminal-row binding (BEFORE the evaluation
        # recompute; re-review#4 rows carry the record verbatim, so the
        # byte-level equality kills even canon-hash-equal variants)
        art, bundle = _setup(tmp_path)
        bundle["records"]["factor"]["factor_scores"][0]["score_0_5"] = 1
        with pytest.raises(RegistryError, match="解析记录本体不符"):
            verify_execution_bundle(bundle, art, **_dirs(tmp_path))

    def test_selected_row_field_tamper_refused(self, tmp_path):
        # dies at the bundle-vs-on-disk equality (the resolved on-disk row is
        # the authority now — re-review#2 moved the kill earlier)
        art, bundle = _setup(tmp_path)
        bundle["selected_provenance"]["factor"]["raw_sha256"] = "a" * 64
        with pytest.raises(RegistryError, match="与盘上唯一状态机终态不符"):
            verify_execution_bundle(bundle, art, **_dirs(tmp_path))

    def test_self_sealed_row_not_on_disk_refused(self, tmp_path):
        # a self-consistent row (entry_hash recomputed) that was never persisted
        # — the bundle is not the authority; must equal the on-disk resolved fact
        art, bundle = _setup(tmp_path)
        row = dict(bundle["selected_provenance"]["factor"])
        row["raw_sha256"] = "b" * 64
        body = {k: v for k, v in row.items() if k != "entry_hash"}
        row["entry_hash"] = seal_hash(body)             # self-sealed, valid shape
        bundle["selected_provenance"]["factor"] = row
        with pytest.raises(RegistryError, match="与盘上唯一状态机终态不符"):
            verify_execution_bundle(bundle, art, **_dirs(tmp_path))

    def test_verdict_status_semantics_refused(self, tmp_path):
        # outcome says factor success, but the on-disk terminal claims
        # call_error — forged by direct file rewrite (bypassing the writer);
        # the verdict/leg-status semantics check is the kill
        art, bundle = _setup(tmp_path)
        forged = _replace_terminal(tmp_path, bundle["execution_id"], "factor",
                                   verdict="call_error", raw_sha256=None,
                                   parsed_record_hash=None)
        bundle["selected_provenance"]["factor"] = forged
        with pytest.raises(RegistryError, match="语义不符"):
            verify_execution_bundle(bundle, art, **_dirs(tmp_path))

    def test_missing_selected_row_refused(self, tmp_path):
        art, bundle = _setup(tmp_path)
        bundle["selected_provenance"]["factor"] = None
        with pytest.raises(RegistryError, match="恰一终态"):
            verify_execution_bundle(bundle, art, **_dirs(tmp_path))

    def test_foreign_execution_id_refused(self, tmp_path):
        # a foreign execution_id has NO on-disk terminals — resolution refuses
        art, bundle = _setup(tmp_path)
        bundle["execution_id"] = "d1:deadbeefdeadbeef"   # not the rows' attempt
        with pytest.raises(RegistryError, match="须恰一"):
            verify_execution_bundle(bundle, art, **_dirs(tmp_path))


# ------------------------------------- terminal-row <-> leg <-> record binding
# (archive-review B2 regressions — each probe reproduced by the reviewer)

class TestTerminalRecordBinding:
    def test_foreign_leg_name_refused_at_persist(self, tmp_path):
        from workspace.research.ai_research_dept.engine.news_executors import (
            _persist_execution_provenance,
        )
        with pytest.raises(RegistryError, match="未注册出处 leg"):
            _persist_execution_provenance(
                tmp_path / "prov", execution_id="e", decision_id="d1",
                leg="foreign_leg", payload_hash="0" * 64, verdict="valid",
                schema_id="c16_news_horizon_v1", raw="{}",
                parsed_record={"a": 1})

    def test_cross_leg_row_in_factor_slot_refused(self, tmp_path):
        # a REAL persisted row of the OTHER leg placed in the factor terminal
        # slot — the bundle row must equal the on-disk resolved FACTOR terminal
        art, bundle = _setup(tmp_path)
        bundle["selected_provenance"]["factor"] = dict(
            bundle["selected_provenance"]["penalty"])   # leg == "penalty"
        with pytest.raises(RegistryError, match="与盘上唯一状态机终态不符"):
            verify_execution_bundle(bundle, art, **_dirs(tmp_path))

    def test_forged_deterministic_zero_with_evidence_refused(self, tmp_path):
        # forged zero terminal REPLACING the real one on disk (attempt row
        # dropped so the state machine reads as a clean no-LLM path) + all-zero
        # records + CONSISTENTLY recomputed evaluation, while the real factor
        # population is NON-empty — must die on the population re-derivation
        art, bundle = _setup(tmp_path)
        zero = deterministic_zero_factor_record()
        forged = _replace_terminal(tmp_path, bundle["execution_id"], "factor",
                                   drop_attempt=True,
                                   verdict="deterministic_zero",
                                   parsed_record_hash=seal_hash(zero))
        bundle["selected_provenance"]["factor"] = forged
        bundle["records"]["factor"] = zero
        bundle["evaluation"] = _reeval(bundle, art, zero)
        with pytest.raises(RegistryError, match="总体为空时合法"):
            verify_execution_bundle(bundle, art, **_dirs(tmp_path))

    def test_deterministic_terminal_with_attempt_row_refused(self, tmp_path):
        # same forgery WITHOUT dropping the attempt row — the on-disk state
        # machine (deterministic terminal must have no attempt) kills earlier
        art, bundle = _setup(tmp_path)
        zero = deterministic_zero_factor_record()
        forged = _replace_terminal(tmp_path, bundle["execution_id"], "factor",
                                   verdict="deterministic_zero",
                                   parsed_record_hash=seal_hash(zero))
        bundle["selected_provenance"]["factor"] = forged
        bundle["records"]["factor"] = zero
        bundle["evaluation"] = _reeval(bundle, art, zero)
        with pytest.raises(RegistryError, match="状态机断裂"):
            verify_execution_bundle(bundle, art, **_dirs(tmp_path))

    def test_records_and_evaluation_joint_tamper_refused(self, tmp_path):
        # tamper the record AND recompute the evaluation consistently — the
        # old evaluation-recompute alone would pass; the record<->terminal-row
        # hash binding must be the kill
        art, bundle = _setup(tmp_path)
        bundle["records"]["factor"]["factor_scores"][0]["score_0_5"] = 1
        bundle["evaluation"] = _reeval(bundle, art, bundle["records"]["factor"])
        with pytest.raises(RegistryError, match="解析记录本体不符"):
            verify_execution_bundle(bundle, art, **_dirs(tmp_path))

    def test_hard_fail_arbitrary_records_refused(self, tmp_path):
        def boom(msgs):
            raise ConnectionError("down")
        art, bundle = _setup(tmp_path, call_fn=boom)
        bundle["records"]["factor"] = {"arbitrary": "json"}
        with pytest.raises(RegistryError, match="硬失败不得携带封存记录"):
            verify_execution_bundle(bundle, art, **_dirs(tmp_path))

    def test_records_shape_extra_key_refused(self, tmp_path):
        art, bundle = _setup(tmp_path)
        bundle["records"] = {**bundle["records"], "extra": {"x": 1}}
        with pytest.raises(RegistryError, match="两键 dict"):
            verify_execution_bundle(bundle, art, **_dirs(tmp_path))

    def test_empty_penalty_record_tamper_refused(self, tmp_path):
        # the deterministic empty record is not free text — field-exact
        art, bundle = _setup(tmp_path, art_fn=_artifact_context_only)
        bundle["records"]["penalty"] = {"penalty_scores": [],
                                        "risk_flags": ["smuggled"]}
        with pytest.raises(RegistryError, match="确定性记录"):
            verify_execution_bundle(bundle, art, **_dirs(tmp_path))

    def test_row_key_set_strict_refused(self, tmp_path):
        # a bundle row with an extra key, re-sealed self-consistently — it is
        # no longer the on-disk fact, the resolved-equality check kills it
        art, bundle = _setup(tmp_path)
        row = dict(bundle["selected_provenance"]["factor"])
        del row["entry_hash"]
        row["note"] = "x"
        row["entry_hash"] = seal_hash(row)
        bundle["selected_provenance"]["factor"] = row
        with pytest.raises(RegistryError, match="与盘上唯一状态机终态不符"):
            verify_execution_bundle(bundle, art, **_dirs(tmp_path))

    # ---- archive-re-review#2 Blocker regressions (the reviewer's probes)

    def test_appended_forged_terminal_breaks_key_verifiability(self, tmp_path):
        # the reviewer's probe, file-level form: a SECOND self-consistent valid
        # terminal appended directly to the provenance file (the controlled
        # writer refuses it — the attacker bypasses the writer) + swapped
        # record + consistently recomputed evaluation. Two terminals for the
        # key = the key has lost verifiability -> fail-closed
        art, bundle = _setup(tmp_path)
        forged_record = _valid_factor_record()
        forged_record["factor_scores"][0]["score_0_5"] = 1
        forged = {**bundle["selected_provenance"]["factor"],
                  "parsed_record_hash": seal_hash(forged_record)}
        written = _write_prov_rows(tmp_path, _prov_rows(tmp_path) + [forged])
        bundle["selected_provenance"]["factor"] = written[-1]
        bundle["records"]["factor"] = forged_record
        bundle["evaluation"] = _reeval(bundle, art, forged_record)
        with pytest.raises(RegistryError, match="须恰一"):
            verify_execution_bundle(bundle, art, **_dirs(tmp_path))

    def test_replaced_terminal_dies_at_ledger_commitment(self, tmp_path):
        # the reviewer's 74.0 -> 50.0 probe, strongest surviving form: REPLACE
        # the real terminal in place (unique on disk, state machine intact,
        # record + evaluation consistently recomputed) — the ledger-committed
        # terminal entry_hash is the kill: the forged row is not the terminal
        # the controlled executor committed to the non-rewritable chain
        art, bundle = _setup(tmp_path)
        forged_record = _valid_factor_record()
        forged_record["factor_scores"][0]["score_0_5"] = 1
        forged = _replace_terminal(tmp_path, bundle["execution_id"], "factor",
                                   parsed_record=forged_record,
                                   parsed_record_hash=seal_hash(forged_record))
        bundle["selected_provenance"]["factor"] = forged
        bundle["records"]["factor"] = forged_record
        bundle["evaluation"] = _reeval(bundle, art, forged_record)
        with pytest.raises(RegistryError, match="承诺不符"):
            verify_execution_bundle(bundle, art, **_dirs(tmp_path))

    def test_naked_hash_commitment_api_is_gone(self):
        # re-review#3 P0: the public API that accepted caller-supplied hashes
        # no longer exists — the only door is the deriving commit authority
        import workspace.research.ai_research_dept.engine.news_decision as nd
        assert not hasattr(nd, "record_execution_commitment")

    def test_gpt_probe_forged_fresh_execution_cannot_commit(self, tmp_path):
        # the reviewer's re-review#3 probe, replayed against the fix: fresh
        # execution_id "d1:api_forged_0001", state-machine-valid fake terminals
        # written through the callable writer, then the commitment authority.
        # The authority derives (it cannot be handed hashes), and the ledger's
        # unique-success rule refuses: the REAL execution already committed
        # this decision's one success
        from workspace.research.ai_research_dept.engine.news_executors import (
            _persist_execution_provenance, commit_execution,
        )
        art, bundle = _setup(tmp_path)          # real success committed
        forged_exec = "d1:api_forged_0001"
        forged_record = _valid_factor_record()
        forged_record["factor_scores"][0]["score_0_5"] = 1
        real_f = bundle["selected_provenance"]["factor"]
        real_p = bundle["selected_provenance"]["penalty"]
        for leg, payload_hash, rec in (
                ("factor", real_f["payload_hash"], forged_record),
                ("penalty", real_p["payload_hash"], _valid_penalty_record())):
            _persist_execution_provenance(
                tmp_path / "prov", execution_id=forged_exec, decision_id="d1",
                leg=leg, payload_hash=payload_hash, verdict="attempt_started",
                schema_id="c16_news_horizon_v1")
            _persist_execution_provenance(
                tmp_path / "prov", execution_id=forged_exec, decision_id="d1",
                leg=leg, payload_hash=payload_hash, verdict="valid",
                schema_id="c16_news_horizon_v1",
                raw=json.dumps(rec, ensure_ascii=False), parsed_record=rec)
        with pytest.raises(RegistryError, match="成功执行唯一|success 执行承诺"):
            commit_execution(
                tmp_path / "ledger", tmp_path / "prov", decision_id="d1",
                execution_id=forged_exec, outcome=bundle["outcome"],
                artifact=art, contract=_contract())


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


# --------------------------------------------------- write-once (review B1)

class TestWriteOnce:
    def test_second_success_execution_refused_at_commitment(self, tmp_path):
        # re-review#3 P0: a second SUCCESS execution of the same decision is
        # now refused at the LEDGER (unique success per decision) — it never
        # even reaches the archive; the sealed archive stays intact
        art, bundle1 = _setup(tmp_path)
        first = seal_decision_archive(bundle1, art, **_dirs(tmp_path),
                                      archive_dir=tmp_path / "arch")
        with pytest.raises(RegistryError, match="成功执行唯一"):
            execute_news_decision(
                art, ledger_dir=tmp_path / "ledger", prov_dir=tmp_path / "prov",
                decision_id="d1", contract=_contract(), call_fn=_call_fn())
        on_disk = json.loads(next(
            (tmp_path / "arch").glob("news_decision_*.json")).read_text(
                encoding="utf-8"))
        assert on_disk["execution_id"] == first["execution_id"]

    def test_hard_fail_then_success_retry_recovers(self, tmp_path):
        # recoverability pin: hard_failed commitments do NOT claim the decision
        # — the success retry commits, seals, and loads
        def boom(msgs):
            raise ConnectionError("down")
        art, fail_bundle = _setup(tmp_path, call_fn=boom)
        assert fail_bundle["outcome"].news_status == "hard_failed"
        good = execute_news_decision(
            art, ledger_dir=tmp_path / "ledger", prov_dir=tmp_path / "prov",
            decision_id="d1", contract=_contract(), call_fn=_call_fn())
        seal_decision_archive(good, art, **_dirs(tmp_path),
                              archive_dir=tmp_path / "arch")
        loaded = load_and_verify_decision_archive(
            "d1", art, **_dirs(tmp_path), archive_dir=tmp_path / "arch")
        assert loaded["outcome"]["news_status"] == "success"

    def test_hard_fail_seal_then_success_seal_coexist(self, tmp_path):
        # re-review#4 P1-a (the reviewer's COMBINED probe): hard_failed ->
        # seal -> success retry -> seal success. Per-execution immutable
        # archives: the success seal SUCCEEDS (own file); the DECISION loader
        # returns the success archive (canonical-success rule); the hard-fail
        # execution archive stays audit-loadable. No bricked decision.
        from workspace.research.ai_research_dept.engine.news_archive import (
            load_and_verify_execution_archive,
        )

        def boom(msgs):
            raise ConnectionError("down")
        art, fail_bundle = _setup(tmp_path, call_fn=boom)
        seal_decision_archive(fail_bundle, art, **_dirs(tmp_path),
                              archive_dir=tmp_path / "arch")
        good = execute_news_decision(
            art, ledger_dir=tmp_path / "ledger", prov_dir=tmp_path / "prov",
            decision_id="d1", contract=_contract(), call_fn=_call_fn())
        seal_decision_archive(good, art, **_dirs(tmp_path),
                              archive_dir=tmp_path / "arch")   # NOT blocked
        canonical = load_and_verify_decision_archive(
            "d1", art, **_dirs(tmp_path), archive_dir=tmp_path / "arch")
        assert canonical["outcome"]["news_status"] == "success"
        assert canonical["execution_id"] == good["execution_id"]
        audit = load_and_verify_execution_archive(
            "d1", fail_bundle["execution_id"], art, **_dirs(tmp_path),
            archive_dir=tmp_path / "arch")
        assert audit["outcome"]["news_status"] == "hard_failed"

    def test_decision_load_after_success_commit_never_returns_hard_fail(
            self, tmp_path):
        # re-review#4 P1-b (the reviewer's TOCTOU end-state): hard-fail archive
        # sealed, success committed but its archive NOT yet sealed — the
        # decision loader must NEVER hand back the hard-fail doc; it points at
        # the missing canonical success archive (recoverable) instead
        def boom(msgs):
            raise ConnectionError("down")
        art, fail_bundle = _setup(tmp_path, call_fn=boom)
        seal_decision_archive(fail_bundle, art, **_dirs(tmp_path),
                              archive_dir=tmp_path / "arch")
        execute_news_decision(
            art, ledger_dir=tmp_path / "ledger", prov_dir=tmp_path / "prov",
            decision_id="d1", contract=_contract(), call_fn=_call_fn())
        with pytest.raises(RegistryError, match="档案缺失"):
            load_and_verify_decision_archive(
                "d1", art, **_dirs(tmp_path), archive_dir=tmp_path / "arch")


class TestCrashRecovery:
    def test_recover_after_commitment_crash(self, tmp_path):
        # re-review#4 crash variant: success committed, process died before
        # sealing — rebuild the bundle from PURE on-disk state and seal
        from workspace.research.ai_research_dept.engine.news_archive import (
            recover_and_seal_success_archive,
        )
        art, bundle = _setup(tmp_path)      # committed; pretend we crashed here
        recovered = recover_and_seal_success_archive(
            "d1", art, **_dirs(tmp_path), archive_dir=tmp_path / "arch")
        assert recovered["evaluation"] == bundle["evaluation"]
        assert recovered["execution_id"] == bundle["execution_id"]
        loaded = load_and_verify_decision_archive(
            "d1", art, **_dirs(tmp_path), archive_dir=tmp_path / "arch")
        assert loaded["archive_sha256"] == recovered["archive_sha256"]

    def test_recover_zero_population_decision(self, tmp_path):
        # deterministic paths (zero factor + empty penalty) recover too
        from workspace.research.ai_research_dept.engine.news_archive import (
            recover_and_seal_success_archive,
        )
        art, bundle = _setup(tmp_path, art_fn=_artifact_context_only)
        recovered = recover_and_seal_success_archive(
            "d1", art, **_dirs(tmp_path), archive_dir=tmp_path / "arch")
        assert recovered["outcome"]["penalty_leg_status"] == "empty_success"
        assert recovered["evaluation"] == bundle["evaluation"]

    def test_recovery_is_idempotent_with_existing_archive(self, tmp_path):
        # archive already sealed and ledger unchanged -> recovery re-derives
        # the identical archive and returns it (write-once idempotency)
        from workspace.research.ai_research_dept.engine.news_archive import (
            recover_and_seal_success_archive,
        )
        art, bundle = _setup(tmp_path)
        sealed = seal_decision_archive(bundle, art, **_dirs(tmp_path),
                                       archive_dir=tmp_path / "arch")
        recovered = recover_and_seal_success_archive(
            "d1", art, **_dirs(tmp_path), archive_dir=tmp_path / "arch")
        assert recovered == sealed

    def test_recovery_requires_success_commitment(self, tmp_path):
        from workspace.research.ai_research_dept.engine.news_archive import (
            recover_and_seal_success_archive,
        )

        def boom(msgs):
            raise ConnectionError("down")
        art, _ = _setup(tmp_path, call_fn=boom)     # hard_failed only
        with pytest.raises(RegistryError, match="无可恢复"):
            recover_and_seal_success_archive(
                "d1", art, **_dirs(tmp_path), archive_dir=tmp_path / "arch")

    def test_identical_reseal_is_idempotent(self, tmp_path):
        # same bundle, unchanged ledger — the fully re-derived archive is
        # byte-identical, so the retry returns the existing archive
        art, bundle = _setup(tmp_path)
        first = seal_decision_archive(bundle, art, **_dirs(tmp_path),
                                      archive_dir=tmp_path / "arch")
        again = seal_decision_archive(bundle, art, **_dirs(tmp_path),
                                      archive_dir=tmp_path / "arch")
        assert again == first
        assert len(list((tmp_path / "arch").glob("news_decision_*.json"))) == 1


# ------------------------------------- load-side identity binding (review Major)

class TestLoadIdentity:
    def test_archive_copy_to_other_decision_refused(self, tmp_path):
        # the reviewer's d1 -> d2 replay: overwrite d2's sealed archive file
        # with d1's bytes — the three-way decision-identity check must kill it
        from workspace.research.ai_research_dept.engine.news_archive import (
            _archive_path,
        )
        art, bundle = _setup(tmp_path)
        seal_decision_archive(bundle, art, **_dirs(tmp_path),
                              archive_dir=tmp_path / "arch")
        art2 = _artifact_full("d2")
        record_decision(tmp_path / "ledger", "d2", art2)
        bundle2 = execute_news_decision(
            art2, ledger_dir=tmp_path / "ledger", prov_dir=tmp_path / "prov",
            decision_id="d2", contract=_contract(), call_fn=_call_fn())
        seal_decision_archive(bundle2, art2, **_dirs(tmp_path),
                              archive_dir=tmp_path / "arch")
        src = _archive_path(tmp_path / "arch", "d1", bundle["execution_id"])
        _archive_path(tmp_path / "arch", "d2",
                      bundle2["execution_id"]).write_bytes(src.read_bytes())
        with pytest.raises(RegistryError, match="三向不符"):
            load_and_verify_decision_archive("d2", art2, **_dirs(tmp_path),
                                             archive_dir=tmp_path / "arch")

    def test_archive_schema_tamper_reseal_refused(self, tmp_path):
        # attacker rewrites archive_schema AND re-seals self-consistently —
        # the schema-value pin must be the kill, not just the seal
        art, bundle = _setup(tmp_path)
        seal_decision_archive(bundle, art, **_dirs(tmp_path),
                              archive_dir=tmp_path / "arch")
        p = next((tmp_path / "arch").glob("news_decision_*.json"))
        doc = json.loads(p.read_text(encoding="utf-8"))
        doc["archive_schema"] = "evil_v2"
        body = {k: v for k, v in doc.items() if k != "archive_sha256"}
        doc["archive_sha256"] = seal_hash(body)
        p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        with pytest.raises(RegistryError, match="archive_schema"):
            load_and_verify_decision_archive("d1", art, **_dirs(tmp_path),
                                             archive_dir=tmp_path / "arch")

    def test_archive_extra_key_reseal_refused(self, tmp_path):
        art, bundle = _setup(tmp_path)
        seal_decision_archive(bundle, art, **_dirs(tmp_path),
                              archive_dir=tmp_path / "arch")
        p = next((tmp_path / "arch").glob("news_decision_*.json"))
        doc = json.loads(p.read_text(encoding="utf-8"))
        doc["note"] = "x"
        body = {k: v for k, v in doc.items() if k != "archive_sha256"}
        doc["archive_sha256"] = seal_hash(body)
        p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        with pytest.raises(RegistryError, match="顶层键集"):
            load_and_verify_decision_archive("d1", art, **_dirs(tmp_path),
                                             archive_dir=tmp_path / "arch")

    def _reseal(self, p, doc):
        body = {k: v for k, v in doc.items() if k != "archive_sha256"}
        doc["archive_sha256"] = seal_hash(body)
        p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    def test_outcome_alias_key_reseal_refused(self, tmp_path):
        # archive-re-review#2 Major: top-level was strict but nested objects
        # could smuggle unverified alias fields — outcome must equal the
        # rebuilt canonical payload field-for-field
        art, bundle = _setup(tmp_path)
        seal_decision_archive(bundle, art, **_dirs(tmp_path),
                              archive_dir=tmp_path / "arch")
        p = next((tmp_path / "arch").glob("news_decision_*.json"))
        doc = json.loads(p.read_text(encoding="utf-8"))
        doc["outcome"]["unverified_alias"] = {"x": 1}
        self._reseal(p, doc)
        with pytest.raises(RegistryError, match="outcome 载荷"):
            load_and_verify_decision_archive("d1", art, **_dirs(tmp_path),
                                             archive_dir=tmp_path / "arch")

    def test_selected_provenance_alias_key_reseal_refused(self, tmp_path):
        art, bundle = _setup(tmp_path)
        seal_decision_archive(bundle, art, **_dirs(tmp_path),
                              archive_dir=tmp_path / "arch")
        p = next((tmp_path / "arch").glob("news_decision_*.json"))
        doc = json.loads(p.read_text(encoding="utf-8"))
        doc["selected_provenance"]["unverified_alias"] = {"x": 1}
        self._reseal(p, doc)
        with pytest.raises(RegistryError, match="两键 dict"):
            load_and_verify_decision_archive("d1", art, **_dirs(tmp_path),
                                             archive_dir=tmp_path / "arch")

    def test_anchor_downgrade_to_earlier_chain_member_refused(self, tmp_path):
        # re-review#3 P1 (the reviewer's probe): move the anchor from the
        # execution-commitment row to the EARLIER decision row — a valid chain
        # member, but the commitment is no longer on the ancestry path ending
        # at the anchored head; membership alone must not accept it
        from workspace.research.ai_research_dept.engine.news_decision import (
            lookup_decision,
        )
        art, bundle = _setup(tmp_path)
        seal_decision_archive(bundle, art, **_dirs(tmp_path),
                              archive_dir=tmp_path / "arch")
        dec_row = lookup_decision(tmp_path / "ledger", "d1")
        p = next((tmp_path / "arch").glob("news_decision_*.json"))
        doc = json.loads(p.read_text(encoding="utf-8"))
        assert doc["ledger_head_at_seal"] != dec_row["entry_hash"]
        doc["ledger_head_at_seal"] = dec_row["entry_hash"]
        self._reseal(p, doc)
        with pytest.raises(RegistryError, match="祖先路径"):
            load_and_verify_decision_archive("d1", art, **_dirs(tmp_path),
                                             archive_dir=tmp_path / "arch")

    def test_genesis_anchor_downgrade_refused(self, tmp_path):
        # archive-re-review#2 Major: rewriting the anchor to genesis + reseal
        # must be refused — sealing always postdates decision registration +
        # execution commitment, so genesis is never a legal anchored head
        art, bundle = _setup(tmp_path)
        seal_decision_archive(bundle, art, **_dirs(tmp_path),
                              archive_dir=tmp_path / "arch")
        p = next((tmp_path / "arch").glob("news_decision_*.json"))
        doc = json.loads(p.read_text(encoding="utf-8"))
        doc["ledger_head_at_seal"] = "0" * 64
        self._reseal(p, doc)
        with pytest.raises(RegistryError, match="不在当前账本链内"):
            load_and_verify_decision_archive("d1", art, **_dirs(tmp_path),
                                             archive_dir=tmp_path / "arch")

    def test_whitespace_variant_ids_get_distinct_paths(self, tmp_path):
        # the canon-based name folded "d A" and "d\tA" onto one file; the
        # byte-exact JSON-pair sha256 name keeps decision AND execution
        # variants distinct, with unambiguous delimiting between the two
        from workspace.research.ai_research_dept.engine.news_archive import (
            _archive_path,
        )
        a = _archive_path(tmp_path, "d A", "e")
        assert a != _archive_path(tmp_path, "d\tA", "e")
        assert a != _archive_path(tmp_path, "d A", "e2")
        assert _archive_path(tmp_path, "d", "x:e") \
            != _archive_path(tmp_path, "d:x", "e")            # no concat ambiguity
        assert len(a.stem.split("news_decision_")[1]) == 64   # full digest
