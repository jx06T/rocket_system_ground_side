@echo off
title Rocket Ground Station - Backend Daemon (CH2 / 2.4GHz)
cd /d "%~dp0"

set PYTHON_EXEC=python
if exist ".venv\Scripts\python.exe" (
    set PYTHON_EXEC=.venv\Scripts\python.exe
)

echo Starting Backend Daemon for CH2 (2.4GHz / E28, com7) in Standalone mode...
echo Press Ctrl+C in this window to stop it.
echo.

"%PYTHON_EXEC%" src\backend_daemon.py --channel ch2 --standalone

pause
