"""Growth-strategy OOS diagnostic: 3-leg signal with industry-relative B/P.

Composite = equal-weight rank average of:
  (1) grow_opprofit_qoq           — fundamental QoQ profit growth
  (2) grow_roe_yoy                — fundamental YoY ROE growth
  (3) val_bp_industry_rel         — Shenwan L1 industry-mean-subtract B/P
                                    (B-grade signal, +0.378 ICIR per latest screen)

Universe: gr_u5 (CSI500 mainboard, profitable, mcap≥3B, liquidity≥20M)
TopK=50, Reb=10d (no sector cap — Step 1 showed caps hurt without DD benefit)
Window: OOS 2022-01-01 to 2025-12-31

Question: does adding val_bp_industry_rel as a third leg improve excess
return / IR / DD vs the 2-leg TopK=50 baseline?

Baselines for comparison:
  TopK=50 2-leg, no cap: DD -35.7%, IR 0.79, excess +8.2%, total +39.3%
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
from src.alpha_research.factor_library import (
    add_industry_relative_composites,
    get_industry_relative_defs,
)
from src.data_infra.provider_metadata import build_industry_series_asof

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[3]
QLIB_DIR = str(ROOT / "data" / "qlib_data")
OUT_DIR = ROOT / "workspace" / "research" / "alpha_mining" / "growth_oos_diagnostic_3leg_20260427"
OUT_DIR.mkdir(parents=True, exist_ok=True)

OOS_START = "2022-01-01"
OOS_END = "2025-12-31"
BENCHMARK = "000905_SH"
TOPK = 50
N_DROP = 5


def main():
    qlib.init(provider_uri=QLIB_DIR, region="cn")

    instruments_path = ROOT / "data" / "qlib_data" / "instruments" / "csi500.txt"
    with open(instruments_path, encoding="utf-8") as f:
        universe = sorted({line.split()[0].upper().strip() for line in f if line.strip()})
    logger.info(f"CSI500 universe size: {len(universe)}")

    # Three base factors
    expr_qop = op.fundamental("q_op_qoq")
    expr_roe = op.fundamental("roe_yoy")
    expr_bp = op.book_yield()  # 1.0 / Ref($pb, 1)
    df = D.features(
        universe,
        [expr_qop, expr_roe, expr_bp],
        start_time=OOS_START, end_time=OOS_END, freq="day",
    )
    df.columns = ["grow_opprofit_qoq", "grow_roe_yoy", "val_bp"]

    # Eligibility extras
    extras = D.features(
        universe,
        ["Ref($n_income_attr_p, 1)", "Ref($total_mv, 1)", "Ref($amount, 1)"],
        start_time=OOS_START, end_time=OOS_END, freq="day",
    )
    extras.columns = ["nip", "mv", "amt"]
    df = df.join(extras, how="left")
    eligible = (df["nip"] > 0) & (df["mv"] >= 300_000) & (df["amt"] >= 20_000)
    df.loc[~eligible, ["grow_opprofit_qoq", "grow_roe_yoy", "val_bp"]] = np.nan
    logger.info(f"Eligible obs: {eligible.sum()}/{len(eligible)}")

    # Add val_bp_industry_rel using the new helper
    industry_series = build_industry_series_asof(df.index, level="L1")
    logger.info(f"L1 coverage: {100 * industry_series.notna().mean():.2f}%")
    bp_def = [d for d in get_industry_relative_defs() if d["name"] == "val_bp_industry_rel"]
    df = add_industry_relative_composites(df, industry_series=industry_series, defs=bp_def)
    logger.info(f"Post-industry-relative columns: {df.columns.tolist()}")
    logger.info(f"val_bp_industry_rel non-null: {df['val_bp_industry_rel'].notna().sum()}/{len(df)}")

    # 3-leg equal-weight rank composite
    grouped = df.groupby(level="datetime")
    rank_qop = grouped["grow_opprofit_qoq"].rank(pct=True)
    rank_roe = grouped["grow_roe_yoy"].rank(pct=True)
    rank_bp_rel = grouped["val_bp_industry_rel"].rank(pct=True)
    score = (rank_qop + rank_roe + rank_bp_rel) / 3.0
    score = score.dropna()
    logger.info(f"3-leg signal shape: {score.shape}")

    # Backtest
    pred = score.to_frame("score")
    bt = VectorizedBacktester(qlib_dir=QLIB_DIR)
    result = bt.run(
        predictions=pred, start_time=OOS_START, end_time=OOS_END, benchmark=BENCHMARK,
        account=2_000_000.0, topk=TOPK, n_drop=N_DROP,
        only_tradable=False, forbid_all_trade_at_limit=True,
        exchange_kwargs={"deal_price": "open", "open_cost": 0.0005, "close_cost": 0.0015,
                         "min_cost": 5.0, "limit_threshold": 0.095, "trade_unit": 100},
    )
    summary = result.summary if hasattr(result, "summary") else {}
    report = result.report if hasattr(result, "report") else None
    print("\n" + "=" * 60)
    print(f"OOS DIAGNOSTIC: 3-leg = (qop + roe_yoy + bp_industry_rel) / 3")
    print(f"Window: {OOS_START} to {OOS_END} | TopK={TOPK} | Reb≈10d")
    print("=" * 60)
    if isinstance(summary, dict):
        for k, v in summary.items():
            print(f"  {k:30s} {v}")
    if report is not None and not report.empty:
        equity = report.get("account") if "account" in report.columns else report.get("value")
        if equity is not None:
            running_max = equity.cummax()
            dd = (equity - running_max) / running_max
            print(f"\n  computed_max_drawdown          {float(dd.min()):.4f}")
            print(f"  total_return                   {float(equity.iloc[-1]/equity.iloc[0] - 1):.4f}")
        report.to_csv(OUT_DIR / "oos_report.csv")
    print(f"\nArtifacts in {OUT_DIR}")
    print("\n--- Baselines for comparison ---")
    print("  TopK=50 2-leg (qop+roe_yoy): DD -35.7%  IR 0.79  excess +8.2%  total +39.3%")
    print("  TopK=20 2-leg              : DD -42.0%  IR 0.76  excess +11.5% total +55.6%")


if __name__ == "__main__":
    main()
