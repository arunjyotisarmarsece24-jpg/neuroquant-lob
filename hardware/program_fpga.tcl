# ==============================================================================
# NEUROQUANT-LOB: DIRECT JTAG PROGRAMMER FOR DIGILENT ARTY S7-25
# ==============================================================================
open_hw_manager
connect_hw_server -url localhost:3121
set targets [get_hw_targets]
if {[llength $targets] == 0} {
    puts "[-] Error: No JTAG targets found on localhost:3121!"
    exit 1
}

current_hw_target [lindex $targets 0]
open_hw_target
set device [lindex [get_hw_devices xc7s25*] 0]
if {$device == ""} {
    puts "[-] Error: xc7s25 silicon device not found in JTAG chain!"
    exit 1
}

current_hw_device $device
puts "[+] Detected FPGA Device: $device"

set bitfile "./build_arty_s7/neuroquant_arty_s7.bit"
if {[file exists $bitfile]} {
    puts "[*] Flashing bitstream: $bitfile to $device..."
    set_property PROGRAM.FILE $bitfile $device
    program_hw_devices $device
    puts "[+] SUCCESS! FPGA Bitstream written to SRAM. Diagnostic LEDs are now ACTIVE!"
} else {
    puts "[-] Error: Bitstream file $bitfile does not exist. Run synthesis first."
}

close_hw_target
disconnect_hw_server
close_hw_manager
exit
