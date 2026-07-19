@echo off
title Rocket Ground Station - GUI Visualizer (GUI-Only)
cd /d "%~dp0"

set PYTHON_EXEC=python
if exist ".venv\Scripts\python.exe" (
    set PYTHON_EXEC=.venv\Scripts\python.exe
)

echo Starting GUI Visualizer in GUI-Only mode...
echo It will connect to the pre-running Backend Daemon.
echo.

"%PYTHON_EXEC%" main.py --gui-only

echo GUI exited.
