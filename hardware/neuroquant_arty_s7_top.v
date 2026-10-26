// ==============================================================================
// NEUROQUANT-LOB: DIGILENT ARTY S7 + ARDUINO NANO HARDWARE TOP-LEVEL ACCELERATOR
// ==============================================================================
// Principal Architect: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
// Target Architecture: AMD / Xilinx Spartan-7 (XC7S25-CSGA324 / XC7S50)
// Physical Board:      Digilent Arty S7-25
// Hardware Interfaces:
//   [1] Onboard USB-UART: FTDI FT2232H (Channel B) direct to Host PC (COM9)
//   [2] PMOD Header JA:   Serial Option 1 to Arduino Nano (Pins 1=RX, 2=TX, 5=GND)
//   [3] Shield Header:    Serial Option 2 to Arduino Nano (IO0=RX, IO1=TX, GND=GND)
// Standard:            IEEE 1364-2001 Verilog HDL
// ==============================================================================

`timescale 1ns / 1ps

module neuroquant_arty_s7_top #(
    parameter CLK_FREQ_HZ = 100_000_000,
    parameter BAUD_RATE   = 115_200
)(
    // Master Oscillator: 100 MHz onboard clock (Pin R2 on Arty S7)
    input  wire                   clk_100mhz,

    // Active-Low Reset (Red button labeled RESET / Pin C18 on Arty S7)
    input  wire                   btn_rst_n,

    // Slide Switches (SW0 - SW3)
    input  wire                   sw_killswitch,       // SW0 (Pin H14): Emergency Circuit Breaker (Up = Tripped)
    input  wire                   sw_bypass_parser,    // SW1 (Pin H18): Autonomous Self-Test Demo (Up = 5Hz Auto Ticks)
    input  wire                   sw2_tight_collar,    // SW2 (Pin G18): Risk Collar Stress Mode
    input  wire                   sw3_reserved,        // SW3 (Pin M5):  Reserved (SSTL135 Bank 34)

    // Push Buttons (BTN0 - BTN3)
    input  wire                   btn_manual_tick,     // BTN0 (Pin G15): Manual Normal Tick Injection
    input  wire                   btn1_stress,         // BTN1 (Pin K16): Manual Fat-Finger Breach Test (Flashes RED)
    input  wire                   btn2_spike,          // BTN2 (Pin J16): Manual Neuromorphic LIF Spike Trigger
    input  wire                   btn3_clear,          // BTN3 (Pin H13): Reset Packet & Violation Counters

    // On-board FTDI USB-UART Bridge (COM9 direct micro-USB cable)
    input  wire                   usb_uart_rx,         // Pin V12: RX from Host PC COM9
    output wire                   usb_uart_tx,         // Pin R12: TX to Host PC COM9

    // PMOD Header JA (Serial Interface Option 1 to Arduino Nano)
    input  wire                   ja_uart_rx,          // JA Pin 1 (Pin L17): RX from Arduino Nano TX1
    output wire                   ja_uart_tx,          // JA Pin 2 (Pin L18): TX to Arduino Nano RX0
    output wire                   ja_exec_strobe,      // JA Pin 3 (Pin M14): Outbound Trade Execution Strobe
    output wire                   ja_spike_strobe,     // JA Pin 4 (Pin N14): Neuromorphic Action Potential Spike

    // Arduino / ChipKit Shield Female Header (Serial Interface Option 2 to Arduino Nano)
    input  wire                   ck_io0_rx,           // Socket IO0 (Pin L13): RX from Arduino Nano TX1
    output wire                   ck_io1_tx,           // Socket IO1 (Pin N13): TX to Arduino Nano RX0

    // Physical Diagnostic Single-Color Yellow LEDs (Silkscreen LD2, LD3, LD4, LD5)
    output wire                   led0_ready,          // Silkscreen LD2 (Pin E18): Accelerator Engine Ready (Steady Yellow)
    output wire                   led1_rx_sync,        // Silkscreen LD3 (Pin F13): RX Stream Ingest & 0x55AA Locked (Flashing Yellow)
    output wire                   led2_spike,          // Silkscreen LD4 (Pin E13): Neuromorphic LIF Spike Fired (Flashing Yellow)
    output wire                   led3_approved,       // Silkscreen LD5 (Pin H15): Pre-Trade Gate Approved Trade (Flashing Yellow)

    // RGB LED 0 (Silkscreen LD0): J15=Red, G17=Green, F15=Blue
    output wire                   rgb0_r,              // Red (Pin J15): Risk Breached / Killswitch Tripped
    output wire                   rgb0_g,              // Green (Pin G17): Clean State / System Operational
    output wire                   rgb0_b,              // Blue (Pin F15): Ingress Stream Active (Pulses on data reception)

    // RGB LED 1 (Silkscreen LD1): E15=Red, F18=Green, E14=Blue
    output wire                   rgb1_r,              // Red (Pin E15): Market Volatility / Price Deviation Alert
    output wire                   rgb1_g,              // Green (Pin F18): Trade Clearance Approved Strobe
    output wire                   rgb1_b               // Blue (Pin E14): LIF Neuromorphic Spike Strobe
);

    // -------------------------------------------------------------------------
    // Triple UART RX Ingress Multiplexer:
    // UART idle state is logic HIGH (Mark = 1, Space = 0).
    // Combining inputs with an AND gate allows:
    //   [1] Direct USB-UART cable from Host PC (COM9)
    //   [2] Arduino Nano jumper into Pmod JA (Pin 1)
    //   [3] Arduino Nano jumper into Arduino Shield Header (IO0)
    // to stream packets directly into the hardware engine!
    // -------------------------------------------------------------------------
    wire uart_rx_combined;
    assign uart_rx_combined = usb_uart_rx & ja_uart_rx & ck_io0_rx;

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
    // Autonomous Hardware Self-Test Generator (5 Hz when SW1 is slid UP)
    // -------------------------------------------------------------------------
    // Allows instant physical verification of FPGA without any cables plugged in!
    reg [24:0] self_test_counter;
    reg        self_test_pulse;

    always @(posedge clk_100mhz or negedge btn_rst_n) begin
        if (!btn_rst_n) begin
            self_test_counter <= 25'd0;
            self_test_pulse   <= 1'b0;
        end else if (sw_bypass_parser) begin
            if (self_test_counter >= 25'd20_000_000) begin // 200 ms @ 100MHz = 5 Hz
                self_test_counter <= 25'd0;
                self_test_pulse   <= 1'b1;
            end else begin
                self_test_counter <= self_test_counter + 1'b1;
                self_test_pulse   <= 1'b0;
            end
        end else begin
            self_test_counter <= 25'd0;
            self_test_pulse   <= 1'b0;
        end
    end

    // Combined manual tick trigger: BTN0 + BTN2 + Self-Test pulse
    wire tick_injection_trigger;
    assign tick_injection_trigger = btn_manual_tick | btn2_spike | self_test_pulse;

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
        .sw_emergency_killswitch (sw_killswitch | btn1_stress), // BTN1 forces immediate violation test
        .i_manual_trigger        (tick_injection_trigger),
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
    assign tx_trigger = core_trade_out_valid | core_risk_violated | btn1_stress;

    wire uart_tx_serial;
    uart_tx_telemetry #(
        .CLK_FREQ_HZ (CLK_FREQ_HZ),
        .BAUD_RATE   (BAUD_RATE)
    ) u_uart_tx (
        .clk              (clk_100mhz),
        .rst_n            (btn_rst_n),
        .send_trigger     (tx_trigger),
        .order_approved   (core_order_approved & !btn1_stress),
        .violation_code   (btn1_stress ? 8'h01 : {4'b0000, core_violation_code}),
        .spike_fired      (core_spike),
        .membrane_voltage (core_membrane_voltage),
        .latency_cycles   (latency_counter),
        .uart_tx          (uart_tx_serial),
        .tx_busy          ()
    );

    // Transmit telemetry to Host PC (COM9), PMOD JA, and Shield Header IO1
    assign usb_uart_tx = uart_tx_serial;
    assign ja_uart_tx  = uart_tx_serial;
    assign ck_io1_tx   = uart_tx_serial;

    // PMOD JA diagnostic strobe outputs
    assign ja_exec_strobe  = core_trade_out_valid;
    assign ja_spike_strobe = core_spike;

    // -------------------------------------------------------------------------
    // 4. Human-Visible Pulse Stretchers (80ms @ 100MHz = 8,000,000 Cycles)
    // -------------------------------------------------------------------------
    localparam STRETCH_CYCLES = 23'd8_000_000; // 80ms at 100MHz for vibrant visibility

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
            // RX Activity & Frame Sync Stretcher (triggers on serial byte, packet, or self-test)
            if (rx_frame_sync || rx_byte_valid || self_test_pulse)
                stretch_sync <= STRETCH_CYCLES;
            else if (stretch_sync > 0)
                stretch_sync <= stretch_sync - 1'b1;

            // LIF Spike Stretcher
            if (core_spike || (self_test_pulse && sw_bypass_parser))
                stretch_spike <= STRETCH_CYCLES;
            else if (stretch_spike > 0)
                stretch_spike <= stretch_spike - 1'b1;

            // Approved Order Stretcher
            if (sw_killswitch || btn1_stress)
                stretch_approved <= 23'd0;
            else if (core_order_approved || (self_test_pulse && sw_bypass_parser))
                stretch_approved <= STRETCH_CYCLES;
            else if (stretch_approved > 0)
                stretch_approved <= stretch_approved - 1'b1;

            // Risk Breach / Killswitch Stretcher
            if (core_risk_violated || sw_killswitch || btn1_stress)
                stretch_violation <= STRETCH_CYCLES;
            else if (stretch_violation > 0)
                stretch_violation <= stretch_violation - 1'b1;
        end
    end

    // -------------------------------------------------------------------------
    // 5. Physical Diagnostic LED Output Assignments (Matched to Silkscreen!)
    // -------------------------------------------------------------------------
    // Silkscreen LD2 (User LED 0, Pin E18): Accelerator Engine Operational (Steady Yellow)
    assign led0_ready    = core_ready;

    // Silkscreen LD3 (User LED 1, Pin F13): RX Frame Synchronized (Flashing Yellow)
    assign led1_rx_sync  = rx_frame_sync | (stretch_sync > 0);

    // Silkscreen LD4 (User LED 2, Pin E13): Neuromorphic LIF Spike Fired (Flashing Yellow)
    assign led2_spike    = core_spike | (stretch_spike > 0);

    // Silkscreen LD5 (User LED 3, Pin H15): Pre-Trade Gate Approved Order (Flashing Yellow)
    assign led3_approved = (core_order_approved | (stretch_approved > 0)) & !sw_killswitch & !btn1_stress;

    // Silkscreen LD0 (RGB LED 0, Pins J15, G17, F15):
    // Red (J15): Risk Breached or Emergency Killswitch Tripped
    assign rgb0_r        = core_risk_violated | (stretch_violation > 0) | sw_killswitch | btn1_stress;
    // Green (G17): Clean State / System Operational (Active when normal)
    assign rgb0_g        = core_ready & !sw_killswitch & !btn1_stress & (stretch_violation == 0);
    // Blue (F15): Ingress Packet Stream Active
    assign rgb0_b        = rx_frame_sync | (stretch_sync > 0);

    // Silkscreen LD1 (RGB LED 1, Pins E15, F18, E14):
    // Red (E15): Market Volatility / Price Deviation Alert
    assign rgb1_r        = core_risk_violated | btn1_stress;
    // Green (F18): Approved Order Execution Strobe
    assign rgb1_g        = (core_order_approved | (stretch_approved > 0)) & !sw_killswitch & !btn1_stress;
    // Blue (E14): Neuromorphic LIF Action Potential Spike Strobe
    assign rgb1_b        = core_spike | (stretch_spike > 0);

endmodule
