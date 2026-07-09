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

# ---- FactTable v0.2(chain_v2.0 输入升级:+PS/股息率;+vintage 8 季序列) ----
FACT_TABLE_VERSION = "fact_v0.2"
#: 基本面字段(pit_research_loader,sandbox_screening 全批准,2026-07-08 探测确认)
FUND_FIELDS = [
    "roe_waa", "grossprofit_margin", "netprofit_margin", "ocf_to_or",
    "or_yoy", "netprofit_yoy", "dt_netprofit_yoy", "basic_eps_yoy",
    "debt_to_assets", "current_ratio", "assets_turn",
]
#: 市场字段(provider daily_basic bins,approved;ps_ttm/dv_ratio 注册表实查 2026-07-09)
MKT_FIELDS = ["$pe_ttm", "$pb", "$ps_ttm", "$dv_ratio", "$total_mv", "$turnover_rate"]
#: vintage 8 季序列字段(审计 F3 探测裁决:指标 q-slot 未注册 → 退化 vintage 口径,
#  各点=该采样时点已知值,含 D 日当前点;卡内显式标注)
SERIES_FIELDS = ["or_yoy", "netprofit_yoy", "grossprofit_margin", "roe_waa"]
SERIES_POINTS = 8
#: 行业分位:同业样本数下限,不足回退全市场分位(第一篇 §11 诚实缺口的 fallback)
INDUSTRY_MIN_N = 8
#: 自身时序分位回看(年);季度采样
HIST_YEARS = 10

# ---- 事件库 ----
EVENT_STORE_VERSION = "event_v0.5"   # v0.5: +政策三源无主属事件(v1.5-D);v0.4: +研报/修正潮/互动易
TAG_VERSION = "tags_v0.3"   # v0.3: 概念泛板块过滤(5-300成员+黑名单);v0.2: +概念标签维


#: 概念板块过滤(v1.5-E 修正):同花顺"泛板块"(融资融券/沪股通/机构重仓等状态板,
#  成员数千)不是主题概念 —— 不过滤会让 concept 通道比 industry 还宽(实测吞掉行业通道)。
CONCEPT_MIN_MEMBERS = 5
CONCEPT_MAX_MEMBERS = 300
CONCEPT_NAME_BLOCKLIST = ("融资融券|转融|沪股通|深股通|标的|预盈预增|预亏预减|ST板块|次新股|"
                          "MSCI|富时|成份|样本|同花顺|漂亮|壳资源|股权转让|高送转|破净|低价")


def load_concept_members() -> "object":
    """过滤后的概念成分(事件打标与检索画像共用同一份,防口径漂移)。"""
    import re
    import pandas as pd
    d = PROJECT_ROOT / "data" / "reference" / "ths_concept"
    if not (d / "ths_members.parquet").exists():
        return None
    idx = pd.read_parquet(d / "ths_index.parquet", columns=["ts_code", "name", "count"])
    ok = idx[(idx["count"].fillna(0) >= CONCEPT_MIN_MEMBERS)
             & (idx["count"].fillna(9e9) <= CONCEPT_MAX_MEMBERS)
             & ~idx["name"].astype(str).str.contains(CONCEPT_NAME_BLOCKLIST, regex=True)]
    mem = pd.read_parquet(d / "ths_members.parquet", columns=["ts_code", "con_code"])
    return mem[mem["ts_code"].isin(set(ok["ts_code"]))]


def config_hash() -> str:
    payload = json.dumps({
        "fact": FACT_TABLE_VERSION, "event": EVENT_STORE_VERSION,
        "tags": TAG_VERSION, "fund_fields": FUND_FIELDS, "mkt_fields": MKT_FIELDS,
        "industry_min_n": INDUSTRY_MIN_N, "hist_years": HIST_YEARS,
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]
