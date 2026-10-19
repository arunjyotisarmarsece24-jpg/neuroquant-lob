// ==============================================================================
// NeuroQuant-LOB: Hardware Leaky Integrate-and-Fire (LIF) Neural Core
// ==============================================================================
// Cycle-accurate, synthesis-ready RTL implementation of biological LIF dynamics
// in Q16.16 fixed-point arithmetic targeting AMD Xilinx UltraScale+ / Alveo FPGAs.
//
// Latency: 1 clock cycle pipelined (3.10 ns at 322.26 MHz 10GbE network clock)
// Throughput: 1 spike evaluation per clock cycle
//
// Author: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
// Project: NeuroQuant-LOB Flagship Quantitative Architecture
// License: 100% Free & Open-Source (MIT / Apache-2.0)
// ==============================================================================

`timescale 1ns / 1ps

module lif_neuron_core #(
    // Fixed-Point Format: Q16.16 (Signed 32-bit: 16 int bits, 16 fractional bits)
    // Scale factor: 1.0 = 16'h0001_0000 = 65,536

    // Biological Parameters (in millivolts, scaled by 65536):
    parameter signed [31:0] V_REST          = -32'sd4587520, // -70.0 mV * 65536
    parameter signed [31:0] V_THRESH        = -32'sd3604480, // -55.0 mV * 65536
    parameter signed [31:0] V_RESET         = -32'sd4915200, // -75.0 mV * 65536
    
    // Discrete Exponential Decay Beta = exp(-dt / tau_m) approx 0.950
    // 0.950 * 65536 = 62,259
    parameter signed [31:0] BETA            = 32'sd62259,
    // (1 - Beta) = 0.050 * 65536 = 3,277
    parameter signed [31:0] ONE_MINUS_BETA  = 32'sd3277,
    
    // Refractory Period in clock cycles (e.g., 2 cycles at 100MHz = 20ns)
    parameter integer       REFRACTORY_CYC  = 2
)(
    input  wire                 clk,            // Master system clock (100MHz - 322MHz)
    input  wire                 rst_n,          // Active-low asynchronous reset
    input  wire                 i_valid,        // Input current valid strobe
    input  wire signed [31:0]   i_syn_current,  // Synaptic input current (Q16.16 in mV)
    
    output reg                  o_spike,        // Action potential (spike pulse: 1 cycle high)
    output reg  signed [31:0]   o_v_mem,        // Current membrane potential (Q16.16 in mV)
    output wire                 o_ready         // Ready for next input
);

    // Internal state registers
    reg [3:0] refractory_counter;

    // 64-bit signed intermediate registers for fixed-point multiplication
    wire signed [63:0] mult_decay;
    wire signed [63:0] mult_rest;
    wire signed [31:0] v_decayed;
    wire signed [31:0] v_rest_component;
    wire signed [31:0] v_next;

    // Q16.16 Fixed-Point Multiplications: (A * B) >>> 16 with explicit $signed cast
    assign mult_decay       = o_v_mem * BETA;
    assign mult_rest        = V_REST * ONE_MINUS_BETA;
    assign v_decayed        = $signed(mult_decay[47:16]);        // Preserve signed 2's complement
    assign v_rest_component = $signed(mult_rest[47:16]);

    // Euler update: V[t] = beta * V[t-1] + (1 - beta) * V_rest + I_syn
    assign v_next           = v_decayed + v_rest_component + i_syn_current;

    // Ready signal: always ready unless held in reset
    assign o_ready          = rst_n;

    // Sequential LIF state machine
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            o_spike            <= 1'b0;
            o_v_mem            <= V_REST;
            refractory_counter <= 4'd0;
        end else if (i_valid) begin
            if (refractory_counter > 4'd0) begin
                // Neuron is in absolute refractory period: cannot integrate or fire
                o_spike            <= 1'b0;
                o_v_mem            <= V_RESET;
                refractory_counter <= refractory_counter - 1'b1;
            end else if (v_next >= V_THRESH) begin
                // Action potential threshold crossing!
                o_spike            <= 1'b1;          // Emit 1-cycle spike
                o_v_mem            <= V_RESET;       // Instantaneous voltage reset
                refractory_counter <= REFRACTORY_CYC; // Enter refractory clamp
            end else begin
                // Sub-threshold leaky integration
                o_spike            <= 1'b0;
                o_v_mem            <= v_next;
            end
        end else begin
            // Hold spike low if no valid clock strobe
            o_spike <= 1'b0;
        end
    end

endmodule
