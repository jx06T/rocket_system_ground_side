@echo off
title Rocket Ground Station - Launcher (Persistent Backend)
cd /d "%~dp0"

set PYTHON_EXEC=python
if exist ".venv\Scripts\python.exe" (
    set PYTHON_EXEC=.venv\Scripts\python.exe
)

echo Launching BOTH backend daemons in separate terminal windows...
start "Rocket Backend CH1 (915MHz)" "%PYTHON_EXEC%" src\backend_daemon.py --channel ch1 --standalone
start "Rocket Backend CH2 (2.4GHz)" "%PYTHON_EXEC%" src\backend_daemon.py --channel ch2 --standalone

echo Launching GUI Visualizer (attaches to BOTH daemons)...
echo When the GUI closes, the backend daemon windows will remain active.
echo.

"%PYTHON_EXEC%" main.py --gui-only

echo GUI has exited, but the Backend Daemons are still running in the background.
echo Close them with Ctrl+C in each window.
echo.
pause
