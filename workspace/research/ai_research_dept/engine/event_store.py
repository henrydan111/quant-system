# SCRIPT_STATUS: ACTIVE — 通用事件库 v0:无主属 + 五维打标骨架 + 确定性生成器
"""Universal event store (INTEL_CENTER §2A):事件入库不归属股票,打标后由检索装配。

Schema(每事件一行):
  event_id            sha16(type|subject|date|content-basis)   判同键
  event_type          事件类型(六分类税onomy 内的细类)
  subject_codes       直接主体股列表(个股标签维 —— 标签≠所有权)
  industry_tags       申万 L1 行业标签(主体股 as-of 行业;PIT)
  concept_tags        v0 空(THS v1.5)
  hotword_tags        v0 空(词库 v1.5)
  keyword_tags        标题/内容确定性关键词
  importance_0_5      重要性(规则基线;文本事件的 LLM 复核在分析师链)
  direction           utf: 显著利好|间接利好|轻微利好|中性|轻微利空|间接利空|严重利空
  source / source_tier C15 分层(strong|medium)
  visible_at          可见时点(结构化=数据日 T 盘后=T+1 08:00 保守;文本=sim/decision_visible_at)
  title, payload      内容(payload=JSON 明细)
  tag_version, event_store_version, evidence_class

v0 生成器(全确定性,零 LLM):
  G1 涨跌停/炸板(limit bins,全市场)      G2 龙虎榜+机构席位方向($top_list__/$top_inst__)
  G3 大宗折溢价($block_trade__)           G4 停复牌(suspend_d)
  G5 公告标题分型(anns_d,行政词表杀 + 类型词表;irm_qa 的实质判定属 LLM,v0 不做)

ledger 类生成器(forecast/dividends/stk_holdertrade)等 pit_event_feed 门(任务4)。
用法: venv/Scripts/python.exe workspace/research/ai_research_dept/engine/event_store.py
"""
from __future__ import annotations

import hashlib
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from workspace.research.ai_research_dept.engine import config as C  # noqa: E402
from data_infra.provider_metadata import industry_as_of  # noqa: E402
from data_infra.text_store import load_text  # noqa: E402

logger = logging.getLogger("event_store")

HIST_TEXT_STORE = C.PROJECT_ROOT / "data" / "text_store_hist_pilot"
SUSPEND_DIR = C.PROJECT_ROOT / "data" / "market" / "suspend_d"

# ---- 公告标题分型词表(确定性;命中前表=行政噪音,importance<=1,不进 LLM) ----
ADMIN_KILL = ["章程", "律师", "法律意见", "会议决议", "会议材料", "股东大会", "股东会",
              "监事会", "董事会决议", "工作细则", "管理制度", "审计委员会", "取消",
              "会计师事务所", "更换", "议事规则", "承诺", "备查", "延期回复", "问询函回复"]
TITLE_TYPES = [  # (类型, 关键词, importance 基线, direction 基线)
    ("业绩预告", ["业绩预告", "业绩预增", "业绩预减", "预亏", "扭亏"], 4, "中性"),
    ("业绩快报", ["业绩快报"], 3, "中性"),
    ("减持", ["减持"], 3, "轻微利空"),
    ("增持", ["增持"], 3, "轻微利好"),
    ("回购", ["回购"], 3, "轻微利好"),
    ("中标/合同", ["中标", "重大合同", "框架协议", "签署"], 3, "轻微利好"),
    ("诉讼/仲裁", ["诉讼", "仲裁"], 3, "轻微利空"),
    ("质押", ["质押"], 2, "轻微利空"),
    ("重组/并购", ["重组", "收购", "合并", "分拆", "购买资产"], 4, "中性"),
    ("再融资", ["定增", "非公开发行", "配股", "可转债", "募集"], 3, "中性"),
    ("监管", ["立案", "处罚", "警示函", "监管函", "问询函"], 4, "间接利空"),
    ("停复牌", ["停牌", "复牌"], 4, "中性"),
    ("分红", ["利润分配", "分红", "权益分派"], 2, "轻微利好"),
    ("高管变动", ["辞职", "聘任", "选举", "变更.*总监", "变更.*总经理"], 2, "中性"),
]


def sha16(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


_CONCEPT_MAP: dict | None = None


def concept_map() -> dict[str, list[str]]:
    """con_code(股票) → [概念板块代码];快照口径(PIT 弱于行业,ths_ingest 声明在案)。"""
    global _CONCEPT_MAP
    if _CONCEPT_MAP is None:
        mem = C.load_concept_members()          # 泛板块过滤后的成分(与检索画像同源)
        if mem is not None:
            _CONCEPT_MAP = mem.groupby("con_code")["ts_code"].apply(list).to_dict()
        else:
            logger.warning("ths_members 缺失 — 概念标签维为空(先跑 ths_ingest.py)")
            _CONCEPT_MAP = {}
    return _CONCEPT_MAP


def _event(event_type: str, subjects: list[str], visible_at, title: str,
           payload: dict, importance: int, direction: str, source: str,
           tier: str, keywords: list[str] | None = None,
           industries_override: list[str] | None = None) -> dict:
    day = str(visible_at)[:10]
    if industries_override is not None:      # 宏观/政策事件:无个股主属,直给行业标签
        inds = sorted(set(industries_override))
    else:
        inds = sorted({i for c in subjects
                       if (i := industry_as_of(c, day, "L1")) is not None})
    cmap = concept_map()
    concepts = sorted({b for c in subjects for b in cmap.get(c, [])})[:20]
    return {
        # 判同键哈希用完整标题+来源(复审#2 minor:title[:80] 会把不同事件坍缩同 id);
        # 显示截断只在渲染层
        "event_id": sha16(f"{event_type}|{'|'.join(sorted(subjects))}|{day}|{title}|{source}"),
        "event_type": event_type, "subject_codes": subjects,
        "industry_tags": inds, "concept_tags": concepts, "hotword_tags": [],
        "keyword_tags": keywords or [],
        "importance_0_5": importance, "direction": direction,
        "source": source, "source_tier": tier,
        "visible_at": pd.Timestamp(visible_at), "title": title,
        "payload": json.dumps(payload, ensure_ascii=False),
        "tag_version": C.TAG_VERSION,
        "event_store_version": C.EVENT_STORE_VERSION,
        "evidence_class": C.EVIDENCE_CLASS_REPLAY,
    }


def _next_morning(day: str) -> pd.Timestamp:
    """结构化数据日 T 盘后产生 → 保守可见 = T+1 08:00(次日盘前)。"""
    cal = pd.read_parquet(C.TRADE_CAL)
    opens = sorted(cal.loc[cal["is_open"] == 1, "cal_date"].astype(str))
    import bisect
    nxt = opens[bisect.bisect_right(opens, day)]
    return pd.Timestamp(nxt) + pd.Timedelta(hours=8)


# ------------------------------------------------------- bin-sourced generators

def gen_market_events(days: list[str]) -> list[dict]:
    """G1-G3:涨跌停/炸板 + 龙虎榜/机构方向 + 大宗折溢价(全市场,bins)。"""
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=str(C.QLIB_DIR), region=REG_CN, kernels=1)
    fields = ["$open", "$close", "$high", "$low", "$vol", "$up_limit", "$down_limit",
              "$top_list__amount", "$top_inst__buy", "$top_inst__sell",
              "$block_trade__price", "$block_trade__amount"]
    avail = D.list_instruments(D.instruments("all"),
                               start_time=days[0], end_time=days[-1], as_list=True)
    df = D.features(avail, fields, start_time=days[0], end_time=days[-1], freq="day")
    df.columns = [c.lstrip("$") for c in fields]
    logger.info("market bins loaded: %d rows", len(df))

    def to_ts(qcode: str) -> str:
        root, exch = str(qcode).upper().split("_")
        return f"{root}.{exch}"

    ev = []
    eps = 1e-6
    for (inst, ts), r in df.iterrows():
        code, day = to_ts(inst), ts.strftime("%Y%m%d")
        vis = _next_morning(day)
        c, h, o, up, dn = r["close"], r["high"], r["open"], r["up_limit"], r["down_limit"]
        if pd.notna(c) and pd.notna(up) and c >= up - eps:
            shape = ("一字板" if (pd.notna(r["low"]) and r["low"] >= up - eps)
                     else "T字板" if (pd.notna(o) and o >= up - eps) else "换手板")
            ev.append(_event("涨停", [code], vis, f"{code} 涨停({shape})",
                             {"day": day, "shape": shape, "close": float(c)},
                             2, "轻微利好", "market_daily", "strong", [shape]))
        elif pd.notna(h) and pd.notna(up) and h >= up - eps and pd.notna(c) and c < up - eps:
            ev.append(_event("炸板", [code], vis, f"{code} 炸板(触及涨停未封住)",
                             {"day": day, "close": float(c)}, 2, "轻微利空",
                             "market_daily", "strong"))
        if pd.notna(c) and pd.notna(dn) and c <= dn + eps:
            ev.append(_event("跌停", [code], vis, f"{code} 跌停",
                             {"day": day, "close": float(c)}, 3, "间接利空",
                             "market_daily", "strong"))
        if pd.notna(r["top_list__amount"]):
            net_inst = ((r["top_inst__buy"] or 0) - (r["top_inst__sell"] or 0)
                        if pd.notna(r["top_inst__buy"]) or pd.notna(r["top_inst__sell"])
                        else float("nan"))
            d_ = ("轻微利好" if pd.notna(net_inst) and net_inst > 0
                  else "轻微利空" if pd.notna(net_inst) and net_inst < 0 else "中性")
            ev.append(_event("龙虎榜", [code], vis, f"{code} 龙虎榜上榜",
                             {"day": day, "amount": float(r["top_list__amount"]),
                              "inst_net": None if pd.isna(net_inst) else float(net_inst)},
                             3, d_, "top_list", "strong"))
        if pd.notna(r["block_trade__price"]) and pd.notna(c) and c > 0:
            prem = float(r["block_trade__price"]) / float(c) - 1.0
            if abs(prem) >= 0.05:
                ev.append(_event("大宗折溢价", [code], vis,
                                 f"{code} 大宗{'折' if prem < 0 else '溢'}价 {prem:+.1%}",
                                 {"day": day, "premium": prem}, 2,
                                 "轻微利空" if prem < 0 else "中性",
                                 "block_trade", "strong"))
    return ev


def gen_suspend_events(days: list[str]) -> list[dict]:
    """G4:停复牌(suspend_d reference)。"""
    if not days:
        return []
    # suspend_d is YEAR-PARTITIONED (data/market/suspend_d/<year>/suspend_d_<date>.parquet). Read ONLY
    # the requested dates' files directly rather than globbing + reading all history (GPT 5-C M4/M2).
    files = [SUSPEND_DIR / d[:4] / f"suspend_d_{d}.parquet" for d in days]
    files = [f for f in files if f.exists()]
    if not files:
        return []
    sd = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    dcol = "trade_date" if "trade_date" in sd.columns else "suspend_date"
    sd[dcol] = sd[dcol].astype(str).str.replace("-", "").str[:8]
    sd = sd[(sd[dcol] >= days[0]) & (sd[dcol] <= days[-1])]
    ev = []
    for _, r in sd.iterrows():
        typ = str(r.get("suspend_type", "S"))
        ev.append(_event("停复牌", [r["ts_code"]], _next_morning(r[dcol]),
                         f"{r['ts_code']} {'停牌' if typ.startswith('S') else '复牌'}",
                         {"day": r[dcol], "suspend_type": typ}, 4, "中性",
                         "suspend_d", "strong"))
    return ev


# ------------------------------------------------------------- text generators

def classify_title(title: str) -> tuple[str, int, str] | None:
    """公告标题确定性分型;行政噪音返回 None(杀灭,不成事件)。"""
    import re
    for kw in ADMIN_KILL:
        if kw in title:
            return None
    for typ, kws, imp, d_ in TITLE_TYPES:
        for kw in kws:
            if re.search(kw, title):
                return typ, imp, d_
    return "其他公告", 1, "中性"


def gen_anns_events(window_start: str, window_end: str) -> tuple[list[dict], dict]:
    """G5:anns_d 标题分型(hist pilot store;可见性=sim_visible_at)。"""
    df = pd.read_parquet(HIST_TEXT_STORE / "anns_d" / "text_anns_d.parquet")
    df = df[df["sim_visible_at"].notna()].copy()
    m = (df["sim_visible_at"] >= pd.Timestamp(window_start)) & \
        (df["sim_visible_at"] <= pd.Timestamp(window_end) + pd.Timedelta(days=1))
    df = df[m]
    ev, killed, kept = [], 0, 0
    for _, r in df.iterrows():
        title = str(r.get("title", ""))
        res = classify_title(title)
        if res is None:
            killed += 1
            continue
        typ, imp, d_ = res
        kept += 1
        ev.append(_event(typ, [r["ts_code"]], r["sim_visible_at"], title,
                         {"url": r.get("url", ""), "ann_date": str(r.get("ann_date", ""))},
                         imp, d_, "anns_d", "strong"))
    stats = {"anns_total": int(len(df)), "admin_killed": killed, "kept": kept,
             "kill_rate": round(killed / max(1, len(df)), 3)}
    return ev, stats


def gen_ledger_events(window_start: str, window_end: str) -> list[dict]:
    """G6-G8:业绩预告/董监高增减持/分红 —— 经 sanctioned 事件门(pit_event_feed),
    可见性=账本已验 effective_date(dividends=严格次开盘日推导)。全市场。"""
    from data_infra.pit_event_feed import load_event_feed
    ev = []
    # 业绩预告:类型自带方向;重要性按幅度+方向翻转
    fc = load_event_feed("forecast", start=window_start, end=window_end)
    for _, r in fc.iterrows():
        typ = str(r.get("type", ""))
        pmax = r.get("p_change_max")
        flip = typ in ("扭亏", "首亏")
        imp = 5 if flip else 4 if (pd.notna(pmax) and abs(pmax) >= 50) else 3
        d_ = ("显著利好" if typ in ("预增", "扭亏", "略增", "续盈") and imp >= 4 else
              "轻微利好" if typ in ("预增", "扭亏", "略增", "续盈") else
              "严重利空" if typ in ("首亏",) else
              "间接利空" if typ in ("预减", "略减", "续亏") else "中性")
        rng = (f"{float(r.get('p_change_min')):.1f}%~{float(pmax):.1f}%"
               if pd.notna(r.get("p_change_min")) and pd.notna(pmax) else "")
        ev.append(_event("业绩预告", [r["ts_code"]], r["visible_at"],
                         f"{r['ts_code']} 业绩预告:{typ} {rng}",
                         {"type": typ, "p_change_min": None if pd.isna(r.get("p_change_min")) else float(r["p_change_min"]),
                          "p_change_max": None if pd.isna(pmax) else float(pmax),
                          "summary": str(r.get("summary", ""))[:200]},
                         imp, d_, "forecast", "strong", [typ]))
    # 董监高增减持:方向=in_de;重要性按变动比例
    ht = load_event_feed("stk_holdertrade", start=window_start, end=window_end)
    for _, r in ht.iterrows():
        inc = str(r.get("in_de", "")).upper() in ("IN", "增持")
        ratio = r.get("change_ratio")
        imp = 4 if (pd.notna(ratio) and abs(ratio) >= 0.5) else 3
        ev.append(_event("董监高增减持", [r["ts_code"]], r["visible_at"],
                         f"{r['ts_code']} {str(r.get('holder_type',''))}"
                         f"{'增持' if inc else '减持'} "
                         f"{f'{float(ratio):.2f}' if pd.notna(ratio) else '?'}%",
                         {"holder_type": str(r.get("holder_type", "")),
                          "in_de": str(r.get("in_de", "")),
                          "change_ratio": None if pd.isna(ratio) else float(ratio)},
                         imp, "轻微利好" if inc else "轻微利空",
                         "stk_holdertrade", "strong"))
    # 业绩快报:比正式财报早,数字为实际值(非预告区间)
    ex = load_event_feed("express", start=window_start, end=window_end)
    for _, r in ex.iterrows():
        yoy = r.get("yoy_net_profit")
        imp = 4 if (pd.notna(yoy) and abs(yoy) >= 50) else 3
        d_ = ("显著利好" if pd.notna(yoy) and yoy >= 50 else
              "轻微利好" if pd.notna(yoy) and yoy > 0 else
              "间接利空" if pd.notna(yoy) and yoy <= -30 else
              "轻微利空" if pd.notna(yoy) and yoy < 0 else "中性")
        ev.append(_event("业绩快报", [r["ts_code"]], r["visible_at"],
                         f"{r['ts_code']} 业绩快报:净利同比"
                         f"{'' if pd.isna(yoy) else f'{yoy:+.0f}%'}",
                         {"n_income": None if pd.isna(r.get("n_income")) else float(r["n_income"]),
                          "yoy_net_profit": None if pd.isna(yoy) else float(yoy),
                          "diluted_roe": None if pd.isna(r.get("diluted_roe")) else float(r["diluted_roe"])},
                         imp, d_, "express", "strong"))
    # 非标审计意见:治理红旗(标准无保留意见不成事件)
    au = load_event_feed("fina_audit", start=window_start, end=window_end)
    au = au[au["audit_result"].notna()
            & ~au["audit_result"].astype(str).str.startswith("标准无保留")]
    for _, r in au.iterrows():
        ev.append(_event("非标审计意见", [r["ts_code"]], r["visible_at"],
                         f"{r['ts_code']} 审计意见:{r['audit_result']}",
                         {"audit_result": str(r["audit_result"]),
                          "audit_agency": str(r.get("audit_agency", ""))},
                         5, "严重利空", "fina_audit", "strong"))
    # 分红:预案/实施
    dv = load_event_feed("dividends", start=window_start, end=window_end)
    dv = dv[dv["div_proc"].isin(["预案", "实施"])]
    for _, r in dv.iterrows():
        cash = r.get("cash_div_tax")
        ev.append(_event("分红", [r["ts_code"]], r["visible_at"],
                         f"{r['ts_code']} 分红{r['div_proc']}"
                         f"{'' if pd.isna(cash) else f' 每股{cash}元'}",
                         {"div_proc": str(r["div_proc"]),
                          "cash_div_tax": None if pd.isna(cash) else float(cash)},
                         2, "轻微利好", "dividends", "strong"))
    return ev


def gen_research_report_events(window_start: str, window_end: str) -> list[dict]:
    """G9:研报摘要事件(确定性标题/摘要分型;摘要精华烤进标题供 dossier 呈现)。"""
    df = pd.read_parquet(HIST_TEXT_STORE / "research_report" / "text_research_report.parquet")
    df = df[df["sim_visible_at"].notna()
            & (df["sim_visible_at"] >= pd.Timestamp(window_start))
            & (df["sim_visible_at"] <= pd.Timestamp(window_end) + pd.Timedelta(days=1))]
    df = df[df["ts_code"].notna() & (df["ts_code"].astype(str).str.len() > 0)]
    ev = []
    for _, r in df.iterrows():
        title, abstr = str(r.get("title", "")), str(r.get("abstr", "") or "")
        if "首次覆盖" in title or "首次覆盖" in abstr[:100]:
            typ, imp = "研报首次覆盖", 3
        elif any(k in title for k in ("买入", "增持", "推荐", "强推", "优于大市")):
            typ, imp = "研报评级", 2
        elif "深度" in title:
            typ, imp = "深度研报", 2
        else:
            typ, imp = "研报点评", 1
        show = f"{r.get('inst_csname', '')}研报:{title[:40]}" + \
               (f"——{abstr[:80]}" if abstr else "")
        ev.append(_event(typ, [r["ts_code"]], r["sim_visible_at"], show,
                         {"inst": str(r.get("inst_csname", "")), "abstr": abstr[:300]},
                         imp, "轻微利好" if typ in ("研报首次覆盖", "研报评级") else "中性",
                         "research_report", "medium"))
    return ev


def gen_report_rc_events(days: list[str]) -> list[dict]:
    """G10:分析师修正潮(bins:单日 eps_up/dn ≥3 人 → 事件;全市场)。"""
    from qlib.data import D          # qlib 已在 gen_market_events 初始化
    avail = D.list_instruments(D.instruments("all"),
                               start_time=days[0], end_time=days[-1], as_list=True)
    win_start = (pd.Timestamp(days[0]) - pd.Timedelta(days=30)).strftime("%Y-%m-%d")
    df = D.features(avail, ["$report_rc__eps_up", "$report_rc__eps_dn"],
                    start_time=win_start, end_time=days[-1], freq="day")
    df.columns = ["eps_up", "eps_dn"]
    df = df[(df["eps_up"] >= 3) | (df["eps_dn"] >= 3)]
    ev = []
    for (inst, ts), r in df.iterrows():
        root, exch = str(inst).upper().split("_")
        code, day = f"{root}.{exch}", ts.strftime("%Y%m%d")
        if pd.notna(r["eps_up"]) and r["eps_up"] >= 3:
            ev.append(_event("分析师上调潮", [code], _next_morning(day),
                             f"{code} 单日 {int(r['eps_up'])} 名分析师上调 FY1 EPS",
                             {"day": day, "eps_up": int(r["eps_up"])}, 3, "轻微利好",
                             "report_rc", "medium"))
        if pd.notna(r["eps_dn"]) and r["eps_dn"] >= 3:
            ev.append(_event("分析师下调潮", [code], _next_morning(day),
                             f"{code} 单日 {int(r['eps_dn'])} 名分析师下调 FY1 EPS",
                             {"day": day, "eps_dn": int(r["eps_dn"])}, 3, "轻微利空",
                             "report_rc", "medium"))
    return ev


_IRM_TYPES = ["产能", "订单", "业绩", "产品", "客户", "研发", "扩张", "风险", "其他"]


def _norm_irm_type(raw: str) -> str:
    """LLM 偶发自由组合标签(研发|产品 / 整枚举复读)→ 归一到首个合法类型(税onomy 纪律)。"""
    for token in str(raw).replace("/", "|").split("|"):
        if token.strip() in _IRM_TYPES:
            return token.strip()
    return "其他"


def gen_irm_events() -> list[dict]:
    """G11:互动易实质问答(消费 irm_typing.py 的分型产物;缺文件=跳过并警告)。"""
    p = C.OUT_ROOT / "irm_typed" / f"irm_typed_{C.PILOT_POOL_MONTH}.parquet"
    if not p.exists():
        logger.warning("irm_typed parquet missing (%s) — 互动易事件跳过,先跑 irm_typing.py", p)
        return []
    df = pd.read_parquet(p)
    df["type"] = df["type"].map(_norm_irm_type)
    ev = []
    for _, r in df.iterrows():
        ev.append(_event(f"互动易-{r['type']}", [r["ts_code"]], r["visible_at"],
                         f"{r['ts_code']} 互动易({r['mgmt_tone']}):{r['summary']}",
                         {"q": r["q"], "summary": r["summary"],
                          "mgmt_tone": r["mgmt_tone"]},
                         2, r["direction"], r["source"], "strong"))
    return ev


#: 政策→申万 L1 行业词表(v1 手工;词命中即打行业标签,政策事件经 industry 通道被检索)
_POLICY_IND_WORDS = {
    "房地产|楼市|住房|保障房": "房地产", "银行|信贷|存款|贷款": "银行",
    "证券|券商|资本市场|IPO|上市公司": "非银金融", "保险": "非银金融",
    "芯片|半导体|集成电路": "电子", "汽车|新能源车|智能网联": "汽车",
    "光伏|风电|储能|锂电": "电力设备", "医药|医疗|药品|医保|疫苗": "医药生物",
    "白酒|食品|乳业": "食品饮料", "军工|国防": "国防军工", "煤炭": "煤炭",
    "钢铁": "钢铁", "化工|化肥": "基础化工", "农业|粮食|种业|耕地": "农林牧渔",
    "家电": "家用电器", "基建|建筑|城市更新": "建筑装饰", "水泥|建材": "建筑材料",
    "机械|装备制造|工业母机": "机械设备",
    "人工智能|算力|软件|数据要素|数字经济|信创": "计算机",
    "5G|6G|通信|电信": "通信", "游戏|影视|文化|传媒|广电": "传媒",
    "环保|碳排放|碳中和|绿色": "环保", "电力|电网|电价": "公用事业",
    "石油|油气|成品油": "石油石化", "稀土|有色|锂矿|铜": "有色金属",
    "纺织|服装": "纺织服饰", "零售|消费|免税": "商贸零售",
    "旅游|酒店|餐饮": "社会服务", "物流|快递|航运|港口|铁路|民航": "交通运输",
}


def _l1_name_to_code() -> dict[str, str]:
    mem = pd.read_parquet(C.PROJECT_ROOT / "data" / "universe"
                          / "industry_sw2021_members" / "industry_sw2021_members.parquet",
                          columns=["l1_code", "l1_name"]).drop_duplicates()
    return dict(zip(mem.l1_name, mem.l1_code))


def _match_industries(text: str, name2code: dict) -> tuple[list[str], list[str]]:
    import re
    codes, words = set(), []
    for pat, ind_name in _POLICY_IND_WORDS.items():
        m = re.search(pat, text)
        if m and ind_name in name2code:
            codes.add(name2code[ind_name])
            words.append(m.group(0))
    return sorted(codes), words


def gen_policy_events(window_start: str, window_end: str) -> list[dict]:
    """G12:政策三源(npr/货政/联播)→ 无主属行业级政策事件(v1.5-D)。"""
    n2c = _l1_name_to_code()
    ev = []
    ws, we = pd.Timestamp(window_start), pd.Timestamp(window_end) + pd.Timedelta(days=1)

    def _load(src):
        p = HIST_TEXT_STORE / src / f"text_{src}.parquet"
        if not p.exists():
            return pd.DataFrame()
        df = pd.read_parquet(p)
        df = df[df["sim_visible_at"].notna()
                & (df["sim_visible_at"] >= ws) & (df["sim_visible_at"] <= we)]
        return df

    for _, r in _load("npr").iterrows():
        text = f"{r.get('title', '')} {r.get('ptype', '')}"
        codes, words = _match_industries(text, n2c)
        ev.append(_event("政策发布", [], r["sim_visible_at"],
                         f"[{r.get('puborg', '')}] {str(r.get('title', ''))[:80]}",
                         {"ptype": str(r.get("ptype", ""))}, 4, "中性", "npr",
                         "strong", words, industries_override=codes))
    for _, r in _load("monetary_policy").iterrows():
        ev.append(_event("货币政策报告", [], r["sim_visible_at"],
                         str(r.get("title", ""))[:80], {}, 5, "中性",
                         "monetary_policy", "strong",
                         industries_override=[c for n, c in n2c.items()
                                              if n in ("银行", "非银金融")]))
    for _, r in _load("cctv_news").iterrows():
        text = f"{r.get('title', '')} {str(r.get('content', ''))[:3000]}"
        codes, words = _match_industries(text, n2c)
        if not codes:
            continue                          # 无行业关联的联播条目=宏观噪音,不成事件
        ev.append(_event("新闻联播", [], r["sim_visible_at"],
                         str(r.get("title", ""))[:80],
                         {"matched": words}, 2, "中性", "cctv_news", "strong",
                         words, industries_override=codes))
    return ev


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    from workspace.research.ai_research_dept.engine.fact_table import decision_days
    days = decision_days(C.PILOT_POOL_MONTH, C.PILOT_MONTH_END)
    t0 = time.time()

    # 事件窗 = 决策窗 + 30d 回看(与检索热窗一致)。复审#2 Major:行情/停复牌/修正潮
    # 生成器此前只跑决策日 → 首决策日的检索回看窗内无行情事件(伪冷启动)。
    win_start = (pd.Timestamp(days[0]) - pd.Timedelta(days=30)).strftime("%Y-%m-%d")
    cal = pd.read_parquet(C.TRADE_CAL)
    opens = cal.loc[cal["is_open"] == 1, "cal_date"].astype(str)
    # 复审#3 minor:窗首前再多取一个开市日——win_start 当天可见的行情事件可能来自
    # 前一交易日盘后;最终窗口由检索端按 visible_at 过滤
    open_days = sorted(opens[opens <= days[-1]])
    first = next(i for i, d in enumerate(open_days)
                 if d >= win_start.replace("-", ""))
    event_days = open_days[max(0, first - 1):]

    ev = gen_market_events(event_days)
    logger.info("market events: %d (窗含 %d 个预热交易日)",
                len(ev), len(event_days) - len(days))
    sus = gen_suspend_events(event_days)
    logger.info("suspend events: %d", len(sus))
    anns, stats = gen_anns_events(win_start, days[-1])
    logger.info("anns events: %d | %s", len(anns), stats)
    led = gen_ledger_events(win_start, days[-1])
    logger.info("ledger events (forecast/holdertrade/dividends): %d", len(led))
    rr = gen_research_report_events(win_start, days[-1])
    logger.info("research_report events: %d", len(rr))
    rc = gen_report_rc_events(event_days)
    logger.info("report_rc surge events: %d", len(rc))
    irm = gen_irm_events()
    logger.info("irm_qa substantive events: %d", len(irm))
    pol = gen_policy_events(win_start, days[-1])
    logger.info("policy events (npr/货政/联播): %d", len(pol))

    all_ev = pd.DataFrame(ev + sus + anns + led + rr + rc + irm + pol)
    all_ev = all_ev.drop_duplicates(subset=["event_id"])      # 判同 v0:同键去重
    C.EVENT_DIR.mkdir(parents=True, exist_ok=True)
    out = C.EVENT_DIR / f"events_{C.PILOT_POOL_MONTH}.parquet"
    all_ev.to_parquet(out, index=False)

    summary = {
        "events": len(all_ev),
        "by_type": all_ev["event_type"].value_counts().to_dict(),
        "anns_stats": stats,
        "elapsed_s": round(time.time() - t0, 1),
        "config_hash": C.config_hash(),
        "evidence_class": C.EVIDENCE_CLASS_REPLAY,
    }
    (C.EVENT_DIR / f"summary_{C.PILOT_POOL_MONTH}.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("event store -> %s | %d events", out, len(all_ev))
    print(json.dumps(summary["by_type"], ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
