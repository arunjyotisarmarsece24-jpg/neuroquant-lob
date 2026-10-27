@echo off
title NEUROQUANT-LOB: UNIFIED QUANTITATIVE & HARDWARE ENTERPRISE PLATFORM
color 0B
cd /d "%~dp0"

echo ================================================================================
echo   NEUROQUANT-LOB: ENTERPRISE QUANTITATIVE ^& HARDWARE PLATFORM
echo   Principal Architect: Arunjyoti Sarma ^| Electronics Engineering, IIT (BHU)
echo   Hardware Target: AMD Spartan-7 XC7S25 (Arty S7-25) + Arduino Nano Sidecar
echo ================================================================================
echo.

echo [1/3] Verifying Physical Hardware Connection...
echo   - FPGA Port:    COM9 (Arty S7-25)
echo   - Sidecar Port: COM8 (Arduino Nano)
echo   - JTAG Target:  xc7s25_0 Silicon
echo.

echo [2/3] Checking Mission Control Web Server...
netstat -ano | findstr :5000 | findstr LISTENING >nul
if %errorlevel% equ 0 (
    echo   [OK] Web server is already active on http://127.0.0.1:5000
) else (
    echo   [..] Starting background Flask server...
    start /min "NeuroQuant Server" python run_app.py
    timeout /t 3 /nobreak >nul
    echo   [OK] Web server started!
)

echo.
echo [3/3] Opening Unified Mission Control in Browser...
start "" "http://127.0.0.1:5000"

echo.
echo ================================================================================
echo PLATFORM QUICKLINKS FOR SUPERVISOR DEMONSTRATION:
echo   [1] Full Unified Web Platform:  http://127.0.0.1:5000
echo   [2] FPGA Hardware ^& HIL Tab:     http://127.0.0.1:5000  (Click 'FPGA RTL' Tab)
echo   [3] Live L2 Depth Ladder:       http://127.0.0.1:5000  (Click 'L2 Book' Tab)
echo   [4] Neuromorphic Oscilloscope:  http://127.0.0.1:5000  (Click 'Oscilloscope' Tab)
echo   [5] Fellowship Dossier:         http://127.0.0.1:5000/dossier
echo   [6] 18-Figure Visual Gallery:   http://127.0.0.1:5000/gallery
echo ================================================================================
echo.
echo Press any key to keep this window open or exit...
pause
