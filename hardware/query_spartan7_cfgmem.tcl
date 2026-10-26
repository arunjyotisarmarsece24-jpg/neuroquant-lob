open_hw_manager
connect_hw_server -url localhost:3121
open_hw_target [lindex [get_hw_targets] 0]
set device [lindex [get_hw_devices xc7s25*] 0]
puts "CFGMEM PARTS SUPPORTED FOR SPARTAN-7 XC7S25:"
puts [get_cfgmem_parts -of_objects $device *s25fl*]
puts "ALL 128MB PARTS SUPPORTED FOR SPARTAN-7 XC7S25:"
puts [get_cfgmem_parts -of_objects $device *128*]
close_hw_manager
exit
