// ==============================================================================
// NeuroQuant-LOB: Calibrated Multi-Level OFI & Hawkes Parameters (Day 2)
// ==============================================================================
// Calibrated from 1,000 realistic L2 ticks across 5 depth levels.
// Target Hardware: AMD Xilinx UltraScale+ / Spartan-7 / Artix-7
// Arithmetic: Signed Q16.16 Fixed-Point (Scale: 1.0 = 65,536)
// Generated: 2026-10-29 06:52:15 UTC
// ==============================================================================

`ifndef OPTIMAL_OFI_PARAMS_VH
`define OPTIMAL_OFI_PARAMS_VH

// Multi-Level OFI Weights w_l (Q16.16 signed)
localparam signed [31:0] OFI_WEIGHT_0 = 32'sd4620; // 0.0705
localparam signed [31:0] OFI_WEIGHT_1 = 32'sd1763; // 0.0269
localparam signed [31:0] OFI_WEIGHT_2 = 32'sd54192; // 0.8269
localparam signed [31:0] OFI_WEIGHT_3 = 32'sd1763; // 0.0269
localparam signed [31:0] OFI_WEIGHT_4 = 32'sd3198; // 0.0488

// Discrete Exponential Decay Multipliers exp(-lambda_l * 0.01s) (Q16.16 signed)
localparam signed [31:0] OFI_DECAY_MULT_0 = 32'sd60497; // exp(-8.00*0.01) = 0.9231
localparam signed [31:0] OFI_DECAY_MULT_1 = 32'sd62340; // exp(-5.00*0.01) = 0.9512
localparam signed [31:0] OFI_DECAY_MULT_2 = 32'sd63282; // exp(-3.50*0.01) = 0.9656
localparam signed [31:0] OFI_DECAY_MULT_3 = 32'sd64238; // exp(-2.00*0.01) = 0.9802
localparam signed [31:0] OFI_DECAY_MULT_4 = 32'sd64884; // exp(-1.00*0.01) = 0.9900

// Baseline Hawkes Intensities mu_l (Q16.16 signed)
localparam signed [31:0] HAWKES_MU_0 = 32'sd6732677; // 102.73 events/s
localparam signed [31:0] HAWKES_MU_1 = 32'sd5536101; // 84.47 events/s
localparam signed [31:0] HAWKES_MU_2 = 32'sd4763773; // 72.69 events/s
localparam signed [31:0] HAWKES_MU_3 = 32'sd3761249; // 57.39 events/s
localparam signed [31:0] HAWKES_MU_4 = 32'sd3703590; // 56.51 events/s

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
