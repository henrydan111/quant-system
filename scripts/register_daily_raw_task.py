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
from xml.sax.saxutils import escape

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
    {principal}
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


def _principal(user: str | None) -> str:
    # A dedicated least-privilege account with Password logon runs UNATTENDED across logout/reboot
    # AND keeps network access (Tushare needs it — S4U tasks have no network). Without --user the
    # task uses InteractiveToken: it runs only while that user is interactively logged on, and
    # StartWhenAvailable + the watchdog cover a missed run (GPT M3).
    if user:
        return (f'<Principal id="Author"><UserId>{escape(user)}</UserId>'
                '<LogonType>Password</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal>')
    return ('<Principal id="Author"><LogonType>InteractiveToken</LogonType>'
            '<RunLevel>LeastPrivilege</RunLevel></Principal>')


def _task_xml(desc: str, start: str, cmd: str, arguments: str = "", user: str | None = None) -> str:
    args_el = f"<Arguments>{escape(arguments)}</Arguments>" if arguments else ""
    return _XML.format(desc=escape(desc), start=start, cmd=escape(cmd), args=args_el,
                       cwd=escape(str(PROJECT_ROOT)), principal=_principal(user))


def _register(task_name: str, xml_str: str, user: str | None = None) -> int:
    fd, path = tempfile.mkstemp(suffix=".xml")
    os.close(fd)
    Path(path).write_text(xml_str, encoding="utf-16")  # UTF-16 handles the Chinese repo path safely
    cmd = ["schtasks", "/Create", "/TN", task_name, "/XML", path, "/F"]
    if user:
        # NEVER put the password on the command line (it leaks into process args/history — GPT M4).
        # `/RP *` makes schtasks prompt for it interactively (--register is an operator §13 action).
        cmd += ["/RU", user, "/RP", "*"]
    try:
        return subprocess.run(cmd).returncode
    finally:
        os.remove(path)


def main() -> int:
    ap = argparse.ArgumentParser(description="Manage the Phase 5-C scheduled tasks")
    ap.add_argument("--register", action="store_true", help="Create both tasks (§13 machine mutation)")
    ap.add_argument("--delete", action="store_true", help="Delete both tasks (§13 machine mutation)")
    ap.add_argument("--query", action="store_true", help="Show the task definitions")
    ap.add_argument("--user", default=None,
                    help="Run as this account with Password logon (UNATTENDED across logout/reboot, "
                         "keeps network for Tushare). Omit -> InteractiveToken (runs only when logged on). "
                         "schtasks prompts for the password interactively (/RP *) — never on the cmdline.")
    args = ap.parse_args()

    if not WRAPPER.exists() or not WATCHDOG_SCRIPT.exists():
        print("ERROR: wrapper or watchdog script not found", file=sys.stderr)
        return 2

    daily_xml = _task_xml("Phase 5-C daily raw-layer update + QA (18:30 CST)", DAILY_START,
                          str(WRAPPER), user=args.user)
    watchdog_xml = _task_xml("Phase 5-C missed-run watchdog (10:00 CST)", WATCHDOG_START,
                             str(PY), f'"{WATCHDOG_SCRIPT}"', user=args.user)

    if args.query:
        rc = 0
        for t in (DAILY_TASK, WATCHDOG_TASK):
            rc |= subprocess.run(["schtasks", "/Query", "/TN", t, "/V", "/FO", "LIST"]).returncode
        return rc
    if args.delete:
        rc = 0
        for t in (DAILY_TASK, WATCHDOG_TASK):
            rc |= subprocess.run(["schtasks", "/Delete", "/TN", t, "/F"]).returncode
        return rc
    if args.register:
        if args.user and not sys.stdin.isatty():
            print("ERROR: --user uses Password logon whose /RP * password prompt needs an interactive "
                  "console; no TTY detected. Run --register from a console.", file=sys.stderr)
            return 2
        rc = _register(DAILY_TASK, daily_xml, args.user)
        if rc != 0:
            return rc
        rc2 = _register(WATCHDOG_TASK, watchdog_xml, args.user)
        if rc2 != 0:  # roll back the first so we never leave a half-installed pair
            subprocess.run(["schtasks", "/Delete", "/TN", DAILY_TASK, "/F"])
            return rc2
        return 0

    print("=== " + DAILY_TASK + " XML ===\n" + daily_xml)
    print("\n=== " + WATCHDOG_TASK + " XML ===\n" + watchdog_xml)
    print(f"\n[dry-run] nothing executed. --register creates {DAILY_TASK} (18:30 CST, StartWhenAvailable, "
          f"restart x3) + {WATCHDOG_TASK} (10:00 CST). §13 machine mutation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
