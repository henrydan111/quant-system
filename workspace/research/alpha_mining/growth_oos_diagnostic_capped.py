"""Growth-strategy OOS diagnostic: TopK=50 + sector caps (Path A1+A3 step 1).

Same recipe as before (gr_u5 universe + grow_opprofit_qoq + grow_roe_yoy
equal-weight rank composite) but applies a sector cap: max N positions per
Tushare industry. Tested on OOS window 2022-2025.

Sector cap implementation: instead of letting Qlib's TopkDropout strategy do
the selection, we PRE-FILTER the prediction scores to enforce sector caps,
then feed Qlib a "doctored" rank that the TopK selection will respect.
Approach: per rebalance day, take the top N*5 raw scores, walk down by score,
greedily admit each stock unless its industry is already at the cap, build the
allowed set, then synthesize a prediction column where (a) admitted stocks get
their original scores, (b) others get scores below all admitted stocks.
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
OUT_DIR = ROOT / "workspace" / "research" / "alpha_mining" / "growth_oos_diagnostic_topk50_sectorcap_20260424"
OUT_DIR.mkdir(parents=True, exist_ok=True)

OOS_START = "2022-01-01"
OOS_END = "2025-12-31"
BENCHMARK = "000905_SH"
TOPK = 50
N_DROP = 5
MAX_PER_SECTOR = 5  # 5 of 50 per sub-industry; 110 sub-industries → forces ≥10 distinct sectors


def build_industry_map() -> dict[str, str]:
    """Tushare ts_code -> industry (level-3 sub-industry, 110 distinct)."""
    df = pd.read_parquet(ROOT / "data" / "reference" / "stock_basic.parquet")
    sub = df[["ts_code", "industry"]].dropna(subset=["industry"])
    # Convert to qlib format and uppercase: 000001.SZ -> 000001_SZ
    sub = sub.copy()
    sub["qlib_code"] = sub["ts_code"].str.replace(".", "_", regex=False).str.upper()
    return dict(zip(sub["qlib_code"], sub["industry"]))


def apply_sector_cap(score: pd.Series, ind_map: dict[str, str], topk: int, max_per: int) -> pd.Series:
    """Per-day: greedy fill TopK respecting max_per per sector. Returns a
    re-ranked score series where admitted stocks get their original scores
    and rejected stocks get NaN (so Qlib TopK never picks them).

    Note on index structure: after groupby(level='datetime'), the per-day
    Series may either retain the MultiIndex or be flattened to instrument-only.
    Reset the index to canonical (datetime, instrument) before the per-day loop
    to avoid ambiguous tuple-unpacking bugs.
    """
    score_df = score.rename("score").to_frame()
    # Force canonical index naming and order
    score_df = score_df.reset_index()
    cols = score_df.columns.tolist()
    # Identify which columns hold datetime and instrument
    dt_col = next((c for c in cols if "datetime" in str(c).lower() or "date" in str(c).lower()), cols[0])
    inst_col = next((c for c in cols if "instrument" in str(c).lower() or "stock" in str(c).lower() or "ts_code" in str(c).lower()), cols[1])
    score_df = score_df.rename(columns={dt_col: "datetime", inst_col: "instrument"})

    out_rows: list[dict] = []
    for date, group in score_df.groupby("datetime"):
        ranked = group.dropna(subset=["score"]).sort_values("score", ascending=False)
        admitted: list[str] = []
        sector_count: dict[str, int] = {}
        for _, row in ranked.iterrows():
            instrument = row["instrument"]
            sector = ind_map.get(instrument, "_unknown")
            if sector_count.get(sector, 0) >= max_per:
                continue
            admitted.append(instrument)
            sector_count[sector] = sector_count.get(sector, 0) + 1
            if len(admitted) >= topk * 3:
                break
        admitted_set = set(admitted)
        for _, row in group.iterrows():
            if row["instrument"] in admitted_set:
                out_rows.append({"datetime": date, "instrument": row["instrument"], "score": row["score"]})
    out_df = pd.DataFrame(out_rows)
    return out_df.set_index(["datetime", "instrument"])["score"]


def main():
    qlib.init(provider_uri=QLIB_DIR, region="cn")

    # Universe: CSI500 + filters
    instruments_path = ROOT / "data" / "qlib_data" / "instruments" / "csi500.txt"
    with open(instruments_path, encoding="utf-8") as f:
        universe = sorted({line.split()[0].upper().strip() for line in f if line.strip()})
    logger.info(f"CSI500 universe size: {len(universe)}")

    # Factor signal
    expr_qop = op.fundamental("q_op_qoq")
    expr_roe = op.fundamental("roe_yoy")
    df = D.features(universe, [expr_qop, expr_roe], start_time=OOS_START, end_time=OOS_END, freq="day")
    df.columns = ["qop", "roe"]

    # Eligibility filters (3B mcap, 20M turnover, profitable)
    extras = D.features(universe, ["Ref($n_income_attr_p, 1)", "Ref($total_mv, 1)", "Ref($amount, 1)"],
                         start_time=OOS_START, end_time=OOS_END, freq="day")
    extras.columns = ["nip", "mv", "amt"]
    df = df.join(extras, how="left")
    eligible = (df["nip"] > 0) & (df["mv"] >= 300_000) & (df["amt"] >= 20_000)
    df.loc[~eligible, ["qop", "roe"]] = np.nan
    logger.info(f"Eligible obs: {eligible.sum()}/{len(eligible)}")

    # Cross-sectional rank, equal-weight
    grouped = df.groupby(level="datetime")
    score = (grouped["qop"].rank(pct=True) + grouped["roe"].rank(pct=True)) / 2.0
    score = score.dropna()
    logger.info(f"Pre-cap signal shape: {score.shape}")

    # Sector cap
    ind_map = build_industry_map()
    logger.info(f"Industry map covers {len(ind_map)} stocks")
    capped = apply_sector_cap(score, ind_map, topk=TOPK, max_per=MAX_PER_SECTOR)
    logger.info(f"Post-cap (admitted) obs: {(capped > -np.inf).sum()}")
    # Diagnostic: how concentrated would the natural top-50 be?
    score_reset = score.reset_index()
    dt_col = "datetime" if "datetime" in score_reset.columns else score_reset.columns[0]
    inst_col = "instrument" if "instrument" in score_reset.columns else score_reset.columns[1]
    score_reset = score_reset.rename(columns={dt_col: "datetime", inst_col: "instrument"})
    sample_dt = sorted(score_reset["datetime"].unique())[len(score_reset["datetime"].unique()) // 2]
    sample_day = score_reset[score_reset["datetime"] == sample_dt].nlargest(50, columns=score_reset.columns[-1])
    sectors = sample_day["instrument"].map(lambda i: ind_map.get(i, "?"))
    print(f"\n--- Sector concentration on sample date {sample_dt}, natural top-50 ---")
    print(sectors.value_counts().head(10).to_string())
    print(f"  distinct sectors: {sectors.nunique()}, max per sector: {sectors.value_counts().max()}\n")

    pred = capped.to_frame("score")
    # Replace -inf with NaN so Qlib TopK ignores them
    pred = pred.replace(-np.inf, np.nan).dropna()

    # Backtest
    bt = VectorizedBacktester(qlib_dir=QLIB_DIR)
    result = bt.run(
        predictions=pred,
        start_time=OOS_START, end_time=OOS_END, benchmark=BENCHMARK,
        account=2_000_000.0, topk=TOPK, n_drop=N_DROP,
        only_tradable=False, forbid_all_trade_at_limit=True,
        exchange_kwargs={
            "deal_price": "open",
            "open_cost": 0.0005, "close_cost": 0.0015, "min_cost": 5.0,
            "limit_threshold": 0.095, "trade_unit": 100,
        },
    )

    summary = result.summary if hasattr(result, "summary") else {}
    report = result.report if hasattr(result, "report") else None

    print("\n" + "=" * 60)
    print(f"OOS DIAGNOSTIC: TopK={TOPK} + sector cap (max {MAX_PER_SECTOR} per Tushare industry)")
    print(f"Window: {OOS_START} to {OOS_END}")
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


if __name__ == "__main__":
    main()
