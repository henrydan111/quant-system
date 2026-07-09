# SCRIPT_STATUS: ACTIVE — 关注度榜 v0(市场热点产品的算法核,全确定性)
"""Attention board (INTEL_CENTER §2.1):诚实命名"关注度"(无社媒,不冒充情绪)。

    attention_raw = Σ wᵢ · componentᵢ(全部为分位/归一分量)
    attention     = 当日截面 rank_pct × 100
    trend         = attention 5 日斜率

分量(全部来自已建工件,零新计算源):
    ev_density   30d 直接事件数(事件库)截面分位
    turnover_p   换手率 250d 自身分位(量价包 B)
    vol_ratio    量比截面分位(量价包 B)
    top_list     龙虎榜 20d 次数归一(量价包 D)
    limit_lang   涨停+炸板 20d 归一(量价包 E)
    flow_ex      |净流强度分位-0.5|×2(量价包 D,极端资金关注)

权重预注册(改=新版本);拥挤反指假设(attention>95 分位)由技术席消费,本模块只产数。
用法: venv/Scripts/python.exe workspace/research/ai_research_dept/engine/attention.py
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from workspace.research.ai_research_dept.engine import config as C  # noqa: E402
from workspace.research.ai_research_dept.engine.fact_table import decision_days  # noqa: E402

logger = logging.getLogger("attention")

ATTENTION_VERSION = "attn_v0.1"
WEIGHTS = {"ev_density": 0.25, "turnover_p": 0.20, "vol_ratio": 0.15,
           "top_list": 0.15, "limit_lang": 0.15, "flow_ex": 0.10}
ATTN_DIR = C.OUT_ROOT / "attention"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    days = decision_days(C.PILOT_POOL_MONTH, C.PILOT_MONTH_END)
    pool = sorted(set(pd.read_parquet(
        C.POOL_DIR / f"broker_recommend_{C.PILOT_POOL_MONTH}.parquet")["ts_code"]))
    ev = pd.read_parquet(C.EVENT_DIR / f"events_{C.PILOT_POOL_MONTH}.parquet")
    pv = pd.read_parquet(C.PV_DIR / f"pv_pack_{C.PILOT_POOL_MONTH}.parquet")

    # 事件密度:每股 30d 直接事件数(按决策日窗)
    ev_exp = ev.explode("subject_codes")[["subject_codes", "visible_at", "importance_0_5"]]
    rows = []
    for day in days:
        cutoff = pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]} 09:15:00")
        w = ev_exp[(ev_exp.visible_at <= cutoff)
                   & (ev_exp.visible_at >= cutoff - pd.Timedelta(days=30))]
        counts = w.groupby("subject_codes").size()
        pvd = pv[pv.trade_date == day].pivot_table(
            index="ts_code", columns="item", values="value", aggfunc="first")
        pvp = pv[pv.trade_date == day].pivot_table(
            index="ts_code", columns="item", values="pctl", aggfunc="first")
        for code in pool:
            comp = {
                "ev_density": float(counts.get(code, 0)),
                "turnover_p": float(pvp.get("换手分位250d", pd.Series()).get(code, 0.5) or 0.5),
                "vol_ratio": float(pvd.get("量比", pd.Series()).get(code, 1.0) or 1.0),
                "top_list": min(1.0, float(pvd.get("龙虎榜20d", pd.Series()).get(code, 0) or 0) / 3),
                "limit_lang": min(1.0, (float(pvd.get("涨停20d", pd.Series()).get(code, 0) or 0)
                                        + float(pvd.get("炸板20d", pd.Series()).get(code, 0) or 0)) / 4),
                "flow_ex": abs(float(pvp.get("净流强度分位", pd.Series()).get(code, 0.5) or 0.5) - 0.5) * 2,
            }
            rows.append({"ts_code": code, "trade_date": day, **comp})

    df = pd.DataFrame(rows)
    # 分量归一(ev_density/vol_ratio 截面分位化),加权,截面 0-100
    for col, cross in [("ev_density", True), ("vol_ratio", True)]:
        df[col] = df.groupby("trade_date")[col].rank(pct=True)
    df["attention_raw"] = sum(df[k] * w for k, w in WEIGHTS.items())
    df["attention"] = (df.groupby("trade_date")["attention_raw"]
                       .rank(pct=True) * 100).round(1)
    df = df.sort_values(["ts_code", "trade_date"])
    df["trend"] = (df.groupby("ts_code")["attention"]
                   .transform(lambda s: s.diff(5) / 5).round(2))
    df["attention_version"] = ATTENTION_VERSION
    df["evidence_class"] = C.EVIDENCE_CLASS_REPLAY

    ATTN_DIR.mkdir(parents=True, exist_ok=True)
    out = ATTN_DIR / f"attention_{C.PILOT_POOL_MONTH}.parquet"
    df.to_parquet(out, index=False)
    last = df[df.trade_date == days[-1]].nlargest(5, "attention")
    logger.info("attention -> %s | rows=%d | top5 @%s: %s", out, len(df), days[-1],
                list(zip(last.ts_code, last.attention)))
    (ATTN_DIR / "config.json").write_text(json.dumps(
        {"version": ATTENTION_VERSION, "weights": WEIGHTS}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
