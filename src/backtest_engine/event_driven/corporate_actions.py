"""
Corporate Action Handler for Event-Driven Backtester

Processes cash dividends and bonus shares on ex-dates.
Uses stk_div as the authoritative total bonus per share (verified:
stk_div = stk_bo_rate + stk_co_rate in 4153/4153 rows).

Data source: data/corporate/dividends/dividends_{year}.parquet
(20 files, partitioned by end_date year: 2007-2026)
Only rows with div_proc='实施' and non-null ex_date are actionable.
"""

import os
import logging
from collections import defaultdict

import pandas as pd

logger = logging.getLogger(__name__)


class CorporateActionHandler:
    """Processes cash dividends and bonus shares on ex-dates.

    On each trading day, checks if any held stocks have a corporate
    action on that date. If so:
    1. Credits cash (cash_div_tax * shares) to portfolio
    2. Adds bonus shares (stk_div * shares) to position

    All values are per-share (NOT per-10-shares, despite Tushare docs).

    Args:
        dividends_dir: Path to dividends directory containing yearly
            parquet files (e.g., data/corporate/dividends/).
    """

    def __init__(self, dividends_dir: str):
        self.dividends_dir = dividends_dir
        # Keyed by ex_date string 'YYYYMMDD' -> list of action dicts
        self.by_date: dict[str, list[dict]] = defaultdict(list)
        # Log of all corporate actions applied
        self.action_log: list[dict] = []
        self._load_all()

    def _load_all(self) -> None:
        """Load all dividend files and index implemented actions by ex_date."""
        if not os.path.isdir(self.dividends_dir):
            logger.warning('Dividends directory not found: %s',
                          self.dividends_dir)
            return

        total = 0
        dropped_null_ex_date = 0  # P1-5: observability for the silent drop
        for f in sorted(os.listdir(self.dividends_dir)):
            if not f.endswith('.parquet'):
                continue
            path = os.path.join(self.dividends_dir, f)
            df = pd.read_parquet(path)

            # P1-5: detect rows with div_proc='实施' (implemented) but missing
            # ex_date. These are silently dropped below — the WARNING log makes
            # the drop observable. Pre-implementation states (预案, 股东大会通过)
            # with null ex_date are expected and not flagged.
            implemented_null_ex_date = df[
                (df['div_proc'] == '实施') & df['ex_date'].isna()
            ]
            if not implemented_null_ex_date.empty:
                dropped_null_ex_date += len(implemented_null_ex_date)
                sample = implemented_null_ex_date.head(3)[['ts_code', 'ann_date', 'end_date']]
                logger.warning(
                    "Dropping %d implemented dividend rows with null ex_date in %s. "
                    "Sample: %s. These will not be credited to any portfolio.",
                    len(implemented_null_ex_date),
                    f,
                    sample.to_dict('records'),
                )

            # Filter to implemented actions with ex_date
            impl = df[
                (df['div_proc'] == '实施') &
                df['ex_date'].notna()
            ].copy()

            for _, row in impl.iterrows():
                action = {
                    'ts_code': row['ts_code'],
                    'ex_date': row['ex_date'],  # YYYYMMDD string
                    'cash_div': row.get('cash_div', 0) or 0,
                    'cash_div_tax': row.get('cash_div_tax', 0) or 0,
                    'stk_div': row.get('stk_div', 0) or 0,
                    'stk_bo_rate': row.get('stk_bo_rate', 0) or 0,
                    'stk_co_rate': row.get('stk_co_rate', 0) or 0,
                }
                # Use cash_div_tax (post-tax) for actual credit
                if action['cash_div_tax'] > 0 or action['stk_div'] > 0:
                    self.by_date[row['ex_date']].append(action)
                    total += 1

        logger.info(
            'Loaded %d implemented corporate actions across %d ex-dates '
            '(silently dropped %d 实施-rows with null ex_date)',
            total, len(self.by_date), dropped_null_ex_date,
        )

    def process(self, date: pd.Timestamp, portfolio) -> None:
        """Process corporate actions for the given date.

        Called at the start of each trading day, BEFORE any trading.

        Args:
            date: Current trading date.
            portfolio: Portfolio instance to modify.
        """
        date_str = date.strftime('%Y%m%d')
        actions = self.by_date.get(date_str, [])
        if not actions:
            return

        for action in actions:
            code = action['ts_code']
            pos = portfolio.get_position(code)
            if pos is None:
                continue  # Not holding this stock

            # 1. Cash dividend (post-tax)
            tax_div = action['cash_div_tax']
            if tax_div > 0:
                dividend_cash = tax_div * pos.shares
                portfolio.credit_cash(dividend_cash)
                self.action_log.append({
                    'date': date,
                    'code': code,
                    'type': 'cash_dividend',
                    'per_share': tax_div,
                    'shares': pos.shares,
                    'total': dividend_cash,
                })
                logger.info(
                    'Cash dividend: %s ex=%s, %.4f/share x %d = %.2f',
                    code, date_str, tax_div, pos.shares, dividend_cash
                )

            # 2. Bonus shares (送股 + 转增股)
            # stk_div = total bonus per share
            #   = stk_bo_rate (送股 from earnings) + stk_co_rate (转增 from capital)
            # Verified: stk_div == stk_bo_rate + stk_co_rate in 4153/4153 rows
            bonus_rate = action['stk_div']
            if bonus_rate > 0:
                new_shares = int(pos.shares * bonus_rate)
                if new_shares > 0:
                    pos.shares += new_shares
                    pos.closeable_amount += new_shares  # Bonus immediately available
                    # Adjust avg_cost: total investment unchanged, more shares
                    pos.avg_cost = pos.avg_cost / (1 + bonus_rate)
                    self.action_log.append({
                        'date': date,
                        'code': code,
                        'type': 'bonus_shares',
                        'rate': bonus_rate,
                        'old_shares': pos.shares - new_shares,
                        'new_shares': new_shares,
                        'total_shares': pos.shares,
                    })
                    logger.info(
                        'Bonus shares: %s ex=%s, rate=%.4f, +%d shares '
                        '(new total: %d)',
                        code, date_str, bonus_rate, new_shares, pos.shares
                    )
