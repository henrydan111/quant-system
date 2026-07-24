# P4a shared test infrastructure: REAL-CHAIN artifact factory + evidence registry.
#
# Round-1 P1 (user-arbitrated fold: evidence-at-the-door): `record_decision` now
# PROVES the assembly by re-running P3b from the P2/P3a artifacts + source rows.
# A hand-built artifact can never pass that door — so every engine test that
# records/seals must build its artifact through the real chain
# (text_store -> P1 typing -> P2 assess -> P3a split -> P3b assemble).
#
# This module builds those chains once per variant (cached; artifacts are
# immutable), assembles per decision_id on demand, and keeps an evidence
# registry keyed by artifact_hash so call sites stay one-argument:
#     art = chain_artifact("d1", variant="full")
#     rec(ledger_dir, "d1", art)                  # record with full evidence
#     seal_decision_archive(..., assembly=asm_for(art))
#
# Variant vocabulary (the real chain's shapes; P3a splits are ALWAYS
# {fact, source_status}, so "no penalty-eligible children" can only mean
# "no >=floor fact at all" = floor3):
#   basic        NFD01(imp5, split) + NFD02(imp3)            [decision default]
#   full         basic + NFR01(rumor)                        [archive/executors]
#   context_only 2x comment -> NFU rows, no facts
#   floor3       2x imp3 facts -> NFD01+NFD02, NO split, empty penalty population
import json
import sys
import tempfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from data_infra.text_store import ingest_rows, load_text  # noqa: E402
from workspace.research.ai_research_dept.engine.news_flash_assemble import (  # noqa: E402
    assemble_stock_artifact,
)
from workspace.research.ai_research_dept.engine.news_flash_assess import (  # noqa: E402
    assess_day_flashes,
)
from workspace.research.ai_research_dept.engine.news_flash_split import (  # noqa: E402
    split_day_flashes,
)
from workspace.research.ai_research_dept.engine.news_flash_typing import (  # noqa: E402
    type_day_flashes,
)

CUT = "2025-01-27 18:00:00"
SMIC = "688981.SH"                                    # 中芯国际 — the routed subject
_CAL = pd.DatetimeIndex(pd.bdate_range("2025-01-02", "2025-03-31"))
_NC_COLS = ["ts_code", "name", "start_date", "end_date", "ann_date", "change_reason"]

#: variant -> tuple of (content, dt, typing-overrides); content MUST carry the
#: 4-char resolvable name 中芯国际 so P2 routes it to SMIC
_FACT = {"event_type": "订单合同", "verification_status": "官方证实",
         "content_kind": "事实", "direction": "利好", "is_rumor": False}
VARIANTS = {
    "basic": (
        ("中芯国际签订重大订单甲", "2025-01-27 10:00:00", {**_FACT, "importance": 5}),
        ("中芯国际小事件乙", "2025-01-27 09:00:00", {**_FACT, "importance": 3}),
    ),
    "full": (
        ("中芯国际签订重大订单甲", "2025-01-27 10:00:00", {**_FACT, "importance": 5}),
        ("中芯国际小事件乙", "2025-01-27 09:00:00", {**_FACT, "importance": 3}),
        ("传闻中芯国际将重组", "2025-01-27 08:00:00",
         {"event_type": "传闻未证实", "verification_status": "传闻",
          "content_kind": "事实", "direction": "利好", "importance": 3,
          "is_rumor": True}),
    ),
    "context_only": (
        ("中芯国际盘面点评甲", "2025-01-27 10:00:00",
         {**_FACT, "content_kind": "评论", "importance": 3}),
        ("中芯国际盘面点评乙", "2025-01-27 09:00:00",
         {**_FACT, "content_kind": "评论", "importance": 3}),
    ),
    "floor3": (
        ("中芯国际签订重大订单甲", "2025-01-27 10:00:00", {**_FACT, "importance": 3}),
        ("中芯国际小事件乙", "2025-01-27 09:00:00", {**_FACT, "importance": 3}),
    ),
}


def _stock_basic():
    return pd.DataFrame([{"ts_code": SMIC, "name": "中芯国际",
                          "list_date": "20200716", "delist_date": None}])


def _namechange():
    return pd.DataFrame([{"ts_code": SMIC, "name": "中芯国际",
                          "start_date": "20200716", "end_date": None,
                          "ann_date": "20200716", "change_reason": "上市"}],
                        columns=_NC_COLS)


class _Reply:
    def __init__(self, text):
        self.text = text


def _typer(specs):
    """P1 fake classifier: per-item typing looked up by content."""
    by_content = {c: t for c, _dt, t in specs}

    def fn(msgs):
        payload = json.loads(msgs[1]["content"])
        results = [{"idx": it["idx"], **by_content[it["content"]]}
                   for it in payload["items"]]
        return _Reply(json.dumps({"results": results}, ensure_ascii=False))
    return fn


_CHAINS: dict = {}                 # variant -> (p2, p3a, rows)
_EVIDENCE: dict = {}               # artifact_hash -> (assembly, p2, p3a, rows)


def _chain(variant):
    if variant not in _CHAINS:
        specs = VARIANTS[variant]
        store = Path(tempfile.mkdtemp(prefix=f"nf_chain_{variant}_"))
        ingest_rows("news", pd.DataFrame(
            [{"src": "sina", "datetime": dt, "content": c, "title": None,
              "channels": ""} for c, dt, _t in specs]),
            published_col="datetime",
            retrieved_at=pd.Timestamp("2025-01-27 17:00:00"),
            store_dir=store, ingest_class="forward")
        p1 = type_day_flashes(CUT, ingest_class="forward", call_fn=_typer(specs),
                              store_dir=store)
        p2 = assess_day_flashes(CUT, ingest_class="forward", typed_artifact=p1,
                                stock_basic=_stock_basic(),
                                namechange=_namechange(), open_calendar=_CAL,
                                industry_terms=frozenset({"半导体"}),
                                concept_terms=frozenset({"芯片"}),
                                store_dir=store)
        rows = load_text("news", pd.Timestamp(CUT), store_dir=store,
                         ingest_class="forward")
        p3a = split_day_flashes(CUT, ingest_class="forward",
                                assessed_artifact=p2, source_rows=rows)
        _CHAINS[variant] = (p2, p3a, rows)
    return _CHAINS[variant]


def chain_artifact(decision_id="d1", *, variant="basic", ts_code=SMIC):
    """A genuine D7 artifact for `decision_id` from the cached `variant` chain,
    with its evidence registered for `rec`/`evidence_for`/`asm_for`."""
    p2, p3a, rows = _chain(variant)
    artifact, assembly = assemble_stock_artifact(
        CUT, ingest_class="forward", ts_code=ts_code, decision_id=decision_id,
        assessed_artifact=p2, split_artifact=p3a, source_rows=rows)
    _EVIDENCE[artifact.artifact_hash] = (assembly, p2, p3a, rows)
    return artifact


def asm_for(artifact):
    """The GENUINE assembly for a chain-built artifact (registry lookup)."""
    return _EVIDENCE[artifact.artifact_hash][0]


def evidence_for(artifact) -> dict:
    """record_decision's full evidence kwargs for a chain-built artifact."""
    assembly, p2, p3a, rows = _EVIDENCE[artifact.artifact_hash]
    return dict(assembly=assembly, assessed_artifact=p2, split_artifact=p3a,
                source_rows=rows)


def rec(ledger_dir, decision_id, artifact):
    """record_decision with full re-derivation evidence (the P4a first-write door)."""
    from workspace.research.ai_research_dept.engine.news_decision import (
        record_decision,
    )
    return record_decision(ledger_dir, decision_id, artifact,
                           **evidence_for(artifact))
