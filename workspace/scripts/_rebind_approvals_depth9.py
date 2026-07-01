"""One-off: rebind field-registry approval YAMLs to the depth9_20260630 provider build after the depth-9
slot-depth publish. The m1 byte-audit proved q0..q4 (where every approved field lives) is byte-identical
old-live vs new-live, so the approvals carry over unchanged — only the binding pin needs refreshing
(calendar_policy_id frozen_20260227 is unchanged). Exact-string, byte-level (preserves EOLs), targeted, logged,
idempotent. Mirrors the 2026-06-24 phasec rebind precedent.

  python workspace/scripts/_rebind_approvals_depth9.py        # dry-run (lists files)
  python workspace/scripts/_rebind_approvals_depth9.py --go   # apply
"""
import glob
import os
import sys

OLD = b'provider_build_id: "phasec_profit_dedt_sq_20260624"'
NEW = b'provider_build_id: "depth9_20260630"'
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
    print(f"{'DRY-RUN: would rebind' if dry else 'REBOUND'} {len(changed)} approval YAMLs -> depth9_20260630")
    for c in changed:
        print("  ", c)
    if dry:
        print("re-run with --go to apply")
    return 0


if __name__ == "__main__":
    sys.exit(main())
