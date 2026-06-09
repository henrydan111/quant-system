"""Wave-1A tradability gate for eps_diffusion (does strong IC convert to a tradable spread?).

The project's recurring lesson: cross-sectional IC != long-only return. Before paying the
ingestion toll, this checks — IS 2014-2020, covered universe, monthly 20d holding — whether
eps_diffusion's IC converts to a monotonic quantile ladder + a tradable top-quintile / LS
spread net of turnover cost, and how the IC decays with horizon.

Canonical helpers only (factor_eval): compute_quantile_returns/summary, compute_long_short_returns,
test_monotonicity, compute_ic_decay-style horizon sweep, annualized_turnover, cost_adjusted_sharpe.
"""
from __future__ import annotations
import json, sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
PROJECT_ROOT = HERE.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT)); sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(HERE.parent))

from report_rc_consensus import load_report_rc  # noqa: E402
from report_rc_consensus_v2 import build_consensus_panel_v2  # noqa: E402
from report_rc_pilot import month_end_trading_days, to_qlib  # noqa: E402
from alpha_research.factor_library.operators import compute_factors  # noqa: E402
from alpha_research.factor_eval.quantile_analysis import (  # noqa: E402
    compute_quantile_returns, compute_quantile_summary, compute_long_short_returns, test_monotonicity)
from alpha_research.factor_eval.ic_analysis import compute_ic_series, compute_ic_summary  # noqa: E402
from alpha_research.factor_eval.cost_aware_eval import annualized_turnover, cost_adjusted_sharpe  # noqa: E402

NQ = 5
DECAY_H = [10, 20, 40, 60]
PRIMARY_H = 20
MONTHS_PER_YEAR = 12
COST_BPS = 30  # round-trip cost per unit two-way turnover (bps) — conservative A-share


def ann_stats(monthly: pd.Series):
    m = monthly.dropna()
    mu, sd = m.mean(), m.std()
    return {"ann_return": round(mu * MONTHS_PER_YEAR, 4),
            "ann_sharpe": round(mu / sd * np.sqrt(MONTHS_PER_YEAR), 2) if sd > 0 else 0.0,
            "n": len(m)}


def main():
    asof = month_end_trading_days(2014, 2020)
    rc = load_report_rc(years=range(2010, 2021))
    panel = build_consensus_panel_v2(asof, rc=rc).reset_index()
    panel["instrument"] = panel["ts_code"].map(to_qlib)
    panel = panel.set_index(["datetime", "instrument"]).sort_index()
    feat = panel["eps_diffusion"].astype(float)

    _, fwd = compute_factors({"px": "$close"}, "2014-01-01", "2021-06-01",
                             horizons=DECAY_H, stage="is_only")
    asof_set = set(pd.to_datetime(asof))
    fwd = fwd[fwd.index.get_level_values(0).isin(asof_set)]
    fwd_primary = fwd[f"fwd_{PRIMARY_H}d"].reindex(feat.index)

    # eps_diffusion is DISCRETE with a large point-mass at 0 (many stocks have no /
    # balanced revisions) -> a 5-quantile qcut collapses. The rank IC (Spearman) handles
    # ties correctly; the economically-clean, tie-tolerant PORTFOLIO is a SIGN split:
    # long upward-revised (diffusion>0), short downward-revised (diffusion<0), vs the
    # covered-universe equal-weight mean.
    df = pd.DataFrame({"f": feat, "fwd": fwd_primary}).dropna()

    def _sign(g):
        lo, sh = g.loc[g["f"] > 0, "fwd"], g.loc[g["f"] < 0, "fwd"]
        return pd.Series({"long": lo.mean(), "short": sh.mean(), "uni": g["fwd"].mean(),
                          "n_long": len(lo), "n_short": len(sh)})

    by = df.groupby(level=0).apply(_sign)
    top_excess = (by["long"] - by["uni"]).dropna()       # long-only deployable leg
    ls = (by["long"] - by["short"]).dropna()
    avg_long, avg_short = round(by["n_long"].mean()), round(by["n_short"].mean())

    # turnover of the long set (diffusion>0) one-way + net LS sharpe
    members, one_way = {}, {}
    for d, g in df.groupby(level=0):
        members[d] = set(g.loc[g["f"] > 0].index.get_level_values(1))
    keys = sorted(members)
    for a, b in zip(keys[:-1], keys[1:]):
        prev, cur = members[a], members[b]
        if cur:
            one_way[b] = len(cur - prev) / len(cur)
    ann_to = annualized_turnover(pd.Series(list(one_way.values())), trading_days=MONTHS_PER_YEAR)
    two_way = pd.Series({k: 2 * v for k, v in one_way.items()})
    net_ls_sharpe = cost_adjusted_sharpe(ls, two_way.reindex(ls.index).fillna(0),
                                         cost_bps_per_unit_turnover=COST_BPS,
                                         trading_days=MONTHS_PER_YEAR)

    # 4) IC decay
    decay = {}
    for h in DECAY_H:
        s = compute_ic_summary(compute_ic_series(feat, fwd[f"fwd_{h}d"].reindex(feat.index), min_obs=30))
        decay[f"{h}d"] = {"rank_ic": round(s["mean_rank_ic"], 4), "rank_icir": round(s["rank_icir"], 3)}

    res = {
        "n_months": len(asof), "cost_bps": COST_BPS,
        "construction": "sign split: long diffusion>0, short diffusion<0, vs covered-universe mean",
        "avg_n_long": avg_long, "avg_n_short": avg_short,
        "long_excess_vs_universe": ann_stats(top_excess),
        "long_short": ann_stats(ls),
        "annualized_turnover": round(ann_to, 2),
        "net_ls_sharpe_after_cost": round(net_ls_sharpe, 2),
        "ic_decay": decay,
    }
    print("\n==== eps_diffusion TRADABILITY (IS 2014-2020, monthly 20d hold, covered universe) ====")
    print(f"construction: sign split (avg {avg_long} long / {avg_short} short names per month)")
    print(f"LONG-ONLY leg (diffusion>0 EXCESS vs universe): {res['long_excess_vs_universe']}")
    print(f"long-short (long>0 minus short<0):              {res['long_short']}")
    print(f"annualized turnover: {res['annualized_turnover']}  net LS Sharpe @ {COST_BPS}bps: {res['net_ls_sharpe_after_cost']}")
    print(f"IC decay: {decay}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = PROJECT_ROOT / "workspace" / "outputs" / f"report_rc_tradability_{stamp}.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2,
                              default=lambda o: o.item() if hasattr(o, "item") else float(o)),
                   encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()
