"""
JoinQuant Research Environment — Data Verification Script

Run this in JQ's RESEARCH environment (Jupyter notebook), NOT as a backtest.
It dumps PE_TTM, market_cap, close, volume for all CSI300 main-board stocks
on 3 sample dates so we can compare with local Tushare/Qlib data.

Copy-paste into a JQ research notebook cell and run.
"""

from jqdata import *
import pandas as pd
import numpy as np

# ═══════════════════════════════════════════════════════════
# CONFIG — 3 sample dates spread across 2024
# ═══════════════════════════════════════════════════════════
SAMPLE_DATES = ['2023-12-29', '2024-04-30', '2024-09-30']

all_records = []

for sample_date in SAMPLE_DATES:
    sample_date_dt = pd.Timestamp(sample_date)
    
    # Get CSI300 constituents on this date
    csi300 = get_index_stocks('000300.XSHG', date=sample_date)
    
    # Filter: main board only
    main_board = [
        s for s in csi300
        if s[:3] not in ('300', '301', '688', '689')
        and s[0] not in ('8', '4', '9')
    ]
    
    # Get valuation data (PIT-correct)
    q = query(
        valuation.code,
        valuation.market_cap,      # 总市值 (亿元)
        valuation.pe_ratio,        # PE TTM
        valuation.pb_ratio,        # PB
        valuation.turnover_ratio,  # 换手率
    ).filter(
        valuation.code.in_(main_board),
    )
    val_df = get_fundamentals(q, date=sample_date)
    
    # Get close price and volume
    price_df = get_price(
        main_board,
        end_date=sample_date,
        frequency='daily',
        fields=['close', 'volume', 'open', 'high', 'low', 'pre_close'],
        count=1,
        panel=False,
    )
    
    # Get 20-day price history for momentum
    hist_df = get_price(
        main_board,
        end_date=sample_date,
        frequency='daily',
        fields=['close'],
        count=21,
        panel=False,
    )
    
    # Compute 20d return per stock
    mom_dict = {}
    for code in main_board:
        stock_hist = hist_df[hist_df['code'] == code]['close'].values
        if len(stock_hist) >= 21 and stock_hist[0] > 0:
            mom_dict[code] = stock_hist[-1] / stock_hist[0] - 1
    
    # Merge
    for _, vrow in val_df.iterrows():
        code = vrow['code']
        px = price_df[price_df['code'] == code]
        
        close = px['close'].values[0] if len(px) > 0 else np.nan
        volume = px['volume'].values[0] if len(px) > 0 else np.nan
        open_ = px['open'].values[0] if len(px) > 0 else np.nan
        high = px['high'].values[0] if len(px) > 0 else np.nan
        low = px['low'].values[0] if len(px) > 0 else np.nan
        pre_close = px['pre_close'].values[0] if len(px) > 0 else np.nan
        
        # Convert JQ code to Tushare format: 600741.XSHG -> 600741.SH
        ts_code = code.replace('.XSHG', '.SH').replace('.XSHE', '.SZ')
        
        all_records.append({
            'date': sample_date,
            'code': ts_code,
            'close': round(close, 4) if not np.isnan(close) else np.nan,
            'open': round(open_, 4) if not np.isnan(open_) else np.nan,
            'high': round(high, 4) if not np.isnan(high) else np.nan,
            'low': round(low, 4) if not np.isnan(low) else np.nan,
            'pre_close': round(pre_close, 4) if not np.isnan(pre_close) else np.nan,
            'volume': volume,
            'pe_ttm': round(vrow['pe_ratio'], 4) if not pd.isna(vrow['pe_ratio']) else np.nan,
            'market_cap_yi': round(vrow['market_cap'], 4) if not pd.isna(vrow['market_cap']) else np.nan,
            'pb': round(vrow['pb_ratio'], 4) if not pd.isna(vrow['pb_ratio']) else np.nan,
            'turnover': round(vrow['turnover_ratio'], 4) if not pd.isna(vrow['turnover_ratio']) else np.nan,
            'mom_20d': round(mom_dict.get(code, np.nan), 6),
        })

result_df = pd.DataFrame(all_records)
print(f"Total rows: {len(result_df)}")
print(f"Dates: {sorted(result_df['date'].unique())}")
print(f"Stocks per date: {result_df.groupby('date').size().to_dict()}")
print()
print("Sample (first 5 per date):")
print(result_df.groupby('date').head(5).to_string(index=False))

# Save to CSV — download this file and provide it
result_df.to_csv('jq_factor_dump.csv', index=False)
print("\n✅ Saved to jq_factor_dump.csv — please download and provide this file")
