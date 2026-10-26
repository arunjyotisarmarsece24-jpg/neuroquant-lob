@echo off
TITLE NeuroQuant-LOB: Flagship Research & Hardware Exhibition Gallery
COLOR 0B

echo ==============================================================================
echo   NEUROQUANT-LOB: FLAGSHIP RESEARCH & HARDWARE EXHIBITION GALLERY
echo   18 Publication Figures, Cycle-Accurate Verilog Waveforms & IEEE Whitepaper
echo   Principal Architect: Arunjyoti Sarma (Research Scholar, IIT (BHU))
echo ==============================================================================
echo.

cd /d "%~dp0"

echo [..] Launching Standalone Dark Cyberpunk Exhibition Desktop App...
python neuroquant_showcase_app.py

echo.
echo [INFO] Exhibition gallery closed.
pause
