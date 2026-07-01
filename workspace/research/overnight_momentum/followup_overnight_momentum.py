"""Follow-up on the overnight-momentum factor: honest (non-overlapping, cost-aware)
deployability color + size-neutralized RankIC. Uses the CACHED panel (no recompute).

Corrects the overlap-inflated long-short Sharpe from the first pass (daily-sampled
h-day forward returns annualized by sqrt(252)) by sampling NON-OVERLAPPING h-day
periods (Sharpe x sqrt(252/h)), and splits the gross Q10-Q1 paper spread from the
deployable long-only top-decile excess vs the equal-weight universe, net of a
25 bps-per-one-way-turnover cost. Also reports a size-neutralized RankIC (per-date
OLS residual on ln market cap) to confirm the signal is not a size bet.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(r"E:\量化系统")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.alpha_research.factor_eval.ic_analysis import compute_ic_series, compute_ic_summary
from src.alpha_research.factor_eval.quantile_analysis import (
    compute_quantile_returns, compute_long_short_returns,
)
from src.alpha_research.factor_eval.unified_eval import one_way_turnover

OUT = PROJECT_ROOT / "workspace" / "outputs" / "overnight_momentum"
START, END, WINDOW = "2016-01-01", "2026-02-27", 60
PRIMARY = "on_mom_excl60"
COST_BPS = 25.0   # one-way long-side round-trip ~ realistic_china (stamp+commission+slippage+transfer)

fac = pd.read_parquet(OUT / f"panel_factors_{START}_{END}_w{WINDOW}.parquet")
fwd = pd.read_parquet(OUT / f"panel_fwd_{START}_{END}.parquet")
for c in [PRIMARY, "size_ln"]:
    fac[c] = fac[c].replace([np.inf, -np.inf], np.nan)

f = fac[PRIMARY]
report = {}

# ── non-overlapping long-short + deployable long-only top decile ─────────────
for h in [5, 10, 20]:
    fh = fwd[f"fwd_{h}d"]
    qdf = compute_quantile_returns(f, fh, n_quantiles=10, min_obs=50)
    ls_daily = compute_long_short_returns(qdf).dropna()                 # Q10 - Q1, daily-sampled
    ls_no = ls_daily.iloc[::h]                                          # non-overlapping h-day periods
    ann = 252 / h
    ls_sharpe_no = float(ls_no.mean() / ls_no.std() * np.sqrt(ann)) if ls_no.std() > 0 else float("nan")

    # deployable long-only: top decile vs equal-weight universe mean, net of cost
    top10 = qdf[qdf["quantile"] == 10].set_index("date")["mean_return"]
    dec9 = qdf[qdf["quantile"] == 9].set_index("date")["mean_return"]
    univ_mean = fh[f.notna()].groupby(level=0).mean()                  # cross-sectional EW mean, same dates
    univ_mean.index = pd.to_datetime(univ_mean.index)
    top10.index = pd.to_datetime(top10.index); dec9.index = pd.to_datetime(dec9.index)
    exc = (top10 - univ_mean).dropna().iloc[::h]                       # non-overlapping excess
    exc9 = (dec9 - univ_mean).dropna().iloc[::h]
    turn = one_way_turnover(f, rebalance_days=h, top_q=0.1, trading_days=252, min_names=5)
    cost_per_period = turn["turnover_ann"] * (COST_BPS / 1e4) / ann    # per-rebalance cost
    net = exc - cost_per_period
    lo_sharpe_gross = float(exc.mean() / exc.std() * np.sqrt(ann)) if exc.std() > 0 else float("nan")
    lo_sharpe_net = float(net.mean() / net.std() * np.sqrt(ann)) if net.std() > 0 else float("nan")

    report[f"h{h}"] = {
        "ls_sharpe_nonoverlap_gross": round(ls_sharpe_no, 3),
        "ls_ann_return_gross": round(float(ls_no.mean() * ann), 4),
        "longonly_top10_excess_ann_gross": round(float(exc.mean() * ann), 4),
        "longonly_top10_excess_ann_net": round(float(net.mean() * ann), 4),
        "longonly_top10_sharpe_gross": round(lo_sharpe_gross, 3),
        "longonly_top10_sharpe_net": round(lo_sharpe_net, 3),
        "longonly_dec9_excess_ann_gross": round(float(exc9.mean() * ann), 4),
        "turnover_ann": round(float(turn["turnover_ann"]), 2),
        "annual_cost_drag": round(float(turn["turnover_ann"] * COST_BPS / 1e4), 4),
        "n_periods": int(len(exc)),
    }

# ── size-neutralized RankIC (per-date OLS residual on ln_mcap) ───────────────
def _size_resid(factor: pd.Series, size: pd.Series) -> pd.Series:
    df = pd.DataFrame({"f": factor, "s": size}).dropna()
    def _r(g):
        if len(g) < 10:
            return pd.Series(np.nan, index=g.index)
        x = g["s"].to_numpy(); y = g["f"].to_numpy()
        b = np.polyfit(x, y, 1)
        return pd.Series(y - (b[0] * x + b[1]), index=g.index)
    return df.groupby(level=0, group_keys=False).apply(_r)

resid = _size_resid(f, fac["size_ln"])
neut = {}
for h in [10, 20]:
    ic = compute_ic_series(resid, fwd[f"fwd_{h}d"], min_obs=30)
    s = compute_ic_summary(ic)
    neut[f"h{h}"] = {"neutralized_mean_rank_ic": round(float(s["mean_rank_ic"]), 4),
                     "neutralized_rank_icir": round(float(s["rank_icir"]), 4)}
report["size_neutralized_rankic"] = neut

(OUT / "overnight_momentum_followup.json").write_text(
    json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

print("\n" + "=" * 78)
print("OVERNIGHT MOMENTUM — non-overlapping / cost-aware follow-up")
print("=" * 78)
print(f"{'horizon':<8}{'LS Sharpe':>11}{'LS ann':>9}{'LO top10 net':>14}{'LO Sharpe net':>15}{'turnover':>10}")
for h in [5, 10, 20]:
    r = report[f"h{h}"]
    print(f"h{h:<7}{r['ls_sharpe_nonoverlap_gross']:>11.2f}{r['ls_ann_return_gross']:>9.1%}"
          f"{r['longonly_top10_excess_ann_net']:>14.1%}{r['longonly_top10_sharpe_net']:>15.2f}"
          f"{r['turnover_ann']:>9.1f}x")
print("\n(LS = Q10-Q1 gross paper spread, non-overlapping; LO top10 = deployable "
      "long-only\n top-decile excess vs equal-weight universe, net of "
      f"{COST_BPS:.0f}bps/one-way-turnover)")
print(f"\nsize-neutralized RankIC: h10={neut['h10']['neutralized_mean_rank_ic']:+.4f} "
      f"(ICIR {neut['h10']['neutralized_rank_icir']:+.2f}), "
      f"h20={neut['h20']['neutralized_mean_rank_ic']:+.4f} "
      f"(ICIR {neut['h20']['neutralized_rank_icir']:+.2f})")
print("=" * 78)
