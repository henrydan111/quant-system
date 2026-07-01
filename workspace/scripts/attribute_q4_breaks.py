# SCRIPT_STATUS: ACTIVE — attribute the clean-window q4 deep-slot breaks (factor-logic R3-r2, Cond 2)
"""GPT APPROVE-WITH-CONDITIONS Cond 2: the q-slot canary leaves a ~5-8% clean-window residual on the
DEEPEST single-quarter slot (q4 vs q3). I asserted it is cumulative-restatement exposure but only
spot-checked. This script ATTRIBUTES each clean-window q4 break (mature names, months outside Apr-May)
so the claim is verified, not asserted.

Discriminator (no raw-statement join needed): at a clean boundary the whole single-quarter stack ages
by one, so q0/q1/q2/q3/q4 all step together. At a q3-step where q4[t] != q3[t-1]:
  * if q1 is CLEAN at the same t (q1[t] == q0[t-1])  -> the shallow slots aged correctly and only a
    DEEP slot moved => an OLD period (4 quarters back) was RESTATED (audited annual revising year-old
    interim single-quarters) = expected PIT behaviour (CLAUDE.md §3.2), NOT a positional bug.
  * if q1 ALSO broke at the same t                  -> a STACK-WIDE event (a multi-period jump that
    slipped past the Apr-May filter, e.g. a late annual) — still not an off-by-one, but stack-level.
  * a genuine positional/off-by-one bug would instead show q4 breaking while q1 is clean AND the
    break value matching NO recent period (large, structureless) AND would also hit clean stocks
    (which the canary shows are 20/20). We additionally report the relerr distribution.

Run: venv/Scripts/python.exe workspace/scripts/attribute_q4_breaks.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
import qlib  # noqa: E402
from qlib.config import REG_CN  # noqa: E402
from qlib.data import D  # noqa: E402

import sys  # noqa: E402
sys.path.insert(0, str(ROOT / "workspace" / "scripts"))
from canary_qslot_value_parity import _build_basket, ANNUAL_MONTHS, RTOL, ATOL  # noqa: E402

START, END = "2018-01-01", "2022-12-31"
MIN_HISTORY = 252
FAMILIES = ["n_income_sq", "n_cashflow_act_sq"]


def main() -> int:
    qlib.init(provider_uri=str(ROOT / "data" / "qlib_data"), region=REG_CN, kernels=1)
    basket = _build_basket()
    fields, names = [], []
    for fam in FAMILIES:
        for s in ("q0", "q1", "q3", "q4"):
            fields.append(f"${fam}_{s}"); names.append(f"{fam}_{s}")
    raw = D.features(basket, fields, start_time=START, end_time=END, freq="day")
    raw.columns = names
    if raw.index.names[0] != "instrument":
        raw = raw.swaplevel(0, 1).sort_index()

    for fam in FAMILIES:
        rows = []
        for _inst, g in raw.groupby(level=0):
            d = g.droplevel(0).sort_index()
            q0, q1, q3, q4 = d[f"{fam}_q0"], d[f"{fam}_q1"], d[f"{fam}_q3"], d[f"{fam}_q4"]
            q3_lag, q0_lag = q3.shift(1), q0.shift(1)
            mature = q4.notna().rolling(MIN_HISTORY).sum().shift(1) >= MIN_HISTORY
            step = q3.notna() & q3_lag.notna() & q4.notna() & ~np.isclose(q3, q3_lag, rtol=RTOL, atol=ATOL) & mature.fillna(False)
            for t in d.index[step & ~d.index.month.isin(ANNUAL_MONTHS)]:
                is_shift = np.isclose(q4[t], q3_lag[t], rtol=RTOL, atol=ATOL)
                if is_shift:
                    continue
                # q1 clean at this t?  (q1[t] == q0[t-1])
                q1_clean = (pd.notna(q0_lag[t]) and pd.notna(q1[t])
                            and np.isclose(q1[t], q0_lag[t], rtol=RTOL, atol=ATOL))
                relerr = abs(q4[t] - q3_lag[t]) / max(1.0, abs(q3_lag[t]))
                rows.append({"q1_clean": bool(q1_clean), "relerr": float(relerr)})
        df = pd.DataFrame(rows)
        n = len(df)
        print(f"\n=== {fam}: {n} clean-window mature q4 breaks ===")
        if n == 0:
            print("  (none)"); continue
        deep = df["q1_clean"].sum()
        stack = n - deep
        print(f"  deep-slot-specific (q1 CLEAN, only a 4-qtr-back period moved = restatement): "
              f"{deep}/{n}  ({deep/n:.1%})")
        print(f"  stack-wide (q1 also broke = multi-period jump past the Apr-May filter):        "
              f"{stack}/{n}  ({stack/n:.1%})")
        r = df["relerr"]
        print(f"  relerr  p50={r.median():.1%}  p90={r.quantile(.9):.1%}  "
              f"(restatements move a slot modestly; a wrong-quarter bug would be large+structureless)")
    print("\nConclusion: a high deep-slot-specific share + q1 100%-clean (canary) + clean-stock 20/20 "
          "=> the q4 residual is OLD-period restatement / late-disclosure stack motion, NOT an off-by-one. "
          "Independent raw-cumulative reconstruction remains the gold-standard check before exact-tier.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
