# ──────────────────────────────────────────────────────────────────────
# script_status: research_tooling
# formal_research_allowed: false
# deployment_target: unified_eval_evidence_only
# notes: |
#   F2 — FULL-CATALOG × 7-UNIVERSE evidence matrix (universe plan Draft-7 §3.2).
#   Same engine and metric set as unified_eval_full_run (its _evaluate_batch is
#   reused verbatim via ctx parameterization); the universe enters as a NaN mask
#   applied to each factor BEFORE evaluation, which automatically scopes every
#   metric — heldout walk-forward, HAC, NEUTRALIZED IC (within-domain regression,
#   the §3.7 diagnostic), residuals, quantile profile, turnover — to the domain
#   cross-section. One frozen methodology per universe (7 hashes). IS-only
#   (2014-2020), zero OOS spend, evidence-only. Resumable per (factor, universe).
# ──────────────────────────────────────────────────────────────────────
"""F2 universe-matrix evaluation: every catalog factor × all 7 universes."""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
np.seterr(all="ignore")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.alpha_research.factor_library import get_factor_catalog  # noqa: E402
from src.alpha_research.factor_library import operators as op  # noqa: E402
from src.alpha_research.factor_eval import universes as uv  # noqa: E402
from src.alpha_research.factor_eval.unified_eval import (  # noqa: E402
    STYLE_CONTROLS_V1, build_decay_labels, preprocess_for_residual,
)
from src.data_infra import universe_membership as um  # noqa: E402
from src.research_orchestrator.factor_lifecycle_steps import per_factor_field_eligible  # noqa: E402
from workspace.scripts.unified_eval_common import build_frozen_methodology  # noqa: E402
from workspace.scripts import unified_eval_full_run as fr  # noqa: E402

log = logging.getLogger("unified_eval_matrix")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

TIME_SPLIT = fr.TIME_SPLIT
HORIZON = fr.HORIZON
ADJ_COL = fr.ADJ_COL
OUTDIR = PROJECT_ROOT / "workspace" / "outputs" / "unified_eval_matrix"
RESULTS = OUTDIR / "results.jsonl"
MASK_CACHE = OUTDIR / f"universe_masks_{fr.TIME_SPLIT.is_start[:4]}.parquet"
SEED_CACHE = OUTDIR / f"resident_panel_{fr.TIME_SPLIT.is_start[:4]}.parquet"
MCAP_CACHE = OUTDIR / f"mcap_{fr.TIME_SPLIT.is_start[:4]}.parquet"
MASK_WARMUP_START = "2009-09-01"  # ADV20 needs >=20d before is_start (2010 window)

UNIVERSES = ("univ_all", "univ_csi300", "univ_csi500", "univ_csi1000",
             "univ_microcap", "univ_growth", "univ_liquid_top300")
MASK_FIELDS = {
    "close_raw": "$close", "high": "$high", "low": "$low", "vol": "$vol",
    "up_limit": "$up_limit", "down_limit": "$down_limit",
    "total_mv": "$total_mv", "amount": "$amount",
}


def _build_masks(panel_index: pd.MultiIndex) -> dict[str, pd.Series]:
    """7 universe masks as MultiIndex-aligned bool Series over the IS window.

    Cached to parquet — mask construction needs a raw-field load with ADV warmup.
    """
    inst_level = "instrument" if "instrument" in (panel_index.names or []) else 0
    if MASK_CACHE.exists():
        wide = pd.read_parquet(MASK_CACHE)
        log.info("loaded cached masks %s", MASK_CACHE.name)
        return {u: wide[u] for u in UNIVERSES if u in wide.columns}

    log.info("computing mask fields (with ADV warmup) ...")
    raw, _ = op.compute_factors(catalog=dict(MASK_FIELDS), start_date=MASK_WARMUP_START,
                                end_date=TIME_SPLIT.is_end, horizons=None,
                                qlib_dir=str(PROJECT_ROOT / "data" / "qlib_data"),
                                kernels=1, stage="is_only")
    wides = {}
    for name in MASK_FIELDS:
        s = raw[name]
        w = s.unstack(level=0) if s.index.names[0] in ("instrument", None) else s.unstack(level=1)
        w.index = pd.DatetimeIndex(w.index)
        wides[name] = w.sort_index()
    del raw
    insts = [c for c in wides["close_raw"].columns if not str(c).endswith("_BJ")]
    wides = {k: v[insts] for k, v in wides.items()}
    eval_dates = wides["close_raw"].index
    eval_dates = eval_dates[(eval_dates >= pd.Timestamp(TIME_SPLIT.is_start))
                            & (eval_dates <= pd.Timestamp(TIME_SPLIT.is_end))]

    listing = um.listing_status_masks(eval_dates, insts)
    reference = {"st": um.st_mask(eval_dates, insts),
                 "young": listing["young"], "listed": listing["listed"]}
    panel_for_masks = {k: wides[k] for k in ("vol", "high", "low", "up_limit",
                                             "down_limit", "total_mv", "amount")}
    panel_for_masks["close"] = wides["close_raw"]

    out = {}
    for uid in UNIVERSES:
        t0 = time.time()
        m = uv.build_universe_mask(uid, eval_dates, insts, panel_for_masks,
                                   reference=reference)
        stacked = m.stack()
        stacked.index.names = ["datetime", "instrument"]
        out[uid] = stacked
        log.info("%s: %.0fs, mean breadth %.0f", uid, time.time() - t0,
                 m.sum(axis=1).mean())
    wide_store = pd.DataFrame(out)
    OUTDIR.mkdir(parents=True, exist_ok=True)
    wide_store.to_parquet(MASK_CACHE)
    return out


def _mask_panel(batch_df: pd.DataFrame, names: list, mask: pd.Series) -> pd.DataFrame:
    """NaN-out factor values outside the domain. ADJ/labels stay full-market."""
    aligned = mask.reindex(batch_df.index).fillna(False).astype(bool)
    out = batch_df.copy()
    out.loc[~aligned, names] = np.nan
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-size", type=int, default=12)
    ap.add_argument("--limit", type=int, default=0, help="max factors (smoke)")
    ap.add_argument("--universes", default="", help="comma subset (smoke)")
    args = ap.parse_args()
    OUTDIR.mkdir(parents=True, exist_ok=True)
    universes = [u.strip() for u in args.universes.split(",") if u.strip()] or list(UNIVERSES)

    methods = {u: build_frozen_methodology(is_start=TIME_SPLIT.is_start,
                                           is_end=TIME_SPLIT.is_end, universe_id=u)
               for u in universes}
    mfile = OUTDIR / "methodologies.json"
    saved = json.loads(mfile.read_text(encoding="utf-8")) if mfile.exists() else {}
    for u, m in methods.items():
        if saved.get(u, {}).get("hash") and saved[u]["hash"] != m.methodology_hash:
            from dataclasses import replace
            repinned = replace(m, code_commit=str(saved[u].get("code_commit", "")))
            if repinned.methodology_hash == saved[u]["hash"]:
                log.warning("%s: re-pinning methodology to the run's original commit", u)
                methods[u] = repinned
            else:
                raise RuntimeError(f"methodology drift on resume for {u} — clear {OUTDIR}")
    mfile.write_text(json.dumps(
        {u: {"hash": m.methodology_hash, "code_commit": m.code_commit} for u, m in methods.items()},
        indent=2), encoding="utf-8")
    for u, m in methods.items():
        log.info("%s methodology=%s", u, m.methodology_hash)

    full = get_factor_catalog(include_new_data=True)
    elig = per_factor_field_eligible(list(full), stage="formal_validation")
    base_ok = sorted(n for n, v in elig.items() if v)
    registry = fr._registry_status()
    done = fr._done_factors(RESULTS)
    log.info("eligible %d | done pairs %d", len(base_ok), len(done))

    # shared context pieces (built once, domain-independent). The seed panel is
    # WINDOW-SPECIFIC (the legacy unified_eval_driver_panel covers 2014+ only) —
    # build our own resident panel for the configured TIME_SPLIT window.
    resident_names = sorted(set(STYLE_CONTROLS_V1) | set(methods[universes[0]].reference_set_current))
    if SEED_CACHE.exists():
        seed = pd.read_parquet(SEED_CACHE)
        log.info("loaded resident panel cache %s", SEED_CACHE.name)
    else:
        seed = fr._compute_batch(resident_names, include_adj=True)
        OUTDIR.mkdir(parents=True, exist_ok=True)
        seed.to_parquet(SEED_CACHE)
    missing_res = [n for n in resident_names if n not in seed.columns]
    if missing_res:
        seed = pd.concat([seed, fr._compute_batch(missing_res, include_adj=False)], axis=1)
        seed.to_parquet(SEED_CACHE)
    fr.MCAP_CACHE = MCAP_CACHE  # window-specific mcap for within-domain neutralization
    adj_close = seed[ADJ_COL]
    panel_index = seed.index
    masks = _build_masks(panel_index)
    masks = {u: m for u, m in masks.items() if u in universes}

    decay_labels = build_decay_labels(panel_index, adj_close, is_end=TIME_SPLIT.is_end,
                                      horizons=methods[universes[0]].decay_horizons)
    label = decay_labels[HORIZON]["label"]
    all_dates = sorted(label.index.get_level_values("datetime").unique())
    cut = int(len(all_dates) * methods[universes[0]].orientation_train_frac)
    from src.data_infra import provider_metadata as pm
    base_ctx = {
        "adj_close": adj_close, "label": label, "decay_labels": decay_labels,
        "orient_train": set(all_dates[:cut]), "shape_heldout": set(all_dates[cut:]),
        "rebal_schedule": all_dates[:: methods[universes[0]].rebalance_days],
        "registry": registry,
        "resident_raw": {n: seed[n] for n in resident_names},
        "resident_processed": preprocess_for_residual(
            {n: seed[n] for n in resident_names}, resident_names,
            winsor=methods[universes[0]].winsor_limits),
        "mcap": fr._load_mcap(panel_index.get_level_values("instrument").unique()),
        "benches": fr._bench_fwd(),
    }
    base_ctx["reference_stable"] = list(methods[universes[0]].reference_set_stable)
    base_ctx["approved_current"] = list(methods[universes[0]].reference_set_current)
    log.info("building PIT SW2021 industry labels ...")
    base_ctx["industry"] = pm.build_industry_series_asof(panel_index, level="L1")

    def eval_units(df: pd.DataFrame, names: list):
        """Run `names` through every requested universe (skipping done pairs)."""
        for uid in universes:
            todo = [n for n in names if (n, uid) not in done]
            if not todo:
                continue
            masked = _mask_panel(df, todo, masks[uid])
            aligned = masks[uid].reindex(df.index).fillna(False)
            ctx = {**base_ctx, "method": methods[uid], "results_path": RESULTS,
                   "record_extra": {"universe_id": uid},
                   "domain_total_cells": float(aligned.sum())}
            log.info("evaluating %d factors @ %s", len(todo), uid)
            fr._evaluate_batch(masked, todo, ctx)
            for n in todo:
                done.add((n, uid))

    evaluated = 0
    limit = args.limit or 10**9
    seed_factors = [n for n in seed.columns
                    if n != ADJ_COL and n in full and n in base_ok]
    pending_seed = [n for n in seed_factors
                    if any((n, u) not in done for u in universes)][:limit]
    if pending_seed:
        log.info("batch 0 (seed panel): %d factors", len(pending_seed))
        eval_units(seed, pending_seed)
        evaluated += len(pending_seed)
    del seed

    remaining = [n for n in base_ok
                 if n not in seed_factors and any((n, u) not in done for u in universes)]
    log.info("remaining factors: %d", len(remaining))
    bs = max(1, args.batch_size)
    for i in range(0, len(remaining), bs):
        if evaluated >= limit:
            break
        batch_names = remaining[i: i + bs][: max(0, limit - evaluated)]
        if not batch_names:
            break
        batch_df = fr._compute_batch(batch_names, include_adj=False)
        if not batch_df.index.equals(panel_index):
            batch_df = batch_df.reindex(panel_index)
        eval_units(batch_df, batch_names)
        evaluated += len(batch_names)
        del batch_df

    log.info("MATRIX RUN DONE: %d factor-units this session; results -> %s",
             evaluated, RESULTS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
