"""
ST stock long-only TopK strategy: market cap (small) + revenue (high) + momentum (high).

Exploratory validation. Not pre-registered, not gated, sandbox only. Tests four
momentum horizons (20/60/120/250 trading days) plus a no-momentum baseline.

Universe: ST stocks (data/qlib_data/instruments/st_stocks.txt range form).
Window:   2014-01-01 to 2026-02-27 (calendar end).
Signal:   Equal-weight cross-sectional rank of [-mv, +revenue_q, +mom_Nd], NaN
          on non-ST (date, ticker) entries so TopK picks only from ST pool.
Engine:   VectorizedBacktester, deal_price='open', forbid_all_trade_at_limit=True,
          ST 5% daily limit threshold (override of default 9.5%).

Outputs (under workspace/outputs/st_mom_revenue_<ts>/):
  - summary.md             : per-horizon metric table + IC table + verdict
  - per_horizon/<h>.json   : full backtest summary for horizon h
  - per_horizon/<h>_eq.csv : daily return / cost / bench / cum_ret series
  - ic_summary.csv         : IC, RankIC, ICIR per factor and per horizon
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3].parent  # E:\量化系统
sys.path.insert(0, str(PROJECT_ROOT))

from src.alpha_research.factor_library import operators as op  # noqa: E402
from src.backtest_engine.vectorized import VectorizedBacktester  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("st_mom")

# ── Configuration ──────────────────────────────────────────────────────────
QLIB_DIR = str(PROJECT_ROOT / "data" / "qlib_data")
ST_FILE = PROJECT_ROOT / "data" / "qlib_data" / "instruments" / "st_stocks.txt"
TRADE_CAL = PROJECT_ROOT / "data" / "reference" / "trade_cal.parquet"

START_DATE = "2014-01-01"
# Stop a few bars before the calendar end. Qlib's TopkDropoutStrategy
# evaluates `calendar[step+1]` for the step end, which overflows on the
# very last bar. The provider calendar ends 2026-02-27.
END_DATE = "2026-02-20"

# ST has 5% daily limit. ±4.5% in $pct_chg space (Tushare units, percent not decimal).
ST_LIMIT_KWARGS = {
    "freq": "day",
    "limit_threshold": ("Ge($pct_chg, 4.5)", "Le($pct_chg, -4.5)"),
    "deal_price": "open",
    "open_cost": 0.0005,
    "close_cost": 0.0015,
    "min_cost": 5.0,
}

TOPK = 10
N_DROP = 5  # rotate 5 of 10 → effective ~5d holding given daily decision cadence
BENCHMARK = "000001_SH"  # SSE composite (matches ST theme spec)
ACCOUNT = 2_000_000.0  # 2M CNY, matches ST theme defaults

MOM_HORIZONS = [20, 60, 120, 250]

# Output directory
RUN_TS = time.strftime("%Y%m%d_%H%M%S")
OUT_DIR = PROJECT_ROOT / "workspace" / "outputs" / f"st_mom_revenue_{RUN_TS}"
OUT_DIR.mkdir(parents=True, exist_ok=True)
(OUT_DIR / "per_horizon").mkdir(exist_ok=True)


# ── Helpers ────────────────────────────────────────────────────────────────
def parse_st_ranges(path: Path) -> dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]]:
    ranges: dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]] = defaultdict(list)
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split("\t")
        if len(parts) < 3:
            continue
        code, start, end = parts[0].upper(), parts[1], parts[2]
        ranges[code].append((pd.Timestamp(start), pd.Timestamp(end)))
    return dict(ranges)


def build_st_mask(
    index: pd.MultiIndex,
    st_ranges: dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]],
) -> pd.Series:
    """Per-(date, instrument) boolean: True iff stock is ST on that calendar date."""
    instr_level = index.get_level_values("instrument")
    date_level = index.get_level_values("datetime")
    out = np.zeros(len(index), dtype=bool)
    # group by instrument so we only iterate ranges once per stock
    by_instr: dict[str, list[int]] = defaultdict(list)
    for i, code in enumerate(instr_level):
        by_instr[code].append(i)
    for code, idxs in by_instr.items():
        ranges = st_ranges.get(code)
        if not ranges:
            continue
        positions = np.asarray(idxs)
        dates = date_level[positions].values  # numpy datetime64
        flag = np.zeros(len(positions), dtype=bool)
        for start, end in ranges:
            flag |= (dates >= np.datetime64(start)) & (dates <= np.datetime64(end))
        out[positions] = flag
    return pd.Series(out, index=index)


def trading_calendar(start: str, end: str) -> pd.DatetimeIndex:
    cal = pd.read_parquet(TRADE_CAL)
    cal["cal_date"] = pd.to_datetime(cal["cal_date"], format="%Y%m%d")
    open_days = cal.loc[cal["is_open"] == 1, "cal_date"]
    mask = (open_days >= pd.Timestamp(start)) & (open_days <= pd.Timestamp(end))
    return pd.DatetimeIndex(open_days.loc[mask].sort_values().tolist())


def cs_rank(s: pd.Series) -> pd.Series:
    """Cross-sectional percentile rank per date; NaN entries excluded from ranking."""
    return s.groupby(level="datetime").rank(pct=True)


def compute_forward_return(adj_close_panel: pd.Series, horizon: int = 5) -> pd.Series:
    """h-day forward simple return computed from adj_close. PIT-safe by construction:
    inputs are observed at t, output is realised over [t, t+h]."""
    g = adj_close_panel.groupby(level="instrument", group_keys=False)
    fwd = g.transform(lambda x: x.shift(-horizon) / x - 1.0)
    return fwd


def ic_summary(signal: pd.Series, fwd_ret: pd.Series, name: str) -> dict:
    """Per-date Pearson and Spearman IC; reports mean, std, ICIR (mean / std)."""
    df = pd.concat([signal.rename("sig"), fwd_ret.rename("fwd")], axis=1).dropna()
    if df.empty:
        return {"name": name, "n_dates": 0}

    def _per_date(g):
        if len(g) < 5 or g["sig"].std() == 0 or g["fwd"].std() == 0:
            return pd.Series({"ic": np.nan, "rank_ic": np.nan})
        return pd.Series({
            "ic": g["sig"].corr(g["fwd"]),
            "rank_ic": g["sig"].rank().corr(g["fwd"].rank()),
        })

    daily = df.groupby(level="datetime").apply(_per_date).dropna()
    return {
        "name": name,
        "n_dates": int(len(daily)),
        "ic_mean": float(daily["ic"].mean()),
        "ic_std": float(daily["ic"].std()),
        "icir": float(daily["ic"].mean() / daily["ic"].std()) if daily["ic"].std() > 0 else 0.0,
        "rank_ic_mean": float(daily["rank_ic"].mean()),
        "rank_ic_std": float(daily["rank_ic"].std()),
        "rank_icir": float(daily["rank_ic"].mean() / daily["rank_ic"].std()) if daily["rank_ic"].std() > 0 else 0.0,
    }


# ── Stage 1: Load universe + features ──────────────────────────────────────
def main() -> int:
    log.info("Run dir: %s", OUT_DIR)

    log.info("Parsing ST ranges from %s", ST_FILE)
    st_ranges = parse_st_ranges(ST_FILE)
    ever_st = sorted(st_ranges.keys())
    log.info("Total stocks ever ST: %d (range rows = %d)",
             len(ever_st), sum(len(v) for v in st_ranges.values()))

    log.info("Initialising Qlib backend at %s", QLIB_DIR)
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D

    try:
        qlib.init(provider_uri=QLIB_DIR, region=REG_CN, kernels=1)
    except Exception:
        log.debug("Qlib already initialised")

    # Trust st_stocks.txt; D.features returns empty data for instruments not in
    # the provider, so a sparse panel is harmless.
    universe = ever_st
    log.info("Universe size (ever ST): %d", len(universe))

    # Build feature expression list
    fields = [
        "Ref($total_mv, 1)",      # market cap (smaller is better)
        "Ref($revenue_q, 1)",     # single-quarter revenue (higher is better)
        "Ref(($close * $adj_factor), 1)",  # for IC fwd-return calc
    ]
    field_names = ["total_mv", "revenue_q", "adj_close"]

    for h in MOM_HORIZONS:
        fields.append(op.momentum(h))
        field_names.append(f"mom_{h}d")

    log.info("Loading %d features for %d instruments from %s to %s",
             len(fields), len(universe), START_DATE, END_DATE)
    t0 = time.time()
    df = D.features(universe, fields, start_time=START_DATE, end_time=END_DATE, freq="day")
    log.info("Loaded panel %s in %.1fs", df.shape, time.time() - t0)
    df.columns = field_names

    # Normalise MultiIndex order to (datetime, instrument) for cross-sectional ranks
    if df.index.names[0] == "instrument":
        df = df.swaplevel().sort_index()
    df.index.names = ["datetime", "instrument"]

    # ── Build ST mask and apply ────────────────────────────────────────────
    log.info("Computing per-(date, instrument) ST mask")
    t0 = time.time()
    st_mask = build_st_mask(df.index, st_ranges)
    log.info("ST mask: %d True / %d total (%.1f%%) in %.1fs",
             st_mask.sum(), len(st_mask), 100.0 * st_mask.mean(), time.time() - t0)

    # Mask non-ST rows to NaN so cross-sectional ranking is over ST stocks only
    df_st = df.where(st_mask, other=np.nan)

    # ── Build forward return for IC diagnostics ────────────────────────────
    log.info("Computing 5d forward return for IC")
    fwd_5d = compute_forward_return(df["adj_close"], horizon=5)  # full universe (ST mask applied later)
    fwd_5d = fwd_5d.where(st_mask, other=np.nan)

    # ── Build composite signals + IC summary ───────────────────────────────
    # Standalone single-factor IC
    ic_rows: list[dict] = []
    for col, sign in [("total_mv", -1), ("revenue_q", +1)]:
        sig = sign * cs_rank(df_st[col])
        ic_rows.append(ic_summary(sig, fwd_5d, f"single::{col}({'+' if sign > 0 else '-'})"))
    for h in MOM_HORIZONS:
        sig = cs_rank(df_st[f"mom_{h}d"])
        ic_rows.append(ic_summary(sig, fwd_5d, f"single::mom_{h}d(+)"))

    # Composite signals (one per horizon + baseline)
    rank_neg_mv = -cs_rank(df_st["total_mv"])  # smaller MV better → negate rank
    rank_rev = cs_rank(df_st["revenue_q"])
    composites: dict[str, pd.Series] = {}
    composites["baseline_mv_rev"] = (rank_neg_mv + rank_rev) / 2.0
    for h in MOM_HORIZONS:
        rank_mom = cs_rank(df_st[f"mom_{h}d"])
        composites[f"mom_{h}d"] = (rank_neg_mv + rank_rev + rank_mom) / 3.0

    for name, sig in composites.items():
        ic_rows.append(ic_summary(sig, fwd_5d, f"composite::{name}"))

    pd.DataFrame(ic_rows).to_csv(OUT_DIR / "ic_summary.csv", index=False)
    log.info("IC summary written → %s/ic_summary.csv", OUT_DIR)

    # ── Backtests ──────────────────────────────────────────────────────────
    log.info("Initialising VectorizedBacktester")
    bt = VectorizedBacktester(qlib_dir=QLIB_DIR)

    summaries: dict[str, dict] = {}
    for name, sig in composites.items():
        log.info("--- Backtest: %s ---", name)
        # Drop NaN entries; required by qlib's TopkDropoutStrategy
        clean = sig.dropna().to_frame("score")
        if clean.empty:
            log.warning("Signal %s is empty after dropna; skipping", name)
            continue
        log.info("  Signal rows: %d, dates: %d, instruments: %d",
                 len(clean),
                 clean.index.get_level_values("datetime").nunique(),
                 clean.index.get_level_values("instrument").nunique())

        t0 = time.time()
        try:
            result = bt.run(
                predictions=clean,
                start_time=START_DATE,
                end_time=END_DATE,
                benchmark=BENCHMARK,
                account=ACCOUNT,
                topk=TOPK,
                n_drop=N_DROP,
                only_tradable=False,
                forbid_all_trade_at_limit=True,
                exchange_kwargs=ST_LIMIT_KWARGS,
            )
        except Exception as e:
            log.exception("Backtest %s failed: %s", name, e)
            summaries[name] = {"error": str(e)}
            continue
        log.info("  Backtest done in %.1fs", time.time() - t0)

        s = result.summary
        summaries[name] = s
        log.info("  Sharpe=%.3f  AnnRet=%.4f  ExcessAnn=%.4f  IR=%.3f  MDD=%.4f  Turnover=%.4f",
                 s.get("sharpe", float("nan")),
                 s.get("annualized_return", float("nan")),
                 s.get("excess_annualized_return", float("nan")),
                 s.get("information_ratio", float("nan")),
                 s.get("max_drawdown", float("nan")),
                 s.get("turnover", float("nan")))

        # Persist per-horizon report + equity curve
        with open(OUT_DIR / "per_horizon" / f"{name}.json", "w", encoding="utf-8") as f:
            json.dump(s, f, indent=2, default=str)
        if result.report is not None and not result.report.empty:
            r = result.report.copy()
            r["net_return"] = r["return"] - r["cost"]
            r["cum_net"] = (1 + r["net_return"]).cumprod()
            r["cum_bench"] = (1 + r["bench"]).cumprod()
            r.to_csv(OUT_DIR / "per_horizon" / f"{name}_eq.csv")

    # ── Summary report ─────────────────────────────────────────────────────
    log.info("Writing summary report")
    rows = []
    for name, s in summaries.items():
        if "error" in s:
            rows.append({"variant": name, "status": "ERROR", "note": s["error"][:80]})
            continue
        rows.append({
            "variant": name,
            "n_days": s.get("n_days"),
            "ann_ret": s.get("annualized_return"),
            "excess_ann": s.get("excess_annualized_return"),
            "sharpe": s.get("sharpe"),
            "info_ratio": s.get("information_ratio"),
            "mdd": s.get("max_drawdown"),
            "win_rate": s.get("win_rate"),
            "turnover": s.get("turnover"),
        })
    summary_df = pd.DataFrame(rows)
    summary_df.to_csv(OUT_DIR / "summary.csv", index=False)

    md_lines = [
        "# ST momentum + market cap + revenue — exploratory validation",
        "",
        f"Run: `{RUN_TS}`  |  Window: {START_DATE} → {END_DATE}  |  TopK={TOPK}, n_drop={N_DROP}",
        f"Universe: ST-only via `st_stocks.txt`  |  Benchmark: `{BENCHMARK}`  |  Capital: ¥{ACCOUNT:,.0f}",
        "",
        "Composite = equal-weight cross-sectional rank of [−market_cap, +revenue_q, +mom_Nd].",
        "Costs: open 5bps / close 15bps; ST limit ±4.5% in $pct_chg.",
        "",
        "## Per-variant backtest summary",
        "",
        summary_df.to_markdown(index=False, floatfmt=".4f") if not summary_df.empty else "(no variants completed)",
        "",
        "## Single-factor and composite IC (5d forward return)",
        "",
    ]
    ic_df = pd.read_csv(OUT_DIR / "ic_summary.csv")
    if not ic_df.empty:
        cols = ["name", "n_dates", "ic_mean", "icir", "rank_ic_mean", "rank_icir"]
        cols = [c for c in cols if c in ic_df.columns]
        md_lines.append(ic_df[cols].to_markdown(index=False, floatfmt=".4f"))
    md_lines.append("")
    md_lines.append("## Files")
    md_lines.append("- `summary.csv` — variant-level metrics")
    md_lines.append("- `ic_summary.csv` — single-factor and composite IC")
    md_lines.append("- `per_horizon/<name>.json` — full backtest summary per variant")
    md_lines.append("- `per_horizon/<name>_eq.csv` — daily return / cost / bench / cum series")

    (OUT_DIR / "summary.md").write_text("\n".join(md_lines), encoding="utf-8")
    log.info("Done. Report → %s/summary.md", OUT_DIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
