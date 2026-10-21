// ==============================================================================
// NeuroQuant-LOB: Calibrated Multi-Level OFI & Hawkes Parameters (Day 2)
// ==============================================================================
// Calibrated from 25,000 realistic L2 ticks across 5 depth levels.
// Target Hardware: AMD Xilinx UltraScale+ / Spartan-7 / Artix-7
// Arithmetic: Signed Q16.16 Fixed-Point (Scale: 1.0 = 65,536)
// Generated: 2026-10-21 07:05:59 UTC
// ==============================================================================

`ifndef OPTIMAL_OFI_PARAMS_VH
`define OPTIMAL_OFI_PARAMS_VH

// Multi-Level OFI Weights w_l (Q16.16 signed)
localparam signed [31:0] OFI_WEIGHT_0 = 32'sd11751; // 0.1793
localparam signed [31:0] OFI_WEIGHT_1 = 32'sd11751; // 0.1793
localparam signed [31:0] OFI_WEIGHT_2 = 32'sd11751; // 0.1793
localparam signed [31:0] OFI_WEIGHT_3 = 32'sd18534; // 0.2828
localparam signed [31:0] OFI_WEIGHT_4 = 32'sd11751; // 0.1793

// Discrete Exponential Decay Multipliers exp(-lambda_l * 0.01s) (Q16.16 signed)
localparam signed [31:0] OFI_DECAY_MULT_0 = 32'sd60497; // exp(-8.00*0.01) = 0.9231
localparam signed [31:0] OFI_DECAY_MULT_1 = 32'sd62340; // exp(-5.00*0.01) = 0.9512
localparam signed [31:0] OFI_DECAY_MULT_2 = 32'sd63282; // exp(-3.50*0.01) = 0.9656
localparam signed [31:0] OFI_DECAY_MULT_3 = 32'sd64238; // exp(-2.00*0.01) = 0.9802
localparam signed [31:0] OFI_DECAY_MULT_4 = 32'sd64884; // exp(-1.00*0.01) = 0.9900

// Baseline Hawkes Intensities mu_l (Q16.16 signed)
localparam signed [31:0] HAWKES_MU_0 = 32'sd14028734; // 214.06 events/s
localparam signed [31:0] HAWKES_MU_1 = 32'sd11790497; // 179.91 events/s
localparam signed [31:0] HAWKES_MU_2 = 32'sd9519589; // 145.26 events/s
localparam signed [31:0] HAWKES_MU_3 = 32'sd8309165; // 126.79 events/s
localparam signed [31:0] HAWKES_MU_4 = 32'sd7936442; // 121.10 events/s

// Hawkes Self & Cross-Excitation Kernel Coefficients (alpha_lm in Q16.16)
localparam signed [31:0] HAWKES_ALPHA_SELF  = 32'sd18350; // 0.2800
localparam signed [31:0] HAWKES_ALPHA_ADJ   = 32'sd7864;  // 0.1200
localparam signed [31:0] HAWKES_ALPHA_DIST  = 32'sd3277; // 0.0500

// Hawkes Intensity Decay Multiplier exp(-beta * 0.01s) (beta = 4.0): 0.9608
localparam signed [31:0] HAWKES_BETA_DECAY_MULT = 32'sd62966;

// Institutional Toxic Flow Alert Thresholds (Q16.16 signed)
localparam signed [31:0] TOXIC_OFI_THRESHOLD = 32'sd3276800; // 50 contracts
localparam signed [31:0] TOXIC_HAWKES_THRESHOLD = 32'sd2949120; // 45 events/s

`endif // OPTIMAL_OFI_PARAMS_VH
