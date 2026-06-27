# SCRIPT_STATUS: ACTIVE — research utility (microcap timing replication, 2026-06-11)
"""Build multiple daily turnover-structure / crowding metrics in one pass.

Motivation: top-5%-by-amount (build_concentration.py) measures MEGA-CAP crowding and
is LOW during the 2024 microcap deleveraging crash, so it cannot target microcap risk.
This adds OWN-segment crowding and flight-to-large metrics that plausibly do.

Per day (A-shares, drop .BJ, amount>0):
  - top5_amount       : top-5% by amount, share of total turnover (mega-cap crowding)
  - micro_turn_share  : smallest-400-by-total_mv turnover / total (MICROCAP CROWDING ↑=hot)
  - micro_turn_share_q10: bottom-10%-by-mcap turnover / total (broader microcap crowding)
  - large_turn_share  : largest-300-by-total_mv turnover / total (flight to large)
  - micro_internal_hhi: Herfindahl within the smallest-400 basket (liquidity drying)
  - micro_count_for_half: # of microcap names to reach 50% of microcap turnover (breadth)

Reads data/market/daily/YYYY/ (raw amount + total_mv; sandbox research read).
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DAILY_ROOT = PROJECT_ROOT / "data" / "market" / "daily"
OUT_DIR = PROJECT_ROOT / "workspace" / "outputs" / "microcap_timing"
N_MICRO = 400
N_LARGE = 300

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("build_conc_v2")


def main() -> None:
    years = sorted(int(p.name) for p in DAILY_ROOT.iterdir() if p.is_dir() and p.name.isdigit())
    rows = []
    for year in years:
        for fp in sorted((DAILY_ROOT / str(year)).glob("daily_*.parquet")):
            d = pd.read_parquet(fp, columns=["ts_code", "amount", "total_mv"])
            d = d[~d["ts_code"].str.endswith(".BJ")]
            d = d[np.isfinite(d["amount"]) & (d["amount"] > 0) & np.isfinite(d["total_mv"]) & (d["total_mv"] > 0)]
            n = len(d)
            if n < 50:
                continue
            amt = d["amount"].to_numpy(dtype="float64")
            mv = d["total_mv"].to_numpy(dtype="float64")
            total = amt.sum()

            order_amt = np.sort(amt)[::-1]
            k5 = max(1, int(round(n * 0.05)))

            mv_order = np.argsort(mv)  # ascending mcap
            micro_idx = mv_order[:N_MICRO]
            micro_amt = amt[micro_idx]
            micro_total = micro_amt.sum()
            q10 = max(1, int(round(n * 0.10)))
            micro_q10_idx = mv_order[:q10]
            large_idx = mv_order[-N_LARGE:]

            micro_sorted = np.sort(micro_amt)[::-1]
            cum = np.cumsum(micro_sorted)
            half = int(np.searchsorted(cum, 0.5 * micro_total) + 1)

            date = pd.to_datetime(fp.stem.split("_")[1], format="%Y%m%d")
            rows.append(
                {
                    "trade_date": date,
                    "n_stocks": n,
                    "top5_amount": order_amt[:k5].sum() / total,
                    "micro_turn_share": micro_total / total,
                    "micro_turn_share_q10": amt[micro_q10_idx].sum() / total,
                    "large_turn_share": amt[large_idx].sum() / total,
                    "micro_internal_hhi": float(((micro_amt / micro_total) ** 2).sum()),
                    "micro_count_for_half": half,
                }
            )
        log.info("year %d done (%d rows)", year, len(rows))
    df = pd.DataFrame(rows).set_index("trade_date").sort_index()
    df.to_parquet(OUT_DIR / "concentration_v2.parquet")
    log.info("saved %d days -> %s", len(df), OUT_DIR / "concentration_v2.parquet")
    log.info("describe:\n%s", df[["micro_turn_share", "large_turn_share", "micro_internal_hhi"]].describe().round(4).to_string())


if __name__ == "__main__":
    main()
