# ──────────────────────────────────────────────────────────────────────
# script_status: research_tooling
# formal_research_allowed: false
# deployment_target: unified_eval_evidence_only
# requires_provider_manifest: false
# requires_preload_strict: false
# pr2_audit_class: C
# notes: |
#   Unified-eval production driver (P1b, verify pass on 7 factors). IS-only, zero OOS spend,
#   read-only w.r.t. all registries; output is descriptive EVIDENCE (workspace/outputs JSON),
#   never a registry mutation and never formal-run input. Methodology is frozen+hashed via
#   unified_eval_common.build_frozen_methodology (code commit + definition hashes included).
# ──────────────────────────────────────────────────────────────────────
"""P1b — production driver (verify pass): wire the unified-eval helpers into an end-to-end per-factor
record on the 7 representative factors, with the methodology FROZEN + HASHED.

Computes (all IS-only, zero OOS spend, reusing the tested unified_eval helpers):
  Tier 1: heldout RankICIR + sign-consistency (run_is_walk_forward); mean RankIC + IC hit-rate +
          HAC t (overlap-adjusted) + block-bootstrap CI; monotonicity shape (non-circular orientation,
          judged on the heldout window); one-way turnover; coverage + tier; leak-safe decay vector.
  Tier 2: residual IC vs approved-STABLE (leave-one-out) + approved-CURRENT + style_controls_v1
          (signed AND oriented), with label-aligned effective coverage.
Scale fast-paths: decay labels + residual control transforms precomputed ONCE (factor-independent).
"""
from __future__ import annotations

import json
import logging
import sys
import time
import traceback
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
np.seterr(all="ignore")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.alpha_research.factor_library import operators as op
from src.alpha_research.factor_library.catalog import get_factor_catalog
from src.alpha_research.factor_eval import ic_analysis as ica
from src.alpha_research.factor_eval import quantile_analysis as qa
from src.alpha_research.factor_eval.unified_eval import (
    STYLE_CONTROLS_V1,
    build_decay_labels,
    classify_quantile_shape,
    hac_mean_tstat,
    leak_safe_decay_ic_vector,
    moving_block_bootstrap_mean_ci,
    one_way_turnover,
    preprocess_for_residual,
    residual_ic_vs_controls,
    resolve_orientation,
)
from src.alpha_research.factor_lifecycle.walk_forward_validation import (
    build_is_windowed_panel,
    run_is_walk_forward,
)
from src.alpha_research.walk_forward import TimeSplit
from workspace.scripts.unified_eval_common import build_frozen_methodology

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("unified_eval_driver")

TIME_SPLIT = TimeSplit("2014-01-01", "2020-12-31", "2021-01-01", "2022-01-01")
HORIZON = 20
QLIB_DIR = PROJECT_ROOT / "data" / "qlib_data"
OUTDIR = PROJECT_ROOT / "workspace" / "outputs"
PANEL_CACHE = OUTDIR / "unified_eval_driver_panel.parquet"
OUT = OUTDIR / "unified_eval_driver.json"
ADJ_COL = "__adj_close__"
LABEL_COL = "__label__"

PICKS = {
    "earn_eps_diffusion_60": "approved", "liq_zero_ret_days_10d": "approved",
    "qual_piotroski_fscore_9pt": "approved", "liq_vol_cv_20d": "candidate",
    "qual_gross_profitability": "candidate", "rev_up_down_ratio_20d": "candidate",
    "qual_q_gross_margin": "draft",
}


def _to_dt_inst(s):
    return (s.swaplevel(0, 1) if s.index.names[0] != "datetime" else s).sort_index()


def _f(v):
    try:
        v = float(v)
        return None if v != v else v
    except (TypeError, ValueError):
        return None


def _build_or_load_panel(needed):
    if PANEL_CACHE.exists():
        log.info("Loading cached driver panel %s ...", PANEL_CACHE)
        return pd.read_parquet(PANEL_CACHE)
    full = get_factor_catalog(include_new_data=True)
    catalog = {n: full[n] for n in needed}
    catalog[ADJ_COL] = op.ADJ_CLOSE
    t0 = time.time()
    log.info("Computing %d factors + adj_close over [%s, %s] ...", len(needed),
             TIME_SPLIT.is_start, TIME_SPLIT.is_end)
    panel, _ = op.compute_factors(catalog=catalog, start_date=TIME_SPLIT.is_start,
                                  end_date=TIME_SPLIT.is_end, horizons=None,
                                  qlib_dir=str(QLIB_DIR), kernels=1, stage="is_only")
    log.info("Computed in %.0fs: shape=%s", time.time() - t0, panel.shape)
    OUTDIR.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(PANEL_CACHE)
    return panel


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    method = build_frozen_methodology(is_start=TIME_SPLIT.is_start, is_end=TIME_SPLIT.is_end)
    log.info("methodology_hash=%s (commit=%s)", method.methodology_hash, method.code_commit)
    reference_stable = list(method.reference_set_stable)
    approved_current = list(method.reference_set_current)

    needed = sorted(set(PICKS) | set(approved_current) | set(STYLE_CONTROLS_V1))
    raw = _build_or_load_panel(needed)

    adj_close = raw[ADJ_COL]
    factor_panel = raw[[c for c in raw.columns if c != ADJ_COL]]
    windowed = build_is_windowed_panel(factor_panel, adj_close, is_end=TIME_SPLIT.is_end, horizon=HORIZON)
    panel_index = factor_panel.index
    del factor_panel

    # heldout ICIR + sign for ALL factors in one pass
    wf = run_is_walk_forward(panel=windowed, time_split=TIME_SPLIT, horizon=HORIZON, factor_origin="a_priori")
    wf_rows = {r["factor"]: dict(r) for r in wf.rows}
    label = _to_dt_inst(windowed.label)
    del windowed  # free the ~380MB windowed subset before the per-factor loop

    # fac = column VIEWS into raw (instrument, datetime order) — NO 25× dti copies (the prior OOM).
    # Helpers normalize index order on demand; per-factor copies are transient and freed each iter.
    fac = {n: raw[n] for n in needed}
    all_dates = sorted(label.index.get_level_values("datetime").unique())
    cut = int(len(all_dates) * method.orientation_train_frac)
    orient_train = set(all_dates[:cut])                      # early window → orient sign ONLY
    shape_heldout = set(all_dates[cut:])                     # last 40% → judge shape (GPT R3: no circularity)
    rebal_schedule = all_dates[:: method.rebalance_days]     # FIXED cross-factor rebalance calendar

    # P1c scale fast-paths — both are factor-INDEPENDENT, so compute ONCE for the whole run:
    t0 = time.time()
    decay_labels = build_decay_labels(panel_index, adj_close, is_end=TIME_SPLIT.is_end,
                                      horizons=method.decay_horizons)
    log.info("decay labels (%s) built once in %.0fs", list(method.decay_horizons), time.time() - t0)
    t0 = time.time()
    processed = preprocess_for_residual(fac, needed, winsor=method.winsor_limits)
    log.info("winsor+cs-z transforms for %d names built once in %.0fs", len(processed), time.time() - t0)

    report = []
    for fid, status in PICKS.items():
      try:
        f_dt = _to_dt_inst(fac[fid])  # (datetime, instrument) for the IC/quantile helpers
        ic = ica.compute_ic_series(f_dt, label, min_obs=method.ic_min_obs)
        summ = ica.compute_ic_summary(ic)
        rank_ic = ic["RankIC"].dropna()
        hac = hac_mean_tstat(rank_ic, lags=method.hac_lags)

        # NON-circular orientation: sign from TRAIN window only; shape judged on HELDOUT window only.
        orient = resolve_orientation(rank_ic.rename(None), train_dates=orient_train,
                                     min_train_t=method.orientation_min_train_t)
        if orient["orientation_valid"]:
            of = f_dt * orient["sign"]
            oh = of[of.index.get_level_values("datetime").isin(shape_heldout)]
            lh = label[label.index.get_level_values("datetime").isin(shape_heldout)]
            try:
                qs = qa.compute_quantile_summary(
                    qa.compute_quantile_returns(oh, lh, n_quantiles=method.n_quantiles,
                                                min_obs=method.quantile_min_obs))
                mono = classify_quantile_shape(qs["annualized_return"].tolist())
            except Exception as e:  # noqa: BLE001
                mono = {"mono_shape": None, "mono_reason": f"error:{e}"}
        else:  # GPT R3: no intended-best shape claim when orientation is undetermined
            mono = {"mono_shape": None, "mono_reason": "orientation_undetermined"}

        boot = moving_block_bootstrap_mean_ci(rank_ic, block_len=method.bootstrap_block_len,
                                              n_boot=method.bootstrap_n_boot, ci=method.bootstrap_ci,
                                              seed=method.bootstrap_seed)
        turn = one_way_turnover(fac[fid], rebalance_dates=rebal_schedule, top_q=method.top_q,
                                trading_days=method.trading_days, min_names=method.turnover_min_names)
        cov = float(fac[fid].notna().mean())
        cov_tier = ("full" if cov >= method.coverage_full_min
                    else ("broad" if cov >= method.coverage_broad_min else "sub"))
        decay = leak_safe_decay_ic_vector(fac[fid], is_end=TIME_SPLIT.is_end,
                                          horizons=method.decay_horizons,
                                          precomputed_labels=decay_labels)

        # Tier 2: residual vs approved-STABLE (default) + approved-CURRENT (incl. provisionals, flagged)
        # + style_controls_v1; signed AND orientation-normalized (inverse factors: negative resid = good).
        osign = orient["sign"] if orient["orientation_valid"] else float("nan")
        resid_appr = residual_ic_vs_controls(fid, fac, label, control_names=[b for b in reference_stable if b != fid],
                                             winsor=method.winsor_limits, min_obs=method.residual_min_obs,
                                             hac_lags=method.hac_lags, processed_controls=processed)
        resid_cur = residual_ic_vs_controls(fid, fac, label, control_names=[b for b in approved_current if b != fid],
                                            winsor=method.winsor_limits, min_obs=method.residual_min_obs,
                                            hac_lags=method.hac_lags, processed_controls=processed)
        resid_style = residual_ic_vs_controls(fid, fac, label, control_names=[c for c in STYLE_CONTROLS_V1 if c != fid],
                                              winsor=method.winsor_limits, min_obs=method.residual_min_obs,
                                              hac_lags=method.hac_lags, processed_controls=processed)

        report.append({
            "factor": fid, "registry_status": status, "methodology_hash": method.methodology_hash,
            "tier1": {
                "heldout_rank_icir": wf_rows.get(fid, {}).get("heldout_rank_icir"),
                "sign_consistency": wf_rows.get(fid, {}).get("sign_consistency"),
                "mean_rank_ic": summ.get("mean_rank_ic"), "ic_hit_rate": summ.get("ic_hit_rate"),
                "mean_rank_ic_hac_t": hac.get("hac_t"), "hac_small_sample": hac.get("small_sample_warning"),
                "mean_rank_ic_boot_ci": [_f(boot.get("ci_low")), _f(boot.get("ci_high"))],
                "mono_shape": mono.get("mono_shape"), "mono_reason": mono.get("mono_reason"),
                "shape_eval_window": method.shape_eval_window,
                "direction_source": orient["direction_source"], "orientation_valid": orient["orientation_valid"],
                "turnover_ann": turn.get("turnover_ann"), "tie_rate": turn.get("tie_rate"),
                "bottom_turnover_ann": turn.get("bottom_turnover_ann"),
                "coverage": cov, "coverage_tier": cov_tier,
                "decay_vector": {h: v["rank_icir"] for h, v in decay["vector"].items()},
                "decay_half_life_vs_shortest": decay["half_life_vs_shortest"],
            },
            "tier2": {
                # signed residual IC + orientation-normalized (inverse factors: a negative signed
                # residual is GOOD; oriented = sign × signed, so "more positive oriented" = more marginal)
                "resid_ic_vs_approved_stable_signed": resid_appr.get("residual_mean_rank_ic"),
                "resid_ic_vs_approved_stable_oriented": _f(osign * resid_appr["residual_mean_rank_ic"])
                    if resid_appr.get("residual_mean_rank_ic") is not None and osign == osign else None,
                "resid_eff_coverage_vs_approved_stable": resid_appr.get("effective_residual_coverage"),
                "resid_ic_vs_approved_current_signed": resid_cur.get("residual_mean_rank_ic"),
                "resid_ic_vs_style_controls_v1_signed": resid_style.get("residual_mean_rank_ic"),
                "resid_ic_vs_style_controls_v1_oriented": _f(osign * resid_style["residual_mean_rank_ic"])
                    if resid_style.get("residual_mean_rank_ic") is not None and osign == osign else None,
                "resid_hac_t_vs_style_controls_v1": resid_style.get("residual_hac_t"),
                "resid_eff_coverage_vs_style_controls_v1": resid_style.get("effective_residual_coverage"),
                "reference_set_note": "stable EXCLUDES the 2 provisional report_rc approvals; current INCLUDES them",
            },
        })
        log.info("done %s", fid)
      except Exception as exc:  # noqa: BLE001 — log + continue so one bad factor doesn't abort the run
        log.error("FAILED %s: %s", fid, exc)
        traceback.print_exc()
        report.append({"factor": fid, "registry_status": status,
                       "error": f"{type(exc).__name__}: {exc}"})

    payload = {
        "methodology": {
            "hash": method.methodology_hash, "code_commit": method.code_commit,
            "is_window": [TIME_SPLIT.is_start, TIME_SPLIT.is_end],
            "reference_set_stable": reference_stable,
            "provisional_excluded": list(method.provisional_factors),
            "style_controls_v1": list(STYLE_CONTROLS_V1), "hac_lags": method.hac_lags,
            "benchmark_policy": method.benchmark_policy, "mt_t_bar": method.mt_t_bar,
            "definition_hashes_pinned": bool(method.reference_set_definition_hashes),
        },
        "companion_outputs": ["unified_eval_driver_data.json (neutralized IC + long-leg vs benchmarks, "
                              "same methodology_hash)"],
        "factors": report,
    }
    OUT.write_text(json.dumps(payload, indent=2, default=lambda x: None), encoding="utf-8")
    log.info("=== UNIFIED EVAL DRIVER (methodology_hash=%s) ===", method.methodology_hash)
    log.info("%-28s %-9s %8s %8s %7s %6s %-14s %10s %10s", "factor", "status", "heldICIR", "HAC-t",
             "turn", "cov", "mono_shape", "rsd_appr", "rsd_style")
    for r in report:
        if "error" in r:
            log.info("%-28s FAILED: %s", r["factor"], r["error"])
            continue
        t1, t2 = r["tier1"], r["tier2"]
        def p(x, n=3):
            return f"{x:.{n}f}" if isinstance(x, (int, float)) else "NA"
        log.info("%-28s %-9s %8s %8s %7s %6s %-14s %10s %10s", r["factor"], r["registry_status"],
                 p(t1["heldout_rank_icir"]), p(t1["mean_rank_ic_hac_t"], 2), p(t1["turnover_ann"], 1),
                 p(t1["coverage"], 2), str(t1["mono_shape"]),
                 p(t2["resid_ic_vs_approved_stable_oriented"]), p(t2["resid_ic_vs_style_controls_v1_oriented"]))
    log.info("wrote %s", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
