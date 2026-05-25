"""Growth-strategy OOS diagnostic (Path B, plan jolly-seeking-lollipop).

Runs the same recipe Hyp A/B selected (gr_u5 universe + grow_opprofit_qoq +
grow_roe_yoy, TopK=20, Reb=10, equal-weight rank composite) on the OOS window
2022-01-01 to 2025-12-31 using the vectorized backtester. Sandbox mode — does
NOT touch the formal holdout seal so the seal remains available for a future
redesigned hypothesis (Path A).

Question being answered: does the -59.8% IS max_drawdown reflect a
structural risk profile of the strategy, or was it a 2018-bear-specific tail
that won't recur in 2022-2025?
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

import qlib
from qlib.data import D

from src.backtest_engine.vectorized import VectorizedBacktester
from src.alpha_research.factor_library import operators as op

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[3]
QLIB_DIR = str(ROOT / "data" / "qlib_data")
OUT_DIR = ROOT / "workspace" / "research" / "alpha_mining" / "growth_oos_diagnostic_topk50_20260424"
OUT_DIR.mkdir(parents=True, exist_ok=True)

OOS_START = "2022-01-01"
OOS_END = "2025-12-31"
BENCHMARK = "000905_SH"  # CSI 500
TOPK = 50
N_DROP = 5  # 5 of 50 turnover per rebalance ≈ 10-day cycle for 50 holdings


def build_gr_u5_universe() -> set[str]:
    """gr_u5 universe candidate from registry.py:
    - membership_source = csi500
    - board_policy = mainboard
    - st_mode = exclude
    - min_listing_days = 250
    - market_cap_min = 3,000,000,000 (3B)
    - profitability_field = n_income_attr_p, profitability_positive=True
    - liquidity_floor = 20,000,000 (20M daily turnover)
    Approximation: use CSI500 instruments + filter on positive profit + mcap >= 3B.
    """
    instruments_path = ROOT / "data" / "qlib_data" / "instruments" / "csi500.txt"
    if not instruments_path.exists():
        # Fall back to all
        with open(ROOT / "data" / "qlib_data" / "instruments" / "all_stocks.txt", encoding="utf-8") as f:
            stocks = {line.split()[0].upper().strip() for line in f if line.strip()}
        logger.warning(f"csi500.txt not found, using all_stocks ({len(stocks)})")
        return stocks
    with open(instruments_path, encoding="utf-8") as f:
        stocks = {line.split()[0].upper().strip() for line in f if line.strip()}
    logger.info(f"CSI500 universe size: {len(stocks)}")
    return stocks


def main():
    # ── Init Qlib ──────────────────────────────────────────────────────
    qlib.init(provider_uri=QLIB_DIR, region="cn")

    # ── Build universe ─────────────────────────────────────────────────
    universe = build_gr_u5_universe()

    # ── Compute composite signal ───────────────────────────────────────
    # auto_growth_19 = (grow_opprofit_qoq + grow_roe_yoy) / 2 in rank space
    # In Qlib expression terms: equal-weight average of the two factors
    # Both factors use Ref(..., 1) PIT shift via op.fundamental
    expr_qop = op.fundamental("q_op_qoq")        # grow_opprofit_qoq
    expr_roe = op.fundamental("roe_yoy")          # grow_roe_yoy
    fields = [expr_qop, expr_roe]
    field_names = ["grow_opprofit_qoq", "grow_roe_yoy"]

    logger.info(f"Loading factor data for {len(universe)} stocks, {OOS_START} to {OOS_END}...")
    df = D.features(
        sorted(universe),
        fields,
        start_time=OOS_START,
        end_time=OOS_END,
        freq="day",
    )
    df.columns = field_names
    logger.info(f"Loaded shape={df.shape}, non-null counts: {df.notna().sum().to_dict()}")

    # ── Apply universe-level filters at signal layer ──────────────────
    # Profitability filter: need n_income_attr_p > 0
    # Market cap filter: total_mv >= 3B
    extras = D.features(
        sorted(universe),
        ["Ref($n_income_attr_p, 1)", "Ref($total_mv, 1)", "Ref($amount, 1)"],
        start_time=OOS_START,
        end_time=OOS_END,
        freq="day",
    )
    extras.columns = ["n_income_attr_p", "total_mv", "amount"]
    df = df.join(extras, how="left")

    # Eligibility mask
    # NOTE units: total_mv is in 10,000 CNY (万元); amount is in 1,000 CNY (千元)
    # 3B CNY mcap threshold = 300,000 in 万元; 20M CNY turnover = 20,000 in 千元
    eligible = (
        (df["n_income_attr_p"] > 0)
        & (df["total_mv"] >= 300_000)
        & (df["amount"] >= 20_000)
    )
    df.loc[~eligible, ["grow_opprofit_qoq", "grow_roe_yoy"]] = np.nan
    logger.info(f"Eligible obs after universe filters: {eligible.sum()}/{len(eligible)}")

    # ── Cross-sectional rank, then equal-weight average ───────────────
    grouped = df.groupby(level="datetime")
    rank_qop = grouped["grow_opprofit_qoq"].rank(pct=True)
    rank_roe = grouped["grow_roe_yoy"].rank(pct=True)
    composite = (rank_qop + rank_roe) / 2.0

    # ── Run vectorized backtest ───────────────────────────────────────
    pred = composite.to_frame("score")
    pred = pred.dropna()
    logger.info(f"Composite signal shape after dropna: {pred.shape}")

    bt = VectorizedBacktester(qlib_dir=QLIB_DIR)
    result = bt.run(
        predictions=pred,
        start_time=OOS_START,
        end_time=OOS_END,
        benchmark=BENCHMARK,
        account=2_000_000.0,
        topk=TOPK,
        n_drop=N_DROP,
        only_tradable=False,
        forbid_all_trade_at_limit=True,
        exchange_kwargs={
            "deal_price": "open",
            "open_cost": 0.0005,    # 5bps
            "close_cost": 0.0015,   # 5bps + 0.1% stamp tax
            "min_cost": 5.0,
            "limit_threshold": 0.095,
            "trade_unit": 100,
        },
    )

    # ── Report ─────────────────────────────────────────────────────────
    summary = result.summary if hasattr(result, "summary") else {}
    report = result.report if hasattr(result, "report") else None

    print("\n" + "=" * 60)
    print(f"OOS DIAGNOSTIC: gr_u5 + (grow_opprofit_qoq + grow_roe_yoy)/2")
    print(f"Window: {OOS_START} to {OOS_END} | TopK={TOPK} | Drop={N_DROP}")
    print("=" * 60)
    if isinstance(summary, dict):
        for k, v in summary.items():
            print(f"  {k:30s} {v}")

    if report is not None and not report.empty:
        # Compute drawdown directly
        if "account" in report.columns:
            equity = report["account"]
        elif "value" in report.columns:
            equity = report["value"]
        else:
            equity = None

        if equity is not None:
            running_max = equity.cummax()
            dd = (equity - running_max) / running_max
            max_dd = float(dd.min())
            print(f"\n  computed_max_drawdown          {max_dd:.4f}")
            print(f"  final_equity                   {float(equity.iloc[-1]):.2f}")
            print(f"  start_equity                   {float(equity.iloc[0]):.2f}")
            print(f"  total_return                   {float(equity.iloc[-1] / equity.iloc[0] - 1):.4f}")

        report.to_csv(OUT_DIR / "oos_report.csv")
        print(f"\nReport saved to {OUT_DIR / 'oos_report.csv'}")

    if hasattr(result, "indicators") and result.indicators is not None:
        result.indicators.to_csv(OUT_DIR / "oos_indicators.csv")

    print(f"\nArtifacts in {OUT_DIR}")


if __name__ == "__main__":
    main()
