# SCRIPT_STATUS: ACTIVE — AI 链路观察站 Block A:历史文本获取(Class-D 试点,非证据)
"""Fetch 1yr of text for the 202501 golden-pool names into the ISOLATED hist store.

红线(DESIGN.md §1.3):落库目标是 data/text_store_hist_pilot/ —— 绝不写生产
data/text_store/(回填行的 decision_visible_at=今天,会以"新文本"身份污染 202608 前向)。

四源、串行(§6.1:不并行打 Tushare)、可断点续跑(fetch_progress.json)、
content_hash 幂等(重复 ingest 无副作用)。入库走生产同款 C1 machinery
(text_store.ingest_rows(store_dir=...)),随后补打模拟可见性列:

    sim_visible_at / visibility_basis   (DESIGN.md §3)
    anns_d          rec_time                        real_timestamp
    irm_qa_sh/sz    pub_time                        real_timestamp
    research_report trade_date + 2 开盘日 09:00      nominal_date_plus_2open (report_rc 先例)

用法:
  venv/Scripts/python.exe workspace/research/ai_chain_observatory/fetch_hist_text.py --max-days 2   # 冒烟
  venv/Scripts/python.exe workspace/research/ai_chain_observatory/fetch_hist_text.py                # 全量 (~1-2h)
  ... --sources anns_d,research_report                                                              # 指定源
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from data_infra.text_store import _atomic_write_parquet, ingest_rows  # noqa: E402
from data_infra.fetchers import TushareFetcher  # noqa: E402

HIST_STORE = PROJECT_ROOT / "data" / "text_store_hist_pilot"
OUT_DIR = PROJECT_ROOT / "workspace" / "outputs" / "ai_chain_observatory"
PROGRESS_PATH = OUT_DIR / "fetch_progress.json"
MANIFEST_PATH = OUT_DIR / "fetch_manifest.json"
POOL_PATH = PROJECT_ROOT / "data" / "analyst" / "broker_recommend" / "broker_recommend_202501.parquet"
TRADE_CAL = PROJECT_ROOT / "data" / "reference" / "trade_cal.parquet"
LOG_PATH = PROJECT_ROOT / "logs" / "ai_chain_observatory_fetch.log"

WINDOW_START = "20240101"          # 1yr lookback before the Jan-2025 decisions
WINDOW_END = "20250131"            # replay only consumes sim_visible <= decision day
ALL_SOURCES = ("anns_d", "irm_qa_sh", "irm_qa_sz", "research_report")

logger = logging.getLogger("hist_fetch")


def _setup_logging() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout),
                  logging.FileHandler(LOG_PATH, encoding="utf-8")],
    )
    logging.getLogger("data_infra").setLevel(logging.WARNING)


def load_pool() -> set[str]:
    df = pd.read_parquet(POOL_PATH)
    codes = set(df["ts_code"].dropna())
    if len(codes) < 100:
        raise RuntimeError(f"pool suspiciously small ({len(codes)}) — refusing")
    return codes


def calendar_days(start: str, end: str) -> list[str]:
    return [d.strftime("%Y%m%d") for d in pd.date_range(start, end)]


def load_progress() -> set[str]:
    if PROGRESS_PATH.exists():
        return set(json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))["done"])
    return set()


def save_progress(done: set[str], extra: dict | None = None) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"done": sorted(done)}
    if extra:
        payload.update(extra)
    PROGRESS_PATH.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


# ------------------------------------------------------------------ fetchers

def fetch_anns_day(f: TushareFetcher, day: str, pool: set[str],
                   truncated: list[str]) -> int:
    df = f.fetch_anns_d_paged(day, max_pages=10)
    if df is None or df.empty:
        return 0
    if df.attrs.get("truncated"):
        truncated.append(day)
        logger.warning("anns_d %s TRUNCATED at max_pages — day under-fetched", day)
    sub = df[df["ts_code"].isin(pool)]
    if sub.empty:
        return 0
    ingest_rows("anns_d", sub.reset_index(drop=True), published_col="rec_time",
                retrieved_at=pd.Timestamp.now(), store_dir=HIST_STORE)
    return len(sub)


def fetch_report_day(f: TushareFetcher, day: str, pool: set[str],
                     truncated: list[str]) -> int:
    """research_report caps at 1000/call market-wide — offset-paginate the day."""
    frames, page = [], 0
    while page < 8:
        df = f._safe_api_call(f.pro.research_report, trade_date=day,
                              limit=1000, offset=page * 1000)
        if df is None or df.empty:
            break
        frames.append(df)
        if len(df) < 1000:
            break
        page += 1
    else:
        truncated.append(day)
        logger.warning("research_report %s hit 8-page cap — day under-fetched", day)
    if not frames:
        return 0
    allday = pd.concat(frames, ignore_index=True)
    sub = allday[allday["ts_code"].isin(pool)]
    if sub.empty:
        return 0
    ingest_rows("research_report", sub.reset_index(drop=True), published_col=None,
                retrieved_at=pd.Timestamp.now(), store_dir=HIST_STORE)
    return len(sub)


def fetch_irm_day(f: TushareFetcher, source: str, day: str, pool: set[str],
                  truncated: list[str]) -> int:
    fn = f.fetch_irm_qa_sh if source == "irm_qa_sh" else f.fetch_irm_qa_sz
    df = fn(day, day)
    if df is None or df.empty:
        return 0
    if len(df) >= 3000:
        truncated.append(day)
        logger.warning("%s %s returned 3000-row cap — day may be under-fetched",
                       source, day)
    sub = df[df["ts_code"].isin(pool)]
    if sub.empty:
        return 0
    ingest_rows(source, sub.reset_index(drop=True), published_col="pub_time",
                retrieved_at=pd.Timestamp.now(), store_dir=HIST_STORE)
    return len(sub)


# --------------------------------------------------- simulated visibility pass

def stamp_sim_visibility() -> dict:
    """Post-pass: add sim_visible_at / visibility_basis to every hist-store row.

    生产 C1 戳(decision_visible_at=真实入库时刻)原样保留 — 看板要展示两者的差,
    这是 PIT 教学素材,不是要抹掉的瑕疵。
    """
    cal = pd.read_parquet(TRADE_CAL)
    open_days = np.sort(cal.loc[cal["is_open"] == 1, "cal_date"].astype(str).values)

    def plus_n_open(nominal: pd.Series, n: int) -> pd.Series:
        """nominal date (YYYYMMDD str-able) -> n-th open day strictly after, 09:00."""
        d8 = pd.to_datetime(nominal, errors="coerce").dt.strftime("%Y%m%d")
        idx = np.searchsorted(open_days, d8.fillna("99999999").values, side="right")
        idx = np.minimum(idx + (n - 1), len(open_days) - 1)
        out = pd.to_datetime(pd.Series(open_days[idx], index=nominal.index),
                             format="%Y%m%d") + pd.Timedelta(hours=9)
        return out.where(d8.notna(), pd.NaT)

    stats = {}
    for source in ALL_SOURCES:
        path = HIST_STORE / source / f"text_{source}.parquet"
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        if source == "anns_d":
            sim = pd.to_datetime(df["rec_time"], errors="coerce")
            fallback = plus_n_open(df["ann_date"], 1)
            basis = np.where(sim.notna(), "real_timestamp", "nominal_plus_lag")
            sim = sim.fillna(fallback)
        elif source.startswith("irm_qa"):
            # 深史 SZ 行 pub_time=None(仅名义 trade_date)— C1 语义:名义日不可当可见时点,
            # 保守回退 = trade_date 的下一开盘日 09:00
            sim = pd.to_datetime(df["pub_time"], errors="coerce")
            fallback = plus_n_open(df["trade_date"], 1)
            basis = np.where(sim.notna(), "real_timestamp", "nominal_plus_lag")
            sim = sim.fillna(fallback)
        else:  # research_report — nominal trade_date + 2 open days (report_rc 先例)
            sim = plus_n_open(df["trade_date"], 2)
            basis = np.full(len(df), "nominal_date_plus_2open")
        df["sim_visible_at"] = sim
        df["visibility_basis"] = basis
        n_bad = int(df["sim_visible_at"].isna().sum())
        if n_bad:
            logger.warning("%s: %d rows with unresolvable sim_visible_at (excluded "
                           "by replay loader)", source, n_bad)
        _atomic_write_parquet(df, path)
        stats[source] = {"rows": len(df), "unresolved": n_bad,
                         "basis_counts": pd.Series(basis).value_counts().to_dict()}
        logger.info("sim-visibility stamped: %s rows=%d unresolved=%d",
                    source, len(df), n_bad)
    return stats


# ------------------------------------------------------------------------ main

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", default=",".join(ALL_SOURCES))
    ap.add_argument("--start", default=WINDOW_START)
    ap.add_argument("--end", default=WINDOW_END)
    ap.add_argument("--max-days", type=int, default=0, help="smoke test: limit days/source")
    ap.add_argument("--skip-fetch", action="store_true", help="only re-stamp sim visibility")
    args = ap.parse_args()

    _setup_logging()
    sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    bad = set(sources) - set(ALL_SOURCES)
    if bad:
        raise SystemExit(f"unknown sources: {bad}")

    pool = load_pool()
    logger.info("pool 202501: %d names | window %s..%s | hist store: %s",
                len(pool), args.start, args.end, HIST_STORE)

    t0 = time.time()
    counts: dict[str, int] = {}
    truncated: dict[str, list[str]] = {s: [] for s in sources}

    if not args.skip_fetch:
        fetcher = TushareFetcher()
        done = load_progress()
        days = calendar_days(args.start, args.end)
        for source in sources:
            remaining = [d for d in days if f"{source}:{d}" not in done]
            todo = remaining[: args.max_days] if args.max_days else remaining
            logger.info("[%s] fetching %d of %d remaining days (%d already done)",
                        source, len(todo), len(remaining), len(days) - len(remaining))
            got = 0
            for i, day in enumerate(todo, 1):
                if source == "anns_d":
                    got += fetch_anns_day(fetcher, day, pool, truncated[source])
                elif source == "research_report":
                    got += fetch_report_day(fetcher, day, pool, truncated[source])
                else:
                    got += fetch_irm_day(fetcher, source, day, pool, truncated[source])
                done.add(f"{source}:{day}")
                if i % 20 == 0:
                    save_progress(done)
                    logger.info("[%s] %d/%d days | pool rows so far=%d | %.0fs",
                                source, i, len(todo), got, time.time() - t0)
            save_progress(done)
            counts[source] = got
            logger.info("[%s] DONE: %d pool rows, %d truncated days",
                        source, got, len(truncated[source]))

    stats = stamp_sim_visibility()

    coverage = {}
    for source in ALL_SOURCES:
        path = HIST_STORE / source / f"text_{source}.parquet"
        if path.exists():
            df = pd.read_parquet(path, columns=["ts_code"])
            coverage[source] = int(df["ts_code"].nunique())
    manifest = {
        "run_ts": pd.Timestamp.now().isoformat(),
        "window": {"start": args.start, "end": args.end},
        "pool_names": len(pool),
        "batch_pool_rows": counts,
        "truncated_days": {s: v for s, v in truncated.items() if v},
        "sim_visibility": stats,
        "pool_coverage_names": coverage,
        "elapsed_s": round(time.time() - t0, 1),
        "evidence_class": "NON_EVIDENTIARY_PILOT (C5 quasi-forward; DESIGN.md)",
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                             encoding="utf-8")
    logger.info("manifest -> %s", MANIFEST_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
