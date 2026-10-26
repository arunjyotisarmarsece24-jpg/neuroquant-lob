## ==============================================================================
## NEUROQUANT-LOB: DIGILENT ARTY S7-25 (SPARTAN-7) MASTER CONSTRAINTS (.XDC)
## ==============================================================================
## Board Target:   Digilent Arty S7-25 (XC7S25-CSGA324-1)
## Dual Interface: FTDI FT2232H USB-UART (COM9) + Arduino Nano PMOD JA (COM5)
## Standard:       IEEE 1364-2001 / Vivado Design Suite 2024.2+
## ==============================================================================

## -----------------------------------------------------------------------------
## 1. Primary Clock Definition (100.00 MHz Onboard Oscillator)
## -----------------------------------------------------------------------------
set_property -dict { PACKAGE_PIN R2    IOSTANDARD SSTL135 } [get_ports { clk_100mhz }];
create_clock -add -name sys_clk_pin -period 10.00 -waveform {0 5} [get_ports { clk_100mhz }];

## -----------------------------------------------------------------------------
## 2. Push Buttons & Slide Switches
## -----------------------------------------------------------------------------
# Active-Low Reset (Button 0 on Arty S7)
set_property -dict { PACKAGE_PIN C18   IOSTANDARD LVCMOS33 } [get_ports { btn_rst_n }];

# Button 1: Manual Neuromorphic Tick Injection
set_property -dict { PACKAGE_PIN K16   IOSTANDARD LVCMOS33 } [get_ports { btn_manual_tick }];

# Switch 0: Emergency Hardware System Killswitch Circuit Breaker
set_property -dict { PACKAGE_PIN H14   IOSTANDARD LVCMOS33 } [get_ports { sw_killswitch }];

# Switch 1: Bypass / Synthetic Tick Mode
set_property -dict { PACKAGE_PIN H18   IOSTANDARD LVCMOS33 } [get_ports { sw_bypass_parser }];

## -----------------------------------------------------------------------------
## 3. Physical Diagnostic Green LEDs (LD0 - LD3)
## -----------------------------------------------------------------------------
# LD0: Accelerator Ready
set_property -dict { PACKAGE_PIN E18   IOSTANDARD LVCMOS33 } [get_ports { led0_ready }];

# LD1: ESP8266 / Arduino Frame Synchronized (0x55AA Locked)
set_property -dict { PACKAGE_PIN F13   IOSTANDARD LVCMOS33 } [get_ports { led1_rx_sync }];

# LD2: Neuromorphic LIF Action Potential Spike Fired
set_property -dict { PACKAGE_PIN E13   IOSTANDARD LVCMOS33 } [get_ports { led2_spike }];

# LD3: Pre-Trade Risk Gate Approved Order
set_property -dict { PACKAGE_PIN H15   IOSTANDARD LVCMOS33 } [get_ports { led3_approved }];

## -----------------------------------------------------------------------------
## 4. RGB LED 0 (LD4 on Arty S7-25): J15=Red, G17=Green, F15=Blue
## -----------------------------------------------------------------------------
set_property -dict { PACKAGE_PIN J15   IOSTANDARD LVCMOS33 } [get_ports { rgb0_r }]; # Red: Breaker Tripped / Violation
set_property -dict { PACKAGE_PIN G17   IOSTANDARD LVCMOS33 } [get_ports { rgb0_g }]; # Green: System Normal / Ready
set_property -dict { PACKAGE_PIN F15   IOSTANDARD LVCMOS33 } [get_ports { rgb0_b }]; # Blue: Ingress Active

## -----------------------------------------------------------------------------
## 5. On-Board USB-UART Bridge (FTDI FT2232H Channel B -> Host PC COM9)
## -----------------------------------------------------------------------------
# V12: PC TX -> FPGA RX
set_property -dict { PACKAGE_PIN V12   IOSTANDARD LVCMOS33 PULLUP true } [get_ports { usb_uart_rx }];
# R12: FPGA TX -> PC RX
set_property -dict { PACKAGE_PIN R12   IOSTANDARD LVCMOS33 } [get_ports { usb_uart_tx }];

## -----------------------------------------------------------------------------
## 6. PMOD Header JA: High-Speed Serial Interface Option 1 (Arduino Nano)
## -----------------------------------------------------------------------------
# JA Pin 1 (Pin L17): UART RX from Arduino Nano TX
set_property -dict { PACKAGE_PIN L17   IOSTANDARD LVCMOS33 PULLUP true } [get_ports { ja_uart_rx }];

# JA Pin 2 (Pin L18): UART TX to Arduino Nano RX
set_property -dict { PACKAGE_PIN L18   IOSTANDARD LVCMOS33 } [get_ports { ja_uart_tx }];

# JA Pin 3 (Pin M14): Outbound Trade Execution Strobe
set_property -dict { PACKAGE_PIN M14   IOSTANDARD LVCMOS33 } [get_ports { ja_exec_strobe }];

# JA Pin 4 (Pin N14): Neuromorphic Spike Pulse Output
set_property -dict { PACKAGE_PIN N14   IOSTANDARD LVCMOS33 } [get_ports { ja_spike_strobe }];

## -----------------------------------------------------------------------------
## 7. Arduino / ChipKit Shield Female Header: Serial Interface Option 2 (Arduino Nano)
## -----------------------------------------------------------------------------
# Header IO0 (Pin L13): RX from Arduino Nano TX (Pin D1)
set_property -dict { PACKAGE_PIN L13   IOSTANDARD LVCMOS33 PULLUP true } [get_ports { ck_io0_rx }];

# Header IO1 (Pin N13): TX to Arduino Nano RX (Pin D0)
set_property -dict { PACKAGE_PIN N13   IOSTANDARD LVCMOS33 } [get_ports { ck_io1_tx }];

## -----------------------------------------------------------------------------
## 8. Timing Exceptions & Configuration Constraints
## -----------------------------------------------------------------------------
set_false_path -from [get_ports { sw_killswitch }]
set_false_path -from [get_ports { sw_bypass_parser }]
set_false_path -from [get_ports { btn_manual_tick }]
set_false_path -from [get_ports { btn_rst_n }]

# Quad-SPI Non-Volatile Boot Flash Constraints (Spansion S25FL128S on Arty S7)
set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 4 [current_design]
set_property BITSTREAM.CONFIG.CONFIGRATE 50 [current_design]
set_property CONFIG_VOLTAGE 3.3 [current_design]
set_property CFGBVS VCCO [current_design]
