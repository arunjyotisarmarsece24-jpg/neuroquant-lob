// ==============================================================================
// NEUROQUANT-LOB: SYNTHESIZABLE FIX 4.4 PROTOCOL & LATENCY PARAMETERS (DAY 5)
// ==============================================================================
// Principal Architect: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
// Target: AMD Xilinx Spartan-7 / UltraScale+ Institutional FIX Gateway
// Standard: IEEE 1364-2001 Verilog HDL
// ==============================================================================

`ifndef OPTIMAL_FIX_PARAMS_VH
`define OPTIMAL_FIX_PARAMS_VH

// FIX Wire Delimiters
`define FIX_DELIM_SOH               8'h01       // Start of Header / Field Delimiter
`define FIX_DELIM_EQUALS            8'h3D       // '=' Character (ASCII 61)

// Standard FIX 4.4 Message Types
`define FIX_MSG_HEARTBEAT           8'h30       // '0' Heartbeat
`define FIX_MSG_NEW_ORDER           8'h44       // 'D' NewOrderSingle
`define FIX_MSG_EXEC_REPORT         8'h38       // '8' ExecutionReport
`define FIX_MSG_ORDER_CANCEL        8'h46       // 'F' OrderCancelRequest
`define FIX_MSG_CANCEL_REPLACE      8'h47       // 'G' OrderCancelReplaceRequest
`define FIX_MSG_REJECT              8'h33       // '3' Reject

// Tag Identifiers
`define FIX_TAG_MSG_TYPE            16'd35      // 35: MsgType
`define FIX_TAG_CL_ORD_ID           16'd11      // 11: ClOrdID
`define FIX_TAG_SYMBOL              16'd55      // 55: Symbol
`define FIX_TAG_SIDE                16'd54      // 54: Side (1=Buy, 2=Sell)
`define FIX_TAG_ORDER_QTY           16'd38      // 38: OrderQty
`define FIX_TAG_PRICE               16'd44      // 44: Price
`define FIX_TAG_CHECKSUM            16'd10      // 10: CheckSum

// Microsecond Latency Constraint Registers
`define MAX_LOOPBACK_CYCLES         24'd1000    // 1000 cycles @ 100MHz = 10.0 microseconds SLA
`define TARGET_P50_CYCLES           24'd350     // 350 cycles @ 100MHz = 3.50 microseconds target

`endif // OPTIMAL_FIX_PARAMS_VH
