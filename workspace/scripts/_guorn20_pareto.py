# -*- coding: utf-8 -*-
"""GUORN20 Pareto / efficient frontier — DESCRIPTIVE exploration (NON-FORMAL).

Honest framing (does NOT re-open the sealed holdout for selection; the decision is
LOCKED at EW per GUORN20_FINDINGS.md):
  * LEFT panel  = pre-holdout DESIGN period (2014-01..2023-05): the in-sample
    risk-return Pareto frontier + the 20 books + EW.
  * RIGHT panel = sealed HOLDOUT (2023-06..2026-06): (a) the IN-SAMPLE frontier
    WEIGHTS evaluated out-of-sample (what you'd actually get — they shrink),
    (b) the holdout's OWN ex-post frontier (perfect-hindsight ceiling, NON-investable),
    (c) the 20 books + EW + the study's frozen candidate.
The gap between (a) and (b) on the right IS the overfitting the sealed test caught.

Frontier = long-only, sum=1, 0<=w<=cap mean-variance efficient set (vary target
return), traced continuously -> "more possibilities" beyond the 8 discrete schemes.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import cvxpy as cp
from sklearn.covariance import LedoitWolf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(r"E:\量化系统")
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
from src.result_analysis import metrics as M

DATA = ROOT / "workspace/research/idea_sourcing/guorn/guorn20_daily_returns.parquet"
META = ROOT / "workspace/research/idea_sourcing/guorn/guorn20_meta.csv"
OUT = ROOT / "workspace/outputs/guorn20_reweight/guorn20_pareto.png"
FREEZE = pd.Timestamp("2023-05-31")
HSTART, HEND = pd.Timestamp("2023-06-01"), pd.Timestamp("2026-06-18")
CAP = 0.15
ANNUAL = 252

GROUP_EN = {"A_微盘成长动量": "A Microcap-Growth", "B_GARP质量": "B GARP-Quality",
            "C_价值红利低波": "C Value-Dividend", "D_成长周期分析师": "D Growth-Cycle",
            "E_特殊_ST多资产": "E Special (ST/Funds)"}
GROUP_COLOR = {"A_微盘成长动量": "#d62728", "B_GARP质量": "#ff7f0e", "C_价值红利低波": "#2ca02c",
               "D_成长周期分析师": "#9467bd", "E_特殊_ST多资产": "#1f77b4"}


def cal_cagr(r: pd.Series) -> float:
    total = float((1 + r).prod())
    yrs = (r.index[-1] - r.index[0]).days / 365.25
    return total ** (1 / yrs) - 1 if yrs > 0 else np.nan


def backtest_static(Rp: pd.DataFrame, w: np.ndarray) -> pd.Series:
    """Monthly-rebalance-to-static-target w over period Rp (drift within month)."""
    w = w / w.sum()
    arr = Rp.values
    rebal = pd.Series(range(len(Rp)), index=Rp.index).resample("ME").last().dropna().astype(int).tolist()
    rebal = sorted(set([0] + rebal))
    bounds = rebal + [len(Rp)]
    out = np.empty(len(Rp))
    for k, t0 in enumerate(rebal):
        wc = w.copy()
        for d in range(t0, bounds[k + 1]):
            out[d] = float(wc @ arr[d])
            wc = wc * (1 + arr[d]); wc = wc / wc.sum()
    return pd.Series(out, index=Rp.index)


def pt(Rp, w):
    s = backtest_static(Rp, w)
    return abs(M.calculate_max_drawdown(s)) * 100, cal_cagr(s) * 100


def frontier_weights(Rp, npts=30):
    mu = (Rp.mean() * ANNUAL).values
    cov = LedoitWolf().fit(Rp).covariance_ * ANNUAL
    n = len(mu)
    ws = []
    for tgt in np.linspace(mu.min() * 0.999, mu.max() * 0.999, npts):
        w = cp.Variable(n)
        prob = cp.Problem(cp.Minimize(cp.quad_form(w, cp.psd_wrap(cov))),
                          [cp.sum(w) == 1, w >= 0, w <= CAP, mu @ w >= tgt])
        try:
            prob.solve(solver=cp.OSQP, verbose=False)
        except Exception:
            continue
        if w.value is not None:
            wv = np.clip(np.asarray(w.value).ravel(), 0, None)
            if wv.sum() > 0:
                ws.append(wv / wv.sum())
    return ws


def pareto_envelope(pts):
    """Non-dominated set: maximize CAGR (y), minimize MDD (x). pts=list of (mdd,cagr)."""
    P = sorted(pts, key=lambda z: (z[0], -z[1]))
    env, best = [], -1e9
    for mdd, cagr in P:
        if cagr > best + 1e-9:
            env.append((mdd, cagr)); best = cagr
    return env


def main():
    R = pd.read_parquet(DATA).sort_index()
    R.index = pd.to_datetime(R.index)
    meta = pd.read_csv(META, encoding="utf-8-sig")
    grp = dict(zip(meta["name"], meta["style_group"]))
    R = R[[c for c in meta["name"] if c in R.columns]]
    n = R.shape[1]
    pre = R[R.index <= FREEZE]
    hold = R[(R.index >= HSTART) & (R.index <= HEND)]
    w_ew = np.ones(n) / n

    fw = frontier_weights(pre)          # IN-SAMPLE frontier weights
    fw_h = frontier_weights(hold)       # holdout ex-post (hindsight ceiling)
    print(f"frontier pts: pre={len(fw)} holdout-expost={len(fw_h)}")

    # points
    pre_books = [(*pt(pre, np.eye(n)[i]), grp[R.columns[i]]) for i in range(n)]
    hold_books = [(*pt(hold, np.eye(n)[i]), grp[R.columns[i]]) for i in range(n)]
    pre_ew = pt(pre, w_ew); hold_ew = pt(hold, w_ew)
    pre_front = [pt(pre, w) for w in fw]                 # in-sample frontier, in-sample
    hold_front_oos = [pt(hold, w) for w in fw]           # in-sample weights, OOS realized
    hold_front_expost = [pt(hold, w) for w in fw_h]      # holdout hindsight ceiling
    # study's dynamic frozen candidate (from frozen_candidate.json), holdout
    frozen_hold = (18.66, 41.39)   # mdd_mag%, cagr_cal% (two_stage holdout: see findings)

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(15, 6.5), sharey=False)

    # ---- LEFT: pre-holdout design
    for mdd, cagr, g in pre_books:
        a1.scatter(mdd, cagr, c=GROUP_COLOR[g], s=45, alpha=0.8, edgecolors="white", linewidths=0.5, zorder=3)
    fx = [p[0] for p in pre_front]; fy = [p[1] for p in pre_front]
    a1.plot(fx, fy, "-", color="#1f77b4", lw=2.2, label="MV efficient frontier", zorder=2)
    env = pareto_envelope([(m, c) for m, c, _ in pre_books] + pre_front)
    a1.plot([e[0] for e in env], [e[1] for e in env], "--", color="grey", lw=1.2, alpha=0.7, label="Pareto envelope", zorder=1)
    a1.scatter(*pre_ew, marker="*", s=420, c="black", edgecolors="white", linewidths=1, label="Equal-weight (EW)", zorder=5)
    a1.annotate("EW", pre_ew, textcoords="offset points", xytext=(8, 6), fontweight="bold")
    a1.set_title("DESIGN period 2014-01 .. 2023-05  (in-sample)", fontweight="bold")

    # ---- RIGHT: sealed holdout
    for mdd, cagr, g in hold_books:
        a2.scatter(mdd, cagr, c=GROUP_COLOR[g], s=45, alpha=0.8, edgecolors="white", linewidths=0.5, zorder=3)
    hx = [p[0] for p in hold_front_oos]; hy = [p[1] for p in hold_front_oos]
    a2.plot(hx, hy, "-", color="#d62728", lw=2.2, label="In-sample frontier weights, realized OOS", zorder=2)
    ex = [p[0] for p in hold_front_expost]; ey = [p[1] for p in hold_front_expost]
    a2.plot(ex, ey, ":", color="#1f77b4", lw=2.0, alpha=0.8, label="Holdout hindsight ceiling (NON-investable)", zorder=2)
    a2.scatter(*hold_ew, marker="*", s=420, c="black", edgecolors="white", linewidths=1, label="Equal-weight (EW)", zorder=5)
    a2.annotate("EW", hold_ew, textcoords="offset points", xytext=(8, 6), fontweight="bold")
    a2.scatter(*frozen_hold, marker="D", s=90, c="#7f7f7f", edgecolors="black", linewidths=1, label="Frozen candidate (two_stage)", zorder=5)
    a2.annotate("frozen\n(FAILED)", frozen_hold, textcoords="offset points", xytext=(-44, -28), fontsize=8, color="#444")
    a2.set_title("SEALED HOLDOUT 2023-06 .. 2026-06  (out-of-sample)", fontweight="bold")

    for ax in (a1, a2):
        ax.set_xlabel("Max drawdown  (%, lower = better →left)")
        ax.set_ylabel("CAGR  (%, higher = better ↑)")
        ax.grid(alpha=0.25)
        ax.legend(loc="lower right", fontsize=8, framealpha=0.9)
    # group legend (colors) on left
    from matplotlib.lines import Line2D
    handles = [Line2D([0], [0], marker="o", color="w", markerfacecolor=GROUP_COLOR[k], markersize=8, label=GROUP_EN[k])
               for k in GROUP_EN]
    a1.legend(handles=handles, loc="upper left", fontsize=7.5, title="20 books by style", framealpha=0.9)

    fig.suptitle("Guorn 20-book Pareto frontier — the in-sample frontier does NOT transfer reliably out-of-sample (decision: stay EW)",
                 fontsize=13, fontweight="bold")
    fig.text(0.5, 0.005,
             "Left (in-sample): risk-based portfolios Pareto-DOMINATE EW — the frontier reaches ~15% MDD vs EW's 32%, or EW's return at far less drawdown.  "
             "Right (sealed OOS): those SAME in-sample frontier weights (red) SCATTER unpredictably around EW and below the hindsight ceiling (blue dotted) — a few beat EW by luck, "
             "but the ONE principled pre-committed pick (frozen ◆) FAILED, and EW (★) sits in the pack.  You cannot know ex-ante which point transfers.  "
             "Frontier = long-only mean-variance, 0≤w≤15%.  NON-FORMAL; sealed-OOS decision locked at EW (GUORN20_FINDINGS.md).",
             ha="center", fontsize=7.4, wrap=True)
    fig.tight_layout(rect=[0, 0.03, 1, 0.96])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=130, bbox_inches="tight")
    print(f"saved -> {OUT}")
    # also print the numeric frontier extremes for the report
    print(f"PRE  EW=({pre_ew[0]:.1f}%,{pre_ew[1]:.1f}%)  frontier MDD range {min(fx):.1f}-{max(fx):.1f}%  CAGR {min(fy):.1f}-{max(fy):.1f}%")
    print(f"HOLD EW=({hold_ew[0]:.1f}%,{hold_ew[1]:.1f}%)  in-sample-wts OOS CAGR {min(hy):.1f}-{max(hy):.1f}%  hindsight CAGR {min(ey):.1f}-{max(ey):.1f}%")


if __name__ == "__main__":
    main()
