// ==============================================================================
// EDA PLAYGROUND: NEUROQUANT-LOB COMPLETE FPGA RTL DESIGN
// ==============================================================================
// Instructions for www.edaplayground.com:
// 1. Paste this entire file into the left pane ('design.sv').
// 2. Paste 'edaplayground_testbench.v' into the right pane ('testbench.sv').
// 3. On the left sidebar:
//    - Tools & Simulators: Select "Icarus Verilog 0.10.0"
//    - Check the box: "Open EPWave after run"
// 4. Click the blue "Run" button!
// ==============================================================================

`timescale 1ns / 1ps

// ------------------------------------------------------------------------------
// 1. LEAKY INTEGRATE-AND-FIRE (LIF) NEUROMORPHIC CORE
// ------------------------------------------------------------------------------
module lif_neuron_core #(
    parameter signed [31:0] V_REST          = -32'sd4587520, // -70.0 mV * 65536
    parameter signed [31:0] V_THRESH        = -32'sd3604480, // -55.0 mV * 65536
    parameter signed [31:0] V_RESET         = -32'sd4915200, // -75.0 mV * 65536
    parameter signed [31:0] BETA            = 32'sd62259,    // 0.950 * 65536
    parameter signed [31:0] ONE_MINUS_BETA  = 32'sd3277,     // 0.050 * 65536
    parameter integer       REFRACTORY_CYC  = 2
)(
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire                 i_valid,
    input  wire signed [31:0]   i_syn_current,
    output reg                  o_spike,
    output reg  signed [31:0]   o_v_mem,
    output wire                 o_ready
);
    reg [3:0] refractory_counter;
    wire signed [63:0] mult_decay = $signed(o_v_mem) * $signed(BETA);
    wire signed [63:0] mult_rest  = $signed(V_REST)  * $signed(ONE_MINUS_BETA);
    wire signed [31:0] v_decayed  = mult_decay[47:16];
    wire signed [31:0] v_rest_comp= mult_rest[47:16];
    wire signed [31:0] v_next     = v_decayed + v_rest_comp + i_syn_current;

    assign o_ready = (refractory_counter == 4'd0);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            o_v_mem            <= V_REST;
            o_spike            <= 1'b0;
            refractory_counter <= 4'd0;
        end else begin
            if (refractory_counter > 4'd0) begin
                refractory_counter <= refractory_counter - 1'b1;
                o_spike            <= 1'b0;
                o_v_mem            <= V_RESET;
            end else if (i_valid) begin
                if (v_next >= V_THRESH) begin
                    o_spike            <= 1'b1;
                    o_v_mem            <= V_RESET;
                    refractory_counter <= REFRACTORY_CYC;
                end else begin
                    o_spike            <= 1'b0;
                    o_v_mem            <= v_next;
                end
            end else begin
                o_spike <= 1'b0;
                o_v_mem <= v_decayed + v_rest_comp;
            end
        end
    end
endmodule

// ------------------------------------------------------------------------------
// 2. AXI4-STREAM NASDAQ ITCH 5.0 HARDWARE FEED PARSER
// ------------------------------------------------------------------------------
module itch_parser_axi #(
    parameter DATA_WIDTH = 64
)(
    input  wire                   clk,
    input  wire                   rst_n,
    input  wire [DATA_WIDTH-1:0]  s_axis_tdata,
    input  wire [7:0]             s_axis_tkeep,
    input  wire                   s_axis_tvalid,
    output wire                   s_axis_tready,
    input  wire                   s_axis_tlast,
    output reg                    out_valid,
    output reg  [7:0]             out_msg_type,
    output reg  [63:0]            out_order_ref,
    output reg                    out_buy_sell,
    output reg  [31:0]            out_shares,
    output reg  [31:0]            out_price,
    output reg  [47:0]            out_timestamp,
    output reg  [15:0]            out_stock_locate
);
    localparam STATE_IDLE       = 3'd0;
    localparam STATE_PARSE_A_B1 = 3'd1;
    localparam STATE_PARSE_A_B2 = 3'd2;
    localparam STATE_PARSE_A_B3 = 3'd3;
    localparam STATE_PARSE_A_B4 = 3'd4;
    localparam STATE_PARSE_D_B1 = 3'd5;
    localparam STATE_PARSE_D_B2 = 3'd6;

    reg [2:0] state;
    assign s_axis_tready = 1'b1;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state            <= STATE_IDLE;
            out_valid        <= 1'b0;
            out_msg_type     <= 8'h00;
            out_order_ref    <= 64'd0;
            out_buy_sell     <= 1'b0;
            out_shares       <= 32'd0;
            out_price        <= 32'd0;
            out_timestamp    <= 48'd0;
            out_stock_locate <= 16'd0;
        end else begin
            out_valid <= 1'b0;
            case (state)
                STATE_IDLE: begin
                    if (s_axis_tvalid) begin
                        out_msg_type     <= s_axis_tdata[63:56];
                        out_stock_locate <= s_axis_tdata[55:40];
                        out_timestamp[47:24] <= s_axis_tdata[23:0];
                        if (s_axis_tdata[63:56] == 8'h41)
                            state <= STATE_PARSE_A_B1;
                        else if (s_axis_tdata[63:56] == 8'h44)
                            state <= STATE_PARSE_D_B1;
                    end
                end
                STATE_PARSE_A_B1: begin
                    if (s_axis_tvalid) begin
                        out_timestamp[23:0]   <= s_axis_tdata[63:40];
                        out_order_ref[63:24]  <= s_axis_tdata[39:0];
                        state                 <= STATE_PARSE_A_B2;
                    end
                end
                STATE_PARSE_A_B2: begin
                    if (s_axis_tvalid) begin
                        out_order_ref[23:0] <= s_axis_tdata[63:40];
                        out_buy_sell        <= (s_axis_tdata[39:32] == 8'h42) ? 1'b1 : 1'b0;
                        out_shares          <= s_axis_tdata[31:0];
                        state               <= STATE_PARSE_A_B3;
                    end
                end
                STATE_PARSE_A_B3: begin
                    if (s_axis_tvalid)
                        state <= STATE_PARSE_A_B4;
                end
                STATE_PARSE_A_B4: begin
                    if (s_axis_tvalid) begin
                        out_price <= s_axis_tdata[63:32];
                        out_valid <= 1'b1;
                        state     <= STATE_IDLE;
                    end
                end
                STATE_PARSE_D_B1: begin
                    if (s_axis_tvalid) begin
                        out_timestamp[23:0]  <= s_axis_tdata[63:40];
                        out_order_ref[63:24] <= s_axis_tdata[39:0];
                        state                <= STATE_PARSE_D_B2;
                    end
                end
                STATE_PARSE_D_B2: begin
                    if (s_axis_tvalid) begin
                        out_order_ref[23:0] <= s_axis_tdata[63:40];
                        out_valid           <= 1'b1;
                        state               <= STATE_IDLE;
                    end
                end
                default: state <= STATE_IDLE;
            endcase
        end
    end
endmodule

// ------------------------------------------------------------------------------
// 3. PRE-TRADE MICROSECOND HARDWARE RISK GATE CORE
// ------------------------------------------------------------------------------
module risk_gate_core (
    input  wire                   clk,
    input  wire                   rst_n,
    input  wire                   eval_valid,
    input  wire                   order_side,
    input  wire signed [31:0]     order_qty,
    input  wire signed [31:0]     order_price,
    input  wire signed [31:0]     market_mid_price,
    input  wire signed [31:0]     current_inventory,
    input  wire signed [31:0]     current_mtm_pnl,
    input  wire signed [31:0]     membrane_voltage,
    input  wire                   emergency_killswitch,
    input  wire signed [31:0]     cfg_max_order_size,
    input  wire signed [31:0]     cfg_max_inventory,
    input  wire signed [31:0]     cfg_collar_threshold,
    input  wire signed [31:0]     cfg_drawdown_limit,
    input  wire signed [31:0]     cfg_v_resting,
    input  wire signed [31:0]     cfg_lyapunov_threshold,
    output reg                    decision_valid,
    output reg                    order_approved,
    output reg  [7:0]             violation_code
);
    localparam CODE_APPROVED           = 8'h00;
    localparam CODE_KILLSWITCH_ACTIVE  = 8'h01;
    localparam CODE_COLLAR_BREACH      = 8'h02;
    localparam CODE_MAX_SIZE_BREACH    = 8'h03;
    localparam CODE_INVENTORY_LIMIT    = 8'h04;
    localparam CODE_DRAWDOWN_LIMIT     = 8'h05;
    localparam CODE_LYAPUNOV_INVARIANT = 8'h06;

    wire signed [31:0] price_diff = order_price - market_mid_price;
    wire signed [31:0] abs_price_dev = (price_diff < 0) ? -price_diff : price_diff;
    wire signed [31:0] signed_trade_qty = order_side ? order_qty : -order_qty;
    wire signed [31:0] projected_inventory = current_inventory + signed_trade_qty;
    wire signed [31:0] abs_projected_inv = (projected_inventory < 0) ? -projected_inventory : projected_inventory;
    wire signed [31:0] abs_current_inv   = (current_inventory < 0) ? -current_inventory : current_inventory;
    wire is_derisking = (abs_projected_inv < abs_current_inv);
    wire signed [31:0] v_diff = membrane_voltage - cfg_v_resting;
    wire signed [31:0] abs_v_dev = (v_diff < 0) ? -v_diff : v_diff;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            decision_valid <= 1'b0;
            order_approved <= 1'b0;
            violation_code <= CODE_APPROVED;
        end else if (eval_valid) begin
            decision_valid <= 1'b1;
            if (emergency_killswitch) begin
                order_approved <= 1'b0;
                violation_code <= CODE_KILLSWITCH_ACTIVE;
            end else if (abs_price_dev > cfg_collar_threshold) begin
                order_approved <= 1'b0;
                violation_code <= CODE_COLLAR_BREACH;
            end else if (order_qty > cfg_max_order_size) begin
                order_approved <= 1'b0;
                violation_code <= CODE_MAX_SIZE_BREACH;
            end else if ((abs_projected_inv > cfg_max_inventory) && (!is_derisking)) begin
                order_approved <= 1'b0;
                violation_code <= CODE_INVENTORY_LIMIT;
            end else if (current_mtm_pnl < cfg_drawdown_limit) begin
                order_approved <= 1'b0;
                violation_code <= CODE_DRAWDOWN_LIMIT;
            end else if (abs_v_dev > cfg_lyapunov_threshold) begin
                order_approved <= 1'b0;
                violation_code <= CODE_LYAPUNOV_INVARIANT;
            end else begin
                order_approved <= 1'b1;
                violation_code <= CODE_APPROVED;
            end
        end else begin
            decision_valid <= 1'b0;
        end
    end
endmodule

// ------------------------------------------------------------------------------
// 4. UNIFIED FPGA TOP-LEVEL ACCELERATOR
// ------------------------------------------------------------------------------
module neuroquant_fpga_top #(
    parameter DATA_WIDTH = 64
)(
    input  wire                   clk,
    input  wire                   rst_n,
    input  wire [DATA_WIDTH-1:0]  s_axis_tdata,
    input  wire [7:0]             s_axis_tkeep,
    input  wire                   s_axis_tvalid,
    output wire                   s_axis_tready,
    input  wire                   s_axis_tlast,
    input  wire                   sw_emergency_killswitch,
    input  wire                   i_manual_trigger,
    output wire                   led_ready,
    output wire                   led_itch_valid,
    output wire                   led_spike,
    output wire                   led_order_approved,
    output wire                   led_risk_violated,
    output wire [2:0]             led_violation_code,
    output wire signed [31:0]     o_membrane_voltage,
    output wire                   o_trade_out_valid
);
    wire        parser_valid;
    wire [7:0]  parser_msg_type;
    wire [63:0] parser_order_ref;
    wire        parser_buy_sell;
    wire [31:0] parser_shares;
    wire [31:0] parser_price;
    wire [47:0] parser_timestamp;
    wire [15:0] parser_locate;

    itch_parser_axi #(.DATA_WIDTH(DATA_WIDTH)) u_itch_parser (
        .clk(clk), .rst_n(rst_n),
        .s_axis_tdata(s_axis_tdata), .s_axis_tkeep(s_axis_tkeep),
        .s_axis_tvalid(s_axis_tvalid), .s_axis_tready(s_axis_tready),
        .s_axis_tlast(s_axis_tlast), .out_valid(parser_valid),
        .out_msg_type(parser_msg_type), .out_order_ref(parser_order_ref),
        .out_buy_sell(parser_buy_sell), .out_shares(parser_shares),
        .out_price(parser_price), .out_timestamp(parser_timestamp),
        .out_stock_locate(parser_locate)
    );

    reg signed [31:0] synaptic_current;
    reg               neuron_input_valid;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            synaptic_current   <= 32'sd0;
            neuron_input_valid <= 1'b0;
        end else begin
            if (parser_valid) begin
                neuron_input_valid <= 1'b1;
                if (parser_msg_type == 8'h41) begin
                    if (parser_shares > 32'd500)
                        synaptic_current <= 32'sd1310720; // +20.0 mV in Q16.16
                    else
                        synaptic_current <= 32'sd327680;  // +5.0 mV in Q16.16
                end else if (parser_msg_type == 8'h44) begin
                    synaptic_current <= -32'sd196608; // -3.0 mV in Q16.16
                end else begin
                    synaptic_current <= 32'sd0;
                end
            end else if (i_manual_trigger) begin
                neuron_input_valid <= 1'b1;
                synaptic_current   <= 32'sd1310720;
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
        .clk(clk), .rst_n(rst_n),
        .i_valid(neuron_input_valid), .i_syn_current(synaptic_current),
        .o_spike(neuron_spike), .o_v_mem(v_mem), .o_ready(neuron_ready)
    );

    assign o_membrane_voltage = v_mem;

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
            eval_side       <= 1'b1;
            eval_qty        <= 32'sd0;
            eval_price      <= 32'sd0;
            mid_price_reg   <= 32'sd4259840;
            current_inv_reg <= 32'sd0;
            mtm_pnl_reg     <= 32'sd0;
        end else begin
            if (neuron_spike) begin
                risk_eval_valid <= 1'b1;
                eval_side       <= 1'b1;
                eval_qty        <= 32'sd10;
                eval_price      <= mid_price_reg;
            end else begin
                risk_eval_valid <= 1'b0;
            end
        end
    end

    wire       decision_valid;
    wire       order_approved;
    wire [7:0] violation_code;

    risk_gate_core u_risk_gate (
        .clk(clk), .rst_n(rst_n),
        .eval_valid(risk_eval_valid), .order_side(eval_side),
        .order_qty(eval_qty), .order_price(eval_price),
        .market_mid_price(mid_price_reg), .current_inventory(current_inv_reg),
        .current_mtm_pnl(mtm_pnl_reg), .membrane_voltage(v_mem),
        .emergency_killswitch(sw_emergency_killswitch),
        .cfg_max_order_size(32'sd100), .cfg_max_inventory(32'sd50),
        .cfg_collar_threshold(32'sd500), .cfg_drawdown_limit(-32'sd50000),
        .cfg_v_resting(-32'sd4587520), .cfg_lyapunov_threshold(32'sd3276800),
        .decision_valid(decision_valid), .order_approved(order_approved),
        .violation_code(violation_code)
    );

    assign led_ready          = rst_n && neuron_ready;
    assign led_itch_valid     = parser_valid;
    assign led_spike          = neuron_spike;
    assign led_order_approved = decision_valid && order_approved;
    assign led_risk_violated  = decision_valid && (!order_approved);
    assign led_violation_code = violation_code[2:0];
    assign o_trade_out_valid  = decision_valid && order_approved;

endmodule
