"""Strive for 50% — push both legitimate levers hard:
 (A) MAXIMIZE the market-neutral Sharpe by combining the LOW-CORRELATED HIGH-IC factors
     (incl the reversal/turnover/vol cluster that fails long-only but is STRONG market-neutral —
     the correct use of the 'high IC + low corr' insight), risk-parity, walk-forward stability check.
 (B) LEVERAGED long-only VQ10 via 融资 margin (which IS available in A-shares, unlike shorting),
     net of ~6%/yr financing.
Then quantify the leverage→50% CAGR frontier + the drawdown cost for each, honestly.
PIT-safe (cached factors). Simulator = validated total-return proxy. Shorting caveat noted for (A).
"""
from __future__ import annotations
import json, itertools
import numpy as np, pandas as pd
import jq_rep_utils as JR
import research_utils as ru

F = JR.factor_panel(); COST = 0.00185
IS=("2014-01-01","2020-12-31"); OOS=("2021-01-01","2026-02-27"); FULL=("2014-01-01","2026-02-27")

# rich factor set (raw col, orient sign chosen empirically by IS sign below)
COLS = ["rev_return_5d","rev_return_10d","rev_max_return_20d","mom_return_20d",
        "mom_return_60d","mom_return_120d","mom_return_250d","risk_vol_60d","risk_downvol_60d",
        "liq_turnover_20d","liq_amihud_20d","val_cftp","val_bp","val_ep_ttm",
        "qual_roa","qual_accruals","grow_netprofit_yoy"]

def mn_leg(col, sign, start, end, q=0.10):
    rebal = ru.monthly_rebalance_dates(start, end); L,S={},{}
    for d in rebal:
        try: day=F.xs(d,level=0)
        except KeyError: L[d]=[];S[d]=[];continue
        day=day[day["liq_log_dollar_vol"].rank(pct=True)>=0.30]
        st=ru.st_codes_on(d)
        if st: day=day[~day.index.map(lambda c:c.upper() in st)]
        s=(day[col]*sign).dropna()
        if s.empty: L[d]=[];S[d]=[];continue
        r=s.rank(pct=True); L[d]=list(s[r>=1-q].index); S[d]=list(s[r<=q].index)
    return (JR.simulate_eqw_monthly(L,start,end,cost_oneway=COST)
            - JR.simulate_eqw_monthly(S,start,end,cost_oneway=COST)).rename("mn")

def sharpe(x): x=x.dropna(); return float(x.mean()/x.std()*np.sqrt(252)) if x.std()>0 else float("nan")

print("building MN legs over FULL (orient by IS sign)...", flush=True)
legs={}
for c in COLS:
    # orient: compute a cheap IS-sign via mean factor-IC proxy -> use +1, flip if IS MN<0
    mn_full = mn_leg(c, +1, FULL[0], FULL[1])
    is_mask = (mn_full.index>=pd.Timestamp(IS[0]))&(mn_full.index<=pd.Timestamp(IS[1]))
    sign = 1 if mn_full[is_mask].mean()>=0 else -1
    legs[c]= mn_full if sign>0 else (-mn_full)
    print(f"  {c:20s} sign={sign:+d} Sharpe(full)={sharpe(legs[c]):5.2f} CAGR={ru.geom_cagr(legs[c]):+6.2%}", flush=True)
M=pd.DataFrame(legs).dropna()
isM=M[(M.index>=pd.Timestamp(IS[0]))&(M.index<=pd.Timestamp(IS[1]))]
oosM=M[(M.index>=pd.Timestamp(OOS[0]))&(M.index<=pd.Timestamp(OOS[1]))]

# risk-parity combo on a SELECTED low-corr high-Sharpe subset (chosen on IS only)
is_sh=isM.apply(sharpe); cm=isM.corr()
# greedy: start from best IS Sharpe, add factor that keeps avg |corr|<0.5 and improves combo IS Sharpe
def rp_combo(cols, frame):
    v=frame[cols].std(); w=(1/v)/(1/v).sum(); return (frame[cols]*w).sum(axis=1)
chosen=[is_sh.idxmax()]
improved=True
while improved and len(chosen)<8:
    improved=False; base=sharpe(rp_combo(chosen,isM)); best=None
    for c in COLS:
        if c in chosen: continue
        if cm.loc[chosen,c].abs().max()>0.7: continue
        s=sharpe(rp_combo(chosen+[c],isM))
        if s>base+0.02 and (best is None or s>best[1]): best=(c,s)
    if best: chosen.append(best[0]); improved=True
print(f"\nChosen low-corr MN subset (IS-selected): {chosen}", flush=True)
combo_is=rp_combo(chosen,isM); combo_oos=rp_combo(chosen,oosM); combo_full=rp_combo(chosen,M)
print(f"  combined MN  IS:  Sharpe={sharpe(combo_is):.2f} CAGR={ru.geom_cagr(combo_is):+.2%} vol={ru.ann_vol(combo_is):.1%} MDD={ru.max_drawdown(combo_is):+.1%}", flush=True)
print(f"  combined MN  OOS: Sharpe={sharpe(combo_oos):.2f} CAGR={ru.geom_cagr(combo_oos):+.2%} vol={ru.ann_vol(combo_oos):.1%} MDD={ru.max_drawdown(combo_oos):+.1%}  (stability check)", flush=True)
print(f"  combined MN  FULL:Sharpe={sharpe(combo_full):.2f} CAGR={ru.geom_cagr(combo_full):+.2%} vol={ru.ann_vol(combo_full):.1%} MDD={ru.max_drawdown(combo_full):+.1%}", flush=True)

def lever(series, L, borrow=0.06):
    d=series.dropna(); return (L*d - (L-1)*borrow/252)
print("\n=== (A) leverage frontier — best low-corr MARKET-NEUTRAL book (needs shorting/futures) ===", flush=True)
cf=ru.ann_vol(combo_full); cc=ru.geom_cagr(combo_full)
for L in (1,2,3,4):
    lv=lever(combo_full,L); print(f"  {L}x: CAGR={ru.geom_cagr(lv):+.2%} vol={ru.ann_vol(lv):.0%} MDD={ru.max_drawdown(lv):+.0%}", flush=True)
print(f"  leverage for 50% CAGR ≈ {0.50/cc:.1f}x", flush=True)

print("\n=== (B) leveraged LONG-ONLY 大市值价值 top10 via 融资 margin (DEPLOYABLE — no shorting) ===", flush=True)
vq = pd.read_parquet(JR.OUT/"sleeve_returns_full.parquet")["value_quality"].dropna()
print(f"  unlevered: CAGR={ru.geom_cagr(vq):+.2%} vol={ru.ann_vol(vq):.0%} MDD={ru.max_drawdown(vq):+.0%} Sharpe={sharpe(vq):.2f}", flush=True)
for L in (1.0,1.5,2.0,2.5,3.0):
    lv=lever(vq,L); print(f"  {L}x: CAGR={ru.geom_cagr(lv):+.2%} vol={ru.ann_vol(lv):.0%} MDD={ru.max_drawdown(lv):+.0%}", flush=True)
print(f"  leverage for 50% CAGR ≈ {0.50/ru.geom_cagr(vq):.1f}x", flush=True)

json.dump({"mn_chosen":chosen,"mn_sharpe_is":sharpe(combo_is),"mn_sharpe_oos":sharpe(combo_oos),
           "mn_sharpe_full":sharpe(combo_full),"mn_cagr_full":ru.geom_cagr(combo_full),
           "mn_vol_full":ru.ann_vol(combo_full)},
          open(JR.OUT/"market_neutral_v2_results.json","w"), indent=2, default=float)
print("\nNOTE (A): A-share single-name shorting restricted -> MN book is a design/what-if needing the parked MN leg + futures.", flush=True)
print("NOTE (B): 融资 margin is available but 2x+ on equities is high-risk; −MDD scales near-linearly; 2.5x → ~50% CAGR at brutal drawdown.", flush=True)
