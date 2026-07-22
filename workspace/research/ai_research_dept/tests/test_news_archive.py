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

    def test_recovery_idempotent_after_chain_growth(self, tmp_path):
        # re-review#5 P2 (the reviewer's probe): archive sealed, then an
        # UNRELATED decision appended to the ledger — recovery must return the
        # existing archive, not refuse on a differing ledger_head_at_seal
        from workspace.research.ai_research_dept.engine.news_archive import (
            recover_and_seal_success_archive,
        )
        art, bundle = _setup(tmp_path)
        sealed = seal_decision_archive(bundle, art, **_dirs(tmp_path),
                                       archive_dir=tmp_path / "arch")
        record_decision(tmp_path / "ledger", "d9", _artifact_full("d9"))
        recovered = recover_and_seal_success_archive(
            "d1", art, **_dirs(tmp_path), archive_dir=tmp_path / "arch")
        assert recovered == sealed


class TestContractCommitmentBinding:
    # re-review#5 P0: the frozen contract (incl. primary_decision_horizon,
    # which outcome_hash does NOT cover) is hash-bound into the commitment;
    # same-schema/same-mode/different-primary substitution must be refused
    # BEFORE any file is written — on seal AND on recovery

    def _alt_contract(self):
        return NewsScoringContract(schema_id="c16_news_horizon_v1",
                                   output_mode="primary_horizon",
                                   primary_decision_horizon="next_open")

    def test_seal_with_different_primary_horizon_refused(self, tmp_path):
        # the reviewer's probe, direct-seal form: evaluation consistently
        # recomputed under the substitute contract, so the contract<->commitment
        # binding must be the kill — and nothing may reach disk
        from workspace.research.ai_research_dept.engine.news_horizon import (
            evaluate_news_horizon,
        )
        art, bundle = _setup(tmp_path)
        alt = self._alt_contract()
        bundle["evaluation"] = evaluate_news_horizon(
            bundle["records"]["factor"], bundle["records"]["penalty"],
            art.final_registry, output_mode="primary_horizon",
            primary_decision_horizon="next_open")
        with pytest.raises(RegistryError, match="契约字段不可替换"):
            seal_decision_archive(
                bundle, art, ledger_dir=tmp_path / "ledger",
                prov_dir=tmp_path / "prov", contract=alt,
                archive_dir=tmp_path / "arch")
        assert not list((tmp_path / "arch").glob("news_decision_*.json"))

    def test_recovery_with_different_primary_horizon_refused(self, tmp_path):
        # the reviewer's probe, recovery form: crash after commitment, then
        # recover under the substitute contract — refused before writing;
        # recovery under the COMMITTED contract still succeeds afterwards
        from workspace.research.ai_research_dept.engine.news_archive import (
            recover_and_seal_success_archive,
        )
        art, bundle = _setup(tmp_path)          # committed; pretend crash
        with pytest.raises(RegistryError, match="契约字段不可替换"):
            recover_and_seal_success_archive(
                "d1", art, ledger_dir=tmp_path / "ledger",
                prov_dir=tmp_path / "prov", contract=self._alt_contract(),
                archive_dir=tmp_path / "arch")
        assert not list((tmp_path / "arch").glob("news_decision_*.json"))
        recovered = recover_and_seal_success_archive(
            "d1", art, **_dirs(tmp_path), archive_dir=tmp_path / "arch")
        assert recovered["evaluation"] == bundle["evaluation"]

    def test_load_requires_committed_contract(self, tmp_path):
        # the loaders run the same commitment binding: a substitute contract
        # cannot read the canonical archive either
        art, bundle = _setup(tmp_path)
        seal_decision_archive(bundle, art, **_dirs(tmp_path),
                              archive_dir=tmp_path / "arch")
        with pytest.raises(RegistryError, match="契约"):
            load_and_verify_decision_archive(
                "d1", art, ledger_dir=tmp_path / "ledger",
                prov_dir=tmp_path / "prov", contract=self._alt_contract(),
                archive_dir=tmp_path / "arch")


class _EvilContract(NewsScoringContract):
    # archive-re-review#6 P0 (the reviewer's probe): a legal frozen-dataclass
    # SUBCLASS whose fields say 1-3d but whose overridden _payload() claims
    # next_open — the self-seal and any virtual-call site would hash the
    # overridden claim while the evaluator reads the real fields
    def _payload(self):
        return {"schema_id": self.schema_id, "output_mode": self.output_mode,
                "primary_decision_horizon": "next_open"}


class TestExactTypeBoundaries:
    def _evil(self):
        return _EvilContract(schema_id="c16_news_horizon_v1",
                             output_mode="primary_horizon",
                             primary_decision_horizon="1-3d")

    def test_evil_contract_refused_at_runner_before_any_write(self, tmp_path):
        # the reviewer's flow: record_decision -> execute with the evil
        # contract — refused at entry; NOTHING reaches provenance or ledger
        art = _artifact_full("d1")
        record_decision(tmp_path / "ledger", "d1", art)
        with pytest.raises(RegistryError, match="子类"):
            execute_news_decision(
                art, ledger_dir=tmp_path / "ledger", prov_dir=tmp_path / "prov",
                decision_id="d1", contract=self._evil(), call_fn=_call_fn())
        assert not (tmp_path / "prov" / "execution_provenance.jsonl").exists()
        from workspace.research.ai_research_dept.engine.news_decision import (
            _ledger_path, _read_chain,
        )
        assert all(e["kind"] == "decision"
                   for e in _read_chain(_ledger_path(tmp_path / "ledger")))

    def test_evil_contract_refused_at_seal_and_recovery(self, tmp_path):
        from workspace.research.ai_research_dept.engine.news_archive import (
            recover_and_seal_success_archive,
        )
        art, bundle = _setup(tmp_path)              # good execution committed
        with pytest.raises(RegistryError, match="子类"):
            seal_decision_archive(
                bundle, art, ledger_dir=tmp_path / "ledger",
                prov_dir=tmp_path / "prov", contract=self._evil(),
                archive_dir=tmp_path / "arch")
        with pytest.raises(RegistryError, match="子类"):
            recover_and_seal_success_archive(
                "d1", art, ledger_dir=tmp_path / "ledger",
                prov_dir=tmp_path / "prov", contract=self._evil(),
                archive_dir=tmp_path / "arch")
        assert not list((tmp_path / "arch").glob("news_decision_*.json"))

    def test_evil_contract_refused_at_commit_authority(self, tmp_path):
        from workspace.research.ai_research_dept.engine.news_executors import (
            commit_execution,
        )
        art, bundle = _setup(tmp_path)
        with pytest.raises(RegistryError, match="子类"):
            commit_execution(
                tmp_path / "ledger", tmp_path / "prov", decision_id="d1",
                execution_id=bundle["execution_id"], outcome=bundle["outcome"],
                artifact=art, contract=self._evil())

    def test_evil_outcome_subclass_refused(self, tmp_path):
        # same invariant class, outcome side: a NewsLegOutcome subclass with an
        # overridden _payload cannot enter the joint verification
        from workspace.research.ai_research_dept.engine.news_legs import (
            NewsLegOutcome,
        )

        class _EvilOutcome(NewsLegOutcome):
            def _payload(self):
                return {**NewsLegOutcome._payload(self),
                        "news_status": "hard_failed"}
        art, bundle = _setup(tmp_path)
        o = bundle["outcome"]
        bundle["outcome"] = _EvilOutcome(
            decision_id=o.decision_id, output_mode=o.output_mode,
            factor_leg_status=o.factor_leg_status,
            penalty_eligible_count=o.penalty_eligible_count,
            penalty_eligible_set_hash=o.penalty_eligible_set_hash,
            penalty_leg_status=o.penalty_leg_status, news_status=o.news_status,
            shadow_complete=o.shadow_complete,
            decision_complete=o.decision_complete,
            binding_eligible=o.binding_eligible,
            factor_payload_hash=o.factor_payload_hash,
            penalty_payload_hash=o.penalty_payload_hash)
        with pytest.raises(RegistryError, match="恰 NewsLegOutcome"):
            verify_execution_bundle(bundle, art, **_dirs(tmp_path))

    def test_canonical_helpers_match_class_payload_no_drift(self, tmp_path):
        # re-review#9 self-review: every sealed class's _payload() must be the
        # SAME single definition the boundary hashes through — a re-introduced
        # dict literal (the drift the self-review caught for contract/outcome)
        # would silently make a genuine object's self-seal disagree with the
        # boundary canonical recompute. Pin equality for a genuine instance of
        # every class that has a module-level canonical helper.
        from workspace.research.ai_research_dept.engine.news_cards import (
            artifact_canonical_payload, attribute_row_canonical_payload,
            base_fact_canonical_payload, bundle_canonical_payload,
            card_canonical_payload,
        )
        from workspace.research.ai_research_dept.engine.news_evidence import (
            card_record_canonical_payload, registry_canonical_payload,
        )
        from workspace.research.ai_research_dept.engine.news_executors import (
            contract_canonical_payload,
        )
        from workspace.research.ai_research_dept.engine.news_legs import (
            outcome_canonical_payload,
        )
        art, bundle = _setup(tmp_path)
        contract, outcome = _contract(), bundle["outcome"]
        assert contract._payload() == contract_canonical_payload(contract)
        assert outcome._payload() == outcome_canonical_payload(outcome)
        assert art._payload() == artifact_canonical_payload(art)
        assert art.card._payload() == card_canonical_payload(art.card)
        assert art.bundle._payload() == bundle_canonical_payload(art.bundle)
        assert art.final_registry._payload() \
            == registry_canonical_payload(art.final_registry)
        assert art.base_facts[0]._payload() \
            == base_fact_canonical_payload(art.base_facts[0])
        assert art.rows[0]._payload() \
            == attribute_row_canonical_payload(art.rows[0])
        rec = next(iter(art.final_registry.records.values()))
        assert rec._payload() == card_record_canonical_payload(rec)

    def test_evil_artifact_subclass_refused_before_recording(self, tmp_path):
        # archive-re-review#7 P0 (the reviewer's probe): a D7DecisionArtifact
        # subclass built from the REAL components but overriding _payload() to
        # mint a forged artifact_hash — verify_d7_artifact must refuse it on
        # exact-type, so it never records / executes / seals
        from workspace.research.ai_research_dept.engine.news_cards import (
            D7DecisionArtifact, verify_d7_artifact,
        )
        art = _artifact_full("d1")

        class _EvilArtifact(D7DecisionArtifact):
            def _payload(self):
                return {**D7DecisionArtifact._payload(self),
                        "final_registry_hash": "f" * 64}
        evil = _EvilArtifact(
            card=art.card, base_facts=art.base_facts,
            source_registry=art.source_registry, rows=art.rows,
            bundle=art.bundle, final_registry=art.final_registry)
        assert evil.artifact_hash != art.artifact_hash     # forged identity
        with pytest.raises(RegistryError, match="恰 D7DecisionArtifact"):
            verify_d7_artifact(evil)
        with pytest.raises(RegistryError, match="恰 D7DecisionArtifact"):
            record_decision(tmp_path / "ledger", "d1", evil)

    def test_polymorphic_frozenset_field_neutralized(self, tmp_path):
        # archive-re-review#11 P0 (the reviewer's probe): a frozenset SUBCLASS
        # that iterates (sorted -> hash) as context_only but membership (in ->
        # authorize) as factor_positive. CardRecord.__post_init__ must coerce
        # allowed_uses to a PLAIN frozenset snapshotted from one iteration, so
        # "what got hashed" == "what authorize reads" — the decoupling is gone.
        from workspace.research.ai_research_dept.engine.news_evidence import (
            CardRecord, authorize, card_record_canonical_payload,
        )
        from workspace.research.ai_research_dept.engine.news_seal import seal_hash

        class _EvilUses(frozenset):
            def __iter__(self):                 # hashing sees context_only
                return iter(["context_only"])
            def __contains__(self, x):          # authorize sees factor_positive
                return x in ("factor_positive", "context_only")
        evil = _EvilUses(["context_only"])
        # content_hash self-consistent for a context_only record
        payload = {"record_id": "NFX01", "domain": "news",
                   "evidence_class": "attention_only",
                   "allowed_uses": ["context_only"], "allowed_consumers": ["news"],
                   "allowed_dimensions": [], "record_schema_id": "generic_v1",
                   "derivation": []}
        rec = CardRecord(record_id="NFX01", domain="news",
                         evidence_class="attention_only", allowed_uses=evil,
                         allowed_consumers=frozenset({"news"}),
                         allowed_dimensions=frozenset(), record_schema_id="generic_v1",
                         derivation=(), content_hash=seal_hash(payload))
        # the stored field is a PLAIN frozenset, not the evil subclass
        assert type(rec.allowed_uses) is frozenset
        assert rec.allowed_uses == frozenset({"context_only"})
        # hashing and authorization now agree: NOT factor_positive
        assert card_record_canonical_payload(rec)["allowed_uses"] == ["context_only"]
        assert authorize(rec, use="factor_positive", consumer_seat="news",
                         target_dimension="event_materiality") is False

    def test_dict_injected_record_field_refused_at_construction(self, tmp_path):
        # archive-re-review#12 P0 (the reviewer's probe): a stateful mapping
        # injects an evil frozenset into a record's __dict__ during the single
        # items() iteration (NO object.__setattr__). The registry must rebuild
        # each value as an independent base-immutable and assert base field
        # types — the injected subclass is refused, nothing seals.
        from workspace.research.ai_research_dept.engine.news_evidence import (
            SealedCardRegistry, build_card_record, build_card_registry,
        )

        class _EvilFS(frozenset):
            def __iter__(self):
                return iter(["context_only"])        # hash sees context_only
            def __contains__(self, x):
                return x in ("context_only", "factor_positive")  # authz differs

        class _Injector(dict):
            def items(self):
                out = []
                for k, v in list(super().items()):
                    v.__dict__["allowed_uses"] = _EvilFS(["context_only"])
                    out.append((k, v))
                return iter(out)
        rec = build_card_record("NFD01", domain="news", evidence_class="NFD",
                                allowed_uses={"context_only"},
                                allowed_consumers={"news"})
        good = build_card_registry("2025-01-27T18:00:00", [rec])
        rec2 = build_card_record("NFD01", domain="news", evidence_class="NFD",
                                 allowed_uses={"context_only"},
                                 allowed_consumers={"news"})
        with pytest.raises(RegistryError, match="frozenset"):
            SealedCardRegistry(cutoff_iso="2025-01-27T18:00:00",
                               records=_Injector({"NFD01": rec2}),
                               registry_hash=good.registry_hash)

    def test_dict_injection_after_construction_refused_at_consume(self, tmp_path):
        # even post-construction, injecting an evil subclass into a stored
        # record's __dict__ is caught the next time the registry is consumed
        # (require_sealed_registry re-asserts base field types)
        from workspace.research.ai_research_dept.engine.news_evidence import (
            require_sealed_registry,
        )
        art = _artifact_full("d1")
        reg = art.source_registry
        victim = next(iter(reg.records.values()))

        class _EvilFS(frozenset):
            def __contains__(self, x): return True
        victim.__dict__["allowed_uses"] = _EvilFS(victim.allowed_uses)
        with pytest.raises(RegistryError, match="frozenset"):
            require_sealed_registry(reg)

    def test_fake_outcome_hash_subclass_refused(self, tmp_path):
        # archive-re-review#12 P1: a str-subclass outcome_hash must be refused
        # before verify/equality, so it cannot serialize a fake hash into an
        # archive that then fails to reload
        from workspace.research.ai_research_dept.engine.news_legs import (
            NewsLegOutcome,
        )
        _, bundle = _setup(tmp_path)
        o = bundle["outcome"]

        class _EvilHash(str):
            def __eq__(self, x): return True
            def __ne__(self, x): return False
            def __hash__(self): return hash(str(self))
        with pytest.raises(RegistryError, match="outcome_hash 须恰 str"):
            NewsLegOutcome(
                decision_id=o.decision_id, output_mode=o.output_mode,
                factor_leg_status=o.factor_leg_status,
                penalty_eligible_count=o.penalty_eligible_count,
                penalty_eligible_set_hash=o.penalty_eligible_set_hash,
                penalty_leg_status=o.penalty_leg_status, news_status=o.news_status,
                shadow_complete=o.shadow_complete,
                decision_complete=o.decision_complete,
                binding_eligible=o.binding_eligible,
                factor_payload_hash=o.factor_payload_hash,
                penalty_payload_hash=o.penalty_payload_hash,
                outcome_hash=_EvilHash(o.outcome_hash))

    def test_registry_key_record_id_swap_refused(self, tmp_path):
        # archive-re-review#13 P0: the registry sealed only the VALUE hash set,
        # not the key->record_id binding. Swapping two keys in
        # final_registry.__dict__["records"] leaves registry_hash unchanged but
        # get(NFD01) returns NFR01's risk content. The (key, hash)-pair seal +
        # key==record_id enforcement must refuse it (no object.__setattr__).
        from types import MappingProxyType
        from workspace.research.ai_research_dept.engine.news_evidence import (
            require_sealed_registry,
        )
        art = _artifact_full("d1")
        reg = art.final_registry
        recs = dict(reg.records)
        ids = [rid for rid in recs if "." not in rid]   # top-level records
        a, b = ids[0], ids[1]
        swapped = dict(recs)
        swapped[a], swapped[b] = recs[b], recs[a]        # key<->record_id broken
        reg.__dict__["records"] = MappingProxyType(swapped)
        with pytest.raises(RegistryError, match="键|record_id"):
            require_sealed_registry(reg)

    def test_evil_outcome_field_refused_before_any_field_read(self, tmp_path):
        # archive-re-review#15 P1 (the reviewer's attack): an evil penalty_leg_
        # status whose comparison has a side effect that would swap
        # bundle["outcome"] during _rebuild_leg_payloads. The consume-time
        # assert moved to the TOP of verify_execution_bundle catches the field
        # (type() is not str) BEFORE any comparison/read fires the side effect.
        art, bundle = _setup(tmp_path)
        fired = {"cmp": False}

        class _EvilStatus(str):
            def __eq__(self, x):
                fired["cmp"] = True
                return str.__eq__(self, x)
            def __hash__(self): return hash(str(self))
        bundle["outcome"].__dict__["penalty_leg_status"] = _EvilStatus(
            bundle["outcome"].penalty_leg_status)
        with pytest.raises(RegistryError, match="penalty_leg_status 须恰 str"):
            verify_execution_bundle(bundle, art, **_dirs(tmp_path))
        assert fired["cmp"] is False        # caught before the field was compared

    def test_seal_consumes_independent_verified_snapshot(self, tmp_path):
        # archive-re-review#15 P1: verify produces an INDEPENDENT type-closed
        # outcome snapshot; seal writes THAT, never re-reads live bundle. So a
        # post-verify swap of bundle["outcome"] cannot change what seals.
        art, bundle = _setup(tmp_path)
        result = verify_execution_bundle(bundle, art, **_dirs(tmp_path))
        v = result["verified"]                            # full archive payload (dicts)
        # the reconstructed outcome object is independent of bundle["outcome"]
        assert result["verified_outcome"] is not bundle["outcome"]
        assert result["verified_outcome"].outcome_hash == bundle["outcome"].outcome_hash
        assert v["execution_id"] == bundle["execution_id"]
        # the verified payload is a pure-JSON deep snapshot (no live aliases)
        assert v["records"] is not bundle["records"]
        assert v["selected_provenance"]["factor"] is not bundle["selected_provenance"]["factor"]
        archive = seal_decision_archive(bundle, art, **_dirs(tmp_path),
                                        archive_dir=tmp_path / "arch")
        assert archive["outcome"]["output_mode"] == v["outcome"]["output_mode"]
        loaded = load_and_verify_decision_archive(
            "d1", art, **_dirs(tmp_path), archive_dir=tmp_path / "arch")
        assert loaded["outcome"]["output_mode"] == "primary_horizon"

    def test_archive_records_provenance_from_disk_resolved(self, tmp_path):
        # archive-re-review#16 P1: the archive's records and selected_provenance
        # come from the DISK-resolved terminal rows, not the caller's bundle.
        art, bundle = _setup(tmp_path)
        archive = seal_decision_archive(bundle, art, **_dirs(tmp_path),
                                        archive_dir=tmp_path / "arch")
        rows = _prov_rows(tmp_path)
        f_term = next(r for r in rows if r["leg"] == "factor"
                      and r["verdict"] in _TERMINALS)
        assert archive["records"]["factor"] == f_term["parsed_record"]
        assert archive["selected_provenance"]["factor"]["entry_hash"] \
            == f_term["entry_hash"]

    def test_container_subclass_selected_provenance_refused_at_snapshot(self, tmp_path):
        # archive-re-review#20 P1: selected_provenance as a dict SUBCLASS (whose
        # get()/items() could run caller code, e.g. tamper live inputs) is
        # refused at the deep-plain-json entry gate — its container methods are
        # NEVER invoked (the exact-type check precedes any access).
        art, bundle = _setup(tmp_path)
        fired = {"n": 0}

        class _EvilSel(dict):
            def get(self, k, default=None):
                fired["n"] += 1
                art.__dict__["artifact_hash"] = "0" * 64
                return super().get(k, default)
            def items(self):
                fired["n"] += 1
                return super().items()
        bundle["selected_provenance"] = _EvilSel(dict(bundle["selected_provenance"]))
        with pytest.raises(RegistryError, match="非纯 JSON"):
            seal_decision_archive(bundle, art, **_dirs(tmp_path),
                                  archive_dir=tmp_path / "arch")
        assert fired["n"] == 0                          # get/items never called
        assert not list((tmp_path / "arch").glob("*.json"))

    def test_selected_row_subclass_refused_at_snapshot(self, tmp_path):
        # archive-re-review#19/#20 P1 (the reviewer's attack): a selected row
        # that is a dict subclass whose stateful items()/__ne__ would mutate the
        # trusted disk row on a second serialization. The deep-plain-json entry
        # gate refuses the subclass container BEFORE any items()/__ne__ can run;
        # covers factor AND penalty.
        fired = {"n": 0}

        class _EvilRow(dict):
            def __ne__(self, other):
                fired["n"] += 1
                if isinstance(other, dict):
                    other["parsed_record"] = {"FORGED": True}
                return False
            def items(self):
                fired["n"] += 1
                return super().items()
        for leg in ("factor", "penalty"):
            art, bundle = _setup(tmp_path / leg)
            genuine = dict(bundle["selected_provenance"][leg])
            bundle["selected_provenance"][leg] = _EvilRow(genuine)
            with pytest.raises(RegistryError, match="非纯 JSON"):
                seal_decision_archive(
                    bundle, art, ledger_dir=tmp_path / leg / "ledger",
                    prov_dir=tmp_path / leg / "prov", contract=_contract(),
                    archive_dir=tmp_path / leg / "arch")
        assert fired["n"] == 0                          # items()/__ne__ never called

    def test_registry_items_callback_cannot_swap_verified_base_facts(self, tmp_path):
        # archive-re-review#23 P1: require_sealed_registry calls the live source-
        # registry mapping's .items(); a malicious mapping that, during .items(),
        # swaps artifact.base_facts to EvilFacts must NOT poison verification —
        # verify_d7_artifact reconstructs card/bundle/facts/rows into independent
        # copies BEFORE the registry snapshot and never re-reads live artifact.*.
        from types import MappingProxyType
        from workspace.research.ai_research_dept.engine.news_cards import (
            verify_d7_artifact,
        )
        art = _artifact_full("d1")
        fired = {"acc": 0}

        class _EvilFact:
            @property
            def fact_hash(self):
                fired["acc"] += 1
                return "0" * 64

        class _SwapMap(dict):
            def items(self):
                # phase-substitution: swap the outer artifact's verified facts
                object.__setattr__(art, "base_facts", (_EvilFact(),))
                return super().items()
        object.__setattr__(art.source_registry, "records",
                           _SwapMap(dict(art.source_registry.records)))
        # verify_d7_artifact still succeeds on the genuine (copied) components;
        # the swapped-in EvilFact.fact_hash accessor is never read
        verify_d7_artifact(art)
        assert fired["acc"] == 0

    def test_load_rejects_nonstr_decision_id_before_compare(self, tmp_path):
        # archive-re-review#23 P1: load/recover reject a non-str decision_id
        # before it reaches any `==` (which would call a malicious __eq__).
        art, bundle = _setup(tmp_path)
        seal_decision_archive(bundle, art, **_dirs(tmp_path),
                              archive_dir=tmp_path / "arch")
        fired = {"eq": False}

        class _EvilId(str):
            def __eq__(self, o):
                fired["eq"] = True
                return True
            def __hash__(self): return 0
        with pytest.raises(RegistryError, match="须恰 str"):
            load_and_verify_decision_archive(
                _EvilId("d1"), art, **_dirs(tmp_path), archive_dir=tmp_path / "arch")
        assert fired["eq"] is False

    def test_registry_callback_bundle_swap_invisible_to_seal_and_load(self, tmp_path):
        # GPT #23 P1#1: verify_d7_artifact used to return the LIVE artifact, so a
        # registry-mapping .items() callback that swaps artifact.bundle to an
        # EvilBundle (whose accessors return the real values) survived into
        # verify_execution_bundle's post-verify reads — seal succeeded WITH the
        # evil accessor running. Now every consumer binds the independent copy
        # returned by verify_d7_artifact: seal AND decision-load both succeed on
        # the genuine data and the EvilBundle accessors are NEVER invoked.
        art, bundle = _setup(tmp_path)
        real_bundle = art.bundle
        genuine_records = dict(art.source_registry.records)
        fired = {"acc": 0}

        class _EvilBundle:
            @property
            def bundle_hash(self):
                fired["acc"] += 1
                return real_bundle.bundle_hash
            @property
            def decision_id(self):
                fired["acc"] += 1
                return real_bundle.decision_id
            def __getattr__(self, name):
                fired["acc"] += 1
                return getattr(real_bundle, name)

        class _SwapMap(dict):
            def items(self):
                # phase-substitution: swap the live bundle AFTER verify_d7_artifact
                # has copied it — the OLD code re-read live artifact.bundle post-
                # verify (accessor fires, seal succeeds WITH evil object read).
                object.__setattr__(art, "bundle", _EvilBundle())
                return super().items()
        object.__setattr__(art.source_registry, "records",
                           _SwapMap(genuine_records))
        archive = seal_decision_archive(bundle, art, **_dirs(tmp_path),
                                        archive_dir=tmp_path / "arch")
        assert archive["bundle_hash"] == real_bundle.bundle_hash
        assert fired["acc"] == 0                        # evil accessors never ran
        # the sealed archive is genuine — restore the clean artifact and load it
        object.__setattr__(art.source_registry, "records", genuine_records)
        object.__setattr__(art, "bundle", real_bundle)
        loaded = load_and_verify_decision_archive(
            "d1", art, **_dirs(tmp_path), archive_dir=tmp_path / "arch")
        assert loaded["archive_sha256"] == archive["archive_sha256"]
        assert fired["acc"] == 0

    def test_registry_callback_contract_field_swap_invisible(self, tmp_path):
        # GPT #23 P1#1 (contract face): the registry callback swaps the verified
        # contract's output_mode to an object with __repr__/__eq__ hooks. The
        # boundary snapshots the contract BEFORE any callback point; the live
        # contract is never read again — seal succeeds on the frozen snapshot and
        # the hooks never fire.
        art, bundle = _setup(tmp_path)
        contract = _contract()
        fired = {"n": 0}

        class _EvilMode:
            def __repr__(self):
                fired["n"] += 1
                return "primary_horizon"
            def __eq__(self, o):
                fired["n"] += 1
                return True
            def __hash__(self):
                return hash("primary_horizon")

        class _SwapMap(dict):
            def items(self):
                object.__setattr__(contract, "output_mode", _EvilMode())
                return super().items()
        object.__setattr__(art.source_registry, "records",
                           _SwapMap(dict(art.source_registry.records)))
        archive = seal_decision_archive(
            bundle, art, ledger_dir=tmp_path / "ledger", prov_dir=tmp_path / "prov",
            contract=contract, archive_dir=tmp_path / "arch")
        assert fired["n"] == 0                          # hooks never ran
        assert archive["contract"]["output_mode"] == "primary_horizon"

    def test_registry_callback_outcome_field_swap_invisible(self, tmp_path):
        # GPT #23 P1#1 (outcome face): the registry callback swaps the verified
        # outcome's penalty_leg_status to an object with a __eq__ hook (which the
        # old dispatch comparisons would run twice). The boundary snapshots the
        # outcome at entry, before any callback point — seal succeeds and the
        # hook never fires.
        art, bundle = _setup(tmp_path)
        live_outcome = bundle["outcome"]
        fired = {"n": 0}

        class _EvilStatus:
            def __eq__(self, o):
                fired["n"] += 1
                return o == "success"
            def __hash__(self):
                return hash("success")

        class _SwapMap(dict):
            def items(self):
                object.__setattr__(live_outcome, "penalty_leg_status",
                                   _EvilStatus())
                return super().items()
        object.__setattr__(art.source_registry, "records",
                           _SwapMap(dict(art.source_registry.records)))
        archive = seal_decision_archive(bundle, art, **_dirs(tmp_path),
                                        archive_dir=tmp_path / "arch")
        assert fired["n"] == 0                          # __eq__ never ran
        assert archive["outcome"]["penalty_leg_status"] == "success"

    def test_recover_rejects_subclass_rows_before_iteration(self, tmp_path):
        # GPT #23 P1#2: recovery used to hand the UNVERIFIED artifact to
        # build_leg_payload_ast, which iterates artifact.rows — a list-subclass
        # rows ran its __iter__ before any unified validation. Recovery now
        # verifies + snapshots the artifact at entry: the exact-type gate
        # (rows must be exactly tuple) statically refuses BEFORE any iteration.
        from workspace.research.ai_research_dept.engine.news_archive import (
            recover_and_seal_success_archive,
        )
        art, bundle = _setup(tmp_path)
        fired = {"it": 0}

        class _EvilRows(list):
            def __iter__(self):
                fired["it"] += 1
                return super().__iter__()
        object.__setattr__(art, "rows", _EvilRows(art.rows))
        with pytest.raises(RegistryError, match="须恰 tuple"):
            recover_and_seal_success_archive(
                "d1", art, **_dirs(tmp_path), archive_dir=tmp_path / "arch")
        assert fired["it"] == 0                         # __iter__ never ran

    def test_bundle_colliding_key_eq_never_runs(self, tmp_path):
        # GPT #24 P1#2 (class 5): an EXACT dict may still carry a non-str key whose
        # __hash__ collides with hash("outcome") — the builtin lookup
        # `bundle["outcome"]` would then call that key's __eq__ (caller code) before
        # any key-type check. The boundary now sweeps every key for exact-str BEFORE
        # the first bundle[...] / bundle.get(...).
        art, bundle = _setup(tmp_path)
        fired = {"eq": 0, "hash": 0}

        class _EvilKey:
            def __hash__(self):
                fired["hash"] += 1
                return hash("outcome")
            def __eq__(self, o):
                # False → a DISTINCT key sharing "outcome"'s bucket, so the builtin
                # lookup must probe past it and call this __eq__ (caller code).
                fired["eq"] += 1
                return False
        poisoned = dict(bundle)
        poisoned[_EvilKey()] = "x"                      # collides with "outcome"
        assert "outcome" in poisoned and len(poisoned) == len(bundle) + 1
        fired["eq"] = fired["hash"] = 0                 # ignore insertion-time probes
        with pytest.raises(RegistryError, match="键须恰 str"):
            seal_decision_archive(poisoned, art, **_dirs(tmp_path),
                                  archive_dir=tmp_path / "arch")
        assert fired["eq"] == 0                         # key __eq__ never ran
        assert not list((tmp_path / "arch").glob("*.json"))

    def test_type_gate_rejections_run_no_caller_code(self, tmp_path):
        # GPT #24 P1#1 (class 3): a rejection path must not run caller code. Every
        # exact-type / membership gate on a caller-supplied value now diagnoses via
        # safe_repr/safe_kind (builtin `type()` + `is` identity + literals only) —
        # never `{x!r}` (calls __repr__) or `type(x).__name__` (calls the metaclass
        # __getattribute__). Covers the four entries the reviewer reproduced.
        from workspace.research.ai_research_dept.engine.news_decision import (
            record_decision, require_recorded,
        )
        from workspace.research.ai_research_dept.engine.news_legs import (
            run_news_two_legs, verify_outcome_for_binding,
        )
        fired = {"n": 0}

        class _LoudMeta(type):
            def __getattribute__(cls, name):
                if name == "__name__":
                    fired["n"] += 1
                return super().__getattribute__(name)

        class _EvilStr(str, metaclass=_LoudMeta):
            def __repr__(self):
                fired["n"] += 1
                return "'d1'"
            def __eq__(self, o):
                fired["n"] += 1
                return True
            def __hash__(self):
                return hash("d1")
        art, _ = _setup(tmp_path)
        evil = _EvilStr("d1")
        for call in (
            lambda: record_decision(tmp_path / "ledger", evil, art),
            lambda: require_recorded(tmp_path / "ledger", evil, art),
            lambda: run_news_two_legs(
                art, ledger_dir=tmp_path / "ledger", decision_id=evil,
                output_mode=_EvilStr("primary_horizon"), factor_payload_ast=None,
                penalty_payload_ast=None, factor_leg_fn=None, penalty_leg_fn=None),
            lambda: verify_outcome_for_binding(
                None, art, None, None, ledger_dir=tmp_path / "ledger",
                expected_output_mode=_EvilStr("primary_horizon")),
        ):
            with pytest.raises(RegistryError):
                call()
        assert fired["n"] == 0                          # no caller code on any path

    def test_boundary_rejection_reads_no_untrusted_type_name(self, tmp_path):
        # archive-re-review#21 P1: a boundary rejection must not read the
        # untrusted object's type().__name__ (which runs the metaclass
        # __getattribute__). A wrong-type outcome is refused with a STATIC
        # message; the metaclass __name__ accessor is never invoked.
        art, bundle = _setup(tmp_path)
        fired = {"name": False}

        class _LiarMeta(type):
            def __getattribute__(cls, name):
                if name == "__name__":
                    fired["name"] = True
                return super().__getattribute__(name)

        class _Liar(metaclass=_LiarMeta):
            pass
        bundle["outcome"] = _Liar()
        with pytest.raises(RegistryError, match="NewsLegOutcome"):
            verify_execution_bundle(bundle, art, **_dirs(tmp_path))
        assert fired["name"] is False

    def test_artifact_subobject_accessor_not_run_before_typecheck(self, tmp_path):
        # archive-re-review#21 P1 (#2): artifact sub-components are exact-type-
        # checked and registries snapshotted BEFORE artifact_canonical_payload
        # reads bf.fact_hash / r.row_hash / registry_hash. An injected base_fact
        # whose fact_hash accessor has a side effect is refused at the exact-type
        # check, before its accessor can run.
        from workspace.research.ai_research_dept.engine.news_cards import (
            verify_d7_artifact,
        )
        art = _artifact_full("d1")
        fired = {"acc": False}

        class _EvilFact:
            @property
            def fact_hash(self):
                fired["acc"] = True
                return "0" * 64
        object.__setattr__(art, "base_facts",
                           (_EvilFact(),) + tuple(art.base_facts))
        with pytest.raises(RegistryError, match="D7BaseFact"):
            verify_d7_artifact(art)
        assert fired["acc"] is False                    # accessor never ran

    def test_liar_metaclass_container_refused_by_identity_check(self, tmp_path):
        # archive-re-review#21 P1: a container whose metaclass makes
        # `type(x) == str` return True (fooling an `in (bool,int,float,str)`
        # equality check) is still refused by the all-`is` identity gate; its
        # metaclass __eq__ and its container .get()/.items() are never invoked.
        art, bundle = _setup(tmp_path)
        fired = {"meta_eq": False, "get": False}

        class _LiarMeta(type):
            def __eq__(cls, other):
                fired["meta_eq"] = True
                return True
            def __hash__(cls): return 0

        class _Liar(dict, metaclass=_LiarMeta):
            def get(self, *a, **k):
                fired["get"] = True
                return super().get(*a, **k)
        bundle["selected_provenance"] = _Liar(dict(bundle["selected_provenance"]))
        with pytest.raises(RegistryError, match="非纯 JSON"):
            seal_decision_archive(bundle, art, **_dirs(tmp_path),
                                  archive_dir=tmp_path / "arch")
        assert fired["meta_eq"] is False and fired["get"] is False

    def test_injected_chain_list_subclass_refused(self, tmp_path):
        # archive-re-review#21 P1: the optional `chain` param is also a caller
        # structure; a list subclass whose __iter__ would mutate verified
        # records is refused at the entry snapshot, __iter__ never called.
        from workspace.research.ai_research_dept.engine.news_decision import (
            _ledger_path, _read_chain,
        )
        art, bundle = _setup(tmp_path)
        genuine_chain = _read_chain(_ledger_path(tmp_path / "ledger"))
        fired = {"iter": False}

        class _EvilChain(list):
            def __iter__(self):
                fired["iter"] = True
                return super().__iter__()
        with pytest.raises(RegistryError, match="非纯 JSON"):
            verify_execution_bundle(bundle, art, **_dirs(tmp_path),
                                    chain=_EvilChain(genuine_chain))
        assert fired["iter"] is False

    def test_records_stateful_items_refused_at_snapshot(self, tmp_path):
        # archive-re-review#20 P1 (the reviewer's exact attack): a records[leg]
        # dict subclass with a STATEFUL items() that would mutate the trusted
        # disk row on _require_record_bound's SECOND serialization (compare then
        # seal_hash). The deep-plain-json entry gate refuses the subclass before
        # items() is ever called. Covers factor and penalty.
        fired = {"n": 0}

        class _StatefulRec(dict):
            def items(self):
                fired["n"] += 1
                return super().items()
        for leg in ("factor", "penalty"):
            art, bundle = _setup(tmp_path / leg)
            genuine = dict(bundle["records"][leg]) if bundle["records"][leg] else {}
            bundle["records"][leg] = _StatefulRec(genuine)
            with pytest.raises(RegistryError, match="非纯 JSON"):
                seal_decision_archive(
                    bundle, art, ledger_dir=tmp_path / leg / "ledger",
                    prov_dir=tmp_path / leg / "prov", contract=_contract(),
                    archive_dir=tmp_path / leg / "arch")
        assert fired["n"] == 0                          # items() never called

    def test_selected_row_nonjson_value_refused(self, tmp_path):
        # a selected row carrying a non-JSON value (an object with magic
        # methods) is refused at the canonical-JSON gate, before any compare.
        art, bundle = _setup(tmp_path)
        row = dict(bundle["selected_provenance"]["factor"])
        row["parsed_record"] = object()                 # non-JSON
        bundle["selected_provenance"]["factor"] = row
        with pytest.raises(RegistryError, match="非纯 JSON|不符"):
            verify_execution_bundle(bundle, art, **_dirs(tmp_path))

    def test_nondict_evaluation_refused_before_ne_fires(self, tmp_path):
        # archive-re-review#17/#18 P1 (the reviewer's attack, both variants):
        # a non-dict bundle["evaluation"] whose __ne__ would either swap
        # artifact.final_registry OR mutate trusted_eval in place. The exact-
        # dict gate refuses it and NEVER invokes __ne__, so neither side effect
        # can fire and nothing is sealed.
        art, bundle = _setup(tmp_path)
        fired = {"ne": False}

        class _EvilEval:
            def __ne__(self, other):
                fired["ne"] = True
                other["news_final"] = 52.0              # in-place mutate (re#18)
                art.__dict__["final_registry"] = None   # registry swap (re#17)
                return False
            def __eq__(self, other): return True
            def __hash__(self): return 0
        bundle["evaluation"] = _EvilEval()
        # refused at the deep-plain-json entry gate (non-JSON evaluation), before
        # the exact-dict gate or any compare — __ne__ never fires
        with pytest.raises(RegistryError, match="非纯 JSON|须恰 dict"):
            verify_execution_bundle(bundle, art, **_dirs(tmp_path))
        assert fired["ne"] is False                     # __ne__ never called
        assert not list((tmp_path / "arch").glob("*.json"))

    def test_trusted_eval_frozen_independent_of_bundle_eval(self, tmp_path):
        # archive-re-review#18 P1: the archived evaluation is a frozen JSON copy,
        # computed from the frozen registry; a genuine (equal) bundle evaluation
        # that is a distinct object does not alias the archived one.
        art, bundle = _setup(tmp_path)
        genuine_final = bundle["evaluation"]["news_final"]
        archive = seal_decision_archive(bundle, art, **_dirs(tmp_path),
                                        archive_dir=tmp_path / "arch")
        assert archive["evaluation"]["news_final"] == genuine_final
        assert archive["evaluation"] is not bundle["evaluation"]
        loaded = load_and_verify_decision_archive(
            "d1", art, **_dirs(tmp_path), archive_dir=tmp_path / "arch")
        assert loaded["evaluation"]["news_final"] == genuine_final

    def test_phase_shifting_registry_mapping_refused(self, tmp_path):
        # archive-re-review#14 P0: require_sealed_registry validated the LIVE
        # records mapping and returned the same object. A mapping whose items()
        # returns legit content on the verify read but restricted content on a
        # later consume read must be defeated by returning an independent frozen
        # snapshot (verify and consume read the SAME frozen content).
        from workspace.research.ai_research_dept.engine.news_evidence import (
            require_sealed_registry,
        )
        art = _artifact_full("d1")
        reg = art.final_registry
        genuine = dict(reg.records)

        class _PhaseShift(dict):
            reads = 0
            def items(self):
                _PhaseShift.reads += 1
                # after the first (snapshot) read, hand back a mutated set
                if _PhaseShift.reads == 1:
                    return super().items()
                return iter([("HACKED", object())])
        reg.__dict__["records"] = _PhaseShift(genuine)
        fresh = require_sealed_registry(reg)
        # the returned registry is a frozen snapshot — later reads are stable
        from types import MappingProxyType
        assert type(fresh.records) is MappingProxyType
        assert set(fresh.records) == set(genuine)
        # and it is NOT the caller's live object
        assert fresh.records is not reg.records
        assert dict(fresh.records.items()) == dict(fresh.records.items())

    def test_injected_outcome_output_mode_subclass_refused(self, tmp_path):
        # archive-re-review#14 P1: a str-subclass output_mode injected into
        # outcome.__dict__ after construction must be refused at the consume
        # boundary (verify_outcome_for_binding), so the archive never seals a
        # divergent output_mode that then fails to reload.
        art, bundle = _setup(tmp_path)

        class _EvilMode(str):
            def __eq__(self, x): return True
            def __ne__(self, x): return False
            def __hash__(self): return hash(str(self))
        bundle["outcome"].__dict__["output_mode"] = _EvilMode(
            bundle["outcome"].output_mode)
        with pytest.raises(RegistryError, match="output_mode 须恰 str"):
            verify_execution_bundle(bundle, art, **_dirs(tmp_path))

    def test_card_text_splitlines_injection_refused(self, tmp_path):
        # archive-re-review#13 P0: a str subclass whose str() returns the sealed
        # text (so card_hash still verifies) but whose .splitlines() is forged.
        # verify_d7_artifact's consume-time exact-base-type assert catches the
        # non-exact-str field before the forged text can reach the factor LLM.
        from workspace.research.ai_research_dept.engine.news_cards import (
            verify_d7_artifact,
        )

        class _EvilText(str):
            def splitlines(self, *a, **k):
                return ["FORGED factor line"]
        art = _artifact_full("d1")
        art.card.__dict__["factor_payload_text"] = _EvilText(
            art.card.factor_payload_text)
        with pytest.raises(RegistryError, match="factor_payload_text 须恰 str"):
            verify_d7_artifact(art)

    def test_injected_outcome_hash_int_refused_at_verify(self, tmp_path):
        # archive-re-review#13 P1: post-construction inject an int subclass into
        # outcome.__dict__["outcome_hash"]; the hardened verify_sealed (exact
        # str + 64-hex) refuses it at the binding boundary, so it never seals.
        art, bundle = _setup(tmp_path)

        class _EvilInt(int):
            def __eq__(self, x): return True
            def __ne__(self, x): return False
            def __hash__(self): return 0
        bundle["outcome"].__dict__["outcome_hash"] = _EvilInt(0)
        # caught by the consume-time base-type assert (re-review#14) before verify
        with pytest.raises((SealError, RegistryError)):
            verify_execution_bundle(bundle, art, **_dirs(tmp_path))

    def test_injected_contract_hash_int_refused_at_consume(self, tmp_path):
        # archive-re-review#13 P1: post-construction inject an int subclass into
        # contract.__dict__["contract_hash"]; require_exact_contract re-verifies
        # the self-hash via the hardened verify_sealed and refuses it.
        from workspace.research.ai_research_dept.engine.news_executors import (
            require_exact_contract,
        )

        class _EvilInt(int):
            def __eq__(self, x): return True
            def __ne__(self, x): return False
            def __hash__(self): return 0
        c = _contract()
        c.__dict__["contract_hash"] = _EvilInt(0)
        with pytest.raises(SealError):
            require_exact_contract(c)

    def test_fake_contract_hash_subclass_neutralized(self, tmp_path):
        # archive-re-review#12 P1: the `type(x) is str` guard skipped str
        # subclasses; contract_hash is now coerced unconditionally, so a
        # str-subclass hash is flattened to a plain str (no decoupling) — and
        # a wrong value is rejected by verify_sealed
        c = _contract()

        class _EvilHash(str):
            def __eq__(self, x): return True
            def __ne__(self, x): return False
            def __hash__(self): return hash(str(self))
        # right value, evil subclass -> neutralized to plain str
        c2 = NewsScoringContract(schema_id="c16_news_horizon_v1",
                                 output_mode="primary_horizon",
                                 primary_decision_horizon="1-3d",
                                 contract_hash=_EvilHash(c.contract_hash))
        assert type(c2.contract_hash) is str
        # wrong value -> verify_sealed rejects (cannot occupy with a fake hash)
        with pytest.raises(SealError):
            NewsScoringContract(schema_id="c16_news_horizon_v1",
                                output_mode="primary_horizon",
                                primary_decision_horizon="1-3d",
                                contract_hash=_EvilHash("0" * 64))

    def test_stateful_registry_mapping_snapshotted(self, tmp_path):
        # archive-re-review#11 P0: SealedCardRegistry must snapshot a live
        # mapping at construction, so verify (values()) and consume (items()/
        # get()) can never see a mutated record set. Also: non-CardRecord
        # values are refused.
        from types import MappingProxyType
        from workspace.research.ai_research_dept.engine.news_evidence import (
            SealedCardRegistry,
        )
        art = _artifact_full("d1")
        genuine = dict(art.source_registry.records)
        # a mapping whose .items() flips after the first (snapshot) read
        class _Stateful(dict):
            calls = 0
            def items(self):
                _Stateful.calls += 1
                if _Stateful.calls == 1:
                    return super().items()
                return iter([("HACKED", object())])   # would break a 2nd read
        reg = SealedCardRegistry(cutoff_iso=art.source_registry.cutoff_iso,
                                 records=_Stateful(genuine),
                                 registry_hash=art.source_registry.registry_hash)
        # stored records are a frozen snapshot (MappingProxyType), not the live map
        assert type(reg.records) is MappingProxyType
        assert set(reg.records) == set(genuine)          # snapshot of first read
        # a non-CardRecord value is refused at construction
        with pytest.raises(RegistryError, match="恰 CardRecord"):
            SealedCardRegistry(cutoff_iso=art.source_registry.cutoff_iso,
                               records={"X": object()}, registry_hash="0" * 64)

    def test_evil_source_registry_subclass_refused(self, tmp_path):
        # same class, source-registry side: a SealedCardRegistry subclass with
        # an overridden _payload() forging registry_hash — refused at the
        # D7 consume boundary (require_sealed_registry exact-type)
        from workspace.research.ai_research_dept.engine.news_cards import (
            D7DecisionArtifact, verify_d7_artifact,
        )
        from workspace.research.ai_research_dept.engine.news_evidence import (
            SealedCardRegistry,
        )
        art = _artifact_full("d1")

        class _EvilRegistry(SealedCardRegistry):
            def _payload(self):
                return {"cutoff": self.cutoff_iso, "record_hashes": ["z" * 64]}
        # self-consistent forged identity: registry_hash seals the evil payload
        forged = seal_hash({"cutoff": art.source_registry.cutoff_iso,
                            "record_hashes": ["z" * 64]})
        evil_src = _EvilRegistry(cutoff_iso=art.source_registry.cutoff_iso,
                                 records=art.source_registry.records,
                                 registry_hash=forged)
        assert evil_src.registry_hash != art.source_registry.registry_hash
        evil_art = D7DecisionArtifact(
            card=art.card, base_facts=art.base_facts, source_registry=evil_src,
            rows=art.rows, bundle=art.bundle, final_registry=art.final_registry)
        with pytest.raises(RegistryError, match="恰 SealedCardRegistry"):
            verify_d7_artifact(evil_art)

    def test_evil_card_record_subclass_refused_before_recording(self, tmp_path):
        # archive-re-review#9 P0 (the reviewer's probe): CardRecord is the LEAF
        # of the identity chain — registry_hash is composed of member
        # content_hashes. A CardRecord subclass with REAL fields but an
        # overridden _payload() forging content_hash must be refused at the
        # registry boundary, so no genuine-typed archive chain can form around
        # a forged record hash — and nothing records.
        from workspace.research.ai_research_dept.engine.news_evidence import (
            CardRecord, SealedCardRegistry, build_card_registry,
        )
        art = _artifact_full("d1")
        genuine = next(iter(art.source_registry.records.values()))

        class _EvilCardRecord(CardRecord):
            def _payload(self):
                # real metadata, but a payload that seals to a DIFFERENT hash
                return {**CardRecord._payload(self), "record_schema_id": "evilX"}
        evil_payload = {
            "record_id": genuine.record_id, "domain": genuine.domain,
            "evidence_class": genuine.evidence_class,
            "allowed_uses": sorted(genuine.allowed_uses),
            "allowed_consumers": sorted(genuine.allowed_consumers),
            "allowed_dimensions": sorted(genuine.allowed_dimensions),
            "record_schema_id": "evilX",
            "derivation": [list(kv) for kv in genuine.derivation]}
        evil = _EvilCardRecord(
            record_id=genuine.record_id, domain=genuine.domain,
            evidence_class=genuine.evidence_class,
            allowed_uses=genuine.allowed_uses,
            allowed_consumers=genuine.allowed_consumers,
            allowed_dimensions=genuine.allowed_dimensions,
            record_schema_id=genuine.record_schema_id,
            derivation=genuine.derivation,
            content_hash=seal_hash(evil_payload))       # self-consistent forgery
        assert evil.content_hash != genuine.content_hash
        others = [r for r in art.source_registry.records.values()
                  if r.record_id != genuine.record_id]
        # rebuild the source registry via the public factory with the evil leaf
        with pytest.raises(RegistryError, match="恰 CardRecord"):
            build_card_registry(art.source_registry.cutoff_iso, [evil, *others])
        # even a direct SealedCardRegistry construction re-verifies members
        with pytest.raises(RegistryError, match="恰 CardRecord"):
            SealedCardRegistry(
                cutoff_iso=art.source_registry.cutoff_iso,
                records={genuine.record_id: evil},
                registry_hash=seal_hash({"cutoff": art.source_registry.cutoff_iso,
                                        "record_hashes": [evil.content_hash]}))
        assert not (tmp_path / "ledger").exists()       # nothing recorded

    def test_recovery_stale_snapshot_grows_then_seals_converges(self, tmp_path):
        # archive-re-review#7 P2 (the reviewer's ordering): recovery A takes a
        # stale chain snapshot at entry; competitor B grows the ledger AND
        # seals the archive; A reaches its exists-branch and must re-verify
        # against a FRESH snapshot (not A's stale one), returning B's archive
        # instead of falsely rejecting the anchor
        import workspace.research.ai_research_dept.engine.news_archive as na
        from workspace.research.ai_research_dept.engine.news_archive import (
            recover_and_seal_success_archive,
        )
        art, bundle = _setup(tmp_path)              # committed, unsealed
        state = {}
        real = na._find_success_commitment

        def racing_find(chain, decision_id):
            out = real(chain, decision_id)          # A's snapshot resolved here
            if not state.get("raced"):
                state["raced"] = True               # B: grow ledger THEN seal
                record_decision(tmp_path / "ledger", "d9", _artifact_full("d9"))
                state["sealed"] = seal_decision_archive(
                    bundle, art, **_dirs(tmp_path), archive_dir=tmp_path / "arch")
            return out
        try:
            na._find_success_commitment = racing_find
            got = recover_and_seal_success_archive(
                "d1", art, **_dirs(tmp_path), archive_dir=tmp_path / "arch")
        finally:
            na._find_success_commitment = real
        assert got["archive_sha256"] == state["sealed"]["archive_sha256"]

    def test_recovery_race_loser_returns_existing_archive(self, tmp_path):
        # archive-re-review#6 P2 (the reviewer's interleaving, deterministic):
        # recovery A passes the entry exists-check; concurrent seal B lands the
        # archive; the ledger then grows legitimately; A's rebuilt seal hits
        # the write-once conflict — A must RETURN the existing archive, not err
        import workspace.research.ai_research_dept.engine.news_archive as na
        from workspace.research.ai_research_dept.engine.news_archive import (
            recover_and_seal_success_archive,
        )
        art, bundle = _setup(tmp_path)              # committed, unsealed
        state = {}
        real_read = na.read_execution_provenance

        def racing_read(prov_dir):
            if not state.get("raced"):
                state["raced"] = True               # B wins the race here:
                state["sealed"] = seal_decision_archive(
                    bundle, art, **_dirs(tmp_path), archive_dir=tmp_path / "arch")
                record_decision(tmp_path / "ledger", "d9", _artifact_full("d9"))
            return real_read(prov_dir)
        try:
            na.read_execution_provenance = racing_read
            out = recover_and_seal_success_archive(
                "d1", art, **_dirs(tmp_path), archive_dir=tmp_path / "arch")
        finally:
            na.read_execution_provenance = real_read
        assert out == state["sealed"]               # loser returns B's archive

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
