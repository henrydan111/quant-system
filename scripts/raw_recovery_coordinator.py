# SCRIPT_STATUS: ACTIVE — 2026-07-13 junction-deletion incident: C:-staged raw-store recovery coordinator (v2)
"""Recovery coordinator v2 (post GPT recovery-review REWORK — see RAW_STORE_RECOVERY_PLAN.md v3).

Hard rules (user directives + GPT B1/B2/B4/M1/M2/M3):
- Run-scoped immutable staging: C:\\quant_recovery\\runs\\<run_id>\\{staging_data,ledger,reports,logs,
  evidence}. A new run REFUSES an existing run_id; --resume re-opens one only with its existing ledger.
- Containment: every coordinator write passes `RecoveryPaths.assert_write` — `Path.relative_to` the run
  root (no string-prefix bypass) + REPARSE-POINT rejection over the whole ancestry (junction/symlink
  anywhere above the target refuses). E: is read-only here. The DRIVEN fetchers are NOT trusted for
  containment: fetch legs stay refused until each has an executable ADAPTER with explicit injected
  paths (no defaults), reviewed + integration-tested with E: write-denied (see ADAPTER_SPECS gaps).
- §6.1 throttle: the REAL floor is central (tushare_lock.MIN_BASE_SLEEP = 1.5, enforced inside
  spaced_call + TushareFetcher) — the leg metadata check is only a redundant label now.
- Doc gate (M3): no leg is plannable unless every endpoint it touches has a COMPLETE, human-reviewed
  entry in workspace/configs/recovery_endpoint_contracts.yaml (doc path+sha256, fields, limits,
  cadence, PIT semantics, reviewed_by/at). Missing/incomplete contract => leg BLOCKED.
- Baseline: data/qlib_builds/thaw_step1_20260703c/manifest.json, sha256-PINNED. Inventory `status` is a
  COARSE PRESENCE SCAN (file-count only), never restoration proof — restoration proof is the per-request
  ledger + profiler comparison (plan v3 §4).
- NO Tushare call in any current mode. --fetch refuses pending adapters + the user's §13 go-ahead.

Usage:
    venv/Scripts/python.exe scripts/raw_recovery_coordinator.py --new-run 20260713a --inventory
    venv/Scripts/python.exe scripts/raw_recovery_coordinator.py --run 20260713a --preflight
    venv/Scripts/python.exe scripts/raw_recovery_coordinator.py --run 20260713a --plan
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

E_ROOT = Path(r"E:\量化系统")
E_DATA = E_ROOT / "data"
MANIFEST = E_DATA / "qlib_builds" / "thaw_step1_20260703c" / "manifest.json"
MANIFEST_SHA256 = "fbc4aec076fda8ab200cc09ef2d1fff07d28ae4491b8020123faf179e467627f"  # pinned baseline
LIVE_PROVIDER_SOURCE_COMMIT = "f93cb9d20ebd4d68f15d31c34caac78b2da17be2"  # builder pin for the oracle
RECOVERY_ROOT = Path(r"C:\quant_recovery") / "runs"
CONTRACTS_YAML = E_ROOT / "workspace" / "configs" / "recovery_endpoint_contracts.yaml"
MIN_STAGING_FREE_GB = 200

# ── survivors: the WHOLE intact trees are copied (allowlists dropped stragglers — GPT M1) ──
SURVIVOR_TREES = ["reference", "universe"]
# incident evidence snapshotted to the run's evidence/ dir (read-only copies, hashed)
EVIDENCE_GLOBS = [
    "data/raw_cache/**/*", "workspace/outputs/calendar_unfreeze/*.json",
    "logs/update_daily_data_202607.log", "logs/catchup_daily_unfreeze.log",
    "logs/catchup_fundamentals_unfreeze.log",
]

# targets that are NOT refetchable — recorded as lost evidence, never claimed "restored" (GPT M1)
IRRECOVERABLE = [
    ("indicator_history_archives", "staged update_flag revision archives — original capture times unreproducible"),
    ("report_rc_revision_baseline", "report_rc.revision_baseline.parquet — pre-incident retrograde baseline gone; "
                                    "rebuilt fresh ONLY after exact live-provider parity (plan v3 §5)"),
    ("report_rc_first_seen", "raw_fetch_ts first-seen stamps for 2026-07-01..incident rows — reconstruct from the "
                             "July catch-up state/logs where provable, else recovery-time floor or quarantine"),
]


@dataclass(frozen=True)
class AdapterSpec:
    """A fetch unit. `gaps` = what must be built/changed BEFORE this leg is executable — free-text driver
    strings are gone (GPT B2); a leg becomes wirable only when its adapter exists, its gaps are closed,
    and its endpoint contracts are reviewed."""
    leg_id: str
    datasets: tuple
    endpoints: tuple          # tushare endpoint names -> must have reviewed contracts (M3)
    driver: str               # the code the adapter wraps (class methods, NOT main())
    gaps: tuple               # verified blockers before wiring
    partition: str            # query partition + cadence for tail semantics


ADAPTER_SPECS = [
    AdapterSpec("L1_market_daily", ("daily", "index_daily"), ("daily", "daily_basic", "adj_factor", "index_daily"),
                "MarketDataInitializer methods DIRECTLY (download_daily/index) — NOT main()",
                ("main() unconditionally calls download_reference_data() (init_market_data.py:249) — adapter must "
                 "bypass main and inject staging paths; import-time E: log handler must be removed/redirected",),
                "per trade_date, trading sessions"),
    AdapterSpec("L2_statements_core", ("income", "balancesheet"), ("income_vip", "balancesheet_vip"),
                "FundamentalsInitializer statement methods only",
                ("run() unconditionally refetches industry + index_weights (survivors!) — adapter must skip; "
                 "E: log handler",), "per report period (ann_date-window tail)"),
    AdapterSpec("L2b_statements_rest", ("cashflow", "income_quarterly", "cashflow_quarterly", "forecast", "indicators"),
                ("cashflow_vip", "income_vip", "cashflow_vip", "forecast_vip", "fina_indicator_vip"),
                "scripts/fetch_quarterly_statements.py (EXISTS — v1 matrix omitted it) + forecast/indicator legs",
                ("hard-coded E: paths; catches per-stock failures and exits 0 — ledger accounting must gate",),
                "per period × report_type; forecast per ann_date window"),
    AdapterSpec("L3_factor_daily", ("moneyflow", "stk_limit", "margin", "northbound", "dividends", "holder_number"),
                ("moneyflow", "stk_limit", "margin_detail", "hk_hold", "dividend", "stk_holdernumber"),
                "FactorDataInitializer methods; margin_detail lands in market/margin (SAME dataset as manifest "
                "'margin' — v1 wrongly listed it as a separate store)",
                ("continues past failed dates and exits 0 (init_factor_data) — per-date ledger rows gate; E: logs",),
                "per trade_date; dividends/holder per ann_date window"),
    AdapterSpec("L4_suspend", ("suspend_d_year", "suspend_d_per_date", "suspension_ranges(derived)"),
                ("suspend_d",),
                "fetch_suspend_d_historical (year files: market/suspension/suspension_YYYY.parquet) + per-date "
                "write_suspend_d store + --ranges-only derived rebuild LAST",
                ("SUSPENSION_DIR hard-codes E: (fetch_suspend_d_historical.py:61)",),
                "per year + per trade_date"),
    AdapterSpec("L5_alpha_endpoints", ("top_list", "top_inst", "block_trade", "stk_holdertrade", "cyq_perf"),
                ("top_list", "top_inst", "block_trade", "stk_holdertrade", "cyq_perf"),
                "fetch_new_alpha_endpoints", ("reference/output roots hard-coded to E: (line 51)",),
                "per trade_date (cyq_perf 2018+)"),
    AdapterSpec("L6_bucket_a", ("report_rc", "express", "disclosure_date", "fina_mainbz", "fina_audit",
                                "repurchase", "pledge_stat", "top10_floatholders"),
                ("report_rc", "express", "disclosure_date", "fina_mainbz", "fina_audit", "repurchase",
                 "pledge_stat", "top10_floatholders"),
                "scripts/fetch_bucket_a.py",
                ("DATA and LOGS hard-code E: (fetch_bucket_a.py:44); report_rc rows need raw_fetch_ts + the "
                 "first-seen policy (plan v3 §5) BEFORE any ledger rebuild",),
                "report_rc month-chunked; siblings per period/window"),
    AdapterSpec("L7_broker_recommend", ("broker_recommend",), ("broker_recommend",),
                "scripts/fetch_broker_recommend_historical.py (EXISTS — v1 claimed it didn't)",
                ("hard-codes E: (line 48)",), "per month"),
    AdapterSpec("L8_indicator_current", ("indicators(current snapshot)",), ("fina_indicator_vip",),
                "refresh_indicator_history --data-root <staging>",
                ("logs/reports still land on E: even with --data-root C: (refresh_indicator_history.py:18, "
                 "indicator_history_refresh.py:137); HISTORICAL archives are IRRECOVERABLE (evidence, not refetch)",),
                "per period"),
    AdapterSpec("L9_tail", ("all daily-partitioned + ann_date families",), ("daily", "moneyflow", "stk_limit"),
                "NEW adapter (existing catch-up drivers cannot target C: and call bare StorageManager())",
                ("catchup_daily_range/catchup_fundamentals_range hard-code E: logs/state/data "
                 "(catchup_fundamentals_range.py:141)",),
                "tail is NOT uniformly trading-session based: announcements = calendar-day ann_date windows; "
                "broker monthly; report_rc needs its TTL halo (GPT answer 3)"),
]


class RecoveryPaths:
    """Injected path authority for THIS run (GPT B1/M2). All writes must pass assert_write: strict
    relative_to containment + reparse-point rejection over the full ancestry."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.root = (RECOVERY_ROOT / run_id).resolve()
        self.staging_data = self.root / "staging_data"
        self.ledger = self.root / "ledger" / "recovery_ledger.jsonl"
        self.reports = self.root / "reports"
        self.logs = self.root / "logs"
        self.evidence = self.root / "evidence"

    @staticmethod
    def _reject_reparse(p: Path) -> None:
        for anc in [p] + list(p.parents):
            if not anc.exists():
                continue
            if anc.is_symlink() or (hasattr(anc, "is_junction") and anc.is_junction()):
                raise RuntimeError(f"REFUSED: reparse point in path ancestry: {anc}")

    def assert_write(self, p: Path) -> Path:
        rp = Path(p).resolve()
        try:
            rp.relative_to(self.root)  # strict containment — no string-prefix bypass (quant_recovery_evil)
        except ValueError:
            raise RuntimeError(f"REFUSED: write target {rp} outside run root {self.root}")
        if str(rp).upper().startswith("E:"):
            raise RuntimeError(f"REFUSED: {rp} is on E: (read-only during recovery)")
        self._reject_reparse(rp.parent)
        return rp

    def write_json(self, path: Path, obj) -> None:
        path = self.assert_write(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, ensure_ascii=False, indent=1)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)

    def ledger_append(self, row: dict) -> None:
        """One row per API request / partition / lifecycle event (GPT B4 schema). fsync'd append under a
        run-local file lock."""
        from filelock import FileLock
        p = self.assert_write(self.ledger)
        p.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(str(p) + ".lock"):
            with open(p, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"at": datetime.now().isoformat(timespec="seconds"), **row},
                                    ensure_ascii=False) + "\n")
                fh.flush()
                os.fsync(fh.fileno())


# ledger row contract (GPT B4) — every fetch adapter must emit rows with exactly these fields:
LEDGER_REQUEST_FIELDS = (
    "leg_id", "dataset", "endpoint", "query_params", "page_count", "raw_row_count",
    "confirmed_empty",        # True ONLY from a positive completeness proof, never from a failure
    "schema_fingerprint",     # sorted col:dtype hash
    "key_stats",              # natural-key null count + duplicate-group count
    "output_path", "output_sha256", "first_fetch_ts", "exception", "doc_sha256", "state",
)  # state: fetched | verified | failed | confirmed_empty


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_baseline() -> dict:
    got = sha256_file(MANIFEST)
    if got != MANIFEST_SHA256:
        raise RuntimeError(f"baseline manifest sha256 {got} != pinned {MANIFEST_SHA256} — refusing")
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["profiled_datasets"]


def load_contracts() -> dict:
    import yaml
    if not CONTRACTS_YAML.exists():
        return {}
    return yaml.safe_load(CONTRACTS_YAML.read_text(encoding="utf-8")) or {}


def contract_complete(c: dict) -> bool:
    need = ("doc_path", "doc_sha256", "fields_reviewed", "rate_limit", "cadence", "pit_semantics",
            "reviewed_by", "reviewed_at")
    return bool(c) and all(c.get(k) for k in need)


def open_run(run_id: str, *, new: bool) -> RecoveryPaths:
    rp = RecoveryPaths(run_id)
    if new:
        if rp.root.exists():
            raise SystemExit(f"REFUSED: run {run_id} already exists — immutable runs; use --run to resume")
        rp.root.mkdir(parents=True)
        rp.ledger_append({"event": "run_created", "run_id": run_id,
                          "baseline_manifest_sha256": MANIFEST_SHA256,
                          "live_provider_source_commit": LIVE_PROVIDER_SOURCE_COMMIT})
    elif not rp.root.exists():
        raise SystemExit(f"REFUSED: run {run_id} does not exist; create with --new-run")
    return rp


def cmd_inventory(rp: RecoveryPaths) -> int:
    """COARSE PRESENCE SCAN (file-count only — NOT restoration proof; GPT minor 1). Network-free."""
    base = load_baseline()
    sys.path.insert(0, str(E_ROOT / "src"))
    from data_infra.pit_backend import DATASET_SPECS
    import glob as _g
    rows, lost_rows = [], 0
    for name, prof in sorted(base.items()):
        spec = DATASET_SPECS.get(name)
        pat = getattr(spec, "raw_pattern", "") if spec else ""
        live = len(_g.glob(str(E_DATA / pat), recursive=True)) if pat else 0
        status = "present_count_scan" if (live and live >= prof.get("file_count", 0)) else (
            "partial_count_scan" if live else "lost")
        if status != "present_count_scan":
            lost_rows += prof.get("row_count", 0)
        rows.append({"dataset": name, "baseline_files": prof.get("file_count"),
                     "baseline_rows": prof.get("row_count"), "live_files": live, "presence": status})
    inv = {
        "note": "presence is a COARSE COUNT SCAN; restoration proof = per-request ledger + profiler comparison",
        "generated": datetime.now().isoformat(timespec="seconds"),
        "baseline": {"manifest": str(MANIFEST), "sha256": MANIFEST_SHA256,
                     "total_rows": sum(p.get("row_count", 0) for p in base.values())},
        "lost_rows_estimate": lost_rows, "datasets": rows,
        "extra_targets": [
            {"id": "suspend_d_per_date", "class": "refetchable", "path": "market/suspend_d/<yr>/"},
            {"id": "suspension_yearly", "class": "refetchable", "path": "market/suspension/suspension_YYYY.parquet"},
            {"id": "suspension_ranges", "class": "derived", "note": "rebuild via --ranges-only AFTER suspend_d"},
            {"id": "broker_recommend", "class": "refetchable", "path": "analyst/broker_recommend/"},
            {"id": "bucket_a_siblings", "class": "refetchable_new_generation",
             "note": "raw-only data gets a NEW raw-generation identity — never claimed byte-equivalent"},
            {"id": "balancesheet_quarterly", "class": "known_empty",
             "note": "intentionally empty; must REMAIN so unless a separately-reviewed vendor change"},
        ],
        "irrecoverable_evidence": [{"id": a, "why": b} for a, b in IRRECOVERABLE],
        "tail": "20260702..last-complete-session; NOT uniformly session-based (ann_date calendar windows, "
                "monthly broker, report_rc TTL halo)",
    }
    rp.write_json(rp.reports / "inventory.json", inv)
    print(f"baseline {inv['baseline']['total_rows']:,} rows; lost-estimate {lost_rows:,}; "
          f"{len([r for r in rows if r['presence'] == 'lost'])} datasets lost; report -> {rp.reports / 'inventory.json'}")
    return 0


def cmd_preflight(rp: RecoveryPaths) -> int:
    """Copy+hash the WHOLE survivor trees & evidence snapshot into the run (E: reads only)."""
    free_gb = shutil.disk_usage(str(RECOVERY_ROOT.drive + "\\"))[2] // 2**30
    if free_gb < MIN_STAGING_FREE_GB:
        print(f"FAIL: C: free {free_gb}GB < {MIN_STAGING_FREE_GB}GB")
        return 2
    manifest_rows = []
    for tree in SURVIVOR_TREES:  # whole trees, not allowlists (GPT M1)
        src_root = E_DATA / tree
        for src in sorted(src_root.rglob("*")):
            if not src.is_file():
                continue
            rel = src.relative_to(E_DATA)
            dst = rp.assert_write(rp.staging_data / rel)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            manifest_rows.append({"path": str(rel).replace("\\", "/"), "sha256": sha256_file(dst),
                                  "size": dst.stat().st_size})
    import glob as _g
    ev_rows = []
    for pat in EVIDENCE_GLOBS:
        for f in _g.glob(str(E_ROOT / pat), recursive=True):
            fp = Path(f)
            if not fp.is_file():
                continue
            rel = fp.relative_to(E_ROOT)
            dst = rp.assert_write(rp.evidence / rel)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(fp, dst)
            ev_rows.append({"path": str(rel).replace("\\", "/"), "sha256": sha256_file(dst)})
    # row-verify the two load-bearing survivors vs baseline (they may have GROWN since 07-03, never shrunk)
    import pandas as pd
    base = load_baseline()
    for name, rel in (("trade_cal", "reference/trade_cal.parquet"), ("stock_basic", "reference/stock_basic.parquet")):
        n = len(pd.read_parquet(rp.staging_data / rel))
        if n < base[name]["row_count"]:
            print(f"FAIL: staged {name} rows {n} < baseline {base[name]['row_count']}")
            return 2
    rp.write_json(rp.reports / "survivor_manifest.json", {"files": manifest_rows, "evidence": ev_rows})
    rp.ledger_append({"event": "preflight_ok", "c_free_gb": free_gb,
                      "survivor_files": len(manifest_rows), "evidence_files": len(ev_rows)})
    print(f"preflight OK: run {rp.run_id}; C: free {free_gb}GB; survivors {len(manifest_rows)} files "
          f"(whole reference/+universe/ trees, hashed); evidence {len(ev_rows)} files")
    return 0


def cmd_plan(rp: RecoveryPaths) -> int:
    contracts = load_contracts()
    print(f"adapter legs (fetch REFUSED until: adapter built + gaps closed + contracts reviewed + user §13 go-ahead)")
    blocked = 0
    for a in ADAPTER_SPECS:
        missing = [e for e in a.endpoints if not contract_complete(contracts.get(e, {}))]
        state = "BLOCKED(doc-gate)" if missing else "contract-ready (adapter still required)"
        if missing:
            blocked += 1
        print(f"  {a.leg_id:<22} {state}")
        print(f"      datasets: {', '.join(a.datasets)}")
        print(f"      driver:   {a.driver}")
        for g in a.gaps:
            print(f"      gap:      {g}")
        if missing:
            print(f"      missing contracts: {', '.join(missing)}")
    print(f"\n{blocked}/{len(ADAPTER_SPECS)} legs blocked by the endpoint-contract doc gate "
          f"({CONTRACTS_YAML.name}); promotion sequence + oracle protocol: RAW_STORE_RECOVERY_PLAN.md v3 §5-6.")
    return 0


def cmd_fetch(_rp) -> int:
    print("REFUSED: no fetch adapter is wired. Prerequisites: (1) adapters built per ADAPTER_SPECS with "
          "injected paths + E:-write-denied integration test, (2) endpoint contracts human-reviewed, "
          "(3) the user's explicit §13 go-ahead in session.", file=sys.stderr)
    return 3


def main() -> int:
    ap = argparse.ArgumentParser(description="C:-staged raw-store recovery coordinator v2 (fetch §13-gated)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--new-run", metavar="RUN_ID")
    g.add_argument("--run", metavar="RUN_ID")
    ap.add_argument("--inventory", action="store_true")
    ap.add_argument("--preflight", action="store_true")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--fetch", action="store_true")
    a = ap.parse_args()
    rp = open_run(a.new_run or a.run, new=bool(a.new_run))
    if a.inventory:
        return cmd_inventory(rp)
    if a.preflight:
        return cmd_preflight(rp)
    if a.plan:
        return cmd_plan(rp)
    if a.fetch:
        return cmd_fetch(rp)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
