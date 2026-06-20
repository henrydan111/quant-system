# SCRIPT_STATUS: ACTIVE — E-wave family-aware marginal selection (Option 1), IS-only, pre-OOS
"""Collapse the 68 E-wave candidates -> a frozen representative set by the canonical
marginal>ICIR rule, IS-only (2010-2020, univ_all). NO 2021+ / NO OOS is touched.

This is the CORRECTED redo of EWaveSelectedSet_v1, which had two verified defects:
  (1) it labeled the raw heldout RankICIR as "style_resid_ic" and selected by it;
  (2) it never computed the factor-factor exposure correlation, so it pruned NO
      within-family redundancy (it saturated every family cap).

Method (Option 1 + style-aware cross-family caps):
  - quality   = |heldout_rank_icir|  (standalone IS strength; the IS-gate metric)
  - redundancy = average month-end cross-sectional Spearman exposure correlation,
                 computed here from the actual factor values over the IS panel
  - greedy: seed = max quality; then repeatedly add argmax of
                 marginal = |icir| * (1 - max|rho| to the already-selected set
                                       UNION the pre-existing redundancy references)
            subject to family caps; stop when marginal < floor or caps exhausted.
  - the style-residual IC (resid_ic_vs_style_controls_v1) is carried as an ANNOTATION
    only (NOT a gate): the families whose controls overlap the style set (vol/liq/mmt)
    collapse against it tautologically; corr/flow are genuinely style-independent.

Outputs (no registry mutation, no OOS):
  workspace/outputs/e_wave_selection_v2/factor_panel_is.parquet   (cached panel)
  workspace/outputs/e_wave_selection_v2/exposure_corr.parquet     (69x69 Spearman)
  workspace/research/cicc_replication/EWaveSelectedSet_v2.json     (the frozen set + trace)
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from src.alpha_research.factor_registry.store import FactorRegistryStore  # noqa: E402
from src.alpha_research.factor_library import get_factor_catalog  # noqa: E402
from src.alpha_research.factor_library import operators as op  # noqa: E402
from src.alpha_research.factor_lifecycle.walk_forward_validation import _expected_direction  # noqa: E402
from workspace.scripts import unified_eval_full_run as fr  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("e_wave_select")

COHORT = "cicc_price_volume_handbook_v1"
REFERENCES = ["rev_up_down_ratio_20d"]  # pre-existing reversal candidate -> redundancy reference (non-selectable)
MATRIX = PROJECT_ROOT / "workspace" / "outputs" / "unified_eval_matrix"
RESULTS = MATRIX / "results.jsonl"
OUT = PROJECT_ROOT / "workspace" / "outputs" / "e_wave_selection_v2"
RES = PROJECT_ROOT / "workspace" / "research" / "cicc_replication"
PANEL_CACHE = OUT / "factor_panel_is.parquet"
CORR_CACHE = OUT / "exposure_corr.parquet"

# style-aware caps (primary) vs v1-equal caps (comparison). vol capped to 1 (most style-spanned:
# the style control set contains risk_vol_20d); corr/flow get 2 (genuinely style-independent);
# liq gets 2 (two genuine sub-families: illiquidity premium + turnover anomaly); mmt 1.
CAPS_STYLE_AWARE = {"corr": 2, "flow": 2, "liq": 2, "vol": 1, "mmt": 1}
CAPS_V1_EQUAL = {"corr": 2, "flow": 2, "liq": 2, "vol": 2, "mmt": 1}
FLOOR = 0.10  # marginal-score floor (redundancy-discounted ICIR must clear the candidate ICIR bar)


def _chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def load_pool():
    st = FactorRegistryStore(PROJECT_ROOT / "data" / "factor_registry")
    cur = st.factor_master[st.factor_master["is_current"].fillna(False)]
    coh = cur[(cur["status"] == "candidate") & (cur["replication_cohort_id"] == COHORT)]
    pool = {r.factor_id: r.family for r in coh.itertuples()}
    if len(pool) != 68:
        log.warning("pool size %d != expected 68", len(pool))
    log.info("pool: %d E-wave candidates by family: %s", len(pool), dict(Counter(pool.values())))
    return pool


def load_inputA(pool):
    """Per-factor IS metrics from the univ_all matrix rows (input A)."""
    want = set(pool) | set(REFERENCES)
    A = {}
    for line in RESULTS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if (r.get("universe_id") or "univ_all") != "univ_all":
            continue
        f = str(r.get("factor", ""))
        if f in want:
            A[f] = r
    missing = want - set(A)
    if missing:
        log.warning("no univ_all matrix row for: %s", sorted(missing))
    return A


def compute_panel(pool):
    if PANEL_CACHE.exists():
        log.info("loading cached factor panel %s", PANEL_CACHE)
        return pd.read_parquet(PANEL_CACHE)
    names = list(pool) + [r for r in REFERENCES if r not in pool]
    cat_all = get_factor_catalog(include_new_data=True)
    names = [n for n in names if n in cat_all]
    log.info("computing %d factor values over IS [%s..%s] (this is the slow step)...",
             len(names), fr.TIME_SPLIT.is_start, fr.TIME_SPLIT.is_end)
    parts = []
    for i, batch in enumerate(_chunks(names, 15), 1):
        t0 = time.time()
        catalog = {n: cat_all[n] for n in batch}
        panel, _ = op.compute_factors(catalog=catalog, start_date=fr.TIME_SPLIT.is_start,
                                      end_date=fr.TIME_SPLIT.is_end, horizons=None,
                                      qlib_dir=str(fr.QLIB_DIR), kernels=1, stage="is_only")
        keep = [c for c in batch if c in panel.columns]
        parts.append(panel[keep])
        log.info("  batch %d/%d (%d cols) in %.0fs", i, (len(names) + 14) // 15, len(keep), time.time() - t0)
    panel = pd.concat(parts, axis=1)
    OUT.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(PANEL_CACHE)
    log.info("panel %s cached -> %s", panel.shape, PANEL_CACHE)
    return panel


def apply_universe_mask(panel):
    mf = MATRIX / "universe_masks_2010.parquet"
    if not mf.exists():
        log.warning("no universe mask file; using full computed panel")
        return panel
    um = pd.read_parquet(mf)
    col = next((c for c in ("univ_all", "all", "ESTU_STYLE_V1") if c in um.columns), None)
    if col is None:
        log.warning("universe mask has no univ_all column (cols=%s); using full panel", list(um.columns)[:8])
        return panel
    mask = um[col].astype(bool)
    # normalize both indices to (instrument, datetime)
    def norm(idx_obj):
        names = list(idx_obj.index.names)
        if names[:2] == ["datetime", "instrument"]:
            return idx_obj.swaplevel(0, 1).sort_index()
        return idx_obj.sort_index()
    panel = norm(panel)
    mask = norm(mask.to_frame("m"))["m"]
    aligned = mask.reindex(panel.index).fillna(False)
    kept = float(aligned.mean())
    log.info("univ_all mask '%s': keeping %.1f%% of panel rows", col, kept * 100)
    return panel.where(aligned, np.nan)


def exposure_corr(panel, names):
    if CORR_CACHE.exists():
        log.info("loading cached exposure corr %s", CORR_CACHE)
        return pd.read_parquet(CORR_CACHE)
    cols = [c for c in names if c in panel.columns]
    panel = panel[cols]
    dates = pd.DatetimeIndex(panel.index.get_level_values("datetime").unique()).sort_values()
    dser = pd.Series(dates, index=dates)
    month_end = list(dser.groupby([dser.index.year, dser.index.month]).max().values)
    log.info("exposure corr: %d month-end cross-sections over %d factors", len(month_end), len(cols))
    mats = []
    for d in month_end:
        cs = panel.xs(d, level="datetime")
        if cs.notna().any(axis=1).sum() < 30:
            continue
        c = cs.corr(method="spearman").reindex(index=cols, columns=cols)
        mats.append(c.values)
    corr = pd.DataFrame(np.nanmean(np.stack(mats), axis=0), index=cols, columns=cols)
    OUT.mkdir(parents=True, exist_ok=True)
    corr.to_parquet(CORR_CACHE)
    log.info("exposure corr cached -> %s (%d valid month-ends)", CORR_CACHE, len(mats))
    return corr


def family_corr_summary(corr, pool):
    fams = sorted(set(pool.values()))
    log.info("=== exposure-correlation structure (mean |rho|) ===")
    for fam in fams:
        members = [f for f in pool if pool[f] == fam and f in corr.index]
        if len(members) < 2:
            log.info("  %-5s within: n=%d (single)", fam, len(members))
            continue
        sub = corr.loc[members, members].abs()
        within = sub.values[np.triu_indices(len(members), 1)]
        log.info("  %-5s within: mean|rho|=%.2f  max=%.2f  (n=%d)", fam, np.nanmean(within), np.nanmax(within), len(members))
    # cross-family (mean abs corr between family medians of members)
    for i, fa in enumerate(fams):
        for fb in fams[i + 1:]:
            ma = [f for f in pool if pool[f] == fa and f in corr.index]
            mb = [f for f in pool if pool[f] == fb and f in corr.index]
            if not ma or not mb:
                continue
            block = corr.loc[ma, mb].abs().values
            log.info("  cross %-5s/%-5s mean|rho|=%.2f max=%.2f", fa, fb, np.nanmean(block), np.nanmax(block))


def greedy(pool, A, corr, caps, floor):
    icir = {f: A[f]["heldout_rank_icir"] for f in pool if f in A}
    sign = {f: A[f]["sign_consistency"] for f in pool if f in A}
    resid = {f: A[f].get("resid_ic_vs_style_controls_v1_signed") for f in A}

    def rho(f, g):
        if f in corr.index and g in corr.columns:
            v = corr.loc[f, g]
            return 0.0 if pd.isna(v) else abs(v)
        return 0.0

    S, fams, trace = [], Counter(), []
    selectable = [f for f in pool if f in icir]
    while True:
        best, best_score, best_info = None, -1.0, None
        for f in selectable:
            if f in [s["factor"] for s in S]:
                continue
            if fams[pool[f]] >= caps.get(pool[f], 99):
                continue
            q = abs(icir[f])
            basis = [s["factor"] for s in S] + REFERENCES
            mc, who = 0.0, None
            for g in basis:
                r = rho(f, g)
                if r > mc:
                    mc, who = r, g
            score = q * (1 - mc)
            if score > best_score:
                best, best_score, best_info = f, score, (q, mc, who)
        if best is None:
            trace.append("STOP: all family caps reached")
            break
        q, mc, who = best_info
        if S and best_score < floor:
            trace.append(f"STOP: next-best {best} marginal={best_score:.3f} < floor {floor} "
                         f"(|icir|={q:.3f}, maxcorr={mc:.2f} vs {who})")
            break
        S.append({"factor": best, "family": pool[best], "heldout_icir": round(icir[best], 3),
                  "sign_consistency": round(sign[best], 2), "marginal_score": round(best_score, 3),
                  "maxcorr_to_set": round(mc, 2), "closest_to": who,
                  "style_resid_ic": (None if resid.get(best) is None else round(resid[best], 3)),
                  "expected_direction": _expected_direction(icir[best])})
        fams[pool[best]] += 1
        trace.append(f"PICK {best:34} fam={pool[best]:5} |icir|={q:.3f} maxcorr={mc:.2f}(vs {who}) marginal={best_score:.3f}")
    return S, trace


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--floor", type=float, default=FLOOR)
    args = ap.parse_args()

    pool = load_pool()
    A = load_inputA(pool)
    panel = compute_panel(pool)
    panel = apply_universe_mask(panel)
    names = list(pool) + [r for r in REFERENCES]
    corr = exposure_corr(panel, names)
    family_corr_summary(corr, pool)

    v1 = {"corr_ret_turnd_20d", "vol_highlow_std_20d", "liq_vstd_20d", "liq_shortcut_avg_20d",
          "corr_price_turn_post_20d", "vol_up_std_20d", "flow_act_buy_shift_dist_xl_20d",
          "mmt_route_20d", "flow_act_buy_prop_l_20d"}

    runs = {}
    for tag, caps in (("style_aware", CAPS_STYLE_AWARE), ("v1_equal", CAPS_V1_EQUAL)):
        for floor in sorted({args.floor, 0.08, 0.12}):
            S, trace = greedy(pool, A, corr, caps, floor)
            key = f"{tag}__floor{floor}"
            runs[key] = {"caps": caps, "floor": floor, "selected": S, "trace": trace}
            log.info("=== %s ===", key)
            for ln in trace:
                log.info("  %s", ln)
            sel = {s["factor"] for s in S}
            log.info("  -> %d reps: %s", len(sel), sorted(sel))
            log.info("  v1-only (dropped): %s", sorted(v1 - sel))
            log.info("  new-vs-v1 (added): %s", sorted(sel - v1))

    primary = runs[f"style_aware__floor{args.floor}"]
    out = {
        "set_id": "EWaveSelectedSet_v2",
        "method": ("Option 1: |heldout_rank_icir| strength x (1 - max month-end Spearman exposure "
                   "corr to selected set + redundancy references); family-capped; marginal floor. "
                   "style_resid_ic is annotation-only (NOT a gate)."),
        "basis_correction_vs_v1": ("v1 selected by raw heldout ICIR mislabeled as style_resid_ic and "
                                   "pruned NO redundancy (saturated every cap). v2 uses the real exposure "
                                   "correlation to prune, and style-aware caps (vol<=1)."),
        "inputs": "univ_all 2010-2020 matrix heldout_rank_icir (input A) + month-end Spearman exposure corr (input B, computed here)",
        "oos_touched": False,
        "pool_size": len(pool),
        "references_used_for_redundancy": REFERENCES,
        "primary": {"tag": "style_aware", "floor": args.floor, "caps": CAPS_STYLE_AWARE,
                    "selected": primary["selected"], "trace": primary["trace"]},
        "all_runs": {k: {"caps": v["caps"], "floor": v["floor"],
                         "selected": [s["factor"] for s in v["selected"]]} for k, v in runs.items()},
    }
    RES.mkdir(parents=True, exist_ok=True)
    (RES / "EWaveSelectedSet_v2.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("wrote %s", RES / "EWaveSelectedSet_v2.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
