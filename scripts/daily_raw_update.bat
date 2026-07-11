@echo off
setlocal
REM ── Phase 5-C: unattended daily raw-layer update + QA (QuantDailyRawUpdate scheduled task) ──
REM Raw-only (--no-qlib): NEVER touches the Qlib provider / calendar / manifest / ledger (D1/D2);
REM the calendar advances only via the monthly formal bump. --last-complete-session picks the last
REM CST-complete trading day (never a partial calendar-today); the updater's is_open check skips
REM non-trading days. QA runs after and writes logs\qa_alert_<date>.flag on failure.
REM
REM SELF-RELATIVE (%~dp0 = this script's dir, resolved by the OS at runtime) so there is NO
REM hardcoded non-ASCII repo path — cmd under code page 936 would misdecode a UTF-8 Chinese path
REM literal and cd would fail. This file is ASCII-only; keep it that way.
cd /d "%~dp0.." || exit /b 2

set "PY=venv\Scripts\python.exe"
"%PY%" src\data_infra\pipeline\update_daily_data.py --no-qlib --last-complete-session
set "UPD=%ERRORLEVEL%"
"%PY%" scripts\run_daily_qa.py
set "QA=%ERRORLEVEL%"

REM Propagate a combined non-zero exit if EITHER the updater or QA failed (GPT M1).
if not "%UPD%"=="0" (echo daily update FAILED exit=%UPD% & exit /b %UPD%)
if not "%QA%"=="0" (echo daily QA FAILED exit=%QA% & exit /b %QA%)
exit /b 0
