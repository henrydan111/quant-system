# NF final-integration: chain_v3.2 bump — the four frozen wiring obligations
# discharged (NF_UNIT_BUMP_DESIGN.md acceptance criteria).
import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import test_news_archive as ta  # noqa: E402 — NF contract/call_fn fixtures

from workspace.research.ai_research_dept.engine import analyst_chain as AC  # noqa: E402
from workspace.research.ai_research_dept.engine.news_flash_decide import (  # noqa: E402
    decide_stock,
)
from workspace.research.ai_research_dept.engine.news_session_embed import (  # noqa: E402
    consume_news_decision, nf_contract_from_chain, nf_cutoff_for_day,
)
from workspace.research.ai_research_dept.tests.assembly_fixtures import (  # noqa: E402
    CUT, SMIC, chain_store,
)

SCORING = {
    "seat_weights": {"fund": {"a": 20.0}, "tech": {"a": 20.0}, "news": {"a": 20.0}},
    "composite_weights": {"fund": 0.4, "tech": 0.3, "news": 0.3},
    "bear_discount_strength": 4,
    "divergence_gap": 40,
}


def _seat(final, *, opaque=False, score=3):
    rec = {"factor_scores": [{"name": "a", "score_0_5": score,
                              "evidence_spans": ["x"]}],
           "penalty_scores": []}
    if opaque:
        rec = {"factor_scores": [], "penalty_scores": []}
    out = {"final": final, "record": rec, "scored_dims": 1, "total_dims": 1}
    if opaque:
        out["opaque_scalar"] = True
        out["opaque_external"] = True
    return out


# ------------------------------------------ obligation (b): opaque judge semantics

def test_opaque_seat_passes_through_without_bear_refutations():
    seats = {"fund": _seat(60.0), "news": _seat(49.0, opaque=True)}
    bear = {"refutations": []}
    v = AC.judge(seats, bear, SCORING)
    assert v["adj_finals"]["news"] == 49.0             # pre-fix: 0.0
    assert v["adj_finals"]["fund"] == 60.0


def test_opaque_seat_passes_through_even_with_bear_refutations():
    # absent an NF-native discount contract, a refutation targeting the news
    # seat has no contract-registered dim to discount — the sealed scalar holds
    seats = {"news": _seat(49.0, opaque=True)}
    bear = {"refutations": [{"target_seat": "news", "target_dim": "a",
                             "strength_0_5": 5}]}
    v = AC.judge(seats, bear, SCORING)
    assert v["adj_finals"]["news"] == 49.0
    assert v["bear_discounts"] == []                   # nothing was discounted


def test_legacy_seats_still_discount():
    # the legacy path is untouched: strength>=4 refutation halves the dim
    seats = {"fund": _seat(60.0)}
    bear = {"refutations": [{"target_seat": "fund", "target_dim": "a",
                             "strength_0_5": 5}]}
    v = AC.judge(seats, bear, SCORING)
    assert v["adj_finals"]["fund"] == 30.0
    assert v["bear_discounts"] == [{"seat": "fund", "dim": "a"}]


def test_opaque_final_is_clamped():
    seats = {"news": _seat(150.0, opaque=True)}
    v = AC.judge(seats, {"refutations": []}, SCORING)
    assert v["adj_finals"]["news"] == 100.0


# ------------------------------------------ obligation (c): contract + cutoff binding

def _chain_contract_ns(nf=None):
    return types.SimpleNamespace(nf=nf if nf is not None else dict(AC.NF_CONTRACT))


def test_nf_contract_frozen_values():
    # the user-frozen v3.2 values (2026-07-24); changing them = another bump
    assert AC.NF_CONTRACT == {
        "schema_id": "c16_news_horizon_v1", "output_mode": "primary_horizon",
        "primary_decision_horizon": "1-3d", "input_cutoff_time": "18:00:00",
        "ingest_class": "forward"}
    assert AC.CHAIN_VERSION == "chain_v3.2"


def test_nf_contract_from_chain_round_trip():
    c = nf_contract_from_chain(_chain_contract_ns())
    assert c.schema_id == "c16_news_horizon_v1"
    assert c.output_mode == "primary_horizon"
    assert c.primary_decision_horizon == "1-3d"


def test_pre_v32_contract_refused():
    with pytest.raises(ValueError, match="nf_contract"):
        nf_contract_from_chain(types.SimpleNamespace(nf={}))
    with pytest.raises(ValueError, match="nf_contract"):
        nf_cutoff_for_day("20250127", types.SimpleNamespace(nf=None))


def test_cutoff_binding_produces_the_full_frozen_timestamp():
    cut = nf_cutoff_for_day("20250127", _chain_contract_ns())
    assert cut.isoformat() == "2025-01-27T18:00:00"    # never a bare date
    with pytest.raises(ValueError, match="YYYYMMDD"):
        nf_cutoff_for_day("2025-01-27", _chain_contract_ns())


def test_manifest_nf_section_validation():
    ok = dict(AC.NF_CONTRACT)
    assert AC._verify_nf_contract(ok) == []
    assert AC._verify_nf_contract(None)                # missing section refused
    assert AC._verify_nf_contract({**ok, "extra": 1})  # strict key set
    assert AC._verify_nf_contract({**ok, "input_cutoff_time": "18:00"})
    assert AC._verify_nf_contract({**ok, "output_mode": "vector_only"})
    vec = {**ok, "output_mode": "vector_only", "primary_decision_horizon": None}
    assert AC._verify_nf_contract(vec) == []


# ------------------------------------------ obligations (a)+(d): the hook wiring

def _stub_seat_runner(calls):
    def fake_run_seat(seat, prompt, payload, card_text, audit, weights, route,
                      registry=None):
        calls.append(seat)
        return _seat(60.0, score=3)
    return fake_run_seat


def _fake_bear(*a, **k):
    # kill_switches must be a NON-EMPTY list of non-empty strings (integrity)
    return {"refutations": [], "kill_switches": ["订单被证伪则观点作废"],
            "blind_spots": [], "validation_dropped": {}, "schema_valid": True,
            "parse_mode": "strict"}


def _fake_contract():
    return types.SimpleNamespace(
        effective_prompts={p: "P" for p in AC.PROMPT_FILES},
        scoring=SCORING, routing={"scoring": {}, "bear": {}},
        llm_config_hash="llmh", manifest_fp="mfp", manifest_sha256="msha",
        nf=dict(AC.NF_CONTRACT))


def _attempt(tmp_path, nf_news, monkeypatch, calls):
    monkeypatch.setattr(AC, "run_seat", _stub_seat_runner(calls))
    monkeypatch.setattr(AC, "run_bear", _fake_bear)
    cards = {"fund_card": "F", "pv_card": "T", "news_card": "N"}
    return AC._execute_attempt(SMIC, "20250127", cards, "", _fake_contract(),
                               tmp_path, "afp", 1, {}, nf_news=nf_news)


def test_hook_on_consumed_seat_and_sealed_identity_block(tmp_path, monkeypatch):
    root = chain_store("full")
    produced = decide_stock(CUT, ingest_class="forward", ts_code=SMIC,
                            ledger_dir=tmp_path / "led", prov_dir=tmp_path / "prov",
                            archive_dir=tmp_path / "arch", store_dir=root,
                            artifact_dir=root, contract=ta._contract(),
                            call_fn=ta._call_fn())

    def nf_news(code, day):
        cut = nf_cutoff_for_day(day, _chain_contract_ns())
        assert cut.isoformat() == "2025-01-27T18:00:00"
        return consume_news_decision(
            code, cut, ingest_class="forward", ledger_dir=tmp_path / "led",
            prov_dir=tmp_path / "prov", archive_dir=tmp_path / "arch",
            store_dir=root, artifact_dir=root, nf_contract=ta._contract())
    calls: list = []
    archive = _attempt(tmp_path, nf_news, monkeypatch, calls)
    assert calls == ["fund", "tech"]                   # news inline LLM NOT run
    assert archive["seats"]["news"]["final"] == 49.0
    # obligation (b) end to end: the sealed scalar survives the judge
    assert archive["seats"]["news"]["adj_final"] == 49.0
    nf = archive["nf_decision"]
    assert nf["decision_id"] == produced["decision_id"]
    assert nf["archive_sha256"] == produced["archive_sha256"]
    # the identity block is sealed under the session archive_sha256
    forged = json.loads(json.dumps(archive, ensure_ascii=False))
    forged["nf_decision"]["archive_sha256"] = "f" * 64
    body = {k: v for k, v in forged.items() if k != "archive_sha256"}
    from workspace.research.ai_research_dept.engine.integrity import archive_seal
    assert archive_seal(body) != archive["archive_sha256"]
    assert archive["complete"] is True


def test_hook_no_decision_falls_back_to_inline_seat(tmp_path, monkeypatch):
    def nf_news(code, day):
        return {"seat": None, "nf_decision": None, "no_decision": True}
    calls: list = []
    archive = _attempt(tmp_path, nf_news, monkeypatch, calls)
    assert calls == ["fund", "tech", "news"]           # legacy inline seat ran
    assert "nf_decision" not in archive
    assert archive["seats"]["news"]["final"] == 60.0


def test_hook_error_seat_is_adopted_and_unpublishable(tmp_path, monkeypatch):
    def nf_news(code, day):
        return {"seat": {"final": None,
                         "record": {"factor_scores": [], "penalty_scores": []},
                         "scored_dims": 0, "total_dims": 0,
                         "error": "nf_consume:load:RegistryError:x"},
                "nf_decision": None, "no_decision": False}
    calls: list = []
    archive = _attempt(tmp_path, nf_news, monkeypatch, calls)
    assert calls == ["fund", "tech"]                   # NO silent fallback
    assert archive["seats"]["news"]["error"] is not None
    assert archive["complete"] is False


def test_hook_default_off_is_pure_legacy(tmp_path, monkeypatch):
    calls: list = []
    archive = _attempt(tmp_path, None, monkeypatch, calls)
    assert calls == ["fund", "tech", "news"]
    assert "nf_decision" not in archive
