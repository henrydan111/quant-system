# =====================================================================
# JoinQuant PIT cache refresh template
# =====================================================================
# Run this in JoinQuant cloud research (Python 3 kernel). It exports
# index_members + valuation + flags for the configured date range and
# writes parquet files matching the local cache layout:
#
#   data/external/jq_pit_cache/
#   ├── index_members/{INDEX}/{YYYY}.parquet     (long format: date, ts_code)
#   ├── valuation/{YYYY-MM}.parquet              (long format: date, ts_code, market_cap, ...)
#   └── flags/{YYYY-MM}.parquet                  (long format: date, ts_code, is_st, paused)
#
# Steps:
#   1. Edit CONFIG (INDICES, START_DATE, END_DATE).
#   2. Run all cells (~5-15 min depending on range).
#   3. Right-click each output parquet in the JQ file tree → download.
#   4. Copy into matching folder under data/external/jq_pit_cache/.
#   5. Locally: venv/Scripts/python.exe scripts/refresh_jq_pit_cache_manifest.py
#
# Refresh cadence: weekly for most strategies (index membership and
# valuation change slowly). Daily if you depend on is_st / paused.
# =====================================================================

# ----- CELL 1: imports + CONFIG ---------------------------------------
from jqdata import *
import pandas as pd
import datetime
import os

# Edit these for the date range you want to export. Default: last 30 days
# (incremental refresh). Use a 12-year range for a full backfill.
START_DATE = datetime.date(2026, 4, 22)
END_DATE   = datetime.date(2026, 5, 22)

# Indices to export membership for. Add/remove as needed.
INDICES = [
    '399101.XSHE',   # 中小综
    '000300.XSHG',   # HS300
    '000852.XSHG',   # ZZ1000
    # '000905.XSHG', # ZZ500   (uncomment if you use this index)
]

# Output dir inside JQ research (downloads happen file-by-file)
OUT_DIR = 'jq_pit_cache_export'
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(f'{OUT_DIR}/index_members', exist_ok=True)
os.makedirs(f'{OUT_DIR}/valuation', exist_ok=True)
os.makedirs(f'{OUT_DIR}/flags', exist_ok=True)

trade_days = [d for d in get_trade_days(start_date=START_DATE, end_date=END_DATE)]
print(f'Date range: {trade_days[0]} -> {trade_days[-1]}  ({len(trade_days)} trading days)')


# ----- CELL 2: index_members export -----------------------------------
def jq_to_tushare(code):
    return code.replace('.XSHE', '.SZ').replace('.XSHG', '.SH')

for idx in INDICES:
    rows = []
    for d in trade_days:
        try:
            members = get_index_stocks(idx, date=d)
        except Exception as e:
            print(f'  {idx} {d}: error {e}')
            continue
        for c in members:
            rows.append((d, jq_to_tushare(c)))
    df = pd.DataFrame(rows, columns=['date', 'ts_code'])
    if df.empty:
        print(f'{idx}: no rows'); continue
    # Partition by year
    df['_year'] = pd.to_datetime(df['date']).dt.year
    out_dir = f'{OUT_DIR}/index_members/{idx}'
    os.makedirs(out_dir, exist_ok=True)
    for yr, g in df.groupby('_year'):
        g.drop(columns=['_year']).to_parquet(f'{out_dir}/{yr}.parquet', index=False)
        print(f'  wrote {out_dir}/{yr}.parquet ({len(g):,} rows)')


# ----- CELL 3: valuation export (market_cap + secondary fields) -------
# Universe: union of all index_members rows in this batch (avoids
# exporting the whole A-share market). For broader coverage, change the
# universe to ``all_a = get_all_securities(['stock']).index.tolist()``.
def collect_universe():
    uni = set()
    for idx in INDICES:
        for d in trade_days:
            try:
                uni.update(get_index_stocks(idx, date=d))
            except Exception:
                pass
    return sorted(uni)

universe = collect_universe()
print(f'Valuation universe: {len(universe)} stocks')

for d in trade_days:
    q = (query(valuation.code, valuation.market_cap,
               valuation.circulating_market_cap, valuation.pe_ratio,
               valuation.pb_ratio)
         .filter(valuation.code.in_(universe)))
    df = get_fundamentals(q, date=d)
    if df.empty:
        continue
    df['date'] = pd.Timestamp(d).normalize()
    df['ts_code'] = df['code'].map(jq_to_tushare)
    df = df.rename(columns={
        'pe_ratio': 'pe',
        'pb_ratio': 'pb',
    })[['date', 'ts_code', 'market_cap', 'circulating_market_cap', 'pe', 'pb']]
    ym = f'{d.year:04d}-{d.month:02d}'
    out = f'{OUT_DIR}/valuation/{ym}.parquet'
    if os.path.exists(out):
        prev = pd.read_parquet(out)
        df = pd.concat([prev[prev['date'] != pd.Timestamp(d).normalize()], df],
                       ignore_index=True)
    df.to_parquet(out, index=False)
print('Wrote valuation parquet files (one per YYYY-MM).')


# ----- CELL 4: flags export (is_st, paused) ---------------------------
# Uses get_extras for is_st (date-axis) and the daily get_current_data
# is_paused query — but get_current_data only works at backtest's
# current_dt. For historical batches, derive paused from price.paused via
# get_price.
for d in trade_days:
    # is_st: get_extras returns a DataFrame indexed by date with ts_codes as cols
    st_df = get_extras('is_st', universe, end_date=d, count=1)
    if st_df.empty:
        continue
    row_st = st_df.iloc[-1]  # latest row = date d
    # paused: from get_price (paused field)
    pr = get_price(universe, end_date=d, count=1, frequency='daily',
                   fields=['paused'], panel=False, fill_paused=False)
    pr['date'] = pd.Timestamp(d).normalize()
    pr['ts_code'] = pr['code'].map(jq_to_tushare)
    pr = pr[['date', 'ts_code', 'paused']]
    # Merge is_st onto pr
    st_long = pd.DataFrame({
        'ts_code': [jq_to_tushare(c) for c in row_st.index],
        'is_st':   row_st.values.astype(bool),
    })
    out_df = pr.merge(st_long, on='ts_code', how='left')
    out_df['is_st'] = out_df['is_st'].fillna(False)
    ym = f'{d.year:04d}-{d.month:02d}'
    out_path = f'{OUT_DIR}/flags/{ym}.parquet'
    if os.path.exists(out_path):
        prev = pd.read_parquet(out_path)
        out_df = pd.concat([prev[prev['date'] != pd.Timestamp(d).normalize()], out_df],
                           ignore_index=True)
    out_df.to_parquet(out_path, index=False)
print('Wrote flags parquet files (one per YYYY-MM).')

# ----- CELL 5: summary + download instructions ------------------------
print(f'\nExport complete. Files in {OUT_DIR}/')
for root, _, files in os.walk(OUT_DIR):
    for f in files:
        full = os.path.join(root, f)
        sz = os.path.getsize(full) / 1024
        print(f'  {full}  ({sz:.1f} KB)')

print('\nDownload each file via the JQ research file-tree (right-click → 下载).')
print('Then on local: copy into the matching folder under data/external/jq_pit_cache/,')
print('and run:  venv/Scripts/python.exe scripts/refresh_jq_pit_cache_manifest.py')
