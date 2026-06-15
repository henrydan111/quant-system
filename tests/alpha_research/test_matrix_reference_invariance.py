"""R4 regression test — matrix Layer-1 reference-invariance (GPT 5.5 Pro decoupling review, round-2).

The approved-factor BOOK must NOT change ANY Layer-1 column produced by the unified-eval matrix.
In `unified_eval_full_run._evaluate_batch` the book is read ONLY at the two lines

    stable  = [b for b in ctx["reference_stable"] if b != fid]
    current = [b for b in ctx["approved_current"] if b != fid]

and feeds ONLY the `r_st`/`r_cu` residuals → ONLY the `resid_ic_vs_approved_*` columns. Every other
column (walk-forward IC/ICIR, quantile profile, decay, turnover, coverage, neutralized IC, the
STYLE_CONTROLS_V1 residual, long-leg) is reference-INVARIANT.

This test runs `_evaluate_batch` TWICE on IDENTICAL synthetic panels, changing ONLY the approved
book, and asserts every emitted column is byte-identical except the `resid_ic_vs_approved_*` family.
It is the implementation GATE for the reference-decoupling (PR-1): it must be GREEN on current code
before any methodology-hash / namespace change lands, and must stay green after. The synthetic data
need not be "correct" market data — the metrics only need to be CONSTANT across the two book runs.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from workspace.scripts import unified_eval_full_run as fr
from src.alpha_research.factor_eval.unified_eval import (
    EvalMethodology,
    STYLE_CONTROLS_V1,
    build_decay_labels,
    preprocess_for_residual,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# The ONLY columns allowed to differ when the approved book changes (+ the timing field).
BOOK_DEPENDENT = {
    "resid_ic_vs_approved_stable_signed",
    "resid_ic_vs_approved_stable_oriented",
    "resid_hac_t_vs_approved_stable",
    "resid_eff_coverage_vs_approved_stable",
    "resid_ic_vs_approved_current_signed",
    # PR-1b: the reference-set hashes IDENTIFY the book used for the residuals above — they are
    # book-dependent BY DESIGN (their whole purpose is to record which book a residual used).
    "reference_set_stable_hash",
    "reference_set_current_hash",
}
ALLOWED_DIFF = BOOK_DEPENDENT | {"eval_seconds"}


def _trading_days(start: str, end: str) -> list:
    cal = pd.read_csv(PROJECT_ROOT / "data" / "qlib_data" / "calendars" / "day.txt", header=None)[0]
    d = pd.to_datetime(cal)
    return list(d[(d >= pd.Timestamp(start)) & (d <= pd.Timestamp(end))])


def _run_once(base_ctx: dict, batch_df: pd.DataFrame, book: dict, tmp_path: Path, tag: str) -> dict:
    rp = tmp_path / f"r_{tag}.jsonl"
    if rp.exists():
        rp.unlink()
    ctx = {**base_ctx, **book, "results_path": rp}
    fr._evaluate_batch(batch_df, ["cand"], ctx)
    rows = [json.loads(line) for line in rp.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1, f"expected 1 record, got {len(rows)}"
    return rows[0]


@pytest.mark.skipif(
    not (PROJECT_ROOT / "data" / "qlib_data" / "calendars" / "day.txt").exists(),
    reason="needs the qlib trading calendar (data/ not present in this checkout)",
)
def test_layer1_metrics_are_reference_invariant(tmp_path):
    rng = np.random.default_rng(11)
    dates = _trading_days("2010-01-01", "2020-12-31")
    insts = [f"T{i:04d}" for i in range(60)]
    idx = pd.MultiIndex.from_product([insts, dates], names=["instrument", "datetime"]).sort_values()
    n = len(idx)

    def rand(positive: bool = False) -> pd.Series:
        v = rng.standard_normal(n)
        return pd.Series(np.abs(v) + 1.0 if positive else v, index=idx)

    # adjusted close: a positive random walk per instrument (for label realization)
    rets = rng.standard_normal((len(insts), len(dates))) * 0.02
    px = (100.0 * np.cumprod(1.0 + rets, axis=1)).reshape(-1)
    adj = pd.Series(px, index=pd.MultiIndex.from_product(
        [insts, dates], names=["instrument", "datetime"])).sort_index()

    book_pool = [f"ap{i}" for i in range(1, 7)]
    ctrl_names = list(STYLE_CONTROLS_V1) + book_pool
    resident_raw = {nm: rand() for nm in ctrl_names}
    resident_processed = preprocess_for_residual(resident_raw, ctrl_names, winsor=(0.01, 0.99))
    batch_df = pd.DataFrame({"cand": rand()})

    method = EvalMethodology(
        is_start=fr.TIME_SPLIT.is_start, is_end=fr.TIME_SPLIT.is_end,
        reference_set_stable=("ap1", "ap2"), reference_set_current=("ap1", "ap2", "ap3"),
        bootstrap_n_boot=100,  # held constant across both runs; smaller only for test speed
    )
    decay_labels = build_decay_labels(adj.index, adj, is_end=fr.TIME_SPLIT.is_end,
                                      horizons=method.decay_horizons)
    label = decay_labels[fr.HORIZON]["label"]
    all_dates = sorted(label.index.get_level_values("datetime").unique())
    cut = int(len(all_dates) * method.orientation_train_frac)
    bdates = pd.DatetimeIndex(all_dates)

    base_ctx = {
        "method": method, "adj_close": adj, "label": label, "decay_labels": decay_labels,
        "orient_train": set(all_dates[:cut]), "shape_heldout": set(all_dates[cut:]),
        "rebal_schedule": all_dates[:: method.rebalance_days], "registry": {},
        "resident_raw": resident_raw, "resident_processed": resident_processed,
        "mcap": rand(positive=True),
        "industry": pd.Series(rng.integers(0, 10, n), index=idx),
        "benches": {"CSI300": pd.Series(rng.standard_normal(len(bdates)) * 0.01, index=bdates),
                    "CSI500": pd.Series(rng.standard_normal(len(bdates)) * 0.01, index=bdates)},
        "record_extra": {}, "domain_total_cells": float(n),
    }

    book_a = {"reference_stable": ["ap1", "ap2"], "approved_current": ["ap1", "ap2", "ap3"]}
    book_b = {"reference_stable": ["ap3", "ap4", "ap5"], "approved_current": ["ap3", "ap4", "ap5", "ap6"]}

    rec_a = _run_once(base_ctx, batch_df, book_a, tmp_path, "A")
    rec_b = _run_once(base_ctx, batch_df, book_b, tmp_path, "B")

    # both runs must produce a FULL record (not the error fallback) — else the test proves nothing
    assert "error" not in rec_a, rec_a
    assert "error" not in rec_b, rec_b
    # the full Layer-1 column set must actually be present
    assert rec_a.get("heldout_rank_icir") is not None or "heldout_rank_icir" in rec_a, rec_a

    differing = {k for k in set(rec_a) | set(rec_b) if rec_a.get(k) != rec_b.get(k)}
    unexpected = differing - ALLOWED_DIFF
    detail = {k: (rec_a.get(k), rec_b.get(k)) for k in sorted(unexpected)}
    assert not unexpected, (
        "approved-book membership changed Layer-1 column(s) that must be reference-invariant: "
        f"{sorted(unexpected)}\n  (A, B) = {detail}"
    )
