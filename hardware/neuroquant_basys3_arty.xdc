## ==============================================================================
## NEUROQUANT-LOB: XILINX VIVADO PHYSICAL CONSTRAINTS FILE (.XDC)
## ==============================================================================
## Target Boards: Digilent Arty A7-35T / Arty A7-100T / Basys3 (XC7A35T / XC7A100T)
## Target Clock:  100.00 MHz Primary Clock (10.00 ns Period)
## Standard:      IEEE 1364-2001 / Vivado Design Suite
## ==============================================================================

## -----------------------------------------------------------------------------
## 1. Primary Clock Definition (100 MHz onboard oscillator)
## -----------------------------------------------------------------------------
set_property -dict { PACKAGE_PIN E3    IOSTANDARD LVCMOS33 } [get_ports { clk }];
create_clock -add -name sys_clk_pin -period 10.00 -waveform {0 5} [get_ports { clk }];

## -----------------------------------------------------------------------------
## 2. Reset Button & Emergency Switch Inputs
## -----------------------------------------------------------------------------
# Active-low Master Reset (Button 0 or Active-Low CPU Reset Pin C2)
set_property -dict { PACKAGE_PIN C2    IOSTANDARD LVCMOS33 } [get_ports { rst_n }];

# Switch 0: Emergency System Killswitch Circuit Breaker
set_property -dict { PACKAGE_PIN A8    IOSTANDARD LVCMOS33 } [get_ports { sw_emergency_killswitch }];

# Button 1: Manual Neuromorphic Tick Injection
set_property -dict { PACKAGE_PIN D9    IOSTANDARD LVCMOS33 } [get_ports { i_manual_trigger }];

## -----------------------------------------------------------------------------
## 3. Physical Diagnostic Output LEDs
## -----------------------------------------------------------------------------
# LED 0 (Green): System Initialized & Neuromorphic Ready
set_property -dict { PACKAGE_PIN H5    IOSTANDARD LVCMOS33 } [get_ports { led_ready }];

# LED 1 (Blue): NASDAQ ITCH Packet Decoded Wire Strobe
set_property -dict { PACKAGE_PIN J5    IOSTANDARD LVCMOS33 } [get_ports { led_itch_valid }];

# LED 2 (Yellow): Neuromorphic Action Potential Spike Fired
set_property -dict { PACKAGE_PIN T9    IOSTANDARD LVCMOS33 } [get_ports { led_spike }];

# LED 3 (Green): Pre-Trade Risk Gate Approved Order
set_property -dict { PACKAGE_PIN T10   IOSTANDARD LVCMOS33 } [get_ports { led_order_approved }];

# RGB LED 0 Red: Circuit Breaker Violation Strobe
set_property -dict { PACKAGE_PIN E1    IOSTANDARD LVCMOS33 } [get_ports { led_risk_violated }];

# RGB LED 1 (R, G, B): Violation Code [2:0]
set_property -dict { PACKAGE_PIN G6    IOSTANDARD LVCMOS33 } [get_ports { led_violation_code[0] }];
set_property -dict { PACKAGE_PIN F6    IOSTANDARD LVCMOS33 } [get_ports { led_violation_code[1] }];
set_property -dict { PACKAGE_PIN E2    IOSTANDARD LVCMOS33 } [get_ports { led_violation_code[2] }];

## -----------------------------------------------------------------------------
## 4. PMOD Header JA: Outbound Execution Signal to Network Subsystem
## -----------------------------------------------------------------------------
set_property -dict { PACKAGE_PIN G13   IOSTANDARD LVCMOS33 } [get_ports { o_trade_out_valid }];

## -----------------------------------------------------------------------------
## 5. Timing & False Paths
## -----------------------------------------------------------------------------
# Asynchronous inputs do not need tight setup constraints
set_false_path -from [get_ports { sw_emergency_killswitch }]
set_false_path -from [get_ports { i_manual_trigger }]
set_false_path -from [get_ports { rst_n }]
