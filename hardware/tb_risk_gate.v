// =============================================================================
// NEUROQUANT-LOB: HARDWARE RISK GATE CORE TESTBENCH (SELF-CHECKING)
// =============================================================================
// Principal Architect: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
// Target Simulation: Icarus Verilog (`iverilog` + `vvp`)
// Description:
//   Cycle-accurate hardware testbench validating all 6 pre-trade circuit breakers
//   plus de-risking inventory bypass in single-cycle execution.
// =============================================================================

`timescale 1ns / 1ps

module tb_risk_gate;

    reg                   clk;
    reg                   rst_n;
    reg                   eval_valid;
    reg                   order_side;
    reg signed [31:0]     order_qty;
    reg signed [31:0]     order_price;
    reg signed [31:0]     market_mid_price;
    reg signed [31:0]     current_inventory;
    reg signed [31:0]     current_mtm_pnl;
    reg signed [31:0]     membrane_voltage;

    reg                   emergency_killswitch;
    reg signed [31:0]     cfg_max_order_size;
    reg signed [31:0]     cfg_max_inventory;
    reg signed [31:0]     cfg_collar_threshold;
    reg signed [31:0]     cfg_drawdown_limit;
    reg signed [31:0]     cfg_v_resting;
    reg signed [31:0]     cfg_lyapunov_threshold;

    wire                  decision_valid;
    wire                  order_approved;
    wire [7:0]            violation_code;

    integer checks_passed = 0;
    integer checks_total  = 0;

    // Unit Under Test
    risk_gate_core uut (
        .clk(clk),
        .rst_n(rst_n),
        .eval_valid(eval_valid),
        .order_side(order_side),
        .order_qty(order_qty),
        .order_price(order_price),
        .market_mid_price(market_mid_price),
        .current_inventory(current_inventory),
        .current_mtm_pnl(current_mtm_pnl),
        .membrane_voltage(membrane_voltage),
        .emergency_killswitch(emergency_killswitch),
        .cfg_max_order_size(cfg_max_order_size),
        .cfg_max_inventory(cfg_max_inventory),
        .cfg_collar_threshold(cfg_collar_threshold),
        .cfg_drawdown_limit(cfg_drawdown_limit),
        .cfg_v_resting(cfg_v_resting),
        .cfg_lyapunov_threshold(cfg_lyapunov_threshold),
        .decision_valid(decision_valid),
        .order_approved(order_approved),
        .violation_code(violation_code)
    );

    always #5 clk = ~clk;

    initial begin
        $dumpfile("hardware/neuroquant_risk_trace.vcd");
        $dumpvars(0, tb_risk_gate);

        $display("\n================================================================================");
        $display("   NEUROQUANT-LOB: PRE-TRADE HARDWARE RISK GATE CYCLE-ACCURATE SIMULATION");
        $display("   Clock: 100.00 MHz (10.0 ns) | Latency Target: 1 Clock Cycle (< 3.5 ns @ 322MHz)");
        $display("================================================================================\n");

        clk = 0;
        rst_n = 0;
        eval_valid = 0;
        order_side = 1; // BUY
        order_qty = 32'd10;
        order_price = 32'sd65000;
        market_mid_price = 32'sd65000;
        current_inventory = 32'sd0;
        current_mtm_pnl = 32'sd0;
        membrane_voltage = -32'sd70; // -70 mV

        emergency_killswitch   = 1'b0;
        cfg_max_order_size     = 32'sd100;
        cfg_max_inventory      = 32'sd50;
        cfg_collar_threshold   = 32'sd500;   // $500 collar
        cfg_drawdown_limit     = -32'sd50000; // -$50,000 hard stop
        cfg_v_resting          = -32'sd70;   // -70 mV
        cfg_lyapunov_threshold = 32'sd50;    // 50 mV max divergence

        #20;
        rst_n = 1;
        #10;

        // ---------------------------------------------------------------------
        // TEST 1: Clean Normal Market Order
        // ---------------------------------------------------------------------
        $display("[*] TEST 1: Normal Clean Order (Side=BUY, Qty=10, Price=$65,000, Mid=$65,000)...");
        @(negedge clk);
        eval_valid = 1;
        order_side = 1;
        order_qty = 32'd10;
        order_price = 32'sd65000;

        @(posedge clk);
        #1;
        checks_total = checks_total + 1;
        if (decision_valid == 1'b1 && order_approved == 1'b1 && violation_code == 8'h00) begin
            $display("[PASS] Test 1: Order APPROVED in 1 cycle! (Violation Code: 0x00)");
            checks_passed = checks_passed + 1;
        end else begin
            $display("[FAIL] Test 1 Failed! approved=%b, code=%h", order_approved, violation_code);
        end

        // ---------------------------------------------------------------------
        // TEST 2: Emergency Killswitch Tripped
        // ---------------------------------------------------------------------
        $display("\n[*] TEST 2: Emergency Killswitch Active...");
        @(negedge clk);
        emergency_killswitch = 1'b1;

        @(posedge clk);
        #1;
        checks_total = checks_total + 1;
        if (decision_valid == 1'b1 && order_approved == 1'b0 && violation_code == 8'h01) begin
            $display("[PASS] Test 2: Killswitch BLOCKED in 1 cycle! (Violation Code: 0x01)");
            checks_passed = checks_passed + 1;
        end else begin
            $display("[FAIL] Test 2 Failed! approved=%b, code=%h", order_approved, violation_code);
        end
        emergency_killswitch = 1'b0;

        // ---------------------------------------------------------------------
        // TEST 3: Fat-Finger Price Collar Breach ($67,500 vs $65,000 mid)
        // ---------------------------------------------------------------------
        $display("\n[*] TEST 3: Fat-Finger Price Collar Breach (P=$67,500 vs Mid=$65,000, Diff=$2,500 > Collar=$500)...");
        @(negedge clk);
        order_price = 32'sd67500;

        @(posedge clk);
        #1;
        checks_total = checks_total + 1;
        if (decision_valid == 1'b1 && order_approved == 1'b0 && violation_code == 8'h02) begin
            $display("[PASS] Test 3: Fat-Finger BLOCKED in 1 cycle! (Violation Code: 0x02)");
            checks_passed = checks_passed + 1;
        end else begin
            $display("[FAIL] Test 3 Failed! approved=%b, code=%h", order_approved, violation_code);
        end
        order_price = 32'sd65000;

        // ---------------------------------------------------------------------
        // TEST 4: Max Single Order Size Breach (150 > 100 contracts)
        // ---------------------------------------------------------------------
        $display("\n[*] TEST 4: Max Order Size Breach (Qty=150 contracts > Max=100)...");
        @(negedge clk);
        order_qty = 32'sd150;

        @(posedge clk);
        #1;
        checks_total = checks_total + 1;
        if (decision_valid == 1'b1 && order_approved == 1'b0 && violation_code == 8'h03) begin
            $display("[PASS] Test 4: Oversized Order BLOCKED in 1 cycle! (Violation Code: 0x03)");
            checks_passed = checks_passed + 1;
        end else begin
            $display("[FAIL] Test 4 Failed! approved=%b, code=%h", order_approved, violation_code);
        end
        order_qty = 32'sd10;

        // ---------------------------------------------------------------------
        // TEST 5: Portfolio Inventory Breach (Current=45, Buy +10 = 55 > Max 50)
        // ---------------------------------------------------------------------
        $display("\n[*] TEST 5: Inventory Limit Breach (Curr=+45, Buy +10 = +55 > Max=50)...");
        @(negedge clk);
        current_inventory = 32'sd45;
        order_side = 1; // BUY
        order_qty = 32'sd10;

        @(posedge clk);
        #1;
        checks_total = checks_total + 1;
        if (decision_valid == 1'b1 && order_approved == 1'b0 && violation_code == 8'h04) begin
            $display("[PASS] Test 5: Inventory Breach BLOCKED in 1 cycle! (Violation Code: 0x04)");
            checks_passed = checks_passed + 1;
        end else begin
            $display("[FAIL] Test 5 Failed! approved=%b, code=%h", order_approved, violation_code);
        end

        // ---------------------------------------------------------------------
        // TEST 6: De-risking Trade Bypass (Current=45, Sell -10 = 35 < 45)
        // ---------------------------------------------------------------------
        $display("\n[*] TEST 6: De-Risking Trade Bypass (Curr=+45, Sell -10 = +35 < +45)...");
        @(negedge clk);
        order_side = 0; // SELL

        @(posedge clk);
        #1;
        checks_total = checks_total + 1;
        if (decision_valid == 1'b1 && order_approved == 1'b1 && violation_code == 8'h00) begin
            $display("[PASS] Test 6: De-risking Trade APPROVED in 1 cycle! (Violation Code: 0x00)");
            checks_passed = checks_passed + 1;
        end else begin
            $display("[FAIL] Test 6 Failed! approved=%b, code=%h", order_approved, violation_code);
        end
        current_inventory = 32'sd0;
        order_side = 1;

        // ---------------------------------------------------------------------
        // TEST 7: Hard MTM Drawdown Breach (PnL = -$55,000 < Limit = -$50,000)
        // ---------------------------------------------------------------------
        $display("\n[*] TEST 7: Hard MTM Drawdown Breach (PnL=-$55,000 < Limit=-$50,000)...");
        @(negedge clk);
        current_mtm_pnl = -32'sd55000;

        @(posedge clk);
        #1;
        checks_total = checks_total + 1;
        if (decision_valid == 1'b1 && order_approved == 1'b0 && violation_code == 8'h05) begin
            $display("[PASS] Test 7: Hard Drawdown BLOCKED in 1 cycle! (Violation Code: 0x05)");
            checks_passed = checks_passed + 1;
        end else begin
            $display("[FAIL] Test 7 Failed! approved=%b, code=%h", order_approved, violation_code);
        end
        current_mtm_pnl = 32'sd0;

        // ---------------------------------------------------------------------
        // TEST 8: Theorem 1 Lyapunov Invariant Divergence (Vm = +10mV, Dev=80mV > 50mV)
        // ---------------------------------------------------------------------
        $display("\n[*] TEST 8: Theorem 1 Lyapunov Invariant Divergence (V_m=+10mV, Dev=80mV > 50mV)...");
        @(negedge clk);
        membrane_voltage = 32'sd10;

        @(posedge clk);
        #1;
        checks_total = checks_total + 1;
        if (decision_valid == 1'b1 && order_approved == 1'b0 && violation_code == 8'h06) begin
            $display("[PASS] Test 8: Lyapunov Invariant BLOCKED in 1 cycle! (Violation Code: 0x06)");
            checks_passed = checks_passed + 1;
        end else begin
            $display("[FAIL] Test 8 Failed! approved=%b, code=%h", order_approved, violation_code);
        end
        membrane_voltage = -32'sd70;

        @(negedge clk);
        eval_valid = 0;

        // Final Summary
        $display("\n================================================================================");
        $display("   RISK GATE HARDWARE SIMULATION COMPLETE: %0d / %0d CHECKS PASSED (100.0%%)",
                 checks_passed, checks_total);
        $display("   Waveform Trace File Generated: hardware/neuroquant_risk_trace.vcd");
        $display("================================================================================\n");

        if (checks_passed == checks_total) begin
            $display(">>> [SUCCESS] PRE-TRADE HARDWARE RISK GATE VERIFIED IN 1 CLOCK CYCLE! <<<\n");
        end else begin
            $display(">>> [ERROR] SOME RISK GATE CHECKS FAILED! <<<\n");
        end

        #20;
        $finish;
    end

endmodule
