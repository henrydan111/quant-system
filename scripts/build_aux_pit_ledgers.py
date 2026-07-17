# SCRIPT_STATUS: ACTIVE — 辅助 PIT 账本构建器:express / fina_audit / fina_mainbz
"""Build auxiliary PIT ledgers for the three intel-center gap datasets (缺口①②③).

范围与边界(诚实声明):
- 这三个账本服务 **事件/卡片**(经 pit_event_feed 白名单门读取),不是因子字段;
  若将来要进 provider bins/因子,必须迁入 pit_backend.DATASET_SPECS 正规族(记录在案);
- schema 与既有账本约定逐字一致:raw 列 + qlib_code + disclosure_date + effective_date,
  effective_date 用同一个 strictly_next_open_trade_day(§3.2 的承重锚,复用不重造);
- PIT 锚:express/fina_audit = 自带 ann_date(★文档已读,2026-07-09);
  **fina_mainbz 无 ann_date(仅报告期)→ 可见性 join income 账本同 (ts_code,end_date)
  的 ann_date**(主营构成随定期报告披露;join 不上的行丢弃并计数——fail-closed);
- 去重:同键多版本保留 ann_date 最新(restatement 取最新已知,与账本家族一致);
- 变更安全(§6.4):只写 data/pit_ledger/{express,fina_audit,fina_mainbz}/(新目录),
  支持 --dry-run;绝不触碰既有账本。

用法:
  venv/Scripts/python.exe scripts/build_aux_pit_ledgers.py --dry-run
  venv/Scripts/python.exe scripts/build_aux_pit_ledgers.py
"""
from __future__ import annotations

import argparse
import glob
import logging
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from data_infra.pit_backend import strictly_next_open_trade_day, ts_code_to_qlib  # noqa: E402

logger = logging.getLogger("aux_ledgers")

RAW_ROOT = PROJECT_ROOT / "data" / "fundamentals"
LEDGER_ROOT = PROJECT_ROOT / "data" / "pit_ledger"
TRADE_CAL = PROJECT_ROOT / "data" / "reference" / "trade_cal.parquet"
INCOME_LEDGER = LEDGER_ROOT / "income" / "income.parquet"

#: 去重键(同键保留 ann_date 最新)
DEDUP_KEYS = {
    "express": ["ts_code", "end_date"],
    "fina_audit": ["ts_code", "end_date"],
    # bz_code (P按产品 / D按地区 / I按行业) is part of the row identity — the SAME bz_item text can
    # appear under different breakdown dimensions, so omitting bz_code collapses distinct segment rows
    # (GPT sign-off HOLD MAJOR; matches the corrected fina_mainbz vendor_record_key in
    # raw_recovery_coordinator.py). See test_build_aux_pit_ledgers_fina_mainbz_bz_code.
    "fina_mainbz": ["ts_code", "end_date", "bz_item", "bz_code"],
}


def open_calendar() -> pd.DatetimeIndex:
    cal = pd.read_parquet(TRADE_CAL)
    dates = pd.to_datetime(cal.loc[cal["is_open"] == 1, "cal_date"].astype(str))
    return pd.DatetimeIndex(dates.sort_values().unique())


def load_raw(name: str) -> pd.DataFrame:
    files = sorted(glob.glob(str(RAW_ROOT / name / "*.parquet")))
    if not files:
        raise SystemExit(f"no raw files for {name} under {RAW_ROOT / name}")
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    logger.info("%s: %d raw rows from %d files", name, len(df), len(files))
    return df


def build_one(name: str, cal: pd.DatetimeIndex, dry_run: bool) -> dict:
    df = load_raw(name)
    stats = {"raw": len(df)}

    if name == "fina_mainbz":
        # 可见性 join:主营构成随定期报告披露 → income 同 (ts_code, end_date) 的 ann_date
        inc = pd.read_parquet(INCOME_LEDGER, columns=["ts_code", "end_date", "ann_date"])
        inc = (inc.assign(ann_date=pd.to_datetime(inc["ann_date"], errors="coerce"))
                  .dropna(subset=["ann_date"])
                  .groupby(["ts_code", "end_date"], as_index=False)["ann_date"].min())
        # 格式归一:mainbz='20260331' 紧凑串 vs income 账本=Timestamp → 统一紧凑串
        df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce").dt.strftime("%Y%m%d")
        inc["end_date"] = pd.to_datetime(inc["end_date"], errors="coerce").dt.strftime("%Y%m%d")
        df = df.merge(inc, on=["ts_code", "end_date"], how="left")
        stats["no_report_match_dropped"] = int(df["ann_date"].isna().sum())
        df = df[df["ann_date"].notna()]
    else:
        df["ann_date"] = pd.to_datetime(df["ann_date"], errors="coerce")
        stats["null_ann_dropped"] = int(df["ann_date"].isna().sum())
        df = df[df["ann_date"].notna()]

    # 去重:同键保留最新公告(restatement = 最新已知状态,与账本家族一致)
    df = (df.sort_values("ann_date")
            .drop_duplicates(subset=DEDUP_KEYS[name], keep="last"))
    stats["after_dedup"] = len(df)

    df["qlib_code"] = df["ts_code"].map(lambda v: ts_code_to_qlib(str(v), lower=True))
    df["disclosure_date"] = df["ann_date"]
    df["effective_date"] = strictly_next_open_trade_day(df["disclosure_date"], cal)
    stats["null_effective_dropped"] = int(df["effective_date"].isna().sum())
    df = df[df["effective_date"].notna()]
    stats["final"] = len(df)

    out_dir = LEDGER_ROOT / name
    out = out_dir / f"{name}.parquet"
    if dry_run:
        logger.info("[DRY-RUN] would write %d rows -> %s | %s", len(df), out, stats)
    else:
        out_dir.mkdir(parents=True, exist_ok=True)
        df.to_parquet(out, index=False)
        logger.info("wrote %d rows -> %s | %s", len(df), out, stats)
    return stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--datasets", default="express,fina_audit,fina_mainbz")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    targets = [d.strip() for d in args.datasets.split(",")]
    logger.info("aux ledger build: %s (dry_run=%s) — 只写新目录,不触碰既有账本",
                targets, args.dry_run)
    cal = open_calendar()
    for name in targets:
        if name not in DEDUP_KEYS:
            raise SystemExit(f"unknown dataset {name}")
        build_one(name, cal, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
