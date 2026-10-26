@echo off
TITLE NeuroQuant-LOB: NVIDIA Graduate Fellowship Dossier Generator
COLOR 06

echo ==============================================================================
echo   NEUROQUANT-LOB: NVIDIA FELLOWSHIP PRODUCTION DOSSIER COMPILER
echo   Compiling executive report, silicon utilization, and 18 publication assets
echo   Principal Architect: Arunjyoti Sarma (Research Scholar, IIT (BHU))
echo ==============================================================================
echo.

cd /d "%~dp0"

python generate_fellowship_production_dossier.py

echo.
echo [..] Opening Interactive Dossier in default browser...
start "" "dossier\NVIDIA_FELLOWSHIP_PRODUCTION_DOSSIER.html"

echo.
pause
