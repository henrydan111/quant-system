# SCRIPT_STATUS: ACTIVE — research utility (microcap timing replication, 2026-06-11)
"""Direction A (hysteresis+confirmation trend leg) and Direction B (drawdown-based
risk state; plus vol-target control) — both keeping the 8/8 capitulation leg
Timing(ma5/ma200, 0.85, 0.95). Binary position in {0,1} (no leverage), signal at
T close -> position T+1.

Windows: IS 2014-01-02..data end, OOS 2009-01-05..2013-12-31.
Anti-cherry-pick: report grid min/median/max per window; detail tables use the
grid-CENTER config, not the best cell.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUT = PROJECT_ROOT / "workspace" / "outputs" / "microcap_timing"
RF = 0.04
IS_W = slice("2014-01-02", None)
OOS_W = slice("2009-01-05", "2013-12-31")

out = pd.read_parquet(OUT / "guoren_microcap_replica.parquet")
level, ret = out["level"], out["ret"].fillna(0)
ma5, ma200 = level.rolling(5).mean(), level.rolling(200).mean()
ratio = ma5 / ma200
rarr = ratio.to_numpy()


def capitulation_state(lower=0.85, upper=0.95) -> np.ndarray:
    s = np.zeros(len(rarr), dtype=bool)
    for t in range(len(rarr)):
        if np.isnan(rarr[t]):
            s[t] = False
        elif rarr[t] < lower:
            s[t] = True
        elif rarr[t] > upper:
            s[t] = False
        else:
            s[t] = s[t - 1] if t > 0 else False
    return s


CAP = capitulation_state()


def stats_row(pos: pd.Series, label: str, window: slice, cost: float = 0.0) -> dict:
    pr = (ret * pos) - pos.diff().abs().fillna(0) * cost
    pr = pr.loc[window]
    lv = (1 + pr).cumprod()
    n_days = (lv.index[-1] - lv.index[0]).days
    ann = lv.iloc[-1] ** (365.25 / n_days) - 1
    vol = pr.std() * np.sqrt(245)
    dd = (lv / lv.cummax() - 1).min()
    return {
        "config": label,
        "ann_pct": round(ann * 100, 1),
        "vol_pct": round(vol * 100, 1),
        "mdd_pct": round(dd * 100, 1),
        "sharpe": round((ann - RF) / vol, 2),
        "flips": int(pos.loc[window].diff().abs().sum()),
    }


def make_pos(sig: np.ndarray) -> pd.Series:
    s = pd.Series(sig.astype(float), index=level.index)
    s[ratio.isna() & ~pd.Series(CAP, index=level.index)] = 0.0
    return s.shift(1).fillna(0)


# ---------- Direction A: hysteresis trend leg ----------
def trend_hysteresis(band: float, m: int) -> np.ndarray:
    """Long-state ON when ratio>1; OFF after ratio<band for m consecutive days; else hold."""
    below = rarr < band
    s = np.zeros(len(rarr), dtype=bool)
    run = 0
    for t in range(len(rarr)):
        if np.isnan(rarr[t]):
            s[t] = False
            run = 0
            continue
        run = run + 1 if below[t] else 0
        if rarr[t] > 1:
            s[t] = True
        elif run >= m:
            s[t] = False
        else:
            s[t] = s[t - 1] if t > 0 else False
    return s


# ---------- Direction B: drawdown-state risk control ----------
def dd_state(n: int, exit_x: float, reenter_y: float) -> np.ndarray:
    """Risk-OFF when dd from rolling n-day high < -exit_x; back ON when dd > -reenter_y."""
    dd = (level / level.rolling(n, min_periods=1).max() - 1).to_numpy()
    flat = np.zeros(len(dd), dtype=bool)
    for t in range(len(dd)):
        if dd[t] < -exit_x:
            flat[t] = True
        elif dd[t] > -reenter_y:
            flat[t] = False
        else:
            flat[t] = flat[t - 1] if t > 0 else False
    return ~flat


def grid_report(name: str, configs: dict[str, np.ndarray]) -> pd.DataFrame:
    rows = []
    for lab, sig in configs.items():
        pos = make_pos(sig | CAP)
        r_is = stats_row(pos, lab, IS_W)
        r_oos = stats_row(pos, lab, OOS_W)
        rows.append(
            {
                "config": lab,
                "IS_ann": r_is["ann_pct"],
                "IS_mdd": r_is["mdd_pct"],
                "IS_sharpe": r_is["sharpe"],
                "OOS_ann": r_oos["ann_pct"],
                "OOS_mdd": r_oos["mdd_pct"],
                "OOS_sharpe": r_oos["sharpe"],
                "flips_IS": r_is["flips"],
            }
        )
    g = pd.DataFrame(rows)
    g.to_csv(OUT / f"v3_grid_{name}.csv", index=False)
    print(f"\n=== {name} grid ===")
    print(g.to_string(index=False))
    print(
        f"{name} IS ann min/med/max: {g.IS_ann.min()}/{g.IS_ann.median()}/{g.IS_ann.max()}"
        f" | OOS ann min/med/max: {g.OOS_ann.min()}/{g.OOS_ann.median()}/{g.OOS_ann.max()}"
        f" | OOS mdd min/med/max: {g.OOS_mdd.min()}/{g.OOS_mdd.median()}/{g.OOS_mdd.max()}"
    )
    return g


# baselines
base_rows = []
ones = pd.Series(1.0, index=level.index)
v1_pos = make_pos((rarr > 1))
v2_pos = make_pos((rarr > 1) | CAP)
for w, wl in ((IS_W, "IS"), (OOS_W, "OOS")):
    base_rows += [
        {**stats_row(ones, "untimed", w), "window": wl},
        {**stats_row(v1_pos, "v1", w), "window": wl},
        {**stats_row(v2_pos, "v2", w), "window": wl},
    ]
print("=== baselines ===")
print(pd.DataFrame(base_rows).to_string(index=False))

# Direction A grid
a_cfgs = {}
for band in (0.96, 0.97, 0.98, 1.00):
    for m in (1, 3, 5):
        a_cfgs[f"A band={band} m={m}"] = trend_hysteresis(band, m)
ga = grid_report("A_hysteresis", a_cfgs)

# Direction B grid
b_cfgs = {}
for n in (60, 120, 250):
    for x in (0.10, 0.12, 0.15):
        for y in (0.04, 0.06, 0.08):
            b_cfgs[f"B n={n} x={int(x*100)} y={int(y*100)}"] = dd_state(n, x, y)
gb = grid_report("B_drawdown", b_cfgs)

# Vol-target control (continuous position, OR-with-capitulation via max)
print("\n=== B2 vol-target control ===")
for tgt in (0.20, 0.25):
    vol20 = ret.rolling(20).std() * np.sqrt(245)
    vp = (tgt / vol20).clip(0, 1).fillna(0)
    pos = pd.concat([vp, pd.Series(CAP.astype(float), index=level.index)], axis=1).max(axis=1).shift(1).fillna(0)
    print(pd.DataFrame([
        {**stats_row(pos, f"voltgt={tgt}", IS_W), "window": "IS"},
        {**stats_row(pos, f"voltgt={tgt}", OOS_W), "window": "OOS"},
    ]).to_string(index=False))

# ---- detail: grid-center representatives ----
repA = make_pos(trend_hysteresis(0.97, 3) | CAP)
repB = make_pos(dd_state(120, 0.12, 0.06) | CAP)
print("\n=== representatives (grid centers), with 0.2% one-way cost ===")
det = []
for w, wl in ((IS_W, "IS"), (OOS_W, "OOS")):
    det.append({**stats_row(repA, "A band=0.97 m=3", w, cost=0.002), "window": wl})
    det.append({**stats_row(repB, "B n=120 x=12 y=6", w, cost=0.002), "window": wl})
print(pd.DataFrame(det).to_string(index=False))

for rep, lab in ((repA, "A"), (repB, "B")):
    pr = (ret * rep)
    yearly = pd.DataFrame({
        "index": (1 + ret).groupby(ret.index.year).prod() - 1,
        lab: (1 + pr).groupby(pr.index.year).prod() - 1,
    }).loc[2009:]
    yearly["edge_pp"] = (yearly[lab] - yearly["index"]) * 100
    print(f"\n=== yearly, representative {lab} (%) ===")
    print((yearly * [100, 100, 1]).round(1).to_string())

# 2015/2024 crash behavior of repB
for pk, tr in (("2015-06-12", "2015-07-08"), ("2024-01-02", "2024-02-07")):
    seg = slice(pk, tr)
    idx_mv = (1 + ret.loc[seg]).prod() - 1
    b_mv = (1 + (ret * repB).loc[seg]).prod() - 1
    print(f"\ncrash {pk}->{tr}: index {idx_mv*100:.1f}% | repB {b_mv*100:.1f}% | days in mkt {repB.loc[seg].mean()*100:.0f}%")
