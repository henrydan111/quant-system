@echo off
REM ── Phase 5-C: unattended daily raw-layer update + QA (QuantDailyRawUpdate scheduled task) ──
REM Raw-only (--no-qlib): NEVER touches the Qlib provider / calendar / manifest / ledger (D1/D2 —
REM the calendar advances only via the monthly formal bump). The updater's internal is_open check
REM skips non-trading days, so a plain DAILY trigger is correct. --last-complete-session picks the
REM last CST-complete trading day (past the ~16:00 vendor close), never a partial calendar-today.
REM QA runs after the update and writes logs\qa_alert_<date>.flag on failure (Phase 5-C/C3).
cd /d E:\量化系统
venv\Scripts\python.exe src\data_infra\pipeline\update_daily_data.py --no-qlib --last-complete-session
venv\Scripts\python.exe scripts\run_daily_qa.py
