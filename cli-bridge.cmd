@echo off
rem cli-bridge launcher for Windows. Works from a fresh clone:  cli-bridge setup
set "DIR=%~dp0"
if exist "%DIR%.venv\Scripts\python.exe" (
  "%DIR%.venv\Scripts\python.exe" "%DIR%bridge.py" %*
) else (
  python "%DIR%bridge.py" %*
)
