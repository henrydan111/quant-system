@echo off
REM ============================================================================
REM Manually rebuild AND open the centralized HTML dashboard (double-click me).
REM
REM Uses %~dp0 (this .bat's own folder) instead of hardcoding the project path,
REM so the file text stays pure-ASCII. A .bat containing the Chinese path
REM "量化系统" breaks when cmd.exe reads it under a non-UTF-8 code page (e.g. from
REM Task Scheduler) — %~dp0 expands to the real Unicode path at runtime and
REM sidesteps that entirely.
REM
REM The SessionEnd hook and the QuantDashboardRefresh scheduled task call
REM python.exe directly (see .claude/settings.json) and do NOT use this file.
REM ============================================================================
REM %~dp0 = ...\src\dashboard\  ->  venv is two levels up at the project root.
"%~dp0..\..\venv\Scripts\python.exe" "%~dp0build_dashboard.py" --open
echo.
pause
