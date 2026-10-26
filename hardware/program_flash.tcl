# ==============================================================================
# NEUROQUANT-LOB: PERMANENT SPI FLASH PROGRAMMER FOR DIGILENT ARTY S7-25
# ==============================================================================
open_hw_manager
connect_hw_server -url localhost:3121
current_hw_target [lindex [get_hw_targets] 0]
open_hw_target
set device [lindex [get_hw_devices xc7s25*] 0]
current_hw_device $device

# Create configuration memory object for Spansion S25FL128S Quad-SPI Flash (exact part string)
set cfg_part [lindex [get_cfgmem_parts {s25fl128sxxxxxx0-spi-x1_x2_x4}] 0]
puts "USING CFGMEM PART: $cfg_part"
create_hw_cfgmem -hw_device $device $cfg_part

set_property PROGRAM.BLANK_CHECK  0 [ get_property PROGRAM.HW_CFGMEM $device ]
set_property PROGRAM.ERASE        1 [ get_property PROGRAM.HW_CFGMEM $device ]
set_property PROGRAM.CFG_PROGRAM  1 [ get_property PROGRAM.HW_CFGMEM $device ]
set_property PROGRAM.VERIFY       1 [ get_property PROGRAM.HW_CFGMEM $device ]
set_property PROGRAM.CHECKSUM     0 [ get_property PROGRAM.HW_CFGMEM $device ]

set_property PROGRAM.ADDRESS_RANGE  {use_file} [ get_property PROGRAM.HW_CFGMEM $device ]
set_property PROGRAM.FILES [list "./build_arty_s7/neuroquant_arty_s7.bin"] [ get_property PROGRAM.HW_CFGMEM $device ]
set_property PROGRAM.PRM_FILE {./build_arty_s7/neuroquant_arty_s7.prm} [ get_property PROGRAM.HW_CFGMEM $device ]

puts "WRITING TO NON-VOLATILE SPI FLASH MEMORY..."
program_hw_cfgmem -hw_cfgmem [ get_property PROGRAM.HW_CFGMEM $device ]
puts "SUCCESS: Written to Flash! Board will now permanently boot NeuroQuant-LOB on power-up!"

boot_hw_device $device
close_hw_target
disconnect_hw_server
close_hw_manager
exit
