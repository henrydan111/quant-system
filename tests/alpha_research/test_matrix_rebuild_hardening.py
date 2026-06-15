"""Fail-closed hardening for the residual-scope matrix rebuild (GPT pre-flight review 2026-06-15).

Fast unit tests (no calendar / no eval) for the launch-blocker guards: JSONL tail sanitizer,
methodology-aware done-set, residual-panel broad-ness guard, eval_mask alignment fail-closed, and
the legacy-contaminated quarantine + canonical-view exclusion.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from workspace.scripts.unified_eval_full_run import (
    _assert_residual_panel_broad, _done_factors, _is_success_record, _sanitize_results_tail,
)
from src.alpha_research.factor_eval.unified_eval import _mask_to_eval_universe, _to_dt_inst
from src.alpha_research.factor_registry.store import (
    LEGACY_CONTAMINATED_RESIDUAL_SCOPE, canonical_layer1_evidence,
)


# ── _is_success_record / _done_factors (blocker 1: error/stale rows must recompute) ─────────────
def test_is_success_record_rejects_error_stale_partial():
    schema, l1 = "S1", {"univ_all": "H_ALL", "univ_csi300": "H_300"}
    good = {"factor": "f", "universe_id": "univ_all", "methodology_schema_version": "S1",
            "layer1_methodology_hash": "H_ALL", "heldout_rank_icir": 0.3, "mean_rank_ic": 0.01,
            "coverage": 0.8, "effective_ic_days": 1000}
    assert _is_success_record(good, expected_schema=schema, expected_layer1_by_universe=l1)
    assert not _is_success_record({**good, "error": "boom"}, expected_schema=schema, expected_layer1_by_universe=l1)
    assert not _is_success_record({**good, "layer1_methodology_hash": "STALE"}, expected_schema=schema, expected_layer1_by_universe=l1)
    assert not _is_success_record({**good, "methodology_schema_version": "OLD"}, expected_schema=schema, expected_layer1_by_universe=l1)
    incomplete = {k: v for k, v in good.items() if k != "coverage"}
    assert not _is_success_record(incomplete, expected_schema=schema, expected_layer1_by_universe=l1)


def test_done_factors_skips_error_and_stale(tmp_path):
    rj = tmp_path / "results.jsonl"
    base = {"methodology_schema_version": "S1", "heldout_rank_icir": 0.3, "mean_rank_ic": 0.01,
            "coverage": 0.8, "effective_ic_days": 1000}
    rj.write_text("\n".join([
        json.dumps({"factor": "ok", "universe_id": "univ_all", "layer1_methodology_hash": "H", **base}),
        json.dumps({"factor": "err", "universe_id": "univ_all", "error": "x"}),
        json.dumps({"factor": "stale", "universe_id": "univ_all", "layer1_methodology_hash": "OLD", **base}),
    ]) + "\n", encoding="utf-8")
    v = lambda r: _is_success_record(r, expected_schema="S1", expected_layer1_by_universe={"univ_all": "H"})
    done = _done_factors(rj, validator=v)
    assert done == {("ok", "univ_all")}  # err + stale must recompute


# ── _sanitize_results_tail (blocker 2: a partial tail must be removed before append) ────────────
def test_sanitize_results_tail_truncates_partial(tmp_path):
    rj = tmp_path / "results.jsonl"
    rj.write_text(json.dumps({"factor": "a"}) + "\n" + '{"factor": "partial_no_newline"',
                  encoding="utf-8")  # last line is a corrupt partial (crash mid-write)
    out = _sanitize_results_tail(rj)
    assert out["dropped"] == 1 and out["backup"] is not None
    lines = [json.loads(l) for l in rj.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert lines == [{"factor": "a"}]                     # only the complete line survives
    assert rj.read_text(encoding="utf-8").endswith("\n")  # safe to append after
    assert (tmp_path / out["backup"]).exists()            # original preserved for audit


# ── _assert_residual_panel_broad (blocker 3: no masked residual_panel fallback) ─────────────────
def _mk(idx, masked):
    insts = idx.get_level_values(0)
    s = pd.Series(np.arange(len(idx), dtype=float), index=idx)
    return s.where(~insts.isin([f"T{i:03d}" for i in range(50, 100)])) if masked else s


def test_residual_panel_broad_guard():
    insts = [f"T{i:03d}" for i in range(100)]
    dates = pd.bdate_range("2020-01-01", periods=20)
    idx = pd.MultiIndex.from_product([insts, dates], names=["instrument", "datetime"]).sort_values()
    mask = pd.Series([ix[0] < "T050" for ix in idx], index=idx)  # universe = first 50 instruments
    broad = pd.DataFrame({"f": _mk(idx, masked=False)})
    masked = pd.DataFrame({"f": _mk(idx, masked=True)})          # NaN outside the universe == masked
    _assert_residual_panel_broad(broad, ["f"], mask)             # broad -> ok
    with pytest.raises(RuntimeError, match="already universe-masked"):
        _assert_residual_panel_broad(masked, ["f"], mask)        # masked -> fail-closed


# ── _mask_to_eval_universe (item 5/7): small gap => outside-universe; GROSS mismatch => raise ───
def test_mask_to_eval_universe_small_gap_vs_gross_mismatch():
    idx = pd.MultiIndex.from_product([pd.bdate_range("2020-01-01", periods=4), ["A", "B", "C"]],
                                     names=["datetime", "instrument"])  # 12 rows, already (dt, inst)
    s = pd.Series(1.0, index=idx)
    full_mask = pd.Series(True, index=idx)
    assert _mask_to_eval_universe(s, full_mask).notna().all()          # complete mask -> ok
    # SMALL gap (2/12 absent): the absent rows are treated as outside-universe (NaN), NOT a raise
    out_small = _mask_to_eval_universe(s, full_mask.iloc[:-2])
    assert out_small.isna().sum() == 2 and out_small.notna().sum() == 10
    # GROSS mismatch (8/12 = 67% absent): an index/orientation bug -> fail closed
    with pytest.raises(ValueError, match="gross"):
        _mask_to_eval_universe(s, full_mask.iloc[:4])


# ── quarantine + canonical exclusion (blocker 4: contaminated rows fail-closed out of reads) ────
def test_canonical_excludes_quarantined_rows():
    def row(role, fid="f1"):
        return {"run_id": "r", "run_type": "factor_lifecycle_auto", "factor_id": fid, "version": 1,
                "universe_id": "univ_all", "row_role": role, "evidence_time": "2026-06-15",
                "is_rank_icir": 0.1}
    # f1 has ONLY a contaminated row -> it must NOT surface in the canonical view (fail-closed)
    ev = pd.DataFrame([row(LEGACY_CONTAMINATED_RESIDUAL_SCOPE, "f1"),
                       row("native_layer1", "f2")])
    out = canonical_layer1_evidence(ev)
    assert set(out["factor_id"]) == {"f2"}
    assert (out["row_role"] != LEGACY_CONTAMINATED_RESIDUAL_SCOPE).all()


def test_quarantine_legacy_residual_scope_marks_empty_hash_rows(tmp_path):
    from src.alpha_research.factor_registry.store import FactorRegistryStore
    store = FactorRegistryStore(tmp_path)
    store.factor_evidence = pd.DataFrame([
        {"run_id": "matrix_old", "run_type": "factor_lifecycle_auto", "factor_id": "f1", "version": 1,
         "universe_id": "univ_all", "row_role": "", "layer1_methodology_hash": ""},
        {"run_id": "matrix_v1_univ_all_NEW", "run_type": "factor_lifecycle_auto", "factor_id": "f1",
         "version": 1, "universe_id": "univ_all", "row_role": "native_layer1",
         "layer1_methodology_hash": "NEW"},
    ])
    dry = store.quarantine_legacy_residual_scope(dry_run=True)
    assert dry["matched"] == 1 and dry["dry_run"]
    live = store.quarantine_legacy_residual_scope(dry_run=False)
    assert live["matched"] == 1
    roles = dict(zip(store.factor_evidence["row_role"], store.factor_evidence["layer1_methodology_hash"]))
    assert LEGACY_CONTAMINATED_RESIDUAL_SCOPE in store.factor_evidence["row_role"].tolist()  # empty-hash row marked
    assert "native_layer1" in store.factor_evidence["row_role"].tolist()                     # new row spared
    # idempotent: a second pass matches nothing
    assert store.quarantine_legacy_residual_scope(dry_run=False)["matched"] == 0
