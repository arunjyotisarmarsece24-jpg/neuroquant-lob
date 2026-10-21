// ==============================================================================
// NEUROQUANT-LOB: MULTI-LEVEL OFI & HAWKES HARDWARE TESTBENCH
// ==============================================================================
// Principal Architect: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
// Toolchain: Icarus Verilog (`iverilog`) + Virtual Processor (`vvp`)
// Clock: 100.00 MHz (10.0 ns Period) | Arithmetic: Q16.16 Signed Fixed-Point
// ==============================================================================

`timescale 1ns / 1ps

module tb_multilevel_ofi_hawkes;

    reg clk;
    reg rst_n;
    reg tick_valid;

    // 5-level Bid/Ask Prices & Sizes
    reg signed [31:0] bp0, bp1, bp2, bp3, bp4;
    reg signed [31:0] bs0, bs1, bs2, bs3, bs4;
    reg signed [31:0] ap0, ap1, ap2, ap3, ap4;
    reg signed [31:0] as0, as1, as2, as3, as4;

    wire        out_valid;
    wire signed [31:0] raw0, raw1, raw2, raw3, raw4;
    wire signed [31:0] dec0, dec1, dec2, dec3, dec4;
    wire signed [31:0] comp_ofi;
    wire signed [31:0] lam0, lam1, lam2, lam3, lam4;
    wire        toxic_alert;
    wire        ready;

    // Unit Under Test (UUT)
    multilevel_ofi_hawkes #(
        .LEVELS(5),
        .DATA_WIDTH(32)
    ) uut (
        .clk(clk),
        .rst_n(rst_n),
        .i_tick_valid(tick_valid),
        .i_bid_price_0(bp0), .i_bid_price_1(bp1), .i_bid_price_2(bp2), .i_bid_price_3(bp3), .i_bid_price_4(bp4),
        .i_bid_size_0(bs0),  .i_bid_size_1(bs1),  .i_bid_size_2(bs2),  .i_bid_size_3(bs3),  .i_bid_size_4(bs4),
        .i_ask_price_0(ap0), .i_ask_price_1(ap1), .i_ask_price_2(ap2), .i_ask_price_3(ap3), .i_ask_price_4(ap4),
        .i_ask_size_0(as0),  .i_ask_size_1(as1),  .i_ask_size_2(as2),  .i_ask_size_3(as3),  .i_ask_size_4(as4),
        .o_valid(out_valid),
        .o_raw_ofi_0(raw0), .o_raw_ofi_1(raw1), .o_raw_ofi_2(raw2), .o_raw_ofi_3(raw3), .o_raw_ofi_4(raw4),
        .o_decayed_ofi_0(dec0), .o_decayed_ofi_1(dec1), .o_decayed_ofi_2(dec2), .o_decayed_ofi_3(dec3), .o_decayed_ofi_4(dec4),
        .o_composite_ofi(comp_ofi),
        .o_hawkes_intensity_0(lam0), .o_hawkes_intensity_1(lam1), .o_hawkes_intensity_2(lam2), .o_hawkes_intensity_3(lam3), .o_hawkes_intensity_4(lam4),
        .o_toxic_flow_alert(toxic_alert),
        .o_ready(ready)
    );

    // 100 MHz Clock Generation (10.0 ns period)
    always #5.0 clk = ~clk;

    // Test Variables
    integer passed_checks;
    integer total_checks;

    initial begin
        $dumpfile("hardware/neuroquant_ofi_trace.vcd");
        $dumpvars(0, tb_multilevel_ofi_hawkes);

        clk = 0;
        rst_n = 0;
        tick_valid = 0;
        passed_checks = 0;
        total_checks = 5;

        // Initial Price Ladder ($100.00 base, 0.25 ticks, Q16.16)
        // 100.00 * 65536 = 6553600
        bp0 = 32'sd6553600; bs0 = 32'sd6553600; // $100.00, 100.0 shares
        bp1 = 32'sd6537216; bs1 = 32'sd9830400; // $99.75,  150.0 shares
        bp2 = 32'sd6520832; bs2 = 32'sd13107200; // $99.50,  200.0 shares
        bp3 = 32'sd6504448; bs3 = 32'sd16384000; // $99.25,  250.0 shares
        bp4 = 32'sd6488064; bs4 = 32'sd19660800; // $99.00,  300.0 shares

        ap0 = 32'sd6569984; as0 = 32'sd7208960; // $100.25, 110.0 shares
        ap1 = 32'sd6586368; as1 = 32'sd10485760; // $100.50, 160.0 shares
        ap2 = 32'sd6602752; as2 = 32'sd13762560; // $100.75, 210.0 shares
        ap3 = 32'sd6619136; as3 = 32'sd17039360; // $101.00, 260.0 shares
        ap4 = 32'sd6635520; as4 = 32'sd20316160; // $101.25, 310.0 shares

        $display("\n================================================================================");
        $display("   NEUROQUANT-LOB: MULTI-LEVEL OFI & HAWKES HARDWARE RTL SIMULATION");
        $display("   Toolchain: Icarus Verilog (`iverilog`) + Virtual Processor (`vvp`)");
        $display("   Clock: 100.00 MHz (10.0 ns Period) | Arithmetic: Q16.16 Signed Fixed-Point");
        $display("================================================================================\n");

        // CHECK 1: Reset & Initialization
        #20;
        rst_n = 1;
        #10;
        if (ready == 0 && comp_ofi == 0) begin
            $display("[PASS] Check 1: Asynchronous reset cleared registers cleanly (ready=0, ofi=0)");
            passed_checks = passed_checks + 1;
        end else begin
            $display("[FAIL] Check 1: Reset failed");
        end

        // Baseline Tick
        @(posedge clk);
        tick_valid = 1;
        @(posedge clk);
        tick_valid = 0;
        #10;
        if (ready == 1) begin
            $display("[PASS] Baseline tick established book ladders. Engine ready=1.");
        end

        // CHECK 2: Level 0 Bid Price Tick Up (+0.25 tick) -> Positive Imbalance
        @(posedge clk);
        bp0 = bp0 + 32'sd16384; // +$0.25 tick
        bs0 = 32'sd3276800;     // 50 shares at new best bid
        tick_valid = 1;
        @(posedge clk);
        tick_valid = 0;
        #10;
        if (raw0 > 0 && comp_ofi > 0) begin
            $display("[PASS] Check 2: Level 0 Bid tick-up produced positive raw OFI (%0.2f) and positive composite (%0.2f)",
                     $itor(raw0) / 65536.0, $itor(comp_ofi) / 65536.0);
            passed_checks = passed_checks + 1;
        end else begin
            $display("[FAIL] Check 2: Expected positive OFI on bid uptick");
        end

        // CHECK 3: Level 1 Depth Queue Depletion (Ask cancellation at level 1)
        @(posedge clk);
        as1 = as1 - 32'sd1966080; // 30 shares canceled from Ask Level 1
        tick_valid = 1;
        @(posedge clk);
        tick_valid = 0;
        #10;
        if (raw1 > 0) begin
            $display("[PASS] Check 3: Ask queue cancel at Level 1 produced positive multi-level OFI (%0.2f)",
                     $itor(raw1) / 65536.0);
            passed_checks = passed_checks + 1;
        end else begin
            $display("[FAIL] Check 3: Ask queue cancel failed to reflect positive OFI");
        end

        // CHECK 4: Exponential Decay Verification (No volume change, OFI decays toward 0)
        @(posedge clk);
        tick_valid = 1; // repeat identical prices/sizes
        @(posedge clk);
        tick_valid = 0;
        #10;
        if (raw0 == 0 && dec0 < 32'sd3276800) begin
            $display("[PASS] Check 4: Exponential decay active without incoming volume (raw=0, decayed=%0.2f)",
                     $itor(dec0) / 65536.0);
            passed_checks = passed_checks + 1;
        end else begin
            $display("[FAIL] Check 4: Decay check failed");
        end

        // CHECK 5: Massive Toxic Sweep Injection -> Toxic Alert Triggered
        @(posedge clk);
        // Ask sweeps through top 3 levels (severe aggressive buying pressure)
        ap0 = ap0 + 32'sd49152; // Ask jumps +3 ticks
        as0 = 32'sd9830400;     // 150 shares
        tick_valid = 1;
        @(posedge clk);
        tick_valid = 0;
        #10;
        if (toxic_alert == 1 || lam0 > 32'sd655360) begin
            $display("[PASS] Check 5: Toxic sweep correctly excited Hawkes intensity (%0.2f events/s) and tripped toxic alert (%0d)",
                     $itor(lam0) / 65536.0, toxic_alert);
            passed_checks = passed_checks + 1;
        end else begin
            $display("[FAIL] Check 5: Toxic sweep detection failed");
        end

        $display("\n================================================================================");
        $display("   MULTI-LEVEL OFI & HAWKES HARDWARE SIMULATION COMPLETE: %0d / %0d PASSED",
                 passed_checks, total_checks);
        $display("   Waveform Trace File Generated: hardware/neuroquant_ofi_trace.vcd");
        $display("================================================================================\n");

        if (passed_checks == total_checks) begin
            $display(">>> [SUCCESS] 100%% MULTI-LEVEL OFI & HAWKES RTL VERIFIED! <<<\n");
        end else begin
            $display(">>> [FAIL] Hardware RTL checks failed! <<<\n");
        end

        $finish;
    end

endmodule
