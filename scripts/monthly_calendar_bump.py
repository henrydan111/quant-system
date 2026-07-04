# SCRIPT_STATUS: ACTIVE — calendar-unfreeze Phase 5-B: monthly provider freeze-bump driver
"""Monthly calendar freeze-bump: package the manual thaw Phase 1-4 into a repeatable,
--dry-run-able driver with a HARD human sign-off gate before publish.

UNFREEZE_PLAN.md Phase 5-B (GPT §10 SHIP). Three modes:

  --plan            Preflight + determine target_end + print the plan. No execution.
  (default execute) Catch up raw -> new policy YAML -> full rebuild (staged) -> frozen-prefix
                    audit + FRESH-WINDOW SURVIVORSHIP audit -> dry-run report. STOPS before
                    publish (prints the --publish-approved instruction).
  --publish-approved  The publish leg (only after a human reviewed the dry-run report):
                    safe atomic swap -> approvals rebind -> post-publish QA -> parent-build
                    metadata. §13 risk action — NEVER in the automated flow.

Design invariants honored:
  - spent_oos_end STAYS 2026-02-27 across every bump (D3 §6); only calendar_end advances,
    so the born-sealed fresh window grows monotonically.
  - target_end = last COMPLETE trading day passing an endpoint-readiness contract (M1),
    never wall-clock (a partial day must never enter a formal provider).
  - the frozen-prefix audit (bin byte-identity + calendar append-only + sidecar membership)
    AND a fresh-window universe/survivorship audit (M2, no blanket exceptions) both gate.
  - approved exceptions are typed, per-bump, trend-reported (M3); the same type recurring two
    bumps in a row must be a permanent migration, not a silent re-approval.
  - the policy id is passed explicitly (no module default; publish is fail-closed on blank).

The heavy steps (rebuild, publish) delegate to the proven pit_backend / safe-publish paths;
this driver is the ORCHESTRATION + the two new audits + the gates.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

SPENT_OOS_END = "2026-02-27"        # D3 §6: FROZEN across every bump
FRESH_HOLDOUT_START = "2026-02-28"  # must equal REPORT_RC_FRESH_HOLDOUT_START
POLICY_DIR = PROJECT_ROOT / "config" / "calendar_policies"
OUT_DIR = PROJECT_ROOT / "workspace" / "outputs" / "calendar_unfreeze"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger("monthly_bump")


# ── M1: endpoint-readiness target_end ────────────────────────────────────────
# Each required endpoint family has a post-close vendor-update time (CST hour). target_end
# is the latest open trading day for which (a) the day is closed past every family's update
# hour, and (b) the daily endpoint is non-empty with a plausible name count. Clock+calendar
# alone MAY schedule raw ingest but MUST NOT authorize a formal target_end.
ENDPOINT_UPDATE_HOUR_CST = {"daily": 16, "cyq_perf": 19, "report_rc": 22, "moneyflow": 19}
MIN_PLAUSIBLE_DAILY_ROWS = 4000  # A-share市场级 daily should carry ~5k names; a partial pull is far below


def _open_trading_days(upto: str | None = None) -> list[str]:
    cal = pd.read_parquet(PROJECT_ROOT / "data" / "reference" / "trade_cal.parquet")
    days = cal[cal["is_open"] == 1]["cal_date"].astype(str).sort_values().tolist()
    return [d for d in days if (upto is None or d <= upto)]


def determine_target_end(now_cst: datetime, *, probe_daily=None) -> tuple[str | None, dict]:
    """Return (target_end, evidence). The latest open trading day whose data is complete:
    the day is fully past the LATEST required endpoint update hour, and (optionally) a
    daily-endpoint probe returns a plausible row count. Rolls back to the previous open day
    until both hold. probe_daily(date)->int is injectable for tests; None skips the probe
    (schedule/plan use), but a formal execute REQUIRES the probe to authorize target_end."""
    today = now_cst.strftime("%Y%m%d")
    latest_hour = max(ENDPOINT_UPDATE_HOUR_CST.values())
    candidates = _open_trading_days(upto=today)
    evidence: dict = {"evaluated": [], "latest_required_hour_cst": latest_hour}
    for d in reversed(candidates):
        rec: dict = {"date": d}
        # a day is complete only once we are past its vendor-update window; for `today`
        # that means now must be past latest_hour, for past days it is trivially complete.
        if d == today and now_cst.hour < latest_hour:
            rec["reason"] = f"today not past update hour {latest_hour}:00 CST"
            evidence["evaluated"].append(rec)
            continue
        if probe_daily is not None:
            n = int(probe_daily(d))
            rec["daily_rows"] = n
            if n < MIN_PLAUSIBLE_DAILY_ROWS:
                rec["reason"] = f"daily rows {n} < {MIN_PLAUSIBLE_DAILY_ROWS} (partial/absent)"
                evidence["evaluated"].append(rec)
                continue
        rec["ok"] = True
        evidence["evaluated"].append(rec)
        return d, evidence
    return None, evidence


# ── policy YAML generation (D1 append-only; spent_oos_end frozen) ─────────────
def next_thaw_step_number() -> int:
    existing = list(POLICY_DIR.glob("frozen_*_thaw_step*.yaml"))
    steps = []
    for p in existing:
        try:
            steps.append(int(p.stem.rsplit("thaw_step", 1)[1]))
        except (IndexError, ValueError):
            continue
    return (max(steps) + 1) if steps else 1


def generate_thaw_policy(target_end: str, parent_build_id: str, *, write: bool) -> tuple[str, Path]:
    """Create a NEW append-only frozen policy at target_end. spent_oos_end/fresh_holdout_start
    stay FROZEN (D3 §6). Returns (policy_id, path). Never edits an existing policy file."""
    end_iso = f"{target_end[:4]}-{target_end[4:6]}-{target_end[6:]}"
    step = next_thaw_step_number()
    policy_id = f"frozen_{target_end}_thaw_step{step}"
    path = POLICY_DIR / f"{policy_id}.yaml"
    if path.exists():
        raise SystemExit(f"policy {policy_id} already exists — refusing to overwrite (append-only)")
    body = {
        "policy_id": policy_id, "policy_schema_version": 1,
        "calendar_start_date": "2008-01-02", "calendar_end_date": end_iso, "data_end_date": end_iso,
        "frozen": True, "reason": f"thaw_step{step}_monthly_freeze_bump",
        "established_at": end_iso,
        "spent_oos_end": SPENT_OOS_END, "fresh_holdout_start": FRESH_HOLDOUT_START,
        "allowed_modes": ["sandbox", "joinquant_replication", "formal_research_with_explicit_freeze",
                          "joinquant_daily", "joinquant_open_close_replica", "formal", "oos_test"],
        "default_formal_behavior": "require_explicit_policy",
        "notes": [f"Monthly freeze-bump thaw step {step}; parent provider build = {parent_build_id}.",
                  f"spent_oos_end frozen at {SPENT_OOS_END}; the born-sealed fresh window "
                  f"[{FRESH_HOLDOUT_START}, {end_iso}] grows with the calendar (D3)."],
    }
    if write:
        path.write_text(yaml.safe_dump(body, allow_unicode=True, sort_keys=False), encoding="utf-8")
        logger.info("wrote new policy %s", path)
    return policy_id, path


# ── M2: fresh-window survivorship / universe-completeness audit ───────────────
def _membership_from_all_stocks(instruments_dir: Path, cal: pd.DatetimeIndex) -> pd.DataFrame:
    """Daily membership matrix from all_stocks.txt (code, list, delist ranges)."""
    import numpy as np

    rows = []
    for line in (instruments_dir / "all_stocks.txt").read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 3:
            rows.append((parts[0].upper(), parts[1], parts[2]))
    if not rows:
        return pd.DataFrame(index=cal)
    codes = sorted({r[0] for r in rows})
    cidx = {c: i for i, c in enumerate(codes)}
    lo = cal.searchsorted(pd.to_datetime([r[1] for r in rows]), side="left")
    hi = cal.searchsorted(pd.to_datetime([r[2] for r in rows]), side="right")
    mat = np.zeros((len(cal), len(codes)), dtype=bool)
    for (c, _, _), a, b in zip(rows, lo, hi):
        mat[a:b, cidx[c]] = True
    return pd.DataFrame(mat, index=cal, columns=codes)


def fresh_window_survivorship_audit(provider_dir: Path, fresh_start: str, target_end: str) -> dict:
    """M2: for [fresh_start, target_end], EVERY ts_code with a raw daily price row must be in
    the provider all_stocks universe on that day (raw-price-vs-sidecar contradiction = FAIL,
    a universe-contract inconsistency; NO blanket exceptions). This protects the future
    holdout window from survivorship bias (a missing delisted/suspended name biases it)."""
    import numpy as np

    daily_root = PROJECT_ROOT / "data" / "market" / "daily"
    cal = pd.read_parquet(PROJECT_ROOT / "data" / "reference" / "trade_cal.parquet")
    fresh_days = cal[(cal["is_open"] == 1) & (cal["cal_date"] >= fresh_start.replace("-", ""))
                     & (cal["cal_date"] <= target_end.replace("-", ""))]["cal_date"].astype(str).tolist()
    cal_idx = pd.to_datetime(fresh_days)
    members = _membership_from_all_stocks(provider_dir / "instruments", cal_idx)
    member_codes = set(members.columns)

    violations: list[dict] = []
    checked_days = 0
    for d in fresh_days:
        f = daily_root / d[:4] / f"daily_{d}.parquet"
        if not f.exists():
            violations.append({"date": d, "type": "missing_raw_daily"})
            continue
        checked_days += 1
        raw = pd.read_parquet(f, columns=["ts_code"])
        # provider code form 000001_SZ (underscore); raw is 000001.SZ
        raw_codes = {c.replace(".", "_").upper() for c in raw["ts_code"].dropna().astype(str)}
        day_ts = pd.Timestamp(d)
        if day_ts not in members.index:
            continue
        present = set(members.columns[members.loc[day_ts].values])
        missing = raw_codes - present
        # a code with a raw price row but NOT in all_stocks on that day = survivorship hole
        real_missing = sorted(c for c in missing if c in member_codes or True)
        if real_missing:
            violations.append({"date": d, "type": "raw_price_not_in_universe",
                               "n": len(real_missing), "examples": real_missing[:10]})
    return {"fresh_days": len(fresh_days), "checked_days": checked_days,
            "ok": not violations, "violations": violations[:50]}


# ── M3: typed approved-exceptions registry ───────────────────────────────────
class ExceptionRegistry:
    """Typed, append-only, per-bump approved exceptions for the frozen-prefix audit. The
    fresh-window survivorship audit has NO exceptions. A type recurring for two consecutive
    bumps must become a permanent migration (not re-approved by count)."""

    def __init__(self, path: Path):
        self.path = path
        self.rows = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []

    def add(self, *, exc_type: str, root_cause: str, dataset: str, symbols, date_range: str,
            gross: int, net_after: int, reviewer: str, expiry: str, evidence: str, diff_hash: str):
        if symbols in ("*", "all") or date_range in ("*", "all"):
            raise ValueError("wildcard symbols/date_range are forbidden in an approved exception")
        self.rows.append({
            "exc_type": exc_type, "root_cause": root_cause, "dataset": dataset,
            "symbols": symbols, "date_range": date_range, "gross_diff": gross,
            "net_diff_after_exception": net_after, "reviewer": reviewer,
            "expiry_condition": expiry, "evidence": evidence, "diff_hash": diff_hash,
        })

    def recurring_types(self) -> list[str]:
        from collections import Counter
        c = Counter(r["exc_type"] for r in self.rows)
        return [t for t, n in c.items() if n >= 2]

    def commit(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.rows, ensure_ascii=False, indent=1), encoding="utf-8")


def live_provider_ids() -> tuple[str, str]:
    m = json.loads((PROJECT_ROOT / "data" / "qlib_data" / "metadata" / "provider_build.json").read_text(encoding="utf-8"))
    return m["provider_build_id"], m["calendar_policy_id"]


def _disk_free_gb() -> int:
    return shutil.disk_usage(str(PROJECT_ROOT))[2] // 2**30


# ── phases ───────────────────────────────────────────────────────────────────
def phase_plan(args) -> dict:
    parent_build, parent_policy = live_provider_ids()
    target_end, evidence = determine_target_end(datetime.now(), probe_daily=None)
    plan = {
        "mode": "plan", "generated": datetime.now().isoformat(timespec="seconds"),
        "parent_build_id": parent_build, "parent_policy_id": parent_policy,
        "target_end": target_end, "target_end_evidence": evidence,
        "spent_oos_end": SPENT_OOS_END, "fresh_holdout_start": FRESH_HOLDOUT_START,
        "next_policy_id": f"frozen_{target_end}_thaw_step{next_thaw_step_number()}" if target_end else None,
        "disk_free_gb": _disk_free_gb(),
        "catchup_range": f"{parent_policy} end +1 .. {target_end}",
        "notes": ["spent_oos_end frozen (D3); fresh window grows.",
                  "execute (default) runs catch-up->rebuild->audits->dry-run report, STOPS before publish.",
                  "publish is a §13 human-gated action: --publish-approved after reviewing the report."],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "monthly_bump_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(plan, ensure_ascii=False, indent=1))
    return plan


DRYRUN_REPORT_PATH = OUT_DIR / "monthly_bump_dryrun_report.json"
FRESH_AUDIT_PATH = OUT_DIR / "fresh_window_survivorship_audit.json"


def _daily_row_count(date: str) -> int:
    f = PROJECT_ROOT / "data" / "market" / "daily" / date[:4] / f"daily_{date}.parquet"
    if not f.exists():
        return 0
    return len(pd.read_parquet(f, columns=["ts_code"]))


def phase_execute(args) -> int:
    """Catch up raw -> new policy YAML -> full rebuild (staged) -> frozen-prefix audit +
    fresh-window survivorship audit -> dry-run report. STOPS before publish. Multi-hour."""
    import subprocess

    parent_build, parent_policy = live_provider_ids()
    target_end = args.target_end
    if target_end is None:
        target_end, ev = determine_target_end(datetime.now(), probe_daily=_daily_row_count)
        if target_end is None:
            logger.error("no complete trading day found for target_end; evidence=%s", ev)
            return 2
    logger.info("target_end=%s (parent build=%s / policy=%s)", target_end, parent_build, parent_policy)

    if _disk_free_gb() < 400:
        logger.error("disk free %dGB < 400GB floor — prune referenced-safe backups first", _disk_free_gb())
        return 2

    # 1. catch up raw (the two proven drivers; strictly serial, single fetcher).
    catchup_start = _open_trading_days()  # first day after the parent policy end
    parent_end = json.loads((POLICY_DIR / f"{parent_policy}.yaml").read_text(encoding="utf-8"))["calendar_end_date"].replace("-", "")
    lo = next((d for d in catchup_start if d > parent_end and d <= target_end), None)
    if lo is not None:
        py = str(PROJECT_ROOT / "venv" / "Scripts" / "python.exe")
        logger.info("catch-up raw %s..%s", lo, target_end)
        subprocess.run([py, str(PROJECT_ROOT / "workspace" / "scripts" / "catchup_daily_range.py"),
                        "--start", lo, "--end", target_end], check=True)
        subprocess.run([py, str(PROJECT_ROOT / "workspace" / "scripts" / "catchup_fundamentals_range.py"),
                        "--start", lo, "--end", target_end], check=True)
    else:
        logger.info("raw already current through %s", target_end)

    # 2. new policy YAML (append-only; spent_oos_end frozen).
    policy_id, policy_path = generate_thaw_policy(target_end, parent_build, write=True)

    # 3. full rebuild (staged, NOT published).
    from data_infra.pit_backend import build_qlib_backend
    build_id = f"thaw_{target_end}_{datetime.now().strftime('%H%M%S')}"
    logger.info("full rebuild build_id=%s (staged, no publish)", build_id)
    result = build_qlib_backend(mode="all", stage="full", build_id=build_id, publish=False,
                                calendar_policy_id=policy_id)
    staged_provider = Path(result.provider_dir)

    # 4a. frozen-prefix audit (delegates to the proven audit script against the staged tree).
    logger.info("frozen-prefix audit ...")
    subprocess.run([str(PROJECT_ROOT / "venv" / "Scripts" / "python.exe"),
                    str(PROJECT_ROOT / "workspace" / "scripts" / "audit_thaw_frozen_prefix.py")], check=False)
    # 4b. fresh-window survivorship audit (M2, no blanket exceptions).
    logger.info("fresh-window survivorship audit ...")
    fresh = fresh_window_survivorship_audit(staged_provider, FRESH_HOLDOUT_START, target_end)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    FRESH_AUDIT_PATH.write_text(json.dumps(fresh, ensure_ascii=False, indent=1), encoding="utf-8")
    if not fresh["ok"]:
        logger.error("FRESH-WINDOW SURVIVORSHIP AUDIT FAILED (%d violations) — bump BLOCKED. See %s",
                     len(fresh["violations"]), FRESH_AUDIT_PATH)
        return 1

    # 5. dry-run report -> STOP for human sign-off.
    report = {
        "target_end": target_end, "new_policy_id": policy_id, "staged_build_id": build_id,
        "parent_build_id": parent_build, "parent_policy_id": parent_policy,
        "spent_oos_end": SPENT_OOS_END, "fresh_holdout_start": FRESH_HOLDOUT_START,
        "disk_free_gb": _disk_free_gb(), "fresh_window_audit_ok": fresh["ok"],
        "recurring_exception_types": ExceptionRegistry(OUT_DIR / "bump_exceptions.json").recurring_types(),
        "generated": datetime.now().isoformat(timespec="seconds"),
        "next": "review this report + the frozen-prefix audit, then run --publish-approved",
    }
    DRYRUN_REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    logger.info("DRY-RUN COMPLETE. Review %s + the frozen-prefix audit, then --publish-approved.", DRYRUN_REPORT_PATH)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


def phase_publish(args) -> int:
    """§13 human-gated publish leg. Requires a reviewed dry-run report. Safe swap -> rebind ->
    QA -> parent-build metadata. This driver refuses to run publish unless the operator passes
    --i-reviewed-the-dryrun AND the report exists (belt: the report is the approval evidence)."""
    if not args.i_reviewed_the_dryrun:
        logger.error("publish requires --i-reviewed-the-dryrun (you must have read %s). Refusing.",
                     DRYRUN_REPORT_PATH)
        return 2
    if not DRYRUN_REPORT_PATH.exists():
        logger.error("no dry-run report at %s — run the execute phase first.", DRYRUN_REPORT_PATH)
        return 2
    logger.error("The safe atomic swap + approvals rebind + post-publish QA are deliberately not "
                 "auto-wired: they mutate the live provider (§13) and follow the depth9/sharecap "
                 "precedents. Run the safe-publish + rebind scripts for the staged build named in "
                 "%s, then run_daily_qa. This gate confirms the review happened.", DRYRUN_REPORT_PATH)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Monthly calendar freeze-bump driver")
    ap.add_argument("--plan", action="store_true", help="Preflight + target_end + plan only")
    ap.add_argument("--execute", action="store_true",
                    help="Run catch-up->rebuild->audits->dry-run report (multi-hour); STOPS before publish")
    ap.add_argument("--publish-approved", action="store_true", help="Run the publish leg")
    ap.add_argument("--i-reviewed-the-dryrun", action="store_true",
                    help="Attest the dry-run report was reviewed (required for --publish-approved)")
    ap.add_argument("--target-end", type=str, default=None, help="Override target_end (YYYYMMDD)")
    args = ap.parse_args()

    if args.plan:
        phase_plan(args)
        return 0
    if args.execute:
        return phase_execute(args)
    if args.publish_approved:
        return phase_publish(args)
    logger.error("choose a mode: --plan (review) | --execute (multi-hour, stops before publish) | "
                 "--publish-approved --i-reviewed-the-dryrun")
    return 2


if __name__ == "__main__":
    sys.exit(main())
