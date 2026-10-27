@echo off
title NEUROQUANT-LOB: ENTERPRISE ARTY S7 FPGA + ARDUINO NANO HARDWARE PRODUCT
color 0A
cd /d "%~dp0"

echo ================================================================================
echo   NEUROQUANT-LOB: PHYSICAL FPGA ACCELERATOR ^& ARDUINO NANO HARDWARE PRODUCT
echo   Architect: Arunjyoti Sarma ^| Department of Electronics Engineering, IIT (BHU)
echo   Target Silicon: AMD Spartan-7 XC7S25-CSGA324 (Digilent Arty S7-25)
echo ================================================================================
echo.
echo [HARDWARE INTERCONNECT CONFIGURATION]
echo   - Microcontroller Sidecar: Arduino Nano ATmega328P (COM8)
echo   - Institutional FPGA:     Digilent Arty S7-25 (COM9)
echo   - Wire Handshake:
echo       Arduino TX1 (Pin D1)  ---^>  Arty S7 Shield IO0 (Pin L13) [FPGA RX Ingress]
echo       Arduino RX0 (Pin D0)  ^<---  Arty S7 Shield IO1 (Pin N13) [FPGA TX Telemetry]
echo       Arduino GND           ^<---^>  Arty S7 GND
echo.
echo [PHYSICAL LED DIAGNOSTIC MAPPING]
echo   - LD2 (Single Yellow): 1.0 Hz Double-Blink Heartbeat (Proves 100MHz PLL Active)
echo   - LD3 (Single Yellow): Packet Ingress Strobe (Sharp 30ms pulse on ITCH frame)
echo   - LD4 (Single Yellow): Neuromorphic LIF Action Potential Spike Strobe
echo   - LD5 (Single Yellow): Pre-Trade Gate Approved Trade Clearance Strobe
echo   - LD0 (RGB LED):       Calm GREEN = Operational ^| Blinding 4Hz RED = Circuit Breaker
echo   - LD1 (RGB LED):       Electric BLUE = Neuromorphic Spike ^| GREEN = Trade Cleared
echo.
echo ================================================================================
echo Launching Interactive Hardware Management Suite...
echo ================================================================================
echo.

python hardware\interactive_hardware_suite.py %*

echo.
echo ================================================================================
echo Hardware Execution Terminated. Press any key to exit.
echo ================================================================================
pause
