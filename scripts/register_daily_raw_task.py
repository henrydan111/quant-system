# SCRIPT_STATUS: ACTIVE — calendar-unfreeze Phase 5-C: QuantDailyRawUpdate scheduled-task manager
"""Register / inspect / delete the QuantDailyRawUpdate Windows scheduled task (Phase 5-C).

The task runs [daily_raw_update.bat](daily_raw_update.bat) every day at 18:30 CST: raw-only daily
update (`update_daily_data.py --no-qlib --last-complete-session`) + `run_daily_qa.py`. It never
touches the Qlib provider/calendar (D1/D2); the calendar advances only via the monthly formal bump
([monthly_calendar_bump.py](monthly_calendar_bump.py)). Non-trading days skip internally.

DRY-RUN by default (prints the schtasks command, executes nothing). Actually creating/deleting the
task mutates the machine (§13) — pass --register / --delete explicitly.

    venv/Scripts/python.exe scripts/register_daily_raw_task.py            # dry-run (print only)
    venv/Scripts/python.exe scripts/register_daily_raw_task.py --register # create the task (§13)
    venv/Scripts/python.exe scripts/register_daily_raw_task.py --query    # show the task
    venv/Scripts/python.exe scripts/register_daily_raw_task.py --delete   # remove the task (§13)
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TASK_NAME = "QuantDailyRawUpdate"
WRAPPER = PROJECT_ROOT / "scripts" / "daily_raw_update.bat"
RUN_TIME = "18:30"  # CST: after the ~16:00 vendor daily close + margin (matches design §5.3)


def _create_cmd() -> list[str]:
    # DAILY trigger; the updater's internal is_open check skips non-trading days. /RL LIMITED = least
    # privilege; /F overwrites so re-registration is idempotent.
    return ["schtasks", "/Create", "/TN", TASK_NAME, "/TR", f'"{WRAPPER}"',
            "/SC", "DAILY", "/ST", RUN_TIME, "/RL", "LIMITED", "/F"]


def main() -> int:
    ap = argparse.ArgumentParser(description="Manage the QuantDailyRawUpdate scheduled task (Phase 5-C)")
    ap.add_argument("--register", action="store_true", help="Create the task (§13 machine mutation)")
    ap.add_argument("--delete", action="store_true", help="Delete the task (§13 machine mutation)")
    ap.add_argument("--query", action="store_true", help="Show the task definition")
    args = ap.parse_args()

    if not WRAPPER.exists():
        print(f"ERROR: wrapper not found: {WRAPPER}", file=sys.stderr)
        return 2

    if args.delete:
        cmd = ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"]
    elif args.query:
        cmd = ["schtasks", "/Query", "/TN", TASK_NAME, "/V", "/FO", "LIST"]
    else:
        cmd = _create_cmd()

    print("schtasks command:\n  " + " ".join(cmd))
    if not (args.register or args.delete or args.query):
        print(f"\n[dry-run] nothing executed. Trigger: DAILY {RUN_TIME} CST -> {WRAPPER.name} "
              f"(update --no-qlib --last-complete-session + run_daily_qa). Non-trading days skip "
              f"internally.\nRe-run with --register to create it (§13).")
        return 0
    result = subprocess.run(cmd)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
