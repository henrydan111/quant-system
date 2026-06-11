# SCRIPT_STATUS: ACTIVE — Phase C anchor calibration (CICC truth comparison)
"""Phase C: anchor-factor calibration against the CICC handbook truth tables.

Runs 9 anchor factors through the EXACT CICC protocol (cicc_protocol.py) on
univ_all / univ_csi300 / univ_csi500 over the handbook window (2010.01–2022.07),
then prints a cell-by-cell comparison against the verified truth values
(Knowledge/AI量化增强/CICC_因子表现真值.md). Purpose: ONE global dark-knob
configuration must put every anchor inside tolerance — that certifies our PIT
data + factor construction + evaluation pipeline against an independent
external yardstick. Descriptive/sandbox only: no registry writes, no seals.

Anchors and the data path each one certifies:
    ln_mc          log(total_mv)                       valuation/size (daily_basic)
    ep_ttm         NI_TTM / total_mv                   income PIT TTM + mcap units
    dp             dv_ttm (0-filled non-payers)        dividend path
    roa_ttm        NI_TTM / total_assets               income TTM + balancesheet
    cfoa           OCF_TTM / total_assets              cashflow PIT TTM
    gpmd           GPM_TTM(q0..q3) − GPM_TTM(q1..q4)   margin delta (quarter slots)
    np_q_yoy       (NIattr_q0 − NIattr_q4)/|NIattr_q4| single-quarter derivation
    mmt_normal_m   past-20d adjusted return            adjusted price path
    mmt_range_m    20d top20%-amp − bottom20%-amp ret  OHLC amplitude path

Construction caveats (recorded, may eat tolerance):
    - roa_ttm/cfoa/ep_ttm use n_income (incl. minority) for TTM because attr_p
      single-quarter slots exist only at q0/q4; CICC likely uses 归母. np_q_yoy
      uses attr_p (q0/q4 suffice there).
    - dp uses the vendor dv_ttm (%); non-payers filled 0 per CICC pool semantics.
    - gpmd uses total_revenue (营业总收入) — oper_cost slots pair with it.

Usage:
    venv/Scripts/python.exe workspace/scripts/cicc_anchor_calibration.py [--quick]
    --quick: 2015-2018 subwindow smoke (fast pipeline shakeout, no truth verdicts)
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from src.alpha_research.factor_library import operators as op  # noqa: E402
from src.alpha_research.factor_eval.cicc_protocol import (  # noqa: E402
    CiccProtocolConfig, evaluate_cicc_protocol, month_end_schedule,
)
from src.alpha_research.factor_eval import universes as uv  # noqa: E402
from src.data_infra import universe_membership as um  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("cicc_anchor")

QLIB_DIR = PROJECT_ROOT / "data" / "qlib_data"
OUT_DIR = PROJECT_ROOT / "workspace" / "outputs" / "cicc_anchor_calibration"

# CICC handbook window (价量手册口径; 基本面手册标注约2010-2022)
WINDOW_START, WINDOW_END = "2010-01-04", "2022-07-01"
WARMUP_START = "2008-06-01"  # TTM quarter slots + 20d momentum warmup

NI_TTM = "($n_income_sq_q0 + $n_income_sq_q1 + $n_income_sq_q2 + $n_income_sq_q3)"
OCF_TTM = "($n_cashflow_act_sq_q0 + $n_cashflow_act_sq_q1 + $n_cashflow_act_sq_q2 + $n_cashflow_act_sq_q3)"
REV_TTM0 = "($total_revenue_sq_q0 + $total_revenue_sq_q1 + $total_revenue_sq_q2 + $total_revenue_sq_q3)"
REV_TTM1 = "($total_revenue_sq_q1 + $total_revenue_sq_q2 + $total_revenue_sq_q3 + $total_revenue_sq_q4)"
COST_TTM0 = "($oper_cost_sq_q0 + $oper_cost_sq_q1 + $oper_cost_sq_q2 + $oper_cost_sq_q3)"
COST_TTM1 = "($oper_cost_sq_q1 + $oper_cost_sq_q2 + $oper_cost_sq_q3 + $oper_cost_sq_q4)"

# total_mv is 万元; statement fields are 元 -> scale 1e4.
ANCHOR_EXPRS = {
    "ln_mc": "Log($total_mv)",
    "ep_ttm": f"{NI_TTM} / ($total_mv * 10000)",
    "dp": "$dv_ttm",
    "roa_ttm": f"{NI_TTM} / $total_assets_q0",
    "cfoa": f"{OCF_TTM} / $total_assets_q0",
    "gpmd": f"(1 - {COST_TTM0}/{REV_TTM0}) - (1 - {COST_TTM1}/{REV_TTM1})",
    "np_q_yoy": "($n_income_attr_p_sq_q0 - $n_income_attr_p_sq_q4) / Abs($n_income_attr_p_sq_q4)",
    "mmt_normal_m": "$close*$adj_factor / Ref($close*$adj_factor, 20) - 1",
    # mmt_range_m is computed in pandas at rebalance dates (conditional rolling sums)
}
RAW_FIELDS = {
    "close_raw": "$close", "adj": "$adj_factor", "high": "$high", "low": "$low",
    "vol": "$vol", "up_limit": "$up_limit", "down_limit": "$down_limit",
    "total_mv": "$total_mv",
}

UNIVERSES = ("univ_all", "univ_csi300", "univ_csi500")
BENCH_BY_UNIVERSE = {"univ_all": None, "univ_csi300": "000300_SH", "univ_csi500": "000905_SH"}

# verified truth cells: (IC均值%, IC_IR, t, 多头年化%, 多头超额%, 单调性); None = not in table
TRUTH = {
    ("roa_ttm", "univ_all"): (2.56, 0.31, 3.72, 9.36, -0.13, 0.85),
    ("roa_ttm", "univ_csi300"): (3.20, 0.23, 2.79, 6.07, 5.43, 0.77),
    ("roa_ttm", "univ_csi500"): (3.32, 0.33, 3.95, 8.66, 4.73, 0.81),
    ("cfoa", "univ_all"): (2.21, 0.48, 5.79, 12.04, 2.24, 0.93),
    ("cfoa", "univ_csi300"): (2.57, 0.24, 2.95, 6.30, 5.90, 0.76),
    ("cfoa", "univ_csi500"): (2.92, 0.41, 4.99, 8.49, 4.67, 0.89),
    ("np_q_yoy", "univ_all"): (3.51, 0.60, 7.30, 14.67, 5.21, 0.95),
    ("np_q_yoy", "univ_csi300"): (3.79, 0.38, 4.57, 7.82, 8.08, 0.93),
    ("np_q_yoy", "univ_csi500"): (4.22, 0.51, 6.14, 10.64, 7.28, 0.83),
    ("gpmd", "univ_all"): (2.23, 0.63, 7.61, 11.83, 2.51, 0.94),
    ("gpmd", "univ_csi300"): (2.34, 0.27, 3.30, 6.03, 6.09, 0.83),
    ("gpmd", "univ_csi500"): (2.60, 0.40, 4.88, 8.76, 5.45, 0.95),
    ("ep_ttm", "univ_all"): (4.53, 0.56, 6.76, 10.90, 0.78, 0.92),
    ("ep_ttm", "univ_csi300"): (4.18, 0.27, 3.31, 4.71, 4.25, 0.75),
    ("ep_ttm", "univ_csi500"): (4.91, 0.47, 5.73, 10.03, 6.12, 0.95),
    ("dp", "univ_all"): (3.80, 0.60, 7.32, 12.95, 2.90, 0.89),
    ("dp", "univ_csi300"): (3.82, 0.29, 3.51, 5.69, 5.66, 0.78),
    ("dp", "univ_csi500"): (4.04, 0.45, 5.45, 8.92, 5.49, 0.93),
    ("ln_mc", "univ_all"): (-2.82, -0.56, -6.84, 11.11, 1.47, -0.93),
    ("ln_mc", "univ_csi300"): (1.15, None, 0.85, 4.49, 3.83, 0.67),
    ("ln_mc", "univ_csi500"): (0.96, None, 1.13, 3.60, 0.41, 0.26),
    ("mmt_normal_m", "univ_all"): (-6.2, -0.63, -7.77, 12.5, 3.8, 0.81),
    ("mmt_normal_m", "univ_csi300"): (-3.8, -0.30, -3.62, 7.3, 7.1, 0.89),
    ("mmt_normal_m", "univ_csi500"): (-4.4, -0.37, -4.56, 6.6, 3.5, 0.85),
    ("mmt_range_m", "univ_all"): (-6.8, -1.03, -12.60, 13.7, 4.8, 0.90),
    ("mmt_range_m", "univ_csi300"): (-3.9, -0.40, -4.90, 7.3, 7.1, 0.80),
    ("mmt_range_m", "univ_csi500"): (-5.2, -0.64, -7.89, 9.4, 6.2, 0.90),
}
# main-judgment tolerances (per the frozen Phase-C protocol)
TOL_IC, TOL_MONO, TOL_LONG_ANN = 0.5, 0.15, 2.0  # pp / abs / pp


def _wide(panel: pd.DataFrame, col: str) -> pd.DataFrame:
    s = panel[col]
    w = s.unstack(level=0) if s.index.names[0] in ("instrument", None) else s.unstack(level=1)
    w.index = pd.DatetimeIndex(w.index)
    return w.sort_index()


def load_panels(start: str, end: str) -> dict[str, pd.DataFrame]:
    catalog = {**ANCHOR_EXPRS, **RAW_FIELDS}
    t0 = time.time()
    log.info("compute_factors: %d expressions %s..%s (full market)", len(catalog), start, end)
    panel, _ = op.compute_factors(catalog=catalog, start_date=start, end_date=end,
                                  horizons=None, qlib_dir=str(QLIB_DIR), kernels=1,
                                  stage="is_only")
    log.info("loaded %d rows in %.0fs", len(panel), time.time() - t0)
    # MultiIndex order: D.features returns (instrument, datetime) — _wide handles both
    wides = {name: _wide(panel, name) for name in catalog}
    return wides


def compute_mmt_range_m(high, low, close_adj, schedule, top_frac=0.2, lookback=20) -> pd.DataFrame:
    """振幅调整动量: within the past `lookback` trading days, sum of daily close
    returns on the top-20%-amplitude days minus the bottom-20% days. Computed at
    rebalance dates only (the protocol samples month-ends)."""
    amp = high / low - 1.0
    ret = close_adj / close_adj.shift(1) - 1.0
    k = max(1, int(round(lookback * top_frac)))
    out = pd.DataFrame(np.nan, index=schedule, columns=close_adj.columns)
    pos = close_adj.index.get_indexer(schedule)
    for j, (t, i) in enumerate(zip(schedule, pos)):
        if i < lookback:
            continue
        a = amp.iloc[i - lookback + 1: i + 1]
        r = ret.iloc[i - lookback + 1: i + 1]
        arank = a.rank(axis=0, method="first")
        n_valid = a.notna().sum(axis=0)
        hi = (arank > (n_valid - k)).where(a.notna(), False)
        lo = (arank <= k).where(a.notna(), False)
        val = (r.where(hi).sum(axis=0, min_count=1) - r.where(lo).sum(axis=0, min_count=1))
        val[n_valid < lookback // 2] = np.nan
        out.loc[t] = val
    return out


def load_benchmark_monthly(schedule: pd.DatetimeIndex) -> dict[str, pd.Series]:
    import qlib
    from qlib.data import D
    qlib.init(provider_uri=str(QLIB_DIR), region="cn")
    out = {}
    for code in ("000300_SH", "000905_SH"):
        df = D.features([code], ["$close"], start_time=str(schedule.min().date()),
                        end_time=str(schedule.max().date()))
        close = df["$close"].xs(code, level=df.index.names[0]) if df.index.nlevels > 1 else df["$close"]
        close.index = pd.DatetimeIndex(close.index)
        c = close.reindex(schedule).ffill()
        out[code] = (c.shift(-1) / c - 1.0).iloc[:-1]  # entry-date indexed period return
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="2015-2018 smoke run")
    args = ap.parse_args()

    w_start, w_end = ("2015-01-05", "2018-12-28") if args.quick else (WINDOW_START, WINDOW_END)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    wides = load_panels(WARMUP_START, w_end)
    dates_all = wides["close_raw"].index
    insts = list(wides["close_raw"].columns)

    close_adj = wides["close_raw"] * wides["adj"]
    schedule = month_end_schedule(dates_all, start=w_start, end=w_end)
    log.info("schedule: %d month-ends %s..%s; %d instruments",
             len(schedule), schedule.min().date(), schedule.max().date(), len(insts))

    wides["mmt_range_m"] = compute_mmt_range_m(wides["high"], wides["low"], close_adj, schedule)
    wides["dp"] = wides["dp"].fillna(0.0)  # CICC pool semantics: non-payers DP=0

    # reference + universe masks (panel only needs the screen columns at schedule dates,
    # but masks are daily by design)
    eval_dates = dates_all[(dates_all >= schedule.min()) & (dates_all <= schedule.max())]
    panel_for_masks = {
        "vol": wides["vol"], "close": wides["close_raw"], "high": wides["high"],
        "low": wides["low"], "up_limit": wides["up_limit"], "down_limit": wides["down_limit"],
    }
    listing = um.listing_status_masks(eval_dates, insts)
    reference = {"st": um.st_mask(eval_dates, insts),
                 "young": listing["young"], "listed": listing["listed"]}
    masks = {}
    for uid in UNIVERSES:
        t0 = time.time()
        masks[uid] = uv.build_universe_mask(uid, eval_dates, insts,
                                            panel_for_masks, reference=reference)
        cnt = masks[uid].loc[schedule[len(schedule) // 2]].sum()
        log.info("%s built in %.0fs (mid-window count %d)", uid, time.time() - t0, cnt)

    bench = load_benchmark_monthly(schedule)
    factors = list(ANCHOR_EXPRS) + ["mmt_range_m"]
    results, verdicts = {}, []
    for uid in UNIVERSES:
        bench_code = BENCH_BY_UNIVERSE[uid]
        bench_m = bench.get(bench_code) if bench_code else None
        for fid in factors:
            try:
                res = evaluate_cicc_protocol(
                    wides[fid], close_adj, masks[uid], schedule=schedule,
                    benchmark_monthly=bench_m, config=CiccProtocolConfig())
            except ValueError as e:
                log.warning("%s × %s: %s", fid, uid, e)
                continue
            results[(fid, uid)] = res
            truth = TRUTH.get((fid, uid))
            row = {"factor": fid, "universe": uid, **res.to_row(),
                   "group_ann": res.group_ann, "group_mean_count": res.group_mean_count}
            if truth and not args.quick:
                t_ic, t_ir, t_t, t_long, t_exc, t_mono = truth
                d_ic = res.ic_mean * 100 - t_ic
                d_mono = (res.monotonicity - t_mono) if t_mono is not None else None
                d_long = res.long_ann * 100 - t_long
                ok_ic = abs(d_ic) <= TOL_IC
                ok_mono = d_mono is not None and abs(d_mono) <= TOL_MONO and \
                    (res.monotonicity * t_mono > 0 if t_mono else True)
                ok_long = abs(d_long) <= TOL_LONG_ANN
                row.update({"truth_ic": t_ic, "d_ic_pp": round(d_ic, 2), "ok_ic": ok_ic,
                            "truth_mono": t_mono, "d_mono": None if d_mono is None else round(d_mono, 2),
                            "ok_mono": ok_mono, "truth_long_ann": t_long,
                            "d_long_pp": round(d_long, 2), "ok_long": ok_long,
                            "PASS": ok_ic and ok_mono and ok_long})
            verdicts.append(row)
            log.info("%s × %s: IC %.2f%% (truth %s) IR %.2f t %.2f long %.1f%% mono %.2f",
                     fid, uid, res.ic_mean * 100,
                     truth[0] if truth else "—", res.ic_ir, res.ic_t,
                     res.long_ann * 100, res.monotonicity)

    out_file = OUT_DIR / ("verdicts_quick.json" if args.quick else "verdicts.json")
    out_file.write_text(json.dumps(verdicts, ensure_ascii=False, indent=1, default=str),
                        encoding="utf-8")
    log.info("wrote %s", out_file)

    if not args.quick:
        scored = [v for v in verdicts if "PASS" in v]
        n_pass = sum(1 for v in scored if v["PASS"])
        log.info("=== CALIBRATION VERDICT: %d/%d anchor×universe cells PASS ===",
                 n_pass, len(scored))
        for v in scored:
            if not v["PASS"]:
                log.info("  FAIL %s×%s: dIC %+0.2fpp dMono %s dLong %+0.1fpp",
                         v["factor"], v["universe"], v["d_ic_pp"], v["d_mono"], v["d_long_pp"])
        return 0 if n_pass == len(scored) else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
