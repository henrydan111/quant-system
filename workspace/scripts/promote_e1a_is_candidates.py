# SCRIPT_STATUS: ACTIVE — E1a draft->candidate IS-gate promotion (matrix-reuse, user-gated, hardened)
"""Promote the E1a momentum/reversal IS-passers draft -> candidate via the factor-lifecycle
IS gate, RE-USING the 2010-2020 univ_all walk-forward numbers the unified_eval matrix already
computed. Same lean, proven path as resign_candidates_2010_2020.py: the matrix sweep ran
``run_is_walk_forward(factor_origin='a_priori')`` on 2010-2020, BIT-IDENTICAL to the orchestrator
candidate gate (reproduced to 1e-15, 2026-06-10). Writing ``formal_evidence_eligible=True`` rows +
``set_status('candidate')`` IS the human gate; the user authorized "promote all 3" (2026-06-17).

HARDENING (GPT IS-promotion cross-review, all blocking, before --live):
  1. Use the REAL formal candidate rule ``assign_candidate_status(field_ok, ...)`` — field eligibility
     via the canonical ``per_factor_field_eligible(stage='formal_validation')``, NOT a local threshold.
  2. ALL-OR-NONE: after evidence attach, fail the batch unless attached == ALL requested and there is
     NO drift/unknown; assert promoted == requested after the status loop.
  3. MATRIX-ROW IDENTITY: each univ_all row must pass the import-side validators (schema +
     layer1_methodology_hash + reference hashes), the methodology scope must be ESTU_STYLE_V1
     (corrected residual-scope), the IS window <= 2020-12-31, metrics finite, factor appears exactly
     once — proves the row is the corrected native 2010-2020 Layer-1 matrix, not a stale/legacy/smoke row.
  4. Pre-status must be ``draft`` for all three (no candidate->candidate spam / silent overwrite).

Scope (user): all 3 — mmt_route_20d, mmt_route_250d, mmt_discrete_20d. ``mmt_discrete_20d`` is a
documented NEAR-DUPLICATE of rev_up_down_ratio_20d (already candidate): promoted with a
non-independence caveat (must NOT count as an independent discovery/marginal win unless a later
residual test clears it). Provenance a_priori (IS-selected on 2010-2020) — NOT oos_informed_backfill,
so 2021+ stays SEALED.

Dry-run on a TEMP registry copy by default; ``--live`` commits to data/factor_registry (backup first).
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
# reuse the import-side hardened validators (DRY): row identity + scope/reference consistency
from workspace.scripts.import_matrix_evidence import (  # noqa: E402
    _validate_row, _assert_scope_and_reference_consistency, MATRIX_DIR,
)

RESULTS = MATRIX_DIR / "results.jsonl"
METHODS = MATRIX_DIR / "methodologies.json"
PROV_DIR = PROJECT_ROOT / "workspace" / "research" / "cicc_replication" / "e1a_is_promotion"
RUN_ID = "e1a_is_candidate_2010_2020"
EVIDENCE_CLASS = "a_priori"
EVIDENCE_KIND = "a_priori_2010_2020_matrix_reuse"
FACTORS = ["mmt_route_20d", "mmt_route_250d", "mmt_discrete_20d"]
NEAR_DUP = {"mmt_discrete_20d": "rev_up_down_ratio_20d"}
IS_END = fr.TIME_SPLIT.is_end   # "2020-12-31"


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

    # ── (3) methodology scope + reference consistency: proves the matrix is the corrected
    # ESTU_STYLE_V1 build (raises on scope drift / legacy / non-decoupled methodology) ──
    methods = json.loads(METHODS.read_text(encoding="utf-8"))
    _assert_scope_and_reference_consistency(methods)   # asserts residual_preprocess_scope==ESTU_STYLE_V1
    univ_method = methods.get("univ_all")
    if univ_method is None:
        raise SystemExit("methodologies.json has no univ_all methodology — cannot validate rows")

    # ── (3) collect + validate the univ_all row for each requested factor (exactly once) ──
    rows: dict[str, dict] = {}
    blocked: list = []
    for line in RESULTS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("factor") not in FACTORS or (r.get("universe_id") or "univ_all") != "univ_all":
            continue
        fid = r["factor"]
        reason = _validate_row(r, univ_method)   # schema / layer1_hash / ref hashes / metric-key presence
        if reason:
            blocked.append((fid, f"row-identity: {reason}")); continue
        eff_end = str(r.get("effective_end") or "")
        if eff_end and eff_end > IS_END:
            blocked.append((fid, f"effective_end {eff_end} beyond IS end {IS_END}")); continue
        if not (_finite(r.get("heldout_rank_icir")) and _finite(r.get("sign_consistency"))):
            blocked.append((fid, "non-finite heldout_rank_icir/sign_consistency")); continue
        if fid in rows:
            raise SystemExit(f"{fid}: >1 univ_all row in results.jsonl — ambiguous, refuse (fail-closed)")
        rows[fid] = r

    # ── (1) field eligibility (canonical) + the REAL formal candidate rule ──
    field_elig = per_factor_field_eligible(FACTORS, stage="formal_validation")
    verdicts, report = [], []
    for fid in FACTORS:
        r = rows.get(fid)
        if r is None:
            if not any(b[0] == fid for b in blocked):
                blocked.append((fid, "no valid univ_all matrix row")); continue
            continue
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
        report.append({"factor": fid, "heldout_rank_icir": icir, "sign_consistency": sc,
                       "expected_direction": direction, "field_ok": bool(field_elig.get(fid, False)),
                       "rule_reason": reason, "near_duplicate_of": NEAR_DUP.get(fid)})

    print(f"hardened candidate gate: {len(verdicts)}/{len(FACTORS)} pass")
    for r in report:
        tag = f"  [NEAR-DUP of {r['near_duplicate_of']} — non-independent]" if r["near_duplicate_of"] else ""
        print(f"  {r['factor']:20} ICIR={r['heldout_rank_icir']:+.4f} sign={r['sign_consistency']:.2f} "
              f"dir={r['expected_direction']} field_ok={r['field_ok']}{tag}")
    for fid, why in blocked:
        print(f"  BLOCKED {fid}: {why}")

    expected = {v["factor"] for v in verdicts}
    if expected != set(FACTORS):
        msg = (f"hardened gate admitted {sorted(expected)} != requested {FACTORS} — refuse "
               "partial promotion (user authorized all 3; fail-closed).")
        if args.live:
            raise SystemExit(msg)
        print(f"\n[dry-run] WOULD REFUSE LIVE: {msg}")

    # ── registry target (temp copy unless --live) ──
    if args.live:
        registry_dir = PROJECT_ROOT / "data" / "factor_registry"
    else:
        tmp = Path(tempfile.mkdtemp(prefix="e1a_promote_dryrun_"))
        shutil.copytree(PROJECT_ROOT / "data" / "factor_registry", tmp / "factor_registry")
        registry_dir = tmp / "factor_registry"
        print(f"dry-run registry copy: {registry_dir}")

    store = FactorRegistryStore(registry_dir)
    pre_status = {fid: _status(store, fid) for fid in FACTORS}
    # ── (4) pre-status must be draft for every requested factor ──
    bad = {fid: st for fid, st in pre_status.items() if st != "draft"}
    if bad:
        raise SystemExit(f"expected ALL requested factors at 'draft' before promotion; got {bad} "
                         "(refuse candidate->candidate spam / silent overwrite).")

    # ── write FORMAL IS evidence (fail-closed on definition drift) ──
    out = store.record_lifecycle_evidence(
        run_id=RUN_ID, verdicts=verdicts, evidence_class=EVIDENCE_CLASS, source_run_dir=str(PROV_DIR))
    attached = set(out["attached"])
    print(f"\nrecord_lifecycle_evidence: attached={sorted(attached)} "
          f"skipped_drift={out['skipped_drift']} skipped_unknown={out['skipped_unknown']}")
    # ── (2) ALL-OR-NONE: refuse any partial attach ──
    if attached != expected or out["skipped_drift"] or out["skipped_unknown"]:
        raise SystemExit(f"evidence attach INCOMPLETE: attached={sorted(attached)} expected={sorted(expected)} "
                         f"drift={out['skipped_drift']} unknown={out['skipped_unknown']} — refuse (all-or-none).")

    # ── set_status(candidate) + expected_direction for every attached factor ──
    promoted = []
    for v in verdicts:
        fid = v["factor"]
        store.set_status(factor_id=fid, status="candidate",
                         reason=(f"E1a factor_lifecycle IS-heldout gate ({EVIDENCE_KIND}; heldout "
                                 f"ICIR={v['heldout_rank_icir']:+.3f}, sign={v['sign_consistency']:.2f})"),
                         source_run_id=RUN_ID)
        store.set_expected_direction(factor_id=fid, expected_direction=v["expected_direction"])
        promoted.append(fid)
    assert set(promoted) == expected, f"promoted {sorted(promoted)} != expected {sorted(expected)}"
    if args.live:
        store.save()
        print("store.save() committed to disk")

    post_status = {fid: _status(store, fid) for fid in FACTORS}
    print("\nstatus transitions:")
    for fid in FACTORS:
        print(f"  {fid:20} {pre_status[fid]} -> {post_status[fid]}")

    # ── provenance ──
    PROV_DIR.mkdir(parents=True, exist_ok=True)
    prov = {
        "run_id": RUN_ID, "generated_at": datetime.now().isoformat(timespec="seconds"),
        "live": bool(args.live), "evidence_class": EVIDENCE_CLASS,
        "mechanism": ("matrix-reuse (resign pattern): 2010-2020 univ_all run_is_walk_forward("
                      "factor_origin='a_priori') from unified_eval_matrix, bit-identical to the "
                      "orchestrator candidate gate (1e-15, 2026-06-10); rows validated for corrected "
                      "ESTU_STYLE_V1 native Layer-1 identity (schema+layer1_hash+scope+window)."),
        "gate_authorization": ("User authorized 'promote all 3 IS-passers' (AskUserQuestion 2026-06-17). "
                               "Writing formal_evidence_eligible=True + set_status(candidate) IS the human gate."),
        "oos_status": ("a_priori IS-selection on 2010-2020 only; 2021+ is UNBURNED/sealed for a future "
                       "candidate->approved step (NOT oos_informed_backfill)."),
        "hardening_guards": ["assign_candidate_status(field_ok)", "all-or-none attach",
                             "matrix-row identity (ESTU_STYLE_V1 native 2010-2020)", "pre-status==draft"],
        "non_independence_caveats": NEAR_DUP,
        "promoted": promoted, "blocked": blocked, "verdicts": report,
        "recorder_result": {k: out[k] for k in ("attached", "skipped_drift", "skipped_unknown")},
    }
    (PROV_DIR / "e1a_is_promotion_provenance.json").write_text(
        json.dumps(prov, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nprovenance -> {PROV_DIR / 'e1a_is_promotion_provenance.json'}")
    if not args.live:
        print("dry-run complete — real registry untouched. Re-run with --live to commit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
