# ──────────────────────────────────────────────────────────────────────
# script_status: class_d_research_tooling
# formal_research_allowed: false
# touches_formal_data_plane: false
# pr2_audit_class: D
# notes: |
#   DEPLOYMENT GATE for EWaveSelectedSet_v2 (the 6-core that went 6/6 on the
#   sealed OOS). The sealed-OOS bar (decile LS Sharpe 1.6-5.9) is GROSS / 5d /
#   full-universe (incl microcaps) = registration metric, NOT tradability. This
#   answers "is it deployable?" by building the DEPLOYABLE form: the 6 as a
#   direction-aligned equal-weight z-score COMPOSITE, long-only top-K, on the
#   LIQUID universe (top-300 by trailing 20d $-vol), through the EventDrivenBacktester
#   (T+1, limits, suspension, corporate actions, REALISTIC China costs), UNLEVERED
#   (1x). 5 of 6 are held short -> long-only longs the LOW end of those (aligned).
#   A-share 融券 restricted -> LS not tradeable -> long-only top-K is the deployable form.
#   Mirrors workspace/research/idea_sourcing/build/eval_eps_diffusion_deployment.py.
#   OOS window 2021-2026. NO registry mutation, NO seal (the OOS is already spent).
# ──────────────────────────────────────────────────────────────────────
"""Event-driven deployment gate for the EWaveSelectedSet_v2 6-core composite."""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "workspace" / "research" / "long_only_50cagr"),
          str(ROOT / "workspace" / "research" / "jq_replication")):
    if p not in sys.path:
        sys.path.insert(0, p)
import research_utils as ru                                              # noqa: E402
from src.backtest_engine.event_driven import EventDrivenBacktester, CostConfig  # noqa: E402
from src.backtest_engine.event_driven.strategies import RankedFallbackStrategy  # noqa: E402
from src.alpha_research.factor_library import operators as op, get_factor_catalog  # noqa: E402

# (factor, alignment sign): -1 = held short -> negate so high=long; +1 = held long.
SIX = [("corr_ret_turnd_20d", -1), ("liq_vstd_20d", -1), ("vol_w_downshadow_std_60d", -1),
       ("corr_price_turn_post_20d", -1), ("flow_act_buy_shift_dist_xl_20d", -1),
       ("liq_shortcut_avg_20d", +1)]
WARM_START, OOS_START, END = "2020-06-01", "2021-01-01", "2026-02-26"
BENCH, CAPITAL, VOL_LIMIT = "000300.SH", 10_000_000.0, 0.10
LIQ_TOPN, MIN_FACTORS = 300, 3   # liquid universe size; min non-NaN factors for a composite score
PRELOAD = ["$open", "$close", "$high", "$low", "$vol", "$amount", "$pre_close", "$adj_factor"]
OUT = ROOT / "workspace" / "outputs" / "e_wave_v2_deployment"

print("computing the 6-core panel + liquidity + tradeability ...", flush=True)
cat = get_factor_catalog(include_new_data=True)
exprs = {fid: cat[fid] for fid, _ in SIX}
exprs.update({"close": "$close", "amount": "$amount", "amt20": "Mean(Ref($amount,1),20)"})
fdf, _ = op.compute_factors(exprs, WARM_START, END, horizons=None, kernels=1)
nm = list(fdf.index.names)
if "datetime" in nm and nm != ["datetime", "instrument"]:
    fdf = fdf.reorder_levels(["datetime", "instrument"])
fdf = fdf.sort_index()
print(f"panel: {len(fdf)} rows, {fdf.index.get_level_values(0).nunique()} dates", flush=True)


def composite_ranked(d):
    """Direction-aligned equal-weight z-score composite within the liquid top-300; high = long."""
    try:
        day = fdf.xs(d, level=0)
    except KeyError:
        return None
    liq = day["amt20"].dropna().sort_values(ascending=False).head(LIQ_TOPN).index
    sub = day.loc[liq]
    sub = sub[sub["close"].notna() & (sub["amount"].fillna(0) > 0)]   # tradeable on rebal day
    st = ru.st_codes_on(d)
    if st:
        sub = sub[~sub.index.map(lambda c: str(c).upper() in st)]
    if len(sub) < 50:
        return None
    zs = []
    for fid, sign in SIX:
        col = sub[fid].astype(float)
        sd = col.std()
        if sd and np.isfinite(sd) and sd > 0:
            zs.append(sign * (col - col.mean()) / sd)
    if not zs:
        return None
    Z = pd.concat(zs, axis=1)
    comp = Z.mean(axis=1).where(Z.notna().sum(axis=1) >= MIN_FACTORS)   # need >=3 factors present
    return comp.dropna().sort_values(ascending=False)                   # high composite = long


def ranked_schedule(topk):
    headroom = topk * 3
    sched, members = {}, {}
    for d in ru.monthly_rebalance_dates(OOS_START, END):
        ranked = composite_ranked(d)
        if ranked is None:
            sched[pd.Timestamp(d)] = []; continue
        sched[pd.Timestamp(d)] = [str(i).upper().replace("_", ".") for i in ranked.head(headroom).index]
        members[pd.Timestamp(d)] = set(ranked.head(topk).index)
    keys = sorted(members)
    ch = [len(members[keys[i]] - members[keys[i-1]]) / max(len(members[keys[i]]), 1)
          for i in range(1, len(keys)) if members[keys[i]]]
    return sched, (float(np.mean(ch)) if ch else float("nan"))


def run(topk, cost, cost_label):
    sched, sched_turn = ranked_schedule(topk)
    bt = EventDrivenBacktester(data_dir=str(ROOT / "data"))
    res = bt.run(strategy=RankedFallbackStrategy(sched, topk=topk), start_time=OOS_START, end_time=END,
                 benchmark=BENCH, account=CAPITAL, exchange_config=cost, slippage=None,
                 volume_limit=VOL_LIMIT, preload_fields=PRELOAD)
    rep = res.report.copy()
    if "date" in rep.columns:
        rep = rep.set_index(pd.to_datetime(rep["date"]))
    net = rep["return"].astype(float)
    bench = rep["bench_return"].astype(float) if "bench_return" in rep.columns else None
    m = ru.goal_metrics(net, bench)
    m["calmar"] = m["cagr"] / abs(m["mdd"]) if m.get("mdd", 0) < 0 else float("nan")
    m["sched_monthly_turnover"] = round(sched_turn, 3)
    m.update(topk=topk, cost=cost_label)
    yr = net.groupby(net.index.year).apply(lambda r: (1 + r).prod() - 1)
    print(f"\ntop{topk} / {cost_label:16s}  CAGR={m['cagr']:+7.2%}  MDD={m['mdd']:+7.2%}  "
          f"Sharpe={m['sharpe']:5.2f}  Calmar={m.get('calmar', float('nan')):4.2f}  "
          f"turnover/mo={m['sched_monthly_turnover']:.0%}", flush=True)
    print("  yearly: " + "  ".join(f"{int(y)}:{v:+.0%}" for y, v in yr.items()), flush=True)
    return m


print(f"\n== EWaveSelectedSet_v2 6-core DEPLOYMENT (event-driven, long-only top-K composite, "
      f"liquid top-{LIQ_TOPN}, 1x, OOS {OOS_START}..{END}, vs {BENCH}) ==")
results = []
for k in (30, 50):
    results.append(run(k, CostConfig.realistic_china(), "realistic_china"))
results.append(run(30, CostConfig(), "joinquant"))   # optimistic-cost bracket
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "e_wave_v2_deployment.json").write_text(
    json.dumps([{k: v for k, v in r.items() if k != "yearly"} for r in results], indent=2, default=str),
    encoding="utf-8")
print(f"\nNOTE: long-only top-K composite on the LIQUID top-{LIQ_TOPN} is the DEPLOYABLE form (A-share 融券 "
      f"restricted -> the gross sealed-OOS LS Sharpe is NOT tradeable). 1x, realistic costs. "
      f"This is where the microcap-driven gross numbers get haircut. Saved -> {OUT/'e_wave_v2_deployment.json'}")
