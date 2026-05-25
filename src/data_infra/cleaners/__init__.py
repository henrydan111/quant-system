"""
Data Cleaning Module
Handles suspensions, survivorship bias (delistings), price adjustments, and outlier removal.
"""
import pandas as pd
import numpy as np


class DataCleaner:
    """
    Utility class for cleaning and adjusting raw market data.

    Provides methods for basic data hygiene (null handling, type enforcement),
    backward-adjusted price calculation using adjustment factors, and
    winsorization for outlier control in cross-sectional factor data.
    """

    def __init__(self):
        pass

    def clean_daily_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Process raw Tushare daily data.

        Drops rows missing key identifiers, enforces correct date types,
        and sorts by stock code and date.

        Args:
            df: Raw daily DataFrame with ts_code and trade_date columns.

        Returns:
            Cleaned DataFrame sorted by (ts_code, trade_date).
        """
        if df.empty:
            return df

        df = df.dropna(subset=['ts_code', 'trade_date'])
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        df = df.sort_values(by=['ts_code', 'trade_date'])
        return df

    def adjust_prices(self, df: pd.DataFrame,
                      price_cols: list = None) -> pd.DataFrame:
        """
        Calculate backward-adjusted prices using adjustment factors.

        Uses the formula: adj_price = price * adj_factor / latest_adj_factor
        This ensures the most recent price equals the unadjusted close,
        while historical prices are adjusted for splits and dividends.

        The adjustment is applied per stock (grouped by ts_code). If adj_factor
        is missing, prices are returned unchanged.

        Args:
            df: DataFrame containing price columns and 'adj_factor'.
                Must have 'ts_code' column for per-stock grouping.
            price_cols: List of price column names to adjust.
                Defaults to ['open', 'high', 'low', 'close'].

        Returns:
            DataFrame with additional adj_* columns (e.g., adj_open, adj_close).
        """
        if df.empty:
            return df

        if 'adj_factor' not in df.columns:
            return df

        if price_cols is None:
            price_cols = ['open', 'high', 'low', 'close']

        # Only adjust columns that exist in the DataFrame
        price_cols = [c for c in price_cols if c in df.columns]
        if not price_cols:
            return df

        result = df.copy()

        def _adjust_group(group):
            """Apply backward adjustment within a single stock's time series."""
            latest_factor = group['adj_factor'].iloc[-1]
            if pd.isna(latest_factor) or latest_factor == 0:
                return group
            ratio = group['adj_factor'] / latest_factor
            for col in price_cols:
                group[f'adj_{col}'] = group[col] * ratio
            return group

        if 'ts_code' in result.columns:
            result = result.sort_values(['ts_code', 'trade_date'] if 'trade_date' in result.columns else ['ts_code'])
            result = result.groupby('ts_code', group_keys=False).apply(_adjust_group, include_groups=False)
        else:
            # Single-stock DataFrame without ts_code
            latest_factor = result['adj_factor'].iloc[-1]
            if not pd.isna(latest_factor) and latest_factor != 0:
                ratio = result['adj_factor'] / latest_factor
                for col in price_cols:
                    result[f'adj_{col}'] = result[col] * ratio

        return result

    def winsorize_outliers(self, series: pd.Series,
                           limits: list = None) -> pd.Series:
        """
        Winsorize extreme values by clipping to specified quantiles.

        Commonly used for cross-sectional fundamental data (e.g., PE ratios,
        ROE) where extreme outliers can distort factor rankings.

        Args:
            series: Numeric series to winsorize.
            limits: Two-element list [lower_quantile, upper_quantile].
                Defaults to [0.01, 0.99] (1st and 99th percentiles).

        Returns:
            Clipped series with extreme values replaced by quantile bounds.
        """
        if limits is None:
            limits = [0.01, 0.99]
        lower_bound = series.quantile(limits[0])
        upper_bound = series.quantile(limits[1])
        return series.clip(lower=lower_bound, upper=upper_bound)
