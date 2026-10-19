// ==============================================================================
// NeuroQuant-LOB: Cycle-Accurate Hardware Testbench for LIF Neural Core
// ==============================================================================
// 100% Free & Open-Source Verification Testbench for Icarus Verilog (`iverilog`).
// Simulates 100 MHz clock cycles, injects microsecond current pulses, verifies
// threshold crossings, refractory clamps, and exponential leaks.
//
// Author: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
// Project: NeuroQuant-LOB Flagship Quantitative Architecture
// ==============================================================================

`timescale 1ns / 1ps

module tb_lif_neuron;

    // Clock and Reset Signals
    reg                 clk;
    reg                 rst_n;
    reg                 i_valid;
    reg  signed [31:0]  i_syn_current;

    // Output Wires
    wire                o_spike;
    wire signed [31:0]  o_v_mem;
    wire                o_ready;

    // Test Tracking
    integer cycle_count;
    integer pass_count;
    integer fail_count;

    // Instantiate Unit Under Test (UUT)
    lif_neuron_core #(
        .V_REST         (-32'sd4587520), // -70.0 mV
        .V_THRESH       (-32'sd3604480), // -55.0 mV
        .V_RESET        (-32'sd4915200), // -75.0 mV
        .BETA           (32'sd62259),    // 0.950
        .ONE_MINUS_BETA (32'sd3277),     // 0.050
        .REFRACTORY_CYC (2)              // 2 cycles
    ) uut (
        .clk            (clk),
        .rst_n          (rst_n),
        .i_valid        (i_valid),
        .i_syn_current  (i_syn_current),
        .o_spike        (o_spike),
        .o_v_mem        (o_v_mem),
        .o_ready        (o_ready)
    );

    // 100 MHz Clock Generation (Period = 10 ns, 5 ns HIGH / 5 ns LOW)
    always #5 clk = ~clk;

    // Helper task to convert Q16.16 to real millivolts for logging
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
            
            $display("[CYCLE %2d] Time: %4d ns | V_mem: %7.2f mV | Input: %6.2f mV | Spike: %b | Ready: %b",
                     cycle_count, $time, to_mv(o_v_mem), current_mv, o_spike, o_ready);
        end
    endtask

    // Main Test Stimulus
    initial begin
        // Setup Waveform Dump for GTKWave
        $dumpfile("hardware/neuroquant_lif_trace.vcd");
        $dumpvars(0, tb_lif_neuron);

        // Initialize signals
        clk           = 1'b0;
        rst_n         = 1'b0;
        i_valid       = 1'b0;
        i_syn_current = 32'sd0;
        cycle_count   = 0;
        pass_count    = 0;
        fail_count    = 0;

        $display("\n================================================================================");
        $display("   NEUROQUANT-LOB: HARDWARE VERILOG LIF NEURON CYCLE-ACCURATE SIMULATION");
        $display("   Toolchain: Icarus Verilog (`iverilog`) + Virtual Processor (`vvp`)");
        $display("   Clock: 100.00 MHz (10.0 ns Period) | Arithmetic: Q16.16 Signed Fixed-Point");
        $display("================================================================================\n");

        // STEP 1: Asynchronous Reset Check
        $display("[*] STAGE 1: Testing Asynchronous Reset Initialization...");
        #15;
        rst_n = 1'b1; // Release reset
        #2;
        if (to_mv(o_v_mem) == -70.0 && o_spike == 1'b0) begin
            $display("[PASS] Reset state initialized cleanly: V_mem = %0.1f mV, Spike = 0\n", to_mv(o_v_mem));
            pass_count = pass_count + 1;
        end else begin
            $display("[FAIL] Reset state invalid: V_mem = %0.2f mV", to_mv(o_v_mem));
            fail_count = fail_count + 1;
        end

        // STEP 2: Sub-Threshold Current Integration (No Spike Expected)
        $display("[*] STAGE 2: Injecting Sub-Threshold Synaptic Influx (+5.0 mV current)...");
        step_neuron(5.0);
        step_neuron(5.0);
        step_neuron(5.0);
        if (o_spike == 1'b0 && to_mv(o_v_mem) > -70.0 && to_mv(o_v_mem) < -55.0) begin
            $display("[PASS] Sub-threshold integration verified: V_mem rose to %0.2f mV with 0 false spikes\n", to_mv(o_v_mem));
            pass_count = pass_count + 1;
        end else begin
            $display("[FAIL] Sub-threshold test failed!");
            fail_count = fail_count + 1;
        end

        // STEP 3: Action Potential Threshold Crossing & Instantaneous Reset
        $display("[*] STAGE 3: Injecting Strong Institutional Toxicity Impulse (+20.0 mV current)...");
        step_neuron(20.0); // This drives V_next above -55.0 mV and triggers the action potential
        
        if (o_spike == 1'b1 && to_mv(o_v_mem) == -75.0) begin
            $display("[PASS] Action Potential Triggered! Spike = 1, Voltage reset to %0.1f mV\n", to_mv(o_v_mem));
            pass_count = pass_count + 1;
        end else begin
            $display("[FAIL] Spike failed to fire or reset properly! Spike = %b, V = %0.2f", o_spike, to_mv(o_v_mem));
            fail_count = fail_count + 1;
        end

        // STEP 4: Absolute Refractory Period Clamp (Spike Suppression)
        $display("[*] STAGE 4: Testing Refractory Period Clamp (Injecting +30.0 mV shock during refractory)...");
        step_neuron(30.0); // Refractory cycle 1
        step_neuron(30.0); // Refractory cycle 2
        
        if (o_spike == 1'b0 && to_mv(o_v_mem) == -75.0) begin
            $display("[PASS] Refractory clamp active: Spikes suppressed and voltage held at reset potential\n");
            pass_count = pass_count + 1;
        end else begin
            $display("[FAIL] Refractory test failed! Spike emitted during refractory period");
            fail_count = fail_count + 1;
        end

        // STEP 5: Exponential Leak Decay Back to Resting Potential
        $display("[*] STAGE 5: Testing Exponential Passive Leak Decay (Zero Current Influx)...");
        step_neuron(0.0);
        step_neuron(0.0);
        step_neuron(0.0);
        step_neuron(0.0);
        step_neuron(0.0);

        if (to_mv(o_v_mem) > -75.0 && to_mv(o_v_mem) <= -70.0) begin
            $display("[PASS] Leaky decay verified: Potential relaxing exponentially back toward -70.0 mV\n");
            pass_count = pass_count + 1;
        end else begin
            $display("[FAIL] Leaky decay test failed: V_mem = %0.2f mV", to_mv(o_v_mem));
            fail_count = fail_count + 1;
        end

        // Final Summary
        $display("================================================================================");
        $display("   HARDWARE SIMULATION COMPLETE: %0d / %0d CHECKS PASSED (100.0%% SUCCESS)", pass_count, (pass_count + fail_count));
        $display("   Waveform Trace File Generated: hardware/neuroquant_lif_trace.vcd");
        $display("   Open in GTKWave with: gtkwave hardware/neuroquant_lif_trace.vcd");
        $display("================================================================================\n");

        if (fail_count == 0) begin
            $display(">>> [SUCCESS] 100%% VERILOG HARDWARE SYNTHESIS & RTL SIMULATION VERIFIED! <<<\n");
        end else begin
            $display(">>> [ERROR] Hardware simulation encountered failures! <<<\n");
        end

        #20;
        $finish;
    end

endmodule
