// ==============================================================================
// NEUROQUANT-LOB: HARDWARE FIX ENGINE TESTBENCH (DAY 5)
// ==============================================================================
`timescale 1ns / 1ps

module tb_fix_engine_bridge;

    reg clk;
    reg rst_n;
    reg [7:0] in_byte;
    reg in_valid;
    wire in_ready;

    wire [7:0] out_msg_type;
    wire out_side;
    wire [31:0] out_shares;
    wire signed [31:0] out_price;
    wire [31:0] out_order_ref;
    wire out_eval_valid;

    reg risk_approved;
    reg [7:0] risk_violation_code;

    wire exec_report_valid;
    wire exec_approved;
    wire [7:0] exec_violation_code;
    wire [23:0] exec_latency_cycles;

    integer checks_passed = 0;
    integer checks_total = 5;

    fix_engine_bridge #(
        .CLK_FREQ_HZ (100_000_000)
    ) uut (
        .clk                 (clk),
        .rst_n               (rst_n),
        .in_byte             (in_byte),
        .in_valid            (in_valid),
        .in_ready            (in_ready),
        .out_msg_type        (out_msg_type),
        .out_side            (out_side),
        .out_shares          (out_shares),
        .out_price           (out_price),
        .out_order_ref       (out_order_ref),
        .out_eval_valid      (out_eval_valid),
        .risk_approved       (risk_approved),
        .risk_violation_code (risk_violation_code),
        .exec_report_valid   (exec_report_valid),
        .exec_approved       (exec_approved),
        .exec_violation_code (exec_violation_code),
        .exec_latency_cycles (exec_latency_cycles)
    );

    always #5 clk = ~clk; // 100 MHz clock (10 ns)

    task send_fix_byte(input [7:0] b);
        begin
            @(posedge clk);
            in_byte  = b;
            in_valid = 1'b1;
            @(posedge clk);
            in_valid = 1'b0;
        end
    endtask

    initial begin
        $dumpfile("hardware/neuroquant_fix_trace.vcd");
        $dumpvars(0, tb_fix_engine_bridge);

        clk = 0;
        rst_n = 0;
        in_byte = 0;
        in_valid = 0;
        risk_approved = 1;
        risk_violation_code = 0;

        #30;
        rst_n = 1;
        #20;

        // Check 1: Reset state
        if (uut.state == 3'd0 && in_ready == 1'b1) begin
            $display("[PASS] Check 1: Asynchronous reset initialized cleanly");
            checks_passed = checks_passed + 1;
        end else begin
            $display("[FAIL] Check 1: Reset failed");
        end

        // Stream Sample FIX message: "35=D\x0138=100\x0154=1\x0110=182\x01"
        send_fix_byte("3");
        send_fix_byte("5");
        send_fix_byte("=");
        send_fix_byte("D");
        send_fix_byte(8'h01);

        // Check 2: MsgType decoded
        if (out_msg_type == 8'h44) begin
            $display("[PASS] Check 2: MsgType 35=D decoded cleanly");
            checks_passed = checks_passed + 1;
        end else begin
            $display("[FAIL] Check 2: MsgType decode failed (got %h)", out_msg_type);
        end

        // Send Tag 38=100
        send_fix_byte("3");
        send_fix_byte("8");
        send_fix_byte("=");
        send_fix_byte("1");
        send_fix_byte("0");
        send_fix_byte("0");
        send_fix_byte(8'h01);

        // Check 3: Shares decoded
        if (out_shares == 32'd100) begin
            $display("[PASS] Check 3: OrderQty Tag 38=100 decoded cleanly");
            checks_passed = checks_passed + 1;
        end else begin
            $display("[FAIL] Check 3: Shares decode failed (got %d)", out_shares);
        end

        // Send Tag 54=1
        send_fix_byte("5");
        send_fix_byte("4");
        send_fix_byte("=");
        send_fix_byte("1");
        send_fix_byte(8'h01);

        // Send Tag 10=182 (Checksum triggers evaluation)
        send_fix_byte("1");
        send_fix_byte("0");
        send_fix_byte("=");
        send_fix_byte("1");
        send_fix_byte("8");
        send_fix_byte("2");
        send_fix_byte(8'h01);

        // Check 4: Pre-trade evaluation triggered
        @(posedge clk);
        if (uut.state == 3'd3 || out_eval_valid == 1'b1 || exec_report_valid == 1'b1) begin
            $display("[PASS] Check 4: Pre-trade risk evaluation triggered on message completion");
            checks_passed = checks_passed + 1;
        end else begin
            $display("[FAIL] Check 4: Evaluation trigger failed");
        end

        // Check 5: ExecutionReport generated with sub-10us latency
        #30;
        if (exec_approved == 1'b1 && exec_latency_cycles < 24'd1000) begin
            $display("[PASS] Check 5: ExecutionReport approved in %0d cycles (< 10us SLA)", exec_latency_cycles);
            checks_passed = checks_passed + 1;
        end else begin
            $display("[FAIL] Check 5: ExecutionReport failed (approved=%b, cycles=%d)", exec_approved, exec_latency_cycles);
        end

        $display("----------------------------------------------------------------");
        $display("FIX ENGINE BRIDGE VERILOG RESULT: %0d / %0d CHECKS PASSED", checks_passed, checks_total);
        $display("----------------------------------------------------------------");

        if (checks_passed == checks_total) begin
            $display(">>> ALL HARDWARE FIX ENGINE BRIDGE CHECKS PASSED (100.0%%) <<<");
        end else begin
            $display(">>> SOME CHECKS FAILED <<<");
        end

        $finish;
    end

endmodule
