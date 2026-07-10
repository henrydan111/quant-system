# SCRIPT_STATUS: ACTIVE — 卡片渲染器 v2.1(纯确定性,零 LLM/编排依赖;GPT REVISE 修复)
"""Card renderers shared by the analyst chain AND the read-only platform.

边界说明:本模块只依赖 pandas,不 import 任何 LLM/编排代码——平台进程可安全引用。

v2.1(GPT REVISE Blocker-4 + Major 修复):
- **固定语义行 ID**(注册表制,缺项不移位):基本面 F01-F17 按字段注册、序列 FS1-FS4、
  披露 FD1、业务 FB1-;量价 TA/TB/TC/TD/TE 按项目注册;消息 N00 全景 / ND 直接明细 /
  NDA 直接聚合 / NX01 缺席 / NI 间接明细 / NIA 间接聚合(动态节内按 重要性→新近→event_id
  确定性排序后编号)。
- 红旗缺席改**谓词**判定(类型+标题方向;修复"卡内有 董监高减持 却声明无减持")。
- 序列节:显示采样日期 + 真二阶(加速/减速由相邻差分计算,非单调误标)。
- NaN 估值行显式状态(亏损/未披露),不再静默消失。
- 间接明细行带事件龄+星标;聚合行按 通道×类型 分组并带龄距;同源(类型,来源)超2条合并。
- 市值 ≥1万亿 切换万亿显示。
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

#: 固定语义 ID 注册表(B4:缺项跳过不移位;新增字段必须先注册)
FUND_FIELD_ID = {f: f"F{i+1:02d}" for i, f in enumerate([
    "roe_waa", "grossprofit_margin", "netprofit_margin", "ocf_to_or",
    "or_yoy", "netprofit_yoy", "dt_netprofit_yoy", "basic_eps_yoy",
    "debt_to_assets", "current_ratio", "assets_turn",
    "pe_ttm", "pb", "ps_ttm", "dv_ratio", "total_mv", "turnover_rate"])}
SERIES_FIELD_ID = {"or_yoy": "FS1", "netprofit_yoy": "FS2",
                   "grossprofit_margin": "FS3", "roe_waa": "FS4"}
PV_ITEM_ID = {
    "均线排列": "TA01", "距52周高": "TA02", "距52周低": "TA03", "趋势阶段": "TA04",
    "本股收益5d": "TA05", "本股收益20d": "TA06", "RS_vs_300_20d": "TA07",
    "RS_vs_300_60d": "TA08", "RS_行业分位_60d": "TA09", "所属行业": "TA10",
    "申万L1成分等权5d": "TA11", "申万L1成分等权20d": "TA12",
    "连阳连阴": "TA13", "长上影5日": "TA14", "向上缺口20日": "TA15",
    "量价四象限": "TB01", "量比": "TB02", "换手分位250d": "TB03",
    "换手5d/20d比": "TB04", "波动分位": "TB05", "布林带宽分位": "TB06",
    "收盘位置5d": "TB07", "量价背离": "TB08",
    "获利盘": "TC01", "获利盘60d变化": "TC02", "现价距成本5分位": "TC03",
    "现价距成本50分位": "TC04", "现价距成本95分位": "TC05", "筹码集中度": "TC06",
    "融资余额20d变动": "TC07", "融资买入占比": "TC08", "北向持股比": "TC09",
    "北向20d变动": "TC10",
    "大单净流5d占成交额": "TD01", "大单净流20d占成交额": "TD02",
    "大单同向天数": "TD03", "大小单形态": "TD04", "净流强度": "TD05",
    "龙虎榜20d": "TD06",
    "涨停20d": "TE01", "连板高度": "TE02", "断板": "TE03", "炸板20d": "TE04",
    "跌停20d": "TE05", "涨停次日溢价均值": "TE06",
}

#: 字段呈现类型:pct1=已是百分数值(1 位小数);ratio2=比率(2 位小数);mv=市值(万→亿/万亿)
_FUND_FMT = {"roe_waa": "pct1", "grossprofit_margin": "pct1", "netprofit_margin": "pct1",
             "or_yoy": "pct1", "netprofit_yoy": "pct1", "dt_netprofit_yoy": "pct1",
             "basic_eps_yoy": "pct1", "debt_to_assets": "pct1", "turnover_rate": "pct1",
             "dv_ratio": "pct1",
             "ocf_to_or": "ratio2", "current_ratio": "ratio2", "assets_turn": "ratio2",
             "pe_ttm": "ratio2", "pb": "ratio2", "ps_ttm": "ratio2",
             "total_mv": "mv"}
#: NaN 显式状态(M6:静默消失=信息损失;NaN≠0)
_FUND_NAN_STATE = {"pe_ttm": "不适用(亏损或未披露)", "ps_ttm": "未披露",
                   "dv_ratio": "无分红或未披露"}


def _fmt_fund(field: str, v) -> str:
    if v is None or pd.isna(v):
        return _FUND_NAN_STATE.get(field, "缺失(不可等同于0)")
    v = float(v)
    kind = _FUND_FMT.get(field, "ratio2")
    if kind == "mv":
        yi = v / 1e4                    # 万 → 亿
        return f"{yi/1e4:.2f}万亿" if yi >= 1e4 else f"{yi:,.0f}亿"
    if field == "pe_ttm" and v < 0:
        return "亏损(PE无意义)"
    return f"{v:.1f}" if kind == "pct1" else f"{v:.2f}"


def _series_trend(vals: list[float]) -> str:
    """真二阶判定(M5):相邻差分;先判穿零,再判加速/减速。"""
    dedup = [v for i, v in enumerate(vals) if i == 0 or v != vals[i - 1]]
    if len(dedup) < 3:
        return ""
    d1, d0 = dedup[-1] - dedup[-2], dedup[-2] - dedup[-3]
    if dedup[-1] > 0 >= dedup[-2]:
        return "转正"
    if dedup[-1] < 0 <= dedup[-2]:
        return "转负"
    if d1 > 0 and d0 > 0:
        return "加速改善" if d1 > d0 else "持续改善"
    if d1 < 0 and d0 < 0:
        return "加速恶化" if d1 < d0 else "持续恶化"
    return "方向反复"


def render_fund_card(facts: pd.DataFrame, biz_text: str | None = None,
                     series: pd.DataFrame | None = None,
                     disclosure: str | None = None) -> str:
    lines = ["【基本面三锚定事实表】(行ID|字段: 值|行业分位(同业家数)|行业中值/90分位|"
             "自身10年分位;⚑=代码判定焦点行:三锚定背离>50pp或极端分位)"]
    rows = list(facts.iterrows())
    div = []
    for i, (_, r) in enumerate(rows):
        ip, hp = r["industry_pctl"], r["hist_pctl"]
        score = 0.0
        if pd.notna(ip) and pd.notna(hp) and abs(ip - hp) > 0.5:
            score = max(score, abs(ip - hp))
        if pd.notna(ip) and abs(ip - 0.5) > 0.4:
            score = max(score, (abs(ip - 0.5) - 0.4) * 2)
        div.append((score, i))
    flagged = {i for s, i in sorted(div, reverse=True)[:3] if s > 0}
    for i, (_, r) in enumerate(rows):
        f = r["field"]
        fid = FUND_FIELD_ID.get(f)
        if fid is None:                    # 未注册字段不可被引用(fail-closed)
            continue
        ip = "" if pd.isna(r["industry_pctl"]) else \
            f"行业分位{r['industry_pctl']:.0%}({r['industry_n']}家)"
        bench = ""
        if "industry_median" in r.index and pd.notna(r.get("industry_median")):
            bench = (f"中值{_fmt_fund(f, r['industry_median'])}"
                     f"/90分位{_fmt_fund(f, r.get('industry_p90'))}")
        hp = "" if pd.isna(r["hist_pctl"]) else f"10年分位{r['hist_pctl']:.0%}"
        flag = "⚑" if i in flagged else ""
        lines.append(f"- [{fid}]{flag}{FIELD_CN.get(f, f)}: "
                     f"{_fmt_fund(f, r['value'])}|{ip}|{bench}|{hp}")
    if series is not None and len(series):
        lines.append("◆ 关键指标近8季采样(vintage口径:各点=该采样时点已知值,旧→新;"
                     "括号内为采样日;趋势=相邻差分二阶判定)")
        for f in series["field"].unique():
            fid = SERIES_FIELD_ID.get(f)
            if fid is None:
                continue
            s = series[series["field"] == f].sort_values("seq")
            vals = [float(v) for v in s["value"]]
            dates = [str(d)[:6] for d in s["sample_date"]]
            arrow = " → ".join(f"{v:.1f}({d})" for v, d in zip(vals, dates))
            t = _series_trend(vals)
            lines.append(f"- [{fid}]{FIELD_CN.get(f, f)}: {arrow}"
                         + (f"【{t}】" if t else ""))
    if disclosure:
        lines.append(f"- [FD1]披露动态: {disclosure}"
                     "(本行只可支撑 earnings_inflection)")
    if biz_text:
        # v1.5-A 业务构成节:行加 FB 序号(节内位置编号,节内容有界)
        bl = str(biz_text).splitlines()
        out_b, k = [], 0
        for ln in bl:
            if ln.strip().startswith("- "):
                k += 1
                out_b.append(f"- [FB{k}]{ln.strip()[2:]}")
            else:
                out_b.append(ln)
        lines.extend(out_b)
    return "\n".join(lines)


#: pv 项目呈现类型
_PV_PCT_SIGNED = {"距52周高", "距52周低", "趋势阶段", "RS_vs_300_20d", "RS_vs_300_60d",
                  "本股收益5d", "本股收益20d", "申万L1成分等权5d", "申万L1成分等权20d",
                  "现价距成本5分位", "现价距成本50分位", "现价距成本95分位",
                  "融资余额20d变动", "大单净流5d占成交额", "大单净流20d占成交额",
                  "净流强度", "涨停次日溢价均值", "融资买入占比"}
_PV_PCT_PLAIN = {"波动分位", "布林带宽分位", "RS_行业分位_60d"}
_PV_RATIO2 = {"量比", "换手5d/20d比", "筹码集中度", "收盘位置5d"}
_PV_UNIT = {"换手分位250d": "%", "获利盘": "%", "获利盘60d变化": "pp", "北向持股比": "%",
            "北向20d变动": "pp"}


def _fmt_pv(item: str, v) -> str:
    if v is None or pd.isna(v):
        return ""
    v = float(v)
    if item in _PV_RATIO2:
        return f"{v:.2f}"
    if item in _PV_PCT_SIGNED:
        return f"{v * 100:+.1f}%"
    if item in _PV_PCT_PLAIN:
        return f"{v * 100:.1f}%"
    u = _PV_UNIT.get(item, "")
    return f"{v:.1f}{u}" if v % 1 else f"{v:g}{u}"


def render_pv_card(pv: pd.DataFrame) -> str:
    lines = ["【量价情报包】(行ID|项目: 值「状态」[分位];全部由代码判定;"
             "⚑=极端分位焦点行;「截至D-1」=次晨披露数据滞后一日)"]
    rows = list(pv.iterrows())
    ext = sorted([(abs(float(r["pctl"]) - 0.5), i) for i, (_, r) in enumerate(rows)
                  if r["pctl"] is not None and pd.notna(r["pctl"])
                  and (float(r["pctl"]) >= 0.9 or float(r["pctl"]) <= 0.1)],
                 reverse=True)
    flagged = {i for _, i in ext[:3]}
    for card in "ABCDE":
        idxs = [i for i, (_, r) in enumerate(rows) if r["subcard"] == card]
        if not idxs:
            continue
        lines.append(f"◆ {SUBCARD_CN[card]}")
        for i in idxs:
            r = rows[i][1]
            tid = PV_ITEM_ID.get(r["item"])
            if tid is None:                # 未注册项目不可被引用(fail-closed)
                continue
            v = _fmt_pv(r["item"], r["value"])
            s = f"「{r['state']}」" if r["state"] else ""
            p = "" if r["pctl"] is None or pd.isna(r["pctl"]) else f"[分位{r['pctl']:.0%}]"
            flag = "⚑" if i in flagged else ""
            body = f"{v}{s}{p}" if v or s or p else ""
            lines.append(f"- [{tid}]{flag}{r['item']}: {body}")
    return "\n".join(lines)


_CHANNEL_CN = {"concept": "概念", "industry": "行业", "relation": "关联"}
#: 红旗类别谓词(M3:类型精确匹配会漏"董监高增减持|减持方向"——改 类型+标题 谓词)
_RED_FLAG_PREDICATES = {
    "减持": lambda t, title: t == "减持" or (t == "董监高增减持" and "减持" in title),
    "质押": lambda t, title: t == "质押" or "质押" in title,
    "监管处分": lambda t, title: t == "监管",
    "诉讼": lambda t, title: t == "诉讼/仲裁",
}


def disclosure_status(r_direct: pd.DataFrame, day: str) -> str:
    """披露动态行(审计 §6.4 B 方案):只给类型+极性+事件龄,幅度留给消息席。"""
    fc = r_direct[r_direct["event_type"].isin(("业绩预告", "业绩快报"))]
    if fc.empty:
        return "检索窗口内无业绩预告/快报"
    fc = fc.sort_values("visible_at") if "visible_at" in fc.columns else fc
    r = fc.iloc[-1]
    age = _age_str(day, r["visible_at"]) if "visible_at" in fc.columns else ""
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


def _t70(title) -> str:
    """canonical 标题截断(复审#2 minor):所有证据行统一 70 字,保证整行 <160
    与接地上限兼容;event_id 哈希用全文,截断只在显示层。"""
    return str(title)[:70]


def _det_sort(df: pd.DataFrame, has_vis: bool) -> pd.DataFrame:
    """确定性排序:重要性 desc → 新近 desc → event_id asc(GPT minor:动态编号前的平局裁决)。"""
    cols, asc = ["importance"], [False]
    if has_vis:
        cols.append("visible_at"); asc.append(False)
    if "event_id" in df.columns:
        cols.append("event_id"); asc.append(True)
    return df.sort_values(cols, ascending=asc, kind="mergesort")


def render_news_card(retr: pd.DataFrame, day: str | None = None) -> str:
    day = day or (str(retr["trade_date"].iloc[0]) if len(retr) else "")
    has_vis = "visible_at" in retr.columns
    has_src = "source" in retr.columns
    lines = ["【检索装配单】(行ID|[事件龄|重要性]类型|标题|极性;间接事件标通道与相关度;"
             "聚合行=同 通道×类型 计数压缩)"]
    d = retr[retr["channel"] == "direct"]
    ind = retr[retr["channel"].isin(("concept", "industry", "relation"))]
    tc = d["event_type"].value_counts()
    top_types = "/".join(f"{t}{c}" for t, c in tc.head(3).items())
    lines.append(f"- [N00]检索窗口全景: 直接事件 {len(d)} 条({top_types or '无'}),"
                 f"间接事件 {len(ind)} 条(检索返回集)")
    # ---- 直接节:确定性排序;同源(类型,来源)≤2 条,溢出并入聚合 ----
    if len(d):
        ds = _det_sort(d, has_vis)
        shown, over_rows = [], []
        src_cnt: dict[tuple, int] = {}
        for _, r in ds.iterrows():
            key = (r["event_type"], r.get("source") if has_src else None)
            if src_cnt.get(key, 0) < 2 and len(shown) < 12:
                shown.append(r)
                src_cnt[key] = src_cnt.get(key, 0) + 1
            else:
                over_rows.append(r)
        lines.append(f"—— 直接事件(本股,{len(d)} 条"
                     f"{'' if not over_rows else ',超额/同源已聚合'})——")
        for k, r in enumerate(shown, 1):
            age = _age_str(day, r["visible_at"]) if has_vis else "—"
            lines.append(f"- [ND{k:02d}][{age}|{_stars(r.get('importance'))}]"
                         f"{r['event_type']}|{_t70(r['title'])}|{r['direction']}")
        if over_rows:
            og = pd.DataFrame(over_rows)
            for k, ((t,), grp) in enumerate(og.groupby(["event_type"]), 1):
                dirs = "/".join(f"{a}{b}" for a, b in grp["direction"].value_counts().items())
                ages = ""
                if has_vis:
                    a_new = _age_str(day, grp["visible_at"].max())
                    a_old = _age_str(day, grp["visible_at"].min())
                    ages = f"|{a_new}~{a_old}"
                lines.append(f"- [NDA{k}][直接聚合{ages}]{t}: 另有{len(grp)}条({dirs})")
    else:
        lines.append("—— 直接事件:无 ——")
    # ---- 红旗缺席声明(谓词判定,M3) ----
    hits = set()
    for _, r in d.iterrows():
        for cat, pred in _RED_FLAG_PREDICATES.items():
            if pred(str(r["event_type"]), str(r["title"])):
                hits.add(cat)
    absent = [c for c in _RED_FLAG_PREDICATES if c not in hits]
    if absent:
        lines.append(f"- [NX01]检索窗口内无以下类别的直接事件(按类型+标题谓词判定): "
                     f"{'/'.join(absent)}")
    # ---- 间接节:通道×类型 配额≤3 + 聚合(带龄距/星标) ----
    if len(ind):
        srt = ind.sort_values(["relevance"] + (["event_id"] if "event_id" in ind.columns else []),
                              ascending=[False] + ([True] if "event_id" in ind.columns else []),
                              kind="mergesort")
        picked, over = [], {}
        cnt: dict[tuple, int] = {}
        for _, r in srt.iterrows():
            key = (r["channel"], r["event_type"])
            if cnt.get(key, 0) < 3 and len(picked) < 15:
                picked.append(r)
                cnt[key] = cnt.get(key, 0) + 1
            else:
                over.setdefault(key, []).append(r)
        lines.append(f"—— 间接事件(概念/行业同伴,返回集 {len(ind)} 条,"
                     f"明细每通道×类型≤3,余为聚合)——")
        for k, r in enumerate(picked, 1):
            age = _age_str(day, r["visible_at"]) if has_vis else "—"
            lines.append(f"- [NI{k:02d}][{_CHANNEL_CN.get(r['channel'], r['channel'])}"
                         f"|{age}|{_stars(r.get('importance'))}]{r['event_type']}"
                         f"|{_t70(r['title'])}|{r['direction']}|相关度{r['relevance']:.2f}")
        for k, ((ch, t), rows_t) in enumerate(sorted(over.items(),
                                                     key=lambda kv: -len(kv[1])), 1):
            g = pd.DataFrame(rows_t)
            dirs = "/".join(f"{a}{b}" for a, b in g["direction"].value_counts().items())
            ages = ""
            if has_vis:
                ages = f"|{_age_str(day, g['visible_at'].max())}~{_age_str(day, g['visible_at'].min())}"
            lines.append(f"- [NIA{k}][{_CHANNEL_CN.get(ch, ch)}聚合{ages}]{t}: "
                         f"返回集内另有{len(g)}条({dirs})——聚合行属间接证据,封顶3分")
    else:
        lines.append("—— 间接事件:无 ——")
    return "\n".join(lines)
