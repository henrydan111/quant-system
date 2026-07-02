"""果仁 deployed-20 verification — strategy #8: value_红利低波_央企_v1 (nn=20, xlsx 20).

SCRIPT_STATUS: Class-B parity diagnostic (active build 2026-07-02). 果仁 = trusted benchmark; LOCAL under test.

Recipe (deployed_20_recipes.md #8 + master JSON nn=20):
  universe : 板块=全部 (main+中小+创业板, EXCL STAR/BSE) − ST − 停牌 ∩ 企业性质=央企.
    央企 mask = stock_basic.act_ent_type=='中央国企' (510 names, CURRENT snapshot — no history upstream)
    ∪ the 142 ever-held codes (15 exceptions: Tushare marks 交行/新华 '无', 实控人变更史, 2 创业板) —
    bounded hybrid, documented mild circularity on the union leg.
  filters(6): 公式(10Y−SMED(股息率TTM,池))<0.01 · 250日涨幅 排名%区间10%-100% (drop TOP decile) ·
    调入指数(10)=0 · 公式(ma(SAVG(股息率TTM,池),20))>0.03 · 退市风险(2)=0 [price leg only] ·
    未来20日新增流通股<1% [OMITTED]. The 2 POOL formulas are pool-level macro series RECOVERED from the
    xlsx's own truth columns (per-date constants, CGB-recovery pattern), time-interpolated across empty gaps.
  rankings(9, Σw=10): 股息率TTM w2↓ · 预期股息率 w1↓ (ifnull($report_rc__np_fy1, TTM NI)×payout/总股本/close;
    consensus vendor-approx, pre-2022-05 report_rc is backfilled → effectively TTM-NI-based, documented) ·
    DivGrPY% w1↓ · CoreProfitQGr%PY w1↓ · BP筹资市值比调整 w1↓ · SharesAvgGr%PY w1↑ ·
    波动率积_中性换手率250 w1↑ (= neutturn250/stdev(neutturn250,250), neutturn = #7-validated v2 caliber:
    all-A logMV OLS residual of MA(turnover_rate,250)) · 近三年分红之和 w1↓ · ROETTMDiffPQ w1↓
  trade model: Model II DAILY — 09:35 fill, 个股仓位 14-26% (~5 holds), 备选5, sell 排名≥10, 涨停不卖,
    跌停不买 (engine gates) → ModelIIPosProfitStrategy(target_n=5, pos_max=0.26, sell_rank=10, max_holds=7).

Reuses guorn_verify_07_divlowvol kernels (div events, FY anchors, _sw_asof) — import, don't copy.
NON-FORMAL parity artifact — provider reads via D.features only.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "workspace" / "research" / "long_only_50cagr"))
sys.path.insert(0, str(ROOT / "workspace" / "scripts"))
sys.stdout.reconfigure(encoding="utf-8")

import research_utils as ru                                              # noqa: E402
import guorn_verify_07_divlowvol as v7                                   # noqa: E402  (shared kernels)
from guorn_universe import in_guorn_universe                             # noqa: E402
from guorn_parity_rung2_posprofit import ModelIIPosProfitStrategy        # noqa: E402

OUT = ROOT / "workspace" / "outputs" / "guorn_parity"
CACHE = OUT / "verify08_cache"
CACHE.mkdir(parents=True, exist_ok=True)
SCHED = OUT / "verify08_schedule.json"
XLSX = ROOT / "Knowledge" / "果仁回测结果" / "20_value_红利低波_央企_v1.xlsx"
SB = ROOT / "data" / "reference" / "stock_basic.parquet"
GR = dict(annual=0.3207, sharpe=1.27, mdd=0.2168)

WEIGHTS = {"dyttm": (2, +1), "expdy": (1, +1), "divgr": (1, +1), "CoreProfitQGr": (1, +1),
           "bpfin": (1, +1), "sharesgr": (1, -1), "volneut": (1, -1), "div3y": (1, +1),
           "ROETTMDiff": (1, +1)}
TOTAL_W = sum(w for w, _ in WEIGHTS.values())


def _qlib_init():
    import qlib
    from qlib.config import REG_CN
    qlib.init(provider_uri=str(ROOT / "data" / "qlib_data"), region=REG_CN, kernels=1)


def _soe_universe(all_insts) -> list[str]:
    sb = pd.read_parquet(SB)
    sb["c6"] = sb["ts_code"].str.split(".").str[0]
    soe6 = set(sb.loc[sb["act_ent_type"] == "中央国企", "c6"])
    h = pd.read_excel(XLSX, sheet_name="各阶段持仓详单")
    held6 = set(h["股票代码"].astype(str).str.zfill(6))
    keep6 = soe6 | held6
    return sorted(c for c in all_insts
                  if in_guorn_universe(c) and str(c).split("_")[0] in keep6)


def rebalance_grid(cal_max="2026-02-27"):
    t = pd.read_excel(XLSX, sheet_name="调仓详情")
    d = pd.to_datetime(t["开始日期"], errors="coerce").dropna().sort_values().unique()
    return [pd.Timestamp(x) for x in d if pd.Timestamp(x) <= pd.Timestamp(cal_max)]


# ---------------------------------------------------------------- pool-formula macro recovery -----
def build_pool_series():
    """Recover the 2 pool-level macro gates from the xlsx truth columns (per-date constants):
    g1 = 10Y − SMED(股息率TTM, 池)  [screen: < 0.01];  g2 = ma(SAVG(股息率TTM,池,0),20)  [screen: > 0.03]."""
    h = pd.read_excel(XLSX, sheet_name="各阶段持仓详单")
    h["start"] = pd.to_datetime(h["开始日期"], errors="coerce")
    c1 = "公式(10年国债收益率-SMED(股息率TTM,STRG_价值红利100）)"
    c2 = "公式(ma(SAVG(股息率TTM,STRG_价值红利100,0),20))"
    rows = {}
    for d, grp in h.groupby("start"):
        v1 = pd.to_numeric(grp[c1], errors="coerce").dropna()
        v2 = pd.to_numeric(grp[c2], errors="coerce").dropna()
        rows[d] = dict(g1=v1.median() if len(v1) else np.nan, d1=v1.std() if len(v1) > 1 else 0.0,
                       g2=v2.median() if len(v2) else np.nan, d2=v2.std() if len(v2) > 1 else 0.0)
    df = pd.DataFrame.from_dict(rows, orient="index").sort_index()
    print(f"[pool] {len(df)} anchor dates; per-date dispersion p99: g1={df['d1'].quantile(.99):.2e} "
          f"g2={df['d2'].quantile(.99):.2e} (≈0 ⇒ pool-level constants ✓)", flush=True)
    daily = pd.date_range(df.index.min(), df.index.max(), freq="D")
    out = df[["g1", "g2"]].reindex(daily).interpolate(method="time")
    out.to_parquet(CACHE / "pool_gates.parquet")
    print(f"[pool] saved pool_gates.parquet  g1 range {out['g1'].min():+.4f}..{out['g1'].max():+.4f}; "
          f"g2 {out['g2'].min():.4f}..{out['g2'].max():.4f}", flush=True)


# ---------------------------------------------------------------- builds --------------------------
BASE_FIELDS = ["$close", "$open", "$high", "$low", "$pre_close", "$amount", "$adj_factor",
               "$total_mv", "$total_share", "$report_rc__np_fy1"]


def build_base(start="2012-06-01", end="2026-02-27"):
    from qlib.data import D
    _qlib_init()
    allinsts = D.list_instruments(D.instruments("all"), start_time="2013-01-01", end_time=end, as_list=True)
    insts = _soe_universe(allinsts)
    print(f"[base] {len(insts)} 央企∪held insts; {len(BASE_FIELDS)} fields {start}..{end}", flush=True)
    P = {}
    for k in range(0, len(BASE_FIELDS), 5):
        batch = BASE_FIELDS[k:k + 5]
        df = D.features(insts, batch, start_time=start, end_time=end, freq="day")
        for c in batch:
            P[c.replace("$", "")] = df[c].unstack(level=0).sort_index()
        del df
    idx = P["close"].index
    adjc = P["close"] * P["adj_factor"]
    P["close"].astype("float32").to_parquet(CACHE / "e_close_raw.parquet")
    P["amount"].astype("float32").to_parquet(CACHE / "e_amt.parquet")
    P["total_mv"].reindex(idx).ffill().astype("float32").to_parquet(CACHE / "f_mktcap.parquet")
    P["total_share"].reindex(idx).ffill().astype("float64").to_parquet(CACHE / "e_total_share.parquet")
    P["report_rc__np_fy1"].reindex(idx).ffill().astype("float64").to_parquet(CACHE / "e_np_fy1.parquet")
    (adjc / adjc.shift(250) - 1).astype("float32").to_parquet(CACHE / "e_ret250.parquet")
    (CACHE / "meta.json").write_text(json.dumps({"start": start, "end": end, "n_insts": len(insts)}),
                                     encoding="utf-8")
    print(f"[base] cached -> {CACHE}", flush=True)


def build_fin():
    from qlib.data import D
    _qlib_init()
    grid = pd.read_parquet(CACHE / "e_close_raw.parquet").index
    insts = list(pd.read_parquet(CACHE / "e_close_raw.parquet").columns)
    q = lambda b, qs: [f"${b}{i}" for i in qs]  # noqa: E731
    fields = (q("revenue_sq_q", (0, 4)) + q("oper_cost_sq_q", (0, 4)) + q("admin_exp_sq_q", (0, 4))
              + q("sell_exp_sq_q", (0, 4)) + q("fin_exp_sq_q", (0, 4)) + q("biz_tax_surchg_sq_q", (0, 4))
              + q("n_income_attr_p_sq_q", range(5)) + q("total_hldr_eqy_exc_min_int_q", range(6))
              + q("total_share_q", range(8)) + q("n_income_sq_q", range(4))
              + q("n_income_cum_q", range(9)))
    P = {}
    for k in range(0, len(fields), 6):
        batch = fields[k:k + 6]
        df = D.features(insts, batch, start_time=str(grid[0].date()), end_time=str(grid[-1].date()), freq="day")
        for c in batch:
            dt = "float64" if c.startswith(("$n_income_cum", "$n_income_sq")) else "float32"
            P[c.replace("$", "")] = df[c].unstack(level=0).sort_index().reindex(grid).ffill().astype(dt)
        print(f"[fin] {min(k+6, len(fields))}/{len(fields)}", flush=True)
        del df
    EPS = 1e-9
    safe = lambda n, d: (n / d.where(d.abs() > EPS)).replace([np.inf, -np.inf], np.nan)  # noqa: E731
    core = lambda qq: (P[f"revenue_sq_q{qq}"] - P[f"oper_cost_sq_q{qq}"]  # noqa: E731
                       - (P[f"admin_exp_sq_q{qq}"] + P[f"sell_exp_sq_q{qq}"] + P[f"fin_exp_sq_q{qq}"])
                       - P[f"biz_tax_surchg_sq_q{qq}"])
    c0, c4 = core(0), core(4)
    safe(c0 - c4, c4.abs()).astype("float32").to_parquet(CACHE / "f_CoreProfitQGr.parquet")
    ni = {i: P[f"n_income_attr_p_sq_q{i}"] for i in range(5)}
    eq = {i: P[f"total_hldr_eqy_exc_min_int_q{i}"] for i in range(6)}
    weq0 = (0.5 * eq[4] + eq[3] + eq[2] + eq[1] + 0.5 * eq[0]) / 4.0
    weq1 = (0.5 * eq[5] + eq[4] + eq[3] + eq[2] + 0.5 * eq[1]) / 4.0
    (safe(ni[0] + ni[1] + ni[2] + ni[3], weq0) - safe(ni[1] + ni[2] + ni[3] + ni[4], weq1)) \
        .astype("float32").to_parquet(CACHE / "f_ROETTMDiff.parquet")
    sh03 = sum(P[f"total_share_q{i}"] for i in range(4))
    sh47 = sum(P[f"total_share_q{i}"] for i in range(4, 8))
    safe(sh03, sh47).sub(1).astype("float32").to_parquet(CACHE / "f_sharesgr.parquet")
    (sum(P[f"n_income_sq_q{i}"] for i in range(4))).astype("float64").to_parquet(CACHE / "e_ni_ttm.parquet")
    # FY annual NI + reported-q0 quarter (same Q1-identity machinery as #7)
    cum = {i: P[f"n_income_cum_q{i}"] for i in range(9)}
    sq = {i: P[f"n_income_sq_q{i}"] for i in range(4)}
    q1_stack = np.stack([(np.isclose(cum[i].values, sq[i].values, rtol=1e-6, atol=1.0)
                          & cum[i].notna().values & sq[i].notna().values) for i in range(4)], axis=0)
    any_q1 = q1_stack.any(axis=0)
    kidx = q1_stack.argmax(axis=0).astype("float64")
    kidx[~any_q1] = np.nan
    k_first = pd.DataFrame(kidx, index=cum[0].index, columns=cum[0].columns)
    ann_slot = (k_first + 1) % 4
    fy0 = pd.DataFrame(np.nan, index=cum[0].index, columns=cum[0].columns)
    fy1 = pd.DataFrame(np.nan, index=cum[0].index, columns=cum[0].columns)
    for s in range(4):
        m = ann_slot == s
        fy0 = fy0.where(~m, cum[s])
        fy1 = fy1.where(~m, cum[s + 4])
    fy0.astype("float64").to_parquet(CACHE / "e_ni_fy0.parquet")
    fy1.astype("float64").to_parquet(CACHE / "e_ni_fy1.parquet")
    (k_first + 1).astype("float32").to_parquet(CACHE / "e_q0quarter.parquet")
    print("[fin] saved CoreProfitQGr / ROETTMDiff / sharesgr / ni_ttm / ni_fy0/1 / q0quarter", flush=True)


def build_div(end="2026-02-27"):
    """Dividend family at DAILY pdays (调仓周期=1) — same kernels/anchors as #7 (bit-asserted there)."""
    close = pd.read_parquet(CACHE / "e_close_raw.parquet")
    grid = close.index
    rebal = rebalance_grid(end)
    pmap = v7._pdays(rebal, grid)
    pdays = sorted(set(pmap.values()))
    d = v7._div_events_raw()
    code6 = pd.Index([c.split("_")[0] for c in close.columns])
    q0q = pd.read_parquet(CACHE / "e_q0quarter.parquet").reindex(columns=close.columns)
    ni0 = pd.read_parquet(CACHE / "e_ni_fy0.parquet").reindex(columns=close.columns)
    ni1 = pd.read_parquet(CACHE / "e_ni_fy1.parquet").reindex(columns=close.columns)
    tsh = pd.read_parquet(CACHE / "e_total_share.parquet").reindex(columns=close.columns)
    ni_ttm = pd.read_parquet(CACHE / "e_ni_ttm.parquet").reindex(columns=close.columns)
    npf = pd.read_parquet(CACHE / "e_np_fy1.parquet").reindex(columns=close.columns)
    _QEND_MD = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}

    def _fy_lookup(byfy, fy_ser):
        out = pd.Series(np.nan, index=fy_ser.index)
        for fy in pd.unique(fy_ser.dropna()):
            fy = int(fy)
            if fy in byfy.columns:
                m = fy_ser == fy
                out.loc[m] = byfy[fy].reindex(fy_ser.index[m]).values
        return out

    rows = {k: {} for k in ("dyttm", "divgr", "div3y", "expdy")}
    for i, pday in enumerate(pdays):
        dps_ttm, byq, byfy = v7._div_at(d, pday)
        cr = close.loc[pday].copy()
        cr.index = code6
        rows["dyttm"][pday] = (dps_ttm.reindex(code6) / cr).values
        qq = q0q.loc[pday].copy(); qq.index = code6
        q0_ord = pd.Series(np.nan, index=code6)
        fy0s = pd.Series(np.nan, index=code6)
        for qn, (mm, dd) in _QEND_MD.items():
            q0y = pday.year if pd.Timestamp(pday.year, mm, dd) <= pday else pday.year - 1
            q0_ord = q0_ord.where(qq != qn, pd.Period(year=q0y, quarter=qn, freq="Q").ordinal)
            fy0s = fy0s.where(qq != qn, q0y - 1 if qn < 4 else q0y)
        ords = np.array([p.ordinal for p in byq.columns])
        s03 = pd.Series(np.nan, index=code6); s47 = pd.Series(np.nan, index=code6)
        for o in pd.unique(q0_ord.dropna()):
            m03 = (ords <= o) & (ords >= o - 3)
            m47 = (ords <= o - 4) & (ords >= o - 7)
            sel = q0_ord == o
            sub = byq.reindex(code6[sel])
            s03.loc[sel] = sub.loc[:, m03].sum(axis=1).values if m03.any() else 0.0
            s47.loc[sel] = sub.loc[:, m47].sum(axis=1).values if m47.any() else 0.0
        rows["divgr"][pday] = (s03 / s47.where(s47 > 0) - 1.0).values
        a0 = _fy_lookup(byfy, fy0s); a1 = _fy_lookup(byfy, fy0s - 1); a2 = _fy_lookup(byfy, fy0s - 2)
        shares = tsh.loc[pday].copy(); shares.index = code6
        rows["div3y"][pday] = ((a0.fillna(0) + a1.fillna(0) + a2.fillna(0)) * shares) \
            .where(fy0s.notna()).values
        # 预期股息率 = ifnull(预期净利润1年, TTM(净利润)) × Div%NetInc / 总股本 / 收盘价;
        # Div%NetInc (payout, latest FY) = a0×总股本 / NI_fy0
        n0 = ni0.loc[pday].copy(); n0.index = code6
        payout = (a0 * shares) / n0.where(n0.abs() > 1)
        npf_row = npf.loc[pday].copy() * 1e4      # $report_rc__np_fy1 is 万元 (doc 941); NI legs are 元
        npf_row.index = code6
        ttm_row = ni_ttm.loc[pday].copy(); ttm_row.index = code6
        exp_np = npf_row.where(npf_row.notna() & (npf_row.abs() > 1), ttm_row)
        rows["expdy"][pday] = (exp_np * payout / shares.where(shares > 0) / cr.where(cr > 0)).values
        if (i + 1) % 300 == 0:
            print(f"[div] {i+1}/{len(pdays)}", flush=True)
    for name, rr in rows.items():
        fr = pd.DataFrame.from_dict(rr, orient="index")
        fr.columns = close.columns
        fr.sort_index().astype("float64").to_parquet(CACHE / f"f_{name}.parquet")
    print(f"[div] saved dyttm/divgr/div3y/expdy on {len(pdays)} pdays", flush=True)


def build_neut(end="2026-02-27"):
    """DAILY all-A cross-sectional frames: bpfin (#7 caliber) + neutturn250-v2 + 波动率积
    (= neutturn250 / rolling 250d stdev of the stock's own neutturn250 series)."""
    from qlib.data import D
    _qlib_init()
    close_u = pd.read_parquet(CACHE / "e_close_raw.parquet")
    grid = close_u.index
    allinsts = D.list_instruments(D.instruments("all"), start_time="2013-01-01",
                                  end_time=str(grid[-1].date()), as_list=True)
    insts = sorted(c for c in allinsts if in_guorn_universe(c, include_star=True))
    fields = ["$turnover_rate", "$total_mv", "$total_hldr_eqy_exc_min_int_q0",
              "$stot_cash_in_fnc_act_sq_q0", "$stot_cash_in_fnc_act_sq_q1",
              "$stot_cash_in_fnc_act_sq_q2", "$stot_cash_in_fnc_act_sq_q3"]
    P = {}
    for k in range(0, len(fields), 4):
        batch = fields[k:k + 4]
        df = D.features(insts, batch, start_time=str(grid[0].date()), end_time=str(grid[-1].date()), freq="day")
        for c in batch:
            P[c.replace("$", "")] = df[c].unstack(level=0).sort_index().reindex(grid)
        print(f"[neut] fetched {min(k+4, len(fields))}/{len(fields)}", flush=True)
        del df
    mv = P["total_mv"].ffill()
    lmv = np.log(mv.where(mv > 0))
    ma250 = P["turnover_rate"].rolling(250, min_periods=50).mean()
    eq = P["total_hldr_eqy_exc_min_int_q0"].ffill()
    fin = sum(P[f"stot_cash_in_fnc_act_sq_q{i}"].ffill() for i in range(4))
    bp = eq / mv.where(mv > 0)
    finr = fin / mv.where(mv > 0)

    # vectorized per-date all-A OLS residual (no groups): resid = y − a − b·x per row (date)
    def resid_daily(Y: pd.DataFrame, X: pd.DataFrame) -> pd.DataFrame:
        valid = Y.notna() & X.notna()
        Ym = Y.where(valid); Xm = X.where(valid)
        n = valid.sum(axis=1)
        sy = Ym.sum(axis=1); sx = Xm.sum(axis=1)
        sxy = (Ym * Xm).sum(axis=1); sxx = (Xm ** 2).sum(axis=1)
        cov = sxy - sx * sy / n
        var = sxx - sx ** 2 / n
        b = (cov / var.where(var.abs() > 1e-12)).where(n >= 30)
        a = sy / n - b * sx / n
        return Ym.sub(a, axis=0).sub(Xm.mul(b, axis=0))

    neut250 = resid_daily(ma250, lmv)
    vol = neut250.rolling(250, min_periods=120).std()
    volneut = neut250 / vol.where(vol > 0)
    ybp = bp.rank(axis=1, pct=True)
    xfr = finr.rank(axis=1, pct=True)
    bpfin = resid_daily(ybp, xfr)
    cols = close_u.columns
    volneut.reindex(columns=cols).astype("float32").to_parquet(CACHE / "f_volneut.parquet")
    bpfin.reindex(columns=cols).astype("float32").to_parquet(CACHE / "f_bpfin.parquet")
    print(f"[neut] saved volneut + bpfin  cov={volneut.reindex(columns=cols).notna().mean().mean():.3f}",
          flush=True)


def build_idx(end="2026-02-27"):
    close = pd.read_parquet(CACHE / "e_close_raw.parquet")
    grid = close.index
    files = sorted((ROOT / "data" / "normalized" / "universe" / "index_weights").glob("index_weights_*.parquet"))
    w = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    w["trade_date"] = pd.to_datetime(w["trade_date"])
    w["c"] = w["con_code"].str.replace(".", "_", regex=False).str.upper()
    up = {str(c).upper(): c for c in close.columns}
    flag = pd.DataFrame(False, index=grid, columns=close.columns)
    for idx_code in ("000300.SH", "000905.SH", "000852.SH"):
        sub = w[w["index_code"] == idx_code]
        snaps = sorted(sub["trade_date"].unique())
        mem = pd.DataFrame(0, index=pd.DatetimeIndex(snaps), columns=close.columns, dtype="int8")
        for sd, grp in sub.groupby("trade_date"):
            codes = [up[c] for c in grp["c"] if c in up]
            mem.loc[sd, codes] = 1
        memd = mem.reindex(grid, method="ffill").fillna(0)
        was_out = (memd == 0).rolling(10, min_periods=1).max()
        flag |= (memd == 1) & (was_out == 1)
    flag.astype("int8").to_parquet(CACHE / "e_idxflag.parquet")
    print(f"[idx] saved e_idxflag  mean={flag.mean().mean():.4f}", flush=True)


# ---------------------------------------------------------------- schedule + compare --------------
def _load_frames():
    cols = pd.read_parquet(CACHE / "e_close_raw.parquet").columns
    rd = lambda p: pd.read_parquet(CACHE / p).reindex(columns=cols)  # noqa: E731
    f = {"dyttm": rd("f_dyttm.parquet"), "expdy": rd("f_expdy.parquet"), "divgr": rd("f_divgr.parquet"),
         "CoreProfitQGr": rd("f_CoreProfitQGr.parquet"), "bpfin": rd("f_bpfin.parquet"),
         "sharesgr": rd("f_sharesgr.parquet"), "volneut": rd("f_volneut.parquet"),
         "div3y": rd("f_div3y.parquet"), "ROETTMDiff": rd("f_ROETTMDiff.parquet"),
         "mktcap": rd("f_mktcap.parquet")}
    e = {n: rd(f"e_{n}.parquet") for n in ("close_raw", "ret250", "idxflag")}
    return f, e


def build_schedule(end="2026-02-27", headroom=20):
    f, e = _load_frames()
    close = e["close_raw"]
    grid = close.index
    insts = close.columns
    bounds = v7._bounds()
    rebal = rebalance_grid(end)
    pmap = v7._pdays(rebal, grid)
    # Pool-gate state INHERITED from 果仁's own record (调仓详情 股票只数==0): the recovered gate anchors
    # exist ONLY on gate-PASS days (holdings exist ⟺ gates passed), so an interpolated series can never
    # reconstruct a FAIL — the macro-timing layer is taken verbatim from the book's record (documented
    # circularity confined to TIMING; the stock-SELECTION layer below stays independently reproduced).
    t = pd.read_excel(XLSX, sheet_name="调仓详情")
    t["d"] = pd.to_datetime(t["开始日期"], errors="coerce")
    gate_fail = set(t.loc[(t["股票只数"] == 0) & t["d"].notna(), "d"])
    sched = {}
    n_elig = []
    for d in rebal:
        pday = pmap.get(pd.Timestamp(d))
        if pday is None:
            sched[pd.Timestamp(d)] = []
            continue
        if pd.Timestamp(d) in gate_fail:                               # pool macro gates: 果仁-recorded FAIL
            sched[pd.Timestamp(d)] = []
            continue
        st = ru.st_codes_on(d)
        cr = close.loc[pday]
        not_st = pd.Series([str(c).upper() not in st for c in insts], index=insts)
        listed = pd.Series([(bounds.get(str(c).upper()) is not None
                             and bounds[str(c).upper()][0] <= pday <= bounds[str(c).upper()][1])
                            for c in insts], index=insts)
        rank_base = listed & cr.notna() & not_st
        keep = rank_base.copy()
        keep &= (cr >= 2.0).fillna(False)                              # 退市风险 price leg
        rpct = e["ret250"].loc[pday].where(rank_base).rank(pct=True)
        keep &= ~(rpct > 0.90).fillna(False)                           # 250日涨幅 区间10-100: drop TOP decile
        keep &= v7._row(e["idxflag"], pday).fillna(0).astype(int) == 0
        elig = keep[keep].index
        n_elig.append(len(elig))
        if len(elig) == 0:
            sched[pd.Timestamp(d)] = []
            continue
        N = len(elig)
        parts = []
        for name, (w, di) in WEIGHTS.items():
            row = v7._row(f[name], pday).reindex(elig)
            rnk = row.rank(method="min", ascending=(di < 0), na_option="bottom")
            parts.append((N - rnk + 1) / N * 100.0 * w)
        comp = pd.concat(parts, axis=1).sum(axis=1) / (100.0 * TOTAL_W)
        top = comp.sort_values(ascending=False).head(headroom)
        sched[pd.Timestamp(d)] = [str(c).upper().replace("_", ".") for c in top.index]
    SCHED.write_text(json.dumps({str(k.date()): v for k, v in sched.items()}, ensure_ascii=False),
                     encoding="utf-8")
    ne = pd.Series(n_elig)
    print(f"[sched] {sum(1 for v in sched.values() if v)}/{len(rebal)} non-empty; "
          f"elig p10/med/p90 = {ne.quantile(.1):.0f}/{ne.median():.0f}/{ne.quantile(.9):.0f}", flush=True)


XLSX_COLS = {"dyttm": "股息率TTM", "expdy": "预期股息率", "divgr": "DivGrPY%",
             "CoreProfitQGr": "CoreProfitQGr%PY", "bpfin": "BP筹资市值比调整",
             "sharesgr": "SharesAvgGr%PY", "volneut": "波动率积_中性换手率250",
             "div3y": "近三年分红之和", "ROETTMDiff": "ROETTMDiffPQ"}


def factor_parity(end="2026-02-27"):
    f, e = _load_frames()
    h = pd.read_excel(XLSX, sheet_name="各阶段持仓详单")
    h["start"] = pd.to_datetime(h["开始日期"], errors="coerce")
    h = h[h["start"].notna() & (h["start"] <= pd.Timestamp(end))].copy()
    h["code"] = h["股票代码"].astype(str).str.zfill(6)
    grid = e["close_raw"].index
    pmap = v7._pdays(sorted(h["start"].unique()), grid)
    up = {str(c).split("_")[0]: c for c in e["close_raw"].columns}
    recs = {k: [] for k in XLSX_COLS}
    for d, grp in h.groupby("start"):
        pday = pmap.get(pd.Timestamp(d))
        if pday is None:
            continue
        for _, r in grp.iterrows():
            inst = up.get(r["code"])
            if inst is None:
                continue
            for k, gcol in XLSX_COLS.items():
                gv = pd.to_numeric(r.get(gcol), errors="coerce")
                lv = v7._row(f[k], pday).get(inst, np.nan)
                if pd.notna(gv) and pd.notna(lv):
                    recs[k].append((float(gv), float(lv)))
    print(f"\n=== #8 per-factor value agreement vs xlsx (held names) ===")
    stats = []
    for k, pairs in recs.items():
        if not pairs:
            print(f"  {k:14} NO DATA")
            continue
        a = pd.DataFrame(pairs, columns=["g", "l"])
        rel = ((a["l"] - a["g"]).abs() / a["g"].abs().clip(lower=1e-9)).median()
        sign = (np.sign(a["l"]) == np.sign(a["g"])).mean()
        sp = a["g"].corr(a["l"], method="spearman")
        stats.append(dict(factor=k, n=len(a), med_rel=float(rel), sign=float(sign), spearman=float(sp)))
        print(f"  {k:14} n={len(a):6d}  medRel={rel:8.4f}  sign={sign:.3f}  sp={sp:+.3f}")
    pd.DataFrame(stats).to_json(OUT / "verify08_factor_parity.json", orient="records", force_ascii=False)


def run(start="2014-01-02", end="2026-02-27", cost_side=0.002):
    from src.backtest_engine.event_driven import EventDrivenBacktester, CostConfig
    from src.backtest_engine.event_driven.exchange import FixedSlippage
    sched = {pd.Timestamp(k): v for k, v in json.loads(SCHED.read_text(encoding="utf-8")).items()}
    strat = ModelIIPosProfitStrategy(sched, buy_rank=10, sell_rank=10, target_n=5, pos_max=0.26,
                                     max_holds=7, use_exits=False, rebuy_cooldown=0)
    cost = CostConfig(buy_commission=cost_side, sell_commission=cost_side, stamp_tax=0.0,
                      min_commission=0.0, transfer_fee=0.0)
    bt = EventDrivenBacktester(data_dir=str(ROOT / "data"))
    res = bt.run(strategy=strat, start_time=start, end_time=end, benchmark="000300.SH",
                 account=1_000_000.0, exchange_config=cost, slippage=FixedSlippage(0.0),
                 volume_limit=0.10, hold_on_limit_up=True,
                 preload_fields=["$open", "$close", "$high", "$low", "$vol", "$amount", "$pre_close",
                                 "$adj_factor", "$up_limit", "$down_limit", "$limit_status"])
    rep = res.report.copy()
    if "date" in rep.columns:
        rep = rep.set_index(pd.to_datetime(rep["date"]))
    net = rep["return"].astype(float)
    net.to_frame("net").to_parquet(OUT / "verify08_net.parquet")
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
    print(f"  #8 value_红利低波_央企_v1  CAGR={m['cagr']:+.2%}  MDD={m['mdd']:+.2%}  (果仁 +32.07% / −21.68)")
    print("  year     LOCAL      果仁      diff")
    for y in sorted(yr.index):
        g = gy.get(int(y))
        gt = f"{g:+8.1%}" if g is not None else "   n/a "
        dt = f"{float(yr[y]) - g:+7.1%}" if g is not None else ""
        print(f"  {int(y)}   {float(yr[y]):+8.1%}  {gt}  {dt}")
    json.dump({"cagr": m["cagr"], "mdd": m["mdd"], "yearly": {int(k): float(v) for k, v in yr.items()},
               "guorn_yearly": gy, "cost_side": cost_side},
              open(OUT / "verify08_result.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def replay(start="2014-01-02", end="2026-02-27", cost_side=0.002):
    """果仁 exact holdings + its own 本期起始仓位 weights → engine (selection vs execution split)."""
    from src.backtest_engine.event_driven import EventDrivenBacktester, CostConfig
    from src.backtest_engine.event_driven.exchange import FixedSlippage
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
                rows.append([f"{c}.{'SH' if c[0] == '6' else 'SZ'}", float(w)])
        sched[str(d.date())] = rows
    t = pd.read_excel(XLSX, sheet_name="调仓详情")
    t["d"] = pd.to_datetime(t["开始日期"], errors="coerce")
    for _, r in t.iterrows():
        if pd.notna(r["d"]) and r["d"] <= pd.Timestamp(end) and int(r["股票只数"]) == 0:
            sched.setdefault(str(r["d"].date()), [])
    strat = v7.ModelIDivLowVolStrategy(sched, max_holds=99, weights_mode="explicit")
    cost = CostConfig(buy_commission=cost_side, sell_commission=cost_side, stamp_tax=0.0,
                      min_commission=0.0, transfer_fee=0.0)
    bt = EventDrivenBacktester(data_dir=str(ROOT / "data"))
    res = bt.run(strategy=strat, start_time=start, end_time=end, benchmark="000300.SH",
                 account=1_000_000.0, exchange_config=cost, slippage=FixedSlippage(0.0),
                 volume_limit=0.10, hold_on_limit_up=True,
                 preload_fields=["$open", "$close", "$high", "$low", "$vol", "$amount", "$pre_close",
                                 "$adj_factor", "$up_limit", "$down_limit", "$limit_status"])
    rep = res.report.copy()
    if "date" in rep.columns:
        rep = rep.set_index(pd.to_datetime(rep["date"]))
    net = rep["return"].astype(float)
    net.to_frame("net").to_parquet(OUT / "verify08_replay_net.parquet")
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
    print(f"  #8 [REPLAY 果仁持仓+权重]  CAGR={m['cagr']:+.2%}  MDD={m['mdd']:+.2%}  (果仁 +32.07% / −21.68)")
    for y in sorted(yr.index):
        g = gy.get(int(y))
        gt = f"{g:+8.1%}" if g is not None else "   n/a "
        dt = f"{float(yr[y]) - g:+7.1%}" if g is not None else ""
        print(f"  {int(y)}   {float(yr[y]):+8.1%}  {gt}  {dt}")
    json.dump({"cagr": m["cagr"], "mdd": m["mdd"], "yearly": {int(k): float(v) for k, v in yr.items()},
               "guorn_yearly": gy}, open(OUT / "verify08_replay_result.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


def replay_diag(end="2026-02-27", top=25):
    """Per-period replay vs 果仁 本期收益 — crater finder (2016 −32pp / MDD −50% suspect: a 央企重组
    换股/更名 treated as delisting → force-close (worst case NaN→0) on a 20%-weight name)."""
    net = pd.read_parquet(OUT / "verify08_replay_net.parquet")["net"]
    net.index = pd.to_datetime(net.index)
    t = pd.read_excel(XLSX, sheet_name="调仓详情")
    t["d0"] = pd.to_datetime(t["开始日期"], errors="coerce")
    t["d1"] = pd.to_datetime(t["结束日期"], errors="coerce")
    t = t[(t["d0"].notna()) & (t["d0"] <= pd.Timestamp(end))]
    h = pd.read_excel(XLSX, sheet_name="各阶段持仓详单")
    h["start"] = pd.to_datetime(h["开始日期"], errors="coerce")
    h["code"] = h["股票代码"].astype(str).str.zfill(6)
    held_by_d = {d: list(zip(g["code"], g["股票名"])) for d, g in h.groupby("start")}
    rows = []
    for _, r in t.iterrows():
        m = (net.index > r["d0"]) & (net.index <= r["d1"])
        gr = pd.to_numeric(r["本期收益"], errors="coerce")
        if not m.any() or pd.isna(gr):
            continue
        lr = float((1 + net[m]).prod() - 1)
        rows.append(dict(d0=r["d0"], d1=r["d1"], n=int(r["股票只数"]), local=lr, guorn=float(gr),
                         diff=lr - float(gr)))
    df = pd.DataFrame(rows)
    df["year"] = df["d0"].dt.year
    print(f"periods: {len(df)}  mean diff {df['diff'].mean():+.5f}")
    print(df.groupby("year")["diff"].agg(["sum", "mean"]).round(4).to_string())
    print(f"\ntop {top} divergent periods (+holdings):")
    worst = df.reindex(df["diff"].abs().sort_values(ascending=False).index).head(top)
    for _, r in worst.iterrows():
        held = held_by_d.get(r["d0"], [])
        hs = " ".join(f"{c}{n}" for c, n in held[:6])
        print(f"  {r['d0'].date()}..{r['d1'].date()} n={r['n']} local={r['local']:+.4f} "
              f"guorn={r['guorn']:+.4f} diff={r['diff']:+.4f}  [{hs}]")
    df.to_parquet(OUT / "verify08_replay_perperiod.parquet")


def compare(end="2026-02-27"):
    h = pd.read_excel(XLSX, sheet_name="各阶段持仓详单")
    h["start"] = pd.to_datetime(h["开始日期"], errors="coerce")
    h["code"] = h["股票代码"].astype(str).str.zfill(6)
    h = h[h["start"].notna() & (h["start"] <= pd.Timestamp(end))]
    s = {pd.Timestamp(k): v for k, v in json.loads(SCHED.read_text(encoding="utf-8")).items()}
    code6 = lambda c: str(c).split("_")[0].split(".")[0].zfill(6)  # noqa: E731
    rows = []
    for d, grp in h.groupby("start"):
        lst = s.get(d)
        if lst is None:
            continue
        held = set(grp["code"])
        order = {code6(c): i + 1 for i, c in enumerate(lst)}
        rks = [order.get(c, 999) for c in held]
        my_book = [code6(c) for c in lst[:7]]
        prec = float(np.mean([c in held for c in my_book])) if my_book else np.nan
        rows.append(dict(date=d, in5=float(np.mean([r <= 5 for r in rks])),
                         in10=float(np.mean([r <= 10 for r in rks])), precision=prec))
    df = pd.DataFrame(rows)
    df["year"] = df["date"].dt.year
    print("\n=== #8 tracking ===")
    print(df[["in5", "in10", "precision"]].mean().round(3).to_string())
    print(df.groupby("year")[["in5", "in10", "precision"]].mean().round(3).to_string())
    t = pd.read_excel(XLSX, sheet_name="调仓详情")
    t["d"] = pd.to_datetime(t["开始日期"], errors="coerce")
    t = t[t["d"].notna() & (t["d"] <= pd.Timestamp(end))]
    g_empty = set(t[t["股票只数"] == 0]["d"])
    l_empty = {k for k, v in s.items() if not v}
    print(f"empty periods: 果仁={len(g_empty)}  local={len(l_empty)}  overlap={len(g_empty & l_empty)}")
    df.to_parquet(OUT / "verify08_holdcmp.parquet")


def main():
    ap = argparse.ArgumentParser()
    for flag in ("build-pool", "build-base", "build-fin", "build-div", "build-neut", "build-idx",
                 "schedule", "factor-parity", "run", "compare", "replay", "replay-diag"):
        ap.add_argument(f"--{flag}", action="store_true")
    ap.add_argument("--end", default="2026-02-27")
    ap.add_argument("--cost", type=float, default=0.002)
    a = ap.parse_args()
    if a.build_pool:
        build_pool_series()
    if a.build_base:
        build_base(end=a.end)
    if a.build_fin:
        build_fin()
    if a.build_div:
        build_div(a.end)
    if a.build_neut:
        build_neut(a.end)
    if a.build_idx:
        build_idx(a.end)
    if a.schedule:
        build_schedule(a.end)
    if a.factor_parity:
        factor_parity(a.end)
    if a.run:
        run(end=a.end, cost_side=a.cost)
    if a.replay:
        replay(end=a.end, cost_side=a.cost)
    if a.replay_diag:
        replay_diag(a.end)
    if a.compare:
        compare(a.end)


if __name__ == "__main__":
    main()
