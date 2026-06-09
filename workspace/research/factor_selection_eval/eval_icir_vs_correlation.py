"""Evaluate the claim: "Don't chase high ICIR; chase okay-IC + low-correlation factors."

Empirical test on the cached 31-factor IS panel (2014-2020, PIT-safe, fwd_20d). Measures
whether a factor's MARGINAL contribution to a combined signal is driven by its standalone
ICIR or by its (low) correlation to the existing set, and quantifies the breadth law
IR_combined ≈ IR * sqrt(k/(1+(k-1)ρ)). Descriptive IS analysis of a selection PRINCIPLE.
"""
from __future__ import annotations
import sys, json
from pathlib import Path
import numpy as np, pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))
CACHE = PROJECT_ROOT / "workspace" / "outputs" / "long_only_50cagr"
OUT = PROJECT_ROOT / "workspace" / "outputs" / "factor_selection_eval"
OUT.mkdir(parents=True, exist_ok=True)

print("loading factors + fwd...", flush=True)
F = pd.read_parquet(CACHE / "factors_is.parquet")
fwd = pd.read_parquet(CACHE / "fwd_is.parquet")["fwd_20d"]
# universe/size columns are not predictive alphas per se — keep all, orient by IC sign
DATE = F.index.get_level_values(0)

def per_day_rank(s):           # pct-rank within each day
    return s.groupby(DATE).rank(pct=True)

print("pre-ranking fwd + factors per day...", flush=True)
fwd_r = per_day_rank(fwd).reindex(F.index)
RK = {}                        # oriented per-day pct-ranks for each factor
ic_series = {}                 # oriented daily RankIC series
meanic, icir = {}, {}
for c in F.columns:
    r = per_day_rank(F[c])
    # daily RankIC = per-day pearson(rank(f), rank(fwd))
    df = pd.DataFrame({"s": r.values, "f": fwd_r.values}, index=DATE)
    g = df.groupby(level=0)
    ms, mf = g["s"].transform("mean"), g["f"].transform("mean")
    cov = ((df["s"] - ms) * (df["f"] - mf)).groupby(df.index).mean()
    sd = df["s"].groupby(df.index).std(ddof=0) * df["f"].groupby(df.index).std(ddof=0)
    ic = (cov / sd).dropna()
    sign = np.sign(ic.mean()) or 1.0
    ic = ic * sign
    ic_series[c] = ic
    meanic[c] = float(ic.mean())
    icir[c] = float(ic.mean() / ic.std()) if ic.std() > 0 else 0.0
    RK[c] = (r if sign > 0 else (1.0 - r))     # oriented rank (higher = better)

ICS = pd.DataFrame(ic_series)                   # date x factor (oriented RankIC)
tab = pd.DataFrame({"mean_rankic": meanic, "rank_icir": icir}).sort_values("rank_icir", ascending=False)
ic_corr = ICS.corr()                            # payoff (IC-series) correlation
tab["avg_abs_payoff_corr"] = ic_corr.abs().mean()

print("\n=== per-factor: standalone ICIR vs avg payoff-correlation ===", flush=True)
print(tab.round(3).to_string(), flush=True)

# fast combined RankICIR for a set of factors (equal-weight mean of oriented ranks)
def combo_icir(cols):
    comp = pd.concat([RK[c] for c in cols], axis=1).mean(axis=1)
    df = pd.DataFrame({"s": comp.values, "f": fwd_r.values}, index=DATE)
    g = df.groupby(level=0)
    ms, mf = g["s"].transform("mean"), g["f"].transform("mean")
    cov = ((df["s"] - ms) * (df["f"] - mf)).groupby(df.index).mean()
    sd = df["s"].groupby(df.index).std(ddof=0) * df["f"].groupby(df.index).std(ddof=0)
    ic = (cov / sd).dropna()
    return float(ic.mean()), float(ic.mean() / ic.std()) if ic.std() > 0 else 0.0

# ---------- A. marginal-contribution regression ----------
base = tab.index[0]                              # highest standalone ICIR
base_mic, base_icir = combo_icir([base])
rows = []
for f in tab.index[1:]:
    cm, ci = combo_icir([base, f])
    rows.append({"factor": f, "standalone_icir": icir[f], "standalone_ic": meanic[f],
                 "payoff_corr_to_base": float(ic_corr.loc[base, f]),
                 "pair_icir": ci, "increment_icir": ci - base_icir})
M = pd.DataFrame(rows)
# standardized regression: increment ~ standalone_icir + payoff_corr_to_base
import numpy.linalg as la
X = M[["standalone_icir", "payoff_corr_to_base"]].copy()
X = (X - X.mean()) / X.std()
X.insert(0, "const", 1.0)
y = (M["increment_icir"] - M["increment_icir"].mean()) / M["increment_icir"].std()
beta, *_ = la.lstsq(X.values, y.values, rcond=None)
corr_inc_icir = M["increment_icir"].corr(M["standalone_icir"])
corr_inc_pcorr = M["increment_icir"].corr(M["payoff_corr_to_base"])

print(f"\n=== A. marginal contribution (base = {base}, base ICIR={base_icir:.3f}) ===", flush=True)
print(f"standardized betas: standalone_icir={beta[1]:+.3f}  payoff_corr_to_base={beta[2]:+.3f}", flush=True)
print(f"corr(increment, standalone_icir) = {corr_inc_icir:+.3f}", flush=True)
print(f"corr(increment, payoff_corr_to_base) = {corr_inc_pcorr:+.3f}", flush=True)

# ---------- B. concrete contrast: high-ICIR-redundant vs moderate-ICIR-orthogonal ----------
cand = M.copy()
H = cand.sort_values("standalone_icir", ascending=False).iloc[0]      # highest ICIR among non-base
L = cand[cand["standalone_icir"] > cand["standalone_icir"].median()].sort_values("payoff_corr_to_base").iloc[0]
print("\n=== B. concrete contrast (pair with base) ===", flush=True)
for tagrow, name in [(H, "HIGH-ICIR"), (L, "LOW-CORR ")]:
    print(f"  {name}: {tagrow['factor']:20s} ICIR={tagrow['standalone_icir']:+.3f} "
          f"corr2base={tagrow['payoff_corr_to_base']:+.3f} -> pair_increment={tagrow['increment_icir']:+.4f}", flush=True)

# ---------- C. greedy-by-ICIR vs greedy-by-marginal ----------
K = 6
by_icir = list(tab.index[:K])
gm, gi = combo_icir(by_icir)
# forward selection by marginal combined ICIR
chosen = [base]
for _ in range(K - 1):
    best, best_ic = None, -1
    for f in tab.index:
        if f in chosen:
            continue
        _, ci = combo_icir(chosen + [f])
        if ci > best_ic:
            best, best_ic = f, ci
    chosen.append(best)
fm, fi = combo_icir(chosen)
print(f"\n=== C. {K}-factor combinations ===", flush=True)
print(f"  greedy-by-standalone-ICIR {by_icir}", flush=True)
print(f"     combined ICIR={gi:.3f}  meanIC={gm:.4f}  avg_payoff_corr={ic_corr.loc[by_icir, by_icir].values[np.triu_indices(K,1)].mean():.3f}", flush=True)
print(f"  greedy-by-marginal        {chosen}", flush=True)
print(f"     combined ICIR={fi:.3f}  meanIC={fm:.4f}  avg_payoff_corr={ic_corr.loc[chosen, chosen].values[np.triu_indices(K,1)].mean():.3f}", flush=True)

# ---------- D. breadth law: low-corr vs high-corr quartet of similar standalone ICIR ----------
mid = tab[(tab["rank_icir"] > tab["rank_icir"].quantile(0.3)) & (tab["rank_icir"] < tab["rank_icir"].quantile(0.85))].index.tolist()
# pick 4 most mutually-orthogonal vs 4 most mutually-correlated among mid-ICIR factors
def avg_pair_corr(cols):
    sub = ic_corr.loc[cols, cols].values
    return sub[np.triu_indices(len(cols), 1)].mean()
import itertools
best_lo, best_hi = (None, 9), (None, -9)
for combo in itertools.combinations(mid, 4):
    c = avg_pair_corr(list(combo))
    if c < best_lo[1]: best_lo = (list(combo), c)
    if c > best_hi[1]: best_hi = (list(combo), c)
lo_m, lo_i = combo_icir(best_lo[0]); hi_m, hi_i = combo_icir(best_hi[0])
print("\n=== D. breadth law (4 mid-ICIR factors: low-corr vs high-corr) ===", flush=True)
print(f"  LOW-corr  {best_lo[0]} avg_corr={best_lo[1]:+.3f} -> combined ICIR={lo_i:.3f} (avg standalone ICIR={tab.loc[best_lo[0],'rank_icir'].mean():.3f})", flush=True)
print(f"  HIGH-corr {best_hi[0]} avg_corr={best_hi[1]:+.3f} -> combined ICIR={hi_i:.3f} (avg standalone ICIR={tab.loc[best_hi[0],'rank_icir'].mean():.3f})", flush=True)

# ---------- E. zero-IC caveat: uncorrelated NOISE factor adds ~0 ----------
rng = np.random.default_rng(42)
noise = pd.Series(rng.standard_normal(len(F)), index=F.index)
RK["__noise__"] = per_day_rank(noise)
nm, ni = combo_icir([base, "__noise__"])
print("\n=== E. zero-IC caveat ===", flush=True)
print(f"  base+NOISE (uncorrelated, ~0 IC): pair ICIR={ni:.3f} vs base {base_icir:.3f} -> increment={ni-base_icir:+.4f} (≈0: low-corr noise adds nothing)", flush=True)

out = {"base": base, "base_icir": base_icir,
       "A_betas": {"standalone_icir": float(beta[1]), "payoff_corr_to_base": float(beta[2])},
       "A_corr_increment_icir": float(corr_inc_icir), "A_corr_increment_pcorr": float(corr_inc_pcorr),
       "B_high_icir": {"factor": H["factor"], "icir": float(H["standalone_icir"]), "corr": float(H["payoff_corr_to_base"]), "increment": float(H["increment_icir"])},
       "B_low_corr": {"factor": L["factor"], "icir": float(L["standalone_icir"]), "corr": float(L["payoff_corr_to_base"]), "increment": float(L["increment_icir"])},
       "C_greedy_icir": {"factors": by_icir, "combined_icir": gi},
       "C_greedy_marginal": {"factors": chosen, "combined_icir": fi},
       "D_low_corr": {"factors": best_lo[0], "avg_corr": best_lo[1], "combined_icir": lo_i},
       "D_high_corr": {"factors": best_hi[0], "avg_corr": best_hi[1], "combined_icir": hi_i},
       "E_noise_increment": float(ni - base_icir)}
json.dump(out, open(OUT / "icir_vs_corr_results.json", "w"), indent=2, default=float)
tab.to_csv(OUT / "per_factor_table.csv")
print(f"\nSaved -> {OUT/'icir_vs_corr_results.json'}", flush=True)
