# SCRIPT_STATUS: ACTIVE — research utility (microcap timing replication, 2026-06-11)
"""Build a daily market turnover-concentration series from raw daily files.

Per the 小红书 risk-control idea: conc = (turnover of top-5% stocks by amount) /
(total market turnover). High conc = money crowding into few names (poor breadth),
historically associated with microcap underperformance. Also emits robustness
variants (top-1%, top-10%, Herfindahl, CSI300 turnover share).

Reads data/market/daily/YYYY/ (raw amount; sandbox research read). A-shares only
(drop .BJ). Window 2008+ so the 2009-2013 OOS has a warmed threshold.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DAILY_ROOT = PROJECT_ROOT / "data" / "market" / "daily"
OUT_DIR = PROJECT_ROOT / "workspace" / "outputs" / "microcap_timing"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("build_conc")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    years = sorted(int(p.name) for p in DAILY_ROOT.iterdir() if p.is_dir() and p.name.isdigit())
    rows = []
    for year in years:
        for fp in sorted((DAILY_ROOT / str(year)).glob("daily_*.parquet")):
            d = pd.read_parquet(fp, columns=["ts_code", "amount"])
            d = d[~d["ts_code"].str.endswith(".BJ")]
            a = d["amount"].to_numpy(dtype="float64")
            a = a[np.isfinite(a) & (a > 0)]
            if a.size < 50:
                continue
            total = a.sum()
            a_sorted = np.sort(a)[::-1]
            n = a.size
            k5 = max(1, int(round(n * 0.05)))
            k1 = max(1, int(round(n * 0.01)))
            k10 = max(1, int(round(n * 0.10)))
            hhi = float(((a / total) ** 2).sum())
            date = pd.to_datetime(fp.stem.split("_")[1], format="%Y%m%d")
            rows.append(
                {
                    "trade_date": date,
                    "n_stocks": n,
                    "conc_top5": a_sorted[:k5].sum() / total,
                    "conc_top1": a_sorted[:k1].sum() / total,
                    "conc_top10": a_sorted[:k10].sum() / total,
                    "hhi": hhi,
                    "total_amount": total,
                }
            )
        log.info("year %d done (%d rows so far)", year, len(rows))
    df = pd.DataFrame(rows).set_index("trade_date").sort_index()
    df.to_parquet(OUT_DIR / "concentration.parquet")
    log.info("saved %d days -> %s", len(df), OUT_DIR / "concentration.parquet")
    log.info("conc_top5 describe:\n%s", df["conc_top5"].describe().round(4).to_string())


if __name__ == "__main__":
    main()
