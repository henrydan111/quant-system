# SCRIPT_STATUS: ACTIVE — v1.5-D:政策三源试点回补(npr/货政/新闻联播 → hist store)
"""Policy text sources pilot backfill (§6.1 docs read + permission probed 2026-07-08).

可见性(DESIGN 同款纪律):
  npr             pubtime(真时间戳)          → real_timestamp
  monetary_policy pub_date 仅日级             → +1 开盘日 09:00, nominal_plus_lag
  cctv_news       date 名义日(19:00 播出)    → +1 开盘日 09:00, nominal_plus_lag
生产日拉:独立于 MVP 的 text_daily_pull(其 manifest 被 FORWARD_PREREG 门控,不可连坐)。
用法: venv/Scripts/python.exe workspace/research/ai_research_dept/engine/policy_ingest.py
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from workspace.research.ai_research_dept.engine import config as C  # noqa: E402
from workspace.research.ai_research_dept.engine.fact_table import decision_days  # noqa: E402
from data_infra.fetchers import TushareFetcher  # noqa: E402
from data_infra.text_store import _atomic_write_parquet, ingest_rows  # noqa: E402

logger = logging.getLogger("policy_ingest")
HIST = C.PROJECT_ROOT / "data" / "text_store_hist_pilot"


def plus_one_open(nominal: pd.Series) -> pd.Series:
    cal = pd.read_parquet(C.TRADE_CAL)
    opens = np.sort(cal.loc[cal["is_open"] == 1, "cal_date"].astype(str).unique())
    d8 = pd.to_datetime(nominal, errors="coerce").dt.strftime("%Y%m%d")
    idx = np.minimum(np.searchsorted(opens, d8.fillna("99999999").values, side="right"),
                     len(opens) - 1)
    out = pd.to_datetime(pd.Series(opens[idx], index=nominal.index),
                         format="%Y%m%d") + pd.Timedelta(hours=9)
    return out.where(d8.notna(), pd.NaT)


def stamp(source: str, sim: pd.Series, basis) -> None:
    p = HIST / source / f"text_{source}.parquet"
    df = pd.read_parquet(p)
    df["sim_visible_at"] = sim.values if len(sim) == len(df) else sim.reindex(df.index).values
    df["visibility_basis"] = basis
    _atomic_write_parquet(df, p)
    logger.info("%s: %d rows stamped (%s)", source, len(df), basis)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    days = decision_days(C.PILOT_POOL_MONTH, C.PILOT_MONTH_END)
    win_start = (pd.Timestamp(days[0]) - pd.Timedelta(days=35)).strftime("%Y-%m-%d")
    win_end = f"{days[-1][:4]}-{days[-1][4:6]}-{days[-1][6:]}"
    f = TushareFetcher()
    now = pd.Timestamp.now()

    npr = f.fetch_npr(f"{win_start} 00:00:00", f"{win_end} 23:59:59")
    logger.info("npr rows: %d", 0 if npr is None else len(npr))
    if npr is not None and not npr.empty:
        ingest_rows("npr", npr.reset_index(drop=True), published_col="pubtime",
                    retrieved_at=now, store_dir=HIST)
        full = pd.read_parquet(HIST / "npr" / "text_npr.parquet")
        stamp("npr", pd.to_datetime(full["pubtime"], errors="coerce"), "real_timestamp")

    mp = f.fetch_monetary_policy(win_start.replace("-", ""), days[-1])
    logger.info("monetary_policy rows: %d", 0 if mp is None else len(mp))
    if mp is not None and not mp.empty:
        ingest_rows("monetary_policy", mp.reset_index(drop=True), published_col=None,
                    retrieved_at=now, store_dir=HIST)
        full = pd.read_parquet(HIST / "monetary_policy" / "text_monetary_policy.parquet")
        stamp("monetary_policy", plus_one_open(full["pub_date"]), "nominal_plus_lag")

    frames = []
    for d in pd.date_range(win_start, win_end):
        df = f.fetch_cctv_news(d.strftime("%Y%m%d"))
        if df is not None and not df.empty:
            frames.append(df)
    cctv = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    logger.info("cctv_news rows: %d (%d days)", len(cctv), len(frames))
    if not cctv.empty:
        ingest_rows("cctv_news", cctv, published_col=None, retrieved_at=now,
                    store_dir=HIST)
        full = pd.read_parquet(HIST / "cctv_news" / "text_cctv_news.parquet")
        stamp("cctv_news", plus_one_open(full["date"]), "nominal_plus_lag")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
