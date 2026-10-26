// =============================================================================
// NEUROQUANT-LOB: ALMGREN-CHRISS PRE-TRADE HARDWARE EXECUTION RISK GATE (DAY 3)
// =============================================================================
// Principal Architect: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
// Target Architecture: AMD Xilinx Spartan-7 / UltraScale+ (100 MHz / 322 MHz)
// Standard: IEEE 1364-2001 Verilog HDL
// Description:
//   Cycle-accurate, zero-allocation pre-trade hardware execution gate enforcing
//   Almgren-Chriss optimal liquidation invariants in a single pipelined clock cycle:
//     1. Execution Rate Collar: v_k <= AC_MAX_RATE_CAP (Q16.16)
//     2. Dynamic Slippage Guard: |P_exec - P_mid| <= AC_SLIPPAGE_TOL (Q16.16)
//     3. Inventory Target Conservation: Cumulative traded <= Total Target X_0
//     4. Neuromorphic Urgency Boost: Dynamic rate expansion upon LIF toxicity alert
// =============================================================================

`timescale 1ns / 1ps
`include "optimal_almgren_params.vh"

module almgren_chriss_risk_gate (
    input  wire                   clk,
    input  wire                   rst_n,

    // Execution Order Evaluation Strobe
    input  wire                   eval_valid,
    input  wire                   order_side,           // 1 = BUY, 0 = SELL
    input  wire signed [31:0]     order_qty,            // Traded shares in this interval
    input  wire signed [31:0]     interval_dt_q16,      // Interval duration tau in Q16.16 (e.g. 2.0s = 32'sd131072)
    input  wire signed [31:0]     order_price_q16,      // Exec price in Q16.16 ($)
    input  wire signed [31:0]     market_mid_q16,       // Mid price in Q16.16 ($)
    input  wire signed [31:0]     target_total_shares,  // Total liquidation inventory X_0 (integer)
    input  wire                   neuro_urgency_boost,  // Toxicity spike from LIF cortex

    // Dynamic Parameter Overrides (Defaults set by optimal_almgren_params.vh)
    input  wire signed [31:0]     cfg_max_rate_cap_q16, // Max allowed rate (shares/sec in Q16.16)
    input  wire signed [31:0]     cfg_slippage_tol_q16, // Max allowed slippage ($ in Q16.16)

    // Single-Cycle Decision Outputs
    output reg                    decision_valid,
    output reg                    order_approved,
    output reg  [7:0]             violation_code,
    output reg  signed [31:0]     cumulative_executed,
    output reg  signed [31:0]     remaining_inventory,
    output reg  signed [31:0]     current_rate_q16
);

    // Violation Code Definitions
    localparam CODE_APPROVED           = 8'h00;
    localparam CODE_RATE_EXCEEDED      = 8'h11;
    localparam CODE_SLIPPAGE_BREACH    = 8'h12;
    localparam CODE_INVENTORY_OVERSHOOT= 8'h13;
    localparam CODE_INVALID_INTERVAL   = 8'h14;

    // Combinational calculations
    wire signed [31:0] effective_max_rate;
    wire signed [31:0] effective_slippage_tol;
    wire signed [31:0] calc_rate_q16;
    wire signed [31:0] price_diff_q16;
    wire signed [31:0] abs_price_diff_q16;
    wire signed [31:0] projected_cum_exec;

    // If neuro_urgency_boost is active, allow 50% rate expansion (multiply by 1.5 in Q16.16)
    // to aggressively liquidate inventory before adverse selection consumes book depth
    assign effective_max_rate = neuro_urgency_boost ?
                                (cfg_max_rate_cap_q16 + (cfg_max_rate_cap_q16 >>> 1)) :
                                cfg_max_rate_cap_q16;

    // Expand slippage tolerance slightly during urgency regimes
    assign effective_slippage_tol = neuro_urgency_boost ?
                                    (cfg_slippage_tol_q16 + (cfg_slippage_tol_q16 >>> 2)) :
                                    cfg_slippage_tol_q16;

    // Clean synthesizable execution rate calculation:
    // interval_dt_q16 >> 16 gives seconds (e.g. 2.0s = 2)
    wire [31:0] dt_seconds;
    wire [31:0] rate_shares_sec;
    assign dt_seconds = (interval_dt_q16 >> 16);
    assign rate_shares_sec = (dt_seconds > 0) ? (order_qty / dt_seconds) : order_qty;
    assign calc_rate_q16 = (rate_shares_sec << 16);

    // Slippage calculation
    assign price_diff_q16     = order_price_q16 - market_mid_q16;
    assign abs_price_diff_q16 = (price_diff_q16 < 0) ? -price_diff_q16 : price_diff_q16;

    // Projected execution
    assign projected_cum_exec = cumulative_executed + order_qty;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            decision_valid      <= 1'b0;
            order_approved      <= 1'b0;
            violation_code      <= CODE_APPROVED;
            cumulative_executed <= 32'sd0;
            remaining_inventory <= target_total_shares;
            current_rate_q16    <= 32'sd0;
        end else begin
            if (eval_valid) begin
                decision_valid   <= 1'b1;
                current_rate_q16 <= calc_rate_q16;

                if (interval_dt_q16 <= 0) begin
                    order_approved <= 1'b0;
                    violation_code <= CODE_INVALID_INTERVAL;
                end else if (calc_rate_q16 > effective_max_rate) begin
                    // Execution pace violates Almgren-Chriss maximum instantaneous rate
                    order_approved <= 1'b0;
                    violation_code <= CODE_RATE_EXCEEDED;
                end else if (abs_price_diff_q16 > effective_slippage_tol) begin
                    // Slippage exceeds square-root impact boundary
                    order_approved <= 1'b0;
                    violation_code <= CODE_SLIPPAGE_BREACH;
                end else if (projected_cum_exec > target_total_shares) begin
                    // Cumulative trades exceed total target liquidation position
                    order_approved <= 1'b0;
                    violation_code <= CODE_INVENTORY_OVERSHOOT;
                end else begin
                    // Approved
                    order_approved      <= 1'b1;
                    violation_code      <= CODE_APPROVED;
                    cumulative_executed <= projected_cum_exec;
                    remaining_inventory <= target_total_shares - projected_cum_exec;
                end
            end else begin
                decision_valid <= 1'b0;
            end
        end
    end

endmodule
