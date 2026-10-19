// =============================================================================
// NEUROQUANT-LOB: AXI4-STREAM NASDAQ TOTALVIEW-ITCH 5.0 HARDWARE FEED PARSER
// =============================================================================
// Principal Architect: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
// Target Architecture: AMD Alveo U50 / Xilinx UltraScale+ (322.26 MHz 10GbE Clock)
// Standard: IEEE 1364-2001 Verilog HDL
// Description:
//   Zero-latency cycle-accurate hardware packet unpacker operating over a 64-bit
//   AXI4-Stream network interface. Directly extracts Order Reference ID, Side,
//   Quantity, and Price in fixed cycles (15.5 ns at 322 MHz) with zero software
//   or OS kernel bypass overhead.
// =============================================================================

`timescale 1ns / 1ps

module itch_parser_axi #(
    parameter DATA_WIDTH = 64
)(
    input  wire                   clk,
    input  wire                   rst_n,

    // AXI4-Stream Slave Interface (from 10GbE MAC / DMA Subsystem)
    input  wire [DATA_WIDTH-1:0]  s_axis_tdata,
    input  wire [7:0]             s_axis_tkeep,
    input  wire                   s_axis_tvalid,
    output wire                   s_axis_tready,
    input  wire                   s_axis_tlast,

    // Decoded Microstructure Event Output Registers
    output reg                    out_valid,
    output reg  [7:0]             out_msg_type,    // 'A'=Add, 'E'=Exec, 'C'=ExecPrice, 'X'=Cancel, 'D'=Delete
    output reg  [63:0]            out_order_ref,   // 64-bit unique Order Reference ID
    output reg                    out_buy_sell,    // 1 = BUY ('B'), 0 = SELL ('S')
    output reg  [31:0]            out_shares,      // Number of shares
    output reg  [31:0]            out_price,       // Fixed-point price (4 decimal places, e.g. $65000.00 = 650000000)
    output reg  [47:0]            out_timestamp,   // Nanoseconds since midnight
    output reg  [15:0]            out_stock_locate // Locate code
);

    // State machine encodings
    localparam STATE_IDLE         = 3'd0;
    localparam STATE_PARSE_A_B1   = 3'd1;
    localparam STATE_PARSE_A_B2   = 3'd2;
    localparam STATE_PARSE_A_B3   = 3'd3;
    localparam STATE_PARSE_A_B4   = 3'd4;
    localparam STATE_PARSE_D_B1   = 3'd5;
    localparam STATE_PARSE_D_B2   = 3'd6;

    reg [2:0] state;

    // Ready signal: Can accept streaming beats continuously
    assign s_axis_tready = 1'b1;

    // Temporary assembly registers
    reg [23:0]  temp_ts_hi;
    reg [39:0]  temp_ref_hi;
    reg [7:0]   curr_type;
    reg [15:0]  curr_locate;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state            <= STATE_IDLE;
            out_valid        <= 1'b0;
            out_msg_type     <= 8'h00;
            out_order_ref    <= 64'd0;
            out_buy_sell     <= 1'b0;
            out_shares       <= 32'd0;
            out_price        <= 32'd0;
            out_timestamp    <= 48'd0;
            out_stock_locate <= 16'd0;
            temp_ts_hi       <= 24'd0;
            temp_ref_hi      <= 40'd0;
            curr_type        <= 8'h00;
            curr_locate      <= 16'd0;
        end else begin
            // Default pulse deassertion
            out_valid <= 1'b0;

            if (s_axis_tvalid && s_axis_tready) begin
                case (state)
                    STATE_IDLE: begin
                        curr_type    <= s_axis_tdata[63:56];
                        curr_locate  <= s_axis_tdata[55:40];
                        // Tracking number is in [39:24]
                        temp_ts_hi   <= s_axis_tdata[23:0]; // high 24 bits of 48-bit timestamp

                        if (s_axis_tdata[63:56] == 8'h41) begin
                            // Type 'A': Add Order (36 bytes total, 5 beats on 64-bit bus)
                            state <= STATE_PARSE_A_B1;
                        end else if (s_axis_tdata[63:56] == 8'h44) begin
                            // Type 'D': Order Delete (19 bytes total, 3 beats on 64-bit bus)
                            state <= STATE_PARSE_D_B1;
                        end else begin
                            state <= STATE_IDLE;
                        end
                    end

                    // -------------------------------------------------------------
                    // Parse 'A' (Add Order) Beats
                    // -------------------------------------------------------------
                    STATE_PARSE_A_B1: begin
                        // Beat 1:
                        // [63:40] = Timestamp low (24 bits)
                        // [39:0]  = Order Reference high (40 bits)
                        out_timestamp <= {temp_ts_hi, s_axis_tdata[63:40]};
                        temp_ref_hi   <= s_axis_tdata[39:0];
                        state         <= STATE_PARSE_A_B2;
                    end

                    STATE_PARSE_A_B2: begin
                        // Beat 2:
                        // [63:40] = Order Reference low (24 bits) -> completes 64-bit ref
                        // [39:32] = Buy/Sell Indicator ('B'=0x42, 'S'=0x53)
                        // [31:0]  = Quantity / Shares (32 bits)
                        out_order_ref <= {temp_ref_hi, s_axis_tdata[63:40]};
                        out_buy_sell  <= (s_axis_tdata[39:32] == 8'h42); // 1 if BUY ('B')
                        out_shares    <= s_axis_tdata[31:0];
                        state         <= STATE_PARSE_A_B3;
                    end

                    STATE_PARSE_A_B3: begin
                        // Beat 3:
                        // [63:0] = Stock Symbol (8 ASCII bytes, e.g. "AAPL    ")
                        state <= STATE_PARSE_A_B4;
                    end

                    STATE_PARSE_A_B4: begin
                        // Beat 4:
                        // [63:32] = Price (32 bits, 4 decimal places)
                        // [31:0]  = Reserved / Next message prefix
                        out_msg_type     <= curr_type;
                        out_stock_locate <= curr_locate;
                        out_price        <= s_axis_tdata[63:32];
                        out_valid        <= 1'b1; // Trigger downstream trading core strobe!
                        state            <= STATE_IDLE;
                    end

                    // -------------------------------------------------------------
                    // Parse 'D' (Order Delete) Beats
                    // -------------------------------------------------------------
                    STATE_PARSE_D_B1: begin
                        // Beat 1:
                        // [63:40] = Timestamp low (24 bits)
                        // [39:0]  = Order Reference high (40 bits)
                        out_timestamp <= {temp_ts_hi, s_axis_tdata[63:40]};
                        temp_ref_hi   <= s_axis_tdata[39:0];
                        state         <= STATE_PARSE_D_B2;
                    end

                    STATE_PARSE_D_B2: begin
                        // Beat 2:
                        // [63:40] = Order Reference low (24 bits)
                        out_order_ref    <= {temp_ref_hi, s_axis_tdata[63:40]};
                        out_msg_type     <= curr_type;
                        out_stock_locate <= curr_locate;
                        out_buy_sell     <= 1'b0;
                        out_shares       <= 32'd0;
                        out_price        <= 32'd0;
                        out_valid        <= 1'b1; // Strobe deletion downstream!
                        state            <= STATE_IDLE;
                    end

                    default: state <= STATE_IDLE;
                endcase
            end
        end
    end

endmodule
