"""A1 fix: re-fetch stock_basic WITH act_name/act_ent_type (default-显示=Y fields
previously omitted by the hardcoded field whitelist). Backs up the existing file,
verifies the 2 new columns are present + populated, then overwrites.
"""
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(r'E:\量化系统')
sys.path.insert(0, str(ROOT / 'src'))
from data_infra.fetchers import TushareFetcher  # noqa: E402

TARGET = ROOT / 'data' / 'reference' / 'stock_basic.parquet'
NEW_COLS = ['act_name', 'act_ent_type']


def main():
    old = pd.read_parquet(TARGET) if TARGET.exists() else None
    old_n = len(old) if old is not None else 0
    old_cols = set(old.columns) if old is not None else set()
    print(f'existing stock_basic: {old_n} rows, {len(old_cols)} cols, '
          f'has new cols={[c for c in NEW_COLS if c in old_cols]}')

    fetcher = TushareFetcher(config_path=str(ROOT / 'config.yaml'))
    df = fetcher.fetch_stock_basic()
    if df is None or df.empty:
        print('FATAL: fetch returned empty — aborting, file untouched')
        sys.exit(1)
    print(f'fetched: {len(df)} rows, cols={list(df.columns)}')

    missing = [c for c in NEW_COLS if c not in df.columns]
    if missing:
        print(f'FATAL: new cols still missing from fetch: {missing} — aborting')
        sys.exit(1)
    for c in NEW_COLS:
        nn = int(df[c].notna().sum())
        print(f'  {c}: non-null {nn}/{len(df)} ({nn/len(df)*100:.1f}%)')

    # guard: don't shrink the universe (delisted+listed should be >= prior count)
    if old_n and len(df) < old_n * 0.95:
        print(f'FATAL: new row count {len(df)} < 95% of old {old_n} — aborting (suspicious)')
        sys.exit(1)

    if TARGET.exists():
        bak = TARGET.with_suffix(f'.parquet.bak_{datetime.now():%Y%m%d_%H%M%S}')
        shutil.copy2(TARGET, bak)
        print(f'backed up -> {bak.name}')
    df.to_parquet(TARGET, index=False)
    print(f'WROTE {TARGET} ({len(df)} rows, {len(df.columns)} cols)')


if __name__ == '__main__':
    main()
