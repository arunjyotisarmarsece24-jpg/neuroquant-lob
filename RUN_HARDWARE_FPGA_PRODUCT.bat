@echo off
title NEUROQUANT-LOB: PHYSICAL FPGA HARDWARE RUNNER (ARTY S7 + ARDUINO NANO)
color 0B
cd /d "%~dp0"

echo ================================================================================
echo   [NEUROQUANT-LOB] PHYSICAL HARDWARE FPGA ACCELERATOR RUNNER
echo   Architect: Arunjyoti Sarma ^| Department of Electronics Engineering, IIT (BHU)
echo   Target: AMD Spartan-7 XC7S25 (Arty S7-25) + Arduino Nano Sidecar
echo ================================================================================
echo.
echo [HARDWARE PINOUT CONFIGURATION]
echo   - Arduino Nano TX1 (Pin D1)  ---^>  Arty S7 Shield IO0 (Pin L13) [FPGA RX]
echo   - Arduino Nano RX0 (Pin D0)  ^<---  Arty S7 Shield IO1 (Pin N13) [FPGA TX]
echo   - Arduino Nano GND           ^<---^>  Arty S7 GND
echo.
echo [DIAGNOSTIC LED ILLUMINATION MAP]
echo   - LD2 (Yellow):       Accelerator Engine Operational
echo   - LD3 (Yellow Pulse): Ingress Stream 0x55AA Frame Lock
echo   - LD4 (Yellow Pulse): Neuromorphic LIF Action Potential Spike
echo   - LD5 (Yellow Pulse): Pre-Trade Gate Approved Trade Clearance
echo   - LD0 (RGB):          Green = Normal ^| Blue = Data Ingest ^| Red = Risk Breach
echo   - LD1 (RGB):          Green = Clearance ^| Blue = Neuromorphic Spike
echo.
echo ================================================================================
echo Starting Hardware Telemetry ^& Injection Engine...
echo ================================================================================
echo.

python hardware\run_live_hardware_product.py %*

echo.
echo ================================================================================
echo Hardware Execution Session Complete. Press any key to exit.
echo ================================================================================
pause
