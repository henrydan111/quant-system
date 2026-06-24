"""Register the stk_holdertrade 高管 fields + re-bind drifted approvals to the new provider build.

Safety: re-bind is sound ONLY if the re-bound datasets' fields are byte-identical between the new
live provider and the .bak (= the old live the evidence was generated against). The Phase-1 rebuild
only touched indicators (q_* added; existing re-materialized identically) + stk_holdertrade (高管
added; existing identical); every other dataset was copied unchanged. Verify, then re-bind.
"""
import sys
import json
import glob
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path("E:/量化系统")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

OLD_ID = "20260623_004545"
NEW_ID = "phase1_qfields_holdertrade_v2_20260624"
LIVE = ROOT / "data/qlib_data"
BAK = ROOT / f"data/qlib_data.bak_{NEW_ID}"


def fbytes(prov, code, field):
    f = prov / "features" / code / (field + ".day.bin")
    return f.read_bytes() if f.exists() else None


# 1) byte-identity: re-bound datasets' fields unchanged (new-live == .bak)
assert BAK.is_dir(), f"backup missing: {BAK}"
print("=== re-bound field byte-identity (new-live vs .bak) ===")
checks = [("close", "copied"), ("n_income_sq_q0", "copied"), ("total_assets_q0", "copied"),
          ("forecast__np_q_yoy", "copied"), ("net_mf_amount", "copied"),
          ("report_rc__n_active_analysts", "copied"), ("q_roe", "re-mat"), ("arturn_days", "re-mat")]
ok = True
for field, kind in checks:
    res = []
    for code in ["000001_sz", "600519_sh"]:
        s = fbytes(LIVE, code, field)
        b = fbytes(BAK, code, field)
        res.append(s is not None and b is not None and s == b)
    allok = all(res)
    print(f"  {field:30s} ({kind}): identical={allok}")
    ok = ok and allok
if not ok:
    print("ABORT: re-bound fields not byte-identical new-live vs .bak")
    sys.exit(1)

# 2) append the append-only approval-log entry for the 高管 fields
log = ROOT / "config/field_registry/field_approval_log.jsonl"
entry = {
    "event": "promotion", "date": "2026-06-24", "dataset_id": "stk_holdertrade",
    "from_status": "approved", "to_status": "approved",
    "evidence_file": "config/field_registry/approvals/2026-06-24_stk_holdertrade_mgr_directional_to_approved.yaml",
    "fields_added": ["$holdertrade_mgr_in_vol", "$holdertrade_mgr_in_amount", "$holdertrade_mgr_in_ratio",
                     "$holdertrade_mgr_in_events", "$holdertrade_mgr_de_vol", "$holdertrade_mgr_de_amount",
                     "$holdertrade_mgr_de_ratio", "$holdertrade_mgr_de_events"],
    "pr": "report-rc-registration",
    "notes": ("高管(holder_type=G) DIRECTIONAL per-day aggregates (果仁 高管过去N日增持/减持 via Sum(...,N)). "
              "aggregate_directional_holdertrade; amount min_count=1 (all-unpriced=NaN, priced-event lower "
              "bound); vol/ratio/events complete; change_vol/change_ratio 0 negatives (data-audit canary). "
              "provider phase1_qfields_holdertrade_v2_20260624. GPT R1(amount false-zero)->R2 SHIP. "
              "Canary tests/data_infra/test_holdertrade_directional.py 6 passed."),
}
with open(log, "a", encoding="utf-8") as fh:
    fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
print("appended approval-log entry")

# 3) re-bind: targeted provider_build_id update (ONLY the binding value, not prose mentions)
n = 0
for f in glob.glob(str(ROOT / "config/field_registry/approvals/*.yaml")):
    t = Path(f).read_text(encoding="utf-8")
    new = t.replace(f'provider_build_id: "{OLD_ID}"', f'provider_build_id: "{NEW_ID}"')
    if new != t:
        Path(f).write_text(new, encoding="utf-8")
        n += 1
print(f"re-bound {n} approval YAMLs {OLD_ID} -> {NEW_ID}")

# 4) verify all bindings against the live manifest
from data_infra.approval_evidence import evaluate_approval_evidence_bindings  # noqa: E402
drifts = evaluate_approval_evidence_bindings()
n_drift = sum(1 for d in drifts if getattr(d, "drift", False))
print(f"approval bindings: {len(drifts)} scanned, {n_drift} drift")
for d in drifts:
    if getattr(d, "drift", False):
        print("  DRIFT:", getattr(d, "approval_id", d))
