@echo off
cd /d "%~dp0"
title NEUROQUANT-LOB: 1-Click Institutional Web Server & API Host
echo ===============================================================================
echo   NEUROQUANT-LOB: WEB APPLICATION & REST API SERVER LAUNCHER
echo   Principal Architect: Arunjyoti Sarma (Research Scholar, IIT BHU)
echo   Target: Institutional Tier-1 HFT Web Dashboard (http://127.0.0.1:5000)
echo ===============================================================================
echo.

echo [*] Launching NeuroQuant Web Application & REST API Host on port 5000...
start "NeuroQuant-LOB Web Server [Port 5000]" python run_app.py

echo [*] Waiting 3 seconds for server initialization...
timeout /t 3 /nobreak >nul
echo.

python check_api.py

echo.
echo ===============================================================================
echo   DASHBOARD URL: http://127.0.0.1:5000 (Open in your browser)
echo   API ENDPOINT:  http://127.0.0.1:5000/api/sweeps/status
echo ===============================================================================
pause
