# SCRIPT_STATUS: ACTIVE — E1a draft->candidate IS-gate promotion (matrix-reuse, user-gated)
"""Promote the E1a momentum/reversal IS-passers draft -> candidate via the factor-lifecycle
IS gate, RE-USING the 2010-2020 univ_all walk-forward numbers the unified_eval matrix already
computed. This is the same lean, proven path as resign_candidates_2010_2020.py: the matrix sweep
ran ``run_is_walk_forward(factor_origin='a_priori')`` on 2010-2020, which is BIT-IDENTICAL to the
orchestrator candidate gate (reproduced to 1e-15, 2026-06-10). Writing
``formal_evidence_eligible=True`` rows + ``set_status('candidate')`` IS the human gate; the user
authorized "promote all 3 IS-passers" (AskUserQuestion 2026-06-17).

Candidate bar (status_rules.assign_candidate_status): ``abs(heldout_rank_icir) >= 0.10 AND
sign_consistency >= 0.70``. The SIGN is captured by ``expected_direction`` (these are NEGATIVE-ICIR
=> ``inverse`` reversal factors; the bar uses |ICIR|).

Scope (user decision): all 3 IS-passers — mmt_route_20d, mmt_route_250d, mmt_discrete_20d.
``mmt_discrete_20d`` is a documented NEAR-DUPLICATE of rev_up_down_ratio_20d (already a candidate):
promoted with a non-independence caveat — it must NOT count as an independent discovery / marginal
contribution win unless a later residual/marginal test clears it (GPT E1a-gate review).

Provenance: a_priori (CICC-handbook-defined, IS-selected on 2010-2020) — NOT oos_informed_backfill,
so 2021+ remains a genuinely SEALED window for any future candidate->approved step.

Dry-run on a TEMP registry copy by default; ``--live`` commits to data/factor_registry (confirm-first).
"""
from __future__ import annotations

import argparse
import json
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
from src.alpha_research.factor_lifecycle.status_rules import (  # noqa: E402
    CAND_HELDOUT_ICIR_MIN, CAND_SIGN_CONSISTENCY_MIN,
)
from src.alpha_research.factor_lifecycle.walk_forward_validation import _expected_direction  # noqa: E402

MATRIX = PROJECT_ROOT / "workspace" / "outputs" / "unified_eval_matrix" / "results.jsonl"
PROV_DIR = PROJECT_ROOT / "workspace" / "research" / "cicc_replication" / "e1a_is_promotion"
RUN_ID = "e1a_is_candidate_2010_2020"
EVIDENCE_CLASS = "a_priori"
FACTORS = ["mmt_route_20d", "mmt_route_250d", "mmt_discrete_20d"]
NEAR_DUP = {"mmt_discrete_20d": "rev_up_down_ratio_20d"}   # non-independence caveat


def _passes(icir, sc) -> bool:
    return (icir is not None and sc is not None
            and abs(float(icir)) >= CAND_HELDOUT_ICIR_MIN and float(sc) >= CAND_SIGN_CONSISTENCY_MIN)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="commit to the REAL registry (default: temp dry-run)")
    args = ap.parse_args()

    # 1. matrix 2010-2020 univ_all numbers (gate-equivalent, bit-identical)
    auto = {}
    for line in MATRIX.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if (r.get("universe_id") or "univ_all") == "univ_all" and "error" not in r:
            auto[r["factor"]] = r

    verdicts, report, blocked = [], [], []
    for fid in FACTORS:
        a = auto.get(fid)
        if a is None:
            blocked.append((fid, "absent from matrix")); continue
        icir, sc = a.get("heldout_rank_icir"), a.get("sign_consistency")
        if not _passes(icir, sc):
            blocked.append((fid, f"below candidate bar (|ICIR|={icir}, sign={sc})")); continue
        direction = _expected_direction(icir)   # negative ICIR -> 'inverse'
        verdicts.append({
            "factor": fid, "heldout_rank_icir": icir, "sign_consistency": sc,
            "n_heldout_blocks": a.get("n_heldout_blocks") or a.get("selected_fold_count"),
            "effective_start": a.get("effective_start"), "effective_end": a.get("effective_end"),
            "universe_id": "univ_all", "expected_direction": direction,
        })
        report.append({"factor": fid, "heldout_rank_icir": icir, "sign_consistency": sc,
                       "expected_direction": direction, "near_duplicate_of": NEAR_DUP.get(fid)})
    print(f"candidate-bar passers: {len(verdicts)}/{len(FACTORS)}")
    for r in report:
        tag = f"  [NEAR-DUP of {r['near_duplicate_of']} — non-independent]" if r["near_duplicate_of"] else ""
        print(f"  {r['factor']:20} ICIR={r['heldout_rank_icir']:+.4f} sign={r['sign_consistency']:.2f} "
              f"dir={r['expected_direction']}{tag}")
    for fid, why in blocked:
        print(f"  BLOCKED {fid}: {why}")
    if not verdicts:
        raise SystemExit("no passers — nothing to promote")

    # 2. registry target (temp copy unless --live)
    if args.live:
        registry_dir = PROJECT_ROOT / "data" / "factor_registry"
    else:
        tmp = Path(tempfile.mkdtemp(prefix="e1a_promote_dryrun_"))
        shutil.copytree(PROJECT_ROOT / "data" / "factor_registry", tmp / "factor_registry")
        registry_dir = tmp / "factor_registry"
        print(f"dry-run registry copy: {registry_dir}")

    store = FactorRegistryStore(registry_dir)
    pre_status = {fid: _status(store, fid) for fid in FACTORS}

    # 3. write FORMAL IS evidence (fail-closed on definition drift) — the human-gate signature
    out = store.record_lifecycle_evidence(
        run_id=RUN_ID, verdicts=verdicts, evidence_class=EVIDENCE_CLASS, source_run_dir=str(PROV_DIR))
    attached = set(out["attached"])
    print(f"\nrecord_lifecycle_evidence: attached={sorted(attached)} "
          f"skipped_drift={out['skipped_drift']} skipped_unknown={out['skipped_unknown']}")

    # 4. set_status(candidate) + expected_direction ONLY for drift-clean attached factors
    promoted = []
    for v in verdicts:
        fid = v["factor"]
        if fid not in attached:
            print(f"  NOT promoting {fid} (evidence not attached — drift/unknown)"); continue
        store.set_status(factor_id=fid, status="candidate",
                         reason=f"E1a factor_lifecycle IS-heldout gate (a_priori; matrix-reuse 2010-2020, "
                                f"heldout ICIR={v['heldout_rank_icir']:+.3f}, sign={v['sign_consistency']:.2f})",
                         source_run_id=RUN_ID)
        store.set_expected_direction(factor_id=fid, expected_direction=v["expected_direction"])
        promoted.append(fid)
    if args.live:
        store.save()
        print("store.save() committed to disk")

    post_status = {fid: _status(store, fid) for fid in FACTORS}
    print("\nstatus transitions:")
    for fid in FACTORS:
        print(f"  {fid:20} {pre_status[fid]} -> {post_status[fid]}")

    # 5. provenance (always)
    PROV_DIR.mkdir(parents=True, exist_ok=True)
    prov = {
        "run_id": RUN_ID, "generated_at": datetime.now().isoformat(timespec="seconds"),
        "live": bool(args.live), "evidence_class": EVIDENCE_CLASS,
        "mechanism": ("matrix-reuse (resign pattern): 2010-2020 univ_all run_is_walk_forward("
                      "factor_origin='a_priori') from unified_eval_matrix, bit-identical to the "
                      "orchestrator candidate gate (proven 1e-15, 2026-06-10)."),
        "candidate_bar": {"heldout_icir_min": CAND_HELDOUT_ICIR_MIN, "sign_consistency_min": CAND_SIGN_CONSISTENCY_MIN},
        "gate_authorization": ("User authorized 'promote all 3 IS-passers' (AskUserQuestion 2026-06-17). "
                               "Writing formal_evidence_eligible=True + set_status(candidate) IS the human gate."),
        "oos_status": ("a_priori IS-selection on 2010-2020 only; 2021+ is UNBURNED/sealed for a future "
                       "candidate->approved step (NOT oos_informed_backfill)."),
        "non_independence_caveats": NEAR_DUP,
        "promoted": promoted, "blocked": blocked,
        "verdicts": report,
        "recorder_result": {k: out[k] for k in ("attached", "skipped_drift", "skipped_unknown")},
    }
    (PROV_DIR / "e1a_is_promotion_provenance.json").write_text(
        json.dumps(prov, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nprovenance -> {PROV_DIR / 'e1a_is_promotion_provenance.json'}")
    if not args.live:
        print("dry-run complete — real registry untouched. Re-run with --live to commit.")
    return 0


def _status(store, fid) -> str:
    cur = store.factor_master[store.factor_master["is_current"].fillna(False)]
    r = cur[cur["factor_id"] == fid]
    return str(r.iloc[0]["status"]) if len(r) else "ABSENT"


if __name__ == "__main__":
    raise SystemExit(main())
