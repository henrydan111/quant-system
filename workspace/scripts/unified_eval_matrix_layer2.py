# ──────────────────────────────────────────────────────────────────────
# script_status: research_tooling
# formal_research_allowed: false
# deployment_target: unified_eval_evidence_only
# notes: |
#   F2 supplement — Layer-2 composites (20) + industry-relative (4) × 7 universes,
#   completing the 208-factor catalog matrix. Components recomputed once full-market
#   (Layer-1), composites assembled via the canonical add_composites /
#   add_industry_relative_composites, then NaN-masked per universe and pushed
#   through the same parameterized _evaluate_batch as the base matrix.
#   §3.9 composite rule: effective window = INTERSECTION of components — enforced
#   here by building composites from FULL component panels (a composite value
#   exists only where every component does because the canonical builders require
#   complete component rows), and the engine's effective_* fields record it.
# ──────────────────────────────────────────────────────────────────────
"""F2 Layer-2 supplement: composites + industry-relative × all 7 universes."""
from __future__ import annotations

import argparse
import json
import logging
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

from src.alpha_research.factor_library import (  # noqa: E402
    add_composites, add_industry_relative_composites, get_composite_defs,
)
from src.alpha_research.factor_library.catalog import get_industry_relative_defs  # noqa: E402
from src.alpha_research.factor_eval.unified_eval import (  # noqa: E402
    STYLE_CONTROLS_V1, build_decay_labels, preprocess_for_residual,
)
from workspace.scripts.unified_eval_common import build_frozen_methodology  # noqa: E402
from workspace.scripts import unified_eval_full_run as fr  # noqa: E402
from workspace.scripts import unified_eval_universe_matrix as mx  # noqa: E402

log = logging.getLogger("unified_eval_matrix_l2")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

TIME_SPLIT = fr.TIME_SPLIT
HORIZON = fr.HORIZON
ADJ_COL = fr.ADJ_COL
OUTDIR = mx.OUTDIR
RESULTS = mx.RESULTS
COMP_CACHE = OUTDIR / f"layer2_components_{TIME_SPLIT.is_start[:4]}.parquet"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    universes = list(mx.UNIVERSES)
    methods = {u: build_frozen_methodology(is_start=TIME_SPLIT.is_start,
                                           is_end=TIME_SPLIT.is_end, universe_id=u)
               for u in universes}
    # methodology consistency with the base matrix run
    mfile = OUTDIR / "methodologies.json"
    saved = json.loads(mfile.read_text(encoding="utf-8"))
    for u, m in methods.items():
        if saved.get(u, {}).get("hash") != m.methodology_hash:
            from dataclasses import replace
            repinned = replace(m, code_commit=str(saved[u].get("code_commit", "")))
            if repinned.methodology_hash == saved[u]["hash"]:
                methods[u] = repinned
            else:
                raise RuntimeError(f"methodology drift vs base matrix for {u}")

    comp_defs = get_composite_defs()
    ind_defs = get_industry_relative_defs()
    layer2_names = [c["name"] for c in comp_defs] + [d["name"] for d in ind_defs]
    done = fr._done_factors(RESULTS)
    todo_any = [n for n in layer2_names if any((n, u) not in done for u in universes)]
    log.info("layer-2 factors: %d total, %d with pending domains", len(layer2_names), len(todo_any))
    if not todo_any:
        log.info("nothing to do")
        return 0

    # ---- components (full-market Layer-1, cached)
    comp_needed = set()
    for c in comp_defs:
        comp_needed.update(c["components"])
    for d in ind_defs:
        if d.get("base"):
            comp_needed.add(d["base"])
    comp_needed = sorted(comp_needed)
    if COMP_CACHE.exists():
        comp_df = pd.read_parquet(COMP_CACHE)
        log.info("loaded component cache %s (%d cols)", COMP_CACHE.name, len(comp_df.columns))
    else:
        comp_df = fr._compute_batch(comp_needed + [ADJ_COL[2:-2]] if False else comp_needed,
                                    include_adj=True)
        comp_df.to_parquet(COMP_CACHE)
    missing = [n for n in comp_needed if n not in comp_df.columns]
    if missing:
        extra = fr._compute_batch(missing, include_adj=False)
        comp_df = pd.concat([comp_df, extra.reindex(comp_df.index)], axis=1)
        comp_df.to_parquet(COMP_CACHE)

    adj_close = comp_df[ADJ_COL]
    panel_index = comp_df.index
    masks = mx._build_masks(panel_index)

    # ---- shared ctx (mirrors the base matrix)
    from src.data_infra import provider_metadata as pm
    fr.MCAP_CACHE = mx.MCAP_CACHE
    resident_names = sorted(set(STYLE_CONTROLS_V1) | set(methods[universes[0]].reference_set_current))
    seed = pd.read_parquet(mx.SEED_CACHE)
    decay_labels = build_decay_labels(panel_index, adj_close, is_end=TIME_SPLIT.is_end,
                                      horizons=methods[universes[0]].decay_horizons)
    label = decay_labels[HORIZON]["label"]
    all_dates = sorted(label.index.get_level_values("datetime").unique())
    cut = int(len(all_dates) * methods[universes[0]].orientation_train_frac)
    base_ctx = {
        "adj_close": adj_close, "label": label, "decay_labels": decay_labels,
        "orient_train": set(all_dates[:cut]), "shape_heldout": set(all_dates[cut:]),
        "rebal_schedule": all_dates[:: methods[universes[0]].rebalance_days],
        "registry": fr._registry_status(),
        "resident_raw": {n: seed[n] for n in resident_names if n in seed.columns},
        "resident_processed": preprocess_for_residual(
            {n: seed[n] for n in resident_names if n in seed.columns},
            [n for n in resident_names if n in seed.columns],
            winsor=methods[universes[0]].winsor_limits),
        "mcap": fr._load_mcap(panel_index.get_level_values("instrument").unique()),
        "benches": fr._bench_fwd(),
        "reference_stable": list(methods[universes[0]].reference_set_stable),
        "approved_current": list(methods[universes[0]].reference_set_current),
    }
    log.info("building PIT SW2021 industry labels ...")
    base_ctx["industry"] = pm.build_industry_series_asof(panel_index, level="L1")

    # ---- assemble composites on the FULL market (Layer-1.5: estimation universe),
    # then mask per evaluation universe (§3.7: identity transforms full-market once)
    log.info("building %d composites + %d industry-relative ...", len(comp_defs), len(ind_defs))
    l2 = add_composites(comp_df, comp_defs)
    l2 = add_industry_relative_composites(l2, base_ctx["industry"], base_ctx["mcap"], defs=ind_defs)
    l2_df = l2[[n for n in layer2_names if n in l2.columns]].copy()
    l2_df[ADJ_COL] = adj_close
    del l2, comp_df

    evaluated = 0
    limit = args.limit or 10**9
    for uid in universes:
        todo = [n for n in layer2_names if (n, uid) not in done and n in l2_df.columns][:limit]
        if not todo:
            continue
        masked = mx._mask_panel(l2_df, todo, masks[uid])
        aligned = masks[uid].reindex(l2_df.index).fillna(False)
        ctx = {**base_ctx, "method": methods[uid], "results_path": RESULTS,
               "record_extra": {"universe_id": uid},
               "domain_total_cells": float(aligned.sum())}
        log.info("layer-2: %d factors @ %s", len(todo), uid)
        fr._evaluate_batch(masked, todo, ctx)
        evaluated += len(todo)

    log.info("LAYER-2 MATRIX DONE: %d units; results -> %s", evaluated, RESULTS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
