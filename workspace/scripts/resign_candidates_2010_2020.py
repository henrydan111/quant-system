# SCRIPT_STATUS: ACTIVE — one-off: re-sign candidate-gate evidence on the 2010-2020 IS window
"""Re-sign the human-gated factor-lifecycle evidence onto the current 2010-2020 IS window.

CONTEXT (2026-06-14). The 95 ``formal_evidence_eligible=True`` signed rows were produced by
the ``factor_lifecycle`` orchestrator gate on the RETIRED 2014-2020 IS window (run
``phase6_factor_lifecycle_live_prod72`` et al.). The evaluation window was later migrated to
2010-2020 and the automated sweep recomputed, leaving the signed evidence stale (dashboard ↻).

This driver re-signs the signed evidence onto 2010-2020 using the EXACT numbers the candidate
gate would compute — the automated matrix sweep already ran ``run_is_walk_forward(
factor_origin='a_priori')`` on 2010-2020 (bit-identical to the gate; proven: the 2026-06-10
old-window refresh reproduced the signed numbers to 1e-15). We re-use those numbers rather than
recompute. Each re-signed row carries the IS window (effective_start/end) + universe_id so the
dashboard can establish same-window comparability (the gate emits no methodology_hash).

GATE AUTHORIZATION. Writing ``formal_evidence_eligible=True`` rows is the human gate. The user
explicitly authorized this on 2026-06-14 (AskUserQuestion → "Re-sign the 87, flag the 8" +
"Flag only, keep candidate status"). That decision IS the gate-review approval.

RE-VALIDATION. Of the signed set, the ones that still clear the candidate bar
(|heldout_rank_icir| >= 0.10 AND sign_consistency >= 0.70) on the WIDER 2010-2020 window are
re-signed. The ones that no longer clear it are NOT re-signed and NOT downgraded — they keep
candidate status (resolve-but-label) and are flagged in the provenance JSON for human review.

Fail-closed: ``record_lifecycle_evidence`` independently re-checks definition drift; a factor
whose registry definition_hash != the catalog hash is SKIPPED (reported).

Dry-run by default (writes to a temp copy); ``--live`` commits to data/factor_registry.
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

import pandas as pd  # noqa: E402

from src.alpha_research.factor_registry.store import FactorRegistryStore  # noqa: E402
from src.alpha_research.factor_lifecycle.status_rules import (  # noqa: E402
    CAND_HELDOUT_ICIR_MIN,
    CAND_SIGN_CONSISTENCY_MIN,
)

MATRIX = PROJECT_ROOT / "workspace" / "outputs" / "unified_eval_matrix" / "results.jsonl"
PROV_DIR = PROJECT_ROOT / "workspace" / "research" / "factor_resign_2010_2020"
RUN_ID = "resign_univ_all_2010_2020"
EVIDENCE_CLASS = "a_priori"


def _passes(icir, sign_cons) -> bool:
    if icir is None or sign_cons is None:
        return False
    return abs(float(icir)) >= CAND_HELDOUT_ICIR_MIN and float(sign_cons) >= CAND_SIGN_CONSISTENCY_MIN


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="commit to the REAL registry (default: dry-run copy)")
    args = ap.parse_args()

    # 1. authoritative new-window (2010-2020) univ_all numbers, straight from the gate-equivalent sweep
    auto = {}
    for line in MATRIX.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if (r.get("universe_id") or "univ_all") != "univ_all" or "error" in r:
            continue
        auto[r["factor"]] = r

    # 2. the signed set = factors with an existing formal_evidence_eligible factor_lifecycle row
    ev = pd.read_parquet(PROJECT_ROOT / "data" / "factor_registry" / "factor_evidence.parquet")
    signed_ids = sorted(set(
        ev[(ev.run_type == "factor_lifecycle") & (ev.formal_evidence_eligible == True)]["factor_id"]  # noqa: E712
    ))
    master = pd.read_parquet(PROJECT_ROOT / "data" / "factor_registry" / "factor_master.parquet")
    status = master[master.is_current == True].set_index("factor_id")["status"].to_dict()  # noqa: E712

    # 3. re-validate on the wider window; split passers / failers
    verdicts, passers, failers, missing = [], [], [], []
    for fid in signed_ids:
        a = auto.get(fid)
        if a is None:
            missing.append(fid)
            continue
        icir, sc = a.get("heldout_rank_icir"), a.get("sign_consistency")
        rec = {"factor": fid, "status": status.get(fid, "?"),
               "new_icir": icir, "new_sign_cons": sc,
               "effective_start": a.get("effective_start"), "effective_end": a.get("effective_end")}
        if _passes(icir, sc):
            passers.append(rec)
            verdicts.append({
                "factor": fid, "heldout_rank_icir": icir, "sign_consistency": sc,
                "effective_start": a.get("effective_start"), "effective_end": a.get("effective_end"),
                "universe_id": "univ_all",
            })
        else:
            reason = ("uncomputable on new window" if icir is None or sc is None
                      else f"|ICIR|={abs(float(icir)):.3f}<{CAND_HELDOUT_ICIR_MIN} or "
                           f"sign_cons={float(sc):.2f}<{CAND_SIGN_CONSISTENCY_MIN}")
            rec["reason"] = reason
            failers.append(rec)

    print(f"signed set: {len(signed_ids)} | auto-missing: {len(missing)} | "
          f"PASS (re-sign): {len(passers)} | FAIL (flag, keep candidate): {len(failers)}")
    for r in failers:
        print(f"  FLAG ▼ {r['factor']:30} status={r['status']:10} icir={r['new_icir']} "
              f"sign={r['new_sign_cons']}  ({r['reason']})")

    # 4. registry target (dry-run copy unless --live)
    if args.live:
        registry_dir = PROJECT_ROOT / "data" / "factor_registry"
    else:
        tmp = Path(tempfile.mkdtemp(prefix="resign_dryrun_"))
        shutil.copytree(PROJECT_ROOT / "data" / "factor_registry", tmp / "factor_registry")
        registry_dir = tmp / "factor_registry"
        print(f"dry-run registry copy: {registry_dir}")

    store = FactorRegistryStore(registry_dir)
    out = store.record_lifecycle_evidence(
        run_id=RUN_ID, verdicts=verdicts, evidence_class=EVIDENCE_CLASS,
        source_run_dir=str(PROV_DIR),
    )
    print(f"record_lifecycle_evidence: attached={len(out['attached'])} "
          f"skipped_drift={out['skipped_drift']} skipped_unknown={out['skipped_unknown']}")

    if args.live:
        store.save()
        print("store.save() committed to disk")

    # 5. provenance JSON (always written — audit trail for both dry-run and live)
    PROV_DIR.mkdir(parents=True, exist_ok=True)
    prov = {
        "run_id": RUN_ID,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "live": bool(args.live),
        "is_window": {"effective_start": "2010-01-04", "effective_end": "2020-12-03",
                      "nominal_time_split": "2010-01-01..2020-12-31"},
        "candidate_bar": {"heldout_icir_min": CAND_HELDOUT_ICIR_MIN,
                          "sign_consistency_min": CAND_SIGN_CONSISTENCY_MIN},
        "gate_authorization": (
            "User explicitly authorized on 2026-06-14 (AskUserQuestion: 'Re-sign the 87, flag the 8' "
            "+ 'Flag only, keep candidate status'). This is the human gate-review approval. Numbers "
            "are the 2010-2020 run_is_walk_forward(factor_origin='a_priori') results from "
            "unified_eval_matrix (bit-identical to the candidate gate)."),
        "source": str(MATRIX),
        "signed_set_size": len(signed_ids),
        "auto_missing": missing,
        "resigned": passers,
        "flagged_weakened_kept_candidate": failers,
        "recorder_result": {k: out[k] for k in ("attached", "skipped_drift", "skipped_unknown")},
    }
    (PROV_DIR / "resign_provenance.json").write_text(
        json.dumps(prov, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"provenance -> {PROV_DIR / 'resign_provenance.json'}")
    if not args.live:
        print("dry-run complete — real registry untouched. Re-run with --live to commit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
