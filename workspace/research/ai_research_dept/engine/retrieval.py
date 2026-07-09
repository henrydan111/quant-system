# SCRIPT_STATUS: ACTIVE — 检索层 v0:画像 → 通道检索 → 确定性相关度 → 快照
"""Retrieval layer v0 (INTEL_CENTER §2A.3;受横切 #8 检索治理 + #10 FORWARD_PREREG 约束)。

v0 通道:direct(个股标签)+ industry(申万 L1)。relation/concept/hotword/keyword 通道
随 relation_store/THS/词库 上线(v1.5)。LLM 边界精筛 v1 关闭(阈值保守,横切 #8 在案)。

确定性相关度(参数属 RetrievalConfig,冻结于 config;改动=新 CandidateID):
    relevance = channel_w × (importance/5) × tier_w × 0.97^age_days
每次装配持久化 retrieval_profile_snapshot_id(R2 Minor-1:某日所见不可漂移)。

用法: venv/Scripts/python.exe workspace/research/ai_research_dept/engine/retrieval.py
"""
from __future__ import annotations

import hashlib
import json
import logging
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from workspace.research.ai_research_dept.engine import config as C  # noqa: E402
from workspace.research.ai_research_dept.engine.fact_table import decision_days  # noqa: E402
from data_infra.provider_metadata import industry_as_of  # noqa: E402

logger = logging.getLogger("retrieval")

#: RetrievalConfig(横切 #8:任何改动 = 新 CandidateID;首轮前向前 FORWARD_PREREG 冻结)
#  v0.2: +concept 通道(THS 快照,特异性 direct>concept>industry)
RETRIEVAL_CONFIG = {
    "retrieval_config_id": "retr_v0.2",
    "lookback_days": 30,
    "decision_time_cn": "09:15",
    "channel_w": {"direct": 1.0, "relation": 0.7, "concept": 0.5,
                  "industry": 0.4, "hotword": 0.3, "keyword": 0.2},
    "tier_w": {"strong": 1.0, "medium": 0.8},
    "decay_per_day": 0.97,
    "min_relevance": 0.05,
    "max_items_nondirect": 25,
    "llm_borderline_judging": False,       # v1 关闭
}
RETR_DIR = C.OUT_ROOT / "retrieval"


def snapshot_id() -> str:
    payload = json.dumps({
        "tag_version": C.TAG_VERSION, "event_store_version": C.EVENT_STORE_VERSION,
        "relation_graph_version": "none_v0", "focus_word_version": "none_v0",
        "retrieval_config": RETRIEVAL_CONFIG,
    }, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


_STOCK_CONCEPTS: dict | None = None


def stock_concepts() -> dict[str, set]:
    global _STOCK_CONCEPTS
    if _STOCK_CONCEPTS is None:
        mem = C.load_concept_members()          # 与事件打标同一份过滤成分
        if mem is not None:
            _STOCK_CONCEPTS = mem.groupby("con_code")["ts_code"].apply(set).to_dict()
        else:
            _STOCK_CONCEPTS = {}
    return _STOCK_CONCEPTS


def assemble_for_stock(code: str, day: str, ev: pd.DataFrame,
                       cutoff: pd.Timestamp, win_start: pd.Timestamp) -> list[dict]:
    cfg = RETRIEVAL_CONFIG
    ind = industry_as_of(code, day, "L1")
    my_concepts = stock_concepts().get(code, set())
    w = ev[(ev["visible_at"] <= cutoff) & (ev["visible_at"] >= win_start)]
    out = []
    for _, r in w.iterrows():
        subjects = list(r["subject_codes"])
        ct_raw = r.get("concept_tags")
        ct = set(list(ct_raw)) if ct_raw is not None and len(ct_raw) else set()  # np数组禁truthiness
        if code in subjects:
            channel = "direct"
        elif my_concepts and (my_concepts & ct):
            channel = "concept"           # 特异性:直接 > 概念 > 行业(2A.3)
        elif ind is not None and ind in list(r["industry_tags"]):
            channel = "industry"
        else:
            continue
        age = max(0.0, (cutoff - r["visible_at"]).total_seconds() / 86400.0)
        rel = (cfg["channel_w"][channel] * (r["importance_0_5"] / 5.0)
               * cfg["tier_w"].get(r["source_tier"], 0.8)
               * cfg["decay_per_day"] ** age)
        if channel == "direct" or rel >= cfg["min_relevance"]:
            out.append({"ts_code": code, "trade_date": day, "event_id": r["event_id"],
                        "event_type": r["event_type"], "title": r["title"],
                        "direction": r["direction"], "importance": r["importance_0_5"],
                        "channel": channel, "relevance": round(float(rel), 4)})
    # direct 全保留;非 direct 取 top-K
    direct = [x for x in out if x["channel"] == "direct"]
    nond = sorted([x for x in out if x["channel"] != "direct"],
                  key=lambda x: -x["relevance"])[: cfg["max_items_nondirect"]]
    ranked = direct + nond
    for i, x in enumerate(sorted(ranked, key=lambda x: -x["relevance"]), 1):
        x["rank"] = i
    return ranked


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    days = decision_days(C.PILOT_POOL_MONTH, C.PILOT_MONTH_END)
    pool_df = pd.read_parquet(C.POOL_DIR / f"broker_recommend_{C.PILOT_POOL_MONTH}.parquet")
    pool = sorted(set(pool_df["ts_code"]))
    ev = pd.read_parquet(C.EVENT_DIR / f"events_{C.PILOT_POOL_MONTH}.parquet")
    snap = snapshot_id()
    logger.info("retrieval v0: %d days × %d names | %d events | snapshot=%s",
                len(days), len(pool), len(ev), snap)

    t0, rows = time.time(), []
    hh, mm = RETRIEVAL_CONFIG["decision_time_cn"].split(":")
    for day in days:
        cutoff = pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]} {hh}:{mm}:00")
        win_start = cutoff - pd.Timedelta(days=RETRIEVAL_CONFIG["lookback_days"])
        for code in pool:
            rows.extend(assemble_for_stock(code, day, ev, cutoff, win_start))
        logger.info("[%s] cumulative items: %d", day, len(rows))

    df = pd.DataFrame(rows)
    df["retrieval_profile_snapshot_id"] = snap
    df["retrieval_config_id"] = RETRIEVAL_CONFIG["retrieval_config_id"]
    df["evidence_class"] = C.EVIDENCE_CLASS_REPLAY
    RETR_DIR.mkdir(parents=True, exist_ok=True)
    out = RETR_DIR / f"retrieval_{C.PILOT_POOL_MONTH}.parquet"
    df.to_parquet(out, index=False)
    (RETR_DIR / "retrieval_config_v0.json").write_text(
        json.dumps({**RETRIEVAL_CONFIG, "snapshot_id": snap}, indent=2,
                   ensure_ascii=False), encoding="utf-8")

    per = df.groupby(["ts_code", "trade_date"]).size()
    summary = {
        "items": len(df),
        "per_name_day": {"mean": round(float(per.mean()), 1),
                          "p90": int(per.quantile(0.9)), "max": int(per.max())},
        "by_channel": df.channel.value_counts().to_dict(),
        "snapshot_id": snap, "elapsed_s": round(time.time() - t0, 1),
        "evidence_class": C.EVIDENCE_CLASS_REPLAY,
    }
    (RETR_DIR / f"summary_{C.PILOT_POOL_MONTH}.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("retrieval -> %s | %s", out, summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
