# SCRIPT_STATUS: ACTIVE — eps_diffusion re-evaluation: decompose the "too-good" 7.24 LS Sharpe
"""Re-evaluation diagnostic for the revoked earn_eps_diffusion_60/_120 (revoke 2026-06-14:
restatement residual [now MEASURED negligible] + deep-history granularity + UNEXPLAINED too-good
5d LS Sharpe 7.24). This decomposes that LS Sharpe to decide whether it is a CONTAMINATION
signature or a benign eval-config artifact (5d horizon + illiquid analyst-covered sub-universe +
gross), which is the last open item before a re-approval can be justified.

NOT a fresh sealed OOS: the 2021-2026 OOS (FrozenSelectionSet c5335681…) is already SPENT. This is
a post-hoc DIAGNOSTIC over already-observed data — it claims no seal and asserts no new OOS pass.
It uses the SAME screening path the registration used (run_batch_screening engine="batch",
n_quantiles=5 to match the quintile-era evidence) so the full-window 5d LS reproduces ~7.24 as a
built-in sanity check.

Reads two axes:
  * HORIZON 5/10/20 — a real signal's LS Sharpe degrades gracefully as the horizon lengthens;
    a t+0-style lookahead tends to be horizon-insensitive or erratic.
  * WINDOW full(2021-2026) vs clean(2022-05+, where create_time is a REAL per-row stamp) — if the
    clean window is consistent with / weaker than full, the pre-2022 deep-history JQ-approximation
    is NOT inflating the result (it adds noise, which deflates, not lookahead, which inflates).

Run: venv/Scripts/python.exe workspace/research/idea_sourcing/eps_diffusion_lssharpe_decomposition.py
"""
from __future__ import annotations
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
N_QUANTILES = 5   # match the pre-2026-06-11 quintile registration evidence
WINDOWS = {"full_2021_2026": ("2021-01-01", "2026-02-27"),
           "deep_2021_to_2022_04": ("2021-01-01", "2022-04-30"),   # pre-create_time, JQ-consensus-approximated breadth
           "clean_2022_05+": ("2022-05-01", "2026-02-27")}          # real per-row create_time breadth


def _col(df, *cands):
    for c in cands:
        if c in df.columns:
            return c
    return None


def main() -> int:
    cat = get_factor_catalog(include_new_data=True)
    exprs = {f: cat[f] for f in FACTORS}
    print("eps_diffusion LS-Sharpe decomposition (DIAGNOSTIC over spent OOS — no seal, no new pass)\n")

    out = {}
    for wlabel, (start, end) in WINDOWS.items():
        fdf, fwd = op.compute_factors(catalog=exprs, start_date=start, end_date=end,
                                      horizons=list(HORIZONS), qlib_dir=QD, kernels=1, stage="oos_test")
        fcols = [c for c in FACTORS if c in fdf.columns]
        res = run_batch_screening(fdf[fcols], fwd, horizons=HORIZONS, engine="batch", n_quantiles=N_QUANTILES)
        if hasattr(res, "reset_index"):
            res = res.reset_index()
        out[wlabel] = res
        print(f"================= window {wlabel} ({start}..{end}) =================")
        # keep only the columns that mention our metrics of interest, for a compact dump
        keep = [c for c in res.columns if any(k in str(c).lower()
                for k in ("factor", "name", "horizon", "rank_icir", "ls_sharpe", "rankic", "icir", "ic_mean"))]
        with pd.option_context("display.width", 200, "display.max_columns", 60):
            print(res[keep].to_string(index=False) if keep else res.to_string(index=False))
        print()

    sample = next(iter(out.values()))
    print("ALL result columns:", sorted(map(str, sample.columns.tolist())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
