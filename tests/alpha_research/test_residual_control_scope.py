"""Residual control-scope tests (GPT 5.5 Pro ruling 2026-06-15).

Locks the canonical residual pipeline: winsorize+z-score candidate AND controls on a FIXED broad
estimation universe, THEN mask to the evaluation universe before the per-date OLS residual + IC.
These guard against the batch-order-dependent control-scope bug (resident factors got universe-masked
controls in batch-0; non-resident factors got full-market controls) and pin the hashed scope knob.
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.alpha_research.factor_eval.unified_eval import (
    EvalMethodology, STYLE_CONTROLS_V1, preprocess_for_residual, residual_ic_vs_controls,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _panel(n_inst=60, n_dates=240, seed=7, heavy_tail=False):
    rng = np.random.default_rng(seed)
    insts = [f"T{i:04d}" for i in range(n_inst)]
    dates = pd.bdate_range("2015-01-01", periods=n_dates)
    idx = pd.MultiIndex.from_product([insts, dates], names=["instrument", "datetime"]).sort_values()
    n = len(idx)

    def col(ht=False):
        v = rng.standard_normal(n)
        if ht:  # inject fat tails / outliers so winsorization scope BITES
            v = v + rng.standard_t(2, n) * 3.0
        return pd.Series(v, index=idx)

    cand = col(heavy_tail)
    controls = {c: col(heavy_tail) for c in ["c_a", "c_b", "c_c"]}
    fwd = pd.Series(rng.standard_normal(n) * 0.02, index=idx)
    # universe = a SUBSET of instruments (the "thin" evaluation domain)
    uni_insts = set(insts[: n_inst // 3])
    mask = pd.Series([ix[0] in uni_insts for ix in idx], index=idx)
    return cand, controls, fwd, mask, idx


# ── Test 2: scope contract — broad-then-mask differs from universe-local on heavy tails ──────────
def test_residual_scope_contract_broad_then_mask_differs_from_local():
    cand, controls, fwd, mask, idx = _panel(heavy_tail=True)
    factors = {"cand": cand, **controls}
    ctrl_names = list(controls)

    # CANONICAL (the fix): winsorize/z-score on the FULL panel, then mask to the universe.
    proc_full = preprocess_for_residual(factors, ["cand", *ctrl_names], winsor=(0.01, 0.99))
    r_broad = residual_ic_vs_controls("cand", factors, fwd, control_names=ctrl_names,
                                      processed_controls=proc_full, eval_mask=mask, min_obs=5)

    # universe-LOCAL (the rejected alternative): winsorize/z-score within the universe only.
    masked_factors = {k: v.where(mask) for k, v in factors.items()}
    proc_local = preprocess_for_residual(masked_factors, ["cand", *ctrl_names], winsor=(0.01, 0.99))
    r_local = residual_ic_vs_controls("cand", masked_factors, fwd.where(mask), control_names=ctrl_names,
                                      processed_controls=proc_local, eval_mask=None, min_obs=5)

    # both evaluate over the SAME universe rows, but the winsorization scope differs (non-affine on
    # heavy tails) -> the residual IC must differ. (If this ever becomes equal, the scope fix is moot.)
    assert r_broad["residual_mean_rank_ic"] is not None and r_local["residual_mean_rank_ic"] is not None
    assert abs(r_broad["residual_mean_rank_ic"] - r_local["residual_mean_rank_ic"]) > 1e-6, (
        "broad-then-mask must differ from universe-local transform on a heavy-tailed panel")


# ── Test 5: universe guard — broad proc IN, regression restricted to the universe ────────────────
def test_residual_eval_mask_restricts_to_universe():
    cand, controls, fwd, mask, idx = _panel(heavy_tail=False)
    factors = {"cand": cand, **controls}
    ctrl_names = list(controls)
    proc_full = preprocess_for_residual(factors, ["cand", *ctrl_names], winsor=(0.01, 0.99))
    # precondition: the processed inputs are BROAD (full-panel, NOT pre-masked) — the function does the
    # masking. Non-null count must far exceed the universe cell count.
    uni_cells = int(mask.sum())
    assert proc_full["cand"].notna().sum() > 1.5 * uni_cells, "proc must be broad (full panel), not pre-masked"

    r_uni = residual_ic_vs_controls("cand", factors, fwd, control_names=ctrl_names,
                                    processed_controls=proc_full, eval_mask=mask, min_obs=5)
    r_full = residual_ic_vs_controls("cand", factors, fwd, control_names=ctrl_names,
                                     processed_controls=proc_full, eval_mask=None, min_obs=5)
    assert r_uni["n_dates"] > 0 and 0.0 <= r_uni["effective_residual_coverage"] <= 1.0
    # eval_mask genuinely restricts: the universe residual must differ from the full-panel residual,
    # and the universe regression sees strictly fewer names (coverage proxy via residual IC differing).
    assert r_uni["residual_mean_rank_ic"] != r_full["residual_mean_rank_ic"], (
        "eval_mask must restrict the regression to the universe (≠ full-panel residual)")


# ── Test 4: residual_preprocess_scope is a hashed knob (both legacy + layer1 hashes) ─────────────
def test_residual_preprocess_scope_changes_methodology_hash():
    m1 = EvalMethodology(is_start="2015-01-01", is_end="2020-12-31")
    m2 = replace(m1, residual_preprocess_scope="ESTU_OTHER_V2")
    assert m1.residual_preprocess_scope == "ESTU_STYLE_V1"
    assert m1.methodology_hash != m2.methodology_hash, "scope must change the legacy methodology hash"
    assert m1.layer1_methodology_hash != m2.layer1_methodology_hash, "scope must change the layer1 hash"
    # and it must NOT depend on the approved book (it is a reference-invariant Layer-1 knob)
    m3 = replace(m1, reference_set_current=("ap1", "ap2", "ap3"))
    assert m1.layer1_methodology_hash == m3.layer1_methodology_hash


# ── Tests 1 + 3: batch-order invariance + IC blast-radius (calendar-gated, via _evaluate_batch) ──
@pytest.mark.skipif(
    not (PROJECT_ROOT / "data" / "qlib_data" / "calendars" / "day.txt").exists(),
    reason="needs the qlib trading calendar (data/ not present in this checkout)")
def test_evaluate_batch_residual_is_batch_order_invariant(tmp_path):
    from workspace.scripts import unified_eval_full_run as fr
    from src.alpha_research.factor_eval.unified_eval import build_decay_labels, preprocess_for_residual

    cal = pd.to_datetime(pd.read_csv(
        PROJECT_ROOT / "data" / "qlib_data" / "calendars" / "day.txt", header=None)[0])
    dates = list(cal[(cal >= "2012-01-01") & (cal <= "2019-12-31")])
    rng = np.random.default_rng(5)
    insts = [f"T{i:04d}" for i in range(80)]
    idx = pd.MultiIndex.from_product([insts, dates], names=["instrument", "datetime"]).sort_values()
    n = len(idx)
    rand = lambda: pd.Series(rng.standard_normal(n), index=idx)  # noqa: E731
    rets = rng.standard_normal((len(insts), len(dates))) * 0.02
    adj = pd.Series((100 * np.cumprod(1 + rets, axis=1)).reshape(-1),
                    index=pd.MultiIndex.from_product([insts, dates],
                                                     names=["instrument", "datetime"])).sort_index()
    ctrls = {c: rand() for c in STYLE_CONTROLS_V1}
    factors = {"cand": rand(), "other1": rand(), "other2": rand(), **ctrls}
    full_df = pd.DataFrame(factors)

    method = EvalMethodology(is_start=fr.TIME_SPLIT.is_start, is_end=fr.TIME_SPLIT.is_end,
                             reference_set_stable=(), reference_set_current=(), bootstrap_n_boot=64)
    decay = build_decay_labels(adj.index, adj, is_end=fr.TIME_SPLIT.is_end, horizons=method.decay_horizons)
    label = decay[fr.HORIZON]["label"]
    all_dates = sorted(label.index.get_level_values("datetime").unique())
    cut = int(len(all_dates) * method.orientation_train_frac)
    bdates = pd.DatetimeIndex(all_dates)
    resident_raw = {c: ctrls[c] for c in STYLE_CONTROLS_V1}
    base_ctx = {
        "method": method, "adj_close": adj, "label": label, "decay_labels": decay,
        "orient_train": set(all_dates[:cut]), "shape_heldout": set(all_dates[cut:]),
        "rebal_schedule": all_dates[:: method.rebalance_days], "registry": {},
        "resident_raw": resident_raw,
        "resident_processed": preprocess_for_residual(resident_raw, list(STYLE_CONTROLS_V1),
                                                      winsor=method.winsor_limits),
        "mcap": pd.Series(np.abs(rng.standard_normal(n)) + 1, index=idx),
        "industry": pd.Series(rng.integers(0, 10, n), index=idx),
        "benches": {"CSI300": pd.Series(rng.standard_normal(len(bdates)) * 0.01, index=bdates)},
        "reference_stable": [], "approved_current": [],
    }
    # a thin evaluation universe (subset of instruments)
    uni = set(insts[:30])
    mask = pd.Series([ix[0] in uni for ix in idx], index=idx)

    def run(names, tag):
        rp = tmp_path / f"r_{tag}.jsonl"
        if rp.exists():
            rp.unlink()
        masked = full_df.copy()
        masked.loc[~mask.values, names] = np.nan
        ctx = {**base_ctx, "results_path": rp, "record_extra": {"universe_id": "thin"},
               "domain_total_cells": float(mask.sum()), "residual_panel": full_df, "eval_mask": mask}
        fr._evaluate_batch(masked, names, ctx)
        rows = {json.loads(l)["factor"]: json.loads(l)
                for l in rp.read_text(encoding="utf-8").splitlines() if l.strip()}
        return rows["cand"]

    solo = run(["cand"], "solo")                       # evaluated alone
    batch = run(["other1", "cand", "other2"], "batch")  # evaluated mid-batch with neighbors

    assert "error" not in solo and "error" not in batch
    # IC / ICIR are universe-scoped and batch-independent
    for k in ("mean_rank_ic", "heldout_rank_icir"):
        assert solo.get(k) == batch.get(k), f"{k} must be batch-order invariant"
    # the residual columns must NOW be batch-order invariant (the bug made them depend on batch membership)
    for k in ("resid_ic_vs_style_controls_v1_signed", "resid_hac_t_vs_style_controls_v1",
              "resid_ic_vs_style_controls_v1_oriented"):
        assert solo.get(k) == batch.get(k), f"{k} must be batch-order invariant after the scope fix"
