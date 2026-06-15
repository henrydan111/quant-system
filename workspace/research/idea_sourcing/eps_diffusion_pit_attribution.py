# SCRIPT_STATUS: ACTIVE — eps_diffusion OOS-decay PIT attribution (clean-window residual-lookahead stress)
"""Attribute the eps_diffusion OOS decay: is the clean-window weakness the factor's TRUE (weak) edge,
or is there a RESIDUAL PIT problem even on the real per-row create_time window (2022-05+)?

Test: push the report_rc visibility anchor progressively LATER by k EXTRA trading days
(Ref($report_rc__*, 1) -> Ref($report_rc__*, 1+k)). Extra lag can only REMOVE lookahead, never add
it. So:
  * clean-window IC FLAT across k  -> no residual lookahead; the weak 0.041 is the honest PIT-clean edge.
  * clean-window IC DROPS with k    -> the signal lives in the first day(s) after the report = a
                                       residual too-early read (PIT problem persists on real data).
Contrast the deep (pre-2022-05, JQ-consensus-BACKFILLED) window: if the deep strength also survives
lag, its inflation is a data-VINTAGE artifact (the 2022-05 reconstruction isn't genuinely as-of),
not a marginal-timing lookahead.

CAVEAT: these are 60d/120d ROLLING breadth factors — a few days of lag shifts a ~60d window only
slightly, so this test is INSENSITIVE to a per-revision (single-day) lookahead diluted over the
window. It cleanly detects a SHARP announcement-window read, not a subtle per-revision one. Read
alongside the buffer sweep (Spearman 0.94 across +1/+2/+3) and the conservative create_time+1 anchor.

DIAGNOSTIC over already-observed data — no seal, no new OOS pass.
Run: venv/Scripts/python.exe workspace/research/idea_sourcing/eps_diffusion_pit_attribution.py
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

import warnings
warnings.filterwarnings("ignore")
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.alpha_research.factor_library import operators as op  # noqa: E402
from src.alpha_research.factor_library.catalog import get_factor_catalog  # noqa: E402
from src.alpha_research.factor_eval.batch_screening import run_batch_screening  # noqa: E402

FACTORS = ["earn_eps_diffusion_60", "earn_eps_diffusion_120"]
QD = str(ROOT / "data" / "qlib_data")
HORIZONS = (5, 10, 20)
N_QUANTILES = 5
# (window_label, start, end, extra_lags_k)
PLAN = [
    ("clean_2022_05+", "2022-05-01", "2026-02-27", [0, 2, 5, 10]),   # real per-row create_time — the PIT test
    ("deep_backfill",  "2021-01-01", "2022-04-30", [0, 5]),          # JQ-backfilled — vintage-vs-timing contrast
]
LAG_RE = re.compile(r"(Ref\(\$report_rc__\w+, )1\)")


def lagged(expr: str, k: int) -> str:
    """Add k extra trading days to every report_rc visibility Ref (1 -> 1+k)."""
    if k == 0:
        return expr
    return LAG_RE.sub(lambda m: f"{m.group(1)}{1 + k})", expr)


def main() -> int:
    cat = get_factor_catalog(include_new_data=True)
    base = {f: cat[f] for f in FACTORS}
    print("eps_diffusion PIT attribution — extra-lag stress (RankICIR_20d; later anchor removes any lookahead)\n")
    for wlabel, start, end, lags in PLAN:
        print(f"================= {wlabel} ({start}..{end}) =================")
        traj = {f: [] for f in FACTORS}
        for k in lags:
            exprs = {f: lagged(base[f], k) for f in FACTORS}
            fdf, fwd = op.compute_factors(catalog=exprs, start_date=start, end_date=end,
                                          horizons=list(HORIZONS), qlib_dir=QD, kernels=1, stage="oos_test")
            fcols = [c for c in FACTORS if c in fdf.columns]
            res = run_batch_screening(fdf[fcols], fwd, horizons=HORIZONS, engine="batch", n_quantiles=N_QUANTILES)
            if hasattr(res, "reset_index"):
                res = res.reset_index()
            fac_col = "factor" if "factor" in res.columns else res.columns[0]
            for f in FACTORS:
                row = res[res[fac_col] == f]
                ric = float(row["rank_icir_20d"].iloc[0]) if len(row) and "rank_icir_20d" in res else float("nan")
                ls = float(row["ls_sharpe"].iloc[0]) if len(row) and "ls_sharpe" in res else float("nan")
                traj[f].append((k, ric, ls))
        for f in FACTORS:
            cells = " | ".join(f"+{k}td: ICIR={ric:+.3f} LS={ls:+.2f}" for k, ric, ls in traj[f])
            print(f"  {f:26} {cells}")
        print()
    print("READ: clean-window ICIR flat across +k => no residual lookahead (0.041 is the honest weak edge); "
          "a sharp drop => residual too-early read. Deep window holding across +k => data-vintage (backfill) "
          "artifact, not a marginal-timing lookahead.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
