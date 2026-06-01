"""Phase 6 dry-run diagnostic: WHY did build_is_windowed_panel produce an empty label?

Reproduces ONLY the label-realization mapping + reindex (the cheap 12s adj_close compute),
NOT the 29-min 114-factor panel. Reports whether `fut = adj.reindex(future_index)` matches
anything and pinpoints any datetime-representation mismatch between trade_cal open-days and
the Qlib panel datetime index. Read-only; no writes anywhere.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.alpha_research.factor_library import operators
from src.alpha_research.factor_lifecycle.walk_forward_validation import load_open_trading_days

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("phase6_diag")

IS_START, IS_END = "2014-01-01", "2020-12-31"
HORIZON = 20
QLIB_DIR = str(PROJECT_ROOT / "data" / "qlib_data")
ADJ_EXPR = getattr(operators, "ADJ_CLOSE", "$close * $adj_factor")


def main() -> int:
    log.info("Computing adj_close over [%s, %s] (cheap ~12s) ...", IS_START, IS_END)
    adj_panel, _ = operators.compute_factors(
        catalog={"adj_close": ADJ_EXPR}, start_date=IS_START, end_date=IS_END,
        horizons=None, qlib_dir=QLIB_DIR, kernels=1, stage="is_only",
    )
    adj = adj_panel["adj_close"].sort_index()
    log.info("adj index names=%s  nrows=%d", list(adj.index.names), len(adj))

    panel_dts = adj.index.get_level_values("datetime")
    panel_dates = pd.DatetimeIndex(sorted(panel_dts.unique()))
    open_days = load_open_trading_days(None)

    log.info("panel datetime dtype=%s  open_days dtype=%s", panel_dts.dtype, open_days.dtype)
    log.info("panel n_dates=%d  [%s .. %s]", len(panel_dates),
             panel_dates.min().date(), panel_dates.max().date())
    log.info("open_days n=%d  [%s .. %s]", len(open_days),
             open_days.min().date(), open_days.max().date())

    # CORE CHECK 1: are panel dates a subset of open_days?
    in_cal = panel_dates.isin(open_days)
    log.info("panel dates IN open_days: %d / %d (%.1f%%)",
             int(in_cal.sum()), len(panel_dates), 100.0 * in_cal.mean())
    if not in_cal.all():
        missing = panel_dates[~in_cal][:10]
        log.warning("panel dates NOT in open_days (sample): %s", [d for d in missing])
        # show nearest open_days around the first missing one
        m0 = panel_dates[~in_cal][0]
        near = open_days[(open_days >= m0 - pd.Timedelta(days=5)) & (open_days <= m0 + pd.Timedelta(days=5))]
        log.warning("open_days near %s: %s", m0.date(), [d for d in near])
        log.warning("repr panel_date[0]=%r   repr open_day_sample=%r", panel_dates[0], open_days[0])

    # CORE CHECK 2: reproduce the exact realization mapping + reindex
    pos = open_days.searchsorted(panel_dates, side="left")
    target = pos + HORIZON
    real_map = {fd: (open_days[t] if t < len(open_days) else pd.NaT)
                for fd, t in zip(panel_dates, target)}
    dts = adj.index.get_level_values("datetime")
    insts = adj.index.get_level_values("instrument")
    r_for_rows = pd.DatetimeIndex([real_map.get(d, pd.NaT) for d in dts])
    n_nat = int(pd.isna(r_for_rows).sum())
    log.info("r(t) NaT rows (factor dates within %d of calendar end): %d / %d",
             HORIZON, n_nat, len(r_for_rows))

    future_index = pd.MultiIndex.from_arrays([insts, r_for_rows], names=["instrument", "datetime"])
    fut = adj.reindex(future_index).to_numpy()
    cur = adj.reindex(adj.index).to_numpy()
    n_fut_ok = int((~np.isnan(fut)).sum())
    n_cur_ok = int((~np.isnan(cur)).sum())
    log.info("cur non-NaN=%d / %d   fut non-NaN=%d / %d", n_cur_ok, len(cur), n_fut_ok, len(fut))

    label = (fut / cur - 1.0)
    n_label_ok = int((~np.isnan(label)).sum())
    log.info("=== label non-NaN=%d / %d ===", n_label_ok, len(label))

    # CORE CHECK 3: does a SPECIFIC (instrument, r(t)) pair exist in adj?
    # take an early factor date (well inside the window), find its r(t), and probe one stock.
    early = panel_dates[100]
    rt = real_map[early]
    log.info("probe: early factor date=%s -> r(t)=%s", early.date(), getattr(rt, "date", lambda: rt)())
    if rt is not pd.NaT and not pd.isna(rt):
        log.info("is r(t)=%s in adj datetime index? %s", rt.date(), rt in set(panel_dates))
        some_inst = adj.index.get_level_values("instrument")[0]
        log.info("probe pair (%s, %s) in adj index? %s",
                 some_inst, rt.date(), (some_inst, rt) in adj.index)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
