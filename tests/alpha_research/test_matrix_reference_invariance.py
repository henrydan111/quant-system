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
    BOOK_DEPENDENT_LAYER1_FIELDS,
    build_decay_labels,
    preprocess_for_residual,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# The ONLY columns allowed to differ when the approved book changes (+ the timing field). Sourced
# from the CANONICAL list in unified_eval (shared with the evidence-migration byte-equality proof);
# methodology_hash is constant in THIS test (one fixed `method` object run under two books) so its
# presence in the set is harmless here.
BOOK_DEPENDENT = set(BOOK_DEPENDENT_LAYER1_FIELDS)
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


# ── Layer-2 store (PR-1c) — fast unit tests, no eval ──────────────────────────
def test_layer2_store_is_append_only_and_latest_wins(tmp_path):
    from src.alpha_research.factor_eval.layer2_residual_store import Layer2ResidualStore
    s = Layer2ResidualStore(tmp_path)
    base = {"factor_id": "f1", "universe_id": "univ_all", "layer1_methodology_hash": "L1",
            "reference_book_type": "current"}
    s.append([{**base, "reference_set_hash": "BOOK_A", "residual_mean_rank_ic": 0.10,
               "computed_at": "2026-06-15T00:00:00Z"}])
    s.append([{**base, "reference_set_hash": "BOOK_B", "residual_mean_rank_ic": 0.20,
               "computed_at": "2026-06-15T01:00:00Z"}])  # an approval changed the book -> APPEND
    assert len(s.records()) == 2, "append-only: the BOOK_A row must not be overwritten"
    latest = s.latest_descriptive(universe_id="univ_all", layer1_methodology_hash="L1",
                                  reference_book_type="current")
    assert len(latest) == 1 and float(latest.iloc[0]["residual_mean_rank_ic"]) == 0.20
    with pytest.raises(ValueError):
        s.append([{**base, "reference_book_type": "bogus", "reference_set_hash": "X"}])
    # V2: a row missing a required key (e.g. layer1_methodology_hash) is rejected at WRITE time
    with pytest.raises(ValueError):
        s.append([{"factor_id": "f1", "universe_id": "univ_all", "reference_book_type": "current",
                   "reference_set_hash": "BOOK_C"}])  # no layer1_methodology_hash


def test_layer2_assert_single_reference_blocks_cross_book_comparison():
    from src.alpha_research.factor_eval.layer2_residual_store import Layer2ResidualStore
    df = pd.DataFrame([{"factor_id": "f1", "reference_set_hash": "A"},
                       {"factor_id": "f2", "reference_set_hash": "B"}])
    with pytest.raises(ValueError):
        Layer2ResidualStore.assert_single_reference(df)
    Layer2ResidualStore.assert_single_reference(df[df.reference_set_hash == "A"])  # single book -> ok


def test_extract_layer2_from_results_jsonl(tmp_path):
    from src.alpha_research.factor_eval.layer2_residual_store import (
        Layer2ResidualStore, extract_layer2_residuals,
    )
    rj = tmp_path / "results.jsonl"
    rj.write_text("\n".join([
        json.dumps({"factor": "f1", "universe_id": "univ_all", "layer1_methodology_hash": "L1",
                    "reference_set_stable_hash": "S", "reference_set_current_hash": "C",
                    "resid_ic_vs_approved_stable_signed": 0.05,
                    "resid_ic_vs_approved_stable_oriented": 0.05,
                    "resid_ic_vs_approved_current_signed": 0.04}),
        json.dumps({"factor": "f2", "field_eligible": True, "error": "boom"}),         # skipped (error)
        json.dumps({"factor": "f3", "reference_set_stable_hash": None}),               # skipped (no book)
        json.dumps({"factor": "f4", "reference_set_stable_hash": "S", "reference_set_current_hash": "C"}),  # skipped (no layer1 hash)
    ]), encoding="utf-8")
    store = Layer2ResidualStore(tmp_path)
    n = extract_layer2_residuals(rj, store, computed_at="2026-06-15T00:00:00Z",
                                 members_by_book={"stable": ["b", "a"], "current": ["a", "b", "c"]})
    assert n == 2  # f1 -> stable + current; f2 (error) / f3 (no book) / f4 (no layer1 hash) skipped
    recs = store.records()
    assert set(recs["reference_book_type"]) == {"stable", "current"}
    assert set(recs["reference_set_hash"]) == {"S", "C"}
    # A2: member JSON populated + sorted
    stable_row = recs[recs["reference_book_type"] == "stable"].iloc[0]
    assert json.loads(stable_row["reference_set_members_json"]) == ["a", "b"]


# ── canonical Layer-1 default-view (migrated XOR legacy) — fast unit test ──────
def test_canonical_layer1_evidence_dedups_migrated_xor_legacy():
    from src.alpha_research.factor_registry.store import canonical_layer1_evidence

    def row(role, t, ic, run_id, rt="factor_lifecycle_auto", fid="f1", uni="univ_all"):
        return {"run_id": run_id, "run_type": rt, "factor_id": fid, "version": 1,
                "universe_id": uni, "row_role": role, "evidence_time": t, "is_rank_icir": ic}

    # f1: legacy + migrated sibling + a fresh native row -> native wins (highest precedence)
    # f2: legacy + migrated only -> migrated wins (supersedes the immutable legacy row)
    # a non-auto (revalidation) row must pass through untouched, never deduped
    ev = pd.DataFrame([
        row("", "2026-01-01", 0.10, "matrix_legacyA"),
        row("migrated_layer1", "2026-06-01", 0.11, "matrix_legacyA"),
        row("native_layer1", "2026-06-10", 0.12, "matrix_v1_L1"),
        row("", "2026-01-01", 0.20, "matrix_legacyB", fid="f2"),
        row("migrated_layer1", "2026-06-01", 0.21, "matrix_legacyB", fid="f2"),
        row("", "2026-02-02", 0.99, "reval_run", rt="revalidation", fid="f3"),
    ])
    out = canonical_layer1_evidence(ev)
    f1 = out[(out.factor_id == "f1")]
    assert len(f1) == 1 and f1.iloc[0]["row_role"] == "native_layer1"
    assert float(f1.iloc[0]["is_rank_icir"]) == 0.12
    f2 = out[(out.factor_id == "f2")]
    assert len(f2) == 1 and f2.iloc[0]["row_role"] == "migrated_layer1"
    assert float(f2.iloc[0]["is_rank_icir"]) == 0.21
    f3 = out[(out.factor_id == "f3")]   # non-auto row untouched
    assert len(f3) == 1 and float(f3.iloc[0]["is_rank_icir"]) == 0.99
    assert len(out) == 3
