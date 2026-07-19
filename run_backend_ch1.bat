@echo off
title Rocket Ground Station - Backend Daemon (CH1)
cd /d "%~dp0"

set PYTHON_EXEC=python
if exist ".venv\Scripts\python.exe" (
    set PYTHON_EXEC=.venv\Scripts\python.exe
)

echo Starting Backend Daemon for CH1 in Standalone mode...
echo Telemetry files and logs will be written in the background.
echo Press Ctrl+C in this window to stop the backend daemon.
echo.

"%PYTHON_EXEC%" src\backend_daemon.py --channel ch1 --standalone

pause
