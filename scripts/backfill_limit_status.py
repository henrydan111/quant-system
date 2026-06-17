# SCRIPT_STATUS: ACTIVE — one-time backfill of the derived limit_status field into the live provider
"""Backfill the derived ``limit_status`` field into the EXISTING Qlib provider without a full rebuild.

For every symbol feature dir it reads the already-written, calendar-aligned ``close`` / ``up_limit`` /
``down_limit`` bins and writes ``limit_status.day.bin`` via the SAME :func:`compute_limit_status` the
provider build now uses (so the live provider and all future builds share one definition). Additive —
it only ADDS ``limit_status.day.bin`` (never overwrites existing bins). Future ``build_qlib_backend``
runs maintain the field via ``PITBackend._materialize_derived_limit_status`` (already wired).

Dry-run by default (reports stats + sanity rate, writes nothing); ``--live`` writes the bins.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from data_infra.storage.qlib_bin_utils import read_qlib_bin, write_qlib_bin  # noqa: E402
from data_infra.pit_backend import compute_limit_status, LIMIT_STATUS_FIELD  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("backfill_limit_status")
FEATURES = PROJECT_ROOT / "data" / "qlib_data" / "features"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="write the bins (default: dry-run, no writes)")
    ap.add_argument("--limit", type=int, default=0, help="process only the first N symbols (testing)")
    args = ap.parse_args()

    dirs = sorted([d for d in FEATURES.iterdir() if d.is_dir()])
    if args.limit:
        dirs = dirs[: args.limit]
    log.info("%s: %d symbol dirs under %s", "LIVE" if args.live else "DRY-RUN", len(dirs), FEATURES)

    written = skipped_missing = skipped_misaligned = 0
    up_days = down_days = normal_days = nan_days = bad_value = 0
    for d in dirs:
        paths = {k: d / f"{k}.day.bin" for k in ("close", "up_limit", "down_limit")}
        if not all(p.exists() for p in paths.values()):
            skipped_missing += 1
            continue
        si_c, close = read_qlib_bin(str(paths["close"]))
        si_u, up = read_qlib_bin(str(paths["up_limit"]))
        si_d, dn = read_qlib_bin(str(paths["down_limit"]))
        if not (si_c == si_u == si_d and len(close) == len(up) == len(dn)):
            skipped_misaligned += 1
            log.warning("%s: bins misaligned (close=%d/%d up=%d/%d down=%d/%d) — skip",
                        d.name, si_c, len(close), si_u, len(up), si_d, len(dn))
            continue
        status = compute_limit_status(close, up, dn)
        up_days += int(np.nansum(status == 1.0)); down_days += int(np.nansum(status == -1.0))
        normal_days += int(np.nansum(status == 0.0)); nan_days += int(np.isnan(status).sum())
        uniq = set(np.unique(status[~np.isnan(status)]).tolist())
        if not uniq <= {-1.0, 0.0, 1.0}:
            bad_value += 1
            log.error("%s: limit_status has unexpected values %s", d.name, uniq)
        if args.live:
            write_qlib_bin(str(d / f"{LIMIT_STATUS_FIELD}.day.bin"), status, start_index=si_c)
            written += 1

    observed = up_days + down_days + normal_days
    rate = (up_days + down_days) / observed if observed else 0.0
    log.info("=== %s SUMMARY ===", "LIVE" if args.live else "DRY-RUN")
    log.info("symbols: processed=%d written=%d skipped_missing_bins=%d skipped_misaligned=%d",
             len(dirs), written, skipped_missing, skipped_misaligned)
    log.info("stock-days: up_limit=%d down_limit=%d normal=%d nan=%d | limit-day rate=%.2f%% (expect ~1-5%%)",
             up_days, down_days, normal_days, nan_days, rate * 100)
    log.info("value domain check: out-of-{-1,0,1} symbols=%d (want 0)", bad_value)
    if not args.live:
        log.info("dry-run complete — no bins written. Re-run with --live to backfill.")
    return 0 if bad_value == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
