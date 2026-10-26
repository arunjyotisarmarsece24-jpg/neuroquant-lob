// ==============================================================================
// NEUROQUANT-LOB: HARDWARE FIX 4.4 PROTOCOL & PRE-TRADE RISK BRIDGE (DAY 5)
// ==============================================================================
// Principal Architect: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
// Target: AMD Xilinx Spartan-7 (xc7s25 / xc7s50) & UltraScale+
// Subsystems:
//   1. Byte-level FSM scanning FIX tags (35, 11, 55, 54, 38, 44, 10)
//   2. Real-time pre-trade risk gate evaluation
//   3. Cycle-accurate latency counter (Tick-to-ExecutionReport)
// ==============================================================================

`timescale 1ns / 1ps

`include "optimal_fix_params.vh"

module fix_engine_bridge #(
    parameter CLK_FREQ_HZ = 100_000_000
)(
    input  wire                   clk,
    input  wire                   rst_n,

    // Inbound Byte-Stream from Ethernet MAC / Host Serial
    input  wire [7:0]             in_byte,
    input  wire                   in_valid,
    output reg                    in_ready,

    // Decoded Order Signals
    output reg [7:0]              out_msg_type,
    output reg                    out_side,            // 1=Buy, 0=Sell
    output reg [31:0]             out_shares,
    output reg signed [31:0]      out_price,
    output reg [31:0]             out_order_ref,

    // Pre-Trade Risk Gate Controls & Status
    output reg                    out_eval_valid,
    input  wire                   risk_approved,
    input  wire [7:0]             risk_violation_code,

    // Outbound FIX ExecutionReport Telemetry
    output reg                    exec_report_valid,
    output reg                    exec_approved,
    output reg [7:0]              exec_violation_code,
    output reg [23:0]             exec_latency_cycles
);

    // FSM States
    localparam STATE_IDLE       = 3'd0;
    localparam STATE_TAG        = 3'd1;
    localparam STATE_VALUE      = 3'd2;
    localparam STATE_RISK_CHECK = 3'd3;
    localparam STATE_REPORT     = 3'd4;

    reg [2:0]  state;
    reg [15:0] current_tag;
    reg [31:0] current_value;
    reg [23:0] latency_counter;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state               <= STATE_IDLE;
            in_ready            <= 1'b1;
            out_msg_type        <= 8'h00;
            out_side            <= 1'b1;
            out_shares          <= 32'd0;
            out_price           <= 32'sd0;
            out_order_ref       <= 32'd0;
            out_eval_valid      <= 1'b0;
            exec_report_valid   <= 1'b0;
            exec_approved       <= 1'b0;
            exec_violation_code <= 8'h00;
            exec_latency_cycles <= 24'd0;
            current_tag         <= 16'd0;
            current_value       <= 32'd0;
            latency_counter     <= 24'd0;
        end else begin
            // Latency counter runs while order is in flight
            if (state != STATE_IDLE && state != STATE_REPORT) begin
                if (latency_counter < 24'hFFFFFF)
                    latency_counter <= latency_counter + 1'b1;
            end

            case (state)
                STATE_IDLE: begin
                    in_ready          <= 1'b1;
                    exec_report_valid <= 1'b0;
                    out_eval_valid    <= 1'b0;
                    current_tag       <= 16'd0;
                    current_value     <= 32'd0;
                    latency_counter   <= 24'd0;

                    if (in_valid) begin
                        latency_counter <= 24'd1;
                        if (in_byte >= 8'h30 && in_byte <= 8'h39) begin
                            current_tag <= {12'd0, in_byte[3:0]};
                            state       <= STATE_TAG;
                        end
                    end
                end

                STATE_TAG: begin
                    if (in_valid) begin
                        if (in_byte == `FIX_DELIM_EQUALS) begin
                            // Tag complete, transition to value
                            current_value <= 32'd0;
                            state         <= STATE_VALUE;
                        end else if (in_byte >= 8'h30 && in_byte <= 8'h39) begin
                            current_tag <= (current_tag * 10) + {12'd0, in_byte[3:0]};
                        end
                    end
                end

                STATE_VALUE: begin
                    if (in_valid) begin
                        if (in_byte == `FIX_DELIM_SOH) begin
                            // SOH delimiter reached
                            case (current_tag)
                                `FIX_TAG_SIDE:      out_side      <= (current_value == 32'd1); // 1=Buy
                                `FIX_TAG_ORDER_QTY: out_shares    <= current_value;
                                `FIX_TAG_PRICE:     out_price     <= current_value; // Q16.16 or cents
                                `FIX_TAG_CL_ORD_ID: out_order_ref <= current_value;
                                `FIX_TAG_CHECKSUM: begin
                                    // End of FIX message: trigger pre-trade risk gate!
                                    if (out_msg_type == `FIX_MSG_NEW_ORDER) begin
                                        state          <= STATE_RISK_CHECK;
                                        out_eval_valid <= 1'b1;
                                    end else begin
                                        state          <= STATE_REPORT;
                                    end
                                end
                            endcase
                            current_tag   <= 16'd0;
                            current_value <= 32'd0;
                            if (current_tag != `FIX_TAG_CHECKSUM) begin
                                state <= STATE_TAG;
                            end
                        end else begin
                            if (current_tag == `FIX_TAG_MSG_TYPE) begin
                                out_msg_type <= in_byte;
                            end else if (in_byte >= 8'h30 && in_byte <= 8'h39) begin
                                current_value <= (current_value * 10) + {28'd0, in_byte[3:0]};
                            end
                        end
                    end
                end

                STATE_RISK_CHECK: begin
                    out_eval_valid <= 1'b0;
                    // Risk Gate evaluates single-cycle response
                    exec_approved       <= risk_approved;
                    exec_violation_code <= risk_violation_code;
                    exec_latency_cycles <= latency_counter;
                    exec_report_valid   <= 1'b1;
                    state               <= STATE_REPORT;
                end

                STATE_REPORT: begin
                    // Strobe ExecutionReport for 1 cycle then return to idle
                    exec_report_valid <= 1'b0;
                    state             <= STATE_IDLE;
                end

                default: state <= STATE_IDLE;
            endcase
        end
    end

endmodule
