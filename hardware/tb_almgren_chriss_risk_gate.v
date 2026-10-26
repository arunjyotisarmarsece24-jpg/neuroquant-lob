// =============================================================================
// NEUROQUANT-LOB: ALMGREN-CHRISS RISK GATE CYCLE-ACCURATE TESTBENCH (SELF-CHECKING)
// =============================================================================
// Principal Architect: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
// Target Simulation: Icarus Verilog (`iverilog` + `vvp`)
// =============================================================================

`timescale 1ns / 1ps
`include "optimal_almgren_params.vh"

module tb_almgren_chriss_risk_gate;

    reg                   clk;
    reg                   rst_n;
    reg                   eval_valid;
    reg                   order_side;
    reg signed [31:0]     order_qty;
    reg signed [31:0]     interval_dt_q16;
    reg signed [31:0]     order_price_q16;
    reg signed [31:0]     market_mid_q16;
    reg signed [31:0]     target_total_shares;
    reg                   neuro_urgency_boost;

    reg signed [31:0]     cfg_max_rate_cap_q16;
    reg signed [31:0]     cfg_slippage_tol_q16;

    wire                  decision_valid;
    wire                  order_approved;
    wire [7:0]            violation_code;
    wire signed [31:0]    cumulative_executed;
    wire signed [31:0]    remaining_inventory;
    wire signed [31:0]    current_rate_q16;

    integer checks_passed = 0;
    integer checks_total  = 0;

    // Instantiate Unit Under Test
    almgren_chriss_risk_gate uut (
        .clk(clk),
        .rst_n(rst_n),
        .eval_valid(eval_valid),
        .order_side(order_side),
        .order_qty(order_qty),
        .interval_dt_q16(interval_dt_q16),
        .order_price_q16(order_price_q16),
        .market_mid_q16(market_mid_q16),
        .target_total_shares(target_total_shares),
        .neuro_urgency_boost(neuro_urgency_boost),
        .cfg_max_rate_cap_q16(cfg_max_rate_cap_q16),
        .cfg_slippage_tol_q16(cfg_slippage_tol_q16),
        .decision_valid(decision_valid),
        .order_approved(order_approved),
        .violation_code(violation_code),
        .cumulative_executed(cumulative_executed),
        .remaining_inventory(remaining_inventory),
        .current_rate_q16(current_rate_q16)
    );

    always #5 clk = ~clk; // 100 MHz clock (10 ns period)

    initial begin
        $dumpfile("hardware/neuroquant_almgren_trace.vcd");
        $dumpvars(0, tb_almgren_chriss_risk_gate);

        $display("\n================================================================================");
        $display("   NEUROQUANT-LOB: ALMGREN-CHRISS RISK GATE CYCLE-ACCURATE RTL SIMULATION");
        $display("   Clock: 100.00 MHz (10.0 ns) | Pre-Trade Hardware Execution Gate (Day 3)");
        $display("================================================================================\n");

        clk = 0;
        rst_n = 0;
        eval_valid = 0;
        order_side = 0; // SELL liquidation
        order_qty = 32'sd0;
        interval_dt_q16 = 32'sd131072; // 2.0 seconds in Q16.16
        order_price_q16 = 32'sd1212416000; // $18,500.00 in Q16.16
        market_mid_q16 = 32'sd1212416000;  // $18,500.00 in Q16.16
        target_total_shares = 32'sd10000;  // 10,000 shares
        neuro_urgency_boost = 0;

        cfg_max_rate_cap_q16 = AC_MAX_RATE_CAP_Q16;
        cfg_slippage_tol_q16 = AC_SLIPPAGE_TOL_Q16;

        #20;
        rst_n = 1;
        #10;

        // ---------------------------------------------------------------------
        // CHECK 1: Reset Behavior & Inventory Initialization
        // ---------------------------------------------------------------------
        checks_total = checks_total + 1;
        if (remaining_inventory == 32'sd10000 && cumulative_executed == 32'sd0 && decision_valid == 1'b0) begin
            $display("[PASS] Check 1: Asynchronous reset initialized inventory (rem=%0d, cum=%0d, valid=0)",
                     remaining_inventory, cumulative_executed);
            checks_passed = checks_passed + 1;
        end else begin
            $display("[FAIL] Check 1: Reset initialization failed!");
        end

        // ---------------------------------------------------------------------
        // CHECK 2: Normal Compliant Execution Slice (300 shares / 2.0s = 150 shares/s)
        // ---------------------------------------------------------------------
        @(negedge clk);
        eval_valid = 1'b1;
        order_qty  = 32'sd300;
        interval_dt_q16 = 32'sd131072; // 2.0s
        order_price_q16 = market_mid_q16 - 32'sd6553; // $0.10 slippage (allowed)
        neuro_urgency_boost = 1'b0;

        @(posedge clk);
        #1;
        checks_total = checks_total + 1;
        if (order_approved == 1'b1 && violation_code == 8'h00 && cumulative_executed == 32'sd300 && remaining_inventory == 32'sd9700) begin
            $display("[PASS] Check 2: Compliant slice approved (qty=300, rate=%0.2f sh/s, rem=%0d)",
                     $itor(current_rate_q16) / 65536.0, remaining_inventory);
            checks_passed = checks_passed + 1;
        end else begin
            $display("[FAIL] Check 2: Compliant execution failed! code=0x%02h approved=%0d", violation_code, order_approved);
        end

        // ---------------------------------------------------------------------
        // CHECK 3: Rate Limit Violation (4,000 shares / 2.0s = 2000 shares/s > Cap)
        // ---------------------------------------------------------------------
        @(negedge clk);
        eval_valid = 1'b1;
        order_qty  = 32'sd4000; // Rate = 2000 > max rate cap (~1591.5)
        order_price_q16 = market_mid_q16;
        neuro_urgency_boost = 1'b0;

        @(posedge clk);
        #1;
        checks_total = checks_total + 1;
        if (order_approved == 1'b0 && violation_code == 8'h11) begin
            $display("[PASS] Check 3: Over-aggressive rate rejected (rate=%0.2f sh/s > cap=%0.2f, code=0x%02h)",
                     $itor(current_rate_q16) / 65536.0, $itor(cfg_max_rate_cap_q16) / 65536.0, violation_code);
            checks_passed = checks_passed + 1;
        end else begin
            $display("[FAIL] Check 3: Rate limit check failed! code=0x%02h approved=%0d rate=%0.2f cap=%0.2f", 
                     violation_code, order_approved, $itor(current_rate_q16) / 65536.0, $itor(cfg_max_rate_cap_q16) / 65536.0);
        end

        // ---------------------------------------------------------------------
        // CHECK 4: Slippage Collar Breach ($2.50 price slippage > tolerance)
        // ---------------------------------------------------------------------
        @(negedge clk);
        eval_valid = 1'b1;
        order_qty  = 32'sd200; // Rate = 100 sh/s (compliant)
        order_price_q16 = market_mid_q16 - 32'sd163840; // $2.50 slippage (exceeds tolerance of ~$0.25)
        neuro_urgency_boost = 1'b0;

        @(posedge clk);
        #1;
        checks_total = checks_total + 1;
        if (order_approved == 1'b0 && violation_code == 8'h12) begin
            $display("[PASS] Check 4: Slippage collar breach rejected (slippage=$2.50 > tol, code=0x%02h)", violation_code);
            checks_passed = checks_passed + 1;
        end else begin
            $display("[FAIL] Check 4: Slippage collar check failed! code=0x%02h approved=%0d", violation_code, order_approved);
        end

        // ---------------------------------------------------------------------
        // CHECK 5: Neuromorphic Urgency Rate Expansion (3,600 shares / 2.0s = 1800 sh/s)
        // ---------------------------------------------------------------------
        @(negedge clk);
        eval_valid = 1'b1;
        // Rate = 1800 sh/s. Normally > cap of 1591.5 sh/s.
        // Under urgency boost, effective cap = 1591.5 * 1.5 = 2387.2 sh/s!
        order_qty  = 32'sd3600; 
        order_price_q16 = market_mid_q16 - 32'sd6553; // $0.10 slippage (compliant)
        neuro_urgency_boost = 1'b1; // Toxicity boost active!

        @(posedge clk);
        #1;
        checks_total = checks_total + 1;
        if (order_approved == 1'b1 && violation_code == 8'h00) begin
            $display("[PASS] Check 5: Neuromorphic urgency approved dynamic rate expansion (boost=1, rate=%0.2f sh/s)",
                     $itor(current_rate_q16) / 65536.0);
            checks_passed = checks_passed + 1;
        end else begin
            $display("[FAIL] Check 5: Urgency expansion check failed! code=0x%02h approved=%0d rate=%0.2f", 
                     violation_code, order_approved, $itor(current_rate_q16) / 65536.0);
        end

        // ---------------------------------------------------------------------
        // CHECK 6: Cumulative Inventory Overshoot Protection
        // ---------------------------------------------------------------------
        @(negedge clk);
        eval_valid = 1'b1;
        // Cumulative executed so far: 300 (check 2) + 3600 (check 5) = 3900.
        // Remaining: 10000 - 3900 = 6100.
        // Attempt 7000 shares in 10.0 seconds (rate = 700 sh/s < 1591.5, so rate is fine, but inventory overshoots!)
        order_qty  = 32'sd7000;
        interval_dt_q16 = 32'sd655360; // 10.0 seconds in Q16.16
        order_price_q16 = market_mid_q16;
        neuro_urgency_boost = 1'b0;

        @(posedge clk);
        #1;
        checks_total = checks_total + 1;
        if (order_approved == 1'b0 && violation_code == 8'h13) begin
            $display("[PASS] Check 6: Cumulative inventory overshoot blocked (qty=7000, rem=%0d, code=0x%02h)",
                     remaining_inventory, violation_code);
            checks_passed = checks_passed + 1;
        end else begin
            $display("[FAIL] Check 6: Overshoot protection failed! code=0x%02h approved=%0d", violation_code, order_approved);
        end

        @(negedge clk);
        eval_valid = 1'b0;
        #20;

        $display("\n--------------------------------------------------------------------------------");
        $display("ALMGREN-CHRISS RISK GATE SIMULATION RESULT: %0d / %0d CHECKS PASSED", checks_passed, checks_total);
        $display("--------------------------------------------------------------------------------\n");

        if (checks_passed == checks_total) begin
            $display(">>> ALL ALMGREN-CHRISS HARDWARE RTL CHECKS PASSED (100.0%%) <<<\n");
            $finish;
        end else begin
            $display(">>> HARDWARE RTL TESTBENCH ENCOUNTERED FAILURES <<<\n");
            $fatal(1);
        end
    end

endmodule
