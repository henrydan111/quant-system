# SCRIPT_STATUS: ACTIVE — NON-FORMAL MVP quant baseline book (2026-07-06c directive)
"""MVP block 1 · 量化基线账本: pool 7-factor composite -> top-K EW, monthly day-4.

PRE-REGISTERED (fixed before results):
  - K = 25, per-industry cap = ceil(K/3) = 9 (directive guardrail; industry =
    CURRENT stock_basic snapshot -> guardrail-only, NOT a signal; PIT industry
    is a Phase-2A item).
  - Ranking = the SAME 7-factor oriented-pct-rank composite as Phase-0
    (registry directions; ranked WITHIN the pool at each anchor; no size
    neutralization — identical caliber to the Phase-0 diagnostic).
  - Rebalance = C3 activation anchors (first trading day >= day-4).
  - Simulator = the mother-signal inline EW monthly harness (book at rebalance r
    earns from r+1; buy-and-hold within month; 0.0016 one-way turnover cost;
    后复权 adjusted close ~ total-return caliber) -> numbers are DIRECTLY
    comparable to the 金股 EW record (CAGR 3.24% / MDD -52%).
  - Legs: (a) quant top-K book [headline], (b) pool EW [reference, same harness],
    benchmarks 沪深300/中证500/中证1000.

CALIBER CAVEATS (recorded): inline sim has no T+1/limit-up gating — hot names'
limit-up buyability makes it OPTIMISTIC in bull runs (果仁 lesson); the
event-driven engine fidelity leg is the required next check before any
deployment-flavored reading. NON-FORMAL: window overlaps spent-OOS 2021+.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))  # operators.py uses `from src....` imports

from data_infra.golden_stock_universe import load_golden_stock_events  # noqa: E402
from data_infra.provider_metadata import tushare_to_qlib_canonical  # noqa: E402
from alpha_research.factor_library.catalog import get_factor_catalog  # noqa: E402
from portfolio_risk.rank_book_construction import select_top_k_equal_weight  # noqa: E402

OUT_DIR = PROJECT_ROOT / "workspace" / "outputs" / "mvp_pool_book"
REGISTRY = PROJECT_ROOT / "data" / "factor_registry" / "factor_master.parquet"
INDEX_DIR = PROJECT_ROOT / "data" / "market" / "index"

FACTORS7 = [
    "liq_zero_ret_days_10d", "rev_turnover_spike_5d", "qual_piotroski_fscore_9pt",
    "earn_sue_ni_assets", "grow_total_revenue_yoy_accel_q",
    "grow_n_income_attr_p_yoy_accel_q", "grow_operate_profit_yoy_accel_q",
]
K = 25
MAX_PER_INDUSTRY = math.ceil(K / 3)  # = 9
COST_ONEWAY = 0.0016
START, END = "2020-06-01", "2026-02-27"
BENCHMARKS = {"沪深300": "000300.SH", "中证500": "000905.SH", "中证1000": "000852.SH"}


def load_directions() -> dict[str, int]:
    reg = pd.read_parquet(REGISTRY)
    id_col = "factor_id" if "factor_id" in reg.columns else "name"
    cur = reg.sort_values(id_col).drop_duplicates(subset=[id_col], keep="last")
    dirs = {}
    for f in FACTORS7:
        rows = cur[cur[id_col] == f]
        if rows.empty:
            raise RuntimeError(f"{f} missing from registry")
        d = str(rows["expected_direction"].iloc[0]).lower()
        dirs[f] = -1 if ("inverse" in d or "neg" in d) else 1
    return dirs


def metrics(net: pd.Series) -> dict:
    nav = (1 + net).cumprod()
    n = len(net)
    cagr = float(nav.iloc[-1] ** (252 / n) - 1)
    sharpe = float(net.mean() / net.std(ddof=1) * np.sqrt(252)) if net.std(ddof=1) > 0 else 0.0
    mdd = float((nav / nav.cummax() - 1).min())
    return {"cagr": round(cagr, 4), "sharpe": round(sharpe, 2), "mdd": round(mdd, 4),
            "ann_vol": round(float(net.std(ddof=1) * np.sqrt(252)), 4)}


def simulate(holdings: dict[pd.Timestamp, list[str]], R: pd.DataFrame,
             days: pd.DatetimeIndex) -> tuple[pd.Series, float]:
    """Mother-signal harness: book at rebalance r earns from r+1; returns (net, mean_turnover)."""
    rebals = pd.DatetimeIndex(sorted(holdings.keys()))
    gov = rebals.searchsorted(days, side="left") - 1
    prev_w = pd.Series(dtype=float)
    out = pd.Series(0.0, index=days)
    turns = []
    for i, r in enumerate(rebals):
        block = days[gov == i]
        names = [s for s in holdings[r] if s in R.columns]
        w = pd.Series(1.0 / len(names), index=names) if names else pd.Series(dtype=float)
        alln = prev_w.index.union(w.index)
        turn = float((w.reindex(alln).fillna(0.0) - prev_w.reindex(alln).fillna(0.0)).abs().sum())
        turns.append(turn)
        prev_w = w
        if len(block) == 0:
            continue
        if names:
            sub = R.loc[R.index.isin(block), names].reindex(block).fillna(0.0)
            nav = (1.0 + sub).cumprod().mean(axis=1)
            port = nav.to_numpy().copy()
            port[1:] = nav.to_numpy()[1:] / nav.to_numpy()[:-1] - 1.0
            port[0] = nav.to_numpy()[0] - 1.0
        else:
            port = np.zeros(len(block))
        port[0] -= turn * COST_ONEWAY
        out.loc[block] = port
    return out.rename("net"), float(np.mean(turns))


def load_benchmark(ts_code: str, days: pd.DatetimeIndex) -> pd.Series | None:
    for cand in (INDEX_DIR / f"index_{ts_code}.parquet",
                 INDEX_DIR / f"index_{tushare_to_qlib_canonical(ts_code)}.parquet"):
        if cand.exists():
            df = pd.read_parquet(cand)
            dcol = "trade_date" if "trade_date" in df.columns else df.columns[0]
            idx = pd.to_datetime(df[dcol].astype(str))
            close = df["close"].astype(float)
            s = pd.Series(close.values, index=idx).sort_index()
            return s.pct_change().reindex(days).fillna(0.0)
    return None


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dirs = load_directions()

    events = load_golden_stock_events()
    anchors = (events.drop_duplicates("month")[["month", "activation_date"]]
               .sort_values("activation_date").reset_index(drop=True))
    pool_by_month = {m: sorted({tushare_to_qlib_canonical(c) for c in g["ts_code"]})
                     for m, g in events.groupby("month")}

    # industry map (CURRENT snapshot -> guardrail only)
    sb = pd.read_parquet(PROJECT_ROOT / "data" / "reference" / "stock_basic.parquet",
                         columns=["ts_code", "industry"])
    industry_of = {tushare_to_qlib_canonical(t): (i if isinstance(i, str) and i else None)
                   for t, i in zip(sb["ts_code"], sb["industry"])}

    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=str(PROJECT_ROOT / "data" / "qlib_data"), region=REG_CN, kernels=1)

    pool_ever = sorted(set().union(*pool_by_month.values()))
    avail = set(D.list_instruments(D.instruments("all"), start_time=START, end_time=END, as_list=True))
    avail_upper = {a.upper(): a for a in avail}
    insts = [avail_upper[c] for c in pool_ever if c in avail_upper]
    print(f"[pool] ever={len(pool_ever)} in-provider={len(insts)}", flush=True)

    cat = get_factor_catalog(include_new_data=True)
    exprs = [cat[f] for f in FACTORS7] + ["$close*$adj_factor"]
    names = FACTORS7 + ["adjclose"]
    print(f"[qlib] computing {len(exprs)} expressions on {len(insts)} pool instruments", flush=True)
    df = D.features(insts, exprs, start_time=START, end_time=END, freq="day")
    df.columns = names
    panels = {c: df[c].unstack(level=0).sort_index() for c in names}
    panels = {k: v.rename(columns={c: c.upper() for c in v.columns}) for k, v in panels.items()}
    R = panels["adjclose"].pct_change()
    days = R.index
    print(f"[qlib] done, panel {R.shape}", flush=True)

    # ---- build books at each anchor ----
    hold_quant: dict[pd.Timestamp, list[str]] = {}
    hold_pool: dict[pd.Timestamp, list[str]] = {}
    diag = []
    for _, a in anchors.iterrows():
        t = a["activation_date"]
        if t not in days:
            continue
        members = [c for c in pool_by_month[a["month"]] if c in R.columns]
        if len(members) < K:
            continue
        # composite: oriented within-pool pct-ranks at t (same caliber as Phase-0)
        comp = pd.Series(0.0, index=members)
        for f in FACTORS7:
            x = panels[f].loc[t, members]
            r = x.rank(pct=True)
            if dirs[f] < 0:
                r = 1.0 - r
            comp = comp.add(r.fillna(0.5), fill_value=0.0)
        comp = comp / len(FACTORS7)
        top = select_top_k_equal_weight(comp, K, industry_of=industry_of,
                                        max_per_industry=MAX_PER_INDUSTRY)
        hold_quant[t] = top
        hold_pool[t] = members
        diag.append({"month": a["month"], "date": t, "n_pool": len(members), "n_book": len(top)})
    print(f"[books] {len(hold_quant)} rebalances", flush=True)

    first = min(hold_quant.keys())
    sim_days = days[(days >= first) & (days <= pd.Timestamp(END))]
    net_q, turn_q = simulate(hold_quant, R, sim_days)
    net_p, turn_p = simulate(hold_pool, R, sim_days)

    res = {
        "design": {"K": K, "max_per_industry": MAX_PER_INDUSTRY, "cost_oneway": COST_ONEWAY,
                   "factors": FACTORS7, "window": f"{first.date()}..{END}",
                   "rebalances": len(hold_quant),
                   "caliber": "inline EW monthly, 后复权 close, no T+1/limit gating (optimistic for hot names)",
                   "evidence_class": "NON_FORMAL_research (window overlaps spent-OOS 2021+)"},
        "quant_topk_book": {**metrics(net_q), "mean_turnover_oneway": round(turn_q / 2, 3)},
        "pool_ew_reference": {**metrics(net_p), "mean_turnover_oneway": round(turn_p / 2, 3)},
        "benchmarks": {},
        "by_year": {},
    }
    for bname, bcode in BENCHMARKS.items():
        b = load_benchmark(bcode, sim_days)
        if b is not None:
            res["benchmarks"][bname] = metrics(b)
    for y, g in net_q.groupby(net_q.index.year):
        gp = net_p[net_p.index.year == y]
        res["by_year"][str(y)] = {"quant_topk": round(float((1 + g).prod() - 1), 4),
                                  "pool_ew": round(float((1 + gp).prod() - 1), 4)}

    pd.DataFrame({"quant_topk": net_q, "pool_ew": net_p}).to_parquet(OUT_DIR / "nav_daily.parquet")
    pd.DataFrame(diag).to_parquet(OUT_DIR / "rebalance_diag.parquet", index=False)
    (OUT_DIR / "baseline_results.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    print("\n=== MVP quant baseline (NON-FORMAL, inline-sim caliber) ===", flush=True)
    for leg in ("quant_topk_book", "pool_ew_reference"):
        print(f"{leg:22s} {res[leg]}", flush=True)
    for b, m in res["benchmarks"].items():
        print(f"bench {b:12s} {m}", flush=True)
    print("\nby year (quant vs poolEW):", flush=True)
    for y, v in res["by_year"].items():
        print(f"  {y}: {v['quant_topk']:+.1%} vs {v['pool_ew']:+.1%}", flush=True)
    print(f"\nwrote -> {OUT_DIR}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
