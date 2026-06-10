@echo off
REM ============================================================================
REM Open the dashboard in your browser. The always-on QuantDashboardServe
REM scheduled task already serves it at http://127.0.0.1:8799 (started at logon),
REM so this just opens the browser — the in-page markdown viewer works.
REM You can also simply BOOKMARK the URL below; no need to run anything.
REM ============================================================================
start "" "http://127.0.0.1:8799/index.html"
