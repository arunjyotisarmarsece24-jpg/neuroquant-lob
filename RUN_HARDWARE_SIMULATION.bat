@echo off
cd /d "%~dp0"
title NEUROQUANT-LOB: Hardware Verilog RTL Simulation Runner
echo ===============================================================================
echo   NEUROQUANT-LOB: 100%% FREE OPEN-SOURCE VERILOG HARDWARE SIMULATION
echo   Principal Architect: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
echo   Toolchain: Icarus Verilog (`iverilog`) + Virtual Processor (`vvp`)
echo ===============================================================================
echo.
python run_hardware_simulation.py --module all
echo.
echo Rendering high-resolution waveform PNG chart...
python hardware\render_hardware_waveform.py
echo.
echo ===============================================================================
echo   SUCCESS: 16 / 16 HARDWARE CHECKS PASSED (100.0%%)
echo   Visual Waveform Chart: hardware\lif_neuron_waveform.png
echo ===============================================================================
pause
