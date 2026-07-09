# SCRIPT_STATUS: ACTIVE — FactTable v0:唯一事实表(三锚定),全确定性零 LLM
"""每股每决策日的唯一事实表(G2 糟粕的对策:数字只算一次,全系统只此一份)。

每条事实 = (ts_code, trade_date, field, value, industry_pctl, industry_n, pctl_scope,
hist_pctl, source) —— 三锚定(蚂蚁 P1):值 + 行业分位 + 自身10年时序分位。

数据门(全 sanctioned):
- 基本面 11 字段:pit_research_loader.load_pit_signal_panel(lag-1,注册表校验 fail-closed)
- 市场 4 字段:provider daily_basic bins(D.features;workspace 研究先例=observatory)
- 行业:provider_metadata.industry_as_of(申万 PIT,区间形式)
横截面分位在全市场算,行业分位在申万 L1 内算(样本 < INDUSTRY_MIN_N 回退全市场,pctl_scope 标注)。
LLM 永不读本模块的原始序列——只读渲染后的三元组。

用法:
  venv/Scripts/python.exe -m workspace.research.ai_research_dept.engine.fact_table  # 202501 试点
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
from data_infra.pit_research_loader import load_pit_signal_panel  # noqa: E402
from data_infra.provider_metadata import (  # noqa: E402
    build_industry_series_asof, tushare_to_qlib_canonical,
)

logger = logging.getLogger("fact_table")


# ------------------------------------------------------------------ helpers

def decision_days(month: str, month_end: str) -> list[str]:
    from data_infra.golden_stock_universe import load_golden_stock_events
    events = load_golden_stock_events()
    cyc = events.loc[events["month"] == month]
    activation = pd.Timestamp(cyc["activation_date"].iloc[0]).strftime("%Y%m%d")
    cal = pd.read_parquet(C.TRADE_CAL)
    opens = cal.loc[cal["is_open"] == 1, "cal_date"].astype(str)
    return sorted(opens[(opens >= activation) & (opens <= month_end)])


def quarterly_dates(end_day: str, years: int) -> list[str]:
    """~4/年的历史采样日(开盘日),供自身时序分位。"""
    cal = pd.read_parquet(C.TRADE_CAL)
    opens = pd.to_datetime(cal.loc[cal["is_open"] == 1, "cal_date"].astype(str))
    end = pd.Timestamp(end_day)
    start = end - pd.DateOffset(years=years)
    qs = pd.date_range(start, end, freq="QE")
    out = []
    for q in qs:
        prior = opens[opens <= q]
        if len(prior):
            out.append(prior.max().strftime("%Y%m%d"))
    return sorted(set(out))


def _pctl_of_last(series: pd.Series) -> float:
    """当前值在自身历史(含当前)中的分位;<8 个观测返回 NaN。"""
    s = series.dropna()
    if len(s) < 8:
        return float("nan")
    return float((s <= s.iloc[-1]).mean())


def _grouped_pctl(day_values: pd.Series, industries: pd.Series,
                  min_n: int) -> pd.DataFrame:
    """行业内分位;样本薄回退全市场。返回 (pctl, n, scope)。"""
    df = pd.DataFrame({"v": day_values, "ind": industries})
    df["mkt_pctl"] = df["v"].rank(pct=True)
    grp = df.groupby("ind")["v"]
    df["ind_pctl"] = grp.rank(pct=True)
    df["ind_n"] = grp.transform("count")
    thin = df["ind_n"].fillna(0) < min_n
    df["pctl"] = np.where(thin, df["mkt_pctl"], df["ind_pctl"])
    df["scope"] = np.where(thin, "market_fallback", "industry_L1")
    df.loc[df["ind"].isna(), "scope"] = "market_fallback"
    return df[["pctl", "ind_n", "scope"]]


# ------------------------------------------------------------------ builders

def build_fund_facts(days: list[str], pool: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """基本面 11 字段:全市场面板(行业分位用)+ 池内 10 年季度史(时序分位用)。

    v0.2 同时产出 vintage 8 季序列(审计 F3 退化口径):每点=该采样时点 loader 已知值
    (lag-1),末点=D 日当前值——全序列同为 vintage 定义,内部一致;卡内显式标注。
    """
    t0 = time.time()
    panels = load_pit_signal_panel(C.FUND_FIELDS, days)          # 全市场
    hist_days = quarterly_dates(days[0], C.HIST_YEARS)
    hist = load_pit_signal_panel(C.FUND_FIELDS, hist_days, instruments=pool)
    logger.info("fund panels loaded (%d fields × %d days + %d hist dates) %.0fs",
                len(C.FUND_FIELDS), len(days), len(hist_days), time.time() - t0)

    series_rows = []
    for f in C.SERIES_FIELDS:
        key = f"${f}" if f"${f}" in panels else f
        hkey = f"${f}" if f"${f}" in hist else f
        hdf = hist[hkey]
        for day in days:
            samples = hdf[hdf.index <= day]
            cur_vals = panels[key].loc[day]
            for code in pool:
                if code not in hdf.columns:
                    continue
                s = samples[code].dropna().iloc[-(C.SERIES_POINTS - 1):]
                pts = list(zip(s.index, s.values))
                cur = cur_vals.get(code)
                if cur is not None and pd.notna(cur):
                    pts.append((day, float(cur)))
                for seq, (d, v) in enumerate(pts):
                    series_rows.append({
                        "ts_code": code, "trade_date": day, "field": f,
                        "seq": seq, "sample_date": str(d), "value": float(v),
                    })

    rows = []
    for day in days:
        # 行业归属(PIT as-of;向量化)
        any_panel = panels[next(iter(panels))]
        codes = any_panel.columns
        idx = pd.MultiIndex.from_product([[pd.Timestamp(day)], codes])
        industries = build_industry_series_asof(idx, "L1").droplevel(0)
        for f in C.FUND_FIELDS:
            key = f"${f}" if f"${f}" in panels else f
            vals = panels[key].loc[day]
            anchors = _grouped_pctl(vals, industries, C.INDUSTRY_MIN_N)
            hkey = f"${f}" if f"${f}" in hist else f
            for code in pool:
                v = vals.get(code)
                if v is None or pd.isna(v):
                    continue
                hp = float("nan")
                if code in hist[hkey].columns:
                    hseries = pd.concat([hist[hkey][code],
                                         pd.Series([v], index=[day])])
                    hp = _pctl_of_last(hseries)
                rows.append({
                    "ts_code": code, "trade_date": day, "field": f,
                    "value": float(v),
                    "industry_pctl": float(anchors.loc[code, "pctl"]),
                    "industry_n": int(anchors.loc[code, "ind_n"])
                    if pd.notna(anchors.loc[code, "ind_n"]) else 0,
                    "pctl_scope": anchors.loc[code, "scope"],
                    "hist_pctl": hp, "source": "pit_research_loader/indicators",
                })
    return pd.DataFrame(rows), pd.DataFrame(series_rows)


def build_mkt_facts(days: list[str], pool: list[str]) -> pd.DataFrame:
    """市场 4 字段:全市场当日横截面 + 池内 10 年日频史。"""
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=str(C.QLIB_DIR), region=REG_CN, kernels=1)

    t0 = time.time()
    start_hist = (pd.Timestamp(days[0]) - pd.DateOffset(years=C.HIST_YEARS)
                  ).strftime("%Y-%m-%d")
    avail = {i.upper(): i for i in D.list_instruments(
        D.instruments("all"), start_time=days[0], end_time=days[-1], as_list=True)}
    all_codes = list(avail.values())
    # 当日横截面(16 天窗)
    cross = D.features(all_codes, C.MKT_FIELDS,
                       start_time=days[0], end_time=days[-1], freq="day")
    # 池内 10 年史
    pool_q = [avail[tushare_to_qlib_canonical(c)] for c in pool
              if tushare_to_qlib_canonical(c) in avail]
    hist = D.features(pool_q, C.MKT_FIELDS,
                      start_time=start_hist, end_time=days[-1], freq="day")
    logger.info("mkt features loaded (%d instruments cross, %d pool hist) %.0fs",
                len(all_codes), len(pool_q), time.time() - t0)

    def to_ts(qcode: str) -> str:
        root, exch = qcode.upper().split("_")
        return f"{root}.{exch}"

    rows = []
    for day in days:
        ts_day = pd.Timestamp(day)
        try:
            day_slice = cross.xs(ts_day, level=1)
        except KeyError:
            continue
        day_slice.index = [to_ts(str(i)) for i in day_slice.index]
        idx = pd.MultiIndex.from_product([[ts_day], day_slice.index])
        industries = build_industry_series_asof(idx, "L1").droplevel(0)
        for f in C.MKT_FIELDS:
            vals = day_slice[f]
            anchors = _grouped_pctl(vals, industries, C.INDUSTRY_MIN_N)
            for code in pool:
                if code not in vals.index or pd.isna(vals[code]):
                    continue
                qc = avail.get(tushare_to_qlib_canonical(code))
                hp = float("nan")
                if qc is not None:
                    try:
                        hseries = hist.xs(qc, level=0)[f]
                        hseries = hseries[hseries.index <= ts_day]
                        hp = _pctl_of_last(hseries)
                    except KeyError:
                        pass
                rows.append({
                    "ts_code": code, "trade_date": day, "field": f.lstrip("$"),
                    "value": float(vals[code]),
                    "industry_pctl": float(anchors.loc[code, "pctl"]),
                    "industry_n": int(anchors.loc[code, "ind_n"])
                    if pd.notna(anchors.loc[code, "ind_n"]) else 0,
                    "pctl_scope": anchors.loc[code, "scope"],
                    "hist_pctl": hp, "source": "provider/daily_basic",
                })
    return pd.DataFrame(rows)


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    days = decision_days(C.PILOT_POOL_MONTH, C.PILOT_MONTH_END)
    pool_df = pd.read_parquet(C.POOL_DIR / f"broker_recommend_{C.PILOT_POOL_MONTH}.parquet")
    pool = sorted(set(pool_df["ts_code"]))
    logger.info("FactTable v0: %d days × %d pool names | config=%s",
                len(days), len(pool), C.config_hash())

    fund, series = build_fund_facts(days, pool)
    mkt = build_mkt_facts(days, pool)
    ft = pd.concat([fund, mkt], ignore_index=True)
    ft["fact_table_version"] = C.FACT_TABLE_VERSION
    ft["evidence_class"] = C.EVIDENCE_CLASS_REPLAY     # replay 自动注入(R2 Minor-C)

    C.FACT_DIR.mkdir(parents=True, exist_ok=True)
    out = C.FACT_DIR / f"fact_table_{C.PILOT_POOL_MONTH}.parquet"
    ft.to_parquet(out, index=False)
    series["fact_table_version"] = C.FACT_TABLE_VERSION
    series["evidence_class"] = C.EVIDENCE_CLASS_REPLAY
    series.to_parquet(C.FACT_DIR / f"fund_series_{C.PILOT_POOL_MONTH}.parquet",
                      index=False)
    logger.info("fund vintage series rows: %d", len(series))

    cov = ft.groupby("field")["value"].count()
    summary = {
        "rows": len(ft), "days": len(days), "pool": len(pool),
        "fields": int(cov.shape[0]),
        "industry_scope_pct": round(float((ft.pctl_scope == "industry_L1").mean()), 3),
        "hist_pctl_coverage": round(float(ft.hist_pctl.notna().mean()), 3),
        "config_hash": C.config_hash(),
        "evidence_class": C.EVIDENCE_CLASS_REPLAY,
    }
    (C.FACT_DIR / f"summary_{C.PILOT_POOL_MONTH}.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("fact table -> %s | %s", out, summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
