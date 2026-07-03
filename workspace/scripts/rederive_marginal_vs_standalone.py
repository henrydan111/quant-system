# SCRIPT_STATUS: ACTIVE — v1.4 B3 residual: re-derive the greedy-by-marginal vs
# greedy-by-standalone-ICIR comparison so the historical figures (combined ICIR 1.02 vs
# 0.70, memory `reference_factor_selection_marginal_not_icir`, statement of record
# unified_eval_standard.md ~L404-406) may be quoted again. Until a full run of THIS
# script reproduces them, those numbers remain unverified-at-source (amendment §1.3).
"""Greedy factor-selection comparison: marginal-orthogonal vs standalone-ICIR.

IS-ONLY by construction (default 2014-01-01..2020-12-31, the standard IS window): no OOS
window is read, no seal is touched. Factors compute through the sanctioned
`compute_factors` door (stage='sandbox_screening'); the h-day forward-return LABEL is
built from the same panel's adjusted close by per-instrument shift(-h) (the label may
look forward — it is the target, not a feature).

Method (mirrors the original experiment):
  1. pool = current `candidate` factors (capped at --max-pool by |standalone ICIR|).
  2. daily cross-sectional rank-IC per factor vs the h-day forward return.
  3. greedy A (standalone): pick top-K by |ICIR|, sign-aligned.
  4. greedy B (marginal): grow the set by the candidate that maximizes the COMBINED
     rank-signal ICIR (mean of sign-aligned cs-ranks) — redundancy pays its true price.
  5. report combined ICIR of both K-sets + the selections.

Usage:
  venv/Scripts/python.exe workspace/scripts/rederive_marginal_vs_standalone.py \
      [--start 2014-01-01] [--end 2020-12-31] [--horizon 20] [--k 4] [--max-pool 40]
      [--factors a,b,c]   # explicit pool override (smoke tests)
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("rederive_marginal")

OUT_DIR = ROOT / "workspace" / "outputs" / "rederive_marginal_vs_standalone"


def _daily_rank_ic(factor: pd.Series, label: pd.Series) -> pd.Series:
    """Per-date cross-sectional Spearman IC (factor and label share a
    (instrument, datetime) MultiIndex)."""
    frame = pd.DataFrame({"f": factor, "y": label}).dropna()
    if frame.empty:
        return pd.Series(dtype=float)
    dates = frame.index.get_level_values("datetime")
    return frame.groupby(dates).apply(
        lambda g: g["f"].rank().corr(g["y"].rank()) if len(g) >= 30 else np.nan
    ).dropna()


def _icir(ic: pd.Series) -> float:
    return float(ic.mean() / ic.std()) if len(ic) > 1 and ic.std() > 0 else 0.0


def _combined_icir(panel: pd.DataFrame, members: list[str], signs: dict[str, float],
                   label: pd.Series) -> float:
    """ICIR of the equal-weight mean of sign-aligned per-date cs-ranks."""
    dates = panel.index.get_level_values("datetime")
    ranks = [
        signs[m] * panel[m].groupby(dates).rank(pct=True)
        for m in members
    ]
    combined = pd.concat(ranks, axis=1).mean(axis=1)
    return _icir(_daily_rank_ic(combined, label))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2014-01-01")
    ap.add_argument("--end", default="2020-12-31")
    ap.add_argument("--horizon", type=int, default=20)
    ap.add_argument("--k", type=int, default=4)
    ap.add_argument("--max-pool", type=int, default=40)
    ap.add_argument("--factors", default="", help="comma-separated explicit pool (smoke)")
    args = ap.parse_args()

    from src.alpha_research.factor_library.catalog import get_factor_catalog
    from src.alpha_research.factor_library.operators import compute_factors

    catalog = get_factor_catalog()
    if args.factors:
        pool_ids = [f.strip() for f in args.factors.split(",") if f.strip()]
        missing = [f for f in pool_ids if f not in catalog]
        if missing:
            raise SystemExit(f"not in catalog: {missing}")
    else:
        from src.alpha_research.factor_registry import FactorRegistryStore

        store = FactorRegistryStore(ROOT / "data" / "factor_registry")
        master = store.factor_master
        current = master[master["is_current"].fillna(False)]
        pool_ids = [
            f for f in current[current["status"] == "candidate"]["factor_id"].tolist()
            if f in catalog
        ]
        log.info("candidate pool from registry: %d factors", len(pool_ids))

    exprs = {f: catalog[f] for f in pool_ids}
    exprs["_close_adj"] = "$close * $adj_factor"  # label basis (adjusted close)
    log.info("computing %d factors + label basis %s..%s (sandbox stage)",
             len(pool_ids), args.start, args.end)
    panel = compute_factors(exprs, args.start, args.end, stage="sandbox_screening")

    # h-day forward return per instrument (the label; target may look forward).
    close = panel["_close_adj"]
    inst = panel.index.get_level_values("instrument")
    fwd = close.groupby(inst).shift(-args.horizon) / close - 1.0
    panel = panel.drop(columns=["_close_adj"])

    # Standalone ICIR per pool factor; cap the pool.
    stats = {}
    for f in panel.columns:
        ic = _daily_rank_ic(panel[f], fwd)
        stats[f] = {"icir": _icir(ic), "n_days": int(len(ic))}
    ranked = sorted(stats, key=lambda f: -abs(stats[f]["icir"]))[: args.max_pool]
    signs = {f: (1.0 if stats[f]["icir"] >= 0 else -1.0) for f in ranked}
    log.info("pool capped to %d by |ICIR| (top: %s)", len(ranked), ranked[:5])

    # Greedy A — standalone: top-K by |ICIR|.
    greedy_standalone = ranked[: args.k]
    icir_standalone = _combined_icir(panel, greedy_standalone, signs, fwd)

    # Greedy B — marginal: grow by best combined-ICIR improvement.
    greedy_marginal: list[str] = []
    for _ in range(args.k):
        best, best_icir = None, -np.inf
        for cand in ranked:
            if cand in greedy_marginal:
                continue
            trial = _combined_icir(panel, greedy_marginal + [cand], signs, fwd)
            if trial > best_icir:
                best, best_icir = cand, trial
        greedy_marginal.append(best)
        log.info("marginal pick %d: %s (combined ICIR %.3f)", len(greedy_marginal), best, best_icir)
    icir_marginal = _combined_icir(panel, greedy_marginal, signs, fwd)

    result = {
        "window": f"{args.start}..{args.end}", "horizon": args.horizon, "k": args.k,
        "pool_size": len(ranked),
        "greedy_by_standalone": {"members": greedy_standalone, "combined_icir": icir_standalone},
        "greedy_by_marginal": {"members": greedy_marginal, "combined_icir": icir_marginal},
        "per_factor_standalone_icir": {f: stats[f]["icir"] for f in ranked},
        "note": "IS-only CURRENT-POOL re-derivation (v1.4 amendment §1.3 B3 residual); no OOS "
                "touched. NOT a bit-for-bit reconstruction of the historical experiment — the "
                "candidate pool has grown since; label any quoted figure accordingly.",
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "result.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("combined ICIR — greedy-by-marginal %.3f vs greedy-by-standalone %.3f -> %s",
             icir_marginal, icir_standalone, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
