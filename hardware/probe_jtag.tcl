open_hw_manager
connect_hw_server -url localhost:3121
puts "=========================================================="
puts "  JTAG TARGET SCAN VIA VIVADO HARDWARE MANAGER"
puts "=========================================================="
set targets [get_hw_targets]
puts "Hardware Targets Found: $targets"

if {[llength $targets] > 0} {
    current_hw_target [lindex $targets 0]
    open_hw_target
    set devices [get_hw_devices]
    puts "Detected FPGA Silicon Devices: $devices"
    foreach dev $devices {
        puts "  -> Device Name: $dev"
        puts "  -> Device Part: [get_property PART $dev]"
        puts "  -> Is Programmed: [get_property IS_PROG $dev]"
    }
    close_hw_target
} else {
    puts "No JTAG targets detected on localhost:3121. Check USB cable and drivers."
}

disconnect_hw_server
close_hw_manager
exit
