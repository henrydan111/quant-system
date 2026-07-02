# SCRIPT_STATUS: ACTIVE — one-time in-place re-anchor of the bare share-capital bins in the live provider
"""Re-anchor the bare ``total_share`` / ``float_share`` / ``free_share`` bins in the EXISTING
Qlib provider from the raw ``data/market/daily`` columns (EFFECTIVE-DATE anchor), without a
full rebuild.

Why: the balancesheet snapshot family's bare compat alias used to clobber ``total_share`` with
the REPORT-anchored q0 series — 1-2 months late vs real share changes and internally
inconsistent with ``$total_mv`` (2026-07-01 果仁-parity finding: BYD 002594 3× share change
visible in raw daily from 2025-07-30 but in the bin only from 2025-11-03). The provider build
now materializes these bins via ``PITBackend._materialize_share_capital_daily`` (already
wired); this script applies the SAME shared kernel (``share_capital_daily_arrays``) to the
published provider in place, so live data and all future builds share one definition.

Units follow ``SHARE_CAPITAL_DAILY_FIELDS`` (legacy-preserving): ``total_share`` in 股
(raw 万股 × 1e4), ``float_share``/``free_share`` in 万股 (raw verbatim).

Safety (CLAUDE.md §6.4): dry-run by default (reports per-field diff stats, writes nothing);
``--live`` first BACKS UP every bin it will overwrite into ``--backup-dir`` and then writes.
Only the three share-capital ``.day.bin`` files per symbol are touched — no staged provider
copy, no calendar change, no ``_qN`` slot change.
"""
from __future__ import annotations

import argparse
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from data_infra.storage.qlib_bin_utils import get_bin_info, read_qlib_bin, write_qlib_bin  # noqa: E402
from data_infra.pit_backend import (  # noqa: E402
    SHARE_CAPITAL_DAILY_FIELDS,
    load_share_capital_daily_frame,
    share_capital_daily_arrays,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("fix_share_capital_bins")

DATA_ROOT = PROJECT_ROOT / "data"
QLIB_DIR = DATA_ROOT / "qlib_data"
FEATURES = QLIB_DIR / "features"
SPOT_CHECK_SYMBOLS = ("002594_sz", "302132_sz")  # BYD (2025 3× 转增), 中航成飞 (2025-01 定增 + 2025-08 注销)


def _load_calendar() -> pd.DatetimeIndex:
    with open(QLIB_DIR / "calendars" / "day.txt", "r", encoding="utf-8") as handle:
        return pd.DatetimeIndex([line.strip() for line in handle if line.strip()])


def _aligned_slice(values: np.ndarray, start_index: int, length: int) -> np.ndarray:
    """Mirror ``PITBackend._write_feature_series`` alignment: full-calendar array -> close-bin window."""
    aligned = np.full(length, np.nan, dtype=np.float32)
    available = max(min(len(values), start_index + length) - start_index, 0)
    if available > 0:
        aligned[:available] = values[start_index : start_index + available].astype(np.float32)
    return aligned


def _step_dates(series: pd.Series) -> pd.Series:
    valid = series.dropna()
    return valid[valid.diff().fillna(0) != 0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="backup + write the bins (default: dry-run, no writes)")
    ap.add_argument("--limit", type=int, default=0, help="process only the first N symbols (testing)")
    ap.add_argument(
        "--backup-dir",
        type=str,
        default=str(DATA_ROOT / "backups" / f"share_capital_bins_{datetime.now():%Y%m%d_%H%M%S}"),
        help="where the pre-fix bins are copied before overwriting (--live only)",
    )
    args = ap.parse_args()
    backup_dir = Path(args.backup_dir)

    fields = list(SHARE_CAPITAL_DAILY_FIELDS)
    dirs = sorted(d for d in FEATURES.iterdir() if d.is_dir())
    if args.limit:
        dirs = dirs[: args.limit]
    log.info(
        "%s: will touch ONLY %s under %d symbol dirs in %s%s",
        "LIVE" if args.live else "DRY-RUN",
        [f"{name}.day.bin" for name in fields],
        len(dirs),
        FEATURES,
        f" (backup -> {backup_dir})" if args.live else "",
    )

    calendar = _load_calendar()
    frame = load_share_capital_daily_frame(str(DATA_ROOT), fields=fields)
    groups = {ts_code: group for ts_code, group in frame.groupby("ts_code")}
    log.info("raw daily share-capital rows: %d over %d symbols", len(frame), len(groups))

    stats = {name: {"symbols_changed": 0, "changed_days": 0, "written": 0, "created": 0} for name in fields}
    skipped_no_raw = skipped_no_close = 0
    spot_report: list[str] = []

    for d in dirs:
        ref = get_bin_info(str(d / "close.day.bin"))
        if ref is None or not ref["valid"]:
            skipped_no_close += 1
            continue
        symbol_df = groups.get(d.name.replace("_", ".").upper())
        if symbol_df is None:
            skipped_no_raw += 1  # index codes / names outside the daily universe: bins untouched
            continue
        arrays = share_capital_daily_arrays(symbol_df, calendar, fields=fields)
        start_index, length = ref["start_index"], ref["data_len"]
        for field_name, values in arrays.items():
            new = _aligned_slice(values, start_index, length)
            bin_path = d / f"{field_name}.day.bin"
            old = None
            if bin_path.exists():
                old_si, old = read_qlib_bin(str(bin_path))
                if old_si == start_index and len(old) == length:
                    diff = ~np.isclose(old, new, rtol=1e-6, atol=0.0, equal_nan=True)
                    n_diff = int(diff.sum())
                else:
                    n_diff = length  # misaligned legacy bin: treat as fully changed
            else:
                n_diff = length
                stats[field_name]["created"] += 1
            if n_diff:
                stats[field_name]["symbols_changed"] += 1
                stats[field_name]["changed_days"] += n_diff
            if d.name in SPOT_CHECK_SYMBOLS and field_name == "total_share":
                window = calendar[start_index : start_index + length]
                old_steps = _step_dates(pd.Series(old, index=window)) if old is not None and len(old) == length else pd.Series(dtype=float)
                new_steps = _step_dates(pd.Series(new, index=window))
                spot_report.append(
                    f"{d.name} total_share steps OLD (last 4):\n{old_steps.tail(4).to_string()}\n"
                    f"{d.name} total_share steps NEW (last 4):\n{new_steps.tail(4).to_string()}"
                )
            if args.live:
                if bin_path.exists():
                    target = backup_dir / d.name
                    target.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(bin_path, target / bin_path.name)
                write_qlib_bin(str(bin_path), new, start_index=start_index)
                stats[field_name]["written"] += 1

    log.info("=== %s SUMMARY ===", "LIVE" if args.live else "DRY-RUN")
    log.info("symbols: processed=%d skipped_no_raw(index etc.)=%d skipped_no_close=%d",
             len(dirs), skipped_no_raw, skipped_no_close)
    for field_name, s in stats.items():
        log.info("%s: symbols_changed=%d changed_days=%d created=%d written=%d",
                 field_name, s["symbols_changed"], s["changed_days"], s["created"], s["written"])
    for block in spot_report:
        log.info("SPOT CHECK\n%s", block)
    if not args.live:
        log.info("dry-run complete — no bins written. Re-run with --live to apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
