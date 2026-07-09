# SCRIPT_STATUS: ACTIVE — 卡片渲染器 v2(纯确定性,零 LLM/编排依赖;chain_v2.0)
"""Card renderers shared by the analyst chain AND the read-only platform.

边界说明:本模块只依赖 pandas,不 import 任何 LLM/编排代码——平台进程可安全引用
(INTEL_CENTER §6 硬边界:平台不得 import 评分/编排模块;渲染器是视图代码)。
席位权重也放此处(链与平台展示共用一份,防两处漂移)。

v2(审计 INPUT_PROMPT_AUDIT_v1,自评通过实施):
- 行 ID(F/T/N 前缀):证据引用可精确定位,证据独占按行唯一化;
- 格式规范(§6.1):百分比 1 位小数、市值亿、禁科学计数法、单位显式;
- ⚑ 确定性焦点旗(§9.1-2):三锚定背离>50pp / 极端分位,top-3,事实标注非意见;
- 基本面卡:+vintage 8 季序列节、PS/股息率、披露动态行(B 方案:方向不给幅度);
- 消息面卡:行内相对时间+重要性星标、间接节类型配额≤3+返回集内聚合、负面缺席声明、
  全景计数行;直接节按 重要性→新近度 排序 cap 12。
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
            "ps_ttm": "PS(TTM)", "dv_ratio": "股息率%",
            "total_mv": "总市值", "turnover_rate": "换手率%"}
SUBCARD_CN = {"A": "趋势形态", "B": "量能结构", "C": "筹码持仓",
              "D": "主力行为", "E": "涨停语言"}

#: 字段呈现类型:pct1=已是百分数值(1 位小数);ratio2=比率(2 位小数);mv=市值(万→亿)
_FUND_FMT = {"roe_waa": "pct1", "grossprofit_margin": "pct1", "netprofit_margin": "pct1",
             "or_yoy": "pct1", "netprofit_yoy": "pct1", "dt_netprofit_yoy": "pct1",
             "basic_eps_yoy": "pct1", "debt_to_assets": "pct1", "turnover_rate": "pct1",
             "dv_ratio": "pct1",
             "ocf_to_or": "ratio2", "current_ratio": "ratio2", "assets_turn": "ratio2",
             "pe_ttm": "ratio2", "pb": "ratio2", "ps_ttm": "ratio2",
             "total_mv": "mv"}


def _fmt_fund(field: str, v: float) -> str:
    kind = _FUND_FMT.get(field, "ratio2")
    if kind == "mv":
        return f"{v / 1e4:,.0f}亿"
    if field in ("pe_ttm",) and v is not None and v < 0:
        return "亏损(PE无意义)"
    if kind == "pct1":
        return f"{v:.1f}"
    return f"{v:.2f}"


def _series_trend(vals: list[float]) -> str:
    # 季度采样会重复同一已知值(年报空窗)→ 先压缩连续等值再判趋势
    dedup = [v for i, v in enumerate(vals) if i == 0 or v != vals[i - 1]]
    vals = dedup
    if len(vals) < 3:
        return ""
    a, b, c = vals[-3], vals[-2], vals[-1]
    if c > b > a:
        return "连续上行"
    if c < b < a:
        return "连续下行"
    if c > 0 >= b:
        return "转正"
    if c < 0 <= b:
        return "转负"
    return ""


def render_fund_card(facts: pd.DataFrame, biz_text: str | None = None,
                     series: pd.DataFrame | None = None,
                     disclosure: str | None = None) -> str:
    lines = ["【基本面三锚定事实表】(行ID|字段: 值|行业分位(同业家数)|自身10年分位;"
             "⚑=代码判定的焦点行:三锚定背离>50pp或极端分位)"]
    # ⚑ 焦点旗:top-3(背离幅度优先,其次极端度);纯事实标注,不写多空
    div = []
    for i, (_, r) in enumerate(facts.iterrows()):
        ip, hp = r["industry_pctl"], r["hist_pctl"]
        score = 0.0
        if pd.notna(ip) and pd.notna(hp):
            score = max(score, abs(ip - hp) if abs(ip - hp) > 0.5 else 0.0)
        if pd.notna(ip):
            score = max(score, (abs(ip - 0.5) - 0.4) * 2 if abs(ip - 0.5) > 0.4 else 0.0)
        div.append((score, i))
    flagged = {i for s, i in sorted(div, reverse=True)[:3] if s > 0}
    for i, (_, r) in enumerate(facts.iterrows()):
        ip = "" if pd.isna(r["industry_pctl"]) else \
            f"行业分位{r['industry_pctl']:.0%}({r['industry_n']}家)"
        hp = "" if pd.isna(r["hist_pctl"]) else f"10年分位{r['hist_pctl']:.0%}"
        flag = "⚑" if i in flagged else ""
        lines.append(f"- [F{i+1:02d}]{flag}{FIELD_CN.get(r['field'], r['field'])}: "
                     f"{_fmt_fund(r['field'], r['value'])}|{ip}|{hp}")
    if series is not None and len(series):
        lines.append("◆ 关键指标近8季采样(vintage口径:各点=该采样时点已知值,旧→新;"
                     "趋势标签由代码判定)")
        for f in series["field"].unique():
            s = series[series["field"] == f].sort_values("seq")
            vals = [float(v) for v in s["value"]]
            arrow = " → ".join(f"{v:.1f}" for v in vals)
            t = _series_trend(vals)
            lines.append(f"- {FIELD_CN.get(f, f)}: {arrow}" + (f"({t})" if t else ""))
    if disclosure:
        # B 方案(审计 §6.4 自裁):方向性状态,不给幅度;prompt 围栏限 earnings_inflection
        lines.append(f"◆ 披露动态: {disclosure}")
    if biz_text:
        lines.append(biz_text)          # v1.5-A: fina_mainbz 业务构成节(as-of 最新报告期)
    return "\n".join(lines)


#: pv 项目呈现类型:值为小数比率 → 百分比显示
_PV_PCT_ITEMS = {"距52周高", "距52周低", "趋势阶段", "RS_vs_300_20d", "RS_vs_300_60d",
                 "本股收益5d", "本股收益20d", "行业指数5d", "行业指数20d",
                 "现价距成本5分位", "现价距成本50分位", "现价距成本95分位",
                 "融资余额20d变动", "大单净流5d占成交额", "大单净流20d占成交额",
                 "净流强度分位", "涨停次日溢价均值", "波动分位", "布林带宽分位",
                 "RS_行业分位_60d", "收盘位置5d", "筹码集中度", "换手5d/20d比"}
_PV_RATIO2 = {"量比", "换手5d/20d比", "筹码集中度", "收盘位置5d"}
_PV_UNIT = {"换手分位250d": "%", "获利盘": "%", "获利盘60d变化": "pp", "北向持股比": "%",
            "北向20d变动": "pp"}


def _fmt_pv(item: str, v) -> str:
    if v is None or pd.isna(v):
        return ""
    if item == "RS_行业分位_60d":          # 分位量,无正负语义
        return f"{float(v) * 100:.1f}%"
    if item in _PV_RATIO2:
        return f"{float(v):.2f}"
    if item in _PV_PCT_ITEMS:
        return f"{float(v) * 100:+.1f}%" if float(v) < 0 or item.startswith(("距", "RS", "本股", "行业", "现价", "融资", "大单", "净流", "涨停次日")) else f"{float(v) * 100:.1f}%"
    u = _PV_UNIT.get(item, "")
    return f"{float(v):.1f}{u}" if isinstance(v, float) and v % 1 else f"{v:g}{u}"


def render_pv_card(pv: pd.DataFrame) -> str:
    lines = ["【量价情报包】(行ID|项目: 值「状态」[分位];全部由代码判定;"
             "⚑=极端分位焦点行)"]
    # ⚑:分位 >90% 或 <10% 的 top-3(按偏离 0.5 距离)
    rows = list(pv.iterrows())
    ext = sorted([(abs(float(r["pctl"]) - 0.5), i) for i, (_, r) in enumerate(rows)
                  if r["pctl"] is not None and pd.notna(r["pctl"])
                  and (float(r["pctl"]) >= 0.9 or float(r["pctl"]) <= 0.1)],
                 reverse=True)
    flagged = {i for _, i in ext[:3]}
    n = 0
    for card in "ABCDE":
        idxs = [i for i, (_, r) in enumerate(rows) if r["subcard"] == card]
        if not idxs:
            continue
        lines.append(f"◆ {SUBCARD_CN[card]}")
        for i in idxs:
            r = rows[i][1]
            n += 1
            v = _fmt_pv(r["item"], r["value"])
            s = f"「{r['state']}」" if r["state"] else ""
            p = "" if r["pctl"] is None or pd.isna(r["pctl"]) else f"[分位{r['pctl']:.0%}]"
            flag = "⚑" if i in flagged else ""
            body = f"{v}{s}{p}" if v or s or p else ""
            lines.append(f"- [T{n:02d}]{flag}{r['item']}: {body}")
    return "\n".join(lines)


_CHANNEL_CN = {"concept": "概念", "industry": "行业", "relation": "关联"}
_RED_FLAG_TYPES = ("减持", "质押", "监管", "诉讼/仲裁", "董监高增减持")


def disclosure_status(r_direct: pd.DataFrame, day: str) -> str:
    """披露动态行(审计 §6.4 B 方案):只给类型+极性+事件龄,幅度留给消息席。
    链与平台共用(纯 pandas,平台可安全 import)。"""
    fc = r_direct[r_direct["event_type"].isin(("业绩预告", "业绩快报"))]
    if fc.empty:
        return "检索窗口内无业绩预告/快报"
    fc = fc.sort_values("visible_at") if "visible_at" in fc.columns else fc
    r = fc.iloc[-1]
    age = ""
    if "visible_at" in fc.columns:
        age = _age_str(day, r["visible_at"])
    return (f"已发布{r['event_type']}[{age}|极性:{r['direction']}]"
            f"(方向性状态;幅度与原文见消息面卡)")


def _age_str(day: str, visible_at) -> str:
    try:
        d = (pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]}")
             - pd.Timestamp(visible_at).normalize()).days
        return "当日" if d <= 0 else f"{d}日前"
    except (ValueError, TypeError):
        return "—"


def _stars(imp) -> str:
    try:
        return "★" * int(imp) or "—"
    except (ValueError, TypeError):
        return "—"


def render_news_card(retr: pd.DataFrame, day: str | None = None) -> str:
    day = day or (str(retr["trade_date"].iloc[0]) if len(retr) else "")
    has_vis = "visible_at" in retr.columns
    lines = ["【检索装配单】(行ID|[事件龄|重要性]类型|标题|极性;间接事件另标通道与相关度)"]
    d = retr[retr["channel"] == "direct"]
    ind = retr[retr["channel"].isin(("concept", "industry", "relation"))]
    # N00 全景计数行(§9.1-6)
    tc = d["event_type"].value_counts()
    top_types = "/".join(f"{t}{c}" for t, c in tc.head(3).items())
    lines.append(f"- [N00]检索窗口全景: 直接事件 {len(d)} 条({top_types or '无'}),"
                 f"间接事件 {len(ind)} 条(检索返回集)")
    n = 0
    # 直接节:重要性 desc → 新近度 desc,cap 12,溢出聚合(§4.2-3)
    if len(d):
        ds = d.sort_values(["importance", "visible_at"] if has_vis else ["importance"],
                           ascending=False)
        shown, overflow = ds.iloc[:12], ds.iloc[12:]
        lines.append(f"—— 直接事件(本股,{len(d)} 条{'' if overflow.empty else ',超额已聚合'})——")
        for _, r in shown.iterrows():
            n += 1
            age = _age_str(day, r["visible_at"]) if has_vis else "—"
            lines.append(f"- [N{n:02d}][{age}|{_stars(r.get('importance'))}]"
                         f"{r['event_type']}|{r['title']}|{r['direction']}")
        for t, grp in overflow.groupby("event_type"):
            n += 1
            dirs = grp["direction"].value_counts()
            dd = "/".join(f"{k}{v}" for k, v in dirs.items())
            lines.append(f"- [N{n:02d}][直接聚合]{t}: 另有{len(grp)}条({dd})")
    else:
        lines.append("—— 直接事件:无 ——")
    # 负面缺席声明(§9.1-3;基于直接通道检索窗口,渲染层可算)
    present = set(d["event_type"].unique())
    absent = [t for t in _RED_FLAG_TYPES if t not in present]
    if absent:
        n += 1
        lines.append(f"- [N{n:02d}]检索窗口内无以下类型的直接事件: {'/'.join(absent)}")
    # 间接节:类型配额≤3 + 返回集内聚合(§4.2-2,F5 修正口径)
    if len(ind):
        srt = ind.sort_values("relevance", ascending=False)
        picked, over = [], {}
        cnt: dict[str, int] = {}
        for _, r in srt.iterrows():
            t = r["event_type"]
            if cnt.get(t, 0) < 3 and len(picked) < 15:
                picked.append(r)
                cnt[t] = cnt.get(t, 0) + 1
            else:
                over.setdefault(t, []).append(r)
        lines.append(f"—— 间接事件(概念/行业同伴,返回集 {len(ind)} 条,"
                     f"明细 top{len(picked)} 每类型≤3,余为聚合)——")
        for r in picked:
            n += 1
            age = _age_str(day, r["visible_at"]) if has_vis else "—"
            lines.append(f"- [N{n:02d}][{_CHANNEL_CN.get(r['channel'], r['channel'])}|{age}]"
                         f"{r['event_type']}|{r['title']}|{r['direction']}"
                         f"|相关度{r['relevance']:.2f}")
        for t, rows_t in over.items():
            n += 1
            dirs = pd.Series([r["direction"] for r in rows_t]).value_counts()
            dd = "/".join(f"{k}{v}" for k, v in dirs.items())
            lines.append(f"- [N{n:02d}][概念聚合]{t}: 返回集内另有{len(rows_t)}条({dd})"
                         f"——聚合行属间接证据,封顶3分")
    else:
        lines.append("—— 间接事件:无 ——")
    return "\n".join(lines)
