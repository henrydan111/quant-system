"""M6 — the microcap engine: directly test the actual source of the JoinQuant
50%+/"无惧牛熊" returns, instead of asserting it. (CLAUDE.md §7.10: run the data.)

The 微盘股 effect is the ONE A-share phenomenon that genuinely produces 50%+ CAGR.
The prior effort EXCLUDED microcap factors; M3 only tested mid-small (size 10-60pct).
Here: true bottom-decile microcap, IS 2014-2020 (contains the 2015 crash + 2018 bear,
which expose the MDD). Tests pure / quality-screened / regime-gated, at two liquidity
floors (0 = the zero-slippage "paper" universe JoinQuant implicitly uses; 0.20 = a
minimally-tradeable floor). Realistic 5/15bps costs (microcap real slippage is far
higher -- so these CAGRs are OPTIMISTIC and the MDDs are CONSERVATIVE).

Goal of M6: determine whether ANY microcap construction reaches 50% CAGR AND <40% MDD.
"""
from __future__ import annotations
import json
import numpy as np, pandas as pd
import jq_utils as J
import research_utils as ru
import backtest_harness as bh
import overlay as ov

IS_START, IS_END = "2014-01-01", "2020-12-31"
BENCH = "000852_SH"  # 中证1000 small-cap benchmark

F = pd.read_parquet(J.CACHE / "factors_is.parquet")
results = []
def rec(label, net, extra=None):
    d = J.metrics_dict(label, net)
    if extra: d.update(extra)
    results.append(d)
    print(J.summary_line(label, net))

def micro_book(label, *, size_high, liq_floor, topk, quality=False, rank="size"):
    rebal = ru.monthly_rebalance_dates(IS_START, IS_END)
    uni = ru.build_universe_mask(F, rebal, liq_pct_floor=liq_floor,
                                 size_low_pct=0.0, size_high_pct=size_high)
    uni_idx = pd.MultiIndex.from_frame(uni)
    sub = F.loc[F.index.isin(uni_idx)]
    if quality:
        keep = (sub["val_cftp"] > 0) & (sub["qual_roa"] > 0) & (sub["grow_netprofit_yoy"] > 0)
        sub = sub[keep.fillna(False)]
    book_uni = sub.index.to_frame(index=False)[["datetime", "instrument"]]
    if rank == "size":
        w, neg = {"size_ln_mcap": 1.0}, {"size_ln_mcap": True}   # smallest-first
    else:
        w, neg = {"val_cftp": 1.0}, {"val_cftp": False}
    rebal_score = bh.build_composite_signal(F, w, neg, rebal, book_uni)
    daily = bh.expand_monthly_signal(rebal_score, rebal, IS_START, IS_END)
    if daily.empty:
        print(f"{label:34s} EMPTY"); return None
    m = bh.run_composite_backtest(F, w, neg, IS_START, IS_END,
                                  daily_signal_override=daily, topk=topk,
                                  benchmark=BENCH, label=label)
    return m

print("=== M6 true-microcap books (IS 2014-2020) ===")
cfgs = [
    ("micro pure d10 liq0 k50",    dict(size_high=0.10, liq_floor=0.00, topk=50)),
    ("micro pure d10 liq0 k100",   dict(size_high=0.10, liq_floor=0.00, topk=100)),
    ("micro pure d20 liq0 k50",    dict(size_high=0.20, liq_floor=0.00, topk=50)),
    ("micro pure d20 liq.2 k50",   dict(size_high=0.20, liq_floor=0.20, topk=50)),
    ("micro qual d20 liq0 k50",    dict(size_high=0.20, liq_floor=0.00, topk=50, quality=True)),
]
books = {}
for label, kw in cfgs:
    m = micro_book(label, **kw)
    if m is None: continue
    rec(label, m["_net"]); books[label] = m["_net"]

# regime-gate the best paper-microcap book (does the trend filter rescue MDD?)
print("\n=== M6 regime-gated microcap (中证1000 MA filter) ===")
key = "micro pure d20 liq0 k50"
if key in books:
    for ma in (120, 200):
        small_on = ov.trend_exposure("000852.SH", ma, IS_START, IS_END)
        idx = books[key].index
        so = small_on.reindex(idx).ffill().fillna(0.0)
        choice = pd.Series("cash", index=idx)
        choice[so > 0] = key
        net = J.combine_regime({key: books[key]}, choice, switch_cost=0.0030)
        rec(f"micro regime[{key}|cash] MA{ma}", net)

print("\n=== yearly breakdown (microcap) ===")
for r in results:
    ys = "  ".join(f"{y}:{v:+.1%}" for y, v in sorted(r["yearly"].items()))
    print(f"{r['label']:34s} {ys}")

# verdict check
print("\n=== M6 verdict check (50% CAGR AND <40% MDD?) ===")
for r in results:
    ok = (r["cagr"] >= 0.50) and (r["mdd"] > -0.40)
    print(f"{r['label']:34s} CAGR={r['cagr']:+7.2%} MDD={r['mdd']:+7.2%} -> "
          f"{'*** MEETS TARGET ***' if ok else 'fails ' + ('CAGR' if r['cagr']<0.50 else '') + ('+MDD' if r['mdd']<=-0.40 else '')}")

with open(J.OUT / "m6_results.json", "w", encoding="utf-8") as f:
    json.dump([{k: v for k, v in r.items() if not k.startswith("_")} for r in results],
              f, indent=2, default=float)
print(f"\nSaved -> {J.OUT/'m6_results.json'}")
