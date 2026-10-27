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
echo   - LD2 (Yellow):       1.0 Hz Double-Blink Heartbeat (100 MHz Alive)
echo   - LD3 (Yellow Pulse): Ingress Stream 0x55AA Frame Lock Strobe
echo   - LD4 (Yellow Pulse): Neuromorphic LIF Action Potential Spike Strobe
echo   - LD5 (Yellow Pulse): Pre-Trade Gate Approved Trade Clearance Strobe
echo   - LD0 (RGB):          Calm Green = Ready ^| Blinding 4Hz Flashing Red = Risk Breach
echo   - LD1 (RGB):          Electric Blue = LIF Spike ^| Green = Clearance
echo.
echo ================================================================================
echo Starting Hardware Telemetry ^& Injection Engine...
echo ================================================================================
echo.

python hardware\interactive_hardware_suite.py %*

echo.
echo ================================================================================
echo Hardware Execution Session Complete. Press any key to exit.
echo ================================================================================
pause
