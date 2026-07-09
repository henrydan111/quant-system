# SCRIPT_STATUS: ACTIVE — 引擎配置(版本化;改动=新 version 字符串,勿原地改语义)
"""Engine config: paths + pinned versions.

一切可调参数在此集中并随工件落盘(config_hash);检索相关参数受二篇横切 #8(RetrievalConfig
CandidateID)+ #10(FORWARD_RETRIEVAL_PREREG)约束——首轮前向前冻结。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]

# ---- 数据门(全部沿系统 sanctioned doors) ----
QLIB_DIR = PROJECT_ROOT / "data" / "qlib_data"
TRADE_CAL = PROJECT_ROOT / "data" / "reference" / "trade_cal.parquet"
POOL_DIR = PROJECT_ROOT / "data" / "analyst" / "broker_recommend"

# ---- 引擎输出(Class-D) ----
OUT_ROOT = PROJECT_ROOT / "workspace" / "outputs" / "ai_research_dept"
FACT_DIR = OUT_ROOT / "fact_table"
EVENT_DIR = OUT_ROOT / "event_store"
PV_DIR = OUT_ROOT / "pv_pack"

# ---- 试点范围(202501 重放;NON_EVIDENTIARY) ----
PILOT_POOL_MONTH = "202501"
PILOT_MONTH_END = "20250131"
EVIDENCE_CLASS_REPLAY = "NON_EVIDENTIARY_PILOT"   # replay 自动注入(R2 Minor-C)

# ---- FactTable v0 ----
FACT_TABLE_VERSION = "fact_v0.1"
#: 基本面字段(pit_research_loader,sandbox_screening 全批准,2026-07-08 探测确认)
FUND_FIELDS = [
    "roe_waa", "grossprofit_margin", "netprofit_margin", "ocf_to_or",
    "or_yoy", "netprofit_yoy", "dt_netprofit_yoy", "basic_eps_yoy",
    "debt_to_assets", "current_ratio", "assets_turn",
]
#: 市场字段(provider daily_basic bins,approved)
MKT_FIELDS = ["$pe_ttm", "$pb", "$total_mv", "$turnover_rate"]
#: 行业分位:同业样本数下限,不足回退全市场分位(第一篇 §11 诚实缺口的 fallback)
INDUSTRY_MIN_N = 8
#: 自身时序分位回看(年);季度采样
HIST_YEARS = 10

# ---- 事件库 ----
EVENT_STORE_VERSION = "event_v0.5"   # v0.5: +政策三源无主属事件(v1.5-D);v0.4: +研报/修正潮/互动易
TAG_VERSION = "tags_v0.1"


def config_hash() -> str:
    payload = json.dumps({
        "fact": FACT_TABLE_VERSION, "event": EVENT_STORE_VERSION,
        "tags": TAG_VERSION, "fund_fields": FUND_FIELDS, "mkt_fields": MKT_FIELDS,
        "industry_min_n": INDUSTRY_MIN_N, "hist_years": HIST_YEARS,
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]
