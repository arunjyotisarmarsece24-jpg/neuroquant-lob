// ==============================================================================
// NEUROQUANT-LOB: UNIFIED FPGA ACCELERATOR TOP-LEVEL (SYNTHESIS & PHYSICAL RTL)
// ==============================================================================
// Principal Architect: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
// Target Architectures:
//   - AMD / Xilinx Artix-7 (Digilent Arty A7-35T / 100T, Basys3)
//   - AMD / Xilinx Kintex / UltraScale+ / Alveo U50 (322.26 MHz 10GbE Network MAC)
//   - Lattice ECP5 (Colorlight 5A-75B / 5A-75E Open-Source $18 FPGA)
// Standard: IEEE 1364-2001 Verilog HDL
//
// Subsystems Integrated:
//   1. 64-bit AXI4-Stream NASDAQ ITCH 5.0 Feed Parser (`itch_parser_axi`)
//   2. Signed Q16.16 Neuromorphic LIF Core (`lif_neuron_core`)
//   3. Single-Cycle Pre-Trade Institutional Risk Gate (`risk_gate_core`)
// ==============================================================================

`timescale 1ns / 1ps

module neuroquant_fpga_top #(
    parameter DATA_WIDTH = 64
)(
    // Master Clock & Reset Inputs
    input  wire                   clk,                 // Board oscillator (100MHz default or 322MHz network)
    input  wire                   rst_n,               // Active-low master reset

    // External AXI4-Stream Network Feed (From 10GbE MAC / DMA or Internal Loopback)
    input  wire [DATA_WIDTH-1:0]  s_axis_tdata,
    input  wire [7:0]             s_axis_tkeep,
    input  wire                   s_axis_tvalid,
    output wire                   s_axis_tready,
    input  wire                   s_axis_tlast,

    // External Physical Controls & Overrides (Switches / Registers)
    input  wire                   sw_emergency_killswitch,
    input  wire                   i_manual_trigger,    // Manual tick injection for board testing

    // Physical Diagnostic Output Telemetry (LEDs / PMOD / Logic Analyzer)
    output wire                   led_ready,           // High when subsystems initialized
    output wire                   led_itch_valid,      // Pulse when NASDAQ packet decoded
    output wire                   led_spike,           // Pulse when neuromorphic LIF neuron fires
    output wire                   led_order_approved,  // Pulse when Risk Gate approves order
    output wire                   led_risk_violated,   // High if trade was blocked by circuit breaker
    output wire [2:0]             led_violation_code,  // Lower 3 bits of breaker code
    output wire signed [31:0]     o_membrane_voltage,  // Real-time membrane voltage readout
    output wire                   o_trade_out_valid    // Order Execution Trigger to Outbound Network MAC
);

    // ==========================================================================
    // 1. NASDAQ ITCH 5.0 AXI4-STREAM PARSER INSTANTIATION
    // ==========================================================================
    wire        parser_valid;
    wire [7:0]  parser_msg_type;
    wire [63:0] parser_order_ref;
    wire        parser_buy_sell;
    wire [31:0] parser_shares;
    wire [31:0] parser_price;
    wire [47:0] parser_timestamp;
    wire [15:0] parser_locate;

    itch_parser_axi #(
        .DATA_WIDTH(DATA_WIDTH)
    ) u_itch_parser (
        .clk(clk),
        .rst_n(rst_n),
        .s_axis_tdata(s_axis_tdata),
        .s_axis_tkeep(s_axis_tkeep),
        .s_axis_tvalid(s_axis_tvalid),
        .s_axis_tready(s_axis_tready),
        .s_axis_tlast(s_axis_tlast),
        .out_valid(parser_valid),
        .out_msg_type(parser_msg_type),
        .out_order_ref(parser_order_ref),
        .out_buy_sell(parser_buy_sell),
        .out_shares(parser_shares),
        .out_price(parser_price),
        .out_timestamp(parser_timestamp),
        .out_stock_locate(parser_locate)
    );

    // ==========================================================================
    // 2. SYNAPTIC INFLUX MODULATOR & LIF NEURON INSTANTIATION
    // ==========================================================================
    // Modulates order book volume imbalance into physical synaptic current (Q16.16)
    reg signed [31:0] synaptic_current;
    reg               neuron_input_valid;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            synaptic_current   <= 32'sd0;
            neuron_input_valid <= 1'b0;
        end else begin
            if (parser_valid) begin
                neuron_input_valid <= 1'b1;
                // Add Order volume creates excitation current: +5.0 mV or +20.0 mV
                if (parser_msg_type == 8'h41) begin // 'A'
                    if (parser_shares > 32'd500)
                        synaptic_current <= 32'sd1310720; // +20.0 mV in Q16.16 (20 * 65536)
                    else
                        synaptic_current <= 32'sd327680;  // +5.0 mV in Q16.16 (5 * 65536)
                end else if (parser_msg_type == 8'h44) begin // 'D'
                    synaptic_current <= -32'sd196608; // -3.0 mV in Q16.16
                end else begin
                    synaptic_current <= 32'sd0;
                end
            end else if (i_manual_trigger) begin
                neuron_input_valid <= 1'b1;
                synaptic_current   <= 32'sd1310720; // +20.0 mV manual pulse
            end else begin
                neuron_input_valid <= 1'b0;
                synaptic_current   <= 32'sd0;
            end
        end
    end

    wire                 neuron_spike;
    wire signed [31:0]   v_mem;
    wire                 neuron_ready;

    lif_neuron_core u_lif_neuron (
        .clk(clk),
        .rst_n(rst_n),
        .i_valid(neuron_input_valid),
        .i_syn_current(synaptic_current),
        .o_spike(neuron_spike),
        .o_v_mem(v_mem),
        .o_ready(neuron_ready)
    );

    assign o_membrane_voltage = v_mem;

    // ==========================================================================
    // 3. PRE-TRADE MICROSECOND HARDWARE RISK GATE INSTANTIATION
    // ==========================================================================
    // When LIF fires an action potential, generate an optimal liquidation order
    reg               risk_eval_valid;
    reg               eval_side;
    reg signed [31:0] eval_qty;
    reg signed [31:0] eval_price;
    reg signed [31:0] mid_price_reg;
    reg signed [31:0] current_inv_reg;
    reg signed [31:0] mtm_pnl_reg;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            risk_eval_valid <= 1'b0;
            eval_side       <= 1'b1; // BUY
            eval_qty        <= 32'sd0;
            eval_price      <= 32'sd0;
            mid_price_reg   <= 32'sd4259840; // $65.00 in Q16.16 (65 * 65536)
            current_inv_reg <= 32'sd0;
            mtm_pnl_reg     <= 32'sd0;
        end else begin
            if (neuron_spike) begin
                // Trigger algorithmic trade on neuromorphic detection
                risk_eval_valid <= 1'b1;
                eval_side       <= 1'b1; // BUY
                eval_qty        <= 32'sd10; // 10 contracts
                eval_price      <= mid_price_reg; // At mid
            end else begin
                risk_eval_valid <= 1'b0;
            end
        end
    end

    wire       decision_valid;
    wire       order_approved;
    wire [7:0] violation_code;

    risk_gate_core u_risk_gate (
        .clk(clk),
        .rst_n(rst_n),
        .eval_valid(risk_eval_valid),
        .order_side(eval_side),
        .order_qty(eval_qty),
        .order_price(eval_price),
        .market_mid_price(mid_price_reg),
        .current_inventory(current_inv_reg),
        .current_mtm_pnl(mtm_pnl_reg),
        .membrane_voltage(v_mem),
        .emergency_killswitch(sw_emergency_killswitch),
        .cfg_max_order_size(32'sd100),         // Max 100 contracts
        .cfg_max_inventory(32'sd50),           // Net collar: +/- 50 contracts
        .cfg_collar_threshold(32'sd500),       // $500 collar
        .cfg_drawdown_limit(-32'sd50000),      // -$50,000 limit
        .cfg_v_resting(-32'sd4587520),         // -70.0 mV
        .cfg_lyapunov_threshold(32'sd3276800), // 50.0 mV Lyapunov bound (Theorem 1)
        .decision_valid(decision_valid),
        .order_approved(order_approved),
        .violation_code(violation_code)
    );

    // ==========================================================================
    // 4. PHYSICAL LED & TELEMETRY MAPPINGS
    // ==========================================================================
    assign led_ready          = rst_n && neuron_ready;
    assign led_itch_valid     = parser_valid;
    assign led_spike          = neuron_spike;
    assign led_order_approved = decision_valid && order_approved;
    assign led_risk_violated  = decision_valid && (!order_approved);
    assign led_violation_code = violation_code[2:0];
    assign o_trade_out_valid  = decision_valid && order_approved;

endmodule
