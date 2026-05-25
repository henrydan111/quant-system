"""Growth-strategy OOS diagnostic: TopK=50 + Shenwan L1 sector cap.

Uses the new (2026-04-27) SW2021 stock-to-industry membership data via
``provider_metadata.build_industry_series_asof`` for time-varying L1
industry labels. With 28 L1 buckets and TopK=50, max_per=5 forces ≥10
distinct L1 industries — meaningful diversification rather than the
no-effect Tushare-sub-industry caps tested earlier.
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
from src.data_infra.provider_metadata import build_industry_series_asof

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[3]
QLIB_DIR = str(ROOT / "data" / "qlib_data")
OUT_DIR = ROOT / "workspace" / "research" / "alpha_mining" / "growth_oos_diagnostic_l1cap_20260427"
OUT_DIR.mkdir(parents=True, exist_ok=True)

OOS_START = "2022-01-01"
OOS_END = "2025-12-31"
BENCHMARK = "000905_SH"
TOPK = 50
N_DROP = 5
MAX_PER_L1 = 5  # 5 of 50 per Shenwan L1; 28 L1s → forces ≥10 distinct sectors


def apply_l1_sector_cap(score: pd.Series, l1_series: pd.Series, topk: int, max_per: int) -> pd.Series:
    """Per-day greedy fill respecting max_per per L1 sector. Returns a
    score series where rejected stocks are dropped (Qlib TopK then picks
    naturally from the remaining)."""
    df = pd.DataFrame({"score": score, "l1": l1_series}).reset_index()
    cols = df.columns.tolist()
    dt_col = next((c for c in cols if "datetime" in str(c).lower() or "date" in str(c).lower()), cols[0])
    inst_col = next((c for c in cols if "instrument" in str(c).lower() or "ts_code" in str(c).lower()), cols[1])
    df = df.rename(columns={dt_col: "datetime", inst_col: "instrument"})

    keep_rows: list[dict] = []
    cap_binding_days = 0
    for date, group in df.groupby("datetime"):
        ranked = group.dropna(subset=["score"]).sort_values("score", ascending=False)
        admitted_count = 0
        l1_count: dict[str, int] = {}
        rejected_due_to_cap = 0
        for _, row in ranked.iterrows():
            l1 = row["l1"] if pd.notna(row["l1"]) else "_unknown"
            if l1_count.get(l1, 0) >= max_per:
                rejected_due_to_cap += 1
                continue
            keep_rows.append({"datetime": date, "instrument": row["instrument"], "score": row["score"]})
            l1_count[l1] = l1_count.get(l1, 0) + 1
            admitted_count += 1
            if admitted_count >= topk * 3:
                break
        if rejected_due_to_cap > 0:
            cap_binding_days += 1
    out = pd.DataFrame(keep_rows).set_index(["datetime", "instrument"])["score"]
    logger.info(f"Cap was binding on {cap_binding_days} of {df['datetime'].nunique()} trading days "
                f"({100*cap_binding_days/max(1,df['datetime'].nunique()):.1f}%)")
    return out


def main():
    qlib.init(provider_uri=QLIB_DIR, region="cn")

    instruments_path = ROOT / "data" / "qlib_data" / "instruments" / "csi500.txt"
    with open(instruments_path, encoding="utf-8") as f:
        universe = sorted({line.split()[0].upper().strip() for line in f if line.strip()})
    logger.info(f"CSI500 universe size: {len(universe)}")

    expr_qop = op.fundamental("q_op_qoq")
    expr_roe = op.fundamental("roe_yoy")
    df = D.features(universe, [expr_qop, expr_roe], start_time=OOS_START, end_time=OOS_END, freq="day")
    df.columns = ["qop", "roe"]
    extras = D.features(universe, ["Ref($n_income_attr_p, 1)", "Ref($total_mv, 1)", "Ref($amount, 1)"],
                         start_time=OOS_START, end_time=OOS_END, freq="day")
    extras.columns = ["nip", "mv", "amt"]
    df = df.join(extras, how="left")
    eligible = (df["nip"] > 0) & (df["mv"] >= 300_000) & (df["amt"] >= 20_000)
    df.loc[~eligible, ["qop", "roe"]] = np.nan
    logger.info(f"Eligible obs: {eligible.sum()}/{len(eligible)}")

    grouped = df.groupby(level="datetime")
    score = (grouped["qop"].rank(pct=True) + grouped["roe"].rank(pct=True)) / 2.0
    score = score.dropna()
    logger.info(f"Pre-cap signal shape: {score.shape}")

    # L1 industry membership (time-varying)
    l1_series = build_industry_series_asof(score.index, level="L1")
    coverage = l1_series.notna().mean()
    n_distinct_l1 = l1_series.dropna().nunique()
    logger.info(f"L1 coverage: {100*coverage:.2f}% | distinct L1s in OOS sample: {n_distinct_l1}")

    capped = apply_l1_sector_cap(score, l1_series, topk=TOPK, max_per=MAX_PER_L1)
    logger.info(f"Post-cap obs: {len(capped)} (vs pre-cap {len(score)})")

    # Diagnostic: sample-day concentration
    sample_dt = score.index.get_level_values(0 if score.index.names[0] == "datetime" else 1).unique()
    sample_dt = sorted(sample_dt)[len(sample_dt) // 2]
    sample = pd.DataFrame({"score": score, "l1": l1_series}).reset_index()
    sample.columns = ["a", "b", "score", "l1"]
    dt_col = "a" if pd.api.types.is_datetime64_any_dtype(sample["a"]) else "b"
    inst_col = "b" if dt_col == "a" else "a"
    sample = sample.rename(columns={dt_col: "datetime", inst_col: "instrument"})
    natural_top50 = sample[sample["datetime"] == sample_dt].nlargest(50, "score")
    print(f"\n--- Sample date {sample_dt} natural-top-50 L1 concentration ---")
    print(natural_top50["l1"].value_counts().head(10).to_string())
    print(f"  distinct L1s: {natural_top50['l1'].nunique()}, max per L1: {natural_top50['l1'].value_counts().max()}\n")

    pred = capped.to_frame("score").dropna()
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
    print(f"OOS DIAGNOSTIC: TopK={TOPK} + Shenwan L1 cap (max {MAX_PER_L1} per L1)")
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
