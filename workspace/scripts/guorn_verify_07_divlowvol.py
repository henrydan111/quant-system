"""果仁 deployed-20 verification — strategy #7: value_红利低波_v2 (nn=19, xlsx 19).

SCRIPT_STATUS: Class-B parity diagnostic (active build 2026-07-02). 果仁 = trusted benchmark; LOCAL under test.

Recipe (deployed_20_recipes.md #7 + master JSON nn=19):
  universe : 主板 ONLY (600/601/603/605 + 000/001/002/003 — xlsx-confirmed 002 held) − ST − 科创 − 停牌
  filters(9): 真实负债资产率 排名%最小50% **二级行业内** · 历史贝塔 排名%最小50% · SharesAvgGr%PY 排名%最小60% ·
    250日涨幅 排名%最小95% · DivGrPY% 排名%最大60% · 退市风险(2)=0 [price-leg only: close<2; proprietary legs omitted] ·
    公式(股息率TTM−10年国债收益率)>0.02 [CGB10y = recovered series] · 调入指数(10)=0 · 未来20日新增流通股<1% [OMITTED — share_float not ingested]
  rankings(8, Σw=11): 股息率TTM w3↓ · CoreProfitQGr%PY w2↓ · 总市值 w1↓ (LARGE-cap) · ROETTMDiffPQ w1↓ (v2 weighted-eq) ·
    中性N日换手率(50) w1↑ (从小到大) · BP筹资市值比调整 w1↓ · Div%NetIncY2 w1↓ · 近三年分红之和 w1↓
  trade model: Model I — 调仓周期5, 10:00 fill (≈open approx), 最大持仓10, 备选10, weights=sqrt(总市值),
    空闲资金→国泰国债ETF [approximated as CASH — 26/606 empty periods ≈4% of time, ~0.1%/yr error]

Calibers (guorn_local_field_mapping.md + platform-semantics block):
  股息率TTM = ann-date DECLARED caliber (declared_dividend_ttm) / raw close.
  分红总金额 = REPORT-PERIOD caliber; sumq legs = fiscal quarters (declared_dividend_by_quarter kernel);
    annual(分红,k) FY anchor = the stock's latest VISIBLE annual report's FY (最近年报, per-stock).
    近三年分红之和/Div%NetIncY2 = per-FY dps × CURRENT $total_share (验证: 建行@2014-01-09 → 1.7925e11 = xlsx).
  Annual(净利润) = TOTAL $n_income (incl minority) FY cum; annual slot located via the Q1 identity
    cum_qk == sq_qk → latest annual = slot (k+1) % 4 (handles all 4 reporting phases).
  ROETTMDiffPQ = v2 weighted-equity legs (0.5·q4+q3+q2+q1+0.5·q0)/4.
  历史贝塔 = 250d slope of stock SIMPLE returns on 000300 SIMPLE returns; NaN when <250 obs (果仁-official).
  中性N日换手率 / BP筹资市值比调整 = FULL-A-share cross-sectional composites (variants; xlsx truth column decides).
  排名%最小 X% = keep the smallest X% (ascending rank-pct ≤ X); 排名%最大 X% = keep the largest X%.
  NaN in keep-smallest screens → KEEP (成长簇-validated NaN-keep); in 排名%最大 → DROP.

NON-FORMAL parity artifact — reads the published provider via D.features (PIT-aligned at build); never touches
data/pit_ledger/*.
"""
from __future__ import annotations
import argparse, glob as _glob, json, sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "workspace" / "research" / "long_only_50cagr"))
sys.path.insert(0, str(ROOT / "workspace" / "scripts"))
sys.stdout.reconfigure(encoding="utf-8")

import research_utils as ru                                              # noqa: E402
import guorn_dividend_caliber as gdc                                     # noqa: E402
from guorn_universe import in_guorn_universe                             # noqa: E402
from src.backtest_engine.event_driven.strategy import Strategy           # noqa: E402

OUT = ROOT / "workspace" / "outputs" / "guorn_parity"
CACHE = OUT / "verify07_cache"
CACHE.mkdir(parents=True, exist_ok=True)
SCHED = OUT / "verify07_schedule.json"
XLSX = ROOT / "Knowledge" / "果仁回测结果" / "19_value_红利低波_v2.xlsx"
CGB = OUT / "guorn_cgb10y_recovered.parquet"
IDXW_DIR = ROOT / "data" / "normalized" / "universe" / "index_weights"
SWM = ROOT / "data" / "universe" / "industry_sw2021_members" / "industry_sw2021_members.parquet"
PROVIDER_URI = str(ROOT / "data" / "qlib_data")
GR = dict(annual=0.2973, sharpe=1.32, mdd=0.2104)

# composite term -> (weight, direction): +1 = 从大到小 (larger better), -1 = 从小到大 (smaller better)
WEIGHTS = {"dyttm": (3, +1), "CoreProfitQGr": (2, +1), "mktcap": (1, +1), "ROETTMDiff": (1, +1),
           "neutturn": (1, -1), "bpfin": (1, +1), "divnetinc": (1, +1), "div3y": (1, +1)}
TOTAL_W = sum(w for w, _ in WEIGHTS.values())

try:
    QENDS = pd.date_range("2005-03-31", "2026-12-31", freq="QE")
except ValueError:                                   # pandas < 2.2 alias
    QENDS = pd.date_range("2005-03-31", "2026-12-31", freq="Q")


def _qlib_init():
    import qlib
    from qlib.config import REG_CN
    qlib.init(provider_uri=PROVIDER_URI, region=REG_CN, kernels=1)


def _main_board(c: str) -> bool:
    return in_guorn_universe(c, boards=("main",))


def rebalance_grid(cal_max: str = "2026-02-27") -> list[pd.Timestamp]:
    """果仁's OWN period grid from the xlsx 调仓详情 (606 periods, 5-trading-day cadence), capped to the
    frozen calendar. Using 果仁's grid (not a self-made 5d grid) removes cadence-phase residual."""
    t = pd.read_excel(XLSX, sheet_name="调仓详情")
    d = pd.to_datetime(t["开始日期"], errors="coerce").dropna().sort_values().unique()
    return [pd.Timestamp(x) for x in d if pd.Timestamp(x) <= pd.Timestamp(cal_max)]


def _pdays(grid_dates, trading_index) -> dict:
    """rebalance date -> signal pday (prev trading day; 实时选股 uses T-1 close data, no lookahead)."""
    out = {}
    for d in grid_dates:
        pos = trading_index.searchsorted(pd.Timestamp(d))
        if pos > 0:
            out[pd.Timestamp(d)] = trading_index[pos - 1]
    return out


# ---------------------------------------------------------------- build: base (主板) --------------
# NOTE: $sw2021_l1 is NOT a provider bin (reads back all-NaN — the verify01 industry_allnan lesson);
# industry comes from the SW members parquet via _sw_asof().
BASE_FIELDS = ["$close", "$open", "$high", "$low", "$pre_close", "$amount", "$adj_factor",
               "$total_mv", "$total_share"]


def _sw_asof(level_col: str, pdays, columns) -> pd.DataFrame:
    """SW2021 industry name as-of each pday for `columns` (qlib codes), from the members parquet
    (in_date/out_date interval join — same source as provider_metadata, no provider bin exists)."""
    m = pd.read_parquet(SWM)
    m["c"] = m["ts_code"].str.replace(".", "_", regex=False).str.upper()
    up = {str(c).upper(): c for c in columns}
    m = m[m["c"].isin(up)]
    rows = {}
    for pday in pdays:
        alive = m[(m["in_date"] <= pday) & ((m["out_date"].isna()) | (m["out_date"] > pday))]
        s = alive.drop_duplicates("c", keep="last").set_index("c")[level_col]
        s.index = [up[i] for i in s.index]
        rows[pday] = s.reindex(columns)
    return pd.DataFrame.from_dict(rows, orient="index").sort_index()


def build_base(start="2012-06-01", end="2026-02-27"):
    from qlib.data import D
    _qlib_init()
    allinsts = D.list_instruments(D.instruments("all"), start_time="2013-01-01", end_time=end, as_list=True)
    insts = sorted(c for c in allinsts if _main_board(c))
    print(f"[base] {len(insts)} 主板 insts; {len(BASE_FIELDS)} fields {start}..{end}", flush=True)
    P = {}
    for k in range(0, len(BASE_FIELDS), 5):
        batch = BASE_FIELDS[k:k + 5]
        df = D.features(insts, batch, start_time=start, end_time=end, freq="day")
        for c in batch:
            P[c.replace("$", "")] = df[c].unstack(level=0).sort_index()
        print(f"[base]   {min(k+5, len(BASE_FIELDS))}/{len(BASE_FIELDS)}", flush=True)
        del df
    idx = P["close"].index
    adjc = P["close"] * P["adj_factor"]
    P["close"].astype("float32").to_parquet(CACHE / "e_close_raw.parquet")
    P["amount"].astype("float32").to_parquet(CACHE / "e_amt.parquet")
    P["total_mv"].reindex(idx).ffill().astype("float32").to_parquet(CACHE / "f_mktcap.parquet")
    P["total_share"].reindex(idx).ffill().astype("float64").to_parquet(CACHE / "e_total_share.parquet")
    (adjc / adjc.shift(250) - 1).astype("float32").to_parquet(CACHE / "e_ret250.parquet")
    adjc.astype("float32").to_parquet(CACHE / "e_adjc.parquet")
    (CACHE / "meta.json").write_text(json.dumps({"start": start, "end": end, "n_insts": len(insts)}),
                                     encoding="utf-8")
    print(f"[base] cached -> {CACHE}", flush=True)


# ---------------------------------------------------------------- build: fundamentals (主板) ------
def build_fin():
    from qlib.data import D
    _qlib_init()
    grid = pd.read_parquet(CACHE / "e_close_raw.parquet").index
    insts = list(pd.read_parquet(CACHE / "e_close_raw.parquet").columns)
    q = lambda b, qs: [f"${b}{i}" for i in qs]  # noqa: E731
    fields = (q("revenue_sq_q", (0, 4)) + q("oper_cost_sq_q", (0, 4)) + q("admin_exp_sq_q", (0, 4))
              + q("sell_exp_sq_q", (0, 4)) + q("fin_exp_sq_q", (0, 4)) + q("biz_tax_surchg_sq_q", (0, 4))
              + q("n_income_attr_p_sq_q", range(5)) + q("total_hldr_eqy_exc_min_int_q", range(6))
              + q("total_share_q", range(8))
              + ["$total_liab_q0", "$total_assets_q0", "$goodwill_q0", "$intan_assets_q0", "$r_and_d_q0"]
              + q("n_income_cum_q", range(9)) + q("n_income_sq_q", range(4)))
    P = {}
    for k in range(0, len(fields), 6):
        batch = fields[k:k + 6]
        df = D.features(insts, batch, start_time=str(grid[0].date()), end_time=str(grid[-1].date()), freq="day")
        for c in batch:
            # n_income cum/sq stay float64 — the Q1 identity (cum==sq) needs full precision
            dt = "float64" if c.startswith(("$n_income_cum", "$n_income_sq")) else "float32"
            P[c.replace("$", "")] = df[c].unstack(level=0).sort_index().reindex(grid).ffill().astype(dt)
        print(f"[fin] {min(k+6, len(fields))}/{len(fields)}", flush=True)
        del df
    EPS = 1e-9
    safe = lambda n, d: (n / d.where(d.abs() > EPS)).replace([np.inf, -np.inf], np.nan)  # noqa: E731

    # CoreProfitQ expense legs NaN→0 (果仁-vendor 0-fill; FINANCIALS lack oper_cost/sell/fin lines and
    # strict-NaN rank-bottomed 建行 etc on the w2 term — found via the #8 term-drag autopsy 2026-07-02;
    # 0-fill 建行@2014-01-08 = 0.0971 vs xlsx 0.0993 structure-exact). Revenue stays REQUIRED.
    zc = lambda fr: fr.fillna(0.0)  # noqa: E731
    core = lambda qq: (P[f"revenue_sq_q{qq}"] - zc(P[f"oper_cost_sq_q{qq}"])  # noqa: E731
                       - (zc(P[f"admin_exp_sq_q{qq}"]) + zc(P[f"sell_exp_sq_q{qq}"]) + zc(P[f"fin_exp_sq_q{qq}"]))
                       - zc(P[f"biz_tax_surchg_sq_q{qq}"]))
    c0, c4 = core(0), core(4)
    safe(c0 - c4, c4.abs()).astype("float32").to_parquet(CACHE / "f_CoreProfitQGr.parquet")

    ni = {i: P[f"n_income_attr_p_sq_q{i}"] for i in range(5)}
    eq = {i: P[f"total_hldr_eqy_exc_min_int_q{i}"] for i in range(6)}
    weq0 = (0.5 * eq[4] + eq[3] + eq[2] + eq[1] + 0.5 * eq[0]) / 4.0
    weq1 = (0.5 * eq[5] + eq[4] + eq[3] + eq[2] + 0.5 * eq[1]) / 4.0
    roe0 = safe(ni[0] + ni[1] + ni[2] + ni[3], weq0)
    roe1 = safe(ni[1] + ni[2] + ni[3] + ni[4], weq1)
    (roe0 - roe1).astype("float32").to_parquet(CACHE / "f_ROETTMDiff.parquet")

    sh03 = sum(P[f"total_share_q{i}"] for i in range(4))
    sh47 = sum(P[f"total_share_q{i}"] for i in range(4, 8))
    safe(sh03, sh47).sub(1).astype("float32").to_parquet(CACHE / "e_sharesgr.parquet")

    z = lambda fr: fr.fillna(0.0)  # noqa: E731
    denom = P["total_assets_q0"] - z(P["goodwill_q0"]) - z(P["intan_assets_q0"]) - z(P["r_and_d_q0"])
    safe(P["total_liab_q0"], denom).astype("float32").to_parquet(CACHE / "e_zsfz.parquet")

    # ---- FY annual NI (TOTAL n_income) via the Q1 identity: cum_qk == sq_qk => slot k is a Q1;
    # latest annual slot = (k+1) % 4, previous annual = that + 4. NaN where undetectable.
    cum = {i: P[f"n_income_cum_q{i}"] for i in range(9)}
    sq = {i: P[f"n_income_sq_q{i}"] for i in range(4)}
    q1_stack = np.stack([(np.isclose(cum[i].values, sq[i].values, rtol=1e-6, atol=1.0)
                          & cum[i].notna().values & sq[i].notna().values) for i in range(4)], axis=0)
    any_q1 = q1_stack.any(axis=0)
    kidx = q1_stack.argmax(axis=0).astype("float64")   # FIRST Q1 slot among q0..q3
    kidx[~any_q1] = np.nan
    k_first = pd.DataFrame(kidx, index=cum[0].index, columns=cum[0].columns)
    ann_slot = (k_first + 1) % 4                       # frame of {0,1,2,3}; NaN when no Q1 slot visible
    fy0 = pd.DataFrame(np.nan, index=cum[0].index, columns=cum[0].columns)
    fy1 = pd.DataFrame(np.nan, index=cum[0].index, columns=cum[0].columns)
    for s in range(4):
        m = ann_slot == s
        fy0 = fy0.where(~m, cum[s])
        fy1 = fy1.where(~m, cum[s + 4])
    fy0.astype("float64").to_parquet(CACHE / "e_ni_fy0.parquet")
    fy1.astype("float64").to_parquet(CACHE / "e_ni_fy1.parquet")
    ann_slot.astype("float32").to_parquet(CACHE / "e_ann_slot.parquet")
    (k_first + 1).astype("float32").to_parquet(CACHE / "e_q0quarter.parquet")   # reported q0's quarter (1..4)
    print("[fin] saved CoreProfitQGr / ROETTMDiff / sharesgr / zsfz / ni_fy0 / ni_fy1 / q0quarter", flush=True)


# ---------------------------------------------------------------- build: beta (250d vs 000300) ----
def build_beta():
    from qlib.data import D
    _qlib_init()
    adjc = pd.read_parquet(CACHE / "e_adjc.parquet")
    grid = adjc.index
    r = adjc.pct_change(fill_method=None)
    idxdf = D.features(["000300_SH"], ["$close"], start_time=str(grid[0].date()),
                       end_time=str(grid[-1].date()), freq="day")
    ridx = (idxdf.reset_index(level=0, drop=True)["$close"].sort_index()
            .reindex(grid).pct_change(fill_method=None))
    # slope = Cov(r, ridx, 250) / Var(ridx, 250) over PAIRWISE-complete obs; 果仁 rule: 上市交易 <250日 →
    # 空值 (gate on days-since-first-quote, not on a gap-free window — a few 停牌 days must not NaN it).
    x = ridx
    n, minp = 250, 200
    valid = r.notna() & x.notna().values[:, None]
    xm = pd.DataFrame(np.where(valid, np.broadcast_to(x.values[:, None], r.shape), np.nan),
                      index=r.index, columns=r.columns)
    rm = r.where(valid)
    cnt = valid.rolling(n, min_periods=1).sum()
    sx = xm.rolling(n, min_periods=minp).sum()
    sy = rm.rolling(n, min_periods=minp).sum()
    sxy = (rm * xm).rolling(n, min_periods=minp).sum()
    sxx = (xm ** 2).rolling(n, min_periods=minp).sum()
    cov = sxy - sx * sy / cnt
    var = sxx - sx ** 2 / cnt
    listed_days = adjc.notna().cumsum()
    beta = (cov / var.where(var.abs() > 1e-12)).where((cnt >= minp) & (listed_days >= n))
    beta.astype("float32").to_parquet(CACHE / "e_beta.parquet")
    print(f"[beta] saved  cov={beta.notna().mean().mean():.3f}", flush=True)


# ---------------------------------------------------------------- build: dividends (pday rows) ----
def _div_events_raw() -> pd.DataFrame:
    frames = [pd.read_parquet(f) for f in _glob.glob(gdc.DIV_GLOB)]
    d = pd.concat(frames, ignore_index=True)
    d["proc"] = d["div_proc"].map(gdc._decode_gbk)
    d["ann"] = pd.to_datetime(d["ann_date"], format="%Y%m%d", errors="coerce")
    d = d[(d["cash_div_tax"].fillna(0) > 0) & d["ann"].notna()].copy()
    d["prio"] = d["proc"].map(gdc._PROC_PRIORITY).fillna(0)
    d["c6"] = d["ts_code"].str.split(".").str[0]
    d["ed"] = d["end_date"].astype(str)  # noqa: unsafe-pit-dates[PIT001] reason: fiscal-period LABEL; visibility PIT-gated per signal below
    d["fy"] = d["ed"].str[:4].astype(int)
    d["edq"] = pd.PeriodIndex(pd.to_datetime(d["ed"], format="%Y%m%d", errors="coerce"), freq="Q")  # noqa: unsafe-pit-dates[PIT001] reason: same fiscal LABEL
    return d


def _div_at(d: pd.DataFrame, sig: pd.Timestamp):
    """Per-signal-date dividend aggregates, mirroring gdc kernels exactly (asserted in --selftest-div).
    Returns (dps_ttm, per_quarter df, per_fy df)."""
    m = d[d["ann"] <= sig]
    # --- 股息率TTM kernel (declared_dividend_ttm): prio-sorted last, window = earliest ann in (sig-365, sig]
    ev = (m.sort_values("prio").groupby(["c6", "ed"], sort=False)
          .agg(dps=("cash_div_tax", "last"), win=("ann", "min")))
    ttm = ev[(ev["win"] > sig - pd.Timedelta(days=365)) & (ev["win"] <= sig)]
    dps_ttm = ttm.groupby(level=0)["dps"].sum()
    # --- report-period kernel (_declared_events): (prio, ann)-sorted last + stale-预案 rule
    ev2 = (m.sort_values(["prio", "ann"]).groupby(["c6", "ed"], sort=False)
           .agg(dps=("cash_div_tax", "last"), best=("proc", "last"), last_ann=("ann", "max"),
                fy=("fy", "last"), edq=("edq", "last")).reset_index())
    stale = (ev2["best"] != "实施") & (ev2["last_ann"] < sig - pd.Timedelta(days=240))
    ev2 = ev2[~stale]
    byq = ev2.groupby(["c6", "edq"])["dps"].sum().unstack("edq")
    byfy = ev2.groupby(["c6", "fy"])["dps"].sum().unstack("fy")
    return dps_ttm, byq, byfy


def build_div(end="2026-02-27"):
    close = pd.read_parquet(CACHE / "e_close_raw.parquet")
    grid = close.index
    rebal = rebalance_grid(end)
    pmap = _pdays(rebal, grid)
    pdays = sorted(set(pmap.values()))
    d = _div_events_raw()
    code6 = pd.Index([c.split("_")[0] for c in close.columns])
    rows_ttm, rows_gr, rows_3y, rows_dn = {}, {}, {}, {}
    # fin-derived frames can carry FEWER columns than base (D.features drops no-data insts) — align
    q0q = pd.read_parquet(CACHE / "e_q0quarter.parquet").reindex(columns=close.columns)
    ni0 = pd.read_parquet(CACHE / "e_ni_fy0.parquet").reindex(columns=close.columns)
    ni1 = pd.read_parquet(CACHE / "e_ni_fy1.parquet").reindex(columns=close.columns)
    tsh = pd.read_parquet(CACHE / "e_total_share.parquet").reindex(columns=close.columns)
    _QEND_MD = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}

    def _fy_lookup(byfy: pd.DataFrame, fy_ser: pd.Series) -> pd.Series:
        """byfy[fy] per-stock with a per-stock fy column choice (2-3 unique fys per date)."""
        out = pd.Series(np.nan, index=fy_ser.index)
        for fy in pd.unique(fy_ser.dropna()):
            fy = int(fy)
            if fy in byfy.columns:
                m = fy_ser == fy
                out.loc[m] = byfy[fy].reindex(fy_ser.index[m]).values
        return out

    for i, pday in enumerate(pdays):
        dps_ttm, byq, byfy = _div_at(d, pday)
        cr = close.loc[pday].copy()
        cr.index = code6
        rows_ttm[pday] = (dps_ttm.reindex(code6) / cr).values
        # --- Per-stock REPORTED-quarter anchor (分红总金额 is a 季报指标 on the REPORT grid — pinned on
        # 建行 2014-01-08: sumq window {2013Q3..2012Q4}/{2012Q3..2011Q4} → 0.1332 = xlsx EXACT; a
        # calendar-quarter window gives −1). Reported q0's quarter = Q1-identity detector (e_q0quarter);
        # its year = latest (year, quarter) whose quarter-end ≤ pday.
        qq = q0q.loc[pday].copy()
        qq.index = code6
        q0_ord = pd.Series(np.nan, index=code6)
        fy0s = pd.Series(np.nan, index=code6)
        for qn, (mm, dd) in _QEND_MD.items():
            q0y = pday.year if pd.Timestamp(pday.year, mm, dd) <= pday else pday.year - 1
            q0_ord = q0_ord.where(qq != qn, pd.Period(year=q0y, quarter=qn, freq="Q").ordinal)
            fy0s = fy0s.where(qq != qn, q0y - 1 if qn < 4 else q0y)   # 最近年报 FY
        # DivGrPY% = Σ dps over REPORTED quarters {q0..q0−3} / {q0−4..q0−7} − 1, per-stock window
        ords = np.array([p.ordinal for p in byq.columns])
        s03 = pd.Series(np.nan, index=code6)
        s47 = pd.Series(np.nan, index=code6)
        for o in pd.unique(q0_ord.dropna()):
            m03 = (ords <= o) & (ords >= o - 3)
            m47 = (ords <= o - 4) & (ords >= o - 7)
            sel = q0_ord == o
            sub = byq.reindex(code6[sel])
            s03.loc[sel] = sub.loc[:, m03].sum(axis=1).values if m03.any() else 0.0
            s47.loc[sel] = sub.loc[:, m47].sum(axis=1).values if m47.any() else 0.0
        gr = (s03 / s47.where(s47 > 0) - 1.0)
        rows_gr[pday] = gr.values
        a0 = _fy_lookup(byfy, fy0s)
        a1 = _fy_lookup(byfy, fy0s - 1)
        a2 = _fy_lookup(byfy, fy0s - 2)
        shares = tsh.loc[pday].copy()
        shares.index = code6
        d3 = (a0.fillna(0) + a1.fillna(0) + a2.fillna(0)) * shares
        rows_3y[pday] = d3.where(fy0s.notna()).values
        n0 = ni0.loc[pday].copy(); n0.index = code6
        n1 = ni1.loc[pday].copy(); n1.index = code6
        r0 = (a0.fillna(0) * shares) / n0.where(n0.abs() > 1)
        r1 = (a1.fillna(0) * shares) / n1.where(n1.abs() > 1)
        both = (r0 + r1) / 2.0
        rows_dn[pday] = both.where(r1.notna(), r0).values
        if (i + 1) % 50 == 0:
            print(f"[div] {i+1}/{len(pdays)} pdays", flush=True)
    cols = close.columns
    for name, rows in (("f_dyttm", rows_ttm), ("e_divgr", rows_gr), ("f_div3y", rows_3y),
                       ("f_divnetinc", rows_dn)):
        fr = pd.DataFrame.from_dict(rows, orient="index")
        fr.columns = cols
        fr.sort_index().astype("float64").to_parquet(CACHE / f"{name}.parquet")
    print(f"[div] saved dyttm/divgr/div3y/divnetinc on {len(pdays)} pdays", flush=True)


def selftest_div():
    """Assert the vectorized kernels == the validated gdc functions on 3 sample dates."""
    d = _div_events_raw()
    for sig in ("2015-06-30", "2020-03-31", "2025-12-31"):
        dps_ttm, byq, byfy = _div_at(d, pd.Timestamp(sig))
        ref = gdc.declared_dividend_ttm(sig)
        j = pd.concat([dps_ttm.rename("mine"), ref.rename("ref")], axis=1).dropna()
        assert np.allclose(j["mine"], j["ref"]), f"ttm mismatch @{sig}"
        assert len(j) == len(ref.dropna()) == len(dps_ttm.dropna()), f"ttm index mismatch @{sig}"
        refq = gdc.declared_dividend_by_quarter(sig)
        refq.columns = pd.PeriodIndex(pd.to_datetime(refq.columns, format="%Y%m%d"), freq="Q")
        refq = refq.T.groupby(level=0).sum(min_count=1).T
        a, b = byq.stack(), refq.stack()
        a.index.names = b.index.names = ["c6", "q"]
        jq = a.rename("mine").to_frame().join(b.rename("ref"), how="outer")
        assert np.allclose(jq["mine"].fillna(-9), jq["ref"].fillna(-9)), f"byq mismatch @{sig}"
        reffy = gdc.declared_dividend_by_fy(sig)
        a, b = byfy.stack(), reffy.stack()
        a.index.names = b.index.names = ["c6", "fy"]
        jf = a.rename("mine").to_frame().join(b.rename("ref"), how="outer")
        assert np.allclose(jf["mine"].fillna(-9), jf["ref"].fillna(-9)), f"byfy mismatch @{sig}"
        print(f"[selftest-div] {sig} OK (ttm n={len(j)}, byq n={len(jq)}, byfy n={len(jf)})", flush=True)


# ---------------------------------------------------------------- build: cross-sectional (ALL A) --
def build_neut(end="2026-02-27"):
    """中性N日换手率(50) + BP筹资市值比调整 — cross-section = ALL A-shares (main+chinext+star), then slice 主板.
    Variants saved side-by-side; the xlsx truth columns pick the winner at --factor-parity."""
    from qlib.data import D
    _qlib_init()
    close_mb = pd.read_parquet(CACHE / "e_close_raw.parquet")
    grid = close_mb.index
    rebal = rebalance_grid(end)
    pdays = sorted(set(_pdays(rebal, grid).values()))
    allinsts = D.list_instruments(D.instruments("all"), start_time="2013-01-01", end_time=str(grid[-1].date()),
                                  as_list=True)
    insts = sorted(c for c in allinsts if in_guorn_universe(c, include_star=True))
    fields = ["$turnover_rate", "$total_mv", "$total_hldr_eqy_exc_min_int_q0",
              "$stot_cash_in_fnc_act_sq_q0", "$stot_cash_in_fnc_act_sq_q1",
              "$stot_cash_in_fnc_act_sq_q2", "$stot_cash_in_fnc_act_sq_q3",
              "$vol", "$total_share"]
    P = {}
    for k in range(0, len(fields), 4):
        batch = fields[k:k + 4]
        df = D.features(insts, batch, start_time=str(grid[0].date()), end_time=str(grid[-1].date()), freq="day")
        for c in batch:
            P[c.replace("$", "")] = df[c].unstack(level=0).sort_index().reindex(grid)
        print(f"[neut] fetched {min(k+4, len(fields))}/{len(fields)}", flush=True)
        del df
    ma50 = P["turnover_rate"].rolling(50, min_periods=1).mean()      # 果仁 SUM/MA window funcs: partial OK
    mv = P["total_mv"].ffill()
    # v4/v5 base: 果仁-official 累计换手率 = 成交股数/总股本 (TOTAL share — Tushare turnover_rate is
    # FLOAT-share), 停牌日计入窗口 (0 traded volume), <N 交易日 → 空值 (果仁选股指标详解).
    tsh_all = P["total_share"].ffill()
    turn_tot = (P["vol"] * 100.0) / tsh_all.where(tsh_all > 0)
    listed_mask = mv.notna()
    turn_tot = turn_tot.where(turn_tot.notna() | ~listed_mask, 0.0)   # suspension inside listing → 0
    tdays = P["vol"].notna().cumsum()
    cum50 = turn_tot.rolling(50, min_periods=1).sum().where(tdays >= 50)
    all_cols = ma50.columns
    ind = _sw_asof("l1_name", pdays, all_cols)                        # SW L1 as-of (members parquet)
    print(f"[neut] L1 industry as-of built  cov={ind.notna().mean().mean():.3f}", flush=True)
    eq = P["total_hldr_eqy_exc_min_int_q0"].ffill()
    fin = sum(P[f"stot_cash_in_fnc_act_sq_q{i}"].ffill() for i in range(4))
    bp = eq / mv.where(mv > 0)
    finr = fin / mv.where(mv > 0)

    def _resid(y: pd.Series, x: pd.Series, g: pd.Series | None) -> pd.Series:
        df = pd.DataFrame({"y": y, "x": x})
        if g is not None:
            if g.notna().sum() == 0:                       # no industry info on this date -> undefined
                return pd.Series(np.nan, index=y.index)
            df["g"] = g
            def f(sub):
                s = sub.dropna(subset=["y", "x"])
                if len(s) < 3 or s["x"].std() == 0:
                    return sub["y"] - sub["y"].mean()
                b = s["y"].cov(s["x"]) / s["x"].var()
                a = s["y"].mean() - b * s["x"].mean()
                return sub["y"] - (a + b * sub["x"])
            res = df.groupby("g", group_keys=False).apply(f)
            if not isinstance(res, pd.Series):             # zero non-degenerate groups edge case
                return pd.Series(np.nan, index=y.index)
            return res.reindex(y.index)
        s = df.dropna()
        if len(s) < 3 or s["x"].std() == 0:
            return df["y"] - df["y"].mean()
        b = s["y"].cov(s["x"]) / s["x"].var()
        a = s["y"].mean() - b * s["x"].mean()
        return df["y"] - (a + b * df["x"])

    mb_cols = close_mb.columns
    variants = {"neutturn_v1": {}, "neutturn_v2": {}, "neutturn_v3": {}, "neutturn_v4": {},
                "neutturn_v5": {}, "bpfin": {}}
    for i, pday in enumerate(pdays):
        t = ma50.loc[pday]
        lmv = np.log(mv.loc[pday].where(mv.loc[pday] > 0))
        gi = ind.loc[pday]
        variants["neutturn_v1"][pday] = _resid(t, lmv, gi)                       # HNeutralize(MA50, logMV, 1)
        variants["neutturn_v2"][pday] = _resid(t, lmv, None)                     # 范围=0 (all-A)
        gm = t.groupby(gi).transform("mean")
        variants["neutturn_v3"][pday] = t / gm.where(gm > 0)                     # ratio-to-L1-industry-mean
        t4 = cum50.loc[pday]
        variants["neutturn_v4"][pday] = _resid(t4, lmv, gi)                      # 官方累计换手(总股本), L1内
        variants["neutturn_v5"][pday] = _resid(t4, lmv, None)                    # 官方累计换手(总股本), 全A
        ybp = bp.loc[pday].rank(pct=True)
        xfr = finr.loc[pday].rank(pct=True)
        variants["bpfin"][pday] = _resid(ybp, xfr, None)                         # HNeutralize(pr(BP), pr(筹资/mv), 0)
        if (i + 1) % 100 == 0:
            print(f"[neut] {i+1}/{len(pdays)}", flush=True)
    for name, rows in variants.items():
        fr = pd.DataFrame.from_dict(rows, orient="index").sort_index()
        fr.reindex(columns=mb_cols).astype("float32").to_parquet(CACHE / f"f_{name}.parquet")
    print("[neut] saved neutturn v1/v2/v3 + bpfin (主板 slice)", flush=True)


# ---------------------------------------------------------------- build: L2 industry + 调入指数 ----
def build_l2(end="2026-02-27"):
    close = pd.read_parquet(CACHE / "e_close_raw.parquet")
    grid = close.index
    pdays = sorted(set(_pdays(rebalance_grid(end), grid).values()))
    m = pd.read_parquet(SWM)
    m["c"] = m["ts_code"].str.replace(".", "_", regex=False).str.upper()
    m = m[m["c"].isin([c.upper() for c in close.columns])]
    up = {c.upper(): c for c in close.columns}
    rows = {}
    for pday in pdays:
        alive = m[(m["in_date"] <= pday) & ((m["out_date"].isna()) | (m["out_date"] > pday))]
        s = alive.drop_duplicates("c", keep="last").set_index("c")["l2_name"]
        s.index = [up[i] for i in s.index]
        rows[pday] = s.reindex(close.columns)
    fr = pd.DataFrame.from_dict(rows, orient="index").sort_index()
    fr.astype("str").to_parquet(CACHE / "industry_l2.parquet")
    print(f"[l2] saved industry_l2 on {len(pdays)} pdays  cov={fr.notna().mean().mean():.3f}", flush=True)


def build_idx(end="2026-02-27"):
    """调入指数(10): member now but non-member at some point in the trailing 10 trading days, any of
    沪深300/中证500/中证1000. Monthly snapshots -> as-of daily membership (step function)."""
    close = pd.read_parquet(CACHE / "e_close_raw.parquet")
    grid = close.index
    files = sorted(IDXW_DIR.glob("index_weights_*.parquet"))
    w = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    w["trade_date"] = pd.to_datetime(w["trade_date"])
    w["c"] = w["con_code"].str.replace(".", "_", regex=False).str.upper()
    up = {c.upper(): c for c in close.columns}
    flag = pd.DataFrame(False, index=grid, columns=close.columns)
    for idx_code in ("000300.SH", "000905.SH", "000852.SH"):
        sub = w[w["index_code"] == idx_code]
        if sub.empty:
            print(f"[idx] WARNING: {idx_code} has no rows — screen degrades", flush=True)
            continue
        snaps = sorted(sub["trade_date"].unique())
        mem = pd.DataFrame(0, index=pd.DatetimeIndex(snaps), columns=close.columns, dtype="int8")
        for sd, grp in sub.groupby("trade_date"):
            codes = [up[c] for c in grp["c"] if c in up]
            mem.loc[sd, codes] = 1
        memd = mem.reindex(grid, method="ffill").fillna(0)
        was_out = (memd == 0).rolling(10, min_periods=1).max()
        flag |= (memd == 1) & (was_out == 1)
        print(f"[idx] {idx_code}: {len(snaps)} snapshots {snaps[0].date()}..{snaps[-1].date()}", flush=True)
    flag.astype("int8").to_parquet(CACHE / "e_idxflag.parquet")
    print(f"[idx] saved e_idxflag  mean={flag.mean().mean():.4f}", flush=True)


# ---------------------------------------------------------------- schedule ------------------------
def _load_frames():
    cols = pd.read_parquet(CACHE / "e_close_raw.parquet").columns
    rd = lambda p: pd.read_parquet(CACHE / p).reindex(columns=cols)  # noqa: E731 (align col sets)
    f = {"dyttm": rd("f_dyttm.parquet"), "CoreProfitQGr": rd("f_CoreProfitQGr.parquet"),
         "mktcap": rd("f_mktcap.parquet"), "ROETTMDiff": rd("f_ROETTMDiff.parquet"),
         "neutturn": rd("f_neutturn_v1.parquet"), "bpfin": rd("f_bpfin.parquet"),
         "divnetinc": rd("f_divnetinc.parquet"), "div3y": rd("f_div3y.parquet")}
    e = {n: rd(f"e_{n}.parquet")
         for n in ("close_raw", "amt", "zsfz", "beta", "sharesgr", "ret250", "divgr", "idxflag", "total_share")}
    l2 = rd("industry_l2.parquet")
    return f, e, l2


def _bounds():
    p = ROOT / "data" / "qlib_data" / "instruments" / "all_stocks.txt"
    df = pd.read_csv(p, sep="\t", header=None, names=["code", "start", "end"], dtype=str)
    return {str(r.code).upper(): (pd.Timestamp(r.start), pd.Timestamp(r.end)) for r in df.itertuples(index=False)}


def _row(fr: pd.DataFrame, pday):
    """Row at pday — dividend/composite frames carry pday rows only; daily frames carry the full grid."""
    if pday in fr.index:
        return fr.loc[pday]
    pos = fr.index.searchsorted(pday)
    if pos == 0:
        return pd.Series(np.nan, index=fr.columns)
    return fr.iloc[pos - 1]


def _cgb_series() -> pd.Series:
    """Recovered 果仁 10Y CGB anchors (578 period-starts), TIME-INTERPOLATED across the 3 empty-period
    gaps (25/108/63 days — ffill held the stale yield through the 2015 crash fall and the 2016-12 bond-rout
    rise, flipping the 2% threshold both ways). Reconstruction of a PUBLIC macro series 果仁 knew at each
    date — not a lookahead (NON-FORMAL parity)."""
    cgb = pd.read_parquet(CGB)
    cgb = cgb.iloc[:, 0] if isinstance(cgb, pd.DataFrame) else cgb
    cgb.index = pd.to_datetime(cgb.index)
    cgb = cgb.sort_index()
    daily = pd.date_range(cgb.index.min(), cgb.index.max(), freq="D")
    return cgb.reindex(daily).interpolate(method="time")


def build_schedule(end="2026-02-27", headroom=20, neutturn_variant="v1"):
    f, e, l2 = _load_frames()
    if neutturn_variant != "v1":
        f["neutturn"] = pd.read_parquet(CACHE / f"f_neutturn_{neutturn_variant}.parquet")
    cgb = _cgb_series()
    close = e["close_raw"]
    grid = close.index
    insts = close.columns
    bounds = _bounds()
    rebal = rebalance_grid(end)
    pmap = _pdays(rebal, grid)
    sched = {}
    n_elig_log = []
    for d in rebal:
        pday = pmap.get(pd.Timestamp(d))
        if pday is None:
            sched[pd.Timestamp(d)] = []
            continue
        st = ru.st_codes_on(d)
        cr = close.loc[pday]
        not_st = pd.Series([str(c).upper() not in st for c in insts], index=insts)
        listed = pd.Series([(bounds.get(str(c).upper()) is not None
                             and bounds[str(c).upper()][0] <= pday <= bounds[str(c).upper()][1])
                            for c in insts], index=insts)
        rank_base = listed & cr.notna() & not_st       # rank% screens over the 投资域 (主板 quoted non-ST)
        keep = rank_base.copy()                                        # 过滤停牌 + universe + 排除ST
        keep &= (cr >= 2.0).fillna(False)                              # 退市风险 price leg (收盘价<2 → excluded)

        def pct_asc(row):
            return row.where(rank_base).rank(pct=True)                 # ascending: smallest -> lowest pct

        # 排名%最小 X% = keep the smallest X% (NaN -> KEEP, 成长簇-validated). Within-group cutoff uses
        # rank ≤ ceil(X·N) — the small-L2-group boundary pinned 2026-07-02 (held-name pcts cluster at
        # 2/3, 4/7, 6/11 = exactly ceil; pass 84.4%→87.7%; residual = 银行簇 vendor-vintage partition).
        zr = e["zsfz"].loc[pday].where(rank_base)
        l2row = _row(l2, pday).replace({"nan": np.nan, "None": np.nan})
        zrank = zr.groupby(l2row).rank(method="min")
        zN = l2row.map(zr.groupby(l2row).count())
        keep &= ~(zrank > np.ceil(0.50 * zN)).fillna(False)            # 真实负债资产率 最小50% 二级行业内
        keep &= ~(pct_asc(e["beta"].loc[pday]) > 0.50).fillna(False)   # 历史贝塔 最小50%
        keep &= ~(pct_asc(e["sharesgr"].loc[pday]) > 0.60).fillna(False)   # SharesAvgGr%PY 最小60%
        keep &= ~(pct_asc(e["ret250"].loc[pday]) > 0.95).fillna(False)     # 250日涨幅 最小95%
        # 排名%最大 60% = keep the largest 60% (NaN -> DROP: NaN ranks bottom of 从大到小)
        gr_pct = _row(e["divgr"], pday).where(rank_base).rank(pct=True, ascending=False)
        keep &= (gr_pct <= 0.60).fillna(False)                         # DivGrPY% 最大60%
        # 股息率TTM − CGB10y > 0.02; CGB looked up at the REBALANCE date d (the recovered series is
        # indexed by the xlsx period starts — the value AT d is exactly what 果仁 used for that period)
        cpos = cgb.index.searchsorted(pd.Timestamp(d), side="right")
        cval = float(cgb.iloc[cpos - 1]) if cpos > 0 else np.nan
        dy = _row(f["dyttm"], pday)
        keep &= ((dy - cval) > 0.02).fillna(False)
        keep &= _row(e["idxflag"], pday).fillna(0).astype(int) == 0    # 调入指数(10) = 0
        elig = keep[keep].index
        n_elig_log.append(len(elig))
        if len(elig) == 0:
            sched[pd.Timestamp(d)] = []
            continue
        # composite: 排名分 = (N−rank+1)/N×100 within elig, NaN -> bottom
        N = len(elig)
        parts = []
        for name, (w, di) in WEIGHTS.items():
            row = _row(f[name], pday).reindex(elig)
            rnk = row.rank(method="min", ascending=(di < 0), na_option="bottom")
            parts.append((N - rnk + 1) / N * 100.0 * w)
        comp = pd.concat(parts, axis=1).sum(axis=1) / (100.0 * TOTAL_W)
        top = comp.sort_values(ascending=False).head(headroom)
        mv = f["mktcap"].loc[pday].reindex(top.index)
        sched[pd.Timestamp(d)] = [[str(c).upper().replace("_", "."), float(mv.get(c, np.nan))]
                                  for c in top.index]
    SCHED.write_text(json.dumps({str(k.date()): v for k, v in sched.items()}, ensure_ascii=False),
                     encoding="utf-8")
    ne = pd.Series(n_elig_log)
    print(f"[sched] {sum(1 for v in sched.values() if v)}/{len(rebal)} non-empty; "
          f"elig-count p10/med/p90 = {ne.quantile(.1):.0f}/{ne.median():.0f}/{ne.quantile(.9):.0f}", flush=True)


# ---------------------------------------------------------------- factor parity vs xlsx -----------
XLSX_COLS = {"dyttm": "股息率TTM", "CoreProfitQGr": "CoreProfitQGr%PY", "ROETTMDiff": "ROETTMDiffPQ",
             "divnetinc": "Div%NetIncY2", "div3y": "近三年分红之和", "bpfin": "BP筹资市值比调整",
             "neutturn": "中性N日换手率(50)"}
XLSX_ECOLS = {"zsfz": "真实负债资产率", "beta": "历史贝塔", "sharesgr": "SharesAvgGr%PY",
              "ret250": "250日涨幅", "divgr": "DivGrPY%"}


def factor_parity(end="2026-02-27"):
    """Join local frames to the xlsx 持仓详单 ground-truth factor columns (held names only) —
    the per-factor value agreement that pins calibers BEFORE any backtest."""
    f, e, l2 = _load_frames()
    h = pd.read_excel(XLSX, sheet_name="各阶段持仓详单")
    h["start"] = pd.to_datetime(h["开始日期"], errors="coerce")
    h = h[h["start"].notna() & (h["start"] <= pd.Timestamp(end))].copy()
    h["code"] = h["股票代码"].astype(str).str.zfill(6)
    grid = e["close_raw"].index
    pmap = _pdays(sorted(h["start"].unique()), grid)
    up = {}
    for c in e["close_raw"].columns:
        up[str(c).split("_")[0]] = c
    frames = {**{k: f[k] for k in XLSX_COLS if k in f}, **{k: e[k] for k in XLSX_ECOLS}}
    # neutturn variants side by side
    for v in ("v1", "v2", "v3", "v4", "v5"):
        p = CACHE / f"f_neutturn_{v}.parquet"
        if p.exists():
            frames[f"neutturn_{v}"] = pd.read_parquet(p)
    frames.pop("neutturn", None)
    stats = []
    l2_hits, l2_tot = 0, 0
    recs = {k: [] for k in frames}
    for d, grp in h.groupby("start"):
        pday = pmap.get(pd.Timestamp(d))
        if pday is None:
            continue
        l2row = _row(l2, pday)
        for _, r in grp.iterrows():
            inst = up.get(r["code"])
            if inst is None:
                continue
            gl2 = str(r.get("二级行业", "")).strip()
            ml2 = str(l2row.get(inst, "")).strip()
            if gl2 and gl2 != "nan":
                l2_tot += 1
                l2_hits += int(gl2 == ml2)
            for k, fr in frames.items():
                gcol = XLSX_COLS.get(k.split("_v")[0] if k.startswith("neutturn") else k,
                                     XLSX_ECOLS.get(k))
                if k.startswith("neutturn"):
                    gcol = "中性N日换手率(50)"
                gv = pd.to_numeric(r.get(gcol), errors="coerce")
                lv = _row(fr, pday).get(inst, np.nan)
                if pd.notna(gv) and pd.notna(lv):
                    recs[k].append((float(gv), float(lv)))
    print(f"\n=== #7 per-factor value agreement vs xlsx 持仓详单 (held names, n periods={h['start'].nunique()}) ===")
    print(f"  二级行业 name match: {l2_hits}/{l2_tot} = {l2_hits/max(l2_tot,1):.1%}")
    for k, pairs in recs.items():
        if not pairs:
            print(f"  {k:16} NO DATA")
            continue
        a = pd.DataFrame(pairs, columns=["g", "l"])
        rel = ((a["l"] - a["g"]).abs() / a["g"].abs().clip(lower=1e-9)).median()
        sign = (np.sign(a["l"]) == np.sign(a["g"])).mean()
        sp = a["g"].corr(a["l"], method="spearman")
        pe = a["g"].corr(a["l"])
        stats.append(dict(factor=k, n=len(a), med_rel=float(rel), sign=float(sign),
                          spearman=float(sp), pearson=float(pe)))
        print(f"  {k:16} n={len(a):5d}  medRel={rel:8.4f}  sign={sign:.3f}  sp={sp:+.3f}  pe={pe:+.3f}")
    pd.DataFrame(stats).to_json(OUT / "verify07_factor_parity.json", orient="records", force_ascii=False)
    print(f"[parity] saved verify07_factor_parity.json", flush=True)


# ---------------------------------------------------------------- Model-I strategy + run ----------
class ModelIDivLowVolStrategy(Strategy):
    """果仁 Model I: rebalance ONLY on grid dates — target = top max_holds selected names, weights ∝
    sqrt(总市值) (as-of pday, from the schedule), fully invested; unbuyable (suspended) targets skipped
    and the next-ranked 备选 promoted. Idle cash when nothing passes = CASH (国泰国债ETF approximation)."""

    def __init__(self, sched: dict, *, max_holds=10, reserve=10, weights_mode="sqrt_mv"):
        super().__init__()
        self.sched = {pd.Timestamp(k): v for k, v in sched.items()}
        self.max_holds, self.reserve = int(max_holds), int(reserve)
        self.weights_mode = weights_mode          # "sqrt_mv" (Model I) | "explicit" (replay: [[code, w]])

    def initialize(self, context):
        return None

    def on_bar(self, context):
        return []

    def after_market_close(self, context):
        return None

    def before_market_open(self, context):
        from src.backtest_engine.event_driven.strategies import _emit_rebalance_orders
        today = pd.Timestamp(context.date)
        lst = self.sched.get(today)
        if lst is None:                      # not a rebalance day -> hold
            return []
        prices = {}
        prev = context.prev_day_data
        if prev is not None and not prev.empty:
            prices = prev.set_index("ts_code")["close"].astype(float).to_dict()

        def tradable(code):
            p = prices.get(code)
            return p is not None and np.isfinite(p) and p > 0

        picks = []
        for item in lst:
            code, mv = (item[0], item[1]) if isinstance(item, (list, tuple)) else (item, np.nan)
            if len(picks) >= self.max_holds:
                break
            if tradable(code) and np.isfinite(mv) and mv > 0:
                picks.append((code, mv))
        if not picks:
            return _emit_rebalance_orders({}, context)   # empty period -> all cash (bond-ETF approx)
        if self.weights_mode == "explicit":
            # RAW recorded weights — do NOT normalize: Model-II books hold partial exposure + CASH when
            # few names qualify (#8: n=1 periods carry Σw≈0.19 — normalizing to 100% quintupled crash
            # exposure and blew the replay MDD to −50%). Σw≈1 books (#7) are unaffected (raw == normed).
            tot = sum(mv for _, mv in picks)
            scale = 1.0 / tot if tot > 1.001 else 1.0
            target = {code: float(mv * scale) for code, mv in picks}
        else:
            w = np.sqrt(np.array([mv for _, mv in picks]))
            w = w / w.sum()
            target = {code: float(x) for (code, _), x in zip(picks, w)}
        return _emit_rebalance_orders(target, context)


def _replay_schedule(end="2026-02-27") -> dict:
    """果仁's EXACT held names + its OWN 本期起始仓位 weights per period (incl. explicit EMPTY periods
    from 调仓详情 股票只数=0) — the replay decomposition input (selection vs execution split)."""
    h = pd.read_excel(XLSX, sheet_name="各阶段持仓详单")
    h["start"] = pd.to_datetime(h["开始日期"], errors="coerce")
    h["code"] = h["股票代码"].astype(str).str.zfill(6)
    h = h[h["start"].notna() & (h["start"] <= pd.Timestamp(end))]
    sched = {}
    for d, grp in h.groupby("start"):
        rows = []
        for _, r in grp.iterrows():
            w = pd.to_numeric(r.get("本期起始仓位"), errors="coerce")
            if pd.notna(w) and w > 0:
                c = r["code"]
                suffix = "SH" if c[0] == "6" else "SZ"
                rows.append([f"{c}.{suffix}", float(w)])
        sched[str(d.date())] = rows
    t = pd.read_excel(XLSX, sheet_name="调仓详情")
    t["d"] = pd.to_datetime(t["开始日期"], errors="coerce")
    for _, r in t.iterrows():
        if pd.notna(r["d"]) and r["d"] <= pd.Timestamp(end) and int(r["股票只数"]) == 0:
            sched.setdefault(str(r["d"].date()), [])
    return sched


def run(start="2014-01-02", end="2026-02-27", cost_side=0.002, net_name="verify07_net.parquet",
        replay=False):
    from src.backtest_engine.event_driven import EventDrivenBacktester, CostConfig
    from src.backtest_engine.event_driven.exchange import FixedSlippage
    if replay:
        sched = _replay_schedule(end)
        net_name = "verify07_replay_net.parquet"
        strat = ModelIDivLowVolStrategy(sched, max_holds=99, weights_mode="explicit")
    else:
        sched = json.loads(SCHED.read_text(encoding="utf-8"))
        strat = ModelIDivLowVolStrategy(sched, max_holds=10, reserve=10)
    cost = CostConfig(buy_commission=cost_side, sell_commission=cost_side, stamp_tax=0.0,
                      min_commission=0.0, transfer_fee=0.0)
    bt = EventDrivenBacktester(data_dir=str(ROOT / "data"))
    # The $limit_status cache-key-rotation workaround (task_5a0289dc) is REMOVED:
    # the M4 rotation self-heal (GPT 3-round SHIP 2026-07-02) lets the door
    # recompute + re-bind a stale-generation key, so the natural field set works.
    res = bt.run(strategy=strat, start_time=start, end_time=end, benchmark="000300.SH",
                 account=1_000_000.0, exchange_config=cost, slippage=FixedSlippage(0.0),
                 volume_limit=0.10, hold_on_limit_up=True,
                 preload_fields=["$open", "$close", "$high", "$low", "$vol", "$amount", "$pre_close",
                                 "$adj_factor", "$up_limit", "$down_limit"])
    rep = res.report.copy()
    if "date" in rep.columns:
        rep = rep.set_index(pd.to_datetime(rep["date"]))
    net = rep["return"].astype(float)
    net.to_frame("net").to_parquet(OUT / net_name)
    m = ru.goal_metrics(net)
    yr = net.groupby(net.index.year).apply(lambda r: (1 + r).prod() - 1)
    gdf = pd.read_excel(XLSX, sheet_name="年度收益统计", header=0)
    gy = {}
    for _, r in gdf.iterrows():
        try:
            y = int(str(r.iloc[0])[:4])
        except Exception:
            continue
        v = pd.to_numeric(r.iloc[1], errors="coerce")
        if pd.notna(v):
            gy[y] = float(v)
    print("\n" + "=" * 72)
    tag = "REPLAY(果仁持仓+果仁权重)" if replay else "LOCAL selection"
    print(f"  #7 value_红利低波_v2 [{tag}]  CAGR={m['cagr']:+.2%}  MDD={m['mdd']:+.2%}  (果仁 +29.73% / −21.04)")
    print(f"  cost={cost_side*1e4:.0f}bp/side  fill=open(≈10:00 approx)  idle-cash≈bond-ETF omission")
    print("  year     LOCAL      果仁      diff")
    for y in sorted(yr.index):
        g = gy.get(int(y))
        gt = f"{g:+8.1%}" if g is not None else "   n/a "
        dt = f"{float(yr[y]) - g:+7.1%}" if g is not None else ""
        print(f"  {int(y)}   {float(yr[y]):+8.1%}  {gt}  {dt}")
    json.dump({"cagr": m["cagr"], "mdd": m["mdd"], "yearly": {int(k): float(v) for k, v in yr.items()},
               "guorn_yearly": gy, "cost_side": cost_side, "replay": replay},
              open(OUT / ("verify07_replay_result.json" if replay else "verify07_result.json"),
                   "w", encoding="utf-8"), ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- holdings tracking ---------------
def compare(end="2026-02-27"):
    h = pd.read_excel(XLSX, sheet_name="各阶段持仓详单")
    h["start"] = pd.to_datetime(h["开始日期"], errors="coerce")
    h["code"] = h["股票代码"].astype(str).str.zfill(6)
    h = h[h["start"].notna() & (h["start"] <= pd.Timestamp(end))]
    s = {pd.Timestamp(k): v for k, v in json.loads(SCHED.read_text(encoding="utf-8")).items()}

    def code6(item):
        c = item[0] if isinstance(item, (list, tuple)) else item
        return str(c).split("_")[0].split(".")[0].zfill(6)

    rows = []
    for d, grp in h.groupby("start"):
        lst = s.get(d)
        if lst is None:
            continue
        held = set(grp["code"])
        order = {code6(c): i + 1 for i, c in enumerate(lst)}
        rks = [order.get(c, 999) for c in held]
        # my Model-I book = first min(10, len) codes; precision exposes EXTRAS (this book's eligible
        # set is tiny — 果仁 holding 2 while I select 4 is invisible to recall alone)
        my_book = [code6(c) for c in lst[:10]]
        prec = float(np.mean([c in held for c in my_book])) if my_book else np.nan
        rows.append(dict(date=d, n=len(held), n_mine=len(my_book), med_rank=float(np.median(rks)),
                         in10=float(np.mean([r <= 10 for r in rks])),
                         in20=float(np.mean([r <= 20 for r in rks])), precision=prec))
    df = pd.DataFrame(rows)
    df["year"] = df["date"].dt.year
    print("\n=== #7 果仁-held tracking (recall = held∈my-topK; precision = my-book∈held) ===")
    print(df[["in10", "in20", "precision"]].mean().round(3).to_string())
    print("\nby year:")
    print(df.groupby("year")[["in10", "in20", "precision"]].mean().round(3).to_string())
    print("\ncount comparison (果仁 n vs my selected n):")
    print(pd.crosstab(df["n"].clip(upper=10), df["n_mine"].clip(upper=10)).to_string())
    # empty-period agreement: 果仁 empty periods vs local empty
    t = pd.read_excel(XLSX, sheet_name="调仓详情")
    t["d"] = pd.to_datetime(t["开始日期"], errors="coerce")
    t = t[t["d"].notna() & (t["d"] <= pd.Timestamp(end))]
    g_empty = set(t[t["股票只数"] == 0]["d"])
    l_empty = {k for k, v in s.items() if not v}
    both = len(g_empty & l_empty)
    print(f"\nempty periods: 果仁={len(g_empty)}  local={len(l_empty)}  overlap={both}")
    df.to_parquet(OUT / "verify07_holdcmp.parquet")


def diag(end="2026-02-27"):
    """Miss/extra decomposition per screen (the validated 成长簇 method): for 果仁-held names absent
    from my book — which LOCAL screen killed them (screen-miss) or did they rank below 10 (rank-miss);
    for my extras — which screens they only marginally passed (candidates for 果仁's two omitted
    proprietary screens or a mis-calibrated boundary)."""
    f, e, l2 = _load_frames()
    cgb = _cgb_series()
    close = e["close_raw"]
    grid = close.index
    insts = close.columns
    bounds = _bounds()
    h = pd.read_excel(XLSX, sheet_name="各阶段持仓详单")
    h["start"] = pd.to_datetime(h["开始日期"], errors="coerce")
    h["code"] = h["股票代码"].astype(str).str.zfill(6)
    h = h[h["start"].notna() & (h["start"] <= pd.Timestamp(end))]
    s = {pd.Timestamp(k): v for k, v in json.loads(SCHED.read_text(encoding="utf-8")).items()}
    up = {str(c).split("_")[0]: c for c in insts}

    def code6(item):
        c = item[0] if isinstance(item, (list, tuple)) else item
        return str(c).split("_")[0].split(".")[0].zfill(6)

    miss_kill = {}          # screen -> count (over missed held names)
    extra_margin = {}       # screen -> count of extras within 5pp of that screen's cutoff
    n_miss = n_rankmiss = n_nobase = n_extra = 0
    for d, grp in h.groupby("start"):
        lst = s.get(pd.Timestamp(d))
        if lst is None:
            continue
        pos = grid.searchsorted(pd.Timestamp(d))
        if pos == 0:
            continue
        pday = grid[pos - 1]
        held = set(grp["code"])
        my_book = [code6(c) for c in lst[:10]]
        st = ru.st_codes_on(d)
        cr = close.loc[pday]
        not_st = pd.Series([str(c).upper() not in st for c in insts], index=insts)
        listed = pd.Series([(bounds.get(str(c).upper()) is not None
                             and bounds[str(c).upper()][0] <= pday <= bounds[str(c).upper()][1])
                            for c in insts], index=insts)
        rank_base = listed & cr.notna() & not_st
        l2row = _row(l2, pday).replace({"nan": np.nan, "None": np.nan})
        _zr = e["zsfz"].loc[pday].where(rank_base)
        _zrank = _zr.groupby(l2row).rank(method="min")
        _zN = l2row.map(_zr.groupby(l2row).count())
        zpct = _zrank / _zN.where(_zN > 0)
        zceil = ~(_zrank > np.ceil(0.50 * _zN)).fillna(False)
        bpct = e["beta"].loc[pday].where(rank_base).rank(pct=True)
        spct = e["sharesgr"].loc[pday].where(rank_base).rank(pct=True)
        rpct = e["ret250"].loc[pday].where(rank_base).rank(pct=True)
        gpct = _row(e["divgr"], pday).where(rank_base).rank(pct=True, ascending=False)
        cpos = cgb.index.searchsorted(pd.Timestamp(d), side="right")
        cval = float(cgb.iloc[cpos - 1]) if cpos > 0 else np.nan
        dy = _row(f["dyttm"], pday)
        idxf = _row(e["idxflag"], pday).fillna(0).astype(int)
        screens = {
            "zsfz50_L2": zceil,
            "beta50": ~(bpct > 0.50).fillna(False),
            "sharesgr60": ~(spct > 0.60).fillna(False),
            "ret250_95": ~(rpct > 0.95).fillna(False),
            "divgr_max60": (gpct <= 0.60).fillna(False),
            "dy_minus_cgb": ((dy - cval) > 0.02).fillna(False),
            "idxflag": idxf == 0,
            "close_ge2": (cr >= 2.0).fillna(False),
        }
        # ---- misses
        for c in held - set(my_book):
            inst = up.get(c)
            n_miss += 1
            if inst is None or not bool(rank_base.get(inst, False)):
                n_nobase += 1
                continue
            failed = [k for k, m in screens.items() if not bool(m.get(inst, False))]
            if failed:
                for k in failed:
                    miss_kill[k] = miss_kill.get(k, 0) + 1
            else:
                n_rankmiss += 1
        # ---- extras: margin profile
        margins = {
            "zsfz50_L2": (0.50 - zpct), "beta50": (0.50 - bpct), "sharesgr60": (0.60 - spct),
            "ret250_95": (0.95 - rpct), "divgr_max60": (0.60 - gpct), "dy_minus_cgb": (dy - cval - 0.02),
        }
        for c in set(my_book) - held:
            inst = up.get(c)
            n_extra += 1
            if inst is None:
                continue
            for k, mg in margins.items():
                v = mg.get(inst, np.nan)
                thr = 0.005 if k == "dy_minus_cgb" else 0.05
                if pd.notna(v) and 0 <= float(v) <= thr:
                    extra_margin[k] = extra_margin.get(k, 0) + 1
            # NaN-keep profile: extras admitted only because a screen factor is NaN (kept by policy)
            for k, fr_ in (("beta_nan", e["beta"].loc[pday]), ("sharesgr_nan", e["sharesgr"].loc[pday]),
                           ("ret250_nan", e["ret250"].loc[pday]), ("zsfz_nan", e["zsfz"].loc[pday])):
                if pd.isna(fr_.get(inst, np.nan)):
                    extra_margin[k] = extra_margin.get(k, 0) + 1
    print(f"\n=== #7 miss/extra per-screen decomposition ===")
    print(f"misses (果仁 held, not in my book): {n_miss}  |  no-rank-base {n_nobase}  rank-miss {n_rankmiss}")
    for k, v in sorted(miss_kill.items(), key=lambda kv: -kv[1]):
        print(f"  screen-miss {k:14} {v}")
    print(f"extras (my book, 果仁 not held): {n_extra}; of which within-margin counts (multi-count):")
    for k, v in sorted(extra_margin.items(), key=lambda kv: -kv[1]):
        print(f"  near-boundary {k:14} {v}")


def replay_diag(end="2026-02-27", top=25):
    """Per-PERIOD replay return vs 果仁's own 调仓详情 本期收益 — localizes the execution residual to
    specific periods (limit-up fills / suspension pricing / dividend credits / fill-time)."""
    net = pd.read_parquet(OUT / "verify07_replay_net.parquet")["net"]
    net.index = pd.to_datetime(net.index)
    t = pd.read_excel(XLSX, sheet_name="调仓详情")
    t["d0"] = pd.to_datetime(t["开始日期"], errors="coerce")
    t["d1"] = pd.to_datetime(t["结束日期"], errors="coerce")
    t = t[(t["d0"].notna()) & (t["d0"] <= pd.Timestamp(end))]
    rows = []
    for _, r in t.iterrows():
        # period return convention: xlsx 本期收益 spans 开始日期(exclusive of prior close)..结束日期;
        # local: compound daily returns in (d0, d1]
        m = (net.index > r["d0"]) & (net.index <= r["d1"])
        if not m.any():
            continue
        lr = float((1 + net[m]).prod() - 1)
        gr = pd.to_numeric(r["本期收益"], errors="coerce")
        if pd.isna(gr):
            continue
        rows.append(dict(d0=r["d0"], d1=r["d1"], n=int(r["股票只数"]), turn=float(r["换手率"]),
                         local=lr, guorn=float(gr), diff=lr - float(gr)))
    df = pd.DataFrame(rows)
    df["year"] = df["d0"].dt.year
    print(f"periods joined: {len(df)};  mean diff {df['diff'].mean():+.4f}  median {df['diff'].median():+.4f}")
    print("\nyearly sum of period diffs (≈ execution residual attribution):")
    print(df.groupby("year")["diff"].agg(["sum", "mean", "count"]).round(4).to_string())
    print(f"\ntop {top} divergent periods:")
    cols = ["d0", "d1", "n", "turn", "local", "guorn", "diff"]
    print(df.reindex(df["diff"].abs().sort_values(ascending=False).index)[cols].head(top)
          .to_string(index=False))
    df.to_parquet(OUT / "verify07_replay_perperiod.parquet")


def autopsy(year: int, end="2026-02-27"):
    """Period-by-period selection autopsy for one YEAR: 果仁 book vs my book; per-miss killing screen
    (with margin); empty-period mismatches with the extras' dy−CGB margins. The tight-year lever finder."""
    f, e, l2 = _load_frames()
    if (CACHE / "f_neutturn_v2.parquet").exists():
        f["neutturn"] = pd.read_parquet(CACHE / "f_neutturn_v2.parquet").reindex(columns=e["close_raw"].columns)
    cgb = _cgb_series()
    close = e["close_raw"]
    grid = close.index
    insts = close.columns
    bounds = _bounds()
    h = pd.read_excel(XLSX, sheet_name="各阶段持仓详单")
    h["start"] = pd.to_datetime(h["开始日期"], errors="coerce")
    h["code"] = h["股票代码"].astype(str).str.zfill(6)
    h = h[h["start"].notna() & (h["start"] <= pd.Timestamp(end))]
    held_by_d = {d: set(g["code"]) for d, g in h.groupby("start")}
    s = {pd.Timestamp(k): v for k, v in json.loads(SCHED.read_text(encoding="utf-8")).items()}
    up = {str(c).split("_")[0]: c for c in insts}
    name_by_code = dict(zip(h["code"], h["股票名"]))

    def code6(item):
        c = item[0] if isinstance(item, (list, tuple)) else item
        return str(c).split("_")[0].split(".")[0].zfill(6)

    for d in sorted(s):
        if d.year != year:
            continue
        pos = grid.searchsorted(d)
        if pos == 0:
            continue
        pday = grid[pos - 1]
        held = held_by_d.get(d, set())
        my_book = [code6(c) for c in s[d][:10]]
        if set(my_book) == held:
            continue
        st = ru.st_codes_on(d)
        cr = close.loc[pday]
        not_st = pd.Series([str(c).upper() not in st for c in insts], index=insts)
        listed = pd.Series([(bounds.get(str(c).upper()) is not None
                             and bounds[str(c).upper()][0] <= pday <= bounds[str(c).upper()][1])
                            for c in insts], index=insts)
        rank_base = listed & cr.notna() & not_st
        l2row = _row(l2, pday).replace({"nan": np.nan, "None": np.nan})
        _zr = e["zsfz"].loc[pday].where(rank_base)
        _zrank = _zr.groupby(l2row).rank(method="min")
        _zN = l2row.map(_zr.groupby(l2row).count())
        bpct = e["beta"].loc[pday].where(rank_base).rank(pct=True)
        spct = e["sharesgr"].loc[pday].where(rank_base).rank(pct=True)
        rpct = e["ret250"].loc[pday].where(rank_base).rank(pct=True)
        gpct = _row(e["divgr"], pday).where(rank_base).rank(pct=True, ascending=False)
        cpos = cgb.index.searchsorted(d, side="right")
        cval = float(cgb.iloc[cpos - 1]) if cpos > 0 else np.nan
        dy = _row(f["dyttm"], pday)
        idxf = _row(e["idxflag"], pday).fillna(0).astype(int)

        def screen_report(inst):
            fails = []
            zr_, zn_ = _zrank.get(inst, np.nan), _zN.get(inst, np.nan)
            if pd.notna(zr_) and zr_ > np.ceil(0.50 * zn_):
                fails.append(f"zsfz(rk{int(zr_)}/{int(zn_)})")
            if (bpct.get(inst, np.nan) or 0) > 0.50:
                fails.append(f"beta({bpct[inst]:.2f})")
            if (spct.get(inst, np.nan) or 0) > 0.60:
                fails.append(f"shr({spct[inst]:.2f})")
            if (rpct.get(inst, np.nan) or 0) > 0.95:
                fails.append(f"ret250({rpct[inst]:.2f})")
            g_ = gpct.get(inst, np.nan)
            if pd.isna(g_) or g_ > 0.60:
                fails.append(f"divgr({'nan' if pd.isna(g_) else f'{g_:.2f}'})")
            dm = dy.get(inst, np.nan) - cval
            if pd.isna(dm) or dm <= 0.02:
                fails.append(f"dyCGB({'nan' if pd.isna(dm) else f'{dm:+.3f}'})")
            if int(idxf.get(inst, 0)) != 0:
                fails.append("idx10")
            if pd.isna(cr.get(inst, np.nan)):
                fails.append("suspended")
            elif cr[inst] < 2.0:
                fails.append("close<2")
            if not bool(not_st.get(inst, True)):
                fails.append("ST")
            return fails

        miss = held - set(my_book)
        extra = set(my_book) - held
        line = f"{d.date()}  果仁 n={len(held)}  mine n={len(my_book)}"
        det = []
        for c in sorted(miss):
            inst = up.get(c)
            nm = name_by_code.get(c, "")
            if inst is None or not bool(rank_base.get(inst, False)):
                det.append(f"  MISS {c} {nm}: not-in-rank-base")
                continue
            fl = screen_report(inst)
            det.append(f"  MISS {c} {nm}: {'|'.join(fl) if fl in ([],) or fl else 'RANK-MISS'}"
                       if fl else f"  MISS {c} {nm}: RANK-MISS")
        for c in sorted(extra):
            inst = up.get(c)
            dm = (dy.get(inst, np.nan) - cval) if inst else np.nan
            det.append(f"  XTRA {c}: dyCGB{'' if pd.isna(dm) else f'{dm:+.3f}'}")
        print(line)
        for x in det:
            print(x)


def main():
    ap = argparse.ArgumentParser()
    for flag in ("build-base", "build-fin", "build-beta", "build-div", "selftest-div", "build-neut",
                 "build-l2", "build-idx", "schedule", "factor-parity", "run", "compare", "diag",
                 "replay", "replay-diag"):
        ap.add_argument(f"--{flag}", action="store_true")
    ap.add_argument("--end", default="2026-02-27")
    ap.add_argument("--cost", type=float, default=0.002)
    ap.add_argument("--neutturn", default="v1", choices=("v1", "v2", "v3", "v4", "v5"))
    ap.add_argument("--autopsy", type=int, default=0, metavar="YEAR")
    a = ap.parse_args()
    if a.build_base:
        build_base(end=a.end)
    if a.build_fin:
        build_fin()
    if a.build_beta:
        build_beta()
    if a.selftest_div:
        selftest_div()
    if a.build_div:
        build_div(a.end)
    if a.build_neut:
        build_neut(a.end)
    if a.build_l2:
        build_l2(a.end)
    if a.build_idx:
        build_idx(a.end)
    if a.schedule:
        build_schedule(a.end, neutturn_variant=a.neutturn)
    if a.factor_parity:
        factor_parity(a.end)
    if a.run:
        run(end=a.end, cost_side=a.cost)
    if a.replay:
        run(end=a.end, cost_side=a.cost, replay=True)
    if a.replay_diag:
        replay_diag(a.end)
    if a.autopsy:
        autopsy(a.autopsy, a.end)
    if a.compare:
        compare(a.end)
    if a.diag:
        diag(a.end)


if __name__ == "__main__":
    main()
