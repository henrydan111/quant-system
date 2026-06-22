"""果仁 PARITY ladder — rung 1: sm_纯市值01 (pure smallest-market-cap microcap).

果仁 = TRUSTED BENCHMARK; this LOCAL reproduction must MATCH it (system-integrity check,
NOT strategy re-validation). A close match validates local 市值 data + universe + PIT +
event-driven engine; a divergence localizes a LOCAL bug.

果仁 TARGET (from 11_sm_纯市值01.xlsx 收益统计 / 年度收益统计):
  annual 66.18% | Sharpe 1.71 (rf=4%) | MDD 48.21% | vol 36.28% | ~11.3 holdings | turnover 1026%/yr | ~98% invested
  yearly: 2014+146% 2015+690% 2016+43% 2017-9% 2018+7% 2019+64% 2020+95%
          2021+61% 2022+18% 2023+79% 2024+25% 2025+69% 2026-10%

果仁 RULES reproduced EXACTLY for parity (NOT realism — matching under realistic microcap
cost would itself be a bug, since 果仁 models none):
  universe : all A-shares, exclude ST, exclude 科创板(688/689); 不过滤停牌
  filters  : 5d avg amount > 0.05亿 (>5000 千元); 上市天数>20 (proxy: >=20 trailing days w/ data)
  ranking  : rank(总市值 asc) + rank(流通市值 asc), equal weight -> smallest combined cap
  model II : buy rank<=10 / sell rank>=15 / hold 11-14  ~ RankedFallbackStrategy(topk=11)
  cost     : flat 0.2%/side, NO slippage, NO stamp/过户费 (果仁 FAQ:59)
  fill     : 09:35 ~ open ; total return (EventDriven credits dividends)

KNOWN parity gaps (v1, to refine if they move the result): 果仁风险预警25版/重大违规 filters
approximated by the ST set only; gold-ETF idle-cash ignored (strategy ~98% invested);
RankedFallback sell-trigger (rank>11) is tighter than 果仁's rank>=15 band -> mild excess turnover.

Usage:
  python workspace/scripts/guorn_parity_rung1_purecap.py --build-panel --start 2014-01-01 --end 2026-06-20
  python workspace/scripts/guorn_parity_rung1_purecap.py --run --start 2014-01-01 --end 2026-06-20 --cadence weekly --topk 11
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "workspace" / "research" / "long_only_50cagr"))
sys.path.insert(0, str(ROOT / "workspace" / "research" / "jq_replication"))
sys.stdout.reconfigure(encoding="utf-8")

import research_utils as ru          # noqa: E402
from jq_rep_utils import board_of    # noqa: E402
from src.backtest_engine.event_driven.strategy import Strategy  # noqa: E402

OUT = ROOT / "workspace" / "outputs" / "guorn_parity"
OUT.mkdir(parents=True, exist_ok=True)
PANEL = OUT / "mktcap_panel.parquet"
FIELDS = ["$total_mv", "$circ_mv", "$amount", "$close"]


def _load_listed_bounds() -> dict:
    """{qlib_code -> (list_start, delist_end)} from the range-form all_stocks.txt
    (the provider's survivorship-free universe with delist boundaries). Used to
    DROP a name once it has delisted — the ffill below would otherwise reanimate
    a delisted name for up to 60d (GPT cross-review Blocker-2)."""
    p = ROOT / "data" / "qlib_data" / "instruments" / "all_stocks.txt"
    df = pd.read_csv(p, sep="\t", header=None, names=["code", "start", "end"], dtype=str)
    return {str(r.code).upper(): (pd.Timestamp(r.start), pd.Timestamp(r.end))
            for r in df.itertuples(index=False)}


LISTED_BOUNDS = _load_listed_bounds()

# 果仁 yearly strategy returns (年度收益统计) for the diff
GR_YEARLY = {2014: 1.4642, 2015: 6.8959, 2016: 0.4268, 2017: -0.0919, 2018: 0.0706,
             2019: 0.6408, 2020: 0.9514, 2021: 0.6078, 2022: 0.1820, 2023: 0.7866,
             2024: 0.2533, 2025: 0.6897, 2026: -0.0993}
GR_HEADLINE = dict(annual=0.6618, sharpe=1.71, mdd=0.4821, vol=0.3628, holdings=11.34, turnover=10.26)


def build_panel(start: str, end: str) -> pd.DataFrame:
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=str(ROOT / "data" / "qlib_data"), region=REG_CN, kernels=1)
    insts = D.list_instruments(D.instruments("all"), start_time=start, end_time=end, as_list=True)
    print(f"[panel] {len(insts)} instruments {start}..{end} — fetching {FIELDS}", flush=True)
    df = D.features(insts, FIELDS, start_time=start, end_time=end, freq="day")
    df.columns = ["total_mv", "circ_mv", "amount", "close"]
    df = df.sort_index()
    df.to_parquet(PANEL)
    print(f"[panel] saved {PANEL}  shape={df.shape}", flush=True)
    return df


def _rebal_dates(start: str, end: str, cadence: str) -> pd.DatetimeIndex:
    cal = ru.trading_calendar()
    cal = cal[(cal >= pd.Timestamp(start)) & (cal <= pd.Timestamp(end))]
    if cadence == "daily":
        return cal
    period = "W" if cadence == "weekly" else "M"
    grp = cal.to_period(period)
    first = pd.Series(cal, index=grp).groupby(level=0).first()
    return pd.DatetimeIndex(sorted(first.values))


def build_schedule(panel: pd.DataFrame, rebal: pd.DatetimeIndex, topk: int,
                   *, headroom_mult: int = 3, amt_min_kcny: float = 5000.0, min_hist: int = 20,
                   low_price_min: float = 1.0):
    """{rebalance_date -> [dot-form codes]} ranked smallest combined市值, + mean topk turnover.
    Ranks on the PREV trading day (PIT-safe for a 09:35 fill).

    Faithfulness fixes (2026-06-22, vs 果仁 sm_纯市值01):
      - 市值 forward-filled so a SUSPENDED held name keeps its last-known rank (果仁 carries it),
        guarded by an `alive` mask (must have traded within 60d) so a DELISTED name does NOT leak.
      - 5d-avg-amount averages over TRADING days only (skip suspended NaN), like 果仁.
      - best-effort 退市风险 atoms (reproducible subset of 果仁风险预警25版): exclude ST/退市
        (st_stocks), 上市天数<=20, and 低价/面值退市 (close <= low_price_min, default ¥1).
        Irreducible (proprietary, no local data): 年报公布逾期 + 重大事项违规处罚 + 严格"预期ST"口径.
        (The 国九条 atoms are 2024+ rules → ~0 effect on pre-2024 windows.)"""
    close_raw = panel["close"].unstack(level=0)
    close = close_raw.ffill()                                    # last-known close through suspension
    tmv = panel["total_mv"].unstack(level=0).ffill()            # carry 市值 through suspension
    cmv = panel["circ_mv"].unstack(level=0).ffill()
    amt5 = panel["amount"].unstack(level=0).rolling(5, min_periods=1).mean()   # avg TRADING days
    hist = close_raw.notna().rolling(min_hist, min_periods=1).sum()            # listing-age (real trading days)
    cal = close.index
    headroom = topk * headroom_mult

    def _listed(code: str, day: pd.Timestamp) -> bool:
        # EXPLICIT delist boundary (GPT Blocker-2): the ffill above would otherwise
        # reanimate a delisted name. A name is tradable only on/before its delist end.
        b = LISTED_BOUNDS.get(str(code).upper())
        return b is not None and day <= b[1]

    sched: dict = {}
    members: dict = {}
    for d in rebal:
        d = pd.Timestamp(d)
        pos = cal.searchsorted(d)
        if pos == 0:
            sched[d] = []
            continue
        pday = cal[pos - 1]                       # prev trading day = PIT rank basis
        df = pd.DataFrame({"tmv": tmv.loc[pday], "cmv": cmv.loc[pday], "close": close.loc[pday],
                           "amt5": amt5.loc[pday], "hist": hist.loc[pday]}).dropna(subset=["tmv", "cmv"])
        st = ru.st_codes_on(d)
        # 果仁 sm_纯市值01 universe = 沪深主板 + 创业板 ONLY (holdings detail: 0 北证, 0 科创板).
        # board_of fixed 2026-06-22: 北证 920xxx -> "bse" (was mis-tagged "bshare"; excluded
        # either way), AND 创业板 302xxx -> "chinext" (was "other" -> silently DROPPED).
        # _listed(c, pday) drops names already delisted as of the rank day (Blocker-2).
        keep = df.index.map(lambda c: board_of(c) in ("main", "chinext")
                            and c.upper() not in st and _listed(c, pday))
        df = df[list(keep)]
        df = df[(df["amt5"] > amt_min_kcny) & (df["hist"] >= min_hist)
                & (df["close"] > low_price_min)]
        if df.empty:
            sched[d] = []
            continue
        score = df["tmv"].rank() + df["cmv"].rank()          # ascending: smallest = lowest score
        ranked = score.sort_values().head(headroom)
        sched[d] = [str(c).upper().replace("_", ".") for c in ranked.index]
        members[d] = set(ranked.head(topk).index)
    keys = sorted(members)
    churn = [len(members[keys[i]] - members[keys[i - 1]]) / max(len(members[keys[i]]), 1)
             for i in range(1, len(keys)) if members[keys[i]]]
    return sched, (float(np.mean(churn)) if churn else float("nan"))


def sample_schedule(panel: pd.DataFrame, rebal: pd.DatetimeIndex, topk: int, n: int = 3):
    """Data sanity: print the smallest-市值 selection on a few dates (before any engine run)."""
    sched, churn = build_schedule(panel, rebal, topk)
    tmv = panel["total_mv"].unstack(level=0)
    keys = [k for k in sorted(sched) if sched[k]]
    picks = keys[:: max(1, len(keys) // n)][:n]
    print(f"\n[sanity] {len(keys)}/{len(rebal)} rebalances non-empty; mean topk turnover/period = {churn:.3f}")
    for d in picks:
        codes = sched[d][:topk]
        pos = tmv.index.searchsorted(d)
        caps = tmv.loc[tmv.index[pos - 1], [c.replace(".", "_") for c in codes]]
        print(f"  {d.date()}  top{topk} smallest总市值(亿): " +
              ", ".join(f"{c}={v/1e4:.1f}" for c, v in zip(codes, caps.values)))
    return sched, churn


class ModelIIStrategy(Strategy):
    """Faithful 果仁 model-II rotation — hold winners in a rank band, rotate laggards.

    Mirrors sm_纯市值01's trade model so the EXECUTION layer matches 果仁 exactly
    (not just the factor): daily, open(09:35) fill, and
      - BUY new names ranked <= buy_rank (10), equal-weighting the freed/idle cash;
      - SELL held names that fall to rank >= sell_rank (15);
      - HOLD names ranked 1..sell_rank-1 at their DRIFTED weight (NOT trimmed back
        to equal weight — winners run), capped at pos_max (15%);
      - limit handling is the engine's job at fill (open-based can_buy/can_sell).

    Contrast RankedFallbackStrategy: it rebalances to strict equal weight every
    period (`_emit_rebalance_orders` trims over-allocated = sells winners), which
    cost ~half the 2015 bull-year return vs 果仁. model-II keeps them.
    """

    def __init__(self, ranked_schedule, *, buy_rank: int = 10, sell_rank: int = 15,
                 target_n: int = 11, pos_max: float = 0.15):
        super().__init__()
        self.ranked_schedule = {pd.Timestamp(d): tuple(c) for d, c in ranked_schedule.items()}
        self.buy_rank, self.sell_rank = int(buy_rank), int(sell_rank)
        self.target_n, self.pos_max = int(target_n), float(pos_max)

    def initialize(self, context):
        return None

    def on_bar(self, context):
        return []

    def after_market_close(self, context):
        return None

    def before_market_open(self, context):
        from src.backtest_engine.event_driven.strategies import _emit_rebalance_orders
        ranked = self.ranked_schedule.get(pd.Timestamp(context.date))
        if not ranked:
            return []
        rank_of = {c: i + 1 for i, c in enumerate(ranked)}
        BIG = 10 ** 9
        held = dict(context.portfolio.positions)
        prices: dict = {}
        prev = context.prev_day_data
        if prev is not None and not prev.empty:
            prices = prev.set_index("ts_code")["close"].astype(float).to_dict()

        def _px(code: str) -> float:
            # NaN-safe (GPT Major-4): a suspended held name has a NaN prev close;
            # prices.get(code, avg_cost) returns the NaN, not the fallback.
            p = prices.get(code)
            if p is None or not np.isfinite(p) or p <= 0:
                p = held[code].avg_cost
            return float(p) if (p is not None and np.isfinite(p) and p > 0) else 0.0

        total = context.portfolio.total_value(prices)
        if total <= 0:
            total = context.portfolio.cash
        cur_w = ({c: held[c].shares * _px(c) / total for c in held} if total > 0 else {})
        # KEEP held names still inside the band (rank < sell_rank), at drifted weight capped at pos_max
        target = {c: min(cur_w.get(c, 0.0), self.pos_max)
                  for c in held if rank_of.get(c, BIG) < self.sell_rank}
        # BUY new names rank <= buy_rank, not held, to fill up to target_n holdings.
        # Each new buy is equal-weight of the residual BUT capped at pos_max (GPT Major-3):
        # with few buys + much freed cash, residual/len(buys) could otherwise exceed 15%.
        n_slots = max(0, self.target_n - len(target))
        buys = [c for c in ranked if rank_of[c] <= self.buy_rank and c not in held][:n_slots]
        residual = max(0.0, 1.0 - sum(v for v in target.values() if pd.notna(v)))
        remaining = len(buys)
        for c in buys:
            if residual <= 0 or remaining <= 0:
                break
            w = min(self.pos_max, residual / remaining)
            if w > 0:
                target[c] = w
                residual -= w
            remaining -= 1
        return _emit_rebalance_orders(target, context)


def run(start: str, end: str, cadence: str, topk: int, model: str = "model2"):
    from src.backtest_engine.event_driven import EventDrivenBacktester, CostConfig
    from src.backtest_engine.event_driven.exchange import FixedSlippage
    from src.backtest_engine.event_driven.strategies import RankedFallbackStrategy

    panel = pd.read_parquet(PANEL)
    # slice to the run window (+90d lookback for the rolling filters) BEFORE the unstack — big speedup
    dt = panel.index.get_level_values(1)
    lo, hi = pd.Timestamp(start) - pd.Timedelta(days=90), pd.Timestamp(end)
    panel = panel[(dt >= lo) & (dt <= hi)]
    rebal = _rebal_dates(start, end, cadence)
    print(f"[run] cadence={cadence} rebalances={len(rebal)} topk={topk}  {start}..{end}  panel_rows={len(panel)}", flush=True)
    sched, churn = sample_schedule(panel, rebal, topk)

    if model == "model2":
        strat = ModelIIStrategy(sched, buy_rank=10, sell_rank=15, target_n=topk)
    else:
        strat = RankedFallbackStrategy(sched, topk=topk)
    print(f"[run] strategy={model} ({type(strat).__name__})", flush=True)

    guoren_cost = CostConfig(buy_commission=0.002, sell_commission=0.002, stamp_tax=0.0,
                             min_commission=0.0, transfer_fee=0.0)
    bt = EventDrivenBacktester(data_dir=str(ROOT / "data"))
    res = bt.run(strategy=strat, start_time=start, end_time=end,
                 benchmark="000300.SH", account=1_000_000.0, exchange_config=guoren_cost,
                 slippage=FixedSlippage(0.0), volume_limit=0.10,
                 preload_fields=["$open", "$close", "$high", "$low", "$vol", "$amount", "$pre_close", "$adj_factor"])
    rep = res.report.copy()
    if "date" in rep.columns:
        rep = rep.set_index(pd.to_datetime(rep["date"]))
    net = rep["return"].astype(float)
    net.to_frame("net").to_parquet(OUT / f"rung1_net_{cadence}.parquet")
    rep.to_parquet(OUT / f"rung1_report_{cadence}.parquet")
    dh = getattr(res, "daily_holdings", None)
    if dh is not None and not dh.empty:
        dh.to_parquet(OUT / f"rung1_holdings_{cadence}.parquet")   # for the holding-level diff vs 果仁
    print(f"[report] columns = {list(rep.columns)}", flush=True)
    for pc in ("position", "invested", "stock_weight", "cash_weight", "cash", "stock_value", "value", "total_value", "n_positions", "n_holdings", "holdings"):
        if pc in rep.columns:
            s = pd.to_numeric(rep[pc], errors="coerce")
            yr_mean = " ".join(f"{int(y)}:{v:.2f}" for y, v in s.groupby(rep.index.year).mean().items())
            print(f"[report] {pc}: mean={s.mean():.3f}  by_year={yr_mean}", flush=True)

    m = ru.goal_metrics(net)
    m["sharpe_rf4"] = ru.sharpe(net, rf=0.04)                 # 果仁 uses rf=4%
    yr = net.groupby(net.index.year).apply(lambda r: (1 + r).prod() - 1)
    yearly = {int(y): float(v) for y, v in yr.items()}

    print("\n" + "=" * 78)
    print(f"  LOCAL  annual≈{m['cagr']:+.2%}  Sharpe(rf0)={m['sharpe']:.2f}  Sharpe(rf4%)={m['sharpe_rf4']:.2f}  "
          f"MDD={m['mdd']:+.2%}  vol={m['ann_vol']:.2%}  turnover/period={churn:.3f}")
    print(f"  果仁   annual={GR_HEADLINE['annual']:+.2%}  Sharpe(rf4%)={GR_HEADLINE['sharpe']:.2f}              "
          f"        MDD={-GR_HEADLINE['mdd']:+.2%}  vol={GR_HEADLINE['vol']:.2%}  ~11.3 holds, ~10.3x/yr")
    print("  year     LOCAL      果仁     diff")
    for y in sorted(yearly):
        g = GR_YEARLY.get(y)
        gtxt = f"{g:+7.1%}" if g is not None else "   n/a "
        dtxt = f"{yearly[y]-g:+7.1%}" if g is not None else ""
        print(f"  {y}   {yearly[y]:+8.1%}  {gtxt}  {dtxt}")
    out = dict(local=m, local_yearly=yearly, guoren_headline=GR_HEADLINE, guoren_yearly=GR_YEARLY,
               cadence=cadence, topk=topk, model=model, turnover_per_period=churn, start=start, end=end)
    (OUT / f"rung1_result_{cadence}.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    # GPT Major-5: a machine-readable NON-FORMAL stamp so these outputs can't be
    # misread later as a formal / realistic-cost / sealed-OOS strategy validation.
    meta = {
        "artifact_type": "guorn_parity_reproduction",
        "strategy": "sm_纯市值01",
        "purpose": "validate local data/ranking/execution core against the 果仁 benchmark",
        "formal_eligible": False,
        "strategy_validation": False,
        "sealed_oos_claim": False,
        "oos_spend_status": "not_a_sealed_oos; full 果仁 benchmark window observed",
        "cost_model": "果仁 parity: 0.2%/side, no stamp, no transfer fee, zero slippage",
        "realistic_cost_claim": False,
        "execution_profile": "guorn_optimistic_open_parity",
        "known_irreducible_deltas": [
            "果仁 proprietary 退市风险 atoms (年报公布逾期 / 重大事项违规处罚 / 严格预期ST) not locally available",
            "果仁 09:35/open fill approximated by daily raw_open (no minute data)",
        ],
    }
    (OUT / f"rung1_metadata_{cadence}.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nNON-FORMAL PARITY ARTIFACT: validates shared data/ranking/execution mechanics only; "
          "NOT deployable strategy alpha, NOT realistic-cost, NOT a sealed-OOS validation.")
    print(f"saved -> {OUT / f'rung1_result_{cadence}.json'}  (+ rung1_metadata_{cadence}.json)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-panel", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--start", default="2014-01-01")
    ap.add_argument("--end", default="2026-06-20")
    ap.add_argument("--cadence", default="daily", choices=["daily", "weekly", "monthly"])  # 果仁=daily
    ap.add_argument("--topk", type=int, default=11)
    ap.add_argument("--model", default="model2", choices=["model2", "fallback"])  # model2 = faithful 果仁
    args = ap.parse_args()
    if args.build_panel:
        build_panel(args.start, args.end)
    if args.run:
        run(args.start, args.end, args.cadence, args.topk, args.model)


if __name__ == "__main__":
    main()
