@echo off
TITLE NeuroQuant-LOB: Enterprise Production Studio Launcher
COLOR 0A

echo ==============================================================================
echo   NEUROQUANT-LOB: ENTERPRISE PRODUCTION STUDIO & EXECUTIVE COCKPIT
echo   Principal Architect: Arunjyoti Sarma (Research Scholar, IIT (BHU))
echo   Target: NVIDIA Graduate Fellowship ($60,000 USD)
echo ==============================================================================
echo.

cd /d "%~dp0"

echo [1/3] Checking Web Server Status (Port 5000)...
netstat -ano | findstr :5000 | findstr LISTENING >nul
if %errorlevel% equ 0 (
    echo [OK] Web Server is already active on http://127.0.0.1:5000
) else (
    echo [..] Starting Flask Web Server in background...
    start /min "NeuroQuant Web Server" python run_app.py
    timeout /t 3 /nobreak >nul
    echo [OK] Web Server successfully launched!
)

echo.
echo [2/3] Verifying Fellowship Dossier & Visual Catalog...
if not exist "dossier\NVIDIA_FELLOWSHIP_PRODUCTION_DOSSIER.html" (
    echo [..] Compiling initial NVIDIA Fellowship Production Dossier...
    python generate_fellowship_production_dossier.py
)
echo [OK] Production Dossier verified!

echo.
echo [3/3] Launching NeuroQuant Enterprise Desktop Cockpit...
echo ------------------------------------------------------------------------------
echo Close the application window when finished.
python neuroquant_studio.py

echo.
echo [INFO] NeuroQuant Studio session terminated cleanly.
pause
