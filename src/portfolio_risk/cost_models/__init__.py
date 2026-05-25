"""
Transaction Cost Models
Models slippage, market impact and commission.
"""
import numpy as np

class MarketImpactModel:
    def __init__(self, commission_rate=0.0003, stamp_duty=0.001):
        self.commission_rate = commission_rate
        self.stamp_duty = stamp_duty

    def estimate_cost(self, trade_amount: np.ndarray, adv: np.ndarray = None) -> np.ndarray:
        """
        Estimate transaction costs including:
        - Fixed commission and stamp duty
        - Spread / Slippage
        - Market impact (e.g. Almgren-Chriss power model)
        """
        # Basic flat rate cost
        base_cost = np.abs(trade_amount) * (self.commission_rate + self.stamp_duty / 2.0)
        
        # If ADV (Average Daily Volume) is provided, add convex market impact penalty
        if adv is not None:
            participation_rate = np.abs(trade_amount) / (adv + 1e-5)
            # Market impact scales non-linearly with participation rate, e.g. root square
            market_impact = np.abs(trade_amount) * 0.1 * np.sqrt(participation_rate)
            return base_cost + market_impact
            
        return base_cost
