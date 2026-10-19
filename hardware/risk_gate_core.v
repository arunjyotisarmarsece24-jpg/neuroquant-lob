// =============================================================================
// NEUROQUANT-LOB: PRE-TRADE HARDWARE RISK GATE CORE (1 CLOCK CYCLE < 3.5 NS)
// =============================================================================
// Principal Architect: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
// Target Architecture: AMD Alveo U50 / Xilinx UltraScale+ (322.26 MHz clock)
// Standard: IEEE 1364-2001 Verilog HDL
// Description:
//   Zero-allocation hardware gate evaluating deterministic pre-trade risk checks
//   in a single pipelined clock cycle:
//     1. Emergency System Killswitch
//     2. Fat-Finger Price Collar (|P_order - P_mid| <= delta)
//     3. Maximum Single Order Size (Qty <= max_size)
//     4. Portfolio Inventory Collar (|Inv + Side*Qty| <= max_inv) with de-risking bypass
//     5. Hard MTM Drawdown Circuit Breaker (Unrealized PnL >= -threshold)
//     6. Gronwall Lyapunov Stability Invariant (|V_m - V_rest| <= 50 mV, Theorem 1)
// =============================================================================

`timescale 1ns / 1ps

module risk_gate_core (
    input  wire                   clk,
    input  wire                   rst_n,

    // Order Evaluation Strobe & Attributes
    input  wire                   eval_valid,
    input  wire                   order_side,          // 1 = BUY, 0 = SELL
    input  wire signed [31:0]     order_qty,           // Contracts / Shares
    input  wire signed [31:0]     order_price,         // Signed Q16.16
    input  wire signed [31:0]     market_mid_price,    // Signed Q16.16
    input  wire signed [31:0]     current_inventory,   // Signed integer
    input  wire signed [31:0]     current_mtm_pnl,     // Signed Q16.16
    input  wire signed [31:0]     membrane_voltage,    // Signed Q16.16

    // Institutional Risk Limit Registers
    input  wire                   emergency_killswitch,
    input  wire signed [31:0]     cfg_max_order_size,
    input  wire signed [31:0]     cfg_max_inventory,
    input  wire signed [31:0]     cfg_collar_threshold,   // e.g. 1.5% in Q16.16
    input  wire signed [31:0]     cfg_drawdown_limit,     // e.g. -$50,000 in Q16.16
    input  wire signed [31:0]     cfg_v_resting,          // -70.0 mV in Q16.16
    input  wire signed [31:0]     cfg_lyapunov_threshold, // 50.0 mV in Q16.16

    // Single-Cycle Decision Outputs
    output reg                    decision_valid,
    output reg                    order_approved,
    output reg  [7:0]             violation_code
);

    // Violation Encodings
    localparam CODE_APPROVED           = 8'h00;
    localparam CODE_KILLSWITCH         = 8'h01;
    localparam CODE_COLLAR_BREACH      = 8'h02;
    localparam CODE_SIZE_BREACH        = 8'h03;
    localparam CODE_INVENTORY_BREACH   = 8'h04;
    localparam CODE_DRAWDOWN_BREACH    = 8'h05;
    localparam CODE_LYAPUNOV_BREACH    = 8'h06;

    // Combinational pre-calculations
    wire signed [31:0] price_diff;
    wire signed [31:0] abs_price_diff;
    wire signed [31:0] post_trade_inv;
    wire signed [31:0] abs_curr_inv;
    wire signed [31:0] abs_post_inv;
    wire signed [31:0] v_deviation;
    wire signed [31:0] abs_v_deviation;
    wire               is_derisking;

    assign price_diff     = order_price - market_mid_price;
    assign abs_price_diff = (price_diff < 0) ? -price_diff : price_diff;

    // Signed quantity delta based on side
    assign post_trade_inv = order_side ? (current_inventory + order_qty)
                                       : (current_inventory - order_qty);

    assign abs_curr_inv = (current_inventory < 0) ? -current_inventory : current_inventory;
    assign abs_post_inv = (post_trade_inv < 0)    ? -post_trade_inv    : post_trade_inv;

    // De-risking bypass: if trade reduces absolute inventory exposure, it is permitted
    assign is_derisking = (abs_post_inv < abs_curr_inv);

    // Lyapunov membrane voltage deviation from resting
    assign v_deviation     = membrane_voltage - cfg_v_resting;
    assign abs_v_deviation = (v_deviation < 0) ? -v_deviation : v_deviation;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            decision_valid <= 1'b0;
            order_approved <= 1'b0;
            violation_code <= CODE_APPROVED;
        end else begin
            if (eval_valid) begin
                decision_valid <= 1'b1;

                if (emergency_killswitch) begin
                    order_approved <= 1'b0;
                    violation_code <= CODE_KILLSWITCH;
                end else if (abs_price_diff > cfg_collar_threshold) begin
                    order_approved <= 1'b0;
                    violation_code <= CODE_COLLAR_BREACH;
                end else if (order_qty > cfg_max_order_size) begin
                    order_approved <= 1'b0;
                    violation_code <= CODE_SIZE_BREACH;
                end else if ((abs_post_inv > cfg_max_inventory) && !is_derisking) begin
                    order_approved <= 1'b0;
                    violation_code <= CODE_INVENTORY_BREACH;
                end else if (current_mtm_pnl < cfg_drawdown_limit) begin
                    order_approved <= 1'b0;
                    violation_code <= CODE_DRAWDOWN_BREACH;
                end else if (abs_v_deviation > cfg_lyapunov_threshold) begin
                    order_approved <= 1'b0;
                    violation_code <= CODE_LYAPUNOV_BREACH;
                end else begin
                    // ALL GATES CLEARED DETERMINISTICALLY
                    order_approved <= 1'b1;
                    violation_code <= CODE_APPROVED;
                end
            end else begin
                decision_valid <= 1'b0;
                order_approved <= 1'b0;
                violation_code <= CODE_APPROVED;
            end
        end
    end

endmodule
