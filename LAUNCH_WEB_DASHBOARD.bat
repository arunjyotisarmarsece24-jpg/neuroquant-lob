@echo off
TITLE NeuroQuant-LOB: Mission Control Web Dashboard Launcher
COLOR 0E

echo ==============================================================================
echo   NEUROQUANT-LOB: MISSION CONTROL WEB DASHBOARD LAUNCHER
echo   Principal Architect: Arunjyoti Sarma (Research Scholar, IIT (BHU))
echo ==============================================================================
echo.

cd /d "%~dp0"

echo [1/2] Checking Flask Web Daemon...
netstat -ano | findstr :5000 | findstr LISTENING >nul
if %errorlevel% equ 0 (
    echo [OK] Web server is already running on port 5000.
) else (
    echo [..] Spawning Flask server background daemon...
    start /min "NeuroQuant Web Server" python run_app.py
    timeout /t 3 /nobreak >nul
    echo [OK] Server started.
)

echo.
echo [2/2] Opening Mission Control in Default Web Browser...
start http://127.0.0.1:5000

echo.
echo Navigation Quicklinks:
echo   - Mission Control:   http://127.0.0.1:5000
echo   - Visual Exhibition: http://127.0.0.1:5000/gallery
echo   - Fellowship Dossier:http://127.0.0.1:5000/dossier
echo.
pause
