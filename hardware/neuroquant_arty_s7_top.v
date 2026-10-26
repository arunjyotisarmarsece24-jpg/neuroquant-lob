// ==============================================================================
// NEUROQUANT-LOB: DIGILENT ARTY S7 + ARDUINO NANO HARDWARE TOP-LEVEL ACCELERATOR
// ==============================================================================
// Principal Architect: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
// Target Architecture: AMD / Xilinx Spartan-7 (XC7S25-CSGA324 / XC7S50)
// Physical Board:      Digilent Arty S7-25
// Hardware Interfaces:
//   [1] USB-UART Bridge:  FTDI FT2232H (Channel B) direct to Host PC (COM9)
//   [2] PMOD Header JA:   Serial Interface to Arduino Nano (COM5)
// Standard:            IEEE 1364-2001 Verilog HDL
// ==============================================================================

`timescale 1ns / 1ps

module neuroquant_arty_s7_top #(
    parameter CLK_FREQ_HZ = 100_000_000,
    parameter BAUD_RATE   = 921_600
)(
    // Master Oscillator: 100 MHz onboard clock (Pin R2 on Arty S7)
    input  wire                   clk_100mhz,

    // Active-Low Reset (Button 0 / Pin C18 on Arty S7)
    input  wire                   btn_rst_n,

    // Slide Switches
    input  wire                   sw_killswitch,       // SW0 (Pin H14): Emergency Circuit Breaker
    input  wire                   sw_bypass_parser,    // SW1 (Pin H18): Synthetic internal tick mode

    // Push Buttons
    input  wire                   btn_manual_tick,     // BTN1 (Pin K16): Inject single test tick

    // On-board FTDI USB-UART Bridge (COM9 direct micro-USB cable)
    input  wire                   usb_uart_rx,         // Pin V12: RX from Host PC COM9
    output wire                   usb_uart_tx,         // Pin R12: TX to Host PC COM9

    // PMOD Header JA (Serial Interface to Arduino Nano)
    input  wire                   ja_uart_rx,          // JA Pin 1 (Pin L17): RX from Arduino Nano TX
    output wire                   ja_uart_tx,          // JA Pin 2 (Pin L18): TX to Arduino Nano RX
    output wire                   ja_exec_strobe,      // JA Pin 3 (Pin M14): Outbound Trade Execution Strobe
    output wire                   ja_spike_strobe,     // JA Pin 4 (Pin N14): Neuromorphic Action Potential Spike

    // Physical Diagnostic Green LEDs (LD0 - LD3)
    output wire                   led0_ready,          // LD0 (Pin E18): Accelerator System Initialized
    output wire                   led1_rx_sync,        // LD1 (Pin F13): Frame Synchronized (0x55AA Locked)
    output wire                   led2_spike,          // LD2 (Pin E13): Neuromorphic LIF Spiking Action Potential
    output wire                   led3_approved,       // LD3 (Pin H15): Pre-Trade Risk Gate Approved Order

    // RGB LED 0 (LD4 on Arty S7-25): J15=Red, G17=Green, F15=Blue
    output wire                   rgb0_r,              // Red (Pin J15): Risk Breached / Killswitch Tripped
    output wire                   rgb0_g,              // Green (Pin G17): Clean State / System Ready
    output wire                   rgb0_b               // Blue (Pin F15): Ingress Stream Active
);

    // -------------------------------------------------------------------------
    // Dual UART RX Ingress Multiplexer:
    // UART idle state is logic HIGH (Mark = 1, Space = 0).
    // Combining both inputs with an AND gate allows either USB-UART (PC COM9)
    // or PMOD JA (Arduino Nano COM5) to stream packets to the hardware engine.
    // -------------------------------------------------------------------------
    wire uart_rx_combined;
    assign uart_rx_combined = usb_uart_rx & ja_uart_rx;

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
    // 1. High-Speed UART Receiver (Deserializes Binary ITCH Packets)
    // -------------------------------------------------------------------------
    uart_rx_bridge #(
        .CLK_FREQ_HZ (CLK_FREQ_HZ),
        .BAUD_RATE   (BAUD_RATE),
        .DATA_WIDTH  (64)
    ) u_uart_rx (
        .clk             (clk_100mhz),
        .rst_n           (btn_rst_n),
        .uart_rx         (uart_rx_combined),
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
    // 3. Hardware UART Telemetry Transmitter
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

    wire tx_trigger;
    assign tx_trigger = core_trade_out_valid | core_risk_violated;

    wire uart_tx_serial;
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
        .uart_tx          (uart_tx_serial),
        .tx_busy          ()
    );

    // Transmit telemetry to both Host PC (COM9) and PMOD JA (Arduino Nano)
    assign usb_uart_tx = uart_tx_serial;
    assign ja_uart_tx  = uart_tx_serial;

    // PMOD JA diagnostic strobe outputs
    assign ja_exec_strobe  = core_trade_out_valid;
    assign ja_spike_strobe = core_spike;

    // -------------------------------------------------------------------------
    // 4. Human-Visible Pulse Stretchers (50ms @ 100MHz = 5,000,000 Cycles)
    // -------------------------------------------------------------------------
    // 10ns single-cycle pulses are physically imperceptible to human retinas.
    // Digital pulse stretchers hold pulses high for 50ms for vivid LED feedback.
    // -------------------------------------------------------------------------
    localparam STRETCH_CYCLES = 23'd5_000_000;

    reg [22:0] stretch_sync;
    reg [22:0] stretch_spike;
    reg [22:0] stretch_approved;
    reg [22:0] stretch_violation;

    always @(posedge clk_100mhz or negedge btn_rst_n) begin
        if (!btn_rst_n) begin
            stretch_sync      <= 23'd0;
            stretch_spike     <= 23'd0;
            stretch_approved  <= 23'd0;
            stretch_violation <= 23'd0;
        end else begin
            // RX Sync Stretcher
            if (rx_frame_sync)
                stretch_sync <= STRETCH_CYCLES;
            else if (stretch_sync > 0)
                stretch_sync <= stretch_sync - 1'b1;

            // LIF Spike Stretcher
            if (core_spike)
                stretch_spike <= STRETCH_CYCLES;
            else if (stretch_spike > 0)
                stretch_spike <= stretch_spike - 1'b1;

            // Approved Order Stretcher
            if (sw_killswitch)
                stretch_approved <= 23'd0;
            else if (core_order_approved)
                stretch_approved <= STRETCH_CYCLES;
            else if (stretch_approved > 0)
                stretch_approved <= stretch_approved - 1'b1;

            // Risk Breach / Killswitch Stretcher
            if (core_risk_violated || sw_killswitch)
                stretch_violation <= STRETCH_CYCLES;
            else if (stretch_violation > 0)
                stretch_violation <= stretch_violation - 1'b1;
        end
    end

    // -------------------------------------------------------------------------
    // 5. Physical Diagnostic LED Output Assignments
    // -------------------------------------------------------------------------
    // LD0: Accelerator Ready
    assign led0_ready    = core_ready;

    // LD1: RX Frame Sync (Glows when receiving 0x55AA ITCH stream)
    assign led1_rx_sync  = rx_frame_sync | (stretch_sync > 0);

    // LD2: Neuromorphic LIF Action Potential (Flashes bright green on spike)
    assign led2_spike    = core_spike | (stretch_spike > 0);

    // LD3: Pre-Trade Risk Gate Approved (Flashes bright green on trade clearance)
    assign led3_approved = (core_order_approved | (stretch_approved > 0)) & !sw_killswitch;

    // RGB LED 0 (LD4 on Arty S7-25):
    // Red: Tripped circuit breaker or risk limit breached
    assign rgb0_r        = core_risk_violated | (stretch_violation > 0) | sw_killswitch;

    // Green: Clean State / System Ready (Active when running normally)
    assign rgb0_g        = core_ready & !sw_killswitch & (stretch_violation == 0);

    // Blue: Ingress Stream Active
    assign rgb0_b        = rx_frame_sync | (stretch_sync > 0);

endmodule
