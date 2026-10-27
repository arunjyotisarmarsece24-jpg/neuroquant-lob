@echo off
title NEUROQUANT-LOB: BERSERK NVIDIA FELLOWSHIP PROPOSAL & SUPERVISOR SUITE
color 0A
cd /d "%~dp0"

echo ================================================================================
echo   [NEUROQUANT-LOB] BERSERK NVIDIA FELLOWSHIP PROPOSAL & SUPERVISOR SUITE
echo   Author: Arunjyoti Sarma (IIT BHU Varanasi) ^| Target: NVIDIA Graduate Fellowship
echo ================================================================================
echo.

echo [1/3] Running Live Berserk Stress & Hardware Benchmark Suite...
python benchmarks\run_brutal_nvidia_stress_suite.py
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Benchmark encountered an error!
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [2/3] Compiling Publication Dossiers & Supervisor LoR Packages...
python generate_berserk_nvidia_dossier.py
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Dossier compilation failed!
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [3/3] Opening Research Proposal & Supervisor Recommendation Letter in Browser...
start "" "dossier\NVIDIA_GRADUATE_FELLOWSHIP_RESEARCH_PROPOSAL.html"
start "" "dossier\SUPERVISOR_LETTER_OF_RECOMMENDATION_DOSSIER.html"

echo.
echo ================================================================================
echo   SUCCESS! The NVIDIA Fellowship Proposal and Supervisor Letter of Recommendation
echo   have been compiled and launched in your browser.
echo ================================================================================
echo.
pause
