"""果仁 PARITY ladder — rung 2: sm_noc_纯市值正盈利_v4 (nn=16).

Rung-1 (sm_纯市值01) validated 市值 data + universe + PIT-prev-day rank + the
event-driven engine + execution. Rung-2 adds exactly ONE new alpha-relevant
element on top of that validated core: the PIT INCOME-STATEMENT earnings gate
``净利润(单季) > 0``. A close match therefore validates the local PIT financial-
statement serving (the provider's effective-date-anchored ``$n_income_sq_q0``);
a divergence localizes to that path. 果仁 = TRUSTED BENCHMARK; LOCAL is UNDER TEST.

PIT field path (validated at the holding level, 96.1% within 0.1% across 14,736
果仁 holdings — see _validate_pit_netprofit_vs_guorn.py): 果仁's plain 净利润(单季)
= TOTAL single-quarter net profit = provider ``$n_income_sq_q0`` (NOT 归母). The
``_sq_q0`` single-quarter alias is a PROVIDER-materialized bin (read via D.features,
the factor-library path) — NOT a raw pit_ledger column. The fundamental gate reads it
AS-OF THE REBALANCE DAY: PIT-safe because the provider anchors the alias on
``effective_date > disclosure`` STRICTLY (§3.2), so as-of-d already excludes anything
disclosed on d and only sees reports tradeable at d's open. This matches 果仁's 公告日
selection (an over-conservative prev-day/Ref(,1) gate wrongly dropped 52/14,736
果仁-held names — GPT R1 Major-1). Market data (rank/filters) still uses the prev day.

果仁 TARGET (16_sm_noc_纯市值正盈利_v4.xlsx 收益统计/年度收益统计):
  annual 60.00% | Sharpe 1.71 (rf=4%) | MDD 35.49% | vol 32.82% | ~5.03 holds | turnover 1829%/yr | ~94% invested
  yearly: 2014+108 2015+515 2016+61 2017-9 2018-7 2019+40 2020+35 2021+69 2022+82 2023+53 2024+82 2025+39 2026-11

果仁 RULES reproduced for parity (the income gate + universe verified vs the xlsx 各阶段持仓详单;
the DEFAULT --exits off run is the RUNG-2 ISOLATION BASELINE, NOT a full-recipe reproduction — see EXITS):
  universe : 中小板(旧) = codes 002xxx + 003xxx ONLY (ground-truth: 100% of held names), exclude ST, 过滤停牌=是
  filters  : 净利润(单季)>0 (PIT $n_income_sq_q0, as-of rebalance day); 5d & 20d avg amount > 0.05亿 (>5000千元);
             上市天数>20; 退市风险_v1(2) reproducible atoms = ST + 收盘价>=2
  ranking  : rank(总市值 asc) ONLY (smallest 总市值) — NOT +流通市值
  model II : sell rank>=8 / hold 1..7; pos 14-26% (~5 holds); 备选 5; daily; 09:35~open. The local sizing is an
             EQUAL-WEIGHT-WITHIN-BAND APPROXIMATION of 果仁's 14-26% band (果仁 weight-level data not used to fit it).
  exits    : 买入后涨幅>=100% (TP), 跌幅>=18% (stop), 最高点跌幅>=18% (trailing); 距上次卖出>=10 (no-rebuy).
             --exits off is the BASELINE: 果仁's price-exits empirically ~never bind (15,233 segments:
             frac(seg-ret<=-18%)=0.000, frac(>=+100%)=0.000) so the book is rank-rotation model-II. NOTE (GPT
             R1 correction): the exits are NOT "PIT-incompatible" — the 09:35/open price IS knowable to the
             ENGINE at fill time (like the fill-price-aware limit gate); they are only un-implementable inside
             before_market_open (strategy pre-open). Faithful exits = execution-time conditional orders evaluated
             by the engine against the fill price (future work), NOT strategy-side same-day reads. --exits on is a
             pre-open APPROXIMATION (prev-close eval) that over-fires; do NOT read it as the faithful recipe.
  cost     : flat 0.3%/side (guorn cache-bug export caveat), NO slippage, NO stamp/过户费 ; total return

IRREDUCIBLE deltas (documented, like rung-1's 退市风险 ceiling):
  - 未来20日新增流通股占比<1% : 果仁 PIT lockup/placement screen; no clean local PIT feed. SKIPPED
    (reproducing it with realized forward shares would be LOOKAHEAD — not allowed). Near-always satisfied
    in the holdings (max 0.94%), so small effect.
  - 退市风险_v1(2) proprietary atoms (预期ST2021 / 果仁风险预警25版 / 重大违规) : no local data (= rung-1).

Usage:
  python workspace/scripts/guorn_parity_rung2_posprofit.py --build-gate --start 2014-01-01 --end 2026-06-20
  python workspace/scripts/guorn_parity_rung2_posprofit.py --run --start 2014-01-01 --end 2026-06-20 --exits on
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
from src.backtest_engine.event_driven.strategy import Strategy  # noqa: E402

OUT = ROOT / "workspace" / "outputs" / "guorn_parity"
OUT.mkdir(parents=True, exist_ok=True)
PANEL = OUT / "mktcap_panel.parquet"                 # reused from rung-1 (total_mv/circ_mv/amount/close)
GATE = OUT / "profit_gate_panel.parquet"             # rung-2: $n_income_sq_q0 wide (datetime x qlib code)
GATE_FIELD = "$n_income_sq_q0"                        # TOTAL single-quarter net profit (validated vs 果仁)
UNIVERSE_PREFIXES = ("002", "003")                   # 中小板(旧) — ground-truth from nn=16 holdings

# 果仁 nn=16 yearly strategy returns (年度收益统计 策略收益) + headline (收益统计 本策略)
GR_YEARLY = {2014: 1.0822, 2015: 5.1526, 2016: 0.6057, 2017: -0.0934, 2018: -0.0695,
             2019: 0.4003, 2020: 0.3514, 2021: 0.6869, 2022: 0.8163, 2023: 0.5345,
             2024: 0.8220, 2025: 0.3902, 2026: -0.1076}
GR_HEADLINE = dict(annual=0.6000, sharpe=1.71, mdd=0.3549, vol=0.3282, holdings=5.03, turnover=18.29)


def _load_listed_bounds() -> dict:
    p = ROOT / "data" / "qlib_data" / "instruments" / "all_stocks.txt"
    df = pd.read_csv(p, sep="\t", header=None, names=["code", "start", "end"], dtype=str)
    return {str(r.code).upper(): (pd.Timestamp(r.start), pd.Timestamp(r.end))
            for r in df.itertuples(index=False)}


LISTED_BOUNDS = _load_listed_bounds()


def _in_universe(qlib_code: str) -> bool:
    return qlib_code.split("_")[0][:3] in UNIVERSE_PREFIXES


def build_gate_panel(start: str, end: str) -> pd.DataFrame:
    """Provider PIT single-quarter net profit (the factor-library path) for the
    中小板 universe, wide (datetime x qlib code). Cached. PIT-anchored on
    effective_date by the backend builder (effective_date > disclosure STRICTLY, §3.2);
    the gate reads this AS-OF THE REBALANCE DAY — as-of-d already excludes anything
    disclosed on d, so it is NOT a same-day raw read. Market-data ranks/filters use the
    prev day (d's close is unknown at d's 09:35 open)."""
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=str(ROOT / "data" / "qlib_data"), region=REG_CN, kernels=1)
    allinsts = D.list_instruments(D.instruments("all"), start_time=start, end_time=end, as_list=True)
    insts = [c for c in allinsts if _in_universe(c)]
    print(f"[gate] {len(insts)} 中小板(002/003) instruments — fetching {GATE_FIELD} {start}..{end}", flush=True)
    df = D.features(insts, [GATE_FIELD], start_time=start, end_time=end, freq="day")
    wide = df.iloc[:, 0].unstack(level=0).sort_index()    # (instrument,datetime) -> datetime x instrument
    wide.to_parquet(GATE)
    print(f"[gate] saved {GATE}  shape={wide.shape}", flush=True)
    return wide


def _rebal_dates(start: str, end: str, cadence: str) -> pd.DatetimeIndex:
    cal = ru.trading_calendar()
    cal = cal[(cal >= pd.Timestamp(start)) & (cal <= pd.Timestamp(end))]
    if cadence == "daily":
        return cal
    period = "W" if cadence == "weekly" else "M"
    grp = cal.to_period(period)
    first = pd.Series(cal, index=grp).groupby(level=0).first()
    return pd.DatetimeIndex(sorted(first.values))


def build_schedule(panel: pd.DataFrame, profit: pd.DataFrame, rebal: pd.DatetimeIndex, *,
                   headroom: int = 30, amt_min_kcny: float = 5000.0, min_hist: int = 20,
                   low_price_min: float = 2.0, sell_rank: int = 8):
    """{rebalance_date -> [dot-form codes]} ranked smallest 总市值, + mean topk turnover.
    Ranks + gates on the PREV trading day (PIT-safe for a 09:35 fill).

    nn=16 faithfulness:
      - universe = 002/003 only (中小板旧, ground-truth), exclude ST, drop delisted (_listed).
      - 过滤停牌=是: a name SUSPENDED on the rank day (raw close NaN) is excluded from selection.
      - 净利润(单季)>0 PIT gate via provider $n_income_sq_q0 AS-OF THE REBALANCE DAY (NaN -> excluded);
        PIT-safe via the provider's strict effective_date>disclosure anchor (NOT a same-day raw read),
        and faithful to 果仁's 公告日 selection. Gating on the prev day (Ref,1) over-dropped 52/14,736
        果仁-held names whose report became effective ON d (GPT R1 Major-1).
      - 5d AND 20d avg amount > 5000千元 (trading-day average); 上市天数>=20; 收盘价>=2 (退市风险_v1(2) atom).
      - rank = 总市值 ascending ONLY (weight irrelevant, single key)."""
    close_raw = panel["close"].unstack(level=0)
    close = close_raw.ffill()
    tmv = panel["total_mv"].unstack(level=0).ffill()
    amt = panel["amount"].unstack(level=0)
    amt5 = amt.rolling(5, min_periods=1).mean()
    amt20 = amt.rolling(20, min_periods=1).mean()
    hist = close_raw.notna().rolling(min_hist, min_periods=1).sum()
    profit = profit.reindex(close.index).ffill()           # daily PIT value, carried across any gap
    cal = close.index

    def _listed(code: str, day: pd.Timestamp) -> bool:
        # GPT R1 Minor-2: bound BOTH ends — a name is tradable only between its list
        # start and delist end (the hist>=20 + non-NaN-close filters already keep
        # pre-list names out, but bound the lower end explicitly for hygiene).
        b = LISTED_BOUNDS.get(str(code).upper())
        return b is not None and b[0] <= day <= b[1]

    sched: dict = {}
    members: dict = {}
    for d in rebal:
        d = pd.Timestamp(d)
        pos = cal.searchsorted(d)
        if pos == 0:
            sched[d] = []
            continue
        pday = cal[pos - 1]
        # MARKET data (rank/filters) uses the PREV day — d's close is unknown at d's 09:35 open.
        # FUNDAMENTAL gate (净利润) uses AS-OF THE REBALANCE DAY d (lag-0), which is PIT-safe AND
        # faithful to 果仁: the provider's $n_income_sq_q0 is effective-date-anchored
        # (effective_date > disclosure STRICTLY, §3.2), so as-of-d already EXCLUDES anything
        # disclosed on d and only includes reports tradeable at d's open — the same info set as the
        # pday close. Gating on pday instead (Ref,1) was over-conservative vs 果仁's 公告日 selection
        # and wrongly dropped 52/14,736 果仁-held names whose report became effective ON d (GPT R1
        # Major-1; rung2_pit_validation.json). Both lags are penny-exact on field identity.
        prow = profit.loc[d] if d in profit.index else pd.Series(dtype=float)
        df = pd.DataFrame({
            "tmv": tmv.loc[pday], "rawclose": close_raw.loc[pday], "close": close.loc[pday],
            "amt5": amt5.loc[pday], "amt20": amt20.loc[pday], "hist": hist.loc[pday],
            "np_q": prow.reindex(tmv.columns),
        }).dropna(subset=["tmv"])
        st = ru.st_codes_on(d)
        keep = df.index.map(lambda c: _in_universe(c) and c.upper() not in st and _listed(c, pday))
        df = df[list(keep)]
        # 过滤停牌=是: exclude names suspended on the rank day (no raw close)
        df = df[df["rawclose"].notna()]
        # filters + PIT earnings gate (NaN net profit -> NOT > 0 -> excluded)
        df = df[(df["amt5"] > amt_min_kcny) & (df["amt20"] > amt_min_kcny)
                & (df["hist"] >= min_hist) & (df["close"] >= low_price_min)
                & (df["np_q"] > 0)]
        if df.empty:
            sched[d] = []
            continue
        ranked = df["tmv"].rank().sort_values().head(headroom)   # smallest 总市值 only
        sched[d] = [str(c).upper().replace("_", ".") for c in ranked.index]
        members[d] = set(list(ranked.index)[:sell_rank])
    keys = sorted(members)
    churn = [len(members[keys[i]] - members[keys[i - 1]]) / max(len(members[keys[i]]), 1)
             for i in range(1, len(keys)) if members[keys[i]]]
    return sched, (float(np.mean(churn)) if churn else float("nan"))


class ModelIIPosProfitStrategy(Strategy):
    """Faithful nn=16 model-II with 果仁's price-based exits + no-rebuy cooldown.

    Each daily rebalance (before_market_open, prev-day-only data):
      - decrement rebuy cooldowns (距离上次卖出天数);
      - EXITS (force-sell regardless of rank): 买入后涨幅>=tp / 跌幅>=sl / 最高点跌幅>=trail,
        evaluated on prev-day close vs cost-basis (entry) and vs running peak;
      - KEEP held names ranked < sell_rank (8) and not exited, at drifted weight capped pos_max;
        a SUSPENDED held name (NaN prev close, 不卖条件 选股日停牌) is carried regardless of rank;
      - BUY top-ranked (<= buy_rank) not-held, not-in-cooldown names to fill target_n, capped pos_max.
    Exits OFF (--exits off) = the pure model-II band, to isolate the exits' contribution.
    """

    def __init__(self, ranked_schedule, *, buy_rank: int = 7, sell_rank: int = 8,
                 target_n: int = 5, pos_max: float = 0.26,
                 tp: float = 1.00, sl: float = 0.18, trail: float = 0.18,
                 rebuy_cooldown: int = 10, use_exits: bool = True, max_holds: int | None = None):
        super().__init__()
        self.ranked_schedule = {pd.Timestamp(d): tuple(c) for d, c in ranked_schedule.items()}
        self.buy_rank, self.sell_rank = int(buy_rank), int(sell_rank)
        self.target_n, self.pos_max = int(target_n), float(pos_max)
        self.max_holds = int(max_holds) if max_holds else None   # 果仁 最大持仓数 cap (None = no cap, rung-2 default)
        self.tp, self.sl, self.trail = float(tp), float(sl), float(trail)
        self.rebuy_cooldown, self.use_exits = int(rebuy_cooldown), bool(use_exits)
        self.peak: dict = {}        # code -> running max prev-close since entry
        self.cooldown: dict = {}    # code -> trading days remaining before rebuy allowed
        self.sell_reasons = {"rank": 0, "tp": 0, "sl": 0, "trail": 0}   # diagnostic counters

    def initialize(self, context):
        return None

    def on_bar(self, context):
        return []

    def after_market_close(self, context):
        return None

    def before_market_open(self, context):
        from src.backtest_engine.event_driven.strategies import _emit_rebalance_orders
        # cooldown ticks every trading day (调仓周期=1)
        for c in list(self.cooldown):
            self.cooldown[c] -= 1
            if self.cooldown[c] <= 0:
                del self.cooldown[c]
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

        def _pxraw(code):
            p = prices.get(code)
            return float(p) if (p is not None and np.isfinite(p) and p > 0) else None

        # update running peak for held names; drop peaks for names no longer held
        for c in list(self.peak):
            if c not in held:
                self.peak.pop(c, None)
        for c in held:
            pc = _pxraw(c)
            if pc is not None:
                self.peak[c] = max(self.peak.get(c, pc), pc)

        def _exit_reason(c):
            if not self.use_exits:
                return None
            pc = _pxraw(c)
            if pc is None:                   # suspended -> can't evaluate / can't trade; carry
                return None
            entry = held[c].avg_cost
            if entry is None or not np.isfinite(entry) or entry <= 0:
                return None
            r_e = pc / entry - 1.0
            pk = self.peak.get(c, pc)
            r_p = pc / pk - 1.0 if pk > 0 else 0.0
            if r_e >= self.tp:
                return "tp"
            if r_e <= -self.sl:
                return "sl"
            if r_p <= -self.trail:
                return "trail"
            return None

        def _suspended(c):
            return _pxraw(c) is None

        # KEEP held names still in the band (rank<sell_rank, not price-exited); a SUSPENDED
        # held name (不卖条件 选股日停牌) is carried regardless of rank.
        exit_reason = {c: _exit_reason(c) for c in held}
        keep = [c for c in held
                if _suspended(c) or (rank_of.get(c, BIG) < self.sell_rank and exit_reason[c] is None)]
        # 果仁 最大持仓数 cap: if more held names are still in-band than 最大持仓, sell the WORST-ranked
        # down to the cap (suspended names can't be sold -> always retained).
        if self.max_holds and len(keep) > self.max_holds:
            susp = [c for c in keep if _suspended(c)]
            tradable = sorted((c for c in keep if not _suspended(c)), key=lambda c: rank_of.get(c, BIG))
            keep = (susp + tradable)[:max(self.max_holds, len(susp))]
        for c in held:                          # SOLD this period -> rebuy cooldown + tally reason
            if c not in keep:
                self.cooldown[c] = self.rebuy_cooldown
                self.peak.pop(c, None)
                self.sell_reasons[exit_reason[c] or "rank"] += 1
        # BUY smallest-市值 available names (not held, not in cooldown) to refill to target_n
        n_slots = max(0, self.target_n - len(keep))
        buys = [c for c in ranked
                if rank_of[c] <= self.buy_rank and c not in held and c not in self.cooldown][:n_slots]
        names = keep + buys
        if not names:
            return []
        # EQUAL-WEIGHT within the 14-26% band, fully invested (果仁 个股仓位范围 14-26%, ~5 holds
        # => ~20% avg). Equal-weight (rather than letting winners pin at pos_max via a water-fill)
        # keeps the book at 果仁's ~20% spread instead of over-concentrating the top names at 26%;
        # for this smallest-市值 strategy model-II ≈ equal-weight (a winner's 市值 grows, its rank
        # worsens, and it rank-rotates out before drift matters — verified in rung-1). This also
        # redeploys idle cash (the 2021-24 invested-fraction fix): n>=4 names => w=1/n is fully
        # invested; the rebuy cooldown can only drop the book to ~4 names (4*0.26>1.0 => still full).
        w = min(self.pos_max, 1.0 / len(names))
        target = {c: w for c in names}
        return _emit_rebalance_orders(target, context)


def run(start: str, end: str, cadence: str, *, use_exits: bool = True,
        target_n: int = 5, pos_max: float = 0.26):
    from src.backtest_engine.event_driven import EventDrivenBacktester, CostConfig
    from src.backtest_engine.event_driven.exchange import FixedSlippage

    panel = pd.read_parquet(PANEL)
    profit = pd.read_parquet(GATE)
    dt = panel.index.get_level_values(1)
    lo, hi = pd.Timestamp(start) - pd.Timedelta(days=120), pd.Timestamp(end)
    panel = panel[(dt >= lo) & (dt <= hi)]
    profit = profit[(profit.index >= lo) & (profit.index <= hi)]
    rebal = _rebal_dates(start, end, cadence)
    print(f"[run] cadence={cadence} rebalances={len(rebal)} exits={use_exits} target_n={target_n}  {start}..{end}", flush=True)
    sched, churn = build_schedule(panel, profit, rebal)
    nonempty = sum(1 for k in sched if sched[k])
    print(f"[run] {nonempty}/{len(rebal)} non-empty rebalances; mean topk turnover/period={churn:.3f}", flush=True)

    strat = ModelIIPosProfitStrategy(sched, target_n=target_n, pos_max=pos_max, use_exits=use_exits)
    guoren_cost = CostConfig(buy_commission=0.003, sell_commission=0.003, stamp_tax=0.0,
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
    tag = "exits" if use_exits else "noexits"
    net.to_frame("net").to_parquet(OUT / f"rung2_net_{tag}.parquet")
    dh = getattr(res, "daily_holdings", None)
    if dh is not None and not dh.empty:
        dh.to_parquet(OUT / f"rung2_holdings_{tag}.parquet")
    for pc in ("position", "invested", "n_positions", "n_holdings", "cash"):
        if pc in rep.columns:
            s = pd.to_numeric(rep[pc], errors="coerce")
            print(f"[report] {pc}: mean={s.mean():.3f}", flush=True)
    sr = strat.sell_reasons
    tot = sum(sr.values()) or 1
    print(f"[sells] total={sum(sr.values())}  " +
          "  ".join(f"{k}={v} ({v/tot:.0%})" for k, v in sr.items()), flush=True)

    m = ru.goal_metrics(net)
    m["sharpe_rf4"] = ru.sharpe(net, rf=0.04)
    yr = net.groupby(net.index.year).apply(lambda r: (1 + r).prod() - 1)
    yearly = {int(y): float(v) for y, v in yr.items()}

    print("\n" + "=" * 80)
    print(f"  LOCAL  annual≈{m['cagr']:+.2%}  Sharpe(rf4%)={m['sharpe_rf4']:.2f}  MDD={m['mdd']:+.2%}  "
          f"vol={m['ann_vol']:.2%}  turnover/period={churn:.3f}  exits={use_exits}")
    print(f"  果仁   annual={GR_HEADLINE['annual']:+.2%}  Sharpe(rf4%)={GR_HEADLINE['sharpe']:.2f}  "
          f"MDD={-GR_HEADLINE['mdd']:+.2%}  vol={GR_HEADLINE['vol']:.2%}  ~5.0 holds, ~18.3x/yr")
    print("  year     LOCAL      果仁     diff")
    for y in sorted(yearly):
        g = GR_YEARLY.get(y)
        gtxt = f"{g:+7.1%}" if g is not None else "   n/a "
        dtxt = f"{yearly[y]-g:+7.1%}" if g is not None else ""
        print(f"  {y}   {yearly[y]:+8.1%}  {gtxt}  {dtxt}")
    out = dict(local=m, local_yearly=yearly, guoren_headline=GR_HEADLINE, guoren_yearly=GR_YEARLY,
               cadence=cadence, use_exits=use_exits, target_n=target_n, pos_max=pos_max,
               turnover_per_period=churn, start=start, end=end)
    (OUT / f"rung2_result_{tag}.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    meta = {
        "artifact_type": "guorn_parity_reproduction", "strategy": "sm_noc_纯市值正盈利_v4 (nn=16)",
        "purpose": "validate the local PIT income-statement path ($n_income_sq_q0) against 果仁",
        "formal_eligible": False, "strategy_validation": False, "sealed_oos_claim": False,
        "cost_model": "果仁 parity: 0.3%/side, no stamp, no transfer, zero slippage",
        "realistic_cost_claim": False, "execution_profile": "guorn_optimistic_open_parity",
        "pit_field": GATE_FIELD,
        "known_irreducible_deltas": [
            "未来20日新增流通股占比<1% (果仁 PIT lockup screen; reproducing with realized shares = lookahead) — SKIPPED",
            "退市风险_v1(2) proprietary atoms (预期ST2021/风险预警25版/重大违规) not locally available",
            "果仁 09:35/open fill approximated by daily raw_open (no minute data)",
        ],
    }
    (OUT / f"rung2_metadata_{tag}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nNON-FORMAL PARITY ARTIFACT: validates the local PIT statement path + shared execution; "
          "NOT deployable alpha, NOT realistic-cost, NOT a sealed-OOS validation.")
    print(f"saved -> {OUT / f'rung2_result_{tag}.json'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-gate", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--start", default="2014-01-01")
    ap.add_argument("--end", default="2026-06-20")
    ap.add_argument("--cadence", default="daily", choices=["daily", "weekly", "monthly"])
    ap.add_argument("--exits", default="on", choices=["on", "off"])
    ap.add_argument("--target-n", type=int, default=5)
    args = ap.parse_args()
    if args.build_gate:
        build_gate_panel(args.start, args.end)
    if args.run:
        run(args.start, args.end, args.cadence, use_exits=(args.exits == "on"), target_n=args.target_n)


if __name__ == "__main__":
    main()
