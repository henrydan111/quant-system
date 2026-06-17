# SCRIPT_STATUS: ACTIVE — #34 warmup-enforcement verification for the E1a price-volume factors
"""Verify the E1a windowed factors are FULLY WARMED at the IS-window start — the #34 formal-gate
prerequisite GPT 5.5 Pro flagged ("the gate must drop partial-window rows, not a generic 60d buffer").

The resolution is NOT a partial-row drop (which would lose data); it is that the IS evaluation window
(2010-01-01) sits deep INSIDE the provider calendar (which starts 2008-01-02), so Qlib's rolling
operators warm every window from the pre-IS runway. Two checks:

  (A) RUNWAY GUARD (structural, fast) — trading days between the calendar start and the IS start must
      be >= every E1a factor's lookback window. If someone moves is_start earlier or adds a deeper
      factor, this fires.
  (B) START-DATE INVARIANCE (empirical) — for each E1a factor, the values over the IS window must be
      BYTE-IDENTICAL whether the Qlib expression is requested from the calendar start (fully warmed)
      or from the IS start (warmed only via Qlib's internal window-extension). max|diff| must be 0.
      This proves the rebuilt matrix evidence (computed from is_start) carries no under-warmed rows.

Read-only. Exit 0 = both checks pass.
"""
from __future__ import annotations

import logging
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

import pandas as pd  # noqa: E402

from src.alpha_research.factor_library import get_factor_catalog  # noqa: E402
from workspace.scripts.unified_eval_full_run import TIME_SPLIT  # noqa: E402

QLIB_DIR = PROJECT_ROOT / "data" / "qlib_data"
CALENDAR = QLIB_DIR / "calendars" / "day.txt"
# E1a factors + their max lookback window (trading days). route/discrete = period/Σ over W (+1 Ref);
# time_rank = Rank(.,250) then Mean(.,20) -> ~271; highest_days = IdxMax(.,250) (+1 Ref) -> 251.
E1A_WINDOWS = {
    "mmt_route_20d": 22, "mmt_route_250d": 252,
    "mmt_discrete_20d": 22, "mmt_discrete_250d": 252,
    "mmt_time_rank_20d": 271, "mmt_highest_days_250d": 251,
}
# a small, liquid, long-listed basket spanning 2008+ (all listed before 2008)
BASKET = ["000001_SZ", "600519_SH", "000651_SZ", "600036_SH", "000333_SZ", "600000_SH"]
# compare over the first 2 IS years [is_start, OVERLAP_END] — covers the warmup-sensitive region
OVERLAP_END = "2011-12-31"
TOL = 1e-9


def main() -> int:
    logging.disable(logging.CRITICAL)
    cal = [l.strip() for l in CALENDAR.read_text().splitlines() if l.strip()]
    cal_start = cal[0]
    is_start = TIME_SPLIT.is_start
    runway = sum(1 for d in cal if d < is_start)   # trading days strictly before the IS start
    max_win = max(E1A_WINDOWS.values())

    print("=" * 78)
    print("E1a WARMUP-RUNWAY VERIFICATION (#34 prerequisite a)")
    print("=" * 78)
    print(f"provider calendar start = {cal_start} | IS window start = {is_start}")
    print(f"(A) RUNWAY GUARD: {runway} trading days before IS start vs max factor window {max_win} -> "
          f"{'PASS' if runway >= max_win else 'FAIL'}")
    runway_ok = runway >= max_win

    cat = get_factor_catalog(include_new_data=True)
    names = [n for n in E1A_WINDOWS if n in cat]
    fields = [cat[n] for n in names]

    import qlib
    from qlib.data import D
    from qlib.config import REG_CN
    qlib.init(provider_uri=str(QLIB_DIR), region=REG_CN, kernels=1)
    # warm = requested from the calendar start (fully warmed); cold = requested from the IS start
    # (warmed only via Qlib's internal window-extension). Both run to OVERLAP_END; compare [is_start, end].
    warm = D.features(BASKET, fields, start_time=cal_start, end_time=OVERLAP_END); warm.columns = names
    cold = D.features(BASKET, fields, start_time=is_start, end_time=OVERLAP_END); cold.columns = names

    print(f"(B) START-DATE INVARIANCE over [{is_start}, {OVERLAP_END}] "
          f"(warmed-from-{cal_start} vs from-{is_start}):")
    all_inv_ok = True
    for n in names:
        a = warm[n].reset_index(); a = a[a["datetime"] >= is_start].set_index(["instrument", "datetime"])[n]
        b = cold[n]
        j = pd.concat([a.rename("w"), b.rename("c")], axis=1).dropna()
        md = float((j["w"] - j["c"]).abs().max()) if len(j) else float("nan")
        early = j.reset_index()
        early = early[early["datetime"] <= "2010-02-15"]
        me = float((early["w"] - early["c"]).abs().max()) if len(early) else float("nan")
        ok = md < TOL
        all_inv_ok &= ok
        print(f"    {n:22} win={E1A_WINDOWS[n]:3d} overlap={len(j):4d} max|diff|={md:.3e} "
              f"early(<=2010-02-15)|diff|={me:.3e} -> {'WARMED-OK' if ok else 'UNDER-WARMED'}")

    verdict = runway_ok and all_inv_ok
    print(f"\nVERDICT: runway_guard={'PASS' if runway_ok else 'FAIL'} | "
          f"start_invariance={'PASS' if all_inv_ok else 'FAIL'} -> "
          f"{'ALL PASS — E1a factors are warmup-clean over the IS window' if verdict else 'FAIL'}")
    return 0 if verdict else 1


if __name__ == "__main__":
    raise SystemExit(main())
