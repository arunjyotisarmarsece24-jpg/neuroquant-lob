# ==============================================================================
# NEUROQUANT-LOB: AUTOMATED VIVADO BITSTREAM & SPI FLASH BUILD SCRIPT
# ==============================================================================
# Target Board: Digilent Arty S7-50 / Arty S7-25
# Target FPGA:  Xilinx Spartan-7 (xc7s50csga324-1 or xc7s25csga324-1)
# Usage:
#   vivado -mode batch -source hardware/build_arty_s7_bitstream.tcl
# ==============================================================================

set outputDir ./build_arty_s7
file mkdir $outputDir

# Target part: default to xc7s50csga324-1 (Arty S7-50)
# Change to xc7s25csga324-1 if using Arty S7-25
set_part xc7s50csga324-1

puts "================================================================================"
puts "  NEUROQUANT-LOB: COMPILING ARTY S7 BITSTREAM VIA VIVADO"
puts "  Target Architecture: Xilinx Spartan-7 (xc7s50csga324-1)"
puts "================================================================================"

# Read Verilog Design Sources
read_verilog hardware/lif_neuron_core.v
read_verilog hardware/itch_parser_axi.v
read_verilog hardware/risk_gate_core.v
read_verilog hardware/neuroquant_fpga_top.v
read_verilog hardware/uart_rx_bridge.v
read_verilog hardware/uart_tx_telemetry.v
read_verilog hardware/neuroquant_arty_s7_top.v

# Read Physical Constraints
read_xdc hardware/neuroquant_arty_s7.xdc

# 1. Synthesis
puts "\n[*] STEP 1: Running Synthesis (Top: neuroquant_arty_s7_top)..."
synth_design -top neuroquant_arty_s7_top -part xc7s50csga324-1 -flatten_hierarchy rebuilt
write_checkpoint -force $outputDir/post_synth.dcp
report_utilization -file $outputDir/post_synth_utilization.rpt

# 2. Logic Optimization & Placement
puts "\n[*] STEP 2: Running Logic Optimization & Physical Placement..."
opt_design
place_design
phys_opt_design
write_checkpoint -force $outputDir/post_place.dcp

# 3. Routing
puts "\n[*] STEP 3: Running Detailed Routing..."
route_design
write_checkpoint -force $outputDir/post_route.dcp

# 4. Reports & Timing Closure
puts "\n[*] STEP 4: Evaluating Timing Closure & Clock Slack..."
report_timing_summary -file $outputDir/timing_summary.rpt
report_utilization -file $outputDir/final_utilization.rpt
report_power -file $outputDir/power_analysis.rpt

# 5. Generate Bitstream & Quad-SPI Flash .bin File
puts "\n[*] STEP 5: Generating FPGA Bitstream & Non-Volatile Quad-SPI .bin Image..."
set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 4 [current_design]
set_property BITSTREAM.CONFIG.CONFIGRATE 50 [current_design]
set_property BITSTREAM.GENERAL.COMPRESS TRUE [current_design]

write_bitstream -force $outputDir/neuroquant_arty_s7.bit
write_cfgmem -format bin -size 16 -interface SPIx4 -loadbit "up 0x00000000 $outputDir/neuroquant_arty_s7.bit" -file $outputDir/neuroquant_arty_s7.bin -force

puts "================================================================================"
puts "  [SUCCESS] ARTY S7 BITSTREAM BUILD COMPLETE!"
puts "  FPGA Bitstream:       $outputDir/neuroquant_arty_s7.bit"
puts "  Quad-SPI Flash Image: $outputDir/neuroquant_arty_s7.bin"
puts "  Timing Report:        $outputDir/timing_summary.rpt"
puts "  Utilization Report:   $outputDir/final_utilization.rpt"
puts "================================================================================"
exit
