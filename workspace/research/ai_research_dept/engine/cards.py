# SCRIPT_STATUS: ACTIVE — 卡片渲染器(纯确定性,零 LLM/编排依赖)
"""Card renderers shared by the analyst chain AND the read-only platform.

边界说明:本模块只依赖 pandas,不 import 任何 LLM/编排代码——平台进程可安全引用
(INTEL_CENTER §6 硬边界:平台不得 import 评分/编排模块;渲染器是视图代码)。
席位权重也放此处(链与平台展示共用一份,防两处漂移)。
"""
from __future__ import annotations

import pandas as pd

#: 席位权重(预注册;Σ=20 → final 原生 0-100)
SEAT_WEIGHTS = {
    "fund": {"profitability_quality": 6, "growth_momentum": 6,
             "balance_sheet_strength": 4, "earnings_inflection": 4},
    "tech": {"trend_structure": 5, "momentum_quality": 4, "volume_price_confirm": 5,
             "chip_structure": 3, "smart_money_consistency": 3},
    "news": {"event_materiality": 6, "fundamental_link": 5, "novelty": 5,
             "catalyst_timing": 4},
}
COMPOSITE_W = {"fund": 0.4, "tech": 0.3, "news": 0.3}

FIELD_CN = {"roe_waa": "ROE(加权)%", "grossprofit_margin": "毛利率%",
            "netprofit_margin": "净利率%", "ocf_to_or": "经营现金流/营收",
            "or_yoy": "营收同比%", "netprofit_yoy": "净利润同比%",
            "dt_netprofit_yoy": "扣非净利同比%", "basic_eps_yoy": "EPS同比%",
            "debt_to_assets": "资产负债率%", "current_ratio": "流动比率",
            "assets_turn": "总资产周转", "pe_ttm": "PE(TTM)", "pb": "PB",
            "total_mv": "总市值(万)", "turnover_rate": "换手率%"}
SUBCARD_CN = {"A": "趋势形态", "B": "量能结构", "C": "筹码持仓",
              "D": "主力行为", "E": "涨停语言"}


def render_fund_card(facts: pd.DataFrame, biz_text: str | None = None) -> str:
    lines = ["【基本面三锚定事实表】(值|行业分位(同业家数)|自身10年分位)"]
    for _, r in facts.iterrows():
        ip = "" if pd.isna(r["industry_pctl"]) else f"行业分位{r['industry_pctl']:.0%}({r['industry_n']}家)"
        hp = "" if pd.isna(r["hist_pctl"]) else f"10年分位{r['hist_pctl']:.0%}"
        lines.append(f"- {FIELD_CN.get(r['field'], r['field'])}: {r['value']:g}|{ip}|{hp}")
    if biz_text:
        lines.append(biz_text)          # v1.5-A: fina_mainbz 业务构成节(as-of 最新报告期)
    return "\n".join(lines)


def render_pv_card(pv: pd.DataFrame) -> str:
    lines = ["【量价情报包】(项目: 值「状态」[分位];全部由代码判定)"]
    for card in "ABCDE":
        sub = pv[pv["subcard"] == card]
        if sub.empty:
            continue
        lines.append(f"◆ {SUBCARD_CN[card]}")
        for _, r in sub.iterrows():
            v = "" if r["value"] is None or pd.isna(r["value"]) else f"{r['value']:g}"
            s = f"「{r['state']}」" if r["state"] else ""
            p = "" if r["pctl"] is None or pd.isna(r["pctl"]) else f"[分位{r['pctl']:.0%}]"
            lines.append(f"- {r['item']}: {v}{s}{p}")
    return "\n".join(lines)


def render_news_card(retr: pd.DataFrame) -> str:
    lines = ["【检索装配单】"]
    d = retr[retr["channel"] == "direct"]
    lines.append(f"—— 直接事件(本股,{len(d)} 条)——" if len(d) else "—— 直接事件:无 ——")
    for _, r in d.iterrows():
        lines.append(f"- {r['event_type']}|{r['title']}|{r['direction']}")
    ind = retr[retr["channel"] == "industry"].nlargest(12, "relevance")
    lines.append(f"—— 行业间接事件(同业,top{len(ind)})——" if len(ind) else "—— 行业间接事件:无 ——")
    for _, r in ind.iterrows():
        lines.append(f"- {r['event_type']}|{r['title']}|{r['direction']}|相关度{r['relevance']:.2f}")
    return "\n".join(lines)
