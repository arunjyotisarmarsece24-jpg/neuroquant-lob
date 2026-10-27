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
    parameter BAUD_RATE   = 115_200,
    parameter POR_ENABLE  = 1
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
    // Unified Hardware Master Reset & Power-On Reset (POR) Circuitry
    // -------------------------------------------------------------------------
    // Dual Physical Reset Sources:
    //   [1] Dedicated Red Button labeled "RESET" (Pin C18, active-low)
    //   [2] User Push-Button BTN3 (Pin H13, active-high)
    // Hardware Power-On Reset (POR):
    //   Ensures rock-solid startup by holding reset asserted for ~20ms
    //   (2,000,000 clock cycles @ 100MHz) upon FPGA bitstream loading.
    reg [21:0] por_cnt = 22'd0;
    reg        por_rst_n = (POR_ENABLE == 0);

    always @(posedge clk_100mhz) begin
        if (POR_ENABLE) begin
            if (por_cnt < 22'd2_000_000) begin
                por_cnt   <= por_cnt + 1'b1;
                por_rst_n <= 1'b0;
            end else begin
                por_rst_n <= 1'b1;
            end
        end else begin
            por_rst_n <= 1'b1;
        end
    end

    // Master Active-Low Reset (Low when C18 pressed OR BTN3 pressed OR POR active)
    wire master_rst_n;
    assign master_rst_n = btn_rst_n & (!btn3_clear) & por_rst_n;

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

    always @(posedge clk_100mhz or negedge master_rst_n) begin
        if (!master_rst_n) begin
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
        .rst_n           (master_rst_n),
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
        .rst_n                   (master_rst_n),
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
    always @(posedge clk_100mhz or negedge master_rst_n) begin
        if (!master_rst_n) begin
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
    assign tx_trigger = core_trade_out_valid | core_risk_violated | btn1_stress | (s_axis_tvalid & s_axis_tlast) | (self_test_pulse & sw_bypass_parser);

    wire uart_tx_serial;
    uart_tx_telemetry #(
        .CLK_FREQ_HZ (CLK_FREQ_HZ),
        .BAUD_RATE   (BAUD_RATE)
    ) u_uart_tx (
        .clk              (clk_100mhz),
        .rst_n            (master_rst_n),
        .send_trigger     (tx_trigger),
        .order_approved   (core_order_approved & !btn1_stress),
        .violation_code   (btn1_stress ? 7'h01 : {4'b0000, core_violation_code}),
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
    // 4. Institutional Diagnostic LED Timing & Pulse Stretchers
    // -------------------------------------------------------------------------
    // Pulse Stretchers (Scaled for crisp, non-saturating human visibility):
    // 100 MHz clock -> 1 ms = 100,000 cycles
    localparam SYNC_PULSE_CYCLES  = 23'd3_000_000;  // 30ms sharp pulse on packet ingress
    localparam SPIKE_PULSE_CYCLES = 23'd7_000_000;  // 70ms pulse on LIF neuromorphic spike
    localparam APPR_PULSE_CYCLES  = 23'd4_000_000;  // 40ms pulse on order approval
    localparam VIOL_PULSE_CYCLES  = 25'd25_000_000; // 250ms pulse on risk breach

    reg [22:0] stretch_sync;
    reg [22:0] stretch_spike;
    reg [22:0] stretch_approved;
    reg [24:0] stretch_violation;

    // Heartbeat Generator (1.0 Hz double-blink: heartbeat alive indication)
    // 100,000,000 cycles = 1 second
    reg [26:0] heartbeat_cnt;
    wire heartbeat_pulse;
    // 0 to 70ms: ON, 70 to 180ms: OFF, 180 to 250ms: ON, 250 to 1000ms: OFF
    assign heartbeat_pulse = (heartbeat_cnt < 27'd7_000_000) || 
                             (heartbeat_cnt >= 27'd18_000_000 && heartbeat_cnt < 27'd25_000_000);

    // 4 Hz Flasher for Critical Risk Breach Alert (Emergency Circuit Breaker)
    // 25,000,000 cycles = 250ms period (125ms ON, 125ms OFF)
    reg [24:0] flash_4hz_cnt;
    wire flash_4hz;
    assign flash_4hz = (flash_4hz_cnt < 25'd12_500_000);

    // Operational Counters & Stretchers
    always @(posedge clk_100mhz or negedge master_rst_n) begin
        if (!master_rst_n) begin
            heartbeat_cnt     <= 27'd0;
            flash_4hz_cnt     <= 25'd0;
            stretch_sync      <= 23'd0;
            stretch_spike     <= 23'd0;
            stretch_approved  <= 23'd0;
            stretch_violation <= 25'd0;
        end else begin
            // Heartbeat counter (0 .. 99,999,999)
            if (heartbeat_cnt >= 27'd99_999_999)
                heartbeat_cnt <= 27'd0;
            else
                heartbeat_cnt <= heartbeat_cnt + 1'b1;

            // 4Hz flasher counter (0 .. 24,999,999)
            if (flash_4hz_cnt >= 25'd24_999_999)
                flash_4hz_cnt <= 25'd0;
            else
                flash_4hz_cnt <= flash_4hz_cnt + 1'b1;

            // Ingress Sync Pulse (Triggers on frame boundary or self-test tick)
            if ((s_axis_tvalid && s_axis_tlast) || self_test_pulse)
                stretch_sync <= SYNC_PULSE_CYCLES;
            else if (stretch_sync > 0)
                stretch_sync <= stretch_sync - 1'b1;

            // LIF Neuromorphic Action Potential Spike Strobe (70ms)
            if (core_spike || btn2_spike)
                stretch_spike <= SPIKE_PULSE_CYCLES;
            else if (stretch_spike > 0)
                stretch_spike <= stretch_spike - 1'b1;

            // Pre-Trade Order Approval Strobe (40ms)
            if (sw_killswitch || btn1_stress)
                stretch_approved <= 23'd0;
            else if (core_order_approved || (self_test_pulse && sw_bypass_parser))
                stretch_approved <= APPR_PULSE_CYCLES;
            else if (stretch_approved > 0)
                stretch_approved <= stretch_approved - 1'b1;

            // Risk Breach / Killswitch Violation Stretcher (250ms)
            if (core_risk_violated || sw_killswitch || btn1_stress)
                stretch_violation <= VIOL_PULSE_CYCLES;
            else if (stretch_violation > 0)
                stretch_violation <= stretch_violation - 1'b1;
        end
    end

    // -------------------------------------------------------------------------
    // 5. Final Physical Diagnostic LED Driving Logic
    // -------------------------------------------------------------------------
    // Silkscreen LD2 (User LED 0, Pin E18): Heartbeat (1.0 Hz double-blink proves 100MHz clock is live)
    assign led0_ready    = core_ready & heartbeat_pulse;

    // Silkscreen LD3 (User LED 1, Pin F13): RX Frame Ingest Pulse (Sharp 30ms blink on packet)
    assign led1_rx_sync  = rx_frame_sync | (stretch_sync > 0);

    // Silkscreen LD4 (User LED 2, Pin E13): Neuromorphic LIF Spike Fired (70ms strobe)
    assign led2_spike    = stretch_spike > 0;

    // Silkscreen LD5 (User LED 3, Pin H15): Pre-Trade Gate Approved Trade (40ms strobe, disabled on breach)
    assign led3_approved = (stretch_approved > 0) & !sw_killswitch & !btn1_stress & (stretch_violation == 0);

    // Silkscreen LD0 (RGB LED 0, Pins J15, G17, F15 - System Health & Pre-Trade Risk Gate):
    // Red (Pin J15): Blinding 4Hz Flashing RED on Risk Breach / Killswitch / Stress
    assign rgb0_r        = (stretch_violation > 0 || sw_killswitch || btn1_stress) & flash_4hz;
    // Green (Pin G17): Solid Calm GREEN when Operational & Clean (Turns OFF completely during violation)
    assign rgb0_g        = core_ready & !sw_killswitch & !btn1_stress & (stretch_violation == 0);
    // Blue (Pin F15): Ingress packet flash (sharp 30ms Cyan flash when combined with Green)
    assign rgb0_b        = (stretch_sync > 0) & (stretch_violation == 0);

    // Silkscreen LD1 (RGB LED 1, Pins E15, F18, E14 - Dedicated Neuromorphic SNN Brain Activity):
    // Red (Pin E15): Dark / OFF (Clean & unpolluted)
    assign rgb1_r        = 1'b0;
    // Green (Pin F18): Dark / OFF (Approval is cleanly signaled by LD5)
    assign rgb1_g        = 1'b0;
    // Blue (Pin E14): Neuromorphic LIF Action Potential Spike Strobe (70ms vibrant Electric Blue)
    assign rgb1_b        = stretch_spike > 0;

endmodule
