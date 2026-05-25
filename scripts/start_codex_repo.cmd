@echo off
setlocal
set "_script=%~dp0start_codex_repo.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -Command "& { param([string]$ScriptPath) & $ScriptPath -CodexArgs $args }" "%_script%" %*
