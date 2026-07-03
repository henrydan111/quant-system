"""果仁 deployed-20 verification — strategy #9: value_红利低波_重股息_v1 (nn=21, xlsx 21).

SCRIPT_STATUS: Class-B parity diagnostic (active build 2026-07-02). 果仁 = trusted benchmark; LOCAL under test.

Recipe (deployed_20_recipes.md #9): universe 板块=全部 (main+chinext, EXCL STAR/BSE) − ST − 停牌.
  filters(8): 连续N年分红(3)>0 [campaign caliber: annual(分红,0/1/2)>0 on FY{-1,-2,-3} + whole-FY listing
    gate] · DivOP% 值区间 10%-200% [sumq(分红,4)/TTM(营业利润)] · YieldRfrDiff>0.02 [股息率TTM −
    MA(10Y,60td); CGB = #7-recovered series daily-interp] · 近三年分红之和>0.3×三年净利润 [ni_fy2 =
    ni_fy1.shift(245td) proxy when the q9-q11 slot is out of depth — coarse gate, documented] ·
    近三年分红之和>5000万 · 调入指数(10)=0 · 退市风险 price leg · 未来20日新增流通股 [OMITTED].
  rankings(5, Σw=7): 波动率_日度指标(分红总金额,720) w1↑ [variants vs xlsx truth col] · SharesAvgGr%PY w1↑ ·
    DivAGrPY% w1↓ · 预期DivAGrPY% w1↓ · 公式(TTM(COREPROFITQ,4)×DIV%NETINC/总股本/收盘价) w3↓
    [CoreProfit 0-fill registry fix #11].
  trade model: Model I — 5d rebalance (xlsx 606-period grid), 09:35≈open fill, 最大持仓10, 备选5,
    weights = sqrt(流通市值 $circ_mv), idle cash = CASH (空闲资金=无 ✓ exact).

NON-FORMAL parity artifact. Reuses v7/v8 kernels (div events, FY anchors, Model-I strategy).
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
import guorn_verify_07_divlowvol as v7                                   # noqa: E402
from guorn_universe import in_guorn_universe                             # noqa: E402
from guorn_beta import _is_ashare_stock                                  # noqa: E402  (drop 6-digit index collisions)

OUT = ROOT / "workspace" / "outputs" / "guorn_parity"
CACHE = OUT / "verify09_cache"
CACHE.mkdir(parents=True, exist_ok=True)
SCHED = OUT / "verify09_schedule.json"
XLSX = ROOT / "Knowledge" / "果仁回测结果" / "21_value_红利低波_重股息_v1.xlsx"
GR = dict(annual=0.3325, sharpe=1.27, mdd=0.3295)

WEIGHTS = {"divvol": (1, -1), "sharesgr": (1, -1), "divagr": (1, +1), "expdivagr": (1, +1),
           "coreyield": (3, +1)}
TOTAL_W = sum(w for w, _ in WEIGHTS.values())


def _qlib_init():
    import qlib
    from qlib.config import REG_CN
    qlib.init(provider_uri=str(ROOT / "data" / "qlib_data"), region=REG_CN, kernels=1)


def rebalance_grid(cal_max="2026-02-27"):
    t = pd.read_excel(XLSX, sheet_name="调仓详情")
    d = pd.to_datetime(t["开始日期"], errors="coerce").dropna().sort_values().unique()
    return [pd.Timestamp(x) for x in d if pd.Timestamp(x) <= pd.Timestamp(cal_max)]


BASE_FIELDS = ["$close", "$open", "$amount", "$adj_factor", "$total_mv", "$circ_mv",
               "$total_share", "$report_rc__np_fy1"]


def build_base(start="2012-06-01", end="2026-02-27"):
    from qlib.data import D
    _qlib_init()
    allinsts = D.list_instruments(D.instruments("all"), start_time="2013-01-01", end_time=end, as_list=True)
    # main+chinext (EXCL STAR/BSE); _is_ashare_stock drops INDEX instruments that collide on the
    # 6-digit prefix (000001_SH 上证指数 vs 000001_SZ — the guorn_beta lesson; dup code6 labels crash joins)
    insts = sorted(c for c in allinsts if in_guorn_universe(c) and _is_ashare_stock(str(c).lower()))
    print(f"[base] {len(insts)} insts; {len(BASE_FIELDS)} fields {start}..{end}", flush=True)
    P = {}
    for k in range(0, len(BASE_FIELDS), 4):
        batch = BASE_FIELDS[k:k + 4]
        df = D.features(insts, batch, start_time=start, end_time=end, freq="day")
        for c in batch:
            P[c.replace("$", "")] = df[c].unstack(level=0).sort_index()
        print(f"[base]   {min(k+4, len(BASE_FIELDS))}/{len(BASE_FIELDS)}", flush=True)
        del df
    idx = P["close"].index
    P["close"].astype("float32").to_parquet(CACHE / "e_close_raw.parquet")
    P["total_mv"].reindex(idx).ffill().astype("float32").to_parquet(CACHE / "f_mktcap.parquet")
    P["circ_mv"].reindex(idx).ffill().astype("float32").to_parquet(CACHE / "e_circ_mv.parquet")
    P["total_share"].reindex(idx).ffill().astype("float64").to_parquet(CACHE / "e_total_share.parquet")
    P["report_rc__np_fy1"].reindex(idx).ffill().astype("float64").to_parquet(CACHE / "e_np_fy1.parquet")
    (CACHE / "meta.json").write_text(json.dumps({"start": start, "end": end, "n_insts": len(insts)}),
                                     encoding="utf-8")
    print(f"[base] cached -> {CACHE}", flush=True)


def build_fin():
    from qlib.data import D
    _qlib_init()
    grid = pd.read_parquet(CACHE / "e_close_raw.parquet").index
    insts = list(pd.read_parquet(CACHE / "e_close_raw.parquet").columns)
    q = lambda b, qs: [f"${b}{i}" for i in qs]  # noqa: E731
    fields = (q("revenue_sq_q", range(8)) + q("oper_cost_sq_q", range(8)) + q("admin_exp_sq_q", range(8))
              + q("sell_exp_sq_q", range(8)) + q("fin_exp_sq_q", range(8)) + q("biz_tax_surchg_sq_q", range(8))
              + q("operate_profit_sq_q", range(4)) + q("total_share_q", range(8))
              + q("n_income_sq_q", range(4)) + q("n_income_cum_q", range(9)))
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
    zc = lambda fr: fr.fillna(0.0)  # noqa: E731  (registry fix #11: expense legs 0-fill, revenue REQUIRED)
    core = lambda qq: (P[f"revenue_sq_q{qq}"] - zc(P[f"oper_cost_sq_q{qq}"])  # noqa: E731
                       - (zc(P[f"admin_exp_sq_q{qq}"]) + zc(P[f"sell_exp_sq_q{qq}"]) + zc(P[f"fin_exp_sq_q{qq}"]))
                       - zc(P[f"biz_tax_surchg_sq_q{qq}"]))
    core_ttm = sum(core(i) for i in range(4))
    core_ttm.astype("float64").to_parquet(CACHE / "e_core_ttm.parquet")
    # 果仁-official TTM(x,4) = the YEAR-AGO 4-quarter sum (前移季度数 — 自定义函数列表 L610), q4..q7
    sum(core(i) for i in range(4, 8)).astype("float64").to_parquet(CACHE / "e_core_ttm_y1.parquet")
    (sum(P[f"operate_profit_sq_q{i}"] for i in range(4))).astype("float64") \
        .to_parquet(CACHE / "e_op_ttm.parquet")
    sh03 = sum(P[f"total_share_q{i}"] for i in range(4))
    sh47 = sum(P[f"total_share_q{i}"] for i in range(4, 8))
    safe(sh03, sh47).sub(1).astype("float32").to_parquet(CACHE / "f_sharesgr.parquet")
    (sum(P[f"n_income_sq_q{i}"] for i in range(4))).astype("float64").to_parquet(CACHE / "e_ni_ttm.parquet")
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
    # FY−2 NI: slot ann_slot+8 exceeds depth for 3 of 4 phases → lag-year proxy of fy1 (coarse 30% gate)
    fy1.shift(245).astype("float64").to_parquet(CACHE / "e_ni_fy2.parquet")
    (k_first + 1).astype("float32").to_parquet(CACHE / "e_q0quarter.parquet")
    print("[fin] saved core_ttm / op_ttm / sharesgr / ni_ttm / ni_fy0/1/2 / q0quarter", flush=True)


def build_div(end="2026-02-27"):
    """Dividend family at the 606 pdays — v7 kernels; adds DivOP%, DivAGrPY%, 预期DivAGrPY%, coreyield,
    divvol720 variants, 连续3年分红, 3FY-NI payout gate legs."""
    close = pd.read_parquet(CACHE / "e_close_raw.parquet")
    grid = close.index
    rebal = rebalance_grid(end)
    pmap = v7._pdays(rebal, grid)
    pdays = sorted(set(pmap.values()))
    d = v7._div_events_raw()
    code6 = pd.Index([c.split("_")[0] for c in close.columns])
    rd = lambda p: pd.read_parquet(CACHE / p).reindex(columns=close.columns)  # noqa: E731
    q0q, tsh = rd("e_q0quarter.parquet"), rd("e_total_share.parquet")
    ni0, ni1, ni2 = rd("e_ni_fy0.parquet"), rd("e_ni_fy1.parquet"), rd("e_ni_fy2.parquet")
    ni_ttm, npf = rd("e_ni_ttm.parquet"), rd("e_np_fy1.parquet")
    core_ttm, op_ttm = rd("e_core_ttm_y1.parquet"), rd("e_op_ttm.parquet")   # TTM(x,4) = year-ago TTM
    bounds = v7._bounds()
    list0 = pd.Series({c: (bounds.get(str(c).upper())[0] if bounds.get(str(c).upper()) else pd.NaT)
                       for c in close.columns})
    list0.index = code6
    _QEND_MD = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}

    def _fy_lookup(byfy, fy_ser):
        out = pd.Series(np.nan, index=fy_ser.index)
        for fy in pd.unique(fy_ser.dropna()):
            fy = int(fy)
            if fy in byfy.columns:
                m = fy_ser == fy
                out.loc[m] = byfy[fy].reindex(fy_ser.index[m]).values
        return out

    names = ("dyttm", "divop", "divagr", "expdivagr", "coreyield", "div3y", "contdiv3", "payout3ok",
             "divvol_a", "divvol_b")
    rows = {k: {} for k in names}
    hist_sumq = {}                                     # pday -> per-code trailing-4q dps (for divvol_a)
    for i, pday in enumerate(pdays):
        dps_ttm, byq, byfy = v7._div_at(d, pday)
        cr = close.loc[pday].copy(); cr.index = code6
        rows["dyttm"][pday] = (dps_ttm.reindex(code6) / cr).values
        qq = q0q.loc[pday].copy(); qq.index = code6
        q0_ord = pd.Series(np.nan, index=code6)
        fy0s = pd.Series(np.nan, index=code6)
        for qn, (mm, dd) in _QEND_MD.items():
            q0y = pday.year if pd.Timestamp(pday.year, mm, dd) <= pday else pday.year - 1
            q0_ord = q0_ord.where(qq != qn, pd.Period(year=q0y, quarter=qn, freq="Q").ordinal)
            fy0s = fy0s.where(qq != qn, q0y - 1 if qn < 4 else q0y)
        ords = np.array([p.ordinal for p in byq.columns])
        s03 = pd.Series(np.nan, index=code6)
        for o in pd.unique(q0_ord.dropna()):
            m03 = (ords <= o) & (ords >= o - 3)
            sel = q0_ord == o
            sub = byq.reindex(code6[sel])
            s03.loc[sel] = sub.loc[:, m03].sum(axis=1).values if m03.any() else 0.0
        hist_sumq[pday] = s03
        shares = tsh.loc[pday].copy(); shares.index = code6
        op = op_ttm.loc[pday].copy(); op.index = code6
        rows["divop"][pday] = ((s03 * shares) / op.where(op.abs() > 1)).values
        a0 = _fy_lookup(byfy, fy0s)
        a1 = _fy_lookup(byfy, fy0s - 1)
        a2 = _fy_lookup(byfy, fy0s - 2)
        d3 = (a0.fillna(0) + a1.fillna(0) + a2.fillna(0)) * shares
        rows["div3y"][pday] = d3.where(fy0s.notna()).values
        rows["divagr"][pday] = ((a0.fillna(0) - a1) / a1.where(a1 > 0)).values
        n0 = ni0.loc[pday].copy(); n0.index = code6
        payout = (a0 * shares) / n0.where(n0.abs() > 1)
        npf_row = npf.loc[pday].copy() * 1e4; npf_row.index = code6      # np_fy1 万元 → 元
        ttm_row = ni_ttm.loc[pday].copy(); ttm_row.index = code6
        exp_np = npf_row.where(npf_row.notna() & (npf_row.abs() > 1), ttm_row)
        a1amt = a1 * shares
        rows["expdivagr"][pday] = ((exp_np * payout - a1amt) / a1amt.where(a1amt > 0)).values
        ct = core_ttm.loc[pday].copy(); ct.index = code6
        rows["coreyield"][pday] = (ct * payout / shares.where(shares > 0) / cr.where(cr > 0)).values
        # 连续3年分红: annual(0/1/2)>0 + whole-FY listing gate (campaign caliber)
        lg = pd.Series([(pd.notna(list0.get(c)) and pd.notna(fy0s.get(c))
                         and list0[c] <= pd.Timestamp(int(fy0s[c]) - 2, 12, 31)) for c in code6], index=code6)
        rows["contdiv3"][pday] = ((a0.fillna(0) > 0) & (a1.fillna(0) > 0) & (a2.fillna(0) > 0) & lg).values
        n1 = ni1.loc[pday].copy(); n1.index = code6
        n2 = ni2.loc[pday].copy(); n2.index = code6
        ni3 = n0.fillna(0) + n1.fillna(0) + n2.fillna(0)
        rows["payout3ok"][pday] = (d3 > 0.3 * ni3).where(fy0s.notna() & (ni3 != 0)).values
        if (i + 1) % 100 == 0:
            print(f"[div] {i+1}/{len(pdays)}", flush=True)
    # divvol720 variants: stdev over trailing 720 CALENDAR days of the pday-sampled series
    sq_df = pd.DataFrame.from_dict(hist_sumq, orient="index").sort_index()      # trailing-4q dps
    tshp = tsh.copy(); tshp.columns = code6
    amt_df = sq_df * tshp.reindex(sq_df.index)                                   # 分红总金额 AMOUNT
    for tag, fr in (("divvol_a", amt_df), ("divvol_b", sq_df)):
        out = {}
        for pday in pdays:
            w = fr[(fr.index > pday - pd.Timedelta(days=720)) & (fr.index <= pday)]
            out[pday] = w.std().values if len(w) >= 20 else np.full(len(code6), np.nan)
        rows[tag] = out
    for name, rr in rows.items():
        fr = pd.DataFrame.from_dict(rr, orient="index")
        fr.columns = close.columns
        fr.sort_index().astype("float64").to_parquet(CACHE / f"f_{name}.parquet")
    print(f"[div] saved {names} on {len(pdays)} pdays", flush=True)


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
            mem.loc[sd, [up[c] for c in grp["c"] if c in up]] = 1
        memd = mem.reindex(grid, method="ffill").fillna(0)
        was_out = (memd == 0).rolling(10, min_periods=1).max()
        flag |= (memd == 1) & (was_out == 1)
    flag.astype("int8").to_parquet(CACHE / "e_idxflag.parquet")
    print(f"[idx] saved e_idxflag  mean={flag.mean().mean():.4f}", flush=True)


def _load_frames():
    cols = pd.read_parquet(CACHE / "e_close_raw.parquet").columns
    rd = lambda p: pd.read_parquet(CACHE / p).reindex(columns=cols)  # noqa: E731
    f = {"divvol": rd("f_divvol_a.parquet"), "sharesgr": rd("f_sharesgr.parquet"),
         "divagr": rd("f_divagr.parquet"), "expdivagr": rd("f_expdivagr.parquet"),
         "coreyield": rd("f_coreyield.parquet")}
    e = {n: rd(f"e_{n}.parquet") for n in ("close_raw", "circ_mv", "idxflag")}
    x = {n: rd(f"f_{n}.parquet") for n in ("dyttm", "divop", "div3y", "contdiv3", "payout3ok", "divvol_b")}
    return f, e, x


def build_schedule(end="2026-02-27", headroom=20, divvol="a"):
    f, e, x = _load_frames()
    if divvol == "b":
        f = dict(f)
        f["divvol"] = x["divvol_b"]
    cgb = v7._cgb_series()
    cgb_ma60 = cgb.rolling(60).mean()                     # MA(10Y, 60) on the daily-interp series
    close = e["close_raw"]
    grid = close.index
    insts = close.columns
    bounds = v7._bounds()
    rebal = rebalance_grid(end)
    pmap = v7._pdays(rebal, grid)
    sched = {}
    n_elig = []
    for dd in rebal:
        pday = pmap.get(pd.Timestamp(dd))
        if pday is None:
            sched[pd.Timestamp(dd)] = []
            continue
        st = ru.st_codes_on(dd)
        cr = close.loc[pday]
        not_st = pd.Series([str(c).upper() not in st for c in insts], index=insts)
        listed = pd.Series([(bounds.get(str(c).upper()) is not None
                             and bounds[str(c).upper()][0] <= pday <= bounds[str(c).upper()][1])
                            for c in insts], index=insts)
        keep = listed & cr.notna() & not_st
        keep &= (cr >= 2.0).fillna(False)
        keep &= v7._row(x["contdiv3"], pday).fillna(0).astype(bool)                  # 连续3年分红
        dop = v7._row(x["divop"], pday)
        keep &= ((dop >= 0.10) & (dop <= 2.00)).fillna(False)                        # DivOP% 值区间
        cpos = cgb_ma60.index.searchsorted(pd.Timestamp(dd), side="right")
        cma = float(cgb_ma60.iloc[cpos - 1]) if cpos > 0 else np.nan
        dy = v7._row(x["dyttm"], pday)
        keep &= ((dy - cma) > 0.02).fillna(False)                                    # YieldRfrDiff
        keep &= v7._row(x["payout3ok"], pday).fillna(0).astype(bool)                 # 3FY 30% payout
        keep &= (v7._row(x["div3y"], pday) > 5e7).fillna(False)                      # 近3年分红>5000万
        keep &= v7._row(e["idxflag"], pday).fillna(0).astype(int) == 0
        elig = keep[keep].index
        n_elig.append(len(elig))
        if len(elig) == 0:
            sched[pd.Timestamp(dd)] = []
            continue
        N = len(elig)
        parts = []
        for name, (w, di) in WEIGHTS.items():
            row = v7._row(f[name], pday).reindex(elig)
            rnk = row.rank(method="min", ascending=(di < 0), na_option="bottom")
            parts.append((N - rnk + 1) / N * 100.0 * w)
        comp = pd.concat(parts, axis=1).sum(axis=1) / (100.0 * TOTAL_W)
        top = comp.sort_values(ascending=False).head(headroom)
        cmv = e["circ_mv"].loc[pday].reindex(top.index)
        sched[pd.Timestamp(dd)] = [[str(c).upper().replace("_", "."), float(cmv.get(c, np.nan))]
                                   for c in top.index]
    SCHED.write_text(json.dumps({str(k.date()): v for k, v in sched.items()}, ensure_ascii=False),
                     encoding="utf-8")
    ne = pd.Series(n_elig)
    print(f"[sched] {sum(1 for v in sched.values() if v)}/{len(rebal)} non-empty; "
          f"elig p10/med/p90 = {ne.quantile(.1):.0f}/{ne.median():.0f}/{ne.quantile(.9):.0f}", flush=True)


XLSX_COLS = {"dyttm": "YieldRfrDiff", "divop": "DivOP%", "divagr": "DivAGrPY%",
             "expdivagr": "预期DivAGrPY%", "coreyield": "公式(TTM(COREPROFITQ,4)*DIV%NETINC/总股本/收盘价)",
             "sharesgr": "SharesAvgGr%PY", "div3y": "最近3年累计分红金额大于5000万",
             "divvol_a": "波动率_日度指标(分红总金额,720)", "divvol_b": "波动率_日度指标(分红总金额,720)"}


def factor_parity(end="2026-02-27"):
    f, e, x = _load_frames()
    frames = {"divop": x["divop"], "divagr": f["divagr"], "expdivagr": f["expdivagr"],
              "coreyield": f["coreyield"], "sharesgr": f["sharesgr"],
              "divvol_a": f["divvol"], "divvol_b": x["divvol_b"]}
    h = pd.read_excel(XLSX, sheet_name="各阶段持仓详单")
    h["start"] = pd.to_datetime(h["开始日期"], errors="coerce")
    h = h[h["start"].notna() & (h["start"] <= pd.Timestamp(end))].copy()
    h["code"] = h["股票代码"].astype(str).str.zfill(6)
    grid = e["close_raw"].index
    pmap = v7._pdays(sorted(h["start"].unique()), grid)
    up = {str(c).split("_")[0]: c for c in e["close_raw"].columns}
    recs = {k: [] for k in frames}
    for dd, grp in h.groupby("start"):
        pday = pmap.get(pd.Timestamp(dd))
        if pday is None:
            continue
        for _, r in grp.iterrows():
            inst = up.get(r["code"])
            if inst is None:
                continue
            for k, fr in frames.items():
                gv = pd.to_numeric(r.get(XLSX_COLS[k]), errors="coerce")
                lv = v7._row(fr, pday).get(inst, np.nan)
                if pd.notna(gv) and pd.notna(lv):
                    recs[k].append((float(gv), float(lv)))
    print(f"\n=== #9 per-factor value agreement vs xlsx (held names) ===")
    for k, pairs in recs.items():
        if not pairs:
            print(f"  {k:12} NO DATA")
            continue
        a = pd.DataFrame(pairs, columns=["g", "l"])
        rel = ((a["l"] - a["g"]).abs() / a["g"].abs().clip(lower=1e-9)).median()
        sign = (np.sign(a["l"]) == np.sign(a["g"])).mean()
        sp = a["g"].corr(a["l"], method="spearman")
        print(f"  {k:12} n={len(a):6d}  medRel={rel:8.4f}  sign={sign:.3f}  sp={sp:+.3f}")


def run(start="2014-01-02", end="2026-02-27", cost_side=0.002, replay=False):
    from src.backtest_engine.event_driven import EventDrivenBacktester, CostConfig
    from src.backtest_engine.event_driven.exchange import FixedSlippage
    if replay:
        h = pd.read_excel(XLSX, sheet_name="各阶段持仓详单")
        h["start"] = pd.to_datetime(h["开始日期"], errors="coerce")
        h["code"] = h["股票代码"].astype(str).str.zfill(6)
        h = h[h["start"].notna() & (h["start"] <= pd.Timestamp(end))]
        sched = {}
        for dd, grp in h.groupby("start"):
            rows = []
            for _, r in grp.iterrows():
                w = pd.to_numeric(r.get("本期起始仓位"), errors="coerce")
                if pd.notna(w) and w > 0:
                    c = r["code"]
                    rows.append([f"{c}.{'SH' if c[0] == '6' else 'SZ'}", float(w)])
            sched[str(dd.date())] = rows
        t = pd.read_excel(XLSX, sheet_name="调仓详情")
        t["d"] = pd.to_datetime(t["开始日期"], errors="coerce")
        for _, r in t.iterrows():
            if pd.notna(r["d"]) and r["d"] <= pd.Timestamp(end) and int(r["股票只数"]) == 0:
                sched.setdefault(str(r["d"].date()), [])
        strat = v7.ModelIDivLowVolStrategy(sched, max_holds=99, weights_mode="explicit")
        net_name, label = "verify09_replay_net.parquet", "REPLAY(果仁持仓+权重)"
    else:
        sched = json.loads(SCHED.read_text(encoding="utf-8"))
        strat = v7.ModelIDivLowVolStrategy(sched, max_holds=10)          # sqrt(circ_mv) via schedule values
        net_name, label = "verify09_net.parquet", "LOCAL selection"
    cost = CostConfig(buy_commission=cost_side, sell_commission=cost_side, stamp_tax=0.0,
                      min_commission=0.0, transfer_fee=0.0)
    bt = EventDrivenBacktester(data_dir=str(ROOT / "data"))
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
    print(f"  #9 value_红利低波_重股息_v1 [{label}]  CAGR={m['cagr']:+.2%}  MDD={m['mdd']:+.2%}  "
          f"(果仁 +33.25% / −32.95)")
    for y in sorted(yr.index):
        g = gy.get(int(y))
        gt = f"{g:+8.1%}" if g is not None else "   n/a "
        dt = f"{float(yr[y]) - g:+7.1%}" if g is not None else ""
        print(f"  {int(y)}   {float(yr[y]):+8.1%}  {gt}  {dt}")
    json.dump({"cagr": m["cagr"], "mdd": m["mdd"], "yearly": {int(k): float(v) for k, v in yr.items()},
               "guorn_yearly": gy, "replay": replay},
              open(OUT / ("verify09_replay_result.json" if replay else "verify09_result.json"),
                   "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def compare(end="2026-02-27"):
    h = pd.read_excel(XLSX, sheet_name="各阶段持仓详单")
    h["start"] = pd.to_datetime(h["开始日期"], errors="coerce")
    h["code"] = h["股票代码"].astype(str).str.zfill(6)
    h = h[h["start"].notna() & (h["start"] <= pd.Timestamp(end))]
    s = {pd.Timestamp(k): v for k, v in json.loads(SCHED.read_text(encoding="utf-8")).items()}
    code6 = lambda item: str(item[0] if isinstance(item, (list, tuple)) else item) \
        .split("_")[0].split(".")[0].zfill(6)  # noqa: E731
    rows = []
    for dd, grp in h.groupby("start"):
        lst = s.get(dd)
        if lst is None:
            continue
        held = set(grp["code"])
        order = {code6(c): i + 1 for i, c in enumerate(lst)}
        rks = [order.get(c, 999) for c in held]
        my_book = [code6(c) for c in lst[:10]]
        prec = float(np.mean([c in held for c in my_book])) if my_book else np.nan
        rows.append(dict(date=dd, in10=float(np.mean([r <= 10 for r in rks])),
                         in20=float(np.mean([r <= 20 for r in rks])), precision=prec))
    df = pd.DataFrame(rows)
    df["year"] = df["date"].dt.year
    print("\n=== #9 tracking ===")
    print(df[["in10", "in20", "precision"]].mean().round(3).to_string())
    print(df.groupby("year")[["in10", "in20", "precision"]].mean().round(3).to_string())
    t = pd.read_excel(XLSX, sheet_name="调仓详情")
    t["d"] = pd.to_datetime(t["开始日期"], errors="coerce")
    t = t[t["d"].notna() & (t["d"] <= pd.Timestamp(end))]
    g_empty = set(t[t["股票只数"] == 0]["d"])
    l_empty = {k for k, v in s.items() if not v}
    print(f"empty periods: 果仁={len(g_empty)}  local={len(l_empty)}  overlap={len(g_empty & l_empty)}")


def main():
    ap = argparse.ArgumentParser()
    for flag in ("build-base", "build-fin", "build-div", "build-idx", "schedule", "factor-parity",
                 "run", "replay", "compare"):
        ap.add_argument(f"--{flag}", action="store_true")
    ap.add_argument("--end", default="2026-02-27")
    ap.add_argument("--cost", type=float, default=0.002)
    ap.add_argument("--divvol", default="a", choices=("a", "b"))
    a = ap.parse_args()
    if a.build_base:
        build_base(end=a.end)
    if a.build_fin:
        build_fin()
    if a.build_div:
        build_div(a.end)
    if a.build_idx:
        build_idx(a.end)
    if a.schedule:
        build_schedule(a.end, divvol=a.divvol)
    if a.factor_parity:
        factor_parity(a.end)
    if a.run:
        run(end=a.end, cost_side=a.cost)
    if a.replay:
        run(end=a.end, cost_side=a.cost, replay=True)
    if a.compare:
        compare(a.end)


if __name__ == "__main__":
    main()
