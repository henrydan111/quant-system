@echo off
REM ============================================================================
REM Serve the dashboard over http://127.0.0.1 so the IN-PAGE markdown viewer
REM works (it uses fetch(), which the browser blocks on a file:// double-click).
REM Double-click me → the dashboard opens in your browser and .md links render
REM inside the page. Close this console window to stop the server.
REM Bound to 127.0.0.1 only (not exposed on the network). %~dp0..\.. = repo root.
REM ============================================================================
set PORT=8799
start "" "http://127.0.0.1:%PORT%/index.html"
"%~dp0..\..\venv\Scripts\python.exe" -m http.server %PORT% --bind 127.0.0.1 --directory "%~dp0..\.."
