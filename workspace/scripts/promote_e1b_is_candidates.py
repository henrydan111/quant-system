# SCRIPT_STATUS: ACTIVE — E1b draft->candidate IS-gate promotion (volatility family, matrix-reuse)
"""Promote the E1b chart-16 VOLATILITY IS-passers draft -> candidate via the factor-lifecycle IS gate,
re-using the 2010-2020 univ_all walk-forward numbers the unified_eval matrix already computed (the same
proven, bit-identical-to-the-gate matrix-reuse path as resign_candidates_2010_2020 / promote_e1a). The
passer set is COMPUTED from the matrix (every catalog ``vol_*`` factor that clears the formal candidate
rule ``assign_candidate_status(field_ok, |heldout_icir|>=0.10, sign>=0.70)``), not hand-listed.

ALL the E1a hardening is reused (GPT IS-promotion review): (1) the REAL ``assign_candidate_status`` with
``field_ok`` from ``per_factor_field_eligible(formal_validation)``; (2) ALL-OR-NONE attach + ``promoted
== requested``; (3) matrix-row identity validation (ESTU_STYLE_V1 native 2010-2020 — ``_validate_row`` +
``_assert_scope_and_reference_consistency``, finite, exactly-once); (4) pre-status==draft guard.

COHORT-REDUNDANCY CAVEAT (user decision 2026-06-17, "all passers"): the volatility passers are ONE
highly-correlated chart-16 family (sign-conditional vol / intraday range / normalized + Williams upper/
lower shadows × {avg,std} × {20,60,120}). They are promoted **resolve-but-label** — each is individually
IS-valid, but they are NOT N independent discoveries; a downstream marginal-contribution selection picks
~4-6 orthogonal representatives (cf. CICC chart-100's 4 ``*_std_6M`` picks). Recorded in provenance.

Provenance a_priori (IS-selected on 2010-2020) -> 2021+ SEALED. Dry-run on a TEMP copy by default; --live
commits (backup first, confirm-first).
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
from workspace.scripts import unified_eval_full_run as fr  # noqa: E402
from workspace.scripts.import_matrix_evidence import (  # noqa: E402
    _validate_row, _assert_scope_and_reference_consistency, MATRIX_DIR,
)

RESULTS = MATRIX_DIR / "results.jsonl"
METHODS = MATRIX_DIR / "methodologies.json"
PROV_DIR = PROJECT_ROOT / "workspace" / "research" / "cicc_replication" / "e1b_is_promotion"
RUN_ID = "e1b_is_candidate_2010_2020"
EVIDENCE_CLASS = "a_priori"
EVIDENCE_KIND = "a_priori_2010_2020_matrix_reuse"
FACTOR_PREFIX = "vol_"
IS_END = fr.TIME_SPLIT.is_end
COHORT_CAVEAT = ("chart-16 volatility family (sign-conditional vol / intraday range / normalized + "
                 "Williams shadows x {avg,std} x {20,60,120}) — HIGHLY CORRELATED; promoted resolve-but-"
                 "label, NOT independent discoveries; a downstream marginal-contribution selection picks "
                 "~4-6 orthogonal representatives (cf. CICC chart-100's 4 *_std_6M picks).")
# the ONE E1b factor that clears |ICIR| but fails sign-consistency (0.64 < 0.70) -> stays draft.
EXPECTED_BLOCKED = {"vol_down_std_20d": "candidate-rule: sign_consistency < 0.70"}


def _assert_pgate_ceilings(registry_dir: Path, factors: set) -> None:
    """GPT IS-gate review finding 3 — P-GATE must precede the IS status change: every factor being
    promoted must already carry a candidate_ceiling ReplicationGovernanceRecord (truth-observed
    2022-07 short-OOS cap). Fail closed if any is missing / not candidate_ceiling."""
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
        raise SystemExit(f"P-GATE preflight FAILED (finding 3): {len(missing)} factors have NO governance "
                         f"record {missing[:5]}, {len(wrong)} not candidate_ceiling {wrong[:5]} — run the "
                         "E1b P-GATE (gate_cohort_factors --live) BEFORE the IS-gate.")
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

    methods = json.loads(METHODS.read_text(encoding="utf-8"))
    _assert_scope_and_reference_consistency(methods)
    univ_method = methods.get("univ_all")
    if univ_method is None:
        raise SystemExit("methodologies.json has no univ_all methodology — cannot validate rows")

    # validate + collect every vol_ univ_all row (exactly once, ESTU_STYLE_V1 native 2010-2020)
    rows: dict[str, dict] = {}
    blocked: list = []
    for line in RESULTS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        fid = str(r.get("factor", ""))
        if not fid.startswith(FACTOR_PREFIX) or (r.get("universe_id") or "univ_all") != "univ_all":
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

    # field eligibility + the REAL formal candidate rule -> the passer set
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

    # GPT IS-gate review finding 2 — EXPECTED-FAMILY GUARD: the promotion set must equal the exact
    # E1b family derived DETERMINISTICALLY from the catalog (independent of results.jsonl), and the
    # sole candidate-rule blocker must be vol_down_std_20d. A stray vol_* factor or a missing E1b row
    # would otherwise silently change the live promotion set.
    from src.alpha_research.factor_library import get_factor_catalog
    expected_e1b = frozenset(n for n in get_factor_catalog(include_new_data=True) if n.startswith(FACTOR_PREFIX))
    rule_blocked = {fid for fid, why in blocked if "candidate-rule" in why}
    if len(expected_e1b) != 36:
        raise SystemExit(f"catalog has {len(expected_e1b)} vol_ factors, expected 36 — refuse (family drift)")
    if set(rows) != expected_e1b:
        raise SystemExit(f"matrix vol_ rows != catalog E1b family — stray={sorted(set(rows)-expected_e1b)} "
                         f"missing={sorted(expected_e1b-set(rows))} — refuse (set integrity).")
    if rule_blocked != set(EXPECTED_BLOCKED):
        raise SystemExit(f"candidate-rule blockers {sorted(rule_blocked)} != expected {sorted(EXPECTED_BLOCKED)} "
                         "— refuse (the IS-pass/fail boundary moved; re-review before promoting).")
    if expected != (expected_e1b - set(EXPECTED_BLOCKED)):
        raise SystemExit(f"passer set {sorted(expected)} != expected_e1b - blocked — refuse (set integrity).")
    print(f"set-integrity guard PASSED: 36 E1b family, 35 pass, sole blocker={sorted(EXPECTED_BLOCKED)}")
    print(f"E1b candidate gate: {len(verdicts)} pass / {len(rows)} vol_ factors evaluated "
          f"({len(blocked)} blocked)")
    for r in sorted(report, key=lambda x: x["heldout_rank_icir"]):
        print(f"  PASS {r['factor']:26} ICIR={r['heldout_rank_icir']:+.4f} sign={r['sign_consistency']:.2f} dir={r['expected_direction']}")
    for fid, why in blocked:
        print(f"  BLOCKED {fid:26} {why}")
    if not verdicts:
        raise SystemExit("no passers — nothing to promote")

    # registry target (temp copy unless --live)
    if args.live:
        registry_dir = PROJECT_ROOT / "data" / "factor_registry"
    else:
        tmp = Path(tempfile.mkdtemp(prefix="e1b_promote_dryrun_"))
        shutil.copytree(PROJECT_ROOT / "data" / "factor_registry", tmp / "factor_registry")
        registry_dir = tmp / "factor_registry"
        print(f"dry-run registry copy: {registry_dir}")

    store = FactorRegistryStore(registry_dir)
    pre_status = {fid: _status(store, fid) for fid in expected}
    bad = {fid: st for fid, st in pre_status.items() if st != "draft"}
    if bad:
        raise SystemExit(f"expected ALL passers at 'draft' before promotion; got {bad}")

    # finding 3: P-GATE ceilings must already exist for every promoted factor (ordering guard)
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
                         reason=(f"E1b factor_lifecycle IS-heldout gate ({EVIDENCE_KIND}; heldout "
                                 f"ICIR={v['heldout_rank_icir']:+.3f}, sign={v['sign_consistency']:.2f}; "
                                 f"cohort-redundant vol family, resolve-but-label)"),
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
                      "from unified_eval_matrix, bit-identical to the gate; rows validated ESTU_STYLE_V1 "
                      "native 2010-2020 (schema+layer1_hash+scope+window)."),
        "gate_authorization": ("User authorized 'all passers, with cohort-redundancy caveat' "
                               "(AskUserQuestion 2026-06-17). Writing formal_evidence_eligible + "
                               "set_status(candidate) IS the human gate."),
        "oos_status": "a_priori IS-selection on 2010-2020 only; 2021+ UNBURNED/sealed.",
        "cohort_redundancy_caveat": COHORT_CAVEAT,
        "hardening_guards": ["assign_candidate_status(field_ok)", "all-or-none attach",
                             "matrix-row identity (ESTU_STYLE_V1 native 2010-2020)", "pre-status==draft"],
        "promoted": promoted, "blocked": blocked, "verdicts": report,
        "recorder_result": {k: out[k] for k in ("attached", "skipped_drift", "skipped_unknown")},
    }
    (PROV_DIR / "e1b_is_promotion_provenance.json").write_text(
        json.dumps(prov, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"provenance -> {PROV_DIR / 'e1b_is_promotion_provenance.json'}")
    if not args.live:
        print("dry-run complete — real registry untouched. Re-run with --live to commit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
