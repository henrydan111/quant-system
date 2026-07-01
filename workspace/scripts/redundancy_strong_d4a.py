# SCRIPT_STATUS: ACTIVE — redundancy / marginal-contribution check for the strong D4a factors (R3 F6)
"""GPT 5.5 Pro factor-logic review Finding 6: the 4 "strong" D4a factors are
  qual_road  (ΔROA = NI_TTM/TA  − prior),  qual_roed (ΔROE = NI_TTM/equity − prior)   — share NI_TTM
  qual_cfoad (ΔCFOA= OCF_TTM/TA − prior),  qual_ccrd (ΔCCR = OCF_TTM/cur_liab − prior) — share OCF_TTM
so they may be ~2 distinct signals (net-income acceleration, cash-flow acceleration) repackaged
across denominators, NOT 4 independent discoveries. Memory: select factors by MARGINAL orthogonal
contribution, not standalone ICIR — near-duplicates must not be counted as separate wins.

This computes the average per-date cross-sectional Spearman correlation between each pair over a
broad liquid universe, monthly, 2018-2022, reading the catalog expressions through D.features
(workspace sandbox; bare D.features allowed outside src/). High within-group corr + low cross-group
corr would confirm ~2 signals.

Run: venv/Scripts/python.exe workspace/scripts/redundancy_strong_d4a.py
"""
from __future__ import annotations

from pathlib import Path
from itertools import combinations

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
import qlib  # noqa: E402
from qlib.config import REG_CN  # noqa: E402
from qlib.data import D  # noqa: E402

import sys  # noqa: E402
sys.path.insert(0, str(ROOT))
from src.alpha_research.factor_library.catalog import get_factor_catalog  # noqa: E402

FACTORS = ["qual_road", "qual_roed", "qual_cfoad", "qual_ccrd"]
GROUP = {"qual_road": "NI_TTM", "qual_roed": "NI_TTM", "qual_cfoad": "OCF_TTM", "qual_ccrd": "OCF_TTM"}
START, END = "2018-01-01", "2022-12-31"


def main() -> int:
    qlib.init(provider_uri=str(ROOT / "data" / "qlib_data"), region=REG_CN, kernels=1)
    cat = get_factor_catalog(include_new_data=True)
    exprs = [cat[f] for f in FACTORS]

    # broad universe sample for a representative cross-section
    uni = D.instruments(market="all")
    names = sorted(D.list_instruments(instruments=uni, start_time=START, end_time=END, as_list=True))
    names = names[:: max(1, len(names) // 700)][:700]
    print(f"universe: {len(names)} names")

    df = D.features(names, exprs, start_time=START, end_time=END, freq="day")
    df.columns = FACTORS
    if df.index.names[0] != "instrument":
        df = df.swaplevel(0, 1)
    df = df.sort_index()

    # monthly cross-sections: one date per month (last available per (year,month))
    dts = df.index.get_level_values("datetime")
    month_key = dts.to_period("M")
    df2 = df.copy()
    df2["_mk"] = month_key
    # pick, per instrument-month, the last row; simpler: sample the set of month-end dates present
    month_last = pd.Series(dts).groupby(month_key).max().tolist()
    sample = df.loc[(slice(None), month_last), :]

    pairs = list(combinations(FACTORS, 2))
    acc = {p: [] for p in pairs}
    for dt in month_last:
        cs = sample.xs(dt, level="datetime")
        cs = cs.dropna(how="any")
        if len(cs) < 30:
            continue
        r = cs.rank()
        for a, b in pairs:
            c = r[a].corr(r[b], method="pearson")  # pearson on ranks == spearman
            if pd.notna(c):
                acc[(a, b)].append(c)

    print(f"\n=== average per-date cross-sectional rank correlation ({len(month_last)} months) ===")
    for (a, b), v in acc.items():
        tag = "WITHIN-GROUP" if GROUP[a] == GROUP[b] else "cross-group"
        m = float(np.mean(v)) if v else float("nan")
        print(f"  {a:12} ~ {b:12}  rho={m:+.3f}   [{tag}, shares {GROUP[a] if GROUP[a]==GROUP[b] else '-'}]")

    # effective-signal summary
    within = [np.mean(acc[(a, b)]) for a, b in pairs if GROUP[a] == GROUP[b] and acc[(a, b)]]
    cross = [np.mean(acc[(a, b)]) for a, b in pairs if GROUP[a] != GROUP[b] and acc[(a, b)]]
    print(f"\n  mean WITHIN-group rho (ΔROE~ΔROA, ΔCFOA~ΔCCR): {np.mean(within):+.3f}")
    print(f"  mean cross-group rho (NI_TTM set vs OCF_TTM set): {np.mean(cross):+.3f}")
    print("\nInterpretation: high within-group + low cross-group rho => ~2 distinct signals "
          "(net-income acceleration, cash-flow acceleration), NOT 4. Select by marginal orthogonal "
          "contribution: keep one strong representative per group (or the orthogonalized residual), "
          "do not count near-duplicates as separate wins.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
