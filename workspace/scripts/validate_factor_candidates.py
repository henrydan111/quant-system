# ──────────────────────────────────────────────────────────────────────
# PR 7 of 2026-05-26 freeze plan — SCRIPT_STATUS header block.
# script_status: historical_investigation
# formal_research_allowed: false
# deployment_target: joinquant_attribution_only
# requires_provider_manifest: false
# requires_preload_strict: false
# pr2_audit_class: C
# notes: |
#   Read-only validator for factor-candidate CSVs. For every expression it
#   (1) checks every $field token against the RAW materialized bin stems
#   (not collapsed base stems — this is what catches non-existent PIT
#   variants like $cash_div_q0), (2) runs the project's PIT-safety parser,
#   (3) resolves field-registry status. Prints a per-row report and a
#   summary; exits non-zero if any row fails field-existence or PIT safety.
#   No mutation of any artifact.
# ──────────────────────────────────────────────────────────────────────
"""Validate factor-candidate CSV rows against the live backend + registry.

Usage:
    venv/Scripts/python.exe workspace/scripts/validate_factor_candidates.py \
        workspace/research/factor_expansion/factor_candidates.csv \
        Knowledge/factor_expansion_gpt_review_new_candidates.csv
"""

from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data_infra.field_registry import extract_qlib_fields, load_field_registry
from tests.alpha_research.test_factor_library_pit_safety import (
    find_unwrapped_field_references,
)

FEATURES_DIR = PROJECT_ROOT / "data" / "qlib_data" / "features"
FORMAL_STAGE = "formal_validation"


def load_raw_materialized_stems() -> set[str]:
    """Return the set of RAW materialized bin stems (incl. PIT variants).

    This is the ground-truth token set an expression's $field references must
    be a subset of. Picks the instrument dir with the most bins.
    """
    import re

    best_dir, best = None, -1
    for child in FEATURES_DIR.iterdir():
        if child.is_dir():
            n = sum(1 for _ in child.glob("*.bin"))
            if n > best:
                best, best_dir = n, child
    if best_dir is None:
        raise FileNotFoundError(f"No instrument dirs under {FEATURES_DIR}")

    stems: set[str] = set()
    for binf in best_dir.glob("*.bin"):
        name = binf.name
        if name.endswith(".day.bin"):
            name = name[: -len(".day.bin")]
        elif name.endswith(".bin"):
            name = name[: -len(".bin")]
        name = re.sub(r"\.[0-9]+$", "", name)
        stems.add(name)
    return stems


def validate_csv(path: Path, raw_stems: set[str], registry) -> list[dict]:
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    results = []
    for r in rows:
        expr = r["qlib_expression"]
        tokens = [t[1:] for t in extract_qlib_fields(expr)]  # strip leading $
        missing = sorted(t for t in tokens if t not in raw_stems)
        unwrapped = find_unwrapped_field_references(expr)
        # registry status (worst-case across fields)
        statuses, eligible = set(), True
        for tok in extract_qlib_fields(expr):
            res = registry.resolve_field(tok, FORMAL_STAGE)
            statuses.add(res.status_id or "unknown_field")
            if not res.allowed:
                eligible = False
        results.append({
            "name": r["name"],
            "field_exists": not missing,
            "missing_fields": missing,
            "pit_safe": not unwrapped,
            "unwrapped": unwrapped,
            "registry_status": (
                "unknown_field" if "unknown_field" in statuses
                else "quarantine" if "quarantine" in statuses
                else "pending_review" if "pending_review" in statuses
                else "approved" if statuses == {"approved"}
                else ";".join(sorted(statuses))
            ),
            "formal_eligible": eligible,
            "claimed_status": r.get("registry_status", ""),
        })
    return results


def main(argv: list[str]) -> int:
    if not argv:
        argv = [
            str(PROJECT_ROOT / "workspace/research/factor_expansion/factor_candidates.csv"),
            str(PROJECT_ROOT / "Knowledge/factor_expansion_gpt_review_new_candidates.csv"),
        ]
    raw_stems = load_raw_materialized_stems()
    print(f"Loaded {len(raw_stems)} raw materialized stems from provider.\n")
    registry = load_field_registry(
        PROJECT_ROOT / "config" / "field_registry" / "field_status.yaml"
    )

    any_fail = False
    for csv_path in argv:
        p = Path(csv_path)
        print(f"=== {p.name} ===")
        results = validate_csv(p, raw_stems, registry)
        fail_exist = [r for r in results if not r["field_exists"]]
        fail_pit = [r for r in results if not r["pit_safe"]]
        status_mismatch = [
            r for r in results
            if r["claimed_status"] and r["claimed_status"] != r["registry_status"]
        ]
        print(f"  rows: {len(results)}")
        print(f"  field_exists FAIL: {len(fail_exist)}")
        for r in fail_exist:
            print(f"    - {r['name']}: missing {r['missing_fields']}")
        print(f"  pit_safe FAIL: {len(fail_pit)}")
        for r in fail_pit:
            print(f"    - {r['name']}: unwrapped {r['unwrapped']}")
        if status_mismatch:
            print(f"  status mismatch (claimed != resolved): {len(status_mismatch)}")
            for r in status_mismatch:
                print(f"    - {r['name']}: claimed={r['claimed_status']} resolved={r['registry_status']}")
        print(f"  resolved status mix: {dict(Counter(r['registry_status'] for r in results))}")
        print(f"  formal-eligible: {sum(1 for r in results if r['formal_eligible'])}/{len(results)}")
        print()
        if fail_exist or fail_pit:
            any_fail = True

    print("RESULT:", "FAIL (see above)" if any_fail else "PASS (all rows field-exist + PIT-safe)")
    return 1 if any_fail else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
