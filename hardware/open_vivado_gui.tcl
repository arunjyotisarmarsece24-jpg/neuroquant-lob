# ==============================================================================
# NEUROQUANT-LOB: LAUNCH VIVADO HARDWARE MANAGER GUI
# ==============================================================================
open_hw_manager
catch { connect_hw_server -url localhost:3121 }
set targets [get_hw_targets]
if {[llength $targets] > 0} {
    current_hw_target [lindex $targets 0]
    open_hw_target
    set device [lindex [get_hw_devices xc7s25*] 0]
    if {$device != ""} {
        current_hw_device $device
        puts "CONNECTED TO ARTY S7 SILICON: $device"
    }
}
start_gui
