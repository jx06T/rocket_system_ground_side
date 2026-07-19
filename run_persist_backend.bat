@echo off
title Rocket Ground Station - Launcher (Persistent Backend)
cd /d "%~dp0"

set PYTHON_EXEC=python
if exist ".venv\Scripts\python.exe" (
    set PYTHON_EXEC=.venv\Scripts\python.exe
)

echo Launching Backend Daemon in a separate terminal window...
start "Rocket Backend Daemon" "%PYTHON_EXEC%" src\backend_daemon.py --channel ch1 --standalone

echo Launching GUI Visualizer...
echo When the GUI closes, the backend daemon window will remain active.
echo.

"%PYTHON_EXEC%" main.py --gui-only

echo GUI has exited, but the Backend Daemon is still running in the background.
echo Check the other terminal window or logs to see the data logging.
echo.
pause
