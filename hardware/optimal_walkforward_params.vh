// ==============================================================================
// NEUROQUANT-LOB: SYNTHESIZABLE MULTI-HORIZON WALK-FORWARD PARAMETERS (DAY 4)
// ==============================================================================
// Generated automatically from empirical Purged & Embargoed Cross-Validation
// Target: AMD Xilinx Spartan-7 / UltraScale+ Pre-Trade Gating Hardware
// Architecture: Fixed-Point Signed Q16.16 Representation
// ==============================================================================

`ifndef OPTIMAL_WALKFORWARD_PARAMS_VH
`define OPTIMAL_WALKFORWARD_PARAMS_VH

// Multi-Horizon Active Horizon Identifier
// 2'b00: H=5 ticks, 2'b01: H=10 ticks, 2'b10: H=20 ticks, 2'b11: H=50 ticks
`define DEFAULT_HORIZON_INDEX       2'b10       // Default H=20 ticks (Hawkes relaxation)

// Deflated Sharpe Ratio Statistical Significance Threshold (DSR >= 0.95)
// Q16.16: 0.95 * 65536 = 62259
`define DSR_SIGNIFICANCE_THRESH     32'sd62259

// Champion Out-of-Sample Deflated Sharpe Ratio (DSR = 1.0000)
// Q16.16: 1.0 * 65536 = 65536
`define CHAMPION_DSR_Q16            32'sd65536

// Minimum Required Net Edge Threshold (7.64 bps)
// Q16.16: 7.64 * 65536 = 500695
`define MIN_NET_EDGE_BPS_Q16        32'sd500695

// Toxic Sweep Defense Fast-Cancel Clock Cycles (Sub-100ns)
`define TOXIC_CANCEL_CYCLES         8'd10       // 10 cycles @ 100MHz = 100 ns

`endif // OPTIMAL_WALKFORWARD_PARAMS_VH
