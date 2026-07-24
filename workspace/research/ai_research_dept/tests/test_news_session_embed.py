# NF integration C1: sealed-decision consumption + session embedding — the seven
# acceptance criteria of NF_UNIT2_SESSION_EMBEDDING_DESIGN.md §4.
import ast
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import test_news_archive as ta  # noqa: E402 — contract/call_fn fixtures

from workspace.research.ai_research_dept.engine.news_executors import (  # noqa: E402
    NewsScoringContract,
)
from workspace.research.ai_research_dept.engine.news_flash_decide import (  # noqa: E402
    decide_stock,
)
from workspace.research.ai_research_dept.engine.news_session_embed import (  # noqa: E402
    consume_news_decision,
)
from workspace.research.ai_research_dept.tests.assembly_fixtures import (  # noqa: E402
    CUT, SMIC, chain_store,
)

EMBED_SRC = (ROOT / "workspace" / "research" / "ai_research_dept" / "engine"
             / "news_session_embed.py")


def _dirs(tmp_path, root):
    return dict(ledger_dir=tmp_path / "ledger", prov_dir=tmp_path / "prov",
                archive_dir=tmp_path / "arch", store_dir=root, artifact_dir=root)


def _produce(tmp_path, *, call_fn=None, contract=None):
    root = chain_store("full")
    out = decide_stock(CUT, ingest_class="forward", ts_code=SMIC,
                       **_dirs(tmp_path, root), contract=contract or ta._contract(),
                       call_fn=call_fn or ta._call_fn())
    return root, out


def _consume(tmp_path, root, *, code=SMIC, contract=None):
    return consume_news_decision(code, CUT, ingest_class="forward",
                                 **_dirs(tmp_path, root),
                                 nf_contract=contract or ta._contract())


# ---------------------------------------------- acceptance 1: single door (AST)

def test_execution_archive_door_never_appears_in_the_embedding_module():
    tree = ast.parse(EMBED_SRC.read_text(encoding="utf-8"))
    names = {n.name for node in ast.walk(tree)
             for n in getattr(node, "names", [])}
    idents = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    attrs = {node.attr for node in ast.walk(tree)
             if isinstance(node, ast.Attribute)}
    banned = "load_and_verify_execution_archive"
    assert banned not in names | idents | attrs, (
        "the session-embedding path must consume ONLY the decision-level "
        "canonical door (binding requirement #7)")


# ---------------------------------------------- happy path + identity block

def test_consume_success_recomputes_final_and_returns_identity(tmp_path):
    root, produced = _produce(tmp_path)
    got = _consume(tmp_path, root)
    assert got["no_decision"] is False
    seat = got["seat"]
    assert seat["final"] == 49.0                      # the sealed chain scalar
    assert seat.get("error") is None
    nf = got["nf_decision"]
    assert nf["decision_id"] == produced["decision_id"]
    assert nf["archive_sha256"] == produced["archive_sha256"]
    assert nf["assembly_hash"] == produced["assembly_hash"]
    assert nf["binding_eligible"] is True
    for k in ("contract_hash", "artifact_hash", "bundle_hash",
              "final_registry_hash", "outcome_hash", "ledger_head_at_seal"):
        assert isinstance(nf[k], str) and nf[k]
    # identity, not copy: no payloads in the block
    assert "evaluation" not in nf and "records" not in nf and "outcome" not in nf


def test_falsifier_mapping_from_horizon_theses(tmp_path):
    # the spec-§5 declared mapping: strongest_counter -> {condition, observable_in}
    factor = {"factor_scores": [
                  {"name": "event_materiality", "score_0_5": 5,
                   "citations": ["NFD01.fact"]},
                  {"name": "fundamental_link", "score_0_5": 5, "citations": []},
                  {"name": "novelty", "score_0_5": 5, "citations": ["NFD02"]}],
              "horizon_factor_scores": [
                  {"name": "tradeability_at_horizon", "horizon": h,
                   "score_0_5": 0, "citations": []}
                  for h in ("next_open", "1-3d", "5-20d")],
              "horizon_theses": [
                  {"horizon": "1-3d", "direction": "利好",
                   "causal_chain": "订单落地带动短期营收预期",
                   "priced_in_status": "未消化",
                   "alternative_explanation": "板块轮动带来的资金效应",
                   "base_adverse_scenario": "大盘回撤时高贝塔回吐",
                   "falsifiable_condition": "三日内无跟进公告",
                   "strongest_counter": "订单金额未经审计且客户集中度极高"}]}

    def fn(msgs):
        if "因子分析" in msgs[0]["content"]:
            return ta._Reply(json.dumps(factor, ensure_ascii=False))
        return ta._Reply(json.dumps(ta._valid_penalty_record(), ensure_ascii=False))
    root, _ = _produce(tmp_path, call_fn=fn)
    got = _consume(tmp_path, root)
    wcw = got["seat"]["record"]["what_could_weaken"]
    assert wcw == [{"condition": "订单金额未经审计且客户集中度极高",
                    "observable_in": "news"}]
    assert got["seat"]["falsifier_norm"]["n_kept"] == 1


# ---------------------------------------------- acceptance 4: fail-closed seat

def test_missing_archive_is_an_error_seat(tmp_path):
    root = chain_store("full")                        # committed chain, NO decision
    got = _consume(tmp_path, root)
    assert got["no_decision"] is False
    assert got["seat"]["final"] is None
    assert got["seat"]["error"].startswith("nf_consume:load:")
    assert got["nf_decision"] is None


def test_hard_failed_decision_is_an_error_seat(tmp_path):
    def broken_fn(msgs):
        return ta._Reply("not json at all")
    root, out = _produce(tmp_path, call_fn=broken_fn)
    assert out["news_status"] == "hard_failed"
    got = _consume(tmp_path, root)
    assert got["seat"]["final"] is None and got["seat"]["error"] is not None


def test_tampered_archive_is_an_error_seat(tmp_path):
    root, produced = _produce(tmp_path)
    arch_dir = tmp_path / "arch"
    victim = next(arch_dir.glob("news_decision_*.json"))
    a = json.loads(victim.read_text(encoding="utf-8"))
    a["evaluation"]["news_final"] = 99.0              # forged sealed value
    victim.write_text(json.dumps(a, ensure_ascii=False), encoding="utf-8")
    got = _consume(tmp_path, root)
    assert got["seat"]["final"] is None
    assert got["seat"]["error"].startswith("nf_consume:load:")


def test_error_seat_makes_the_session_archive_unpublishable():
    # acceptance 4's completion half: a news seat carrying an error refuses
    # publication through the SHARED integrity predicate
    from workspace.research.ai_research_dept.engine.integrity import (
        verify_publishable_archive,
    )
    sw = {"fund": {"a": 1.0}, "tech": {"a": 1.0}, "news": {"a": 1.0}}
    seats = {s: {"final": 50.0} for s in ("fund", "tech")}
    seats["news"] = {"final": None, "error": "nf_consume:load:RegistryError:x"}
    a = {"seats": seats,
         "records": {s: {"factor_scores": []} for s in sw},
         "bear": {"refutations": [], "kill_switches": [], "blind_spots": [],
                  "schema_valid": True, "parse_mode": "strict"},
         "judge": {}}
    problems = verify_publishable_archive(a, sw, {"fund": 1.0})
    assert problems                                    # unpublishable


# ---------------------------------------------- acceptance 5: vector_only

def test_vector_only_never_yields_a_scalar(tmp_path):
    vec = NewsScoringContract(schema_id="c16_news_horizon_v1",
                              output_mode="vector_only",
                              primary_decision_horizon=None)
    root, _ = _produce(tmp_path, contract=vec)
    got = _consume(tmp_path, root, contract=vec)
    assert got["seat"]["final"] is None
    assert got["seat"].get("error") is None            # NOT an error
    assert got["seat"]["vector_only"] is True
    # re-review#2 P2#1: opaque_scalar ⇒ adj_final == final is a SCALAR
    # obligation — a no-scalar seat must never carry it (external origin is
    # marked by opaque_external instead)
    assert "opaque_scalar" not in got["seat"]
    assert got["seat"]["opaque_external"] is True
    assert got["nf_decision"]["binding_eligible"] is False
    assert got["nf_decision"]["output_mode"] == "vector_only"


# ---------------------------------------------- no-decision fallback semantics

def test_unrouted_stock_is_no_decision_not_error(tmp_path):
    root = chain_store("full")
    got = _consume(tmp_path, root, code="300750.SZ")   # never routed
    assert got["no_decision"] is True
    assert got["seat"] is None and got["nf_decision"] is None


# ------------------------------- wiring-obligation DEMO (not a C1 acceptance —
# ------------------------------- re-review#2 P2#2: C1 writes no session archive;
# ------------------------------- the bump unit inherits this pinned property)

def test_tampered_identity_block_changes_the_session_seal(tmp_path):
    from workspace.research.ai_research_dept.engine.integrity import archive_seal
    root, _ = _produce(tmp_path)
    got = _consume(tmp_path, root)
    base = {"ts_code": SMIC, "date": "2025-01-27", "seats": {},
            "nf_decision": dict(got["nf_decision"])}
    s1 = archive_seal(base)
    forged = json.loads(json.dumps(base, ensure_ascii=False))
    forged["nf_decision"]["archive_sha256"] = "f" * 64
    assert archive_seal(forged) != s1                  # commitment proven


# ---------------------------------------------- acceptance 6: legacy unchanged

#: analyst_chain.py 的冻结 v3.1 字节哈希(C1 round-1 P1#1 + re-review#2 P2#3:
#: 字符串缺席证明不了字节未变——追加一行无关注释即可绕过;唯一机械保证是
#: 字节钉)。本钉随正式 chain-version bump 一起移动,除此之外不得更新。
_FROZEN_V31_ANALYST_CHAIN_SHA256 = \
    "0a9c58904a1fc1f0ac1f4e9b00d5f69cd3c807e39555ab317bffda501ff2350a"


def test_analyst_chain_bytes_are_pinned_until_the_version_bump():
    # C1 round-1 P1#1: the manifest hashes analyst_chain.py's BYTES into
    # engine_contract_sha256 — even a default-OFF hook parameter changes the
    # frozen chain_v3.1 contract. Byte-hash pin (re-review#2 P2#3): ANY edit —
    # including an innocuous comment — fails this until the formal bump moves
    # the pin together with the new CHAIN_VERSION.
    import hashlib
    blob = (ROOT / "workspace" / "research" / "ai_research_dept" / "engine"
            / "analyst_chain.py").read_bytes()
    assert hashlib.sha256(blob).hexdigest() == _FROZEN_V31_ANALYST_CHAIN_SHA256, (
        "analyst_chain.py bytes changed without a chain-version bump — the "
        "frozen v3.1 contract hash covers this file (C1 P1#1)")


def test_consumed_seat_declares_the_opaque_scalar(tmp_path):
    # C1 round-1 P1#2: the sealed external score is OPAQUE to the legacy judge
    # (its record's legacy scoring lists are empty BY CONTRACT); the flag is the
    # anchor for wiring obligation (b): adj_final == final absent an NF-native
    # discount contract — a recompute from the empty lists must never zero it.
    root, _ = _produce(tmp_path)
    got = _consume(tmp_path, root)
    assert got["seat"]["opaque_scalar"] is True
    assert got["seat"]["record"]["factor_scores"] == []
    assert got["seat"]["record"]["penalty_scores"] == []
