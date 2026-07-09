# SCRIPT_STATUS: ACTIVE — AI 链路观察站 Block D:日度模拟盘(Class-D 试点,非证据)
"""Daily paper NAV over the replay decisions — 4 legs (DESIGN.md §5).

  pool_ew           池等权,激活日建仓持有(月度基准腿)
  quant_daily       每日量化 top-25 等权(每日调仓到目标)
  ai_daily          每日 AI 叠加 top-25 等权(链路观察腿)
  ai_day4_protocol  首个决策日(=C3 激活日,day-4)的 AI 账本持有到月末(协议腿)

口径与 MVP block-1 一致:决策日 D 开盘成交,book_D 赚 open_D→open_{D+1};
成本 = 0.0016 × Σ|Δw|(单边费率×成交名义)。收益取自 provider $open(前复权口径
用 $open×$adj_factor 归一)。⚠ 全部数字 = 管道演示,非 alpha 证据。

用法: venv/Scripts/python.exe workspace/research/ai_chain_observatory/run_paper_sim.py
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from data_infra.provider_metadata import tushare_to_qlib_canonical  # noqa: E402

OUT_DIR = PROJECT_ROOT / "workspace" / "outputs" / "ai_chain_observatory"
DAILY_DIR = OUT_DIR / "daily"
TRADE_CAL = PROJECT_ROOT / "data" / "reference" / "trade_cal.parquet"
COST_ONEWAY = 0.0016

logger = logging.getLogger("paper_sim")


def load_decisions() -> dict[str, dict]:
    out = {}
    for p in sorted(DAILY_DIR.glob("*/decision.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        out[d["date"]] = d
    if not out:
        raise RuntimeError("no daily decisions found — run run_chain_replay.py first")
    return out


def open_returns(codes: list[str], start: str, end_next: str) -> pd.DataFrame:
    """adj open→open returns, index=trade date (YYYYMMDD), columns=ts_code."""
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=str(PROJECT_ROOT / "data" / "qlib_data"),
              region=REG_CN, kernels=1)
    avail = {i.upper(): i for i in D.list_instruments(
        D.instruments("all"), start_time=start, end_time=end_next, as_list=True)}
    qmap = {c: avail[tushare_to_qlib_canonical(c)] for c in codes
            if tushare_to_qlib_canonical(c) in avail}
    df = D.features(list(qmap.values()), ["$open", "$adj_factor"],
                    start_time=start, end_time=end_next, freq="day")
    adj_open = (df["$open"] * df["$adj_factor"]).unstack(level=0)
    back = {v: k for k, v in qmap.items()}
    adj_open.columns = [back.get(str(c), str(c)) for c in adj_open.columns]
    ret = adj_open.shift(-1) / adj_open - 1.0          # open_D -> open_{D+1}
    ret.index = [d.strftime("%Y%m%d") for d in ret.index]
    return ret


def run_leg(name: str, books: dict[str, list[str]], ret: pd.DataFrame,
            days: list[str]) -> tuple[pd.Series, dict]:
    """books: decision day -> list of codes (equal weight). Daily rebalance to
    target; cost on traded notional."""
    nav, navs, w_prev = 1.0, [], pd.Series(dtype=float)
    turnover_sum = 0.0
    for day in days:
        codes = [c for c in books[day] if c in ret.columns]
        w_new = (pd.Series(1.0 / len(codes), index=codes)
                 if codes else pd.Series(dtype=float))
        l1 = float(w_new.subtract(w_prev, fill_value=0.0).abs().sum())
        cost = COST_ONEWAY * l1
        turnover_sum += l1 / 2.0
        r = float((w_new * ret.loc[day].reindex(w_new.index)).sum()) if codes else 0.0
        nav *= (1.0 + r - cost)
        navs.append({"date": day, "leg": name, "ret_gross": r, "cost": cost,
                     "nav": nav})
        w_prev = w_new
    s = pd.DataFrame(navs).set_index("date")["nav"]
    running_max = s.cummax()
    stats = {
        "total_return_pct": round((nav - 1.0) * 100, 2),
        "mdd_pct": round(float(((s / running_max) - 1.0).min()) * 100, 2),
        "avg_oneway_turnover_per_day": round(turnover_sum / max(1, len(days)), 4),
        "days": len(days),
    }
    return pd.DataFrame(navs), stats


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    decisions = load_decisions()
    days = sorted(decisions)
    logger.info("decisions: %d days %s..%s", len(days), days[0], days[-1])

    pool = decisions[days[0]]["legs"]["pool_ew"]
    all_codes = set(pool)
    for d in decisions.values():
        all_codes |= set(d["legs"]["quant_book"]) | set(d["legs"]["ai_book"])

    cal = pd.read_parquet(TRADE_CAL)
    opens = sorted(cal.loc[cal["is_open"] == 1, "cal_date"].astype(str))
    end_next = opens[opens.index(days[-1]) + 1]        # last book needs D+1 open
    ret = open_returns(sorted(all_codes), days[0], end_next)

    legs = {
        "pool_ew": {d: pool for d in days},
        "quant_daily": {d: decisions[d]["legs"]["quant_book"] for d in days},
        "ai_daily": {d: decisions[d]["legs"]["ai_book"] for d in days},
        "ai_day4_protocol": {d: decisions[days[0]]["legs"]["ai_book"] for d in days},
    }
    frames, summary = [], {}
    for name, books in legs.items():
        df, stats = run_leg(name, books, ret, days)
        frames.append(df)
        summary[name] = stats
        logger.info("%s: %s", name, stats)

    nav = pd.concat(frames).reset_index()
    nav.to_parquet(OUT_DIR / "nav_daily.parquet", index=False)
    summary["evidence_class"] = "NON_EVIDENTIARY_PILOT (C5 quasi-forward)"
    summary["cost_oneway"] = COST_ONEWAY
    (OUT_DIR / "sim_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("-> %s + sim_summary.json", OUT_DIR / "nav_daily.parquet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
