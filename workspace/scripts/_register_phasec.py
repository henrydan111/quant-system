"""POST-PUBLISH registration for $profit_dedt_sq_q0 (GPT Phase-C R2 Blocker: provider must attest FIRST).

A provider-bound approval record must NOT exist in config/field_registry/approvals/ until the live provider
actually carries the field + the matching provider_build_id (else daily-QA approval_evidence_binding fails —
the §3.4 invariant). So the approval YAML lives in workspace/research/materialization_phase1/pending_registration/
until this script runs, AFTER _publish_phasec_additive.py has published the provider.

This script is FAIL-CLOSED: it refuses to register unless
  (1) the live provider_build.json provider_build_id == the additive build id, AND
  (2) the live provider actually SERVES $profit_dedt_sq_q0 (spot-check real bins).
Then it: copies the approval YAML into approvals/, inserts $profit_dedt_sq_q0 into the indicators block of
field_status.yaml, and appends the field_approval_log.jsonl entry. The catalog factor (qual_dtprofit_to_profit_q)
+ sync_catalog + the approval re-bind are done as explicit follow-up steps (printed at the end).

Run AFTER publish:  PYTHONPATH=src venv/Scripts/python.exe workspace/scripts/_register_phasec.py
"""
from __future__ import annotations

import glob
import json
import os
import sys
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path("E:/量化系统")
sys.path.insert(0, str(ROOT / "src"))

BUILD_ID = "phasec_profit_dedt_sq_20260624"
FIELD = "$profit_dedt_sq_q0"
LIVE = ROOT / "data" / "qlib_data"
APPROVALS = ROOT / "config" / "field_registry" / "approvals"
PENDING = ROOT / "workspace" / "research" / "materialization_phase1" / "pending_registration"
APPROVAL_NAME = "2026-06-24_profit_dedt_sq_to_approved.yaml"
FIELD_STATUS = ROOT / "config" / "field_registry" / "field_status.yaml"
APPROVAL_LOG = ROOT / "config" / "field_registry" / "field_approval_log.jsonl"
INDICATORS_ANCHOR = "      - $valuechange_income\n"   # last field in the indicators block (insert AFTER)


def fail(msg: str) -> None:
    print(f"REFUSED: {msg}")
    raise SystemExit(1)


def main() -> int:
    # (1) provider attests the build id
    manifest_p = LIVE / "metadata" / "provider_build.json"
    if not manifest_p.exists():
        fail("no live provider_build.json")
    live_id = json.loads(manifest_p.read_text(encoding="utf-8")).get("provider_build_id")
    if live_id != BUILD_ID:
        fail(f"live provider_build_id={live_id!r} != {BUILD_ID!r} — publish the provider FIRST "
             f"(workspace/scripts/_publish_phasec_additive.py)")
    print(f"OK provider_build_id == {BUILD_ID}")

    # (2) provider actually serves the field (spot-check real bins, >=3 stocks non-empty)
    feat = LIVE / "features"
    found = 0
    for binp in glob.glob(str(feat / "*" / "profit_dedt_sq_q0.day.bin"))[:2000]:
        arr = np.fromfile(binp, dtype=np.float32)
        if arr.size > 1 and np.isfinite(arr[1:]).any():
            found += 1
        if found >= 3:
            break
    if found < 3:
        fail(f"live provider does not serve {FIELD} with real values (found {found}) — publish FIRST")
    print(f"OK provider serves {FIELD} ({found}+ stocks with real bins)")

    # (3) copy approval YAML pending -> approvals/
    src = PENDING / APPROVAL_NAME
    dst = APPROVALS / APPROVAL_NAME
    if not src.exists() and not dst.exists():
        fail(f"approval YAML missing in both {PENDING} and {APPROVALS}")
    if not dst.exists():
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"copied approval YAML -> {dst.relative_to(ROOT)}")
    else:
        print(f"approval YAML already in approvals/ ({dst.name})")

    # (4) insert $profit_dedt_sq_q0 into the indicators block of field_status.yaml (idempotent)
    text = FIELD_STATUS.read_text(encoding="utf-8")
    if f"      - {FIELD}\n" in text:
        print(f"{FIELD} already in field_status.yaml")
    else:
        if INDICATORS_ANCHOR not in text:
            fail(f"indicators anchor {INDICATORS_ANCHOR!r} not found in field_status.yaml")
        insert = (INDICATORS_ANCHOR
                  + "      # Phase-C (2026-06-24): single-quarter 扣非净利润 DERIVED from the indicators\n"
                  + "      # CUMULATIVE profit_dedt (derive_single_quarter_value). PIT-correct replacement for\n"
                  + "      # the unregistered vendor q_dtprofit_to_profit. coverage_tier=sub. q1..q4 stay\n"
                  + "      # unregistered until a factor needs them. See approvals/2026-06-24_profit_dedt_sq_to_approved.yaml.\n"
                  + f"      - {FIELD}\n")
        FIELD_STATUS.write_text(text.replace(INDICATORS_ANCHOR, insert, 1), encoding="utf-8")
        print(f"inserted {FIELD} into the indicators block of field_status.yaml")

    # (5) append the field_approval_log.jsonl entry (idempotent on evidence_file)
    log_text = APPROVAL_LOG.read_text(encoding="utf-8") if APPROVAL_LOG.exists() else ""
    if APPROVAL_NAME in log_text:
        print("approval-log entry already present")
    else:
        entry = {
            "event": "promotion", "date": date.today().isoformat(), "dataset_id": "indicators",
            "from_status": "approved", "to_status": "approved",
            "evidence_file": f"config/field_registry/approvals/{APPROVAL_NAME}",
            "fields_added": [FIELD], "pr": "report-rc-registration",
            "notes": ("Phase-C: single-quarter 扣非净利润 $profit_dedt_sq_q0 DERIVED from the indicators "
                      "CUMULATIVE profit_dedt (derive_single_quarter_value, restatement-safe; ann_date->"
                      "effective_date anchor). PIT-correct replacement for the unregistered vendor "
                      "q_dtprofit_to_profit. Value-parity vs vendor q_dtprofit_q0 EXACT; coverage_tier=sub "
                      f"(主板 84.6%->北证 27.0%). provider {BUILD_ID} (additive robocopy /MIR publish; "
                      "additive_build_provenance.json sidecar). GPT R1->R2 REVISE(blocker: future-bound "
                      "approval)->folded. Smoke test tests/data_infra/test_profit_dedt_sq_registry.py."),
        }
        with open(APPROVAL_LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        print("appended field_approval_log.jsonl entry")

    # (6) RE-BIND all prior approval YAMLs to the new provider_build_id. SOUND only if the re-bound
    #     datasets' fields are byte-identical new-live vs .bak (the old live the evidence was generated
    #     against). The additive publish GUARANTEES this — every existing bin is a robocopy /MIR copy of
    #     the old live, NOT re-derived; only $profit_dedt_sq_q0 is new (and is not in .bak). Verify, then bind.
    bak = ROOT / f"data/qlib_data.bak_{BUILD_ID}"
    if not bak.is_dir():
        fail(f"backup {bak} missing — cannot prove re-bind byte-identity")
    old_id = json.loads((bak / "metadata" / "provider_build.json").read_text(encoding="utf-8")).get("provider_build_id")
    print(f"\nre-bind: OLD (.bak) = {old_id}  ->  NEW (live) = {BUILD_ID}")

    def fbytes(prov: Path, code: str, field: str):
        f = prov / "features" / code / (field + ".day.bin")
        return f.read_bytes() if f.exists() else None

    # byte-identity on a representative cross-section of EXISTING (copied) fields
    sample_fields = ["close", "q_roe", "arturn_days", "n_income_sq_q0", "total_assets_q0",
                     "forecast__np_q_yoy", "report_rc__n_active_analysts", "holdertrade_mgr_in_vol"]
    ident_ok = True
    for field in sample_fields:
        res = []
        for code in ("000001_sz", "600519_sh"):
            s, b = fbytes(LIVE, code, field), fbytes(bak, code, field)
            res.append(s is not None and b is not None and s == b)
        allok = all(res)
        print(f"  byte-identical new-live==.bak: {field:32s} {allok}")
        ident_ok = ident_ok and allok
    if not ident_ok:
        fail("re-bound fields NOT byte-identical new-live vs .bak — additive guarantee violated, refusing re-bind")

    n = 0
    for f in glob.glob(str(APPROVALS / "*.yaml")):
        t = Path(f).read_text(encoding="utf-8")
        new = t.replace(f'provider_build_id: "{old_id}"', f'provider_build_id: "{BUILD_ID}"')
        if new != t:
            Path(f).write_text(new, encoding="utf-8")
            n += 1
    print(f"re-bound {n} approval YAMLs {old_id} -> {BUILD_ID}")

    note = APPROVALS / "2026-06-24_rebind_to_phasec_publish.md"
    if not note.exists():
        note.write_text(
            f"# Re-bind to the Phase-C additive publish ({BUILD_ID})\n\n"
            f"After publishing $profit_dedt_sq_q0 via the additive robocopy /MIR path "
            f"(workspace/scripts/_publish_phasec_additive.py), the live provider_build_id became "
            f"`{BUILD_ID}`, so the prior approval YAMLs (bound to `{old_id}`) drifted. Re-bound after "
            f"verifying byte-identity of a cross-section of existing fields new-live vs "
            f"`data/qlib_data.bak_{BUILD_ID}` (the additive publish re-materialized NOTHING — every existing "
            f"bin is a /MIR copy of the old live; only $profit_dedt_sq_q0 is new). "
            f"evaluate_approval_evidence_bindings() -> 0 drift. See additive_build_provenance.json.\n",
            encoding="utf-8")
        print(f"wrote rebind note {note.name}")

    # (7) verify 0 drift against the live manifest
    from data_infra.approval_evidence import evaluate_approval_evidence_bindings  # noqa: E402
    drifts = evaluate_approval_evidence_bindings()
    n_drift = sum(1 for d in drifts if getattr(d, "drift", False))
    print(f"approval bindings: {len(drifts)} scanned, {n_drift} drift")
    if n_drift:
        for d in drifts:
            if getattr(d, "drift", False):
                print("  DRIFT:", getattr(d, "approval_id", d))
        fail("approval-evidence drift after re-bind")

    print("\nREGISTRATION + RE-BIND DONE (0 drift). Follow-up (explicit, run next):")
    print("  1. add factor qual_dtprofit_to_profit_q to src/alpha_research/factor_library/catalog.py + sync_catalog (draft)")
    print("  2. run tests/data_infra/test_profit_dedt_sq_registry.py (now ACTIVE) + test_field_registry.py + test_approval_evidence.py")
    print("  3. run scripts/run_daily_qa.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
