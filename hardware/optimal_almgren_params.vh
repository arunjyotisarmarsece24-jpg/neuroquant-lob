// =============================================================================
// NEUROQUANT-LOB: SYNTHESIZABLE ALMGREN-CHRISS IMPACT PARAMETER PACKAGE (DAY 3)
// =============================================================================
// Generated: Automated Calibration Engine against 25,000 High-Frequency Fills
// Principal Architect: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
// Target Architecture: AMD Xilinx Spartan-7 / UltraScale+ Fixed-Point Q16.16
// =============================================================================

`ifndef OPTIMAL_ALMGREN_PARAMS_VH
`define OPTIMAL_ALMGREN_PARAMS_VH

// Permanent Price Impact Gamma (x1000 scaled in Q16.16: 4.830471e-06)
localparam signed [31:0] AC_GAMMA_PERM_Q16       = 32'sd317;

// Effective Temporary Price Impact Eta (x1000 scaled in Q16.16: 4.856764e-05)
localparam signed [31:0] AC_ETA_TEMP_Q16         = 32'sd3183;

// Non-linear Power-Law Exponent Alpha (0.5243 ~ Square-Root Law)
localparam signed [31:0] AC_ALPHA_EXP_Q16        = 32'sd34360;

// Optimal Urgency Decay Parameter Kappa (0.1193 s^-1)
localparam signed [31:0] AC_KAPPA_NOMINAL_Q16    = 32'sd7816;

// Maximum Allowed Instantaneous Execution Rate Cap (1591.5 shares/s)
localparam signed [31:0] AC_MAX_RATE_CAP_Q16     = 32'sd104302228;

// Maximum Allowed Price Slippage Collar ($0.2523)
localparam signed [31:0] AC_SLIPPAGE_TOL_Q16     = 32'sd16536;

// Liquidation Half-Life in Ticks (Assuming 100ms clock epoch)
localparam [15:0]        AC_HALF_LIFE_TICKS      = 16'd58;

`endif // OPTIMAL_ALMGREN_PARAMS_VH
