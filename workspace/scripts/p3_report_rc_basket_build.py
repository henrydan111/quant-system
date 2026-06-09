"""P3 basket validation — materialize report_rc into a STAGED provider on REAL data.

Sandbox-safe: a temp staged data_root (no live data/ pollution), basket-filtered so the
full-universe ledger cost (deferred Q5) is sidestepped. Proves the real re-fetched
report_rc (with create_time) flows raw -> normalize -> ledger -> $report_rc__* daily
bins, read back via the Qlib bin reader, with a coverage/sanity summary. Uses the LIVE
trading calendar + LIVE close.day.bin as the materializer's alignment reference.
"""
from __future__ import annotations
import glob, shutil, sys, time
from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT)); sys.path.insert(0, str(PROJECT_ROOT / "src"))
from data_infra.pit_backend import StagedQlibBackendBuilder, provider_calendar, ts_code_to_qlib  # noqa: E402
from data_infra.storage.qlib_bin_utils import read_qlib_bin, validate_stock_bins  # noqa: E402

LIVE = PROJECT_ROOT / "data"
LIVE_QLIB = LIVE / "qlib_data"
STAGE = PROJECT_ROOT / "workspace" / "outputs" / "p3_report_rc_basket"
BASKET = ["600519.SH", "000001.SZ", "600036.SH", "000651.SZ", "000002.SZ"]
RRC_FIELDS = ["report_rc__eps_up", "report_rc__eps_dn",
              "report_rc__eps_revision_count", "report_rc__n_active_analysts"]


def main():
    if STAGE.exists():
        shutil.rmtree(STAGE)
    data_root = STAGE / "data"
    (data_root / "reference").mkdir(parents=True)
    shutil.copy(LIVE / "reference" / "trade_cal.parquet", data_root / "reference" / "trade_cal.parquet")
    shutil.copy(LIVE / "reference" / "stock_basic.parquet", data_root / "reference" / "stock_basic.parquet")

    # basket-filtered raw report_rc
    rc_dir = data_root / "analyst" / "report_rc"
    rc_dir.mkdir(parents=True)
    raw_rows = 0
    for f in sorted(glob.glob(str(LIVE / "analyst" / "report_rc" / "*.parquet"))):
        sub = pd.read_parquet(f)
        sub = sub[sub["ts_code"].isin(BASKET)]
        if len(sub):
            sub.to_parquet(rc_dir / Path(f).name, index=False)
            raw_rows += len(sub)
    print(f"basket raw report_rc rows: {raw_rows}")

    b = StagedQlibBackendBuilder(data_root=str(data_root), qlib_dir=str(STAGE / "qlib"),
                                 build_id="p3_basket", allow_exceptions=True)
    t = time.time(); b.normalize_dataset("report_rc"); print(f"normalize: {time.time()-t:.1f}s")
    t = time.time(); res = b.build_ledger("report_rc"); print(f"build_ledger: {time.time()-t:.1f}s  {res}")
    led = pd.read_parquet(b.ledger_path("report_rc"))
    print(f"ledger rows: {len(led)}  stocks: {led['qlib_code'].nunique()}  "
          f"eff span: {pd.to_datetime(led['effective_date']).min().date()}..{pd.to_datetime(led['effective_date']).max().date()}")

    # materialize into staged feature dirs, aligned to LIVE calendar + LIVE close.day.bin
    cal = provider_calendar(str(LIVE_QLIB))
    feat_root = STAGE / "qlib" / "features"
    target_dirs = {}
    for ts in BASKET:
        qc = ts_code_to_qlib(ts, lower=True)
        live_close = LIVE_QLIB / "features" / qc / "close.day.bin"
        if not live_close.exists():
            print(f"  WARN no live close.day.bin for {qc}"); continue
        fd = feat_root / qc
        fd.mkdir(parents=True, exist_ok=True)
        shutil.copy(live_close, fd / "close.day.bin")
        target_dirs[qc] = str(fd)
    t = time.time()
    written = b._materialize_report_rc_consensus(cal, target_dirs)
    print(f"materialize: {time.time()-t:.1f}s  fields={written}")

    print("\n==== read-back ($report_rc__* via Qlib bin reader) ====")
    for ts in BASKET:
        qc = ts_code_to_qlib(ts, lower=True)
        fd = target_dirs.get(qc)
        if fd is None:
            continue
        errs = validate_stock_bins(fd, RRC_FIELDS)
        _, up = read_qlib_bin(str(Path(fd) / "report_rc__eps_up.day.bin"))
        _, dn = read_qlib_bin(str(Path(fd) / "report_rc__eps_dn.day.bin"))
        _, nact = read_qlib_bin(str(Path(fd) / "report_rc__n_active_analysts.day.bin"))
        maxn = np.nanmax(nact) if np.isfinite(nact).any() else float("nan")
        print(f"{ts} ({qc}): up_events={int(np.nansum(up))} dn_events={int(np.nansum(dn))} "
              f"max_n_active={maxn:.0f} active_days={int(np.isfinite(nact).sum())} "
              f"bins_valid={'OK' if not errs else errs}")
    print(f"\nstaged at {STAGE} (sandbox; live data/qlib_data untouched)")


if __name__ == "__main__":
    main()
