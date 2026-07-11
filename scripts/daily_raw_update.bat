@echo off
setlocal
REM Phase 5-C: unattended daily raw-layer job (QuantDailyRawUpdate scheduled task).
REM Raw-only: the orchestrator never triggers a Qlib rebuild, so it NEVER touches the provider /
REM calendar / manifest / ledger (D1/D2); the calendar advances only via the monthly formal bump.
REM daily_raw_job.py gap-backfills recently-missed sessions oldest-first, runs QA, binds the
REM heartbeat to BOTH succeeding, and returns a combined exit code.
REM
REM SELF-RELATIVE (%~dp0 = this script's dir, resolved by the OS at runtime) so there is NO
REM hardcoded non-ASCII repo path - cmd under code page 936 would misdecode a UTF-8 Chinese path
REM literal and cd would fail. This file is ASCII-only; keep it that way.
cd /d "%~dp0.." || exit /b 2
venv\Scripts\python.exe scripts\daily_raw_job.py
exit /b %ERRORLEVEL%
