"""Demonstrate WHERE the low-correlation insight actually pays off: MARKET-NEUTRAL.

Long-only sleeves are corr ~0.6 (shared beta) -> limited diversification. Build dollar-neutral
long-short factor legs (top-decile long − bottom-decile short, EW, monthly, buy-and-hold within
month) and show: (1) their mutual RETURN correlation collapses (beta removed -> the signal-level
orthogonality now shows in returns); (2) a low-correlated MN combo has high combined Sharpe; (3)
quantify the leverage needed to reach 50% CAGR and whether the Sharpe supports it.

CAVEAT: A-share single-name shorting is restricted (限制性 融券); this is a DESIGN/what-if that
pinpoints the capability needed (a market-neutral leg — currently parked), not a deployable book.
"""
from __future__ import annotations
import json
import numpy as np, pandas as pd
import jq_rep_utils as JR
import research_utils as ru

F = JR.factor_panel()
COST = 0.00185
IS = ("2014-01-01", "2020-12-31"); FULL = ("2014-01-01", "2026-02-27")

# factor -> (column, long_sign)  long the 'good' end (high IC end)
FACTORS = {
    "value_cp":  ("val_cftp", +1), "value_bp": ("val_bp", +1),
    "lowvol":    ("risk_vol_60d", -1), "quality": ("qual_roa", +1),
    "growth":    ("grow_netprofit_yoy", +1), "reversal": ("mom_return_20d", -1),
    "size_sml":  ("size_ln_mcap", -1),
}

def mn_leg(start, end, col, sign, q=0.10):
    rebal = ru.monthly_rebalance_dates(start, end)
    longs, shorts = {}, {}
    for d in rebal:
        try:
            day = F.xs(d, level=0)
        except KeyError:
            longs[d]=[]; shorts[d]=[]; continue
        day = day[day["liq_log_dollar_vol"].rank(pct=True) >= 0.30]   # liquid only
        st = ru.st_codes_on(d)
        if st: day = day[~day.index.map(lambda c: c.upper() in st)]
        s = (day[col] * sign).dropna()
        if s.empty: longs[d]=[]; shorts[d]=[]; continue
        r = s.rank(pct=True)
        longs[d]  = list(s[r >= 1-q].index)
        shorts[d] = list(s[r <= q].index)
    long_net  = JR.simulate_eqw_monthly(longs,  start, end, cost_oneway=COST)
    short_net = JR.simulate_eqw_monthly(shorts, start, end, cost_oneway=COST)
    return (long_net - short_net).rename("mn")   # dollar-neutral

def sharpe(x):
    x=x.dropna(); return float(x.mean()/x.std()*np.sqrt(252)) if x.std()>0 else float("nan")
def cagr(x):  return JR.ru.geom_cagr(x) if hasattr(JR.ru,'geom_cagr') else ru.geom_cagr(x)

for win,(s,e) in {"FULL":FULL}.items():
    print(f"\n===== market-neutral factor legs [{win}] =====", flush=True)
    mns={}
    for name,(col,sign) in FACTORS.items():
        mn = mn_leg(s,e,col,sign)
        mns[name]=mn
        print(f"  {name:10s} MN  CAGR={ru.geom_cagr(mn):+7.2%} vol={ru.ann_vol(mn):5.1%} Sharpe={sharpe(mn):5.2f} MDD={ru.max_drawdown(mn):+7.2%}", flush=True)
    M = pd.DataFrame(mns).dropna()
    cm = M.corr()
    print(f"\n  --- MN factor return correlation [{win}] (contrast long-only ~0.6) ---", flush=True)
    print(cm.round(2).to_string(), flush=True)
    print(f"  avg |off-diag corr| = {cm.abs().values[np.triu_indices(len(cm),1)].mean():.3f}", flush=True)

    # combine low-correlated viable MN factors (drop size_sml: short side untradeable microcap)
    pick = ["value_cp","lowvol","quality","growth","reversal"]
    # inverse-vol weight the MN legs (risk parity)
    vols = M[pick].std()
    w = (1/vols)/(1/vols).sum()
    combo = (M[pick]*w).sum(axis=1)
    cs, cc, cv, cmdd = sharpe(combo), ru.geom_cagr(combo), ru.ann_vol(combo), ru.max_drawdown(combo)
    print(f"\n  COMBINED MN (risk-parity, {pick}):", flush=True)
    print(f"    CAGR={cc:+.2%} vol={cv:.1%} Sharpe={cs:.2f} MDD={cmdd:+.2%} avg_pair_corr={cm.loc[pick,pick].values[np.triu_indices(len(pick),1)].mean():.3f}", flush=True)
    # leverage analysis: scale to target vol; CAGR ~ leverage * mean - drag
    for tgt in (0.15, 0.30):
        L = tgt/cv
        lev = combo*L
        print(f"    @ target vol {tgt:.0%} (leverage {L:.1f}x): CAGR={ru.geom_cagr(lev):+.2%} MDD={ru.max_drawdown(lev):+.2%}", flush=True)
    lev_for_50 = (0.50/ (cc if cc>0 else np.nan))
    print(f"    leverage for ~50% CAGR ≈ {lev_for_50:.1f}x (vol would be {cv*lev_for_50:.0%}, MDD ~{cmdd*lev_for_50:+.0%}) -> {'plausible' if cs>1.5 and lev_for_50<=3 else 'requires high leverage / strong Sharpe'}", flush=True)
    M.to_parquet(JR.OUT/"mn_factor_returns_full.parquet")
print("\nNOTE: A-share single-name shorting is restricted -> this is a design/what-if (the parked market-neutral leg), not a deployable long-only book.", flush=True)
