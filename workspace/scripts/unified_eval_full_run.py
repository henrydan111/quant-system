# ──────────────────────────────────────────────────────────────────────
# script_status: research_tooling
# formal_research_allowed: false
# deployment_target: unified_eval_evidence_only
# requires_provider_manifest: false
# requires_preload_strict: false
# pr2_audit_class: C
# notes: |
#   P1c — FULL-CATALOG unified evaluation (every catalog factor: base + composite +
#   industry-relative). IS-only (2014–2020), zero OOS spend, read-only w.r.t. all
#   registries; output is descriptive EVIDENCE (workspace/outputs/unified_eval/) for the
#   dashboard, never a registry mutation and never formal-run input. Methodology frozen +
#   hashed via unified_eval_common.build_frozen_methodology. Batched (memory: a 185-column
#   full panel would be ~7GB; batches of ~15 keep peak <3GB) and RESUMABLE (per-factor
#   JSONL append; restart skips completed factors). Field-ineligible factors are recorded
#   as explicit rows, never silently dropped. $total_mv / index $close come via bare
#   D.features — MARKET data (not PIT statement fundamentals); sandbox-grade path.
# ──────────────────────────────────────────────────────────────────────
"""P1c full-catalog unified factor evaluation — batched, resumable, evidence-only."""
from __future__ import annotations

import argparse
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

from src.alpha_research.factor_library import (
    add_composites,
    add_industry_relative_composites,
    get_composite_defs,
    get_factor_catalog,
)
from src.alpha_research.factor_library.catalog import get_industry_relative_defs
from src.alpha_research.factor_library import operators as op
from src.alpha_research.factor_eval import ic_analysis as ica
from src.alpha_research.factor_eval import quantile_analysis as qa
from src.alpha_research.factor_eval.unified_eval import (
    STYLE_CONTROLS_V1,
    build_decay_labels,
    classify_quantile_shape,
    hac_mean_tstat,
    index_forward_returns,
    leak_safe_decay_ic_vector,
    long_leg_excess_ir,
    moving_block_bootstrap_mean_ci,
    neutralized_rank_icir,
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
from src.research_orchestrator.factor_lifecycle_steps import per_factor_field_eligible
from workspace.scripts.unified_eval_common import build_frozen_methodology

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("unified_eval_full")

# IS window 2010-2020 (user decision 2026-06-12: data exists from 2008; TTM warmup +
# GFC regime exclude 2008-09; five style regimes covered. Pre-decision evidence rows
# carry the old 2014-window methodology hashes — never mix.)
TIME_SPLIT = TimeSplit("2010-01-01", "2020-12-31", "2021-01-01", "2022-01-01")
HORIZON = 20
QLIB_DIR = PROJECT_ROOT / "data" / "qlib_data"
OUTDIR = PROJECT_ROOT / "workspace" / "outputs" / "unified_eval"
SEED_PANEL = PROJECT_ROOT / "workspace" / "outputs" / "unified_eval_driver_panel.parquet"  # 25 cols + adj
MCAP_CACHE = PROJECT_ROOT / "workspace" / "outputs" / "unified_eval_mcap.parquet"
RESULTS_JSONL = OUTDIR / "results.jsonl"
COMPONENT_CACHE = OUTDIR / "layer2_components.parquet"
FINAL_PARQUET = OUTDIR / "unified_eval_full.parquet"
ADJ_COL = "__adj_close__"
BENCHMARKS = {"CSI300": "000300_SH", "CSI500": "000905_SH"}


def _to_dt_inst(s):
    return (s.swaplevel(0, 1) if s.index.names[0] != "datetime" else s).sort_index()


def _f(v):
    try:
        v = float(v)
        return None if v != v else v
    except (TypeError, ValueError):
        return None


def _done_factors(results_path=None) -> set:
    path = results_path or RESULTS_JSONL
    if not path.exists():
        return set()
    done = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
            done.add((rec["factor"], rec.get("universe_id")) if "universe_id" in rec
                     else rec["factor"])
        except Exception:  # noqa: BLE001
            continue
    return done


def _append_result(rec: dict, results_path=None) -> None:
    path = results_path or RESULTS_JSONL
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, default=lambda x: None) + "\n")


def _registry_status() -> dict:
    m = pd.read_parquet(PROJECT_ROOT / "data" / "factor_registry" / "factor_master.parquet")
    cur = m[m["is_current"] == True]  # noqa: E712
    return {r["factor_id"]: {"status": str(r.get("status")), "kind": str(r.get("factor_kind")),
                             "category": str(r.get("category"))} for _, r in cur.iterrows()}


def _load_mcap(instruments) -> pd.Series:
    if MCAP_CACHE.exists():
        return pd.read_parquet(MCAP_CACHE)["mcap"]
    import qlib
    from qlib.data import D
    qlib.init(provider_uri=str(QLIB_DIR), region="cn")
    df = D.features(sorted(instruments), ["$total_mv"], start_time=TIME_SPLIT.is_start,
                    end_time=TIME_SPLIT.is_end)
    mcap = df["$total_mv"].rename("mcap")
    mcap.to_frame().to_parquet(MCAP_CACHE)
    return mcap


def _bench_fwd() -> dict:
    import qlib
    from qlib.data import D
    qlib.init(provider_uri=str(QLIB_DIR), region="cn")
    out = {}
    for name, code in BENCHMARKS.items():
        df = D.features([code], ["$close"], start_time=TIME_SPLIT.is_start, end_time=TIME_SPLIT.is_end)
        close = df["$close"].xs(code, level=df.index.names[0]) if df.index.nlevels > 1 else df["$close"]
        close.index = pd.DatetimeIndex([pd.Timestamp(d) for d in close.index])
        out[name] = index_forward_returns(close, horizon=HORIZON, is_end=TIME_SPLIT.is_end)
    return out


def _compute_batch(names: list, include_adj: bool) -> pd.DataFrame:
    catalog = {n: get_factor_catalog(include_new_data=True)[n] for n in names}
    if include_adj:
        catalog[ADJ_COL] = op.ADJ_CLOSE
    t0 = time.time()
    log.info("compute_factors: %d fields ...", len(catalog))
    panel, _ = op.compute_factors(catalog=catalog, start_date=TIME_SPLIT.is_start,
                                  end_date=TIME_SPLIT.is_end, horizons=None,
                                  qlib_dir=str(QLIB_DIR), kernels=1, stage="is_only")
    log.info("computed %d fields in %.0fs", len(catalog), time.time() - t0)
    return panel


def _evaluate_batch(batch_df: pd.DataFrame, names: list, ctx: dict) -> None:
    """Evaluate `names` (columns of batch_df) and append one JSONL record each.

    F2: ctx may carry ``results_path`` (output JSONL override) and ``record_extra``
    (dict merged into every record — the universe-matrix driver stamps
    ``universe_id`` this way). Defaults preserve the original single-domain run.
    """
    method = ctx["method"]
    results_path = ctx.get("results_path")
    record_extra = ctx.get("record_extra") or {}
    # heldout walk-forward for the whole batch in one pass
    windowed = build_is_windowed_panel(batch_df[names], ctx["adj_close"], is_end=TIME_SPLIT.is_end,
                                       horizon=HORIZON)
    wf = run_is_walk_forward(panel=windowed, time_split=TIME_SPLIT, horizon=HORIZON,
                             factor_origin="a_priori")
    wf_rows = {r["factor"]: dict(r) for r in wf.rows}
    del windowed
    batch_processed = preprocess_for_residual({n: batch_df[n] for n in names}, names,
                                              winsor=method.winsor_limits)
    processed = {**ctx["resident_processed"], **batch_processed}
    fac_all = {**ctx["resident_raw"], **{n: batch_df[n] for n in names}}
    label = ctx["label"]

    for fid in names:
      try:
        t0 = time.time()
        f_raw = batch_df[fid]
        f_dt = _to_dt_inst(f_raw)
        ic = ica.compute_ic_series(f_dt, label, min_obs=method.ic_min_obs)
        summ = ica.compute_ic_summary(ic)
        rank_ic = ic["RankIC"].dropna()
        hac = hac_mean_tstat(rank_ic, lags=method.hac_lags)
        boot = moving_block_bootstrap_mean_ci(rank_ic, block_len=method.bootstrap_block_len,
                                              n_boot=method.bootstrap_n_boot, ci=method.bootstrap_ci,
                                              seed=method.bootstrap_seed)
        orient = resolve_orientation(rank_ic.rename(None), train_dates=ctx["orient_train"],
                                     min_train_t=method.orientation_min_train_t)
        # decile profile: oriented when orientation is valid; otherwise UN-oriented
        # (raw factor-ascending) fallback so every factor with enough cross-sections
        # still gets a 10-group chart (orientation_undetermined factors are weak-signal,
        # raw deciles are the honest view — we don't claim a direction). The profile is
        # tagged `oriented` so the dashboard can mark raw bars.
        oriented = bool(orient["orientation_valid"])
        of = (f_dt * orient["sign"]) if oriented else f_dt
        oh = of[of.index.get_level_values("datetime").isin(ctx["shape_heldout"])]
        lh = label[label.index.get_level_values("datetime").isin(ctx["shape_heldout"])]
        try:
            qdf = qa.compute_quantile_returns(oh, lh, n_quantiles=method.n_quantiles,
                                              min_obs=method.quantile_min_obs)
            qs = qa.compute_quantile_summary(qdf)
            if oriented:
                mono = classify_quantile_shape(qs["annualized_return"].tolist())
            else:
                mono = {"mono_shape": None, "mono_reason": "orientation_undetermined"}
            bucket_counts = qdf.groupby("quantile")["count"].mean()
            q_profile = [
                {"q": int(q), "ann_return": round(float(r), 6),
                 "mean_count": round(float(bucket_counts.get(q, float("nan"))), 1),
                 "oriented": oriented}
                for q, r in qs["annualized_return"].items()
            ]
            if not q_profile:
                q_profile = None
        except Exception as e:  # noqa: BLE001
            mono = {"mono_shape": None, "mono_reason": f"error:{e}"}
            q_profile = None

        turn = one_way_turnover(f_raw, rebalance_dates=ctx["rebal_schedule"], top_q=method.top_q,
                                trading_days=method.trading_days, min_names=method.turnover_min_names)
        # F2: in a domain run the denominator must be the DOMAIN breadth, not the full
        # panel (a factor covering 80% of csi300 must not read cov=0.07). ctx carries
        # the total in-domain cells count for the masked panel; default = full panel.
        domain_cells = ctx.get("domain_total_cells")
        cov = float(f_raw.notna().sum() / domain_cells) if domain_cells else float(f_raw.notna().mean())
        cov_tier = ("full" if cov >= method.coverage_full_min
                    else ("broad" if cov >= method.coverage_broad_min else "sub"))
        decay = leak_safe_decay_ic_vector(f_raw, is_end=TIME_SPLIT.is_end,
                                          horizons=method.decay_horizons,
                                          precomputed_labels=ctx["decay_labels"])
        neut = neutralized_rank_icir(f_raw, label, ctx["mcap"], ctx["industry"],
                                     min_obs=method.neutralized_ic_min_obs,
                                     neutralize_min_obs=method.neutralize_min_obs,
                                     hac_lags=method.hac_lags)
        osign = orient["sign"] if orient["orientation_valid"] else float("nan")
        stable = [b for b in ctx["reference_stable"] if b != fid]
        current = [b for b in ctx["approved_current"] if b != fid]
        styles = [c for c in STYLE_CONTROLS_V1 if c != fid]
        r_st = residual_ic_vs_controls(fid, fac_all, label, control_names=stable,
                                       winsor=method.winsor_limits, min_obs=method.residual_min_obs,
                                       hac_lags=method.hac_lags, processed_controls=processed)
        r_cu = residual_ic_vs_controls(fid, fac_all, label, control_names=current,
                                       winsor=method.winsor_limits, min_obs=method.residual_min_obs,
                                       hac_lags=method.hac_lags, processed_controls=processed)
        r_sty = residual_ic_vs_controls(fid, fac_all, label, control_names=styles,
                                        winsor=method.winsor_limits, min_obs=method.residual_min_obs,
                                        hac_lags=method.hac_lags, processed_controls=processed)
        legs = {}
        if orient["orientation_valid"]:
            of = f_dt * orient["sign"]
            for bname, bench in ctx["benches"].items():
                try:
                    r = long_leg_excess_ir(of, label, bench, top_q=method.top_q,
                                           cost_bps_per_turnover=method.cost_bps_per_turnover,
                                           rebalance_days=method.rebalance_days,
                                           rebalance_dates=ctx["rebal_schedule"], horizon=method.horizon,
                                           min_names=method.long_leg_min_names,
                                           include_initial_cost=method.include_initial_cost)
                    legs[bname] = {"excess_ann": r["long_leg_excess_ann"],
                                   "ir_proxy_is": r["long_leg_excess_ir_proxy_is"]}
                except Exception as e:  # noqa: BLE001
                    legs[bname] = {"error": str(e)[:120]}
        else:
            legs = {b: {"excess_ann": None, "ir_proxy_is": None, "reason": "orientation_undetermined"}
                    for b in ctx["benches"]}

        reg = ctx["registry"].get(fid, {})
        # effective-window governance (2026-06-12): first-class window-truncation fields.
        # effective_start/end from the IC date axis (cross-sections meeting ic_min_obs);
        # window_tier per the governance rule: full >=90% / partial >=50% / short <50%.
        _ic_dates = rank_ic.index
        _wcov = float(len(_ic_dates) / max(1, len(ctx["orient_train"]) + len(ctx["shape_heldout"])))
        _tier = "full_window" if _wcov >= 0.9 else ("partial_window" if _wcov >= 0.5 else "short_window")
        _append_result({
            "factor": fid, "field_eligible": True, **record_extra,
            "effective_start": str(_ic_dates.min().date()) if len(_ic_dates) else None,
            "effective_end": str(_ic_dates.max().date()) if len(_ic_dates) else None,
            "effective_ic_days": int(len(_ic_dates)),
            "window_coverage": round(_wcov, 4), "window_tier": _tier,
            "registry_status": reg.get("status"), "factor_kind": reg.get("kind"),
            "category": reg.get("category"), "methodology_hash": method.methodology_hash,
            # reference-decoupling (PR-1b): the LIVE identity is layer1_methodology_hash (stable across
            # approved-book churn); the two reference hashes identify the ACTUAL neutralization book used
            # for r_st/r_cu below (ctx book == method book in production). methodology_hash retained as legacy.
            "methodology_schema_version": method.methodology_schema_version,
            "layer1_methodology_hash": method.layer1_methodology_hash,
            "reference_set_stable_hash": method._ref_hash(ctx["reference_stable"]),
            "reference_set_current_hash": method._ref_hash(ctx["approved_current"]),
            "heldout_rank_icir": _f(wf_rows.get(fid, {}).get("heldout_rank_icir")),
            "sign_consistency": _f(wf_rows.get(fid, {}).get("sign_consistency")),
            "mean_rank_ic": _f(summ.get("mean_rank_ic")), "ic_hit_rate": _f(summ.get("ic_hit_rate")),
            "mean_rank_ic_hac_t": _f(hac.get("hac_t")), "hac_small_sample": hac.get("small_sample_warning"),
            "boot_ci_low": _f(boot.get("ci_low")), "boot_ci_high": _f(boot.get("ci_high")),
            "neutralized_rank_icir": _f(neut.get("neutralized_rank_icir")),
            "neutralized_hac_t": _f(neut.get("neutralized_hac_t")),
            "mono_shape": mono.get("mono_shape"), "mono_reason": mono.get("mono_reason"),
            "quantile_profile": q_profile,
            "direction_source": orient["direction_source"], "orientation_valid": orient["orientation_valid"],
            "turnover_ann": _f(turn.get("turnover_ann")), "tie_rate": _f(turn.get("tie_rate")),
            "coverage": cov, "coverage_tier": cov_tier,
            "decay_icir_5": _f(decay["vector"].get(5, {}).get("rank_icir")),
            "decay_icir_10": _f(decay["vector"].get(10, {}).get("rank_icir")),
            "decay_icir_20": _f(decay["vector"].get(20, {}).get("rank_icir")),
            "decay_icir_40": _f(decay["vector"].get(40, {}).get("rank_icir")),
            "decay_half_life_vs_shortest": decay["half_life_vs_shortest"],
            "resid_ic_vs_approved_stable_signed": r_st.get("residual_mean_rank_ic"),
            "resid_ic_vs_approved_stable_oriented": _f(osign * r_st["residual_mean_rank_ic"])
                if r_st.get("residual_mean_rank_ic") is not None and osign == osign else None,
            "resid_hac_t_vs_approved_stable": _f(r_st.get("residual_hac_t")),
            "resid_eff_coverage_vs_approved_stable": _f(r_st.get("effective_residual_coverage")),
            "resid_ic_vs_approved_current_signed": r_cu.get("residual_mean_rank_ic"),
            "resid_ic_vs_style_controls_v1_signed": r_sty.get("residual_mean_rank_ic"),
            "resid_ic_vs_style_controls_v1_oriented": _f(osign * r_sty["residual_mean_rank_ic"])
                if r_sty.get("residual_mean_rank_ic") is not None and osign == osign else None,
            "resid_hac_t_vs_style_controls_v1": _f(r_sty.get("residual_hac_t")),
            "resid_eff_coverage_vs_style_controls_v1": _f(r_sty.get("effective_residual_coverage")),
            "long_leg_excess_ann_csi300": _f(legs.get("CSI300", {}).get("excess_ann")),
            "long_leg_ir_proxy_is_csi300": _f(legs.get("CSI300", {}).get("ir_proxy_is")),
            "long_leg_excess_ann_csi500": _f(legs.get("CSI500", {}).get("excess_ann")),
            "long_leg_ir_proxy_is_csi500": _f(legs.get("CSI500", {}).get("ir_proxy_is")),
            "eval_seconds": round(time.time() - t0, 1),
        }, results_path)
        log.info("done %s%s (%.0fs)", fid,
                 f"@{record_extra.get('universe_id')}" if record_extra.get('universe_id') else "",
                 time.time() - t0)
      except Exception as exc:  # noqa: BLE001
        log.error("FAILED %s: %s", fid, exc)
        traceback.print_exc()
        _append_result({"factor": fid, "field_eligible": True, **record_extra,
                        "error": f"{type(exc).__name__}: {exc}"}, results_path)


def main() -> int:
    global OUTDIR, RESULTS_JSONL, COMPONENT_CACHE, FINAL_PARQUET
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-size", type=int, default=15)
    ap.add_argument("--limit", type=int, default=0, help="evaluate at most N factors (smoke test)")
    ap.add_argument("--factors", default="", help="comma list: restrict the eval to these catalog "
                    "factors (subset evidence run, e.g. a masked-vs-unmasked comparison)")
    ap.add_argument("--outdir", default="", help="redirect ALL outputs (results.jsonl/methodology/"
                    "final parquet) to this dir — REQUIRED with --factors so a subset run can never "
                    "mix into the production results.jsonl")
    args = ap.parse_args()
    if args.factors and not args.outdir:
        raise SystemExit("--factors requires --outdir (subset runs must not touch the production outdir)")
    if args.outdir:
        OUTDIR = Path(args.outdir)
        RESULTS_JSONL = OUTDIR / "results.jsonl"
        COMPONENT_CACHE = OUTDIR / "layer2_components.parquet"
        FINAL_PARQUET = OUTDIR / "unified_eval_full.parquet"
    OUTDIR.mkdir(parents=True, exist_ok=True)

    method = build_frozen_methodology(is_start=TIME_SPLIT.is_start, is_end=TIME_SPLIT.is_end)
    # RESUME PINNING: a resumed run must stamp the SAME methodology_hash as the rows already on
    # disk. If only code_commit moved (a mid-run commit unrelated to the eval), re-pin to the run's
    # original commit; if anything ELSE differs (reference set / definitions / knobs), refuse to mix.
    mfile = OUTDIR / "methodology.json"
    if mfile.exists() and RESULTS_JSONL.exists():
        saved = json.loads(mfile.read_text(encoding="utf-8"))
        # A1 (GPT impl-review): resume identity is layer1_methodology_hash (reference-EXCLUDED) so
        # approval churn does NOT force a rebaseline here either; a protocol/STYLE change still does.
        saved_l1 = saved.get("layer1_hash")
        if saved_l1:
            if saved_l1 != method.layer1_methodology_hash:
                from dataclasses import replace
                repinned = replace(method, code_commit=str(saved.get("code_commit", "")))
                if repinned.layer1_methodology_hash == saved_l1:
                    log.warning("resume across a code commit: re-pinning to the run's original "
                                "layer1 hash %s", saved_l1)
                    method = repinned
                else:
                    raise RuntimeError(
                        f"LAYER-1 methodology drift on resume: saved layer1 {saved_l1} != current "
                        f"{method.layer1_methodology_hash} (protocol/STYLE_CONTROLS change, NOT approval "
                        "churn) — clear workspace/outputs/unified_eval/ for a deliberate re-baseline")
        elif saved.get("hash"):
            raise SystemExit(
                "workspace/outputs/unified_eval/methodology.json is LEGACY (no layer1_hash) — its "
                f"residuals used the OLD approved book. Clear the dir to re-run under schema "
                f"{method.methodology_schema_version}, or migrate it explicitly. Refusing to silently "
                "rewrite the audit trail (GPT impl-review A1).")
    log.info("layer1=%s (legacy=%s commit=%s)", method.layer1_methodology_hash,
             method.methodology_hash, method.code_commit)
    (OUTDIR / "methodology.json").write_text(json.dumps({
        "hash": method.methodology_hash, "layer1_hash": method.layer1_methodology_hash,
        "methodology_schema_version": method.methodology_schema_version,
        "reference_set_stable_hash": method.reference_set_stable_hash,
        "reference_set_current_hash": method.reference_set_current_hash,
        "code_commit": method.code_commit,
        "is_window": [TIME_SPLIT.is_start, TIME_SPLIT.is_end],
        "reference_set_stable": list(method.reference_set_stable),
        "reference_set_current": list(method.reference_set_current),
        "provisional_factors": list(method.provisional_factors),
        "style_controls_v1": list(STYLE_CONTROLS_V1),
        "benchmark_policy": method.benchmark_policy, "mt_t_bar": method.mt_t_bar,
        "note": "IS-only descriptive evidence; never mutates registry status (resolve-but-label).",
    }, indent=2), encoding="utf-8")

    full = get_factor_catalog(include_new_data=True)
    requested: list[str] = []
    if args.factors:
        requested = [f.strip() for f in args.factors.split(",") if f.strip()]
        unknown = [f for f in requested if f not in full]
        if unknown:
            raise SystemExit(f"--factors not in catalog: {unknown}")
        full = {n: full[n] for n in requested}
    elig = per_factor_field_eligible(list(full), stage="formal_validation")
    base_ok = sorted(n for n, v in elig.items() if v)
    base_bad = sorted(n for n, v in elig.items() if not v)
    registry = _registry_status()
    done = _done_factors()
    log.info("base: %d eligible / %d ineligible | already done: %d", len(base_ok), len(base_bad), len(done))

    for fid in base_bad:
        if fid not in done:
            reg = registry.get(fid, {})
            _append_result({"factor": fid, "field_eligible": False,
                            "registry_status": reg.get("status"), "factor_kind": reg.get("kind"),
                            "category": reg.get("category"),
                            "methodology_hash": method.methodology_hash,
                            "mono_reason": "field_ineligible(quarantined/unregistered fields)"})
            done.add(fid)
            log.info("recorded field-ineligible: %s", fid)

    # ---- stage 0: residents from the seed panel (style controls + approved + adj_close)
    resident_names = sorted(set(STYLE_CONTROLS_V1) | set(method.reference_set_current))
    seed = pd.read_parquet(SEED_PANEL)
    missing_residents = [n for n in resident_names if n not in seed.columns]
    if missing_residents:
        extra = _compute_batch(missing_residents, include_adj=False)
        seed = pd.concat([seed, extra], axis=1)
    adj_close = seed[ADJ_COL]
    panel_index = seed.index

    decay_labels = build_decay_labels(panel_index, adj_close, is_end=TIME_SPLIT.is_end,
                                      horizons=method.decay_horizons)
    label = decay_labels[HORIZON]["label"]
    all_dates = sorted(label.index.get_level_values("datetime").unique())
    cut = int(len(all_dates) * method.orientation_train_frac)
    ctx = {
        "method": method, "adj_close": adj_close, "label": label, "decay_labels": decay_labels,
        "orient_train": set(all_dates[:cut]), "shape_heldout": set(all_dates[cut:]),
        "rebal_schedule": all_dates[:: method.rebalance_days],
        "reference_stable": list(method.reference_set_stable),
        "approved_current": list(method.reference_set_current),
        "registry": registry,
        "resident_raw": {n: seed[n] for n in resident_names},
        "resident_processed": preprocess_for_residual({n: seed[n] for n in resident_names},
                                                      resident_names, winsor=method.winsor_limits),
        "mcap": _load_mcap(panel_index.get_level_values("instrument").unique()),
        "industry": None,  # filled below
        "benches": _bench_fwd(),
    }
    from src.data_infra import provider_metadata as pm
    log.info("building PIT SW2021 industry labels ...")
    ctx["industry"] = pm.build_industry_series_asof(panel_index, level="L1")

    evaluated = 0
    limit = args.limit or 10**9

    # ---- batch 0: factors already in the seed panel
    seed_factors = [n for n in seed.columns if n != ADJ_COL and n in full and n in base_ok
                    and n not in done]
    if seed_factors and evaluated < limit:
        take = seed_factors[: max(0, limit - evaluated)]
        log.info("batch 0 (seed panel): %d factors", len(take))
        _evaluate_batch(seed, take, ctx)
        evaluated += len(take)
    # save layer-2 components present in the seed panel
    comp_needed = set()
    for c in get_composite_defs():
        comp_needed.update(c["components"])
    for d in get_industry_relative_defs():  # industry-relative defs carry a single `base` component
        if d.get("base"):
            comp_needed.add(d["base"])
    comp_store = {n: seed[n] for n in comp_needed if n in seed.columns}
    del seed

    # ---- remaining base factors in batches
    remaining = [n for n in base_ok if n not in done and n not in
                 set(ctx["resident_raw"])]  # residents already evaluated via batch 0
    remaining = [n for n in remaining if n not in _done_factors()]
    log.info("remaining base factors to compute: %d", len(remaining))
    bs = max(1, args.batch_size)
    for i in range(0, len(remaining), bs):
        if evaluated >= limit:
            break
        batch_names = remaining[i: i + bs]
        batch_df = _compute_batch(batch_names, include_adj=False)
        if not batch_df.index.equals(panel_index):
            batch_df = batch_df.reindex(panel_index)
        take = batch_names[: max(0, limit - evaluated)]
        log.info("batch %d: %d factors", i // bs + 1, len(take))
        _evaluate_batch(batch_df, take, ctx)
        evaluated += len(take)
        for n in batch_names:
            if n in comp_needed:
                comp_store[n] = batch_df[n]
        del batch_df

    # ---- layer-2: composites + industry-relative
    done = _done_factors()
    comp_defs = get_composite_defs()
    ind_defs = get_industry_relative_defs()
    layer2_names = [c["name"] for c in comp_defs] + [d["name"] for d in ind_defs]
    if requested:
        layer2_names = [n for n in layer2_names if n in requested]
    layer2_todo = [n for n in layer2_names if n not in done]
    if layer2_todo and evaluated < limit:
        missing_comp = [n for n in comp_needed if n not in comp_store]
        if missing_comp:
            extra = _compute_batch(missing_comp, include_adj=False)
            for n in missing_comp:
                comp_store[n] = extra[n].reindex(panel_index) if not extra.index.equals(panel_index) else extra[n]
            del extra
        base_df = pd.DataFrame(comp_store)
        log.info("building %d composites + %d industry-relative from %d components ...",
                 len(comp_defs), len(ind_defs), len(comp_store))
        l2 = add_composites(base_df, comp_defs)
        l2 = add_industry_relative_composites(l2, ctx["industry"], ctx["mcap"], defs=ind_defs)
        l2_df = l2[[n for n in layer2_todo if n in l2.columns]]
        take = list(l2_df.columns)[: max(0, limit - evaluated)]
        log.info("layer-2 batch: %d factors", len(take))
        _evaluate_batch(l2_df, take, ctx)
        evaluated += len(take)

    # ---- assemble final parquet
    rows = [json.loads(line) for line in RESULTS_JSONL.read_text(encoding="utf-8").splitlines()]
    dedup = {}
    for r in rows:
        dedup[r["factor"]] = r  # last wins
    out = pd.DataFrame(list(dedup.values()))
    out.to_parquet(FINAL_PARQUET, index=False)
    n_err = int(out.get("error").notna().sum()) if "error" in out.columns else 0
    log.info("=== FULL RUN ASSEMBLED: %d rows (%d errors) -> %s ===", len(out), n_err, FINAL_PARQUET)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
