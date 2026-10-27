# ==============================================================================
# NEUROQUANT-LOB: VIVADO INTERACTIVE DESIGN INSPECTION SCRIPT (SUPERVISOR DEMO)
# ==============================================================================
# Opens the fully routed checkpoint with complete silicon placement, routing,
# timing closure, and RTL schematic hierarchy for academic review.
# ==============================================================================

set dcp_file "./build_arty_s7/post_route.dcp"

if {[file exists $dcp_file]} {
    puts "================================================================================"
    puts "  OPENING FULLY ROUTED DESIGN CHECKPOINT: $dcp_file"
    puts "  Target FPGA: AMD Spartan-7 (xc7s25csga324-1)"
    puts "================================================================================"
    open_checkpoint $dcp_file
} else {
    puts "Checkpoint not found, elaborating RTL sources..."
    read_verilog hardware/lif_neuron_core.v
    read_verilog hardware/itch_parser_axi.v
    read_verilog hardware/risk_gate_core.v
    read_verilog hardware/neuroquant_fpga_top.v
    read_verilog hardware/uart_rx_bridge.v
    read_verilog hardware/uart_tx_telemetry.v
    read_verilog hardware/neuroquant_arty_s7_top.v
    read_xdc hardware/neuroquant_arty_s7.xdc
    synth_design -top neuroquant_arty_s7_top -part xc7s25csga324-1 -rtl
}

puts "LAUNCHING VIVADO GRAPHICAL USER INTERFACE..."
start_gui
