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


def _event(event_type: str, subjects: list[str], visible_at, title: str,
           payload: dict, importance: int, direction: str, source: str,
           tier: str, keywords: list[str] | None = None) -> dict:
    day = str(visible_at)[:10]
    inds = sorted({i for c in subjects
                   if (i := industry_as_of(c, day, "L1")) is not None})
    return {
        "event_id": sha16(f"{event_type}|{'|'.join(sorted(subjects))}|{day}|{title[:80]}"),
        "event_type": event_type, "subject_codes": subjects,
        "industry_tags": inds, "concept_tags": [], "hotword_tags": [],
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
    files = sorted(SUSPEND_DIR.glob("*.parquet"))
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


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    from workspace.research.ai_research_dept.engine.fact_table import decision_days
    days = decision_days(C.PILOT_POOL_MONTH, C.PILOT_MONTH_END)
    t0 = time.time()

    ev = gen_market_events(days)
    logger.info("market events: %d", len(ev))
    sus = gen_suspend_events(days)
    logger.info("suspend events: %d", len(sus))
    # 文本事件窗 = 决策窗 + 30d 回看(检索热窗一致)
    win_start = (pd.Timestamp(days[0]) - pd.Timedelta(days=30)).strftime("%Y-%m-%d")
    anns, stats = gen_anns_events(win_start, days[-1])
    logger.info("anns events: %d | %s", len(anns), stats)

    all_ev = pd.DataFrame(ev + sus + anns)
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
