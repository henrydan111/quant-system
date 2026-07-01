# ──────────────────────────────────────────────────────────────────────
# script_status: research_tooling
# formal_research_allowed: false
# deployment_target: unified_eval_verification_probe
# requires_provider_manifest: false
# requires_preload_strict: false
# pr2_audit_class: C
# notes: |
#   One-off verification probe for the unified factor-evaluation standard (superseded by
#   unified_eval_driver.py / unified_eval_driver_data.py for production evidence). IS-only,
#   zero OOS spend, read-only w.r.t. all registries.
# ──────────────────────────────────────────────────────────────────────
"""Verify the two remaining unified-standard口径 pieces on the CACHED IS panel (no rebuild):
  (1) the complete monotonicity diagnostic — expected-direction-oriented adjacent-bucket sign
      vector + shape classifier + mono_frac_dominant — on the real 7 factors;
  (2) Tier-2 column #2 `marginal_icir_delta` — incremental folded RankICIR of an equal-weight
      sign-oriented composite when the candidate is added to the approved-8 (leave-one-out).
Read-only; IS-only; uses the panel cached by unified_eval_probe.py.
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
np.seterr(all="ignore")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.alpha_research.factor_eval import ic_analysis as ica
from src.alpha_research.factor_eval import quantile_analysis as qa
from src.alpha_research.factor_library import operators as op

PANEL = PROJECT_ROOT / "workspace" / "outputs" / "unified_eval_probe_panel.parquet"
OUT = PROJECT_ROOT / "workspace" / "outputs" / "unified_eval_verify2.json"
LABEL_COL = "__label__"

PICKS = {
    "earn_eps_diffusion_60": "approved", "liq_zero_ret_days_10d": "approved",
    "qual_piotroski_fscore_9pt": "approved", "liq_vol_cv_20d": "candidate",
    "qual_gross_profitability": "candidate", "rev_up_down_ratio_20d": "candidate",
    "qual_q_gross_margin": "draft",
}
APPROVED_8 = [
    "earn_eps_diffusion_60", "earn_eps_diffusion_120", "grow_n_income_attr_p_yoy_accel_q",
    "grow_operate_profit_yoy_accel_q", "grow_total_revenue_yoy_accel_q", "liq_zero_ret_days_10d",
    "qual_piotroski_fscore_9pt", "rev_turnover_spike_5d",
]


def _to_dt_inst(s: pd.Series) -> pd.Series:
    return (s.swaplevel(0, 1) if s.index.names[0] != "datetime" else s).sort_index()


def _rank_icir(factor: pd.Series, label: pd.Series) -> float:
    ic = ica.compute_ic_series(factor, label, min_obs=30)
    r = ic["RankIC"].dropna()
    return float(r.mean() / r.std()) if r.std() > 0 else float("nan")


def _classify_shape(step_signs: str) -> str:
    n = len(step_signs)
    pos, neg = step_signs.count("+"), step_signs.count("-")
    if pos == n:
        return "monotonic_up"
    if neg == n:
        return "monotonic_down"
    if step_signs[:-1].count("+") == n - 1 and step_signs[-1] == "-":
        return "top_reversal"
    if step_signs[0] == "-" and step_signs[1:].count("+") == n - 1:
        return "bottom_reversal"
    if step_signs == "-" * neg + "+" * pos:
        return "U_shape"
    if step_signs == "+" * pos + "-" * neg:
        return "inverted_U"
    return "irregular"


def _monotonicity(factor: pd.Series, label: pd.Series, direction: float) -> dict:
    """Orient by expected direction (best quantile -> Q_top), then characterize the shape."""
    oriented = factor * (1.0 if direction >= 0 else -1.0)
    qdf = qa.compute_quantile_returns(oriented, label, n_quantiles=5, min_obs=50)
    qs = qa.compute_quantile_summary(qdf)
    if len(qs) < 3:
        return {"mono_reason": f"insufficient_quantiles(n={len(qs)})", "mono_shape": None,
                "mono_step_signs": None, "mono_frac_dominant": None, "monotonic_spearman": None}
    ar = qs["annualized_return"].values
    d = np.diff(ar)
    signs = "".join("+" if x > 1e-12 else ("-" if x < -1e-12 else "0") for x in d)
    pos, neg = signs.count("+"), signs.count("-")
    from scipy import stats
    sp = stats.spearmanr(qs.index.values, ar)[0]
    return {
        "mono_reason": None, "mono_shape": _classify_shape(signs),
        "mono_step_signs": signs, "mono_frac_dominant": round(max(pos, neg) / len(signs), 3),
        "monotonic_spearman": None if sp != sp else round(float(sp), 3),
        "quantile_ann_returns": [round(float(x), 3) for x in ar],
    }


def main() -> int:
    combined = pd.read_parquet(PANEL)
    label = _to_dt_inst(combined.pop(LABEL_COL))
    universe = sorted(set(PICKS) | set(APPROVED_8))
    fac = {n: _to_dt_inst(combined[n]) for n in universe}
    # IS direction per factor = sign of mean RankIC
    direction = {}
    for n in universe:
        ic = ica.compute_ic_series(fac[n], label, min_obs=30)
        direction[n] = float(np.sign(ic["RankIC"].dropna().mean()) or 1.0)

    # pre-orient + z-score each factor once (for composite building)
    z = {n: op.cs_zscore(fac[n] * direction[n]) for n in universe}

    report = []
    for fid, status in PICKS.items():
        mono = _monotonicity(fac[fid], label, direction[fid])

        base = [b for b in APPROVED_8 if b != fid]
        base_comp = pd.concat([z[b] for b in base], axis=1).mean(axis=1)
        with_comp = pd.concat([z[b] for b in base] + [z[fid]], axis=1).mean(axis=1)
        icir_base = _rank_icir(base_comp, label)
        icir_with = _rank_icir(with_comp, label)
        delta = icir_with - icir_base

        report.append({
            "factor": fid, "status": status, "direction": direction[fid],
            "monotonicity": mono,
            "marginal_icir_delta_vs_approved8": {
                "leave_one_out": fid in APPROVED_8, "base_n": len(base),
                "icir_base": round(icir_base, 4), "icir_with": round(icir_with, 4),
                "delta": round(delta, 4),
            },
        })

    OUT.write_text(json.dumps({"factors": report}, indent=2), encoding="utf-8")
    print(f"{'factor':28s} {'status':9s} {'dir':>4s} | {'mono_shape':14s} {'signs':6s} {'frac':>5s} {'spear':>6s} | "
          f"{'icir_base':>9s} {'icir_with':>9s} {'delta':>7s}")
    for r in report:
        m = r["monotonicity"]; d = r["marginal_icir_delta_vs_approved8"]
        print(f"{r['factor']:28s} {r['status']:9s} {r['direction']:>4.0f} | "
              f"{str(m['mono_shape']):14s} {str(m['mono_step_signs']):6s} "
              f"{str(m['mono_frac_dominant']):>5s} {str(m['monotonic_spearman']):>6s} | "
              f"{d['icir_base']:>9.4f} {d['icir_with']:>9.4f} {d['delta']:>+7.4f}")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
