# SCRIPT_STATUS: ACTIVE — 量价情报包 v0:五子卡(第五篇设计),全确定性零 LLM
"""Price-volume intelligence pack (PRICE_VOLUME_INTELLIGENCE_v1.md).

每股每决策日输出长表行 (ts_code, trade_date, subcard, item, value, state, pctl):
  A 趋势形态  B 量能结构  C 筹码持仓  D 主力行为  E 涨停语言
LLM 只读渲染后的 状态标签+分位 三元组;一切形态判定在此代码层。
数据门:provider bins(全 approved)+ industry_as_of(RS 行业分位)。
股东户数(holder_number ledger)v0 缺席 —— 等 pit_event_feed 门(任务4),诚实标注。

用法: venv/Scripts/python.exe workspace/research/ai_research_dept/engine/pv_pack.py
"""
from __future__ import annotations

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
from workspace.research.ai_research_dept.engine.fact_table import decision_days  # noqa: E402
from data_infra.provider_metadata import (  # noqa: E402
    build_industry_series_asof, tushare_to_qlib_canonical,
)

logger = logging.getLogger("pv_pack")

FIELDS = [
    "$open", "$close", "$high", "$low", "$vol", "$amount", "$pre_close",
    "$adj_factor", "$up_limit", "$down_limit", "$turnover_rate", "$volume_ratio",
    "$buy_sm_amount", "$sell_sm_amount", "$buy_lg_amount", "$sell_lg_amount",
    "$buy_elg_amount", "$sell_elg_amount",
    "$rzye", "$rzmre", "$ratio",
    "$cyq_perf__cost_5pct", "$cyq_perf__cost_15pct", "$cyq_perf__cost_50pct",
    "$cyq_perf__cost_85pct", "$cyq_perf__cost_95pct", "$cyq_perf__winner_rate",
    "$top_list__amount",
]
EPS = 1e-6


def pctl_last(s: pd.Series, min_n: int = 30) -> float:
    s = s.dropna()
    if len(s) < min_n:
        return float("nan")
    return float((s <= s.iloc[-1]).mean())


def streak(bools: pd.Series) -> int:
    """尾部连续 True 天数。"""
    n = 0
    for v in bools.iloc[::-1]:
        if bool(v):
            n += 1
        else:
            break
    return n


def rows_for_stock(code: str, g: pd.DataFrame, day: str,
                   ind_rs_pctl: float, bench_ret20: float,
                   bench_ret60: float) -> list[dict]:
    """g = 该股全部历史(至 day),index=Timestamp 升序。"""
    out = []
    add = lambda card, item, value, state="", pctl=float("nan"): out.append(
        {"ts_code": code, "trade_date": day, "subcard": card, "item": item,
         "value": None if value is None or (isinstance(value, float) and np.isnan(value))
         else round(float(value), 4),
         "state": state, "pctl": None if np.isnan(pctl) else round(float(pctl), 3)})

    adj = g["close"] * g["adj_factor"]
    adj_o, adj_h, adj_l = (g[c] * g["adj_factor"] for c in ("open", "high", "low"))
    c_, cur = float(adj.iloc[-1]), g.iloc[-1]

    # ---------- A 趋势形态 ----------
    mas = {n: adj.rolling(n).mean() for n in (5, 10, 20, 60, 120, 250)}
    m5, m20, m60 = (float(mas[n].iloc[-1]) for n in (5, 20, 60))
    if c_ > m5 > m20 > m60:
        arr = "多头排列"
        arr_streak = streak((adj > mas[5]) & (mas[5] > mas[20]) & (mas[20] > mas[60]))
    elif c_ < m5 < m20 < m60:
        arr = "空头排列"
        arr_streak = streak((adj < mas[5]) & (mas[5] < mas[20]) & (mas[20] < mas[60]))
    else:
        arr, arr_streak = "缠绕", 0
    add("A", "均线排列", arr_streak, arr)
    hi52, lo52 = float(adj.iloc[-250:].max()), float(adj.iloc[-250:].min())
    add("A", "距52周高", c_ / hi52 - 1, "创250日新高" if c_ >= hi52 - EPS else "")
    add("A", "距52周低", c_ / lo52 - 1, "创250日新低" if c_ <= lo52 + EPS else "")
    ret20 = float(adj.iloc[-1] / adj.iloc[-21] - 1) if len(adj) > 21 else float("nan")
    ret60 = float(adj.iloc[-1] / adj.iloc[-61] - 1) if len(adj) > 61 else float("nan")
    slope20 = float(mas[20].iloc[-1] / mas[20].iloc[-6] - 1) if len(adj) > 26 else float("nan")
    stage = ("上升" if c_ > m60 and slope20 > 0.005 else
             "下降" if c_ < m60 and slope20 < -0.005 else "盘整")
    dd60 = float(c_ / adj.iloc[-60:].max() - 1)
    add("A", "趋势阶段", dd60, f"{stage}|60日回撤{dd60:.1%}")
    add("A", "RS_vs_300_20d", ret20 - bench_ret20)
    add("A", "RS_vs_300_60d", ret60 - bench_ret60)
    add("A", "RS_行业分位_60d", ind_rs_pctl, "", ind_rs_pctl)
    body = (adj - adj_o).abs()
    up_shadow, dn_shadow = adj_h - np.maximum(adj, adj_o), np.minimum(adj, adj_o) - adj_l
    add("A", "连阳连阴", streak(adj.diff() > 0) or -streak(adj.diff() < 0))
    add("A", "长上影5日", int(((up_shadow > 2 * body) & (body > 0)).iloc[-5:].sum()))
    gap_up = (adj_l > adj_h.shift(1)).iloc[-20:]
    add("A", "向上缺口20日", int(gap_up.sum()))

    # ---------- B 量能结构 ----------
    vma20 = g["vol"].rolling(20).mean()
    up_day = cur["close"] > cur["pre_close"]
    heavy = cur["vol"] > 1.5 * vma20.iloc[-1]
    quad = ("放量涨" if up_day and heavy else "缩量涨" if up_day else
            "放量跌" if heavy else "缩量跌")
    quad_series = pd.Series(
        np.where((g["close"] > g["pre_close"]) & (g["vol"] > 1.5 * vma20), "放量涨",
        np.where(g["close"] > g["pre_close"], "缩量涨",
        np.where(g["vol"] > 1.5 * vma20, "放量跌", "缩量跌"))), index=g.index)
    add("B", "量价四象限", streak(quad_series == quad), quad)
    add("B", "量比", cur["volume_ratio"])
    add("B", "换手分位250d", cur["turnover_rate"], "", pctl_last(g["turnover_rate"].iloc[-250:]))
    rv = adj.pct_change().rolling(20).std() * np.sqrt(252)
    add("B", "波动分位", rv.iloc[-1], "", pctl_last(rv.iloc[-250:]))
    bb_w = (adj.rolling(20).std() * 4) / adj.rolling(20).mean()
    bw_p = pctl_last(bb_w.iloc[-250:])
    add("B", "布林带宽分位", bb_w.iloc[-1], "squeeze" if bw_p < 0.10 else "", bw_p)
    rng = (g["high"] - g["low"]).replace(0, np.nan)
    cpos = ((g["close"] - g["low"]) / rng).rolling(5).mean()
    add("B", "收盘位置5d", cpos.iloc[-1],
        "持续收高" if cpos.iloc[-1] > 0.7 else "持续收低" if cpos.iloc[-1] < 0.3 else "")
    px_newhigh20 = c_ >= adj.iloc[-20:].max() - EPS
    vol_fade = g["vol"].rolling(5).mean().iloc[-1] < vma20.iloc[-1]
    add("B", "量价背离", int(px_newhigh20 and vol_fade),
        "价新高量萎缩" if (px_newhigh20 and vol_fade) else "")

    # ---------- C 筹码持仓 ----------
    wr = g["cyq_perf__winner_rate"]
    if pd.notna(wr.iloc[-1]):
        state = ("高位高获利" if wr.iloc[-1] > 90 and pctl_last(adj.iloc[-250:]) > 0.8 else
                 "低位低获利" if wr.iloc[-1] < 10 else "")
        add("C", "获利盘", wr.iloc[-1], state, pctl_last(wr.iloc[-250:]))
        add("C", "获利盘60d变化", wr.iloc[-1] - wr.iloc[-60] if len(wr) > 60 else float("nan"))
    raw_c = float(g["close"].iloc[-1])
    for q in ("5", "50", "95"):
        cost = g[f"cyq_perf__cost_{q}pct"].iloc[-1]
        if pd.notna(cost) and cost > 0:
            add("C", f"现价距成本{q}分位", raw_c / float(cost) - 1)
    c5, c50, c95 = (g[f"cyq_perf__cost_{q}pct"].iloc[-1] for q in ("5", "50", "95"))
    if all(pd.notna(x) and x > 0 for x in (c5, c50, c95)):
        conc = (c95 - c5) / c50
        conc_series = ((g["cyq_perf__cost_95pct"] - g["cyq_perf__cost_5pct"])
                       / g["cyq_perf__cost_50pct"])
        trend = "收敛" if conc < conc_series.iloc[-20] else "发散"
        add("C", "筹码集中度", conc, trend)
    if pd.notna(cur["rzye"]):
        add("C", "融资余额20d变动", g["rzye"].iloc[-1] / g["rzye"].iloc[-20] - 1
            if len(g) > 20 and g["rzye"].iloc[-20] > 0 else float("nan"),
            "", pctl_last(g["rzye"].iloc[-250:]))
        rz_ratio = g["rzmre"] / g["amount"].replace(0, np.nan) / 10  # 万元 vs 千元 尺度对齐由分位吸收
        add("C", "融资买入占比分位", rz_ratio.iloc[-1], "", pctl_last(rz_ratio.iloc[-250:]))
    if pd.notna(cur["ratio"]):
        add("C", "北向持股比", cur["ratio"],
            "", float("nan"))
        add("C", "北向20d变动", g["ratio"].iloc[-1] - g["ratio"].iloc[-20]
            if len(g) > 20 else float("nan"))

    # ---------- D 主力行为 ----------
    net_big = (g["buy_lg_amount"].fillna(0) + g["buy_elg_amount"].fillna(0)
               - g["sell_lg_amount"].fillna(0) - g["sell_elg_amount"].fillna(0))
    net_sm = g["buy_sm_amount"].fillna(0) - g["sell_sm_amount"].fillna(0)
    add("D", "大单净流5d", net_big.iloc[-5:].sum())
    add("D", "大单净流20d", net_big.iloc[-20:].sum())
    add("D", "大单同向天数", streak(net_big > 0) or -streak(net_big < 0))
    shape = ("吸筹形态" if net_big.iloc[-5:].sum() > 0 and net_sm.iloc[-5:].sum() < 0 else
             "派发形态" if net_big.iloc[-5:].sum() < 0 and net_sm.iloc[-5:].sum() > 0 else "同向")
    add("D", "大小单形态", 0, shape)
    strength = net_big / g["amount"].replace(0, np.nan) / 10
    add("D", "净流强度分位", strength.iloc[-1], "", pctl_last(strength.iloc[-250:]))
    add("D", "龙虎榜20d", int(g["top_list__amount"].iloc[-20:].notna().sum()))

    # ---------- E 涨停语言 ----------
    lim_up = (g["close"] >= g["up_limit"] - EPS) & g["up_limit"].notna()
    lim_dn = (g["close"] <= g["down_limit"] + EPS) & g["down_limit"].notna()
    zha = (g["high"] >= g["up_limit"] - EPS) & (~lim_up) & g["up_limit"].notna()
    add("E", "涨停20d", int(lim_up.iloc[-20:].sum()))
    add("E", "连板高度", streak(lim_up))
    add("E", "断板", int(len(g) > 1 and lim_up.iloc[-2] and not lim_up.iloc[-1]),
        "断板" if (len(g) > 1 and lim_up.iloc[-2] and not lim_up.iloc[-1]) else "")
    add("E", "炸板20d", int(zha.iloc[-20:].sum()))
    add("E", "跌停20d", int(lim_dn.iloc[-20:].sum()))
    lu_idx = np.where(lim_up.iloc[:-1].values)[0]
    if len(lu_idx):
        prem = []
        for i in lu_idx[-10:]:
            if i + 1 < len(g):
                prem.append(float(g["open"].iloc[i + 1] / g["close"].iloc[i] - 1))
        if prem:
            add("E", "涨停次日溢价均值", float(np.mean(prem)), f"样本{len(prem)}次")
    return out


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=str(C.QLIB_DIR), region=REG_CN, kernels=1)

    days = decision_days(C.PILOT_POOL_MONTH, C.PILOT_MONTH_END)
    pool_df = pd.read_parquet(C.POOL_DIR / f"broker_recommend_{C.PILOT_POOL_MONTH}.parquet")
    pool = sorted(set(pool_df["ts_code"]))
    t0 = time.time()

    avail = {i.upper(): i for i in D.list_instruments(
        D.instruments("all"), start_time=days[0], end_time=days[-1], as_list=True)}
    qmap = {c: avail[tushare_to_qlib_canonical(c)] for c in pool
            if tushare_to_qlib_canonical(c) in avail}
    start = (pd.Timestamp(days[0]) - pd.Timedelta(days=420)).strftime("%Y-%m-%d")
    px = D.features(list(qmap.values()), FIELDS, start_time=start,
                    end_time=days[-1], freq="day")
    px.columns = [c.lstrip("$") for c in FIELDS]
    logger.info("pool bins loaded: %d rows %.0fs", len(px), time.time() - t0)

    # 全市场 60d 收益(行业内 RS 分位)+ 基准
    mkt = D.features(list(avail.values()), ["$close", "$adj_factor"],
                     start_time=(pd.Timestamp(days[0]) - pd.Timedelta(days=110)
                                 ).strftime("%Y-%m-%d"),
                     end_time=days[-1], freq="day")
    mkt_adj = (mkt["$close"] * mkt["$adj_factor"]).unstack(level=0)
    bench = pd.read_parquet(C.PROJECT_ROOT / "data" / "market" / "index"
                            / "index_000300.SH.parquet")
    bench["trade_date"] = bench["trade_date"].astype(str)
    bench = bench.set_index("trade_date")["close"].sort_index()
    logger.info("market RS panel loaded %.0fs", time.time() - t0)

    def to_ts(qcode: str) -> str:
        root, exch = str(qcode).upper().split("_")
        return f"{root}.{exch}"

    all_rows = []
    back = {v: k for k, v in qmap.items()}
    for day in days:
        ts_day = pd.Timestamp(day)
        # 行业 RS 分位(60d 收益在申万 L1 内的排名)
        window = mkt_adj.loc[:ts_day]
        ret60_all = (window.iloc[-1] / window.iloc[-61] - 1) if len(window) > 61 else None
        ind_pctl_map = {}
        if ret60_all is not None:
            r = ret60_all.dropna()
            r.index = [to_ts(str(i)) for i in r.index]
            idx = pd.MultiIndex.from_product([[ts_day], r.index])
            inds = build_industry_series_asof(idx, "L1").droplevel(0)
            df_rs = pd.DataFrame({"ret": r, "ind": inds}).dropna()
            df_rs["p"] = df_rs.groupby("ind")["ret"].rank(pct=True)
            ind_pctl_map = df_rs["p"].to_dict()
        b20 = float(bench.loc[:day].iloc[-1] / bench.loc[:day].iloc[-21] - 1)
        b60 = float(bench.loc[:day].iloc[-1] / bench.loc[:day].iloc[-61] - 1)
        for code, qc in qmap.items():
            try:
                g = px.xs(qc, level=0)
                g = g[g.index <= ts_day]
            except KeyError:
                continue
            if len(g) < 80 or pd.isna(g["close"].iloc[-1]):
                continue
            all_rows.extend(rows_for_stock(
                code, g, day, ind_pctl_map.get(code, float("nan")), b20, b60))
        logger.info("[%s] pv rows so far: %d", day, len(all_rows))

    pv = pd.DataFrame(all_rows)
    pv["pv_pack_version"] = "pv_v0.1"
    pv["evidence_class"] = C.EVIDENCE_CLASS_REPLAY
    C.PV_DIR.mkdir(parents=True, exist_ok=True)
    out = C.PV_DIR / f"pv_pack_{C.PILOT_POOL_MONTH}.parquet"
    pv.to_parquet(out, index=False)
    summary = {
        "rows": len(pv), "names": pv.ts_code.nunique(), "days": len(days),
        "items_per_name_day": round(len(pv) / max(1, pv.ts_code.nunique() * len(days)), 1),
        "elapsed_s": round(time.time() - t0, 1),
        "evidence_class": C.EVIDENCE_CLASS_REPLAY,
    }
    (C.PV_DIR / f"summary_{C.PILOT_POOL_MONTH}.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("pv pack -> %s | %s", out, summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
