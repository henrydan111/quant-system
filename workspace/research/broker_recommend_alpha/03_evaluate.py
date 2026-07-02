"""Evaluate the 券商金股 mother signal: does the monthly EW 金股 book beat benchmarks?

Reuses the established 果仁/jq replication tooling:
  - board_of()                       universe classify (exclude 北证/BSE/B-share)
  - D.features([...],["$close*$adj_factor"])   sanctioned adjusted-price load
  - an inline EW monthly simulator mirroring jq_rep_utils.simulate_eqw_monthly
    (no-lookahead: book at rebalance r earns from day after r; buy-and-hold
     within block; turnover cost). We pass OUR return panel so 金股 names that
     are absent from the long_only universe are NOT silently dropped.
  - research_utils.goal_metrics / sharpe / geom_cagr / max_drawdown

Usable sample: holding months 202007..202601 (67 rebalances), realized through
2026-02 — the trade calendar is frozen at 2026-02-27, so 2026-03..06 lists have
no forward window yet.

Outputs: console tables + workspace/outputs/broker_recommend_alpha/eval_results.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "workspace" / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "workspace" / "research" / "long_only_50cagr"))

import research_utils as ru  # noqa: E402
from guorn_universe import board_of  # noqa: E402

OUT_DIR = PROJECT_ROOT / "workspace" / "outputs" / "broker_recommend_alpha"
PANEL = OUT_DIR / "panel_asof.parquet"
RETPANEL = OUT_DIR / "ret_panel.parquet"
INDEX_DIR = PROJECT_ROOT / "data" / "market" / "index"

START = "2020-06-01"
END = "2026-02-27"          # frozen-calendar bound
TRADABLE_BOARDS = ("main", "chinext", "star")   # exclude 北证/BSE + B-share
COST_ONEWAY = 0.0016        # per-unit turnover (matches jq_rep_utils convention)


# ---------- adjusted-return panel for the 金股 universe ----------
def build_ret_panel(insts: list[str]) -> pd.DataFrame:
    if RETPANEL.exists():
        R = pd.read_parquet(RETPANEL)
        if set(insts).issubset(set(R.columns)):
            return R
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=str(PROJECT_ROOT / "data" / "qlib_data"), region=REG_CN, kernels=1)
    print(f"[panel] D.features adj-close for {len(insts)} instruments {START}..{END}", flush=True)
    df = D.features(insts, ["$close*$adj_factor"], start_time=START, end_time=END, freq="day")
    df.columns = ["adjclose"]
    adj = df["adjclose"].unstack(level=0).sort_index()   # qlib MI is (instrument, datetime)
    R = adj.pct_change()
    R.to_parquet(RETPANEL)
    print(f"[panel] saved {RETPANEL} shape={R.shape}", flush=True)
    return R


# ---------- inline EW monthly simulator (mirrors jq_rep_utils.simulate_eqw_monthly) ----------
def simulate(holdings: dict[pd.Timestamp, list[str]], R: pd.DataFrame,
             start: str, end: str, cost_oneway: float = COST_ONEWAY) -> pd.Series:
    cal = ru.trading_calendar()
    days = cal[(cal >= pd.Timestamp(start)) & (cal <= pd.Timestamp(end))]
    rebals = pd.DatetimeIndex(sorted(holdings.keys()))
    gov = rebals.searchsorted(days, side="left") - 1   # day==r -> prior book (earn from r+1)
    prev_w = pd.Series(dtype=float)
    out = pd.Series(0.0, index=days)
    for i, r in enumerate(rebals):
        block = days[gov == i]
        names = [s for s in holdings[r] if s in R.columns]
        w = pd.Series(1.0 / len(names), index=names) if names else pd.Series(dtype=float)
        all_names = prev_w.index.union(w.index)
        turn = float((w.reindex(all_names).fillna(0.0) - prev_w.reindex(all_names).fillna(0.0)).abs().sum())
        prev_w = w
        if len(block) == 0:
            continue
        if names:
            sub = R.loc[R.index.isin(block), names].reindex(block).fillna(0.0)
            nav = (1.0 + sub).cumprod().mean(axis=1)     # EW at entry, then buy-and-hold drift
            port = nav.to_numpy().copy()
            port[1:] = nav.to_numpy()[1:] / nav.to_numpy()[:-1] - 1.0
            port[0] = nav.to_numpy()[0] - 1.0
        else:
            port = np.zeros(len(block))
        port[0] -= turn * cost_oneway
        out.loc[block] = port
    return out.rename("net")


def load_benchmark(code: str, days: pd.DatetimeIndex) -> pd.Series | None:
    f = INDEX_DIR / f"index_{code}.parquet"
    if not f.exists():
        return None
    idx = pd.read_parquet(f)
    idx["trade_date"] = pd.to_datetime(idx["trade_date"].astype(str), format="%Y%m%d")
    s = (idx.set_index("trade_date")["pct_chg"] / 100.0).reindex(days).fillna(0.0)
    return s.rename(code)


def fwd_block_return(R: pd.DataFrame, names: list[str], block: pd.DatetimeIndex) -> pd.Series:
    names = [s for s in names if s in R.columns]
    if not names or len(block) == 0:
        return pd.Series(dtype=float)
    sub = R.loc[R.index.isin(block), names].reindex(block).fillna(0.0)
    return (1.0 + sub).prod(axis=0) - 1.0   # per-stock compounded block return


def main() -> int:
    panel = pd.read_parquet(PANEL)
    panel = panel[panel["qlib_code"].map(lambda c: board_of(c) in TRADABLE_BOARDS)].copy()

    usable = panel[panel["entry_d4"].notna() & panel["exit_d4"].notna()].copy()
    months = sorted(usable["month"].unique())
    print(f"usable months: {months[0]}..{months[-1]} (n={len(months)})")
    insts = sorted(usable["qlib_code"].unique())
    print(f"universe (tradable boards): {len(insts)} instruments")

    R = build_ret_panel(insts)
    cov = np.mean([c in R.columns for c in insts])
    print(f"price-data coverage of recommended names: {cov:.1%}")

    cal = ru.trading_calendar()
    days = cal[(cal >= pd.Timestamp(START)) & (cal <= pd.Timestamp(END))]

    # ---- holdings dicts (d4 primary, d1 sensitivity, conviction>=2 sub-book) ----
    def holdings_for(anchor_col: str, conv_floor: int = 1) -> dict:
        h = {}
        for m, g in usable.groupby("month"):
            g2 = g[g["n_brokers"] >= conv_floor]
            anchor = g2[anchor_col].iloc[0] if len(g2) else None
            if anchor is not None and pd.notna(anchor):
                h[pd.Timestamp(anchor)] = g2["qlib_code"].tolist()
        return h

    books = {
        "jin_gu_EW_d4": holdings_for("entry_d4", 1),
        "jin_gu_EW_d1": holdings_for("entry_d1", 1),
        "jin_gu_conv2_d4": holdings_for("entry_d4", 2),
        "jin_gu_conv3_d4": holdings_for("entry_d4", 3),
    }
    rets = {name: simulate(h, R, START, END) for name, h in books.items()}

    # restrict metric window to where the book is actually invested
    inv_days = rets["jin_gu_EW_d4"][rets["jin_gu_EW_d4"] != 0].index
    win = days[(days >= inv_days.min()) & (days <= inv_days.max())]

    benches = {}
    for code in ["000300.SH", "000906.SH", "000985.SH", "000852.SH", "000905.SH"]:
        b = load_benchmark(code, days)
        if b is not None:
            benches[code] = b

    print("\n===== PORTFOLIO METRICS (window %s .. %s) =====" % (win.min().date(), win.max().date()))
    # primary = size-matched benchmark: prefer 中证800, else 中证500 (金股 EW tilts mid/small)
    primary_code = next((c for c in ["000906.SH", "000905.SH", "000852.SH", "000300.SH"] if c in benches), None)
    primary_bench = benches.get(primary_code) if primary_code else None
    results = {}
    header = f"{'book':>18} | {'CAGR':>7} | {'MDD':>7} | {'Sharpe':>6} | {'AnnVol':>6} | {'exCAGR*':>7} | {'IR*':>5}"
    print(header)
    for name, r in rets.items():
        rw = r.reindex(win).fillna(0.0)
        bw = primary_bench.reindex(win).fillna(0.0) if primary_bench is not None else None
        m = ru.goal_metrics(rw, bw)
        results[name] = m
        print(f"{name:>18} | {m['cagr']:>6.2%} | {m['mdd']:>6.2%} | {m['sharpe']:>6.2f} | "
              f"{m['ann_vol']:>5.1%} | {m.get('excess_cagr', float('nan')):>6.2%} | {m.get('ir', float('nan')):>5.2f}")
    print(f"(* excess/IR vs size-matched primary benchmark {primary_code}; 中证800/000906 not local)")
    print("  NOTE: 金股 book uses adj-close = TOTAL return; index pct_chg = PRICE return")
    print("        -> comparison is biased ~+1-2%/yr IN FAVOR of 金股 (dividend yield).")

    print("\n===== BENCHMARKS (same window) =====")
    for code, b in benches.items():
        bw = b.reindex(win).fillna(0.0)
        m = ru.goal_metrics(bw)
        results[f"bench_{code}"] = m
        print(f"{code:>18} | {m['cagr']:>6.2%} | {m['mdd']:>6.2%} | {m['sharpe']:>6.2f} | {m['ann_vol']:>5.1%}")

    # ---- excess CAGR of the primary EW book vs EVERY benchmark (the 'benchmark unstated' fix) ----
    print("\n===== jin_gu_EW_d4 excess CAGR vs each benchmark =====")
    base = rets["jin_gu_EW_d4"].reindex(win).fillna(0.0)
    base_cagr = ru.geom_cagr(base)
    excess_vs = {}
    for code, b in benches.items():
        ex = base_cagr - ru.geom_cagr(b.reindex(win).fillna(0.0))
        ir = ru.sharpe((base - b.reindex(win).fillna(0.0)).dropna())
        excess_vs[code] = {"excess_cagr": ex, "ir": ir}
        print(f"  vs {code}: excess CAGR {ex:+.2%}  IR {ir:+.2f}")

    # ---- factor-level: monthly RankIC of conviction vs forward block return ----
    print("\n===== CONVICTION factor-level (RankIC of n_brokers vs fwd 1M return) =====")
    anchors = (usable[["month", "entry_d4", "exit_d4"]].drop_duplicates().sort_values("month").reset_index(drop=True))
    ics = []
    for _, row in anchors.iterrows():
        m = row["month"]
        block = days[(days > pd.Timestamp(row["entry_d4"])) & (days <= pd.Timestamp(row["exit_d4"]))]
        g = usable[usable["month"] == m]
        fwd = fwd_block_return(R, g["qlib_code"].tolist(), block)
        if len(fwd) < 8:
            continue
        sig = g.set_index("qlib_code")["n_brokers"].reindex(fwd.index)
        ic = sig.corr(fwd, method="spearman")
        if pd.notna(ic):
            ics.append(ic)
    ics = pd.Series(ics)
    icir = ics.mean() / ics.std() if ics.std() > 0 else float("nan")
    print(f"  mean monthly RankIC={ics.mean():+.4f}  std={ics.std():.4f}  ICIR={icir:+.3f}  "
          f"n_months={len(ics)}  %>0={np.mean(ics>0):.0%}")

    # ---- IS / OOS split (IS 202007..202312, OOS 202401..202601) ----
    def cagr_window(r, a, b):
        seg = r[(r.index >= pd.Timestamp(a)) & (r.index <= pd.Timestamp(b))]
        seg = seg[seg.index.isin(win)]
        return ru.geom_cagr(seg)
    pbench = benches.get(primary_code) if primary_code else base
    print("\n===== IS vs OOS (EW_d4 vs %s) =====" % primary_code)
    for label, a, b in [("IS 2020-07..2023-12", "2020-07-01", "2023-12-31"),
                        ("OOS 2024-01..2026-02", "2024-01-01", "2026-02-27")]:
        pc = cagr_window(base, a, b)
        bc = cagr_window(pbench, a, b)
        print(f"  {label}: 金股 EW {pc:+.2%}  | {primary_code} {bc:+.2%}  | excess {pc-bc:+.2%}")
        results[f"split_{label}"] = {"book_cagr": pc, "bench_cagr": bc}

    results["_meta"] = {
        "usable_months": [months[0], months[-1]], "n_months": len(months),
        "n_instruments": len(insts), "price_coverage": float(cov),
        "window": [str(win.min().date()), str(win.max().date())],
        "conviction_rankic": {"mean": float(ics.mean()), "icir": float(icir), "n": int(len(ics))},
        "excess_vs_benchmarks": excess_vs,
        "cost_oneway": COST_ONEWAY, "benchmarks_available": list(benches.keys()),
    }
    (OUT_DIR / "eval_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    print(f"\nwrote -> {OUT_DIR / 'eval_results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
