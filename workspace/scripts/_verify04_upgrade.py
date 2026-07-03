"""#4 sm_GARP_illiq UPGRADE — unlock 9 of the 12 omitted weight-units (13/25 → 22/25).

SCRIPT_STATUS: Class-B parity diagnostic (2026-07-02). Companion to guorn_verify_04_garp.py (kept intact).
Baseline: +32.24% vs 果仁 +49.59% at 13/25 weight. Unlocks (recon 2026-07-02, all re-probed):
  bpfin(1)            BP筹资市值比调整 — the v7/v8-validated pctrank-OLS composite.
  ep_core_neut(1)     HNeutralize(CoreProfitQ/总市值, ln(总市值), 0) — all-A resid; ranked 一级行业内.
  mi_rndqp(1)         HneutralizeMI(Hwinsorize(CoreProfitQGr,5%,5%)) — winsor → within-L1 ln(mv) resid
                      (semantics variant A; forum answer login-gated — calibrate vs the xlsx truth column).
  ebitda_ev(1)        EBITDAQ/EV; EBITDAQ = ni_attr_sq + fin_exp_sq(0-fill) + D&A(cum-diff, semi-annual);
                      EV = 总市值×1e4 + lt_borr + st_borr + bond_payable + minority_int − money_cap×2(果仁
                      author bug, VERBATIM) − trad_asset, absent legs 0-fill (fix-11 class).
  gp_ev(1)            (rev_sq0 − cost_sq0)/EV, 一级行业内.
  fcf_gr(1)+fcf_mv(1) FCFQ_重算 = n_cashflow_act_sq − c_pay_acq_const_fiolta_sq + n_recp_disp_fiolta_sq
                      + D&A_sq (处置 re-probe = 100%; D&A via cum-differencing).
  express_gr(1)       业绩快报归母净利QGr%PY — raw express direct-read (dividends-caliber precedent),
                      ALIVE-WINDOW: valid iff express period == q0_period + 1 quarter (auto-dies when the
                      real report lands — the #1 forecast lesson).
  core_qoq_ttm(1)     CoreProfitQGr%PQ − CoreProfitTTMGr%PY — depth-9 q4..q7 + fix-12 TTM shift.
Also: CoreProfitQGr (w2) rebuilt with the fix-11 0-fill (f_CoreProfitQGr_v2).
Still omitted (3/25): 波动率_季度指标(12q — needs q0..q15), 营收增长−3年复合, CoreProfitTTM−3Y (12q+ back).
D&A single-quarter derivation: da_sq_k = cum_k − cum_{k+1} (both reported) else cum_k − cum_{k+2}
(2-quarter flow, semi-annual reporters) else cum_k (FY-first) — calibrated vs the xlsx EBITDAQ%EV / FCF cols.
NON-FORMAL parity artifact.
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
import guorn_verify_04_garp as g4                                        # noqa: E402

OUT = ROOT / "workspace" / "outputs" / "guorn_parity"
CACHE = g4.CACHE
SCHED_V2 = OUT / "verify04b_schedule.json"
XLSX = g4.XLSX
EXPRESS_GLOB = str(ROOT / "data" / "fundamentals" / "express" / "express_*.parquet")

WEIGHTS_V2 = dict(g4.WEIGHTS)                       # (weight, dir, scope)
WEIGHTS_V2.update({
    "CoreProfitQGr":   (2, +1, "all"),              # v2 frame (0-fill) swapped in at load
    "bpfin":           (1, +1, "all"),
    "ep_core_neut":    (1, +1, "ind"),
    # mi_rndqp EXCLUDED (parity sp −0.18 — my HneutralizeMI variant is the WRONG semantics; worse than
    # omitting; revisit with zscore/raw-mv/dummy variants against the xlsx truth column)
    "ebitda_ev":       (1, +1, "ind"),
    "gp_ev":           (1, +1, "ind"),
    "fcf_gr":          (1, +1, "all"),
    "fcf_mv":          (1, +1, "all"),
    "express_gr":      (1, +1, "all"),
    "core_qoq_ttm":    (1, +1, "all"),
})
TOTAL_W_V2 = sum(w for w, _, _ in WEIGHTS_V2.values())

# v3 = v1 + ONLY the penny-validated additions (v2 MEASURED FAIL: +15.09% ≪ v1 +32.24% — the sp 0.7-0.85
# approximations [ebitda_ev/fcf_gr/fcf_mv/ep_core_neut] are net rank NOISE at composite level; the ILLIQ
# lesson again: factor-standalone fidelity ≠ book fidelity, keep only measured improvements).
WEIGHTS_V3 = dict(g4.WEIGHTS)
WEIGHTS_V3.update({
    "CoreProfitQGr": (2, +1, "all"),       # fix-11 0-fill frame
    "bpfin":         (1, +1, "all"),       # sp 0.982
    "gp_ev":         (1, +1, "ind"),       # sp 0.981
    "express_gr":    (1, +1, "all"),       # sp 0.990 penny
    "core_qoq_ttm":  (1, +1, "all"),       # sp 0.945 penny
})
TOTAL_W_V3 = sum(w for w, _, _ in WEIGHTS_V3.values())
SCHED_V3 = OUT / "verify04c_schedule.json"


def _qlib_init():
    import qlib
    from qlib.config import REG_CN
    qlib.init(provider_uri=str(ROOT / "data" / "qlib_data"), region=REG_CN, kernels=1)


def build_upgrade():
    from qlib.data import D
    _qlib_init()
    close = pd.read_parquet(CACHE / "e_close_raw.parquet")
    grid = close.index
    insts = list(close.columns)
    q = lambda b, qs: [f"${b}{i}" for i in qs]  # noqa: E731
    CORE6 = ("revenue", "oper_cost", "admin_exp", "sell_exp", "fin_exp", "biz_tax_surchg")
    fields = sorted(set(
        sum((q(f"{b}_sq_q", range(8)) for b in CORE6), [])
        + q("stot_cash_in_fnc_act_sq_q", range(4))
        + q("n_cashflow_act_sq_q", (0, 4)) + q("c_pay_acq_const_fiolta_sq_q", (0, 4))
        + q("n_recp_disp_fiolta_sq_q", (0, 4))
        + q("depr_fa_coga_dpba_cum_q", range(9)) + q("amort_intang_assets_cum_q", range(9))
        + q("lt_amort_deferred_exp_cum_q", range(9))
        + q("n_income_cum_q", range(9)) + q("n_income_sq_q", range(4))
        + q("n_income_attr_p_cum_q", (0,)) + q("n_income_attr_p_sq_q", (0, 1, 2, 3))
        + ["$lt_borr_q0", "$st_borr_q0", "$bond_payable_q0", "$minority_int_q0",
           "$money_cap_q0", "$trad_asset_q0", "$total_hldr_eqy_exc_min_int_q0"]))
    P = {}
    for k in range(0, len(fields), 6):
        batch = fields[k:k + 6]
        df = D.features(insts, batch, start_time=str(grid[0].date()), end_time=str(grid[-1].date()), freq="day")
        for c in batch:
            dt = "float64" if c.startswith(("$n_income", "$depr", "$amort", "$lt_amort")) else "float32"
            # reindex to the FULL cache column set — D.features drops no-data insts (5421 vs 5425)
            P[c.replace("$", "")] = (df[c].unstack(level=0).sort_index().reindex(grid).ffill()
                                     .reindex(columns=insts).astype(dt))
        print(f"[upg] {min(k+6, len(fields))}/{len(fields)}", flush=True)
        del df
    EPS = 1e-9
    safe = lambda n, d: (n / d.where(d.abs() > EPS)).replace([np.inf, -np.inf], np.nan)  # noqa: E731
    zc = lambda fr: fr.fillna(0.0)  # noqa: E731
    tmv = pd.read_parquet(CACHE / "f_mktcap.parquet").reindex(columns=close.columns)
    ind = pd.read_parquet(CACHE / "industry.parquet").reindex(columns=close.columns) \
        .replace({"nan": np.nan, "None": np.nan})

    core = lambda qq: (P[f"revenue_sq_q{qq}"] - zc(P[f"oper_cost_sq_q{qq}"])  # noqa: E731
                       - (zc(P[f"admin_exp_sq_q{qq}"]) + zc(P[f"sell_exp_sq_q{qq}"]) + zc(P[f"fin_exp_sq_q{qq}"]))
                       - zc(P[f"biz_tax_surchg_sq_q{qq}"]))
    c_ = {i: core(i) for i in range(8)}
    safe(c_[0] - c_[4], c_[4].abs()).astype("float32").to_parquet(CACHE / "f_CoreProfitQGr_v2.parquet")
    ttm0 = c_[0] + c_[1] + c_[2] + c_[3]
    ttm4 = c_[4] + c_[5] + c_[6] + c_[7]
    (safe(c_[0] - c_[1], c_[1].abs()) - safe(ttm0 - ttm4, ttm4.abs())) \
        .astype("float32").to_parquet(CACHE / "f_core_qoq_ttm.parquet")

    # --- D&A single-quarter (cum-differencing, semi-annual tolerant) ---
    def da_cum(i):
        return (zc(P[f"depr_fa_coga_dpba_cum_q{i}"]) + zc(P[f"amort_intang_assets_cum_q{i}"])
                + zc(P[f"lt_amort_deferred_exp_cum_q{i}"])).where(
            P[f"depr_fa_coga_dpba_cum_q{i}"].notna() | P[f"amort_intang_assets_cum_q{i}"].notna()
            | P[f"lt_amort_deferred_exp_cum_q{i}"].notna())

    dac = {i: da_cum(i) for i in range(9)}
    # ni-based Q1 phase detector (which slot is a fiscal-Q1) to stop cross-FY differencing
    cum = {i: P[f"n_income_cum_q{i}"] for i in range(9)}
    sqni = {i: P[f"n_income_sq_q{i}"] for i in range(4)}
    q1_stack = np.stack([(np.isclose(cum[i].values, sqni[i].values, rtol=1e-6, atol=1.0)
                          & cum[i].notna().values & sqni[i].notna().values) for i in range(4)], axis=0)
    kidx = q1_stack.argmax(axis=0).astype("float64")
    kidx[~q1_stack.any(axis=0)] = np.nan
    k_first = pd.DataFrame(kidx, index=grid, columns=close.columns)     # latest Q1 slot index (0..3)

    def da_sq(k):
        is_q1 = pd.DataFrame(False, index=grid, columns=close.columns)
        for kk in range(4):
            is_q1 |= (k_first == kk) & (((k - kk) % 4) == 0)            # slot k is a fiscal Q1
        d1 = dac[k] - dac[k + 1]
        d2 = dac[k] - dac[k + 2] if k + 2 <= 8 else pd.DataFrame(np.nan, index=grid, columns=close.columns)
        out = dac[k].where(is_q1, d1.where(d1.notna(), d2))
        return out

    da0, da4 = da_sq(0), da_sq(4)
    ni0 = P["n_income_attr_p_sq_q0"]
    fin0 = zc(P["fin_exp_sq_q0"])
    ebitda0 = ni0 + fin0 + zc(da0)
    ev = (tmv * 1e4 + zc(P["lt_borr_q0"]) + zc(P["st_borr_q0"]) + zc(P["bond_payable_q0"])
          + zc(P["minority_int_q0"]) - zc(P["money_cap_q0"]) - zc(P["money_cap_q0"])   # 果仁 bug: ×2 VERBATIM
          - zc(P["trad_asset_q0"]))
    safe(ebitda0, ev).astype("float32").to_parquet(CACHE / "f_ebitda_ev.parquet")
    rev0, cost0 = P["revenue_sq_q0"], P["oper_cost_sq_q0"]
    safe(rev0 - zc(cost0), ev).astype("float32").to_parquet(CACHE / "f_gp_ev.parquet")
    fcf = lambda qq, da: (P[f"n_cashflow_act_sq_q{qq}"] - zc(P[f"c_pay_acq_const_fiolta_sq_q{qq}"])  # noqa: E731
                          + zc(P[f"n_recp_disp_fiolta_sq_q{qq}"]) + zc(da))
    f0, f4 = fcf(0, da0), fcf(4, da4)
    safe(f0 - f4, f4.abs()).astype("float32").to_parquet(CACHE / "f_fcf_gr.parquet")
    safe(f0, tmv * 1e4).astype("float32").to_parquet(CACHE / "f_fcf_mv.parquet")

    # --- cross-sectional composites (all-A ≈ build universe: main+中小+创+科创, BSE excluded ✓果仁) ---
    def resid_daily(Y, X, groups=None):
        valid = Y.notna() & X.notna()
        if groups is None:
            Ym, Xm = Y.where(valid), X.where(valid)
            n = valid.sum(axis=1)
            sy, sx = Ym.sum(axis=1), Xm.sum(axis=1)
            sxy, sxx = (Ym * Xm).sum(axis=1), (Xm ** 2).sum(axis=1)
            cov = sxy - sx * sy / n
            var = sxx - sx ** 2 / n
            b = (cov / var.where(var.abs() > 1e-12)).where(n >= 30)
            a = sy / n - b * sx / n
            return Ym.sub(a, axis=0).sub(Xm.mul(b, axis=0))
        out = pd.DataFrame(np.nan, index=Y.index, columns=Y.columns)
        for pday in Y.index:
            y, x, g = Y.loc[pday], X.loc[pday], groups.loc[pday] if pday in groups.index else None
            if g is None or g.notna().sum() == 0:
                continue
            df = pd.DataFrame({"y": y, "x": x, "g": g})

            def f(sub):
                s = sub.dropna(subset=["y", "x"])
                if len(s) < 3 or s["x"].std() == 0:
                    return sub["y"] - sub["y"].mean()
                b = s["y"].cov(s["x"]) / s["x"].var()
                a = s["y"].mean() - b * s["x"].mean()
                return sub["y"] - (a + b * sub["x"])
            r = df.groupby("g", group_keys=False).apply(f)
            if isinstance(r, pd.Series):
                out.loc[pday] = r.reindex(Y.columns)
        return out

    lmv = np.log(tmv.where(tmv > 0))
    bp = safe(P["total_hldr_eqy_exc_min_int_q0"], tmv * 1e4)
    finr = safe(sum(P[f"stot_cash_in_fnc_act_sq_q{i}"] for i in range(4)), tmv * 1e4)
    resid_daily(bp.rank(axis=1, pct=True), finr.rank(axis=1, pct=True)) \
        .astype("float32").to_parquet(CACHE / "f_bpfin.parquet")
    ep_core = safe(c_[0], tmv * 1e4)
    resid_daily(ep_core, lmv).astype("float32").to_parquet(CACHE / "f_ep_core_neut.parquet")
    cg = pd.read_parquet(CACHE / "f_CoreProfitQGr_v2.parquet").reindex(columns=close.columns)
    lo = cg.quantile(0.05, axis=1)
    hi = cg.quantile(0.95, axis=1)
    cg_w = cg.clip(lower=lo, upper=hi, axis=0)
    # within-L1 resid is loop-based — restrict to WEEKLY pdays would break daily rebalances; run full grid
    resid_daily(cg_w, lmv, groups=ind).astype("float32").to_parquet(CACHE / "f_mi_rndqp.parquet")

    # --- express (业绩快报) flash-quarter YoY growth, alive-window = exactly one quarter ahead of q0 ---
    import glob as _glob
    ex = pd.concat([pd.read_parquet(f) for f in _glob.glob(EXPRESS_GLOB)], ignore_index=True)
    ex["ann"] = pd.to_datetime(ex["ann_date"], format="%Y%m%d", errors="coerce")
    ex["ped"] = pd.to_datetime(ex["end_date"], format="%Y%m%d", errors="coerce")  # noqa: unsafe-pit-dates[PIT001] reason: fiscal LABEL; visibility gated on ann below
    ex = ex[ex["ann"].notna() & ex["ped"].notna() & ex["n_income"].notna()]
    ex["c"] = ex["ts_code"].str.replace(".", "_", regex=False).str.upper()
    upmap = {str(c).upper(): c for c in close.columns}
    ex = ex[ex["c"].isin(upmap)].sort_values("ann")
    # per (code): as-of series of (period_ord, express cumulative NP)
    q0_quarter = k_first + 1                                            # reported q0's quarter number
    _QEND_MD = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}
    niattr_cum0 = P["n_income_attr_p_cum_q0"]
    niattr_sq = {i: P[f"n_income_attr_p_sq_q{i}"] for i in range(4)}
    out = pd.DataFrame(np.nan, index=grid, columns=close.columns)
    for inst, grp in ex.groupby("c"):
        col = upmap[inst]
        if col not in out.columns:
            continue
        for _, r in grp.iterrows():
            pord = pd.Period(r["ped"], freq="Q").ordinal
            start_i = grid.searchsorted(r["ann"])
            for i in range(start_i, min(start_i + 130, len(grid))):     # cap window ~6 months
                dgrid = grid[i]
                kq = q0_quarter.at[dgrid, col] if col in q0_quarter.columns else np.nan
                if pd.isna(kq):
                    continue
                qn = int(kq)
                mm, dd2 = _QEND_MD[qn]
                q0y = dgrid.year if pd.Timestamp(dgrid.year, mm, dd2) <= dgrid else dgrid.year - 1
                q0_ord = pd.Period(year=q0y, quarter=qn, freq="Q").ordinal
                if pord != q0_ord + 1:                                  # alive iff exactly next quarter
                    if pord <= q0_ord:
                        break                                           # real report landed -> dead
                    continue
                ytd = niattr_cum0.at[dgrid, col]
                ref3 = niattr_sq[3].at[dgrid, col]
                if pd.isna(ytd) or pd.isna(ref3) or abs(ref3) < 1:
                    continue
                out.at[dgrid, col] = (r["n_income"] - ytd - ref3) / abs(ref3)
    out.astype("float32").to_parquet(CACHE / "f_express_gr.parquet")
    print("[upg] saved CoreProfitQGr_v2 / core_qoq_ttm / ebitda_ev / gp_ev / fcf_gr / fcf_mv / bpfin / "
          "ep_core_neut / mi_rndqp / express_gr", flush=True)


def _load_v2():
    cols = pd.read_parquet(CACHE / "e_close_raw.parquet").columns
    f = {}
    for n in WEIGHTS_V2:
        p = CACHE / (f"f_{n}.parquet" if n != "CoreProfitQGr" else "f_CoreProfitQGr_v2.parquet")
        f[n] = pd.read_parquet(p).reindex(columns=cols)
    ind = pd.read_parquet(CACHE / "industry.parquet").reindex(columns=cols)
    e = {n: pd.read_parquet(CACHE / f"e_{n}.parquet").reindex(columns=cols)
         for n in ("close_raw", "illiq5")}
    return f, ind, e


def build_schedule_v2(start="2014-01-01", end="2026-02-27", headroom=25, variant="v2"):
    global WEIGHTS_V2, TOTAL_W_V2, SCHED_V2
    if variant == "v3":
        WEIGHTS_V2, TOTAL_W_V2, SCHED_V2 = WEIGHTS_V3, TOTAL_W_V3, SCHED_V3
    f, ind, e = _load_v2()
    cal = ru.trading_calendar()
    cal = cal[(cal >= pd.Timestamp(start)) & (cal <= pd.Timestamp(end))]
    close = e["close_raw"]
    grid = close.index
    insts = close.columns
    bounds = g4.LISTED_BOUNDS
    list0 = pd.Series({c: (bounds.get(str(c).upper())[0] if bounds.get(str(c).upper()) else pd.NaT)
                       for c in insts})
    sched = {}
    for d in cal:
        d = pd.Timestamp(d)
        pos = grid.searchsorted(d)
        if pos == 0:
            sched[d] = []
            continue
        pday = grid[pos - 1]
        st = ru.st_codes_on(d)
        cr = close.loc[pday]
        keep = cr.notna() & (cr >= 2.0)
        cald = (pday - list0).dt.days + 1
        keep &= (cald > 30).fillna(False)                               # 上市天数>30 (calendar)
        listed = pd.Series([(bounds.get(str(c).upper()) is not None
                             and bounds[str(c).upper()][0] <= pday <= bounds[str(c).upper()][1])
                            for c in insts], index=insts)
        keep &= listed
        keep &= pd.Series([str(c).upper() not in st for c in insts], index=insts)
        from guorn_universe import in_guorn_universe
        keep &= pd.Series([in_guorn_universe(c) for c in insts], index=insts)   # #4: EXCL 科创板
        ilq = e["illiq5"].loc[pday].where(keep)
        keep &= (ilq.rank(pct=True) <= 0.65).fillna(False)              # ILLIQ(5) 0-65% (more-liquid 65%)
        elig = keep[keep].index
        if len(elig) < headroom:
            sched[d] = []
            continue
        comp = g4.composite_row(f, ind, pday, elig, WEIGHTS_V2, TOTAL_W_V2)
        top = comp.sort_values(ascending=False).head(headroom)
        sched[d] = [str(c).upper().replace("_", ".") for c in top.index]
    SCHED_V2.write_text(json.dumps({str(k.date()): v for k, v in sched.items()}, ensure_ascii=False),
                        encoding="utf-8")
    print(f"[sched-v2] {sum(1 for v in sched.values() if v)}/{len(cal)} non-empty", flush=True)


XLSX_COLS = {"bpfin": "BP筹资市值比调整", "mi_rndqp": "指标标准化后中性化MI(RNDQP)",
             "ep_core_neut": "指标1指标2中性化(EPCOREPROFITQ,总市值,0)",
             "ebitda_ev": "EBITDAQ%EV",
             "gp_ev": "公式((营业收入(单季度)-营业成本(单季度))/EV)",
             "fcf_gr": "FCFQ_重算Gr%PYQ", "fcf_mv": "FCFQ%总市值",
             "express_gr": "业绩快报归母净利QGr%PY", "core_qoq_ttm": "公式(COREPROFITQGr%PQ-COREPROFITTTMGr%PY)"}


def factor_parity(end="2026-02-27"):
    cols = pd.read_parquet(CACHE / "e_close_raw.parquet").columns
    h = pd.read_excel(XLSX, sheet_name="各阶段持仓详单")
    h["start"] = pd.to_datetime(h["开始日期"], errors="coerce")
    h = h[h["start"].notna() & (h["start"] <= pd.Timestamp(end))].copy()
    h["code"] = h["股票代码"].astype(str).str.zfill(6)
    print("xlsx cols:", [c for c in h.columns if any(k in str(c) for k in
                                                     ("中性", "EBITDA", "FCF", "快报", "COREPROFIT", "BP筹资"))])
    grid = pd.read_parquet(CACHE / "e_close_raw.parquet").index
    up = {str(c).split("_")[0]: c for c in cols}
    recs = {k: [] for k in XLSX_COLS}
    frames = {}
    for k in XLSX_COLS:
        p = CACHE / f"f_{k}.parquet"
        if p.exists():
            frames[k] = pd.read_parquet(p).reindex(columns=cols)
    for d, grp in h.groupby("start"):
        pos = grid.searchsorted(pd.Timestamp(d))
        if pos == 0:
            continue
        pday = grid[pos - 1]
        for _, r in grp.iterrows():
            inst = up.get(r["code"])
            if inst is None:
                continue
            for k, fr in frames.items():
                gv = pd.to_numeric(r.get(XLSX_COLS[k]), errors="coerce")
                lv = fr.loc[pday].get(inst, np.nan) if pday in fr.index else np.nan
                if pd.notna(gv) and pd.notna(lv):
                    recs[k].append((float(gv), float(lv)))
    print(f"\n=== #4 UPGRADE per-factor value agreement vs xlsx (held names) ===")
    for k, pairs in recs.items():
        if not pairs:
            print(f"  {k:14} NO DATA (column absent or all-NaN)")
            continue
        a = pd.DataFrame(pairs, columns=["g", "l"])
        rel = ((a["l"] - a["g"]).abs() / a["g"].abs().clip(lower=1e-9)).median()
        sign = (np.sign(a["l"]) == np.sign(a["g"])).mean()
        sp = a["g"].corr(a["l"], method="spearman")
        print(f"  {k:14} n={len(a):6d}  medRel={rel:8.4f}  sign={sign:.3f}  sp={sp:+.3f}")


def compare(end="2026-02-27"):
    h = pd.read_excel(XLSX, sheet_name="各阶段持仓详单")
    h["start"] = pd.to_datetime(h["开始日期"], errors="coerce")
    h["code"] = h["股票代码"].astype(str).str.zfill(6)
    h = h[h["start"].notna() & (h["start"] <= pd.Timestamp(end))]
    res = {}
    for tag, sp_ in (("v1", g4.SCHED), ("v2", SCHED_V2)):
        s = {pd.Timestamp(k): v for k, v in json.loads(sp_.read_text(encoding="utf-8")).items()}
        code6 = lambda c: str(c).split("_")[0].split(".")[0].zfill(6)  # noqa: E731
        rows = []
        for d, grp in h.groupby("start"):
            lst = s.get(d)
            if lst is None:
                continue
            held = set(grp["code"])
            order = {code6(c): i + 1 for i, c in enumerate(lst)}
            rks = [order.get(c, 999) for c in held]
            rows.append(dict(date=d, in10=float(np.mean([r <= 10 for r in rks])),
                             in20=float(np.mean([r <= 20 for r in rks]))))
        df = pd.DataFrame(rows)
        res[tag] = df
        print(f"[{tag}] in10={df['in10'].mean():.3f}  in20={df['in20'].mean():.3f}  periods={len(df)}")
    m = res["v1"].merge(res["v2"], on="date", suffixes=("_v1", "_v2"))
    m["year"] = m["date"].dt.year
    print(m.groupby("year")[["in10_v1", "in10_v2", "in20_v1", "in20_v2"]].mean().round(3).to_string())


def run_v2(start="2014-01-01", end="2026-02-27", variant="v2"):
    from src.backtest_engine.event_driven import EventDrivenBacktester, CostConfig
    from src.backtest_engine.event_driven.exchange import FixedSlippage
    from guorn_parity_rung2_posprofit import ModelIIPosProfitStrategy
    sp_ = SCHED_V3 if variant == "v3" else SCHED_V2
    sched = {pd.Timestamp(k): v for k, v in json.loads(sp_.read_text(encoding="utf-8")).items()}
    strat = ModelIIPosProfitStrategy(sched, buy_rank=20, sell_rank=20, target_n=10, pos_max=0.13,
                                     max_holds=14, use_exits=False, rebuy_cooldown=0)
    cost = CostConfig(buy_commission=0.002, sell_commission=0.002, stamp_tax=0.0, min_commission=0.0,
                      transfer_fee=0.0)
    bt = EventDrivenBacktester(data_dir=str(ROOT / "data"))
    res = bt.run(strategy=strat, start_time=start, end_time=end, benchmark="000300.SH", account=1_000_000.0,
                 exchange_config=cost, slippage=FixedSlippage(0.0), volume_limit=0.10, hold_on_limit_up=True,
                 preload_fields=["$open", "$close", "$high", "$low", "$vol", "$amount", "$pre_close",
                                 "$adj_factor", "$up_limit", "$down_limit"])
    rep = res.report.copy()
    if "date" in rep.columns:
        rep = rep.set_index(pd.to_datetime(rep["date"]))
    net = rep["return"].astype(float)
    net.to_frame("net").to_parquet(OUT / f"verify04{'c' if variant == 'v3' else 'b'}_net.parquet")
    m = ru.goal_metrics(net)
    yr = net.groupby(net.index.year).apply(lambda r: (1 + r).prod() - 1)
    gy = g4._read_guorn_yearly()
    print("\n" + "=" * 72)
    print(f"  #4 sm_GARP_illiq [UPGRADE {variant}]  CAGR={m['cagr']:+.2%}  MDD={m['mdd']:+.2%}  "
          f"(果仁 +49.59% / −42.45; v1-13/25w +32.24%)")
    for y in sorted(yr.index):
        g = gy.get(int(y))
        gt = f"{g:+8.1%}" if g is not None else "   n/a "
        dt = f"{float(yr[y]) - g:+7.1%}" if g is not None else ""
        print(f"  {int(y)}   {float(yr[y]):+8.1%}  {gt}  {dt}")
    json.dump({"cagr": m["cagr"], "mdd": m["mdd"], "yearly": {int(k): float(v) for k, v in yr.items()},
               "variant": variant},
              open(OUT / f"verify04{'c' if variant == 'v3' else 'b'}_result.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


def main():
    ap = argparse.ArgumentParser()
    for flag in ("build-upgrade", "schedule", "factor-parity", "compare", "run"):
        ap.add_argument(f"--{flag}", action="store_true")
    ap.add_argument("--end", default="2026-02-27")
    ap.add_argument("--variant", default="v2", choices=("v2", "v3"))
    a = ap.parse_args()
    if a.build_upgrade:
        build_upgrade()
    if a.schedule:
        build_schedule_v2(end=a.end, variant=a.variant)
    if a.factor_parity:
        factor_parity(a.end)
    if a.compare:
        compare(a.end)
    if a.run:
        run_v2(end=a.end, variant=a.variant)


if __name__ == "__main__":
    main()
