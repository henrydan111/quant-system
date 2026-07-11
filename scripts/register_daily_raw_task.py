# SCRIPT_STATUS: ACTIVE — calendar-unfreeze Phase 5-C: QuantDailyRawUpdate + watchdog task manager
"""Register / inspect / delete the Phase 5-C Windows scheduled tasks.

- QuantDailyRawUpdate (18:30 CHINA time): [daily_raw_update.bat](daily_raw_update.bat) — raw-only
  daily update (`update_daily_data.py --no-qlib --last-complete-session`) + `run_daily_qa.py`. Never
  touches the Qlib provider/calendar (D1/D2); the calendar advances only via the monthly bump (5-B).
- QuantDailyRawWatchdog (10:00 CHINA time next morning): [daily_job_watchdog.py](daily_job_watchdog.py)
  — alerts if the daily job silently missed a run (the main task cannot report it never launched).

Registered via Task Scheduler XML so the trigger carries an explicit +08:00 (CHINA) StartBoundary —
`schtasks /ST` uses the HOST's local time, and this host may run in a US timezone, so a naive "18:30"
would fire ~06:30 China time (GPT M2). The XML also sets StartWhenAvailable=true (catch a run missed
while asleep/offline), a bounded RestartOnFailure, and MultipleInstancesPolicy=IgnoreNew.

DRY-RUN by default (prints the XML, executes nothing). --register / --delete mutate the machine (§13).

    venv/Scripts/python.exe scripts/register_daily_raw_task.py            # dry-run (print XML)
    venv/Scripts/python.exe scripts/register_daily_raw_task.py --register # create both tasks (§13)
    venv/Scripts/python.exe scripts/register_daily_raw_task.py --query    # show the tasks
    venv/Scripts/python.exe scripts/register_daily_raw_task.py --delete   # remove both tasks (§13)
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PY = PROJECT_ROOT / "venv" / "Scripts" / "python.exe"

DAILY_TASK = "QuantDailyRawUpdate"
WATCHDOG_TASK = "QuantDailyRawWatchdog"
WRAPPER = PROJECT_ROOT / "scripts" / "daily_raw_update.bat"
WATCHDOG_SCRIPT = PROJECT_ROOT / "scripts" / "daily_job_watchdog.py"
# 18:30 / 10:00 CHINA time — the +08:00 offset is what pins it to CST regardless of host timezone.
# The date part only anchors a DAILY recurrence; a fixed past anchor is fine.
DAILY_START = "2026-01-01T18:30:00+08:00"
WATCHDOG_START = "2026-01-02T10:00:00+08:00"

_XML = '''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>{desc}</Description></RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>{start}</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author"><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal>
  </Principals>
  <Settings>
    <StartWhenAvailable>true</StartWhenAvailable>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <RestartOnFailure><Interval>PT30M</Interval><Count>3</Count></RestartOnFailure>
    <ExecutionTimeLimit>PT4H</ExecutionTimeLimit>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <Enabled>true</Enabled>
  </Settings>
  <Actions Context="Author">
    <Exec><Command>{cmd}</Command>{args}<WorkingDirectory>{cwd}</WorkingDirectory></Exec>
  </Actions>
</Task>'''


def _task_xml(desc: str, start: str, cmd: str, arguments: str = "") -> str:
    args_el = f"<Arguments>{arguments}</Arguments>" if arguments else ""
    return _XML.format(desc=desc, start=start, cmd=cmd, args=args_el, cwd=str(PROJECT_ROOT))


def _register(task_name: str, xml_str: str) -> int:
    fd, path = tempfile.mkstemp(suffix=".xml")
    os.close(fd)
    Path(path).write_text(xml_str, encoding="utf-16")  # UTF-16 handles the Chinese repo path safely
    try:
        return subprocess.run(["schtasks", "/Create", "/TN", task_name, "/XML", path, "/F"]).returncode
    finally:
        os.remove(path)


def main() -> int:
    ap = argparse.ArgumentParser(description="Manage the Phase 5-C scheduled tasks")
    ap.add_argument("--register", action="store_true", help="Create both tasks (§13 machine mutation)")
    ap.add_argument("--delete", action="store_true", help="Delete both tasks (§13 machine mutation)")
    ap.add_argument("--query", action="store_true", help="Show the task definitions")
    args = ap.parse_args()

    if not WRAPPER.exists() or not WATCHDOG_SCRIPT.exists():
        print("ERROR: wrapper or watchdog script not found", file=sys.stderr)
        return 2

    daily_xml = _task_xml("Phase 5-C daily raw-layer update + QA (18:30 CST)", DAILY_START, str(WRAPPER))
    watchdog_xml = _task_xml("Phase 5-C missed-run watchdog (10:00 CST)", WATCHDOG_START,
                             str(PY), f"&quot;{WATCHDOG_SCRIPT}&quot;")

    if args.query:
        for t in (DAILY_TASK, WATCHDOG_TASK):
            subprocess.run(["schtasks", "/Query", "/TN", t, "/V", "/FO", "LIST"])
        return 0
    if args.delete:
        rc = 0
        for t in (DAILY_TASK, WATCHDOG_TASK):
            rc |= subprocess.run(["schtasks", "/Delete", "/TN", t, "/F"]).returncode
        return rc
    if args.register:
        rc = _register(DAILY_TASK, daily_xml)
        rc |= _register(WATCHDOG_TASK, watchdog_xml)
        return rc

    print("=== " + DAILY_TASK + " XML ===\n" + daily_xml)
    print("\n=== " + WATCHDOG_TASK + " XML ===\n" + watchdog_xml)
    print(f"\n[dry-run] nothing executed. --register creates {DAILY_TASK} (18:30 CST, StartWhenAvailable, "
          f"restart x3) + {WATCHDOG_TASK} (10:00 CST). §13 machine mutation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
