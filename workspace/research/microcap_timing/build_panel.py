# SCRIPT_STATUS: ACTIVE — research utility (microcap timing replication, 2026-06-11)
"""Build wide daily panels (return / total_mv / traded flag) for microcap index replication.

Reads data/market/daily/YYYY/daily_YYYYMMDD.parquet (raw market kline — sandbox research
read; no PIT fundamentals involved) and caches dates x ts_code wide matrices to
workspace/outputs/microcap_timing/.

Window: 2012-01-01 .. data end (2026-02-27), giving MA200 warmup ahead of the
2014-01-02 evaluation start used by the Guoren chart.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DAILY_ROOT = PROJECT_ROOT / "data" / "market" / "daily"
OUT_DIR = PROJECT_ROOT / "workspace" / "outputs" / "microcap_timing"

START_YEAR = 2008
COLS = ["ts_code", "trade_date", "pct_chg", "total_mv", "vol"]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("build_panel")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    years = sorted(
        int(p.name) for p in DAILY_ROOT.iterdir() if p.is_dir() and p.name.isdigit()
    )
    years = [y for y in years if y >= START_YEAR]

    ret_frames, mv_frames, traded_frames = [], [], []
    for year in years:
        files = sorted((DAILY_ROOT / str(year)).glob("daily_*.parquet"))
        rows = []
        for fp in files:
            df = pd.read_parquet(fp, columns=COLS)
            rows.append(df)
        ydf = pd.concat(rows, ignore_index=True)
        ydf["trade_date"] = pd.to_datetime(ydf["trade_date"], format="%Y%m%d")
        ret = ydf.pivot_table(index="trade_date", columns="ts_code", values="pct_chg")
        mv = ydf.pivot_table(index="trade_date", columns="ts_code", values="total_mv")
        traded = ydf.pivot_table(index="trade_date", columns="ts_code", values="vol")
        ret_frames.append((ret / 100.0).astype("float32"))
        mv_frames.append(mv.astype("float64"))
        traded_frames.append(traded.notna().astype("int8"))
        log.info("year %d: %d days, %d codes", year, len(ret), ret.shape[1])

    ret_all = pd.concat(ret_frames).sort_index()
    mv_all = pd.concat(mv_frames).sort_index()
    traded_all = pd.concat(traded_frames).sort_index().fillna(0).astype("int8")

    # align columns across the three panels
    cols = ret_all.columns.union(mv_all.columns)
    ret_all = ret_all.reindex(columns=cols)
    mv_all = mv_all.reindex(columns=cols)
    traded_all = traded_all.reindex(columns=cols, fill_value=0)

    ret_all.to_parquet(OUT_DIR / "panel_ret.parquet")
    mv_all.to_parquet(OUT_DIR / "panel_total_mv.parquet")
    traded_all.to_parquet(OUT_DIR / "panel_traded.parquet")
    log.info(
        "saved panels: %d days x %d codes -> %s", len(ret_all), ret_all.shape[1], OUT_DIR
    )


if __name__ == "__main__":
    main()
