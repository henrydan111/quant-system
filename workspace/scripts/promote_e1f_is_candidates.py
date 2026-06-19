# SCRIPT_STATUS: ACTIVE — E1f draft->candidate IS-gate promotion (capital flow, matrix-reuse)
"""Promote the E1f chart-64 CAPITAL-FLOW IS-passers draft -> candidate via the factor-lifecycle IS gate,
re-using the 2010-2020 univ_all walk-forward the unified_eval matrix already computed (matrix-reuse,
documented bit-identical to the orchestrator candidate gate; same path as promote_e1a/b/c/d). The passer
set is COMPUTED from the matrix via the REAL ``assign_candidate_status`` — not hand-listed.

UNLIKE E1c/E1d (all passed), E1f is SELECTIVE: only 3 of the 9 faithful active-family factors clear the
univ_all rule. The signal lives in the ORDER-SIZE decomposition: large-order net-buy intensity is positive
(institutional accumulation), extra-large is negative (distribution / 拉高出货), and the TOTAL aggregates
are DEGENERATE (net flow ≈ 0 → |ICIR| ~0.07). The 6 blocked are EXPECTED (the 2 totals + the borderline
medium/small) — the gate stopping weak factors, which is healthier than the prior all-pass waves.

The ``flow_act_buy_`` namespace is UNIQUELY E1f → bare-prefix family, asserted to be exactly 9.

ALL the E1a/b/c/d hardening is reused: real ``assign_candidate_status(field_ok)``; ALL-OR-NONE attach +
``promoted == requested``; ESTU_STYLE_V1 matrix-row identity; pre-status==draft; P-GATE-ceiling preflight;
set-integrity guard (matrix-9 == catalog-9; rule-blockers == EXPECTED_BLOCKED's 6; passer == family − blocked).

MIXED expected_direction among the 3 passers (2 positive large-order + 1 inverse extra-large). Provenance
a_priori (IS-selected on 2010-2020) -> 2021+ SEALED. Dry-run on a TEMP copy by default; --live commits.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from src.alpha_research.factor_registry.store import FactorRegistryStore  # noqa: E402
from src.alpha_research.factor_lifecycle.status_rules import assign_candidate_status  # noqa: E402
from src.alpha_research.factor_lifecycle.walk_forward_validation import _expected_direction  # noqa: E402
from src.research_orchestrator.factor_lifecycle_steps import per_factor_field_eligible  # noqa: E402
from src.alpha_research.factor_library import get_factor_catalog  # noqa: E402
from workspace.scripts import unified_eval_full_run as fr  # noqa: E402
from workspace.scripts.import_matrix_evidence import (  # noqa: E402
    _validate_row, _assert_scope_and_reference_consistency, MATRIX_DIR,
)

RESULTS = MATRIX_DIR / "results.jsonl"
METHODS = MATRIX_DIR / "methodologies.json"
PROV_DIR = PROJECT_ROOT / "workspace" / "research" / "cicc_replication" / "e1f_is_promotion"
RUN_ID = "e1f_is_candidate_2010_2020"
EVIDENCE_CLASS = "a_priori"
EVIDENCE_KIND = "a_priori_2010_2020_matrix_reuse"
E1F_PREFIX = "flow_act_buy_"   # uniquely E1f
IS_END = fr.TIME_SPLIT.is_end
COHORT_CAVEAT = ("chart-64 capital-flow active-family — the 3 passers are a correlated LARGE-order net-buy "
                 "pair (flow_act_buy_prop_l + flow_act_buy_shift_dist_l, both positive = institutional "
                 "accumulation) + the EXTRA-large displacement (flow_act_buy_shift_dist_xl, inverse = "
                 "distribution). Promoted resolve-but-label, NOT 3 independent discoveries; a downstream "
                 "marginal-contribution selection picks ~2 (one large-order representative + the xl).")
CROSS_WAVE_CAVEAT = ("E1f active-net-flow factors are conceptually related to the existing flow_* family "
                     "(mean-of-ratios net_pct) and to E1c liquidity/turnover; the prop ratio-of-sums is a "
                     "DISTINCT estimator (GPT-confirmed), but downstream marginal-contribution + residual-"
                     "vs-book selection must decide independence before counting as new discoveries.")
# E1f: 6 of 9 blocked by the candidate rule (2 degenerate totals + 4 borderline medium/small). All
# "marginal IS-heldout" (|ICIR|<0.10 OR sign<0.70). Derived from the matrix; the gate filters them.
EXPECTED_BLOCKED: dict = {
    "flow_act_buy_prop_20d": "candidate-rule: total aggregate degenerate (|ICIR| 0.07, sign 0.55)",
    "flow_act_buy_shift_dist_20d": "candidate-rule: total aggregate degenerate (|ICIR| 0.07, sign 0.64)",
    "flow_act_buy_prop_m_20d": "candidate-rule: sign 0.64 < 0.70",
    "flow_act_buy_shift_dist_m_20d": "candidate-rule: sign 0.64 < 0.70",
    "flow_act_buy_prop_s_20d": "candidate-rule: |ICIR| 0.015 < 0.10",
    "flow_act_buy_shift_dist_s_20d": "candidate-rule: |ICIR| 0.090 < 0.10",
}


def _e1f_family() -> frozenset:
    """The 9 E1f flow_act_buy_* ids, derived deterministically from the catalog (independent of results)."""
    ids = frozenset(n for n in get_factor_catalog(include_new_data=True) if n.startswith(E1F_PREFIX))
    if len(ids) != 9:
        raise SystemExit(f"catalog has {len(ids)} E1f flow_act_buy_ factors, expected 9 — refuse (family drift)")
    return ids


def _assert_pgate_ceilings(registry_dir: Path, factors: set) -> None:
    """Every promoted factor must already carry a candidate_ceiling ReplicationGovernanceRecord."""
    from src.alpha_research.factor_registry.replication_governance import ReplicationGovernanceStore
    gov = ReplicationGovernanceStore(registry_dir).records()
    missing, wrong = [], []
    for fid in sorted(factors):
        g = gov[gov["factor_id"] == fid] if len(gov) else gov
        if not len(g):
            missing.append(fid); continue
        ceil = str(g.sort_values("updated_at").iloc[-1]["status_ceiling"])
        if ceil != "candidate_ceiling":
            wrong.append((fid, ceil))
    if missing or wrong:
        raise SystemExit(f"P-GATE preflight FAILED: {len(missing)} no record {missing[:5]}, {len(wrong)} "
                         f"not candidate_ceiling {wrong[:5]} — run the E1f P-GATE BEFORE the IS-gate.")
    print(f"P-GATE preflight PASSED: all {len(factors)} promoted factors carry a candidate_ceiling record")


def _finite(x) -> bool:
    try:
        return x is not None and math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def _status(store, fid) -> str:
    cur = store.factor_master[store.factor_master["is_current"].fillna(False)]
    r = cur[cur["factor_id"] == fid]
    return str(r.iloc[0]["status"]) if len(r) else "ABSENT"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="commit to the REAL registry (default: temp dry-run)")
    args = ap.parse_args()

    e1f_family = _e1f_family()

    methods = json.loads(METHODS.read_text(encoding="utf-8"))
    _assert_scope_and_reference_consistency(methods)
    univ_method = methods.get("univ_all")
    if univ_method is None:
        raise SystemExit("methodologies.json has no univ_all methodology — cannot validate rows")

    rows: dict[str, dict] = {}
    blocked: list = []
    for line in RESULTS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        fid = str(r.get("factor", ""))
        if fid not in e1f_family or (r.get("universe_id") or "univ_all") != "univ_all":
            continue
        reason = _validate_row(r, univ_method)
        if reason:
            blocked.append((fid, f"row-identity: {reason}")); continue
        eff_end = str(r.get("effective_end") or "")
        if eff_end and eff_end > IS_END:
            blocked.append((fid, f"effective_end {eff_end} beyond IS {IS_END}")); continue
        if not (_finite(r.get("heldout_rank_icir")) and _finite(r.get("sign_consistency"))):
            blocked.append((fid, "non-finite metrics")); continue
        if fid in rows:
            raise SystemExit(f"{fid}: >1 univ_all row — ambiguous, refuse")
        rows[fid] = r

    field_elig = per_factor_field_eligible(sorted(rows), stage="formal_validation")
    verdicts, report = [], []
    for fid in sorted(rows):
        r = rows[fid]
        icir, sc = r["heldout_rank_icir"], r["sign_consistency"]
        status, reason = assign_candidate_status(
            field_ok=bool(field_elig.get(fid, False)),
            heldout_rank_icir=icir, sign_consistency=sc, evidence_kind=EVIDENCE_KIND)
        if status != "candidate":
            blocked.append((fid, f"candidate-rule: {reason}")); continue
        direction = _expected_direction(icir)
        verdicts.append({"factor": fid, "heldout_rank_icir": icir, "sign_consistency": sc,
                         "n_heldout_blocks": r.get("n_heldout_blocks") or r.get("selected_fold_count"),
                         "effective_start": r.get("effective_start"), "effective_end": r.get("effective_end"),
                         "universe_id": "univ_all", "expected_direction": direction})
        report.append({"factor": fid, "heldout_rank_icir": round(icir, 4), "sign_consistency": round(sc, 2),
                       "expected_direction": direction})

    expected = {v["factor"] for v in verdicts}
    rule_blocked = {fid for fid, why in blocked if "candidate-rule" in why}
    if set(rows) != e1f_family:
        raise SystemExit(f"matrix E1f rows != catalog E1f family — stray={sorted(set(rows)-e1f_family)} "
                         f"missing={sorted(e1f_family-set(rows))} — refuse (set integrity).")
    if rule_blocked != set(EXPECTED_BLOCKED):
        raise SystemExit(f"candidate-rule blockers {sorted(rule_blocked)} != expected {sorted(EXPECTED_BLOCKED)} "
                         "— refuse (the IS-pass/fail boundary moved; re-review before promoting).")
    if expected != (e1f_family - set(EXPECTED_BLOCKED)):
        raise SystemExit(f"passer set {sorted(expected)} != e1f_family - blocked — refuse (set integrity).")
    n_pos = sum(1 for v in verdicts if v["expected_direction"] == "positive")
    n_inv = sum(1 for v in verdicts if v["expected_direction"] == "inverse")
    print(f"set-integrity guard PASSED: 9 E1f family, {len(expected)} pass, {len(EXPECTED_BLOCKED)} blocked")
    print(f"  expected_direction split: {n_pos} positive (large-order accumulation) / {n_inv} inverse (xl distribution)")
    print(f"E1f candidate gate: {len(verdicts)} pass / {len(rows)} flow_act_buy_ factors evaluated "
          f"({len(blocked)} blocked)")
    for r in sorted(report, key=lambda x: x["heldout_rank_icir"]):
        print(f"  PASS {r['factor']:32} ICIR={r['heldout_rank_icir']:+.4f} sign={r['sign_consistency']:.2f} dir={r['expected_direction']}")
    for fid, why in sorted(blocked):
        print(f"  BLOCKED {fid:32} {why}")
    if not verdicts:
        raise SystemExit("no passers — nothing to promote")

    if args.live:
        registry_dir = PROJECT_ROOT / "data" / "factor_registry"
    else:
        tmp = Path(tempfile.mkdtemp(prefix="e1f_promote_dryrun_"))
        shutil.copytree(PROJECT_ROOT / "data" / "factor_registry", tmp / "factor_registry")
        registry_dir = tmp / "factor_registry"
        print(f"dry-run registry copy: {registry_dir}")

    store = FactorRegistryStore(registry_dir)
    pre_status = {fid: _status(store, fid) for fid in expected}
    bad = {fid: st for fid, st in pre_status.items() if st != "draft"}
    if bad:
        raise SystemExit(f"expected ALL passers at 'draft' before promotion; got {bad}")

    _assert_pgate_ceilings(registry_dir, expected)

    out = store.record_lifecycle_evidence(
        run_id=RUN_ID, verdicts=verdicts, evidence_class=EVIDENCE_CLASS, source_run_dir=str(PROV_DIR))
    attached = set(out["attached"])
    print(f"\nrecord_lifecycle_evidence: attached={len(attached)} skipped_drift={out['skipped_drift']} "
          f"skipped_unknown={out['skipped_unknown']}")
    if attached != expected or out["skipped_drift"] or out["skipped_unknown"]:
        raise SystemExit(f"evidence attach INCOMPLETE: attached={len(attached)} expected={len(expected)} "
                         f"drift={out['skipped_drift']} unknown={out['skipped_unknown']} — refuse (all-or-none).")

    promoted = []
    for v in verdicts:
        fid = v["factor"]
        store.set_status(factor_id=fid, status="candidate",
                         reason=(f"E1f factor_lifecycle IS-heldout gate ({EVIDENCE_KIND}; heldout "
                                 f"ICIR={v['heldout_rank_icir']:+.3f}, sign={v['sign_consistency']:.2f}; "
                                 f"order-size capital-flow, resolve-but-label)"),
                         source_run_id=RUN_ID)
        store.set_expected_direction(factor_id=fid, expected_direction=v["expected_direction"])
        promoted.append(fid)
    assert set(promoted) == expected, f"promoted {len(promoted)} != expected {len(expected)}"
    if args.live:
        store.save()
        print("store.save() committed to disk")

    post = {fid: _status(store, fid) for fid in expected}
    n_cand = sum(1 for s in post.values() if s == "candidate")
    print(f"\nstatus: {n_cand}/{len(expected)} -> candidate (all expected={n_cand == len(expected)})")

    PROV_DIR.mkdir(parents=True, exist_ok=True)
    prov = {
        "run_id": RUN_ID, "generated_at": datetime.now().isoformat(timespec="seconds"),
        "live": bool(args.live), "evidence_class": EVIDENCE_CLASS,
        "mechanism": ("matrix-reuse (resign pattern): 2010-2020 univ_all run_is_walk_forward(a_priori) "
                      "from unified_eval_matrix, bit-identical to the gate; rows validated ESTU_STYLE_V1."),
        "selectivity": (f"{len(expected)} of 9 pass the univ_all rule — SELECTIVE (unlike E1c/E1d all-pass); "
                        "signal in order-size decomposition (large +, extra-large −), totals degenerate."),
        "gate_authorization": ("User authorized 'all passers, with cohort-redundancy caveat'. Writing "
                               "formal_evidence_eligible + set_status(candidate) IS the human gate."),
        "oos_status": "a_priori IS-selection on 2010-2020 only; 2021+ UNBURNED/sealed.",
        "expected_direction_split": {"positive_large_order_accumulation": n_pos, "inverse_xl_distribution": n_inv},
        "cohort_redundancy_caveat": COHORT_CAVEAT,
        "cross_wave_redundancy_caveat": CROSS_WAVE_CAVEAT,
        "deferred": ("the 9 'buy' family (buy_shift_dist = affine alias of act_buy_shift_dist, Pearson 1.0; "
                     "total-buy needs passive flow) + the 10 open/close factors (no intraday split). The 6 "
                     "blocked active factors stay draft (marginal IS; resolve-but-label)."),
        "hardening_guards": ["assign_candidate_status(field_ok)", "all-or-none attach",
                             "matrix-row identity (ESTU_STYLE_V1 native 2010-2020)", "pre-status==draft",
                             "bare-flow_act_buy_ membership (uniquely E1f)", "P-GATE ceiling preflight",
                             "set-integrity (6 EXPECTED_BLOCKED)"],
        "promoted": promoted, "blocked": blocked, "verdicts": report,
        "recorder_result": {k: out[k] for k in ("attached", "skipped_drift", "skipped_unknown")},
    }
    (PROV_DIR / "e1f_is_promotion_provenance.json").write_text(
        json.dumps(prov, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"provenance -> {PROV_DIR / 'e1f_is_promotion_provenance.json'}")
    if not args.live:
        print("dry-run complete — real registry untouched. Re-run with --live to commit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
