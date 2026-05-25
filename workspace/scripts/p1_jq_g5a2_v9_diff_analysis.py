"""Compare v8 vs v9 once v9 finishes, plus year-by-year diff vs JoinQuant.

Reads:
  - v8 report at workspace/research/alpha_mining/p1_jq_g5a2_mimic_v8_100k_capital_run/event_driven_report.csv
  - v9 report at workspace/research/alpha_mining/p1_jq_g5a2_mimic_v9_jq_stoploss_parity_run/event_driven_report.csv
  - JoinQuant daily at C:/Users/henry/Desktop/聚宽回测系统/strategies/G5_韶华纯净小市值/variants/G5_A2_stocknum12/g5_G5_A2_stocknum12_daily.csv

Aligns by trading calendar, computes:
  - per-year compounded return for v8, v9, JQ
  - per-year v9-v8 delta
  - per-year v9-JQ residual
  - cumulative NAV trajectory
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(r"E:/量化系统")
V8 = PROJECT_ROOT / "workspace/research/alpha_mining/p1_jq_g5a2_mimic_v8_100k_capital_run/event_driven_report.csv"
V9 = PROJECT_ROOT / "workspace/research/alpha_mining/p1_jq_g5a2_mimic_v9_jq_stoploss_parity_run/event_driven_report.csv"
V10 = PROJECT_ROOT / "workspace/research/alpha_mining/p1_jq_g5a2_mimic_v10_limitdown_run/event_driven_report.csv"
V11 = PROJECT_ROOT / "workspace/research/alpha_mining/p1_jq_g5a2_mimic_v11_topk100_run/event_driven_report.csv"
V12 = PROJECT_ROOT / "workspace/research/alpha_mining/p1_jq_g5a2_mimic_v12_no_survivor_run/event_driven_report.csv"
V13 = PROJECT_ROOT / "workspace/research/alpha_mining/p1_jq_g5a2_mimic_v13_jq_universe_run/event_driven_report.csv"
V14 = PROJECT_ROOT / "workspace/research/alpha_mining/p1_jq_g5a2_mimic_v14_jq_replay_run/event_driven_report.csv"
V15 = PROJECT_ROOT / "workspace/research/alpha_mining/p1_jq_g5a2_mimic_v15_jq_slippage_run/event_driven_report.csv"
JQ = Path(r"C:/Users/henry/Desktop/聚宽回测系统/strategies/G5_韶华纯净小市值/variants/G5_A2_stocknum12/g5_G5_A2_stocknum12_daily.csv")


def load_local_report(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    cal = pd.read_parquet(PROJECT_ROOT / "data/reference/trade_cal.parquet")
    cal["cal_date"] = pd.to_datetime(cal["cal_date"], format="%Y%m%d", errors="coerce")
    cal = cal[(cal["is_open"] == 1)
              & (cal["cal_date"] >= "2014-01-01")
              & (cal["cal_date"] <= "2026-02-27")]
    cal = cal.sort_values("cal_date").reset_index(drop=True)
    n = len(df)
    df["date"] = cal["cal_date"].iloc[:n].values
    return df


def main() -> int:
    if not V9.exists():
        print(f"v9 report not found at {V9} — wait for backtest to finish")
        return 1

    v8 = load_local_report(V8)
    v9 = load_local_report(V9)
    v10 = load_local_report(V10)
    v11 = load_local_report(V11)
    v12 = load_local_report(V12)
    v13 = load_local_report(V13)
    v14 = load_local_report(V14)
    v15 = load_local_report(V15)
    jq = pd.read_csv(JQ, parse_dates=["time"])
    jq["date"] = jq["time"].dt.normalize()
    jq = jq[["date", "daily_strategy_return", "nav"]].rename(columns={"daily_strategy_return": "ret_jq", "nav": "nav_jq"})
    jq = jq[(jq["date"] >= "2014-01-01") & (jq["date"] <= "2026-02-27")]

    # Merge
    df = pd.DataFrame({"date": v8["date"]}).merge(v8[["date", "return"]].rename(columns={"return": "ret_v8"}), on="date")
    df = df.merge(v9[["date", "return"]].rename(columns={"return": "ret_v9"}), on="date")
    df = df.merge(v10[["date", "return"]].rename(columns={"return": "ret_v10"}), on="date")
    df = df.merge(v11[["date", "return"]].rename(columns={"return": "ret_v11"}), on="date")
    df = df.merge(v12[["date", "return"]].rename(columns={"return": "ret_v12"}), on="date")
    df = df.merge(v13[["date", "return"]].rename(columns={"return": "ret_v13"}), on="date")
    df = df.merge(v14[["date", "return"]].rename(columns={"return": "ret_v14"}), on="date")
    df = df.merge(v15[["date", "return"]].rename(columns={"return": "ret_v15"}), on="date")
    df = df.merge(jq, on="date", how="left")
    df["year"] = df["date"].dt.year

    # NAVs
    df["nav_v8"] = (1 + df["ret_v8"].fillna(0)).cumprod()
    df["nav_v9"] = (1 + df["ret_v9"].fillna(0)).cumprod()
    df["nav_v10"] = (1 + df["ret_v10"].fillna(0)).cumprod()
    df["nav_v11"] = (1 + df["ret_v11"].fillna(0)).cumprod()
    df["nav_v12"] = (1 + df["ret_v12"].fillna(0)).cumprod()
    df["nav_v13"] = (1 + df["ret_v13"].fillna(0)).cumprod()
    df["nav_v14"] = (1 + df["ret_v14"].fillna(0)).cumprod()
    df["nav_v15"] = (1 + df["ret_v15"].fillna(0)).cumprod()
    # NAV-JQ is already in df
    df["nav_jq_cum"] = (1 + df["ret_jq"].fillna(0)).cumprod()

    # Per-year compounded
    by_yr = df.groupby("year")
    yearly = pd.DataFrame({
        "v8":  by_yr["ret_v8"].apply(lambda s: float((1 + s.fillna(0)).prod() - 1)),
        "v9":  by_yr["ret_v9"].apply(lambda s: float((1 + s.fillna(0)).prod() - 1)),
        "v10": by_yr["ret_v10"].apply(lambda s: float((1 + s.fillna(0)).prod() - 1)),
        "v11": by_yr["ret_v11"].apply(lambda s: float((1 + s.fillna(0)).prod() - 1)),
        "v12": by_yr["ret_v12"].apply(lambda s: float((1 + s.fillna(0)).prod() - 1)),
        "v13": by_yr["ret_v13"].apply(lambda s: float((1 + s.fillna(0)).prod() - 1)),
        "v14": by_yr["ret_v14"].apply(lambda s: float((1 + s.fillna(0)).prod() - 1)),
        "v15": by_yr["ret_v15"].apply(lambda s: float((1 + s.fillna(0)).prod() - 1)),
        "jq":  by_yr["ret_jq"].apply(lambda s: float((1 + s.fillna(0)).prod() - 1)),
    })
    yearly["v15_minus_v14_pp"] = (yearly["v15"] - yearly["v14"]) * 100
    yearly["v15_minus_jq_pp"] = (yearly["v15"] - yearly["jq"]) * 100
    yearly["v14_minus_jq_pp"] = (yearly["v14"] - yearly["jq"]) * 100

    print("=" * 100)
    print("Yearly compounded returns + cross-engine deltas")
    print("=" * 100)
    print(yearly.to_string(float_format=lambda x: f"{x:8.4f}" if abs(x) < 100 else f"{x:.2f}"))

    # Cumulative
    cum_v8 = float((1 + df["ret_v8"].fillna(0)).prod() - 1)
    cum_v9 = float((1 + df["ret_v9"].fillna(0)).prod() - 1)
    cum_v10 = float((1 + df["ret_v10"].fillna(0)).prod() - 1)
    cum_v11 = float((1 + df["ret_v11"].fillna(0)).prod() - 1)
    cum_v12 = float((1 + df["ret_v12"].fillna(0)).prod() - 1)
    cum_v13 = float((1 + df["ret_v13"].fillna(0)).prod() - 1)
    cum_v14 = float((1 + df["ret_v14"].fillna(0)).prod() - 1)
    cum_v15 = float((1 + df["ret_v15"].fillna(0)).prod() - 1)
    cum_jq = float((1 + df["ret_jq"].fillna(0)).prod() - 1)
    n_yr = len(df) / 242
    cagr_v8 = (1 + cum_v8) ** (1 / n_yr) - 1
    cagr_v9 = (1 + cum_v9) ** (1 / n_yr) - 1
    cagr_v10 = (1 + cum_v10) ** (1 / n_yr) - 1
    cagr_v11 = (1 + cum_v11) ** (1 / n_yr) - 1
    cagr_v12 = (1 + cum_v12) ** (1 / n_yr) - 1
    cagr_v13 = (1 + cum_v13) ** (1 / n_yr) - 1
    cagr_v14 = (1 + cum_v14) ** (1 / n_yr) - 1
    cagr_v15 = (1 + cum_v15) ** (1 / n_yr) - 1
    cagr_jq = (1 + cum_jq) ** (1 / n_yr) - 1

    print()
    print("=" * 100)
    print(f"Cumulative — v8:  {cum_v8*100:>13,.2f}%   CAGR {cagr_v8*100:.2f}%")
    print(f"Cumulative — v9:  {cum_v9*100:>13,.2f}%   CAGR {cagr_v9*100:.2f}%")
    print(f"Cumulative — v10: {cum_v10*100:>13,.2f}%   CAGR {cagr_v10*100:.2f}%")
    print(f"Cumulative — v11: {cum_v11*100:>13,.2f}%   CAGR {cagr_v11*100:.2f}%")
    print(f"Cumulative — v12: {cum_v12*100:>13,.2f}%   CAGR {cagr_v12*100:.2f}%")
    print(f"Cumulative — v13: {cum_v13*100:>13,.2f}%   CAGR {cagr_v13*100:.2f}%")
    print(f"Cumulative — v14: {cum_v14*100:>13,.2f}%   CAGR {cagr_v14*100:.2f}% (JQ-replay, PctSlippage)")
    print(f"Cumulative — v15: {cum_v15*100:>13,.2f}%   CAGR {cagr_v15*100:.2f}% (JQ-replay + FixedSlippage)")
    print(f"Cumulative — JQ:  {cum_jq*100:>13,.2f}%   CAGR {cagr_jq*100:.2f}%")
    print("=" * 100)

    # Sharpe
    def sharpe(s: pd.Series) -> float:
        s = s.dropna()
        if len(s) < 2 or s.std() == 0:
            return float("nan")
        return float(s.mean() / s.std() * np.sqrt(242))
    print(f"Sharpe — v8: {sharpe(df['ret_v8']):.3f}  v9: {sharpe(df['ret_v9']):.3f}  v10: {sharpe(df['ret_v10']):.3f}  v11: {sharpe(df['ret_v11']):.3f}  v12: {sharpe(df['ret_v12']):.3f}  v13: {sharpe(df['ret_v13']):.3f}  v14: {sharpe(df['ret_v14']):.3f}  JQ: {sharpe(df['ret_jq']):.3f}")

    # MDD
    def mdd(s: pd.Series) -> float:
        nav = (1 + s.fillna(0)).cumprod()
        return float((nav / nav.cummax() - 1).min())
    print(f"MDD — v8: {mdd(df['ret_v8']):.3f}  v9: {mdd(df['ret_v9']):.3f}  v10: {mdd(df['ret_v10']):.3f}  v11: {mdd(df['ret_v11']):.3f}  v12: {mdd(df['ret_v12']):.3f}  v13: {mdd(df['ret_v13']):.3f}  v14: {mdd(df['ret_v14']):.3f}  JQ: {mdd(df['ret_jq']):.3f}")

    # Save full diff for further inspection
    out_path = PROJECT_ROOT / "workspace/research/alpha_mining/p1_jq_g5a2_mimic_v10_limitdown_run/v8_v9_v10_jq_diff_daily.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"\nWrote daily diff: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
