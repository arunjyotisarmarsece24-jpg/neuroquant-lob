@echo off
title NEUROQUANT-LOB: VIVADO FPGA DESIGN ^& SCHEMATIC INSPECTION (SUPERVISOR DEMO)
color 0B
cd /d "%~dp0"

echo ================================================================================
echo   NEUROQUANT-LOB: VIVADO GRAPHICAL USER INTERFACE LAUNCHER
echo   Principal Architect: Arunjyoti Sarma ^| Electronics Engineering, IIT (BHU)
echo   Target Silicon: AMD Spartan-7 XC7S25 (Digilent Arty S7-25)
echo ================================================================================
echo.
echo Launching Vivado GUI with fully placed ^& routed hardware design...
echo   - RTL Schematic: Available in Tools -^> Schematic
echo   - Device View:   Physical Spartan-7 silicon floorplan ^& routing
echo   - Timing Report: WNS = +0.894 ns @ 322 MHz
echo   - Utilization:   1.64%% LUTs, 0 DSPs (Pure Integer ALU)
echo.

"C:\Xilinx\Vivado\2024.2\bin\vivado.bat" -mode gui -source hardware/open_vivado_design.tcl

echo.
echo Vivado session closed. Press any key to exit.
pause
