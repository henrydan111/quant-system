"""One-off: rebind field-registry approval YAMLs to depth9_20260630_sharecap_reanchor_20260701 after the
share-capital in-place value correction (GPT cross-review M1: rewriting APPROVED field values requires a new
provider identity, unlike the additive quality_stability/report_rc publishes). The correction touches ONLY the
bare $total_share/$float_share/$free_share bins (backup retained; audit in provider_patches.jsonl) — every
other approved field is byte-untouched, so the approvals carry over unchanged and only the binding pin needs
refreshing (calendar_policy_id frozen_20260227 is unchanged). Exact-string, byte-level (preserves EOLs),
targeted, logged, idempotent. Mirrors _rebind_approvals_depth9.py.

  python workspace/scripts/_rebind_approvals_sharecap.py        # dry-run (lists files)
  python workspace/scripts/_rebind_approvals_sharecap.py --go   # apply
"""
import glob
import os
import sys

OLD = b'provider_build_id: "depth9_20260630"'
NEW = b'provider_build_id: "depth9_20260630_sharecap_reanchor_20260701"'
APP = "config/field_registry/approvals"


def main() -> int:
    dry = "--go" not in sys.argv
    changed = []
    for p in sorted(glob.glob(os.path.join(APP, "*.yaml"))):
        with open(p, "rb") as f:
            data = f.read()
        if OLD in data:
            changed.append(os.path.basename(p))
            if not dry:
                with open(p, "wb") as f:
                    f.write(data.replace(OLD, NEW))
    print(f"{'DRY-RUN: would rebind' if dry else 'REBOUND'} {len(changed)} approval YAMLs -> depth9_20260630_sharecap_reanchor_20260701")
    for c in changed:
        print("  ", c)
    if dry:
        print("re-run with --go to apply")
    return 0


if __name__ == "__main__":
    sys.exit(main())
