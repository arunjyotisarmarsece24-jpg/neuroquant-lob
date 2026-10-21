// ==============================================================================
// NEUROQUANT-LOB: MULTI-LEVEL ORDER-FLOW IMBALANCE (OFI) & HAWKES RTL CORE
// ==============================================================================
// Principal Architect: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
// Target Architectures: AMD Xilinx UltraScale+, Kintex-7, Artix-7, Spartan-7
// Clock: 100.00 MHz / 322.26 MHz | Sub-Cycle Latency: 1 Clock Cycle (10.0 ns / 3.1 ns)
// Arithmetic: Signed Q16.16 Fixed-Point (Scale: 1.0 = 65,536)
//
// Features:
//   1. 5-Level Depth Ladder Tracking (Bid/Ask Prices & Sizes)
//   2. High-Speed Price-Shift Directional Delta Logic (Cont et al. Multi-Level)
//   3. Exponential Decay Accumulator for Depth-Decayed Information Persistence
//   4. Multi-Level Weighted Composite Imbalance Calculation
//   5. Multivariate Hawkes Cross-Level Excitation Intensity Engine
//   6. Institutional Toxic Sweep Real-Time Alert Assertion
// ==============================================================================

`timescale 1ns / 1ps
`include "optimal_ofi_params.vh"

module multilevel_ofi_hawkes #(
    parameter LEVELS = 5,
    parameter DATA_WIDTH = 32
)(
    input  wire                   clk,
    input  wire                   rst_n,
    input  wire                   i_tick_valid,

    // L2 Depth Input Ladders (Signed Q16.16)
    input  wire signed [31:0]     i_bid_price_0,
    input  wire signed [31:0]     i_bid_price_1,
    input  wire signed [31:0]     i_bid_price_2,
    input  wire signed [31:0]     i_bid_price_3,
    input  wire signed [31:0]     i_bid_price_4,

    input  wire signed [31:0]     i_bid_size_0,
    input  wire signed [31:0]     i_bid_size_1,
    input  wire signed [31:0]     i_bid_size_2,
    input  wire signed [31:0]     i_bid_size_3,
    input  wire signed [31:0]     i_bid_size_4,

    input  wire signed [31:0]     i_ask_price_0,
    input  wire signed [31:0]     i_ask_price_1,
    input  wire signed [31:0]     i_ask_price_2,
    input  wire signed [31:0]     i_ask_price_3,
    input  wire signed [31:0]     i_ask_price_4,

    input  wire signed [31:0]     i_ask_size_0,
    input  wire signed [31:0]     i_ask_size_1,
    input  wire signed [31:0]     i_ask_size_2,
    input  wire signed [31:0]     i_ask_size_3,
    input  wire signed [31:0]     i_ask_size_4,

    // Outputs
    output reg                    o_valid,
    output reg signed [31:0]      o_raw_ofi_0,
    output reg signed [31:0]      o_raw_ofi_1,
    output reg signed [31:0]      o_raw_ofi_2,
    output reg signed [31:0]      o_raw_ofi_3,
    output reg signed [31:0]      o_raw_ofi_4,

    output reg signed [31:0]      o_decayed_ofi_0,
    output reg signed [31:0]      o_decayed_ofi_1,
    output reg signed [31:0]      o_decayed_ofi_2,
    output reg signed [31:0]      o_decayed_ofi_3,
    output reg signed [31:0]      o_decayed_ofi_4,

    output reg signed [31:0]      o_composite_ofi,

    output reg signed [31:0]      o_hawkes_intensity_0,
    output reg signed [31:0]      o_hawkes_intensity_1,
    output reg signed [31:0]      o_hawkes_intensity_2,
    output reg signed [31:0]      o_hawkes_intensity_3,
    output reg signed [31:0]      o_hawkes_intensity_4,

    output reg                    o_toxic_flow_alert,
    output wire                   o_ready
);

    // Initialized Flag & Previous State Registers
    reg        r_initialized;
    reg signed [31:0] r_prev_bp [0:4];
    reg signed [31:0] r_prev_bs [0:4];
    reg signed [31:0] r_prev_ap [0:4];
    reg signed [31:0] r_prev_as [0:4];

    // Decayed OFI Accumulator Registers
    reg signed [31:0] r_decayed_ofi [0:4];

    // Hawkes Intensity Registers
    reg signed [31:0] r_hawkes_intensity [0:4];

    assign o_ready = rst_n && r_initialized;

    // Helper function for fixed-point Q16.16 multiplication with rounding
    function signed [31:0] q_mult(input signed [31:0] a, input signed [31:0] b);
        reg signed [63:0] temp;
        begin
            temp = a * b;
            q_mult = temp[47:16];
        end
    endfunction

    // Helper function for fixed-point Q16.16 absolute value
    function signed [31:0] q_abs(input signed [31:0] val);
        begin
            q_abs = (val < 0) ? -val : val;
        end
    endfunction

    // Combinational Delta & OFI variables
    reg signed [31:0] w_delta_b [0:4];
    reg signed [31:0] w_delta_a [0:4];
    reg signed [31:0] w_raw_ofi [0:4];
    reg signed [31:0] w_next_decayed [0:4];
    reg signed [31:0] w_comp_ofi;
    reg signed [31:0] w_next_hawkes [0:4];
    reg               w_event_active [0:4];

    integer l;

    // Sequential Clocked State Machine
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            r_initialized <= 1'b0;
            o_valid <= 1'b0;
            o_toxic_flow_alert <= 1'b0;
            o_composite_ofi <= 32'sd0;

            for (l = 0; l < 5; l = l + 1) begin
                r_prev_bp[l] <= 32'sd0;
                r_prev_bs[l] <= 32'sd0;
                r_prev_ap[l] <= 32'sd0;
                r_prev_as[l] <= 32'sd0;
                r_decayed_ofi[l] <= 32'sd0;
            end

            r_hawkes_intensity[0] <= HAWKES_MU_0;
            r_hawkes_intensity[1] <= HAWKES_MU_1;
            r_hawkes_intensity[2] <= HAWKES_MU_2;
            r_hawkes_intensity[3] <= HAWKES_MU_3;
            r_hawkes_intensity[4] <= HAWKES_MU_4;

            o_raw_ofi_0 <= 32'sd0;
            o_raw_ofi_1 <= 32'sd0;
            o_raw_ofi_2 <= 32'sd0;
            o_raw_ofi_3 <= 32'sd0;
            o_raw_ofi_4 <= 32'sd0;

            o_decayed_ofi_0 <= 32'sd0;
            o_decayed_ofi_1 <= 32'sd0;
            o_decayed_ofi_2 <= 32'sd0;
            o_decayed_ofi_3 <= 32'sd0;
            o_decayed_ofi_4 <= 32'sd0;

            o_hawkes_intensity_0 <= HAWKES_MU_0;
            o_hawkes_intensity_1 <= HAWKES_MU_1;
            o_hawkes_intensity_2 <= HAWKES_MU_2;
            o_hawkes_intensity_3 <= HAWKES_MU_3;
            o_hawkes_intensity_4 <= HAWKES_MU_4;

        end else if (i_tick_valid) begin
            o_valid <= 1'b1;

            if (!r_initialized) begin
                // Initialize first tick baseline
                r_prev_bp[0] <= i_bid_price_0; r_prev_bs[0] <= i_bid_size_0;
                r_prev_bp[1] <= i_bid_price_1; r_prev_bs[1] <= i_bid_size_1;
                r_prev_bp[2] <= i_bid_price_2; r_prev_bs[2] <= i_bid_size_2;
                r_prev_bp[3] <= i_bid_price_3; r_prev_bs[3] <= i_bid_size_3;
                r_prev_bp[4] <= i_bid_price_4; r_prev_bs[4] <= i_bid_size_4;

                r_prev_ap[0] <= i_ask_price_0; r_prev_as[0] <= i_ask_size_0;
                r_prev_ap[1] <= i_ask_price_1; r_prev_as[1] <= i_ask_size_1;
                r_prev_ap[2] <= i_ask_price_2; r_prev_as[2] <= i_ask_size_2;
                r_prev_ap[3] <= i_ask_price_3; r_prev_as[3] <= i_ask_size_3;
                r_prev_ap[4] <= i_ask_price_4; r_prev_as[4] <= i_ask_size_4;

                r_initialized <= 1'b1;
                o_composite_ofi <= 32'sd0;
                o_toxic_flow_alert <= 1'b0;

            end else begin
                // 1. Calculate Level-by-Level Bid Deltas
                // Level 0
                if (i_bid_price_0 > r_prev_bp[0])       w_delta_b[0] = i_bid_size_0;
                else if (i_bid_price_0 == r_prev_bp[0]) w_delta_b[0] = i_bid_size_0 - r_prev_bs[0];
                else                                    w_delta_b[0] = -r_prev_bs[0];

                // Level 1
                if (i_bid_price_1 > r_prev_bp[1])       w_delta_b[1] = i_bid_size_1;
                else if (i_bid_price_1 == r_prev_bp[1]) w_delta_b[1] = i_bid_size_1 - r_prev_bs[1];
                else                                    w_delta_b[1] = -r_prev_bs[1];

                // Level 2
                if (i_bid_price_2 > r_prev_bp[2])       w_delta_b[2] = i_bid_size_2;
                else if (i_bid_price_2 == r_prev_bp[2]) w_delta_b[2] = i_bid_size_2 - r_prev_bs[2];
                else                                    w_delta_b[2] = -r_prev_bs[2];

                // Level 3
                if (i_bid_price_3 > r_prev_bp[3])       w_delta_b[3] = i_bid_size_3;
                else if (i_bid_price_3 == r_prev_bp[3]) w_delta_b[3] = i_bid_size_3 - r_prev_bs[3];
                else                                    w_delta_b[3] = -r_prev_bs[3];

                // Level 4
                if (i_bid_price_4 > r_prev_bp[4])       w_delta_b[4] = i_bid_size_4;
                else if (i_bid_price_4 == r_prev_bp[4]) w_delta_b[4] = i_bid_size_4 - r_prev_bs[4];
                else                                    w_delta_b[4] = -r_prev_bs[4];

                // 2. Calculate Level-by-Level Ask Deltas
                // Level 0
                if (i_ask_price_0 < r_prev_ap[0])       w_delta_a[0] = i_ask_size_0;
                else if (i_ask_price_0 == r_prev_ap[0]) w_delta_a[0] = i_ask_size_0 - r_prev_as[0];
                else                                    w_delta_a[0] = -r_prev_as[0];

                // Level 1
                if (i_ask_price_1 < r_prev_ap[1])       w_delta_a[1] = i_ask_size_1;
                else if (i_ask_price_1 == r_prev_ap[1]) w_delta_a[1] = i_ask_size_1 - r_prev_as[1];
                else                                    w_delta_a[1] = -r_prev_as[1];

                // Level 2
                if (i_ask_price_2 < r_prev_ap[2])       w_delta_a[2] = i_ask_size_2;
                else if (i_ask_price_2 == r_prev_ap[2]) w_delta_a[2] = i_ask_size_2 - r_prev_as[2];
                else                                    w_delta_a[2] = -r_prev_as[2];

                // Level 3
                if (i_ask_price_3 < r_prev_ap[3])       w_delta_a[3] = i_ask_size_3;
                else if (i_ask_price_3 == r_prev_ap[3]) w_delta_a[3] = i_ask_size_3 - r_prev_as[3];
                else                                    w_delta_a[3] = -r_prev_as[3];

                // Level 4
                if (i_ask_price_4 < r_prev_ap[4])       w_delta_a[4] = i_ask_size_4;
                else if (i_ask_price_4 == r_prev_ap[4]) w_delta_a[4] = i_ask_size_4 - r_prev_as[4];
                else                                    w_delta_a[4] = -r_prev_as[4];

                // 3. Raw OFI per level
                for (l = 0; l < 5; l = l + 1) begin
                    w_raw_ofi[l] = w_delta_b[l] - w_delta_a[l];
                    w_event_active[l] = (w_raw_ofi[l] != 32'sd0);
                end

                o_raw_ofi_0 <= w_raw_ofi[0];
                o_raw_ofi_1 <= w_raw_ofi[1];
                o_raw_ofi_2 <= w_raw_ofi[2];
                o_raw_ofi_3 <= w_raw_ofi[3];
                o_raw_ofi_4 <= w_raw_ofi[4];

                // 4. Exponential Decay Accumulation (Combinational Next State)
                w_next_decayed[0] = q_mult(r_decayed_ofi[0], OFI_DECAY_MULT_0) + w_raw_ofi[0];
                w_next_decayed[1] = q_mult(r_decayed_ofi[1], OFI_DECAY_MULT_1) + w_raw_ofi[1];
                w_next_decayed[2] = q_mult(r_decayed_ofi[2], OFI_DECAY_MULT_2) + w_raw_ofi[2];
                w_next_decayed[3] = q_mult(r_decayed_ofi[3], OFI_DECAY_MULT_3) + w_raw_ofi[3];
                w_next_decayed[4] = q_mult(r_decayed_ofi[4], OFI_DECAY_MULT_4) + w_raw_ofi[4];

                r_decayed_ofi[0] <= w_next_decayed[0];
                r_decayed_ofi[1] <= w_next_decayed[1];
                r_decayed_ofi[2] <= w_next_decayed[2];
                r_decayed_ofi[3] <= w_next_decayed[3];
                r_decayed_ofi[4] <= w_next_decayed[4];

                o_decayed_ofi_0 <= w_next_decayed[0];
                o_decayed_ofi_1 <= w_next_decayed[1];
                o_decayed_ofi_2 <= w_next_decayed[2];
                o_decayed_ofi_3 <= w_next_decayed[3];
                o_decayed_ofi_4 <= w_next_decayed[4];

                // 5. Multi-Level Weighted Composite OFI
                w_comp_ofi = q_mult(w_next_decayed[0], OFI_WEIGHT_0) +
                             q_mult(w_next_decayed[1], OFI_WEIGHT_1) +
                             q_mult(w_next_decayed[2], OFI_WEIGHT_2) +
                             q_mult(w_next_decayed[3], OFI_WEIGHT_3) +
                             q_mult(w_next_decayed[4], OFI_WEIGHT_4);
                o_composite_ofi <= w_comp_ofi;

                // 6. Cross-Level Multivariate Hawkes Intensity Update
                // Level 0 Intensity
                w_next_hawkes[0] = HAWKES_MU_0 +
                    q_mult(r_hawkes_intensity[0] - HAWKES_MU_0, HAWKES_BETA_DECAY_MULT) +
                    (w_event_active[0] ? HAWKES_ALPHA_SELF : 32'sd0) +
                    (w_event_active[1] ? HAWKES_ALPHA_ADJ  : 32'sd0) +
                    (w_event_active[2] ? HAWKES_ALPHA_DIST : 32'sd0);

                // Level 1 Intensity
                w_next_hawkes[1] = HAWKES_MU_1 +
                    q_mult(r_hawkes_intensity[1] - HAWKES_MU_1, HAWKES_BETA_DECAY_MULT) +
                    (w_event_active[0] ? HAWKES_ALPHA_ADJ  : 32'sd0) +
                    (w_event_active[1] ? HAWKES_ALPHA_SELF : 32'sd0) +
                    (w_event_active[2] ? HAWKES_ALPHA_ADJ  : 32'sd0) +
                    (w_event_active[3] ? HAWKES_ALPHA_DIST : 32'sd0);

                // Level 2 Intensity
                w_next_hawkes[2] = HAWKES_MU_2 +
                    q_mult(r_hawkes_intensity[2] - HAWKES_MU_2, HAWKES_BETA_DECAY_MULT) +
                    (w_event_active[1] ? HAWKES_ALPHA_ADJ  : 32'sd0) +
                    (w_event_active[2] ? HAWKES_ALPHA_SELF : 32'sd0) +
                    (w_event_active[3] ? HAWKES_ALPHA_ADJ  : 32'sd0);

                // Level 3 Intensity
                w_next_hawkes[3] = HAWKES_MU_3 +
                    q_mult(r_hawkes_intensity[3] - HAWKES_MU_3, HAWKES_BETA_DECAY_MULT) +
                    (w_event_active[2] ? HAWKES_ALPHA_ADJ  : 32'sd0) +
                    (w_event_active[3] ? HAWKES_ALPHA_SELF : 32'sd0) +
                    (w_event_active[4] ? HAWKES_ALPHA_ADJ  : 32'sd0);

                // Level 4 Intensity
                w_next_hawkes[4] = HAWKES_MU_4 +
                    q_mult(r_hawkes_intensity[4] - HAWKES_MU_4, HAWKES_BETA_DECAY_MULT) +
                    (w_event_active[3] ? HAWKES_ALPHA_ADJ  : 32'sd0) +
                    (w_event_active[4] ? HAWKES_ALPHA_SELF : 32'sd0);

                r_hawkes_intensity[0] <= w_next_hawkes[0];
                r_hawkes_intensity[1] <= w_next_hawkes[1];
                r_hawkes_intensity[2] <= w_next_hawkes[2];
                r_hawkes_intensity[3] <= w_next_hawkes[3];
                r_hawkes_intensity[4] <= w_next_hawkes[4];

                o_hawkes_intensity_0 <= w_next_hawkes[0];
                o_hawkes_intensity_1 <= w_next_hawkes[1];
                o_hawkes_intensity_2 <= w_next_hawkes[2];
                o_hawkes_intensity_3 <= w_next_hawkes[3];
                o_hawkes_intensity_4 <= w_next_hawkes[4];

                // 7. Toxic Flow Alert Condition
                if (q_abs(w_comp_ofi) >= TOXIC_OFI_THRESHOLD ||
                    w_next_hawkes[0] >= TOXIC_HAWKES_THRESHOLD) begin
                    o_toxic_flow_alert <= 1'b1;
                end else begin
                    o_toxic_flow_alert <= 1'b0;
                end

                // Register state updates for next cycle
                r_prev_bp[0] <= i_bid_price_0; r_prev_bs[0] <= i_bid_size_0;
                r_prev_bp[1] <= i_bid_price_1; r_prev_bs[1] <= i_bid_size_1;
                r_prev_bp[2] <= i_bid_price_2; r_prev_bs[2] <= i_bid_size_2;
                r_prev_bp[3] <= i_bid_price_3; r_prev_bs[3] <= i_bid_size_3;
                r_prev_bp[4] <= i_bid_price_4; r_prev_bs[4] <= i_bid_size_4;

                r_prev_ap[0] <= i_ask_price_0; r_prev_as[0] <= i_ask_size_0;
                r_prev_ap[1] <= i_ask_price_1; r_prev_as[1] <= i_ask_size_1;
                r_prev_ap[2] <= i_ask_price_2; r_prev_as[2] <= i_ask_size_2;
                r_prev_ap[3] <= i_ask_price_3; r_prev_as[3] <= i_ask_size_3;
                r_prev_ap[4] <= i_ask_price_4; r_prev_as[4] <= i_ask_size_4;
            end
        end else begin
            o_valid <= 1'b0;
        end
    end

endmodule
