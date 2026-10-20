// ==============================================================================
// NEUROQUANT-LOB: DIGILENT ARTY S7 + ESP8266 PHYSICAL TOP-LEVEL ACCELERATOR
// ==============================================================================
// Principal Architect: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
// Target Architecture: AMD / Xilinx Spartan-7 (XC7S50-CSGA324 / XC7S25)
// Physical Board:      Digilent Arty S7-50 / Arty S7-25
// Hardware Interface:  PMOD JA UART Bridge to NodeMCU ESP8266 Wi-Fi Gateway
// Standard:            IEEE 1364-2001 Verilog HDL
// ==============================================================================

`timescale 1ns / 1ps

module neuroquant_arty_s7_top #(
    parameter CLK_FREQ_HZ = 100_000_000,
    parameter BAUD_RATE   = 921_600
)(
    // Master Oscillator: 100 MHz onboard clock (Pin R2 on Arty S7-50)
    input  wire                   clk_100mhz,

    // Active-Low Reset (Button 0 on Pin C18 / G15)
    input  wire                   btn_rst_n,

    // Slide Switches
    input  wire                   sw_killswitch,       // SW0 (Pin H14): Emergency Circuit Breaker
    input  wire                   sw_bypass_parser,    // SW1 (Pin H18): Synthetic internal tick mode

    // Push Buttons
    input  wire                   btn_manual_tick,     // BTN1 (Pin K16): Inject single test tick

    // PMOD Header JA (Serial Interface to NodeMCU ESP8266)
    input  wire                   ja_uart_rx,          // JA Pin 1 (Pin L17): RX from ESP8266 TX
    output wire                   ja_uart_tx,          // JA Pin 2 (Pin L18): TX to ESP8266 RX
    output wire                   ja_exec_strobe,      // JA Pin 3 (Pin M14): Outbound Trade Execution Strobe
    output wire                   ja_spike_strobe,     // JA Pin 4 (Pin N14): Neuromorphic Action Potential Spike

    // Physical Diagnostic LEDs (Green LEDs LD0 - LD3)
    output wire                   led0_ready,          // LD0 (Pin E18): Accelerator System Initialized
    output wire                   led1_rx_sync,        // LD1 (Pin F13): ESP8266 Frame Synchronized
    output wire                   led2_spike,          // LD2 (Pin E13): LIF Spiking Pulse
    output wire                   led3_approved,       // LD3 (Pin H15): Pre-Trade Risk Gate Approved

    // RGB LED 0 (LD4): Breaker Violation Status
    output wire                   rgb0_r,              // LD4 Red (Pin F15): Risk Breached
    output wire                   rgb0_g,              // LD4 Green (Pin J15): Clean State
    output wire                   rgb0_b               // LD4 Blue (Pin G17): Ingress Active
);

    // -------------------------------------------------------------------------
    // Internal AXI4-Stream Interconnect: UART RX -> Core Engine
    // -------------------------------------------------------------------------
    wire [63:0] s_axis_tdata;
    wire [7:0]  s_axis_tkeep;
    wire        s_axis_tvalid;
    wire        s_axis_tready;
    wire        s_axis_tlast;

    wire        rx_frame_sync;
    wire        rx_byte_valid;
    wire [7:0]  rx_byte_out;
    wire [31:0] rx_packet_count;
    wire [31:0] rx_error_count;

    // Subsystem Telemetry Signals
    wire        core_ready;
    wire        core_itch_valid;
    wire        core_spike;
    wire        core_order_approved;
    wire        core_risk_violated;
    wire [2:0]  core_violation_code;
    wire signed [31:0] core_membrane_voltage;
    wire        core_trade_out_valid;

    // -------------------------------------------------------------------------
    // 1. High-Speed UART Receiver (Deserializes ESP8266 Serial Ticks)
    // -------------------------------------------------------------------------
    uart_rx_bridge #(
        .CLK_FREQ_HZ (CLK_FREQ_HZ),
        .BAUD_RATE   (BAUD_RATE),
        .DATA_WIDTH  (64)
    ) u_uart_rx (
        .clk             (clk_100mhz),
        .rst_n           (btn_rst_n),
        .uart_rx         (ja_uart_rx),
        .m_axis_tdata    (s_axis_tdata),
        .m_axis_tkeep    (s_axis_tkeep),
        .m_axis_tvalid   (s_axis_tvalid),
        .m_axis_tready   (s_axis_tready),
        .m_axis_tlast    (s_axis_tlast),
        .rx_frame_sync   (rx_frame_sync),
        .rx_byte_valid   (rx_byte_valid),
        .rx_byte_out     (rx_byte_out),
        .rx_packet_count (rx_packet_count),
        .rx_error_count  (rx_error_count)
    );

    // -------------------------------------------------------------------------
    // 2. Core Neuromorphic Quant Accelerator (LIF + ITCH + Risk Gate)
    // -------------------------------------------------------------------------
    neuroquant_fpga_top #(
        .DATA_WIDTH (64)
    ) u_neuroquant_core (
        .clk                     (clk_100mhz),
        .rst_n                   (btn_rst_n),
        .s_axis_tdata            (s_axis_tdata),
        .s_axis_tkeep            (s_axis_tkeep),
        .s_axis_tvalid           (s_axis_tvalid),
        .s_axis_tready           (s_axis_tready),
        .s_axis_tlast            (s_axis_tlast),
        .sw_emergency_killswitch (sw_killswitch),
        .i_manual_trigger        (btn_manual_tick),
        .led_ready               (core_ready),
        .led_itch_valid          (core_itch_valid),
        .led_spike               (core_spike),
        .led_order_approved      (core_order_approved),
        .led_risk_violated       (core_risk_violated),
        .led_violation_code      (core_violation_code),
        .o_membrane_voltage      (core_membrane_voltage),
        .o_trade_out_valid       (core_trade_out_valid)
    );

    // -------------------------------------------------------------------------
    // 3. Hardware UART Telemetry Transmitter (Streams decisions to ESP8266)
    // -------------------------------------------------------------------------
    reg [23:0] latency_counter;
    always @(posedge clk_100mhz or negedge btn_rst_n) begin
        if (!btn_rst_n) begin
            latency_counter <= 24'd0;
        end else begin
            if (s_axis_tvalid && s_axis_tlast) begin
                latency_counter <= 24'd0; // Reset counter on packet boundary
            end else if (latency_counter < 24'hFFFFFF) begin
                latency_counter <= latency_counter + 1'b1;
            end
        end
    end

    // Trigger telemetry on either trade approval or breaker rejection
    wire tx_trigger;
    assign tx_trigger = core_trade_out_valid | core_risk_violated;

    uart_tx_telemetry #(
        .CLK_FREQ_HZ (CLK_FREQ_HZ),
        .BAUD_RATE   (BAUD_RATE)
    ) u_uart_tx (
        .clk              (clk_100mhz),
        .rst_n            (btn_rst_n),
        .send_trigger     (tx_trigger),
        .order_approved   (core_order_approved),
        .violation_code   ({4'b0000, core_violation_code}),
        .spike_fired      (core_spike),
        .membrane_voltage (core_membrane_voltage),
        .latency_cycles   (latency_counter),
        .uart_tx          (ja_uart_tx),
        .tx_busy          ()
    );

    // -------------------------------------------------------------------------
    // 4. Physical LED & PMOD Pin Driver Assignments
    // -------------------------------------------------------------------------
    assign ja_exec_strobe  = core_trade_out_valid;
    assign ja_spike_strobe = core_spike;

    assign led0_ready      = core_ready;
    assign led1_rx_sync    = rx_frame_sync;
    assign led2_spike      = core_spike;
    assign led3_approved   = core_order_approved;

    // RGB LED: Red on violation, Green on approval/ready, Blue on ingress
    assign rgb0_r          = core_risk_violated;
    assign rgb0_g          = core_ready & !core_risk_violated;
    assign rgb0_b          = rx_frame_sync;

endmodule
