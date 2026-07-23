# -*- coding: utf-8 -*-
"""Promote ONE recovered family from the C: staging area into the live E: raw store.

This is the last step of the 2026-07-13 raw-store recovery: the verified, consolidated tree under
`C:\\quant_recovery\\runs\\<run>\\staging_data\\consolidated\\<family>` becomes
`E:\\量化系统\\data\\<family>`.

The machinery already exists and is reviewed (`scripts/recovery_promotion.py`): write-ahead journal,
crash-resumable state machine, no-follow containment, hash verification of every file before and after
the swap, a quiescence sentinel that fails consumers closed while a promotion is in flight. This script
only BUILDS THE PLAN and calls the human-driven door (`promote_family`) — one family, attended.

DRY-RUN BY DEFAULT. `--execute` is the §13 mutation of the production raw store.

Usage:
    promote_recovered_family.py --run recover02 --family market/daily
    promote_recovered_family.py --run recover02 --family market/daily --execute
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = ROOT / "data"
RECOVERY_ROOT = Path(r"C:\quant_recovery\runs")

_spec = importlib.util.spec_from_file_location("recovery_promotion",
                                               ROOT / "scripts" / "recovery_promotion.py")
rp = importlib.util.module_from_spec(_spec)
sys.modules["recovery_promotion"] = rp
_spec.loader.exec_module(rp)


def _consolidated_dir(run: str, family: str) -> Path:
    return RECOVERY_ROOT / run / "staging_data" / "consolidated" / family


def _ledger_facts(run: str, family: str) -> dict:
    """What the RUN ITSELF attests about this family — read from the hash-chained ledger, not inferred
    from the files on disk. Promotion must agree with the run's own record."""
    led = RECOVERY_ROOT / run / "ledger" / "recovery_ledger.jsonl"
    rows = [json.loads(l) for l in led.read_text(encoding="utf-8").splitlines() if l.strip()]
    ev = [r for r in rows if r.get("event") == "family_consolidated" and r.get("family") == family]
    if not ev:
        raise SystemExit(f"REFUSED: run {run} has no family_consolidated event for {family!r} — "
                         f"consolidate it before promoting")
    outs = [o for lay in ev[-1].get("layouts", []) for o in lay.get("outputs", [])]
    return {"partitions": len(outs), "rows": sum(o.get("rows", 0) for o in outs),
            "paths": {o["path"] for o in outs}}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--family", required=True, help="e.g. market/daily")
    ap.add_argument("--execute", action="store_true",
                    help="§13: actually mutate the live raw store (default is a dry run)")
    a = ap.parse_args()

    staging = _consolidated_dir(a.run, a.family)
    if not staging.is_dir():
        raise SystemExit(f"REFUSED: no consolidated tree at {staging}")
    live = DATA_ROOT / a.family
    fam_key = a.family.replace("/", "_")
    incoming = DATA_ROOT / rp.INCOMING_AREA / a.run / a.family
    tomb = DATA_ROOT / rp.TOMBSTONE_AREA / a.run / a.family

    facts = _ledger_facts(a.run, a.family)
    print(f"run             : {a.run}")
    print(f"family          : {a.family}")
    print(f"staging (C:)    : {staging}")
    print(f"live target (E:): {live}   {'EXISTS' if live.exists() else 'ABSENT (destroyed 2026-07-13)'}")
    print(f"ledger attests  : {facts['partitions']:,} partitions / {facts['rows']:,} rows")

    print("\nfreezing the source manifest (hashing every file, no-follow) ...", flush=True)
    manifest = rp._manifest_from_dir(staging)
    total = sum(v["size"] for v in manifest.values())
    print(f"  manifest      : {len(manifest):,} files / {total / 1e9:.2f} GB")
    if len(manifest) != facts["partitions"]:
        raise SystemExit(f"REFUSED: staging holds {len(manifest)} files but the ledger attests "
                         f"{facts['partitions']} partitions — the tree does not match the run's record")

    if not a.execute:
        print("\nDRY RUN — nothing was touched. Re-run with --execute to promote.")
        print("On execute: the sentinel arms (consumers fail closed), the tree copies to "
              f"{rp.INCOMING_AREA}/, is re-hashed, then swaps into place; any existing live tree moves "
              f"to {rp.TOMBSTONE_AREA}/ rather than being deleted.")
        return 0

    plan = rp.FamilyPlan(family=a.family, staging_dir=staging, live_dir=live,
                         incoming_dir=incoming, tombstone_dir=tomb, manifest=manifest)
    journal = rp.PromotionJournal(DATA_ROOT / rp.INCOMING_AREA / f"promotion_journal_{a.run}.jsonl")
    coord = rp.PromotionCoordinator(a.run, DATA_ROOT, journal, [plan])
    print("\nPROMOTING (attended, one family) ...", flush=True)
    state = coord.promote_family(a.family)
    print(f"  state         : {state}")

    installed = rp._manifest_from_dir(live)
    same = installed == manifest
    print(f"  live tree     : {len(installed):,} files   manifest match: {same}")
    if not same:
        raise SystemExit("REFUSED: the installed tree does not match the frozen manifest")
    print(f"\nPROMOTED. The sentinel is deliberately LEFT ARMED — consumers stay fail-closed until QA "
          f"and the first verified backup; clearing it is an explicit human step.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
