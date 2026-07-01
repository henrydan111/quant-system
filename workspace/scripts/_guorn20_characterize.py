# -*- coding: utf-8 -*-
"""Phase-A/B data characterization for the 20-strategy 果仁 portfolio re-weighting study.

NOT the optimization. This only:
  1. extracts the daily total-return series (收益曲线 sheet) for the 20 live-portfolio books
  2. aligns them on a common trading calendar, reports coverage
  3. reconstructs per-strategy CAGR/vol/Sharpe/MDD/Calmar and CROSS-CHECKS vs the
     果仁 summary CSV (data-integrity gate — if our reconstruction != 果仁's headline, stop)
  4. correlation structure + style-group clustering
  5. equal-weight (monthly-rebal) baseline + risk-contribution decomposition
  6. persists the aligned daily-returns matrix to parquet for the optimization phase

All descriptive/full-sample — no walk-forward, no weight search here.
"""
from __future__ import annotations
import sys, time
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"E:\量化系统")
from src.result_analysis import metrics as M

DL = Path(r"E:\量化系统\Knowledge\果仁回测结果")
OUT_DIR = Path(r"E:\量化系统\workspace\research\idea_sourcing\guorn")
SUMMARY = DL / "_汇总_收益统计.csv"

# nn -> (name, style_group) for the 20 live-portfolio books
PORT = [
    (1,  "sm_01_成长动量",          "A_微盘成长动量"),
    (5,  "sm_01_成长_v1",           "A_微盘成长动量"),
    (6,  "sm_01_成长高贝塔@TMT_v1", "A_微盘成长动量"),
    (10, "sm_双创研发强度_v1",       "A_微盘成长动量"),
    (7,  "sm_大制造GARP_v3",        "B_GARP质量"),
    (9,  "sm_GARP_illiq",          "B_GARP质量"),
    (19, "value_红利低波_v2",        "C_价值红利低波"),
    (20, "value_红利低波_央企_v1",   "C_价值红利低波"),
    (21, "value_红利低波_重股息_v1", "C_价值红利低波"),
    (22, "value_AH_低溢价GARP_v1",  "C_价值红利低波"),
    (23, "value_FCF_非金sm_v2",     "C_价值红利低波"),
    (24, "value_创业板sm_v1",        "C_价值红利低波"),
    (42, "成长_机构预期@周期_v1",    "D_成长周期分析师"),
    (43, "成长_净利润断层_v2",       "D_成长周期分析师"),
    (44, "成长_双创_GARP@周期_v2",   "D_成长周期分析师"),
    (45, "成长_隔夜动量@周期",       "D_成长周期分析师"),
    (48, "成长_高波@周期",          "D_成长周期分析师"),
    (53, "ST_大市值_v3",            "E_特殊_ST多资产"),
    (31, "MultiA_风险平价_v1",      "E_特殊_ST多资产"),
    (29, "MultiA_动量18",           "E_特殊_ST多资产"),
]

def load_curve(nn: int) -> pd.Series:
    cands = sorted(DL.glob(f"{nn:02d}_*.xlsx"))
    cands = [c for c in cands if "__daily_curve" not in c.name]
    if not cands:
        raise FileNotFoundError(f"no xlsx for nn={nn}")
    p = cands[0]
    cur = pd.read_excel(p, sheet_name="收益曲线", header=None)
    c = cur.iloc[1:].copy()
    c.columns = ["date", "bench_cum", "strat_cum", "strat_ret", "position", "strat_turn", "bench_ret"][: c.shape[1]]
    c["date"] = pd.to_datetime(c["date"])
    c = c.set_index("date").sort_index()
    # reconstruct daily simple return from the cumulative level (4-dec but it is the level, less drift)
    nav = 1.0 + pd.to_numeric(c["strat_cum"], errors="coerce")
    ret = nav / nav.shift(1) - 1.0
    ret.iloc[0] = nav.iloc[0] - 1.0   # day-1 vs implicit NAV=1
    ret_col = pd.to_numeric(c["strat_ret"], errors="coerce")  # 果仁-exported daily return
    return ret, ret_col, p.name

print("=== loading 20 daily curves ===")
rets_cum, rets_exp = {}, {}
t0 = time.time()
for nn, name, grp in PORT:
    r_cum, r_exp, fn = load_curve(nn)
    rets_cum[name] = r_cum
    rets_exp[name] = r_exp
    print(f"  nn={nn:02d} {name:28s} {fn:40s} n={r_cum.notna().sum():4d} "
          f"{r_cum.index.min().date()}..{r_cum.index.max().date()}")
print(f"  loaded in {time.time()-t0:.1f}s")

R_cum = pd.DataFrame(rets_cum).sort_index()
R_exp = pd.DataFrame(rets_exp).sort_index()
print(f"\nunion calendar: {R_cum.shape[0]} days {R_cum.index.min().date()}..{R_cum.index.max().date()}")
print("per-strategy NaN count on union calendar:")
nan_ct = R_cum.isna().sum()
for n in R_cum.columns:
    if nan_ct[n] > 0:
        print(f"   {n}: {nan_ct[n]} NaN")
print("  (strategies with 0 NaN not listed)" if (nan_ct == 0).any() else "")

# common (intersection) window where ALL 20 have data
common = R_cum.dropna(how="any")
print(f"\nintersection window (all-20 present): {common.shape[0]} days "
      f"{common.index.min().date()}..{common.index.max().date()}")

# ---- integrity check: reconstructed full-sample stats vs 果仁 summary CSV ----
summ = pd.read_csv(SUMMARY, encoding="utf-8-sig")
summ["策略"] = summ["策略"].astype(str)
sm = summ.set_index("策略")
print("\n=== INTEGRITY: reconstructed (from strat_cum) vs 果仁 summary CSV ===")
print(f"{'strategy':28s} {'CAGR%':>7s} {'果仁':>7s} | {'MDD%':>7s} {'果仁':>7s} | {'Shrp':>5s} {'果仁':>5s} | {'cum-vs-exp tot%':>14s}")
rows = []
for nn, name, grp in PORT:
    r = R_cum[name].dropna()
    re = R_exp[name].dropna()
    cagr = M.calculate_cagr(r) * 100
    mdd = M.calculate_max_drawdown(r) * 100
    shrp = M.calculate_sharpe_ratio(r, risk_free_rate=0.0)
    tot_cum = ((1 + r).prod() - 1) * 100
    tot_exp = ((1 + re).prod() - 1) * 100
    g_cagr = sm.loc[name, "年化收益%"] if name in sm.index else np.nan
    g_mdd = sm.loc[name, "最大回撤%"] if name in sm.index else np.nan
    g_shrp = sm.loc[name, "夏普"] if name in sm.index else np.nan
    rows.append((name, grp, cagr, mdd, shrp))
    print(f"{name:28s} {cagr:7.1f} {g_cagr:7.1f} | {mdd:7.1f} {g_mdd:7.1f} | {shrp:5.2f} {g_shrp:5.2f} | "
          f"cum={tot_cum:8.0f} exp={tot_exp:8.0f}")

# ---- correlation structure (use exported daily returns, intersection window) ----
Rc = R_exp.reindex(columns=[n for _, n, _ in PORT]).dropna(how="any")
corr = Rc.corr()
print(f"\n=== correlation (exported daily ret, intersection n={Rc.shape[0]}) ===")
avg_corr = (corr.sum(axis=1) - 1) / (len(corr) - 1)
print("avg pairwise corr to other 19 (high = redundant):")
for n in avg_corr.sort_values(ascending=False).index:
    print(f"   {n:28s} {avg_corr[n]:.3f}")
print(f"\noverall mean pairwise corr = {(corr.values[np.triu_indices_from(corr.values,1)]).mean():.3f}")

# style-group block correlations
groups = {}
for nn, name, grp in PORT:
    groups.setdefault(grp, []).append(name)
print("\ngroup-mean intra/inter correlation:")
gkeys = sorted(groups)
gcorr = pd.DataFrame(index=gkeys, columns=gkeys, dtype=float)
for ga in gkeys:
    for gb in gkeys:
        sub = corr.loc[groups[ga], groups[gb]].values
        if ga == gb:
            m = sub[np.triu_indices_from(sub, 1)].mean() if len(groups[ga]) > 1 else np.nan
        else:
            m = sub.mean()
        gcorr.loc[ga, gb] = m
print(gcorr.to_string(float_format=lambda x: f"{x:.2f}"))

# ---- equal-weight baseline (monthly rebalance to 1/N) + risk contribution ----
N = Rc.shape[1]
w_ew = pd.Series(1.0 / N, index=Rc.columns)
# monthly-rebal EW: weight resets to 1/N at each month start, drifts within month
def backtest_fixed_target(R, w_target, rebal="ME"):
    w_target = w_target / w_target.sum()
    rebal_days = R.resample(rebal).last().index
    port = []
    w = w_target.copy()
    prev_month = None
    for dt, row in R.iterrows():
        if prev_month is None or dt.to_period("M") != prev_month:
            w = w_target.copy()
            prev_month = dt.to_period("M")
        r_t = float((w * row).sum())
        port.append((dt, r_t))
        w = w * (1 + row)
        w = w / w.sum()
    return pd.Series(dict(port)).sort_index()

ew = backtest_fixed_target(Rc, w_ew)
print("\n=== EQUAL-WEIGHT baseline (monthly rebal to 1/20, intersection window) ===")
print(f"  CAGR  {M.calculate_cagr(ew)*100:6.2f}%")
print(f"  vol   {M.calculate_volatility(ew)*100:6.2f}%")
print(f"  Sharpe{M.calculate_sharpe_ratio(ew, risk_free_rate=0.0):6.2f}")
print(f"  MDD   {M.calculate_max_drawdown(ew)*100:6.2f}%")
print(f"  Calmar{M.calculate_calmar_ratio(ew):6.2f}")
print(f"  Sortino{M.calculate_sortino_ratio(ew, risk_free_rate=0.0):6.2f}")

# risk contribution under EW (full-sample daily cov, annualized)
Sigma = Rc.cov().values * 252
w = w_ew.values
port_var = float(w @ Sigma @ w)
mrc = Sigma @ w                      # marginal risk contribution
rc = w * mrc / port_var             # % risk contribution (sums to 1)
rc_s = pd.Series(rc, index=Rc.columns)
vol_i = pd.Series(np.sqrt(np.diag(Sigma)), index=Rc.columns)
print(f"\nEW diversification: port vol {np.sqrt(port_var)*100:.1f}% vs avg-asset vol "
      f"{vol_i.mean()*100:.1f}%  (div ratio {vol_i.mean()/np.sqrt(port_var):.2f})")
print("EW capital 5% each, but RISK contribution is skewed:")
print(f"{'strategy':28s} {'vol%':>6s} {'riskContrib%':>12s}")
for n in rc_s.sort_values(ascending=False).index:
    print(f"   {n:28s} {vol_i[n]*100:6.1f} {rc_s[n]*100:11.1f}")
print("\nrisk contribution by STYLE GROUP (capital is 4/2/6/5/3 = 20/10/30/25/15%):")
grp_of = {n: g for _, n, g in PORT}
rc_grp = rc_s.groupby(grp_of).sum().sort_values(ascending=False)
cap_grp = w_ew.groupby(grp_of).sum()
for g in rc_grp.index:
    print(f"   {g:22s} capital {cap_grp[g]*100:5.1f}%   risk {rc_grp[g]*100:5.1f}%")

# ---- persist aligned matrix for the optimization phase ----
out_parq = OUT_DIR / "guorn20_daily_returns.parquet"
Rc.to_parquet(out_parq)
meta = pd.DataFrame(PORT, columns=["nn", "name", "style_group"])
meta.to_csv(OUT_DIR / "guorn20_meta.csv", index=False, encoding="utf-8-sig")
print(f"\n[saved] {out_parq}  shape={Rc.shape}")
print(f"[saved] {OUT_DIR / 'guorn20_meta.csv'}")
