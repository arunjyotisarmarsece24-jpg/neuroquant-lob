// ==============================================================================
// NeuroQuant-LOB: Cycle-Accurate Testbench for Day 1 Pareto Champion LIF Core
// ==============================================================================
// Verifies synthesizable RTL integration of the Pareto-optimal neuromorphic
// parameters discovered via Day 1 grid sweep across realistic L2 order book data.
//
// Automatically imports: `hardware/optimal_neuromorphic_params.vh`
// Direct RTL Target: `hardware/lif_neuron_core.v`
// Arithmetic: Signed Q16.16 Fixed-Point (Scale: 1.0 = 65,536)
//
// Author: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
// Project: NeuroQuant-LOB Flagship Quantitative Architecture
// License: 100% Free & Open-Source (MIT / Apache-2.0)
// ==============================================================================

`timescale 1ns / 1ps

`include "optimal_neuromorphic_params.vh"

module tb_optimal_champion_lif;

    // Clock and Reset Signals
    reg                 clk;
    reg                 rst_n;
    reg                 i_valid;
    reg  signed [31:0]  i_syn_current;

    // Output Wires
    wire                o_spike;
    wire signed [31:0]  o_v_mem;
    wire                o_ready;

    // Test Tracking Variables
    integer cycle_count;
    integer pass_count;
    integer fail_count;

    // Instantiate Leaky Integrate-and-Fire Core with Day 1 Pareto Parameters
    lif_neuron_core #(
        .V_REST         (OPTIMAL_V_REST),
        .V_THRESH       (OPTIMAL_V_THRESH),
        .V_RESET        (OPTIMAL_V_RESET),
        .BETA           (OPTIMAL_BETA),
        .ONE_MINUS_BETA (OPTIMAL_ONE_MINUS_BETA),
        .REFRACTORY_CYC (OPTIMAL_REFRACTORY_CYC)
    ) uut (
        .clk            (clk),
        .rst_n          (rst_n),
        .i_valid        (i_valid),
        .i_syn_current  (i_syn_current),
        .o_spike        (o_spike),
        .o_v_mem        (o_v_mem),
        .o_ready        (o_ready)
    );

    // 100 MHz Clock Generator (Period = 10 ns)
    always #5 clk = ~clk;

    // Real-valued mV conversion function for readable simulation logging
    function real to_mv;
        input signed [31:0] fixed_val;
        begin
            to_mv = fixed_val / 65536.0;
        end
    endfunction

    // Helper task for applying a clock step with synchronous input setup
    task step_neuron;
        input real current_mv;
        begin
            @(negedge clk);
            i_valid       = 1'b1;
            i_syn_current = $rtoi(current_mv * 65536.0);
            @(posedge clk);
            #1; // Sample state immediately after posedge
            cycle_count   = cycle_count + 1;
            $display("[CYCLE %2d] Time: %4d ns | V_mem: %7.3f mV | Input: %6.2f mV | Spike: %b | Ready: %b",
                     cycle_count, $time, to_mv(o_v_mem), current_mv, o_spike, o_ready);
        end
    endtask

    initial begin
        // Signal Waveform Trace Setup
        $dumpfile("hardware/neuroquant_champion_lif_trace.vcd");
        $dumpvars(0, tb_optimal_champion_lif);

        clk           = 1'b0;
        rst_n         = 1'b0;
        i_valid       = 1'b0;
        i_syn_current = 32'sd0;
        cycle_count   = 0;
        pass_count    = 0;
        fail_count    = 0;

        $display("");
        $display("================================================================================");
        $display("   NEUROQUANT-LOB: DAY 1 PARETO CHAMPION LIF HARDWARE RTL SIMULATION");
        $display("================================================================================");
        $display("  Loaded Parameters from optimal_neuromorphic_params.vh:");
        $display("    V_THRESH       = %0d (%.4f mV)", OPTIMAL_V_THRESH, to_mv(OPTIMAL_V_THRESH));
        $display("    V_REST         = %0d (%.4f mV)", OPTIMAL_V_REST, to_mv(OPTIMAL_V_REST));
        $display("    V_RESET        = %0d (%.4f mV)", OPTIMAL_V_RESET, to_mv(OPTIMAL_V_RESET));
        $display("    BETA           = %0d (Tau_m = 25.0 ms)", OPTIMAL_BETA);
        $display("    ONE_MINUS_BETA = %0d", OPTIMAL_ONE_MINUS_BETA);
        $display("    REFRACTORY_CYC = %0d clock cycles", OPTIMAL_REFRACTORY_CYC);
        $display("================================================================================");

        // ----------------------------------------------------------------------
        // CHECK 1: Reset Invariance & Resting Equilibrium
        // ----------------------------------------------------------------------
        $display("\n[*] CHECK 1: Testing Asynchronous Reset Initialization...");
        #15;
        rst_n = 1'b1;
        #2;
        if (to_mv(o_v_mem) == -70.0 && o_spike == 1'b0 && o_ready == 1'b1) begin
            $display("[PASS] Reset state initialized cleanly: V_mem = %0.2f mV, Spike = 0, Ready = 1", to_mv(o_v_mem));
            pass_count = pass_count + 1;
        end else begin
            $display("[FAIL] Reset state invalid: V_mem = %0.2f mV, Spike = %b, Ready = %b", to_mv(o_v_mem), o_spike, o_ready);
            fail_count = fail_count + 1;
        end

        // ----------------------------------------------------------------------
        // CHECK 2: Sub-threshold Depolarization Without Spurious Spikes
        // ----------------------------------------------------------------------
        $display("\n[*] CHECK 2: Injecting Sub-Threshold Synaptic Influx (+5.0 mV current)...");
        step_neuron(5.0);
        step_neuron(5.0);
        step_neuron(5.0);
        if (o_spike == 1'b0 && to_mv(o_v_mem) > -70.0 && to_mv(o_v_mem) < -50.0) begin
            $display("[PASS] Sub-threshold integration verified: V_mem rose to %0.3f mV with 0 false spikes", to_mv(o_v_mem));
            pass_count = pass_count + 1;
        end else begin
            $display("[FAIL] Sub-threshold test failed! V_mem = %0.3f mV, Spike = %b", to_mv(o_v_mem), o_spike);
            fail_count = fail_count + 1;
        end

        // ----------------------------------------------------------------------
        // CHECK 3: Suprathreshold Depolarization & Action Potential
        // ----------------------------------------------------------------------
        $display("\n[*] CHECK 3: Injecting Strong Suprathreshold Impulse (+25.0 mV current)...");
        step_neuron(25.0); // Drives V_next above -50.0 mV and triggers action potential
        
        if (o_spike == 1'b1 && to_mv(o_v_mem) == -75.0) begin
            $display("[PASS] Action Potential Triggered! Spike = 1, Voltage reset to %0.2f mV", to_mv(o_v_mem));
            pass_count = pass_count + 1;
        end else begin
            $display("[FAIL] Spike failed to fire or reset properly! Spike = %b, V = %0.2f", o_spike, to_mv(o_v_mem));
            fail_count = fail_count + 1;
        end

        // ----------------------------------------------------------------------
        // CHECK 4: Absolute Refractory Period Clamp (Spike Suppression)
        // ----------------------------------------------------------------------
        $display("\n[*] CHECK 4: Testing Refractory Period Clamp (Injecting +30.0 mV shock during refractory)...");
        step_neuron(30.0); // Refractory cycle 1
        step_neuron(30.0); // Refractory cycle 2

        if (o_spike == 1'b0 && to_mv(o_v_mem) == -75.0) begin
            $display("[PASS] Refractory clamp active: Spikes suppressed and voltage held at reset potential (-75.0 mV)");
            pass_count = pass_count + 1;
        end else begin
            $display("[FAIL] Refractory test failed! Spike emitted during refractory period or voltage drifted: %0.2f mV", to_mv(o_v_mem));
            fail_count = fail_count + 1;
        end

        // ----------------------------------------------------------------------
        // CHECK 5: Exponential Leak Decay Back to Resting Potential
        // ----------------------------------------------------------------------
        $display("\n[*] CHECK 5: Testing Exponential Passive Leak Decay (Zero Current Influx)...");
        step_neuron(0.0);
        step_neuron(0.0);
        step_neuron(0.0);
        step_neuron(0.0);
        step_neuron(0.0);

        if (to_mv(o_v_mem) > -75.0 && to_mv(o_v_mem) <= -70.0) begin
            $display("[PASS] Leaky decay verified: Potential relaxing exponentially back toward -70.0 mV (current: %0.3f mV)", to_mv(o_v_mem));
            pass_count = pass_count + 1;
        end else begin
            $display("[FAIL] Leaky decay test failed: V_mem = %0.3f mV", to_mv(o_v_mem));
            fail_count = fail_count + 1;
        end

        // ----------------------------------------------------------------------
        // Final Summary Verdict
        // ----------------------------------------------------------------------
        #20;
        $display("\n================================================================================");
        $display("   DAY 1 CHAMPION HARDWARE VERILOG SIMULATION RESULTS");
        $display("================================================================================");
        $display("   Total Checks Evaluated: %0d", (pass_count + fail_count));
        $display("   Passed Assertions:      %0d", pass_count);
        $display("   Failed Assertions:      %0d", fail_count);
        $display("================================================================================");

        if (fail_count == 0) begin
            $display(">>> 100%% VERILOG HARDWARE DAY 1 CHAMPION LIF SIMULATION VERIFIED! <<<");
            $finish(0);
        end else begin
            $display(">>> HARDWARE RTL SIMULATION FAILED WITH %0d ERRORS! <<<", fail_count);
            $finish(1);
        end
    end

endmodule
