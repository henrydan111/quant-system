# SCRIPT_STATUS: ACTIVE — 2026-07-13 junction-deletion incident: C:-staged raw-store recovery coordinator
"""Recovery coordinator for the 2026-07-13 raw-store deletion (see RAW_STORE_RECOVERY_PLAN.md v2).

Design rules (user directives, non-negotiable):
- ALL fetch/staging writes go to C: (`C:\\quant_recovery\\staging_data`) — a WRITE to any E:\\ path is
  structurally refused (`_assert_staging_path`). E: is read-only here (manifest + surviving reference).
- NO Tushare call happens in --inventory / --preflight / --plan. The fetch legs are DECLARED but their
  execution is refused until the user gives the explicit in-session §13 go-ahead (and even then requires
  --i-authorize-tushare-fetch). base_sleep has a hard floor of 1.5 (§6.1) — a leg below it refuses to load.
- Reconciliation baseline = data/qlib_builds/thaw_step1_20260703c/manifest.json (27 datasets,
  78,948,729 rows) — NOT data_tracker approximations.
- Reference/universe SURVIVORS are copied E:->C: so staged fetchers have calendar/stock_basic; the live
  copies are never re-fetched or overwritten (init_market_data's reference leg is banned).

Usage (each mode is safe / network-free):
    venv/Scripts/python.exe scripts/raw_recovery_coordinator.py --inventory
    venv/Scripts/python.exe scripts/raw_recovery_coordinator.py --preflight
    venv/Scripts/python.exe scripts/raw_recovery_coordinator.py --plan
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

E_ROOT = Path(r"E:\量化系统")
E_DATA = E_ROOT / "data"
MANIFEST = E_DATA / "qlib_builds" / "thaw_step1_20260703c" / "manifest.json"
STAGING_ROOT = Path(r"C:\quant_recovery")
STAGING_DATA = STAGING_ROOT / "staging_data"
LEDGER = STAGING_ROOT / "ledger" / "recovery_ledger.jsonl"
REPORTS = STAGING_ROOT / "reports"

BASE_SLEEP_FLOOR = 1.5  # §6.1 — hard floor; legs below this refuse to load
MIN_STAGING_FREE_GB = 200

# survivors (copied E:->C: read-only; NEVER re-fetched — init_market_data's reference leg is banned).
# Includes the HAND-CURATED irreplaceable files (repair overrides / known-empty-dates) the builder needs.
# NOTE: suspension_ranges.parquet was NOT in reference/ — it lived in the deleted tree and is DERIVED
# (rebuild after the suspend_d refetch via fetch_suspend_d_historical --ranges-only).
SURVIVOR_FILES = [
    "reference/trade_cal.parquet", "reference/stock_basic.parquet", "reference/stock_st_daily.parquet",
    "reference/namechange.parquet", "reference/daily_price_repair_overrides.csv",
    "reference/moneyflow_known_empty_dates.txt", "reference/northbound_nonconnect_days.txt",
]
SURVIVOR_DIRS = ["universe/index_weights", "universe/industry_sw2021", "reference/ths_concept"]

# non-DATASET_SPECS stores the v1 plan missed — must be explicit recovery targets
EXTRA_TARGETS = [
    ("suspend_d_per_date", "market/suspend_d", "per-date timing-preserving store (canonical write_suspend_d)"),
    ("broker_recommend", "analyst/broker_recommend", "金股 monthly files — production TUD for the broker work"),
    ("bucket_a_siblings", "fundamentals+corporate", "express/disclosure_date/fina_mainbz/fina_audit/repurchase/pledge_stat/top10_floatholders"),
    ("indicator_archives", "fundamentals/indicators (staged history)", "refresh_indicator_history staged archives"),
    ("margin_detail", "market/margin_detail", "margin detail (repayment fields quarantined in registry, raw still needed)"),
    ("suspension_ranges", "derived from suspend_d", "rebuild AFTER suspend_d refetch: fetch_suspend_d_historical --ranges-only"),
]


@dataclass(frozen=True)
class FetchLeg:
    """A declared, NOT-yet-executable fetch unit. Execution is §13-gated."""
    leg_id: str
    datasets: tuple
    driver: str            # script/entry the leg drives, with staging data-root
    base_sleep: float = 1.5
    notes: str = ""

    def __post_init__(self):
        if self.base_sleep < BASE_SLEEP_FLOOR:
            raise ValueError(f"leg {self.leg_id}: base_sleep {self.base_sleep} < §6.1 floor {BASE_SLEEP_FLOOR}")


FETCH_LEGS = [
    FetchLeg("L1_market_daily", ("daily", "index_daily"),
             "init_market_data market leg ONLY (reference leg banned), data-root=staging, base_sleep=1.5"),
    FetchLeg("L2_fundamentals", ("income", "income_quarterly", "balancesheet", "cashflow",
                                 "cashflow_quarterly", "forecast", "indicators"),
             "init_fundamentals_data --data-root staging --start_year 2008 (+VIP quarterly combines)"),
    FetchLeg("L3_factor_daily", ("moneyflow", "stk_limit", "margin", "margin_detail", "northbound",
                                 "dividends", "holder_number"),
             "init_factor_data with staging data-root; per-date ledger rows (its exit-0-past-failures is overridden by ledger accounting)"),
    FetchLeg("L4_suspend_d", ("suspend_d_year", "suspend_d_per_date"),
             "fetch_suspend_d_historical --data-root staging + per-date write_suspend_d leg"),
    FetchLeg("L5_alpha_endpoints", ("top_list", "top_inst", "block_trade", "stk_holdertrade", "cyq_perf"),
             "fetch_new_alpha_endpoints with staging data-root"),
    FetchLeg("L6_bucket_a", ("report_rc", "express", "disclosure_date", "fina_mainbz", "fina_audit",
                             "repurchase", "pledge_stat", "top10_floatholders"),
             "scripts/fetch_bucket_a.py with staging data-root (report_rc deep history + 7 siblings)"),
    FetchLeg("L7_broker_recommend", ("broker_recommend",),
             "NEW leg: monthly broker_recommend_{YYYYMM} per data_dictionary spec"),
    FetchLeg("L8_indicator_archives", ("indicators_history",),
             "refresh_indicator_history --data-root staging (staged archives)"),
    FetchLeg("L9_tail_catchup", ("all daily-partitioned",),
             "catchup drivers 20260702..last-complete-session into staging (post-manifest tail)"),
]


def _assert_staging_path(p: Path) -> Path:
    """Structural guard: every WRITE lands under C:\\quant_recovery — never on E:."""
    rp = Path(p).resolve()
    if str(rp).upper().startswith(str(E_ROOT.resolve()).upper()) or str(rp)[:2].upper() == "E:":
        raise RuntimeError(f"REFUSED: write target {rp} is on E: (E: is read-only during recovery)")
    if not str(rp).upper().startswith(str(STAGING_ROOT).upper()):
        raise RuntimeError(f"REFUSED: write target {rp} is outside {STAGING_ROOT}")
    return rp


def _write_json(path: Path, obj) -> None:
    path = _assert_staging_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def _ledger_append(row: dict) -> None:
    p = _assert_staging_path(LEDGER)
    p.parent.mkdir(parents=True, exist_ok=True)
    row = {"at": datetime.now().isoformat(timespec="seconds"), **row}
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_baseline() -> dict:
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return m["profiled_datasets"]


def cmd_inventory() -> int:
    """Gap report: manifest baseline vs what exists on the live store TODAY. Network-free; E: read-only."""
    base = load_baseline()
    sys.path.insert(0, str(E_ROOT / "src"))
    from data_infra.pit_backend import DATASET_SPECS
    rows, lost_rows = [], 0
    for name, prof in sorted(base.items()):
        spec = DATASET_SPECS.get(name)
        pat = getattr(spec, "raw_pattern", "") if spec else ""
        root = E_DATA / pat.split("/")[0] if pat else None
        import glob as _g
        live = len(_g.glob(str(E_DATA / pat), recursive=True)) if pat else 0
        status = "SURVIVED" if live >= prof.get("file_count", 0) and live > 0 else (
            "PARTIAL" if live > 0 else "LOST")
        if status != "SURVIVED":
            lost_rows += prof.get("row_count", 0)
        rows.append({"dataset": name, "baseline_files": prof.get("file_count"),
                     "baseline_rows": prof.get("row_count"), "live_files": live, "status": status,
                     "date_range": [prof.get("date_min"), prof.get("date_max")]})
    inv = {"generated": datetime.now().isoformat(timespec="seconds"),
           "baseline_manifest": str(MANIFEST), "baseline_total_rows": sum(p.get("row_count", 0) for p in base.values()),
           "lost_rows_estimate": lost_rows, "datasets": rows,
           "extra_targets_not_in_manifest": [{"id": a, "path": b, "why": c} for a, b, c in EXTRA_TARGETS],
           "post_manifest_tail": "20260702..last-complete-session (reconciled via calendar, not manifest)"}
    _write_json(REPORTS / "inventory.json", inv)
    lost = [r for r in rows if r["status"] == "LOST"]
    print(f"baseline: {inv['baseline_total_rows']:,} rows / 27 datasets (manifest {MANIFEST.name})")
    print(f"LOST: {len(lost)} datasets, ~{lost_rows:,} rows + {len(EXTRA_TARGETS)} extra stores")
    print(f"SURVIVED: {[r['dataset'] for r in rows if r['status'] == 'SURVIVED']}")
    print(f"report -> {REPORTS / 'inventory.json'}")
    return 0


def cmd_preflight() -> int:
    """Prepare C: staging + copy survivors E:->C: (E: reads only). Network-free."""
    free_gb = shutil.disk_usage(str(STAGING_ROOT.drive + "\\"))[2] // 2**30
    if free_gb < MIN_STAGING_FREE_GB:
        print(f"FAIL: C: free {free_gb}GB < {MIN_STAGING_FREE_GB}GB")
        return 2
    for leg in FETCH_LEGS:  # validates every leg's base_sleep >= floor at load
        assert leg.base_sleep >= BASE_SLEEP_FLOOR
    copied = []
    for rel in SURVIVOR_FILES:
        src, dst = E_DATA / rel, STAGING_DATA / rel
        if not src.exists():
            print(f"FAIL: survivor missing on live store: {src}")
            return 2
        _assert_staging_path(dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append((rel, dst.stat().st_size))
    for rel in SURVIVOR_DIRS:
        src, dst = E_DATA / rel, STAGING_DATA / rel
        if not src.exists():
            print(f"FAIL: survivor dir missing: {src}")
            return 2
        _assert_staging_path(dst)
        shutil.copytree(src, dst, dirs_exist_ok=True)
        copied.append((rel, sum(f.stat().st_size for f in dst.rglob('*') if f.is_file())))
    # verify the two load-bearing survivors' row counts vs the manifest baseline
    import pandas as pd
    base = load_baseline()
    for name, rel in (("trade_cal", "reference/trade_cal.parquet"), ("stock_basic", "reference/stock_basic.parquet")):
        n = len(pd.read_parquet(STAGING_DATA / rel))
        want = base[name]["row_count"]
        if n < want:  # calendar/stock_basic may have grown since 07-03; shrinking = corruption
            print(f"FAIL: staged {name} rows {n} < baseline {want}")
            return 2
    _ledger_append({"event": "preflight_ok", "c_free_gb": free_gb,
                    "survivors_copied": [c[0] for c in copied]})
    print(f"preflight OK: C: free {free_gb}GB; staging at {STAGING_DATA}; "
          f"{len(copied)} survivor sets copied + row-verified; {len(FETCH_LEGS)} legs validated (base_sleep>={BASE_SLEEP_FLOOR})")
    return 0


def cmd_plan() -> int:
    print(f"fetch legs (ALL REFUSED until the user's §13 go-ahead; serial, one fetcher, base_sleep>={BASE_SLEEP_FLOOR}):")
    for leg in FETCH_LEGS:
        print(f"  {leg.leg_id:<22} {', '.join(leg.datasets)}")
        print(f"      -> {leg.driver}")
    print("\npromotion (later, separately gated): one atomic C:->E: pass per family after reconciliation passes.")
    return 0


def cmd_fetch(_args) -> int:
    print("REFUSED: fetch legs are not enabled in this build of the coordinator. The user must first "
          "review the plan + preflight output and give the explicit §13 go-ahead in session; the legs "
          "are then wired to the drivers with staging data-roots (see RAW_STORE_RECOVERY_PLAN.md §6).",
          file=sys.stderr)
    return 3


def main() -> int:
    ap = argparse.ArgumentParser(description="C:-staged raw-store recovery coordinator (fetch §13-gated)")
    ap.add_argument("--inventory", action="store_true")
    ap.add_argument("--preflight", action="store_true")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--fetch", action="store_true", help="REFUSED without user §13 go-ahead")
    ap.add_argument("--i-authorize-tushare-fetch", action="store_true")
    a = ap.parse_args()
    if a.inventory:
        return cmd_inventory()
    if a.preflight:
        return cmd_preflight()
    if a.plan:
        return cmd_plan()
    if a.fetch:
        return cmd_fetch(a)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
