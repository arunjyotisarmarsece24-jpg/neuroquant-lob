## ==============================================================================
## NEUROQUANT-LOB: DIGILENT ARTY S7-25 (SPARTAN-7 CSGA324) MASTER CONSTRAINTS (.XDC)
## ==============================================================================
## Principal Architect: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
## Board Target:   Digilent Arty S7-25 (XC7S25-CSGA324-1)
## Reference:      Official Digilent Arty-S7-25-Master.xdc
## Interfaces:     FTDI FT2232H USB-UART (COM9) + Arduino Nano Shield (COM5) + PMOD JA
## ==============================================================================

## -----------------------------------------------------------------------------
## 1. Primary Clock Definition (100.00 MHz Onboard Oscillator)
## -----------------------------------------------------------------------------
set_property -dict { PACKAGE_PIN R2    IOSTANDARD SSTL135 } [get_ports { clk_100mhz }];
create_clock -add -name sys_clk_pin -period 10.00 -waveform {0 5} [get_ports { clk_100mhz }];

## -----------------------------------------------------------------------------
## 2. Push Buttons & Reset
## -----------------------------------------------------------------------------
# Red Push-Button labeled "RESET" on board (Active-Low logic reset, needs internal PULLUP)
set_property -dict { PACKAGE_PIN C18   IOSTANDARD LVCMOS33 PULLUP true } [get_ports { btn_rst_n }];

# Push-Button 0 (BTN0): Manual Normal Tick Injection
set_property -dict { PACKAGE_PIN G15   IOSTANDARD LVCMOS33 } [get_ports { btn_manual_tick }];

# Push-Button 1 (BTN1): Manual Fat-Finger Violation Injection (Triggers Red LED)
set_property -dict { PACKAGE_PIN K16   IOSTANDARD LVCMOS33 } [get_ports { btn1_stress }];

# Push-Button 2 (BTN2): Manual LIF Action Potential Spike
set_property -dict { PACKAGE_PIN J16   IOSTANDARD LVCMOS33 } [get_ports { btn2_spike }];

# Push-Button 3 (BTN3): Reset Hardware Statistics Counter
set_property -dict { PACKAGE_PIN H13   IOSTANDARD LVCMOS33 } [get_ports { btn3_clear }];

## -----------------------------------------------------------------------------
## 3. Slide Switches (SW0 - SW3)
## -----------------------------------------------------------------------------
# Switch 0 (SW0): Emergency Hardware System Killswitch Circuit Breaker (Up = Tripped)
set_property -dict { PACKAGE_PIN H14   IOSTANDARD LVCMOS33 } [get_ports { sw_killswitch }];

# Switch 1 (SW1): Autonomous Hardware Self-Test Mode (Up = 5Hz Autonomous Tick Generator)
set_property -dict { PACKAGE_PIN H18   IOSTANDARD LVCMOS33 } [get_ports { sw_bypass_parser }];

# Switch 2 (SW2): Risk Collar Stress Mode (Up = Tight $50 collar)
set_property -dict { PACKAGE_PIN G18   IOSTANDARD LVCMOS33 } [get_ports { sw2_tight_collar }];

# Switch 3 (SW3): Reserved Bank 34 Switch (SSTL135)
set_property -dict { PACKAGE_PIN M5    IOSTANDARD SSTL135  } [get_ports { sw3_reserved }];

## -----------------------------------------------------------------------------
## 4. User Discrete Single-Color (Yellow) LEDs (Silkscreen LD2, LD3, LD4, LD5)
## -----------------------------------------------------------------------------
# LD2 (Schematic Sch=led[2]): Heartbeat / Accelerator Engine Ready (Steady Yellow)
set_property -dict { PACKAGE_PIN E18   IOSTANDARD LVCMOS33 } [get_ports { led0_ready }];

# LD3 (Schematic Sch=led[3]): Serial Ingress Stream Active & 0x55AA Lock (Flashing Yellow)
set_property -dict { PACKAGE_PIN F13   IOSTANDARD LVCMOS33 } [get_ports { led1_rx_sync }];

# LD4 (Schematic Sch=led[4]): Neuromorphic LIF Spike Fired (Flashing Yellow)
set_property -dict { PACKAGE_PIN E13   IOSTANDARD LVCMOS33 } [get_ports { led2_spike }];

# LD5 (Schematic Sch=led[5]): Pre-Trade Risk Gate Approved Order (Flashing Yellow)
set_property -dict { PACKAGE_PIN H15   IOSTANDARD LVCMOS33 } [get_ports { led3_approved }];

## -----------------------------------------------------------------------------
## 5. RGB LED 0 (Silkscreen LD0): J15=Red, G17=Green, F15=Blue
## -----------------------------------------------------------------------------
# LD0 Red: Circuit Breaker Tripped / Fat-Finger Breach
set_property -dict { PACKAGE_PIN J15   IOSTANDARD LVCMOS33 } [get_ports { rgb0_r }];
# LD0 Green: Engine System Operational & Ready (Quiescent Calm Green)
set_property -dict { PACKAGE_PIN G17   IOSTANDARD LVCMOS33 } [get_ports { rgb0_g }];
# LD0 Blue: Serial Ingress Byte Ingestion (Pulses Blue on incoming byte)
set_property -dict { PACKAGE_PIN F15   IOSTANDARD LVCMOS33 } [get_ports { rgb0_b }];

## -----------------------------------------------------------------------------
## 6. RGB LED 1 (Silkscreen LD1): E15=Red, F18=Green, E14=Blue
## -----------------------------------------------------------------------------
# LD1 Red: Price Impact / Volatility Threshold Alert
set_property -dict { PACKAGE_PIN E15   IOSTANDARD LVCMOS33 } [get_ports { rgb1_r }];
# LD1 Green: Execution Approved Strobe
set_property -dict { PACKAGE_PIN F18   IOSTANDARD LVCMOS33 } [get_ports { rgb1_g }];
# LD1 Blue: Neuromorphic LIF Spike Strobe
set_property -dict { PACKAGE_PIN E14   IOSTANDARD LVCMOS33 } [get_ports { rgb1_b }];

## -----------------------------------------------------------------------------
## 7. On-Board USB-UART Bridge (FTDI FT2232H Channel B -> Host PC COM9)
## -----------------------------------------------------------------------------
# V12: PC TX -> FPGA RX (Pullup ensures idle High)
set_property -dict { PACKAGE_PIN V12   IOSTANDARD LVCMOS33 PULLUP true } [get_ports { usb_uart_rx }];
# R12: FPGA TX -> PC RX
set_property -dict { PACKAGE_PIN R12   IOSTANDARD LVCMOS33 } [get_ports { usb_uart_tx }];

## -----------------------------------------------------------------------------
## 8. PMOD Header JA: High-Speed Serial Interface Option 1 (Arduino Nano)
## -----------------------------------------------------------------------------
# JA Pin 1 (Pin L17): UART RX from Arduino Nano TX1
set_property -dict { PACKAGE_PIN L17   IOSTANDARD LVCMOS33 PULLUP true } [get_ports { ja_uart_rx }];
# JA Pin 2 (Pin L18): UART TX to Arduino Nano RX0
set_property -dict { PACKAGE_PIN L18   IOSTANDARD LVCMOS33 } [get_ports { ja_uart_tx }];
# JA Pin 3 (Pin M14): Outbound Trade Execution Strobe
set_property -dict { PACKAGE_PIN M14   IOSTANDARD LVCMOS33 } [get_ports { ja_exec_strobe }];
# JA Pin 4 (Pin N14): Neuromorphic Spike Pulse Output
set_property -dict { PACKAGE_PIN N14   IOSTANDARD LVCMOS33 } [get_ports { ja_spike_strobe }];

## -----------------------------------------------------------------------------
## 9. Arduino / ChipKit Shield Female Header: Serial Interface Option 2 (Arduino Nano)
## -----------------------------------------------------------------------------
# Header IO0 (Pin L13): RX from Arduino Nano TX1 (Pin D1)
set_property -dict { PACKAGE_PIN L13   IOSTANDARD LVCMOS33 PULLUP true } [get_ports { ck_io0_rx }];
# Header IO1 (Pin N13): TX to Arduino Nano RX0 (Pin D0)
set_property -dict { PACKAGE_PIN N13   IOSTANDARD LVCMOS33 } [get_ports { ck_io1_tx }];

## -----------------------------------------------------------------------------
## 10. Timing Exceptions & Configuration Constraints
## -----------------------------------------------------------------------------
# Internal VREF for Bank 34 (SSTL135 switch / memory standard)
set_property INTERNAL_VREF 0.675 [get_iobanks 34]

set_false_path -from [get_ports { sw_killswitch sw_bypass_parser sw2_tight_collar sw3_reserved }]
set_false_path -from [get_ports { btn_rst_n btn_manual_tick btn1_stress btn2_spike btn3_clear }]

# Quad-SPI Non-Volatile Boot Flash Constraints (Spansion S25FL128S on Arty S7)
set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 4 [current_design]
set_property BITSTREAM.CONFIG.CONFIGRATE 50 [current_design]
set_property CONFIG_VOLTAGE 3.3 [current_design]
set_property CFGBVS VCCO [current_design]
