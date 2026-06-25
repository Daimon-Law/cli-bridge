@echo off
REM ===========================================================================
REM  Windows launcher for cli-bridge (optional, keeps it running after logon).
REM
REM  Reboot-persistence (Startup folder method):
REM    1. Edit the two CHANGE-ME lines below.
REM    2. Press Win+R, type  shell:startup  and press Enter.
REM    3. Put a shortcut to this file in the folder that opens. Right-click this
REM       file, choose Create shortcut, then move the shortcut into that folder.
REM    Windows then runs it automatically each time you log in.
REM
REM  For a version with no console window, use Task Scheduler with an
REM  "At log on" trigger instead of the Startup folder.
REM
REM  bridge.py reads its .env from its own folder, so no extra setup is needed.
REM ===========================================================================

REM CHANGE-ME: the folder containing bridge.py
cd /d "%USERPROFILE%\cli-bridge"

REM CHANGE-ME: "python" if it is on PATH, otherwise the full path to python.exe
python bridge.py
