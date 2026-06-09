"""Wave-1A pilot — does report_rc consensus carry INCREMENTAL predictive value?

The audit-first gate (GPT cross-review verdict). Sandbox, IS 2014-2020 ONLY
(OOS 2021-2026 untouched). For each consensus feature, measures:
  * raw RankIC vs 20d forward return (covered universe only)
  * INCREMENTAL RankIC = RankIC of the residual after per-date cross-sectional
    OLS neutralization vs {log size, price momentum, short reversal, value (pb),
    turnover, owned net money-flow} + SW-L1 industry dummies.
A feature passes only if its incremental RankICIR is meaningfully above noise
(not explained by size/price/value/flow/industry).

Reuses canonical helpers: compute_factors (controls+fwd), factor_eval.neutralization,
factor_eval.ic_analysis (never reimplement IC), build_industry_series_asof.
"""
from __future__ import annotations
import json, sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
PROJECT_ROOT = HERE.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from report_rc_consensus import build_consensus_panel, load_report_rc, FEATURES  # noqa: E402
from alpha_research.factor_library.operators import compute_factors  # noqa: E402
from alpha_research.factor_eval.neutralization import neutralize  # noqa: E402
from alpha_research.factor_eval.ic_analysis import compute_ic_series, compute_ic_summary  # noqa: E402
from data_infra.provider_metadata import build_industry_series_asof  # noqa: E402

IS_START, IS_END = "2014-01-01", "2020-12-31"
FWD_H = 20
CONTROL_CATALOG = {
    "ctl_size": "$total_mv",
    "ctl_mom20": "Ref($close,1)/Ref($close,22)-1",
    "ctl_rev5": "Ref($close,1)/Ref($close,6)-1",
    "ctl_pb": "$pb",
    "ctl_turn20": "Mean(Ref($turnover_rate,1),20)",
    "ctl_flow20": "Mean(Ref($net_mf_amount,1),20)",
}


def to_qlib(ts_code):
    return ts_code.replace(".", "_")


def month_end_trading_days(y0, y1):
    cal = pd.read_parquet(PROJECT_ROOT / "data" / "reference" / "trade_cal.parquet")
    od = pd.to_datetime(cal.loc[cal["is_open"] == 1, "cal_date"], format="%Y%m%d")
    od = od[(od.dt.year >= y0) & (od.dt.year <= y1)]
    return sorted(od.groupby(od.dt.to_period("M")).max().tolist())


def main():
    asof = month_end_trading_days(2014, 2020)
    print(f"as-of month-ends: {len(asof)} ({asof[0].date()}..{asof[-1].date()})")

    # 1) consensus panel (covered universe), index -> (datetime, instrument[qlib])
    rc = load_report_rc(years=range(2010, 2021))
    panel = build_consensus_panel(asof, rc=rc)
    panel = panel.reset_index()
    panel["instrument"] = panel["ts_code"].map(to_qlib)
    panel = panel.set_index(["datetime", "instrument"]).sort_index()
    print(f"panel: {panel.shape[0]:,} rows, {panel.index.get_level_values(1).nunique()} stocks")

    # 2) controls + forward return via canonical compute_factors
    ctrl, fwd = compute_factors(CONTROL_CATALOG, IS_START, "2021-03-01",
                                horizons=[FWD_H], stage="is_only")
    fwd_col = f"fwd_{FWD_H}d"
    asof_set = set(pd.to_datetime(asof))
    ctrl = ctrl[ctrl.index.get_level_values(0).isin(asof_set)]
    fwd = fwd[fwd.index.get_level_values(0).isin(asof_set)]
    # align everything to the panel index
    idx = panel.index
    fwd_ret = fwd[fwd_col].reindex(idx)
    controls = {
        "log_size": np.log(ctrl["ctl_size"].reindex(idx).replace(0, np.nan)),
        "mom20": ctrl["ctl_mom20"].reindex(idx),
        "rev5": ctrl["ctl_rev5"].reindex(idx),
        "pb": ctrl["ctl_pb"].reindex(idx),
        "turn20": ctrl["ctl_turn20"].reindex(idx),
        "flow20": ctrl["ctl_flow20"].reindex(idx),
    }
    industry = build_industry_series_asof(idx, level="L1")
    print(f"fwd coverage on panel: {fwd_ret.notna().mean()*100:.0f}%  "
          f"industry coverage: {industry.notna().mean()*100:.0f}%")

    # 3) raw vs incremental RankIC per feature
    rows = []
    for feat in FEATURES:
        f = panel[feat].astype(float)
        raw = compute_ic_summary(compute_ic_series(f, fwd_ret, min_obs=50))
        resid = neutralize(f, controls=controls, industry=industry, min_obs=50)
        inc = compute_ic_summary(compute_ic_series(resid, fwd_ret, min_obs=50))
        rows.append({
            "feature": feat,
            "n_days": raw["n_days"],
            "raw_rank_ic": round(raw["mean_rank_ic"], 4),
            "raw_rank_icir": round(raw["rank_icir"], 3),
            "incr_rank_ic": round(inc["mean_rank_ic"], 4),
            "incr_rank_icir": round(inc["rank_icir"], 3),
            "incr_hit": round(inc["ic_hit_rate"], 3),
        })
        print(f"  {feat:16} raw RankIC {raw['mean_rank_ic']:+.4f} (ICIR {raw['rank_icir']:+.2f})"
              f"  ->  incr RankIC {inc['mean_rank_ic']:+.4f} (ICIR {inc['rank_icir']:+.2f})")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = PROJECT_ROOT / "workspace" / "outputs" / f"report_rc_pilot_{stamp}.json"
    out.write_text(json.dumps({"is_window": [IS_START, IS_END], "fwd_h": FWD_H,
                               "controls": list(CONTROL_CATALOG), "results": rows},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nwrote", out)
    return rows


if __name__ == "__main__":
    main()
