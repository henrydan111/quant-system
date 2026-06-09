"""A3 fix: drop globally-all-null columns from income_quarterly raw parquets.

`income_quarterly` carries `ebit`/`ebitda` columns that are 100% NULL (Tushare's
single-quarter report_type 2/3 rows never populate cumulative-only fields) — a silent
NaN trap. This drops any column that is all-null across EVERY period file (uniform
schema), after archiving the whole directory.

NOTE: the PIT ledger / Qlib provider were built from the pre-clean raw and should be
rebuilt on the next cycle to drop these columns downstream too (not urgent — no factor
reads single-quarter ebit/ebitda).
"""
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(r'E:\量化系统')
LIVE = ROOT / 'data' / 'fundamentals' / 'income_quarterly'
ARCHIVE = ROOT / 'data' / 'fundamentals' / '_archive' / f'income_quarterly_pre_clean_{datetime.now():%Y%m%d_%H%M%S}'


def main():
    files = sorted(LIVE.glob('*.parquet'))
    if not files:
        print(f'FATAL: no parquet under {LIVE}')
        sys.exit(1)
    print(f'{len(files)} income_quarterly files')

    # global non-null count per column
    nonnull, total = {}, 0
    for f in files:
        t = pq.read_table(f)
        total += t.num_rows
        for name in t.column_names:
            col = t[name]
            nonnull[name] = nonnull.get(name, 0) + (col.length() - col.null_count)
    globally_null = sorted(c for c, nn in nonnull.items() if nn == 0)
    print(f'total rows={total}')
    print(f'globally-all-null columns to DROP: {globally_null}')
    if not globally_null:
        print('nothing to drop — exiting')
        return

    # archive whole dir first
    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(LIVE, ARCHIVE)
    print(f'archived -> {ARCHIVE}')

    # rewrite each file dropping the globally-null columns
    rewritten = 0
    for f in files:
        df = pd.read_parquet(f)
        drop = [c for c in globally_null if c in df.columns]
        if drop:
            df = df.drop(columns=drop)
        df.to_parquet(f, index=False)
        rewritten += 1
    print(f'rewrote {rewritten} files, dropped {globally_null}')

    # verify
    sample = pd.read_parquet(files[0])
    print(f'verify {files[0].name}: {len(sample.columns)} cols; '
          f"ebit present={'ebit' in sample.columns}, ebitda present={'ebitda' in sample.columns}")


if __name__ == '__main__':
    main()
