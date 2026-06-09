"""Wave-1A v2 pilot — incremental IC of the stronger analyst-alpha forms.

Same PIT-correct, covered-universe, neutralized harness as v1, but on the v2
features (diffusion / rec-change / target-implied) and at horizons 5/10/20
(revision alpha decays fast). IS 2014-2020 ONLY.
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
from report_rc_pilot import month_end_trading_days, to_qlib, CONTROL_CATALOG  # noqa: E402
from alpha_research.factor_library.operators import compute_factors  # noqa: E402
from alpha_research.factor_eval.neutralization import neutralize  # noqa: E402
from alpha_research.factor_eval.ic_analysis import compute_ic_series, compute_ic_summary  # noqa: E402
from data_infra.provider_metadata import build_industry_series_asof  # noqa: E402

HORIZONS = [5, 10, 20]
FEATURES = ["eps_diffusion", "rating_diffusion", "rec_up_net", "tp_implied_return"]


def main():
    asof = month_end_trading_days(2014, 2020)
    rc = load_report_rc(years=range(2010, 2021))
    panel = build_consensus_panel_v2(asof, rc=rc).reset_index()
    panel["instrument"] = panel["ts_code"].map(to_qlib)
    panel = panel.set_index(["datetime", "instrument"]).sort_index()

    cat = dict(CONTROL_CATALOG); cat["ctl_close"] = "$close"
    ctrl, fwd = compute_factors(cat, "2014-01-01", "2021-03-01", horizons=HORIZONS, stage="is_only")
    asof_set = set(pd.to_datetime(asof))
    ctrl = ctrl[ctrl.index.get_level_values(0).isin(asof_set)]
    fwd = fwd[fwd.index.get_level_values(0).isin(asof_set)]
    idx = panel.index

    # target-implied return = mean target price / close - 1 (sanitized)
    close = ctrl["ctl_close"].reindex(idx)
    tpi = panel["tp_consensus"] / close - 1.0
    panel["tp_implied_return"] = tpi.where((tpi > -0.8) & (tpi < 4.0))

    controls = {
        "log_size": np.log(ctrl["ctl_size"].reindex(idx).replace(0, np.nan)),
        "mom20": ctrl["ctl_mom20"].reindex(idx), "rev5": ctrl["ctl_rev5"].reindex(idx),
        "pb": ctrl["ctl_pb"].reindex(idx), "turn20": ctrl["ctl_turn20"].reindex(idx),
        "flow20": ctrl["ctl_flow20"].reindex(idx),
    }
    industry = build_industry_series_asof(idx, level="L1")
    fwds = {h: fwd[f"fwd_{h}d"].reindex(idx) for h in HORIZONS}

    rows = []
    for feat in FEATURES:
        f = panel[feat].astype(float)
        cov = f.notna().mean()
        resid = neutralize(f, controls=controls, industry=industry, min_obs=30)
        rec = {"feature": feat, "coverage_pct": round(cov * 100, 1)}
        line = f"  {feat:18} cov={cov*100:4.0f}%  "
        for h in HORIZONS:
            raw = compute_ic_summary(compute_ic_series(f, fwds[h], min_obs=30))
            inc = compute_ic_summary(compute_ic_series(resid, fwds[h], min_obs=30))
            rec[f"raw_ricir_{h}d"] = round(raw["rank_icir"], 3)
            rec[f"incr_ric_{h}d"] = round(inc["mean_rank_ic"], 4)
            rec[f"incr_ricir_{h}d"] = round(inc["rank_icir"], 3)
            rec[f"incr_hit_{h}d"] = round(inc["ic_hit_rate"], 3)
            rec[f"n_days_{h}d"] = inc["n_days"]
            line += f"| {h}d incrIC {inc['mean_rank_ic']:+.4f} ICIR {inc['rank_icir']:+.2f} "
        rows.append(rec)
        print(line)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = PROJECT_ROOT / "workspace" / "outputs" / f"report_rc_pilot_v2_{stamp}.json"
    out.write_text(json.dumps({"horizons": HORIZONS, "results": rows}, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print("\nwrote", out)


if __name__ == "__main__":
    main()
