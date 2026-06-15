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
import atexit
import json
import logging
import os
import socket
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

RUN_LOCK = OUTDIR / "run.lock"
CACHE_MANIFEST = OUTDIR / "cache_manifest.json"


def _git_commit() -> str:
    import subprocess
    try:
        sha = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                      cwd=PROJECT_ROOT, text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"],
                                             cwd=PROJECT_ROOT, text=True).strip())
        return f"{sha}{'-dirty' if dirty else ''}"
    except Exception:  # noqa: BLE001
        return "unknown"


def _acquire_run_lock(meta: dict, *, force: bool) -> None:
    """GPT pre-flight item 5: a single-writer lock on the matrix OUTDIR (prevents two sessions
    appending to the same results.jsonl / Layer-2 store). A crash leaves a stale lock; the operator
    re-runs with --force after confirming no live writer."""
    if RUN_LOCK.exists() and not force:
        raise SystemExit(
            f"run.lock present at {RUN_LOCK} — another matrix writer may be active. If it is STALE "
            f"(prior crash) and NO matrix process is running, re-run with --force.\n--- lock ---\n"
            f"{RUN_LOCK.read_text(encoding='utf-8')}")
    RUN_LOCK.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def _release_run_lock() -> None:
    try:
        RUN_LOCK.unlink()
    except FileNotFoundError:
        pass


def _cache_digest(path: Path) -> str:
    if not path.exists():
        return ""
    st = path.stat()
    return f"{st.st_size}:{int(st.st_mtime)}"


def _check_cache_manifest(methods: dict, universes: list) -> dict:
    """GPT pre-flight item 10: record (and tripwire on) the inputs the cached seed/mcap/mask panels
    depend on. A time_split or schema change vs a prior manifest means the caches are STALE — fail
    closed (clear OUTDIR). resident-set GROWTH is handled separately by the producer's missing_res
    rebuild, so it is not a tripwire here."""
    cur = {"time_split": [TIME_SPLIT.is_start, TIME_SPLIT.is_end],
           "schema": next(iter(methods.values())).methodology_schema_version,
           "git_commit": _git_commit(),
           "layer1_hashes": {u: methods[u].layer1_methodology_hash for u in universes},
           "cache_digests": {p.name: _cache_digest(p) for p in (SEED_CACHE, MCAP_CACHE, MASK_CACHE)}}
    if CACHE_MANIFEST.exists():
        prev = json.loads(CACHE_MANIFEST.read_text(encoding="utf-8"))
        if prev.get("time_split") != cur["time_split"] or prev.get("schema") != cur["schema"]:
            raise SystemExit(
                f"cache_manifest mismatch — time_split/schema changed since the caches were built "
                f"(prev {prev.get('time_split')}/{prev.get('schema')} vs cur {cur['time_split']}/"
                f"{cur['schema']}). The seed/mcap/mask caches are STALE; clear {OUTDIR} and rebuild.")
    CACHE_MANIFEST.write_text(json.dumps(cur, indent=2), encoding="utf-8")
    return cur


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


def build_base_ctx(universes: list, methods: dict):
    """Build the shared, domain-independent matrix eval context + per-universe masks (resident seed
    panel, R5 stable-basis panel index, decay labels, industry/mcap/benches, the approved book as
    residual controls). Returns ``(base_ctx, masks, seed)``.

    Extracted from :func:`main` so the reference-decoupling migration's sample-recompute
    (workspace/scripts/migrate_evidence_reference_decoupling.py) runs the IDENTICAL context-build
    as a live matrix run. The migration compares a CURRENT-code recompute against the STORED legacy
    evidence values: a match proves the legacy rows are protocol-consistent (the current
    layer1_methodology_hash legitimately applies); a mismatch (protocol/STYLE_CONTROLS/window drift)
    FAILS the byte-equality proof and BLOCKS the migration — fail-closed, never silent corruption.
    """
    from src.data_infra import provider_metadata as pm
    registry = fr._registry_status()
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
    # R5 (GPT decoupling review): anchor the panel index to the STABLE basis (ADJ + STYLE_CONTROLS_V1),
    # NOT the approved book. compute_factors returns a fixed universe×calendar grid regardless of the
    # requested factor set (premise-check 2026-06-15: identical index for style-only vs style+approved,
    # index.equals=True), and test_matrix_reference_invariance LOCKS that the approved book changes no
    # Layer-1 metric. Sourcing the index from style+market (not the union seed) makes the anchoring
    # structural + intent-explicit; the approved factors enter ONLY as residual controls (resident_raw).
    _anchor_cols = [ADJ_COL] + [c for c in STYLE_CONTROLS_V1 if c in seed.columns]
    panel_index = seed[_anchor_cols].index
    masks = _build_masks(panel_index)
    masks = {u: m for u, m in masks.items() if u in universes}

    decay_labels = build_decay_labels(panel_index, adj_close, is_end=TIME_SPLIT.is_end,
                                      horizons=methods[universes[0]].decay_horizons)
    label = decay_labels[HORIZON]["label"]
    all_dates = sorted(label.index.get_level_values("datetime").unique())
    cut = int(len(all_dates) * methods[universes[0]].orientation_train_frac)
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
    return base_ctx, masks, seed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-size", type=int, default=12)
    ap.add_argument("--limit", type=int, default=0, help="max factors (smoke)")
    ap.add_argument("--universes", default="", help="comma subset (smoke)")
    ap.add_argument("--migrate-legacy-methodology-json", action="store_true",
                    help="explicitly authorize re-stamping a LEGACY methodologies.json (only 'hash', "
                         "no 'layer1_hash') under the new schema. Backs up the old file first. Required "
                         "because the legacy run's residuals used the OLD approved book (GPT impl-review V1).")
    ap.add_argument("--force", action="store_true",
                    help="override a STALE run.lock (only after confirming no other matrix writer is running).")
    args = ap.parse_args()
    OUTDIR.mkdir(parents=True, exist_ok=True)

    # Warmup guarantee (GPT 5.5 Pro E1a review): Qlib computes rolling expressions over the FULL
    # store and slices to [is_start, is_end], so a factor's window is full at is_start iff the store
    # has >= window trading days BEFORE is_start. Assert the buffer covers the price-volume cohort's
    # deepest window (270d = mmt_time_rank: Ref1 + Rank250 + Mean20) → no partial-window leak in the
    # IS eval (empirically verified: matrix factors at is_start == a deeper-buffer recompute, 0.0 diff).
    # NOTE: a few legacy catalog factors exceed the buffer (e.g. val_relative_pe 750d) and carry a
    # known minor early-window artifact — pre-existing, tracked separately, not introduced here.
    PV_COHORT_MAX_WARMUP_DAYS = 270
    _cal = pd.to_datetime(pd.read_csv(PROJECT_ROOT / "data" / "qlib_data" / "calendars" / "day.txt",
                                      header=None)[0])
    _buffer = int((_cal < pd.Timestamp(TIME_SPLIT.is_start)).sum())
    if _buffer < PV_COHORT_MAX_WARMUP_DAYS:
        raise RuntimeError(
            f"store has only {_buffer} trading days before is_start={TIME_SPLIT.is_start}; need "
            f">= {PV_COHORT_MAX_WARMUP_DAYS} to fill price-volume rolling windows without a "
            f"partial-window leak. Move is_start later or extend the store history.")
    log.info("warmup buffer: %d trading days before is_start (>= %d PV-cohort max) — rolling windows "
             "full at is_start", _buffer, PV_COHORT_MAX_WARMUP_DAYS)

    universes = [u.strip() for u in args.universes.split(",") if u.strip()] or list(UNIVERSES)

    methods = {u: build_frozen_methodology(is_start=TIME_SPLIT.is_start,
                                           is_end=TIME_SPLIT.is_end, universe_id=u)
               for u in universes}
    mfile = OUTDIR / "methodologies.json"
    saved = json.loads(mfile.read_text(encoding="utf-8")) if mfile.exists() else {}
    # Reference-decoupling (PR-1c): the resume identity is layer1_methodology_hash (reference-EXCLUDED),
    # so approving/revoking a factor never trips drift (the bug being fixed); a protocol / STYLE_CONTROLS
    # change still does (a deliberate re-baseline). A LEGACY methodologies.json (only "hash", no
    # "layer1_hash") is transparently re-stamped on this first run — NOT treated as drift.
    for u, m in methods.items():
        saved_l1 = saved.get(u, {}).get("layer1_hash")
        if saved_l1 and saved_l1 != m.layer1_methodology_hash:
            from dataclasses import replace
            repinned = replace(m, code_commit=str(saved[u].get("code_commit", "")))
            if repinned.layer1_methodology_hash == saved_l1:
                log.warning("%s: re-pinning methodology to the run's original commit", u)
                methods[u] = repinned
            else:
                raise RuntimeError(
                    f"LAYER-1 methodology drift on resume for {u} (protocol/STYLE_CONTROLS change, NOT "
                    f"approval churn) — a deliberate re-baseline; clear {OUTDIR}")
    # V1 (GPT impl-review): a LEGACY methodologies.json (only "hash", no "layer1_hash") must NOT be
    # silently re-stamped — its residuals were computed under the OLD approved book, and overwriting
    # the metadata destroys the audit trail the legacy-residual extraction needs. Require an explicit
    # flag + back up the old file first.
    legacy_universes = [u for u in universes
                        if saved.get(u, {}).get("hash") and not saved.get(u, {}).get("layer1_hash")]
    if legacy_universes:
        if not args.migrate_legacy_methodology_json:
            raise SystemExit(
                f"methodologies.json is LEGACY (no layer1_hash) for {legacy_universes}. Its residuals "
                f"used the OLD approved book. Re-run with --migrate-legacy-methodology-json to back it "
                f"up + re-stamp under schema {next(iter(methods.values())).methodology_schema_version}, "
                f"AND migrate the legacy evidence / Layer-2 residuals separately. Refusing to silently "
                f"rewrite the audit trail.")
        from datetime import datetime, timezone
        bak = OUTDIR / f"methodologies.legacy.{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        bak.write_text(json.dumps(saved, indent=2), encoding="utf-8")
        log.warning("backed up LEGACY methodologies.json -> %s before re-stamping %s under the new schema",
                    bak.name, legacy_universes)
    mfile.write_text(json.dumps(
        {u: {"hash": m.methodology_hash, "layer1_hash": m.layer1_methodology_hash,
             "methodology_schema_version": m.methodology_schema_version,
             "reference_set_stable_hash": m.reference_set_stable_hash,
             "reference_set_current_hash": m.reference_set_current_hash,
             # member lists of the ACTUAL book used (A2): the Layer-2 import populates
             # reference_set_members_json from these, pinned to this run's book (not the
             # current live book). Recording them does NOT affect any hash (hashes derive
             # from the methodology object). reference_set_*_hash above is the integrity key.
             "reference_set_stable": list(m.reference_set_stable),
             "reference_set_current": list(m.reference_set_current),
             "code_commit": m.code_commit} for u, m in methods.items()},
        indent=2), encoding="utf-8")
    for u, m in methods.items():
        log.info("%s layer1=%s (legacy=%s)", u, m.layer1_methodology_hash, m.methodology_hash)

    # GPT pre-flight item 5: single-writer lock on the OUTDIR (no two sessions appending to the same
    # results.jsonl). Held for the whole run; released in the finally below; --force overrides a stale lock.
    _acquire_run_lock({"pid": os.getpid(), "hostname": socket.gethostname(),
                       "git_commit": _git_commit(), "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                       "schema": next(iter(methods.values())).methodology_schema_version,
                       "layer1_hashes": {u: methods[u].layer1_methodology_hash for u in universes}},
                      force=args.force)
    atexit.register(_release_run_lock)   # release on normal exit OR unhandled exception

    full = get_factor_catalog(include_new_data=True)
    elig = per_factor_field_eligible(list(full), stage="formal_validation")
    base_ok = sorted(n for n, v in elig.items() if v)
    # GPT pre-flight: sanitize a partial/corrupt JSONL tail BEFORE any append, and count a (factor,
    # universe) pair as DONE only if its row is a success record under the CURRENT methodology
    # (schema + this universe's layer1 hash) — error / stale-hash / partial rows must recompute.
    _san = fr._sanitize_results_tail(RESULTS)
    if _san["dropped"] or _san["backup"]:
        log.warning("sanitized results.jsonl tail: kept=%d dropped=%d backup=%s",
                    _san["kept"], _san["dropped"], _san["backup"])
    _schema = next(iter(methods.values())).methodology_schema_version
    _l1_by_u = {u: m.layer1_methodology_hash for u, m in methods.items()}
    done = fr._done_factors(RESULTS, validator=lambda r: fr._is_success_record(
        r, expected_schema=_schema, expected_layer1_by_universe=_l1_by_u))
    log.info("eligible %d | done pairs %d (methodology-validated)", len(base_ok), len(done))

    base_ctx, masks, seed = build_base_ctx(universes, methods)
    _check_cache_manifest(methods, universes)   # GPT pre-flight item 10: tripwire on stale caches

    def eval_units(df: pd.DataFrame, names: list):
        """Run `names` through every requested universe (skipping done pairs)."""
        for uid in universes:
            todo = [n for n in names if (n, uid) not in done]
            if not todo:
                continue
            masked = _mask_panel(df, todo, masks[uid])
            aligned = masks[uid].reindex(df.index).fillna(False)
            # residual-control-scope fix: raw metrics use the MASKED panel (universe IC/WF/quantile);
            # residuals use the UNMASKED panel (broad-ESTU winsor/z-score) + eval_mask (mask AFTER the
            # transform). See RESIDUAL_CONTROL_SCOPE_FIX_plan.md.
            ctx = {**base_ctx, "method": methods[uid], "results_path": RESULTS,
                   "record_extra": {"universe_id": uid},
                   "domain_total_cells": float(aligned.sum()),
                   "residual_panel": df, "eval_mask": masks[uid]}
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
        panel_index = base_ctx["adj_close"].index   # == seed anchor index (post-extraction)
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
