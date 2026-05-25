"""Instrument v18's ranked_schedule + at-open filter on the stuck-cash Tuesdays
to find WHY v18 didn't rebuy on 08-25 / 09-01 / 09-08.

Reuses v18's universe + schedule construction functions."""

import sys
from pathlib import Path
import pandas as pd

P = Path(r"E:/量化系统")
sys.path.insert(0, str(P))
sys.path.insert(0, str(P / "workspace/scripts"))

import importlib.util
spec = importlib.util.spec_from_file_location("v18mod", str(P / "workspace/scripts/p1_jq_g5a2_mimic_v18_no_trim.py"))
v18 = importlib.util.module_from_spec(spec)
# Prevent main() from running
import builtins
spec.loader.exec_module(v18)

START = pd.Timestamp("2014-01-01")
END = pd.Timestamp("2026-02-27")

universe = v18.build_universe_per_date(START, END)
ranked_schedule, per_day_quotes = v18.compute_rebalance_schedule_v6(universe, START, END)

check_dates = ["2015-08-19", "2015-08-25", "2015-09-01", "2015-09-08", "2015-09-15"]
print()
print("=" * 80)
print("Is each date in ranked_schedule? How many pass the at-open filter?")
print("=" * 80)
EPS = 1e-4
for ds in check_dates:
    d = pd.Timestamp(ds)
    in_sched = d in ranked_schedule
    print(f"\n{ds} (weekday={d.weekday()}): in_ranked_schedule={in_sched}")
    if not in_sched:
        print("   → NOT a rebal date! v18 will NOT rebalance here.")
        continue
    ranked = ranked_schedule[d]
    print(f"   ranked list length: {len(ranked)}")
    # Apply at-open filter
    n_unlocked = 0
    n_no_quote = 0
    n_limit_up = 0
    n_limit_down = 0
    first12 = []
    for code in ranked:
        q = per_day_quotes.get((d, code))
        if q is None:
            n_no_quote += 1
            continue
        open_ = q.get("open"); up = q.get("up_limit"); dn = q.get("down_limit")
        if open_ is None or up is None:
            n_no_quote += 1
            continue
        if open_ >= up - EPS:
            n_limit_up += 1
            continue
        if dn is not None and open_ <= dn + EPS:
            n_limit_down += 1
            continue
        n_unlocked += 1
        if len(first12) < 12:
            first12.append(code)
    print(f"   at-open filter: {n_unlocked} unlocked, {n_no_quote} no-quote, "
          f"{n_limit_up} limit-up, {n_limit_down} limit-down")
    print(f"   → target_unlocked would have {min(n_unlocked,12)} stocks: {first12[:6]}...")
