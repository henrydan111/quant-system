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
"""Verify the FULL unified evaluation口径 (Tier 1 intrinsic + Tier 2 marginal) on the
7-factor representative set, before any full-catalog recompute.

Tier 1 (intrinsic, IS-only, h=20): heldout RankICIR + sign-consistency (run_is_walk_forward),
mean RankIC + IC hit-rate (compute_ic_summary), quantile monotonicity + LS spread
(quantile_analysis), turnover (cost_aware_eval), coverage (non-null fraction).
Tier 2 (marginal, RELATIVE): residual RankIC of each factor vs the 8 approved (leave-one-out for
members), via ic_analysis.compute_marginal_ic.

Decay (Tier 1 #6) needs multi-horizon labels → computed in the FULL run, not here.
Reuses tested factor_eval / factor_lifecycle functions only. Read-only; no registry writes; IS-only
(no OOS spend). Panel cached to parquet so re-runs are cheap.
"""
from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.alpha_research.factor_library.catalog import get_factor_catalog
from src.alpha_research.factor_lifecycle.walk_forward_validation import (
    IsWindowedPanel,
    load_is_windowed_panel,
    load_open_trading_days,
    run_is_walk_forward,
)
from src.alpha_research.factor_eval import ic_analysis as ica
from src.alpha_research.factor_eval import quantile_analysis as qa
from src.alpha_research.factor_eval import cost_aware_eval as cae
from src.alpha_research.walk_forward import TimeSplit

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("unified_eval_probe")

TIME_SPLIT = TimeSplit("2014-01-01", "2020-12-31", "2021-01-01", "2022-01-01")
HORIZON = 20
QLIB_DIR = PROJECT_ROOT / "data" / "qlib_data"
OUTDIR = PROJECT_ROOT / "workspace" / "outputs"
PANEL_CACHE = OUTDIR / "unified_eval_probe_panel.parquet"
OUT = OUTDIR / "unified_eval_probe.json"
LABEL_COL = "__label__"

PICKS = {
    "earn_eps_diffusion_60": "approved",
    "liq_zero_ret_days_10d": "approved",
    "qual_piotroski_fscore_9pt": "approved",
    "liq_vol_cv_20d": "candidate",
    "qual_gross_profitability": "candidate",
    "rev_up_down_ratio_20d": "candidate",
    "qual_q_gross_margin": "draft",
}
# Reference set for Tier 2 marginal = the 8 deployed-grade approved factors.
APPROVED_8 = [
    "earn_eps_diffusion_60", "earn_eps_diffusion_120",
    "grow_n_income_attr_p_yoy_accel_q", "grow_operate_profit_yoy_accel_q",
    "grow_total_revenue_yoy_accel_q", "liq_zero_ret_days_10d",
    "qual_piotroski_fscore_9pt", "rev_turnover_spike_5d",
]


def _to_dt_inst(s: pd.Series) -> pd.Series:
    """Normalize a MultiIndex Series to (datetime, instrument) as the factor_eval toolkit expects."""
    idx = s.index
    names = list(idx.names)
    if names[0] != "datetime" and "datetime" in names:
        s = s.swaplevel(0, 1)
    return s.sort_index()


def _build_or_load_panel(catalog: dict) -> IsWindowedPanel:
    if PANEL_CACHE.exists():
        log.info("Loading cached panel %s ...", PANEL_CACHE)
        combined = pd.read_parquet(PANEL_CACHE)
        label = combined.pop(LABEL_COL)
        return IsWindowedPanel(factor_panel=combined, label=label, is_end=TIME_SPLIT.is_end,
                               horizon=HORIZON, open_days=load_open_trading_days(None))
    t0 = time.time()
    log.info("Building IS panel for %d factors over [%s, %s] ...",
             len(catalog), TIME_SPLIT.is_start, TIME_SPLIT.is_end)
    panel = load_is_windowed_panel(catalog, TIME_SPLIT, horizon=HORIZON, qlib_dir=str(QLIB_DIR))
    log.info("Panel built in %.0fs: shape=%s", time.time() - t0, panel.factor_panel.shape)
    combined = panel.factor_panel.copy()
    combined[LABEL_COL] = panel.label
    OUTDIR.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(PANEL_CACHE)
    log.info("Cached panel -> %s", PANEL_CACHE)
    return panel


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    full = get_factor_catalog(include_new_data=True)
    universe = sorted(set(PICKS) | set(APPROVED_8))
    missing = [f for f in universe if f not in full]
    if missing:
        log.error("not in catalog: %s", missing)
        return 1
    catalog = {n: full[n] for n in universe}

    panel = _build_or_load_panel(catalog)

    # Tier 1 #1-2: heldout RankICIR + sign-consistency (the bit-exact-verified headline)
    wf = run_is_walk_forward(panel=panel, time_split=TIME_SPLIT, horizon=HORIZON, factor_origin="a_priori")
    wf_rows = {r["factor"]: dict(r) for r in wf.rows}

    label = _to_dt_inst(panel.label)
    factors_dt = {n: _to_dt_inst(panel.factor_panel[n]) for n in universe}

    report = []
    for fid, status in PICKS.items():
        fser = factors_dt[fid]
        # Tier 1 #3-4: mean RankIC + IC hit-rate
        ic = ica.compute_ic_series(fser, label, min_obs=30)
        summ = ica.compute_ic_summary(ic)
        # Tier 1 #5: quantile monotonicity (boolean + continuous spearman) + LS spread
        mono_reason = None
        try:
            qdf = qa.compute_quantile_returns(fser, label, n_quantiles=5, min_obs=50)
            qsumm = qa.compute_quantile_summary(qdf)
            n_buckets = int(len(qsumm))
            if n_buckets < 3:
                # qcut collapsed to <3 buckets (discrete/tie-heavy or sparse-coverage factor):
                # spearman is NOT computable — report None, not the 0.0 sentinel. Direction for
                # these factors is the continuous mean_rank_ic (Tier1 #3), which is non-zero.
                mono = {}
                mono_reason = f"insufficient_quantiles(n={n_buckets})"
            else:
                mono = qa.test_monotonicity(qsumm)
            ls = qa.compute_long_short_returns(qdf)
            ls_spread = float(np.nanmean(ls.values)) if ls is not None and len(ls) else float("nan")
        except Exception as e:  # noqa: BLE001
            mono, ls_spread, mono_reason = {}, float("nan"), f"error:{e}"
        # Tier 1 #7: turnover at the ACTUAL rebalance frequency (20d top-quintile one-way churn,
        # annualized = mean(per-rebalance churn) * (252/HORIZON) rebalances/yr)
        turn_ann = _turnover_annualized(fser, rebalance_days=HORIZON)
        # Tier 1 #8: coverage (non-null fraction over the panel) + tier flag
        coverage = float(fser.notna().mean())
        cov_tier = "full" if coverage >= 0.90 else ("broad" if coverage >= 0.50 else "sub")

        # Tier 2: residual RankIC vs approved-8 (leave-one-out for members)
        base = [b for b in APPROVED_8 if b != fid]
        try:
            _, m_summ = ica.compute_marginal_ic(factors_dt, label, base_factors=base,
                                                candidate=fid, min_obs=30)
            marg_mean_rank_ic = _f(m_summ.get("mean_rank_ic"))
            marg_rank_icir = _f(m_summ.get("rank_icir"))
        except Exception as e:  # noqa: BLE001
            marg_mean_rank_ic = marg_rank_icir = None
            log.warning("marginal failed for %s: %s", fid, e)

        report.append({
            "factor": fid, "registry_status": status,
            "tier1": {
                "is_rank_icir": _f(wf_rows.get(fid, {}).get("heldout_rank_icir")),
                "sign_consistency": _f(wf_rows.get(fid, {}).get("sign_consistency")),
                "mean_rank_ic": _f(summ.get("mean_rank_ic")),
                "ic_hit_rate": _f(summ.get("ic_hit_rate")),
                "monotonic": bool(mono.get("is_monotonic")) if isinstance(mono, dict) and "is_monotonic" in mono else None,
                "monotonic_spearman": _f(mono.get("spearman_corr")) if isinstance(mono, dict) and "spearman_corr" in mono else None,
                "monotonic_reason": mono_reason,
                "ls_spread_20d": ls_spread,
                "turnover_ann": turn_ann,
                "coverage": coverage,
                "coverage_tier": cov_tier,
            },
            "tier2_vs_approved8": {
                "base_n": len(base),
                "leave_one_out": fid in APPROVED_8,
                "marginal_residual_mean_rank_ic": marg_mean_rank_ic,
                "marginal_residual_rank_icir": marg_rank_icir,
            },
        })

    payload = {
        "window": {"is_start": TIME_SPLIT.is_start, "is_end": TIME_SPLIT.is_end},
        "horizon": HORIZON, "reference_set": "approved_8",
        "marginal_t_bar": 3.0, "factors": report,
        "note": "Decay (Tier1 #6) + OOS (Tier3) deferred to full run. IS-only; no OOS spent.",
    }
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    log.info("=== UNIFIED EVAL PROBE (Tier1 + Tier2 vs approved-8) ===")
    log.info("%-28s %-9s %8s %8s %8s %7s %7s | %10s", "factor", "status", "isICIR", "meanRIC",
             "hit", "turn", "cov", "margRIC")
    for r in report:
        t1, t2 = r["tier1"], r["tier2_vs_approved8"]
        log.info("%-28s %-9s %8s %8s %8s %7s %7s | %10s",
                 r["factor"], r["registry_status"],
                 _p(t1["is_rank_icir"]), _p(t1["mean_rank_ic"]), _p(t1["ic_hit_rate"]),
                 _p(t1["turnover_ann"], 2), _p(t1["coverage"], 2),
                 _p(t2["marginal_residual_mean_rank_ic"]))
    log.info("wrote %s", OUT)
    return 0


def _turnover_annualized(fser: pd.Series, *, rebalance_days: int = 20) -> float:
    """Top-quintile one-way membership turnover at the actual rebalance frequency.

    Resample to every ``rebalance_days``-th IS trading date, compute one-way churn
    (|symmetric diff| / |union|) of the top-20% membership between consecutive rebalances,
    annualize via ``annualized_turnover(series, trading_days=252/rebalance_days)`` =
    mean(per-rebalance churn) * (rebalances per year)."""
    try:
        df = fser.dropna().reset_index()
        df.columns = ["datetime", "instrument", "val"]
        all_dates = sorted(df["datetime"].unique())
        rebal_dates = set(all_dates[::rebalance_days])
        churn, prev = [], None
        for dt, g in df.groupby("datetime"):
            if dt not in rebal_dates:
                continue
            thr = g["val"].quantile(0.8)
            top = set(g.loc[g["val"] >= thr, "instrument"])
            if prev is not None and (prev or top):
                churn.append(len(top ^ prev) / max(len(top | prev), 1))
            prev = top
        if not churn:
            return float("nan")
        return cae.annualized_turnover(pd.Series(churn), trading_days=252 / rebalance_days)
    except Exception:  # noqa: BLE001
        return float("nan")


def _f(v):
    if v is None:
        return None
    try:
        v = float(v)
        return None if v != v else v
    except (TypeError, ValueError):
        return None


def _p(v, nd=4):
    return f"{v:.{nd}f}" if isinstance(v, float) else "NA"


if __name__ == "__main__":
    raise SystemExit(main())
