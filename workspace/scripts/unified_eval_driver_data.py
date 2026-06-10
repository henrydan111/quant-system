"""P1b-data — the two data-plumbing-heavy columns deferred from the P1b driver, on the 7 factors:
  - neutralized RankIC / ICIR (size $total_mv + PIT SW2021 industry)
  - long-leg-excess-vs-benchmark IR proxy vs BOTH CSI300 (000300_SH) and CSI500 (000905_SH)
    (benchmark policy = show both, no per-factor selection → no snooping).
Reuses the cached factor panel from unified_eval_driver.py (no recompute). Read-only; IS-only.
"""
from __future__ import annotations

import json
import logging
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
np.seterr(all="ignore")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.alpha_research.factor_eval import ic_analysis as ica
from src.alpha_research.factor_eval.unified_eval import (
    index_forward_returns,
    long_leg_excess_ir,
    neutralized_rank_icir,
    resolve_orientation,
)
from src.alpha_research.factor_lifecycle.walk_forward_validation import build_is_windowed_panel
from src.data_infra import provider_metadata as pm

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("unified_eval_driver_data")

IS_START, IS_END, HORIZON = "2014-01-01", "2020-12-31", 20
QLIB_DIR = PROJECT_ROOT / "data" / "qlib_data"
OUTDIR = PROJECT_ROOT / "workspace" / "outputs"
PANEL_CACHE = OUTDIR / "unified_eval_driver_panel.parquet"
MCAP_CACHE = OUTDIR / "unified_eval_mcap.parquet"
OUT = OUTDIR / "unified_eval_driver_data.json"
ADJ_COL = "__adj_close__"
BENCHMARKS = {"CSI300": "000300_SH", "CSI500": "000905_SH"}
PICKS = ["earn_eps_diffusion_60", "liq_zero_ret_days_10d", "qual_piotroski_fscore_9pt",
         "liq_vol_cv_20d", "qual_gross_profitability", "rev_up_down_ratio_20d", "qual_q_gross_margin"]


def _to_dt_inst(s):
    return (s.swaplevel(0, 1) if s.index.names[0] != "datetime" else s).sort_index()


def _load_mcap(instruments) -> pd.Series:
    if MCAP_CACHE.exists():
        log.info("Loading cached mcap %s ...", MCAP_CACHE)
        return pd.read_parquet(MCAP_CACHE)["mcap"]
    import qlib
    from qlib.data import D
    qlib.init(provider_uri=str(QLIB_DIR), region="cn")
    t0 = time.time()
    log.info("Loading $total_mv for %d instruments ...", len(instruments))
    df = D.features(list(instruments), ["$total_mv"], start_time=IS_START, end_time=IS_END)
    mcap = df["$total_mv"].rename("mcap")
    log.info("mcap loaded in %.0fs: %d rows", time.time() - t0, len(mcap.dropna()))
    mcap.to_frame().to_parquet(MCAP_CACHE)
    return mcap


def _bench_fwd_returns() -> dict:
    import qlib
    from qlib.data import D
    qlib.init(provider_uri=str(QLIB_DIR), region="cn")
    out = {}
    for name, code in BENCHMARKS.items():
        df = D.features([code], ["$close"], start_time=IS_START, end_time=IS_END)
        close = df["$close"].xs(code, level=df.index.names[0]) if df.index.nlevels > 1 else df["$close"]
        close.index = pd.DatetimeIndex([pd.Timestamp(d) for d in close.index])
        out[name] = index_forward_returns(close, horizon=HORIZON)
        log.info("%s (%s) fwd returns: %d dates", name, code, len(out[name]))
    return out


def main() -> int:
    if not PANEL_CACHE.exists():
        log.error("panel cache missing — run unified_eval_driver.py first")
        return 1
    raw = pd.read_parquet(PANEL_CACHE)
    factor_panel = raw[[c for c in raw.columns if c != ADJ_COL]]
    windowed = build_is_windowed_panel(factor_panel, raw[ADJ_COL], is_end=IS_END, horizon=HORIZON)
    label = _to_dt_inst(windowed.label)
    instruments = factor_panel.index.get_level_values("instrument").unique()

    mcap = _load_mcap(instruments)
    log.info("Building PIT SW2021 industry labels for the panel index ...")
    industry = pm.build_industry_series_asof(factor_panel.index, level="L1")
    benches = _bench_fwd_returns()

    all_dates = sorted(label.index.get_level_values("datetime").unique())
    orient_train = set(all_dates[: int(len(all_dates) * 0.6)])

    report = []
    for fid in PICKS:
        f = raw[fid]
        neut = neutralized_rank_icir(f, label, mcap, industry, min_obs=30, hac_lags=40)
        # orient (non-circular early-window) for the long-leg
        rank_ic = ica.compute_ic_series(_to_dt_inst(f), label, min_obs=30)["RankIC"].dropna()
        orient = resolve_orientation(rank_ic.rename(None), train_dates=orient_train, min_train_t=1.0)
        of = _to_dt_inst(f) * orient["sign"]
        legs = {}
        for name, bench in benches.items():
            try:
                r = long_leg_excess_ir(of, label, bench, top_q=0.2, cost_bps_per_turnover=25.0,
                                       rebalance_days=HORIZON, horizon=HORIZON)
                legs[name] = {"excess_ann": r["long_leg_excess_ann"],
                              "ir_proxy_is": r["long_leg_excess_ir_proxy_is"], "n": r["n_rebalances"]}
            except Exception as e:  # noqa: BLE001
                legs[name] = {"error": str(e)}
        report.append({
            "factor": fid,
            "neutralized_rank_icir": neut["neutralized_rank_icir"],
            "neutralized_mean_rank_ic": neut["neutralized_mean_rank_ic"],
            "neutralized_hac_t": neut["neutralized_hac_t"],
            "orientation_valid": orient["orientation_valid"],
            "long_leg_excess": legs,
        })
        log.info("done %s", fid)

    OUT.write_text(json.dumps({"factors": report,
                               "benchmark_policy": "show_both_no_selection",
                               "benchmarks": BENCHMARKS}, indent=2, default=lambda x: None),
                   encoding="utf-8")
    log.info("=== P1b-data (neutralized IC + long-leg-excess vs both benchmarks) ===")
    log.info("%-28s %12s %8s | %-22s %-22s", "factor", "neutICIR", "neutHACt", "CSI300 exc/IR", "CSI500 exc/IR")
    for r in report:
        def p(x, n=3):
            return f"{x:.{n}f}" if isinstance(x, (int, float)) else "NA"
        c3, c5 = r["long_leg_excess"].get("CSI300", {}), r["long_leg_excess"].get("CSI500", {})
        log.info("%-28s %12s %8s | %-22s %-22s", r["factor"], p(r["neutralized_rank_icir"]),
                 p(r["neutralized_hac_t"], 2),
                 f"{p(c3.get('excess_ann'))}/{p(c3.get('ir_proxy_is'),2)}",
                 f"{p(c5.get('excess_ann'))}/{p(c5.get('ir_proxy_is'),2)}")
    log.info("wrote %s", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
