// ==============================================================================
// NEUROQUANT-LOB: HIGH-SPEED HARDWARE UART RECEIVER & AXI4-STREAM DESERIALIZER
// ==============================================================================
// Principal Architect: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
// Target Hardware: Digilent Arty S7 (Spartan-7) + NodeMCU ESP8266 Wi-Fi Gateway
// Standard: IEEE 1364-2001 Verilog HDL
//
// Description:
//   Bridges serial byte stream from ESP8266 NodeMCU to 64-bit parallel AXI4-Stream
//   feed into the NeuroQuant neuromorphic accelerator.
//
// Protocol Framing:
//   - Baud Rate: 921,600 baud (Default @ 100 MHz sys_clk) or 115,200 baud
//   - Frame Start: SYNC0 (0x55), SYNC1 (0xAA)
//   - Payload: 5 consecutive 64-bit beats (40 bytes total for NASDAQ ITCH 5.0)
//   - Glitch Immunity: 3-stage majority-voting synchronizer on RX line
//   - Watchdog: Auto-resets on stream stall (> 100 us) to prevent frame desync
// ==============================================================================

`timescale 1ns / 1ps

module uart_rx_bridge #(
    parameter CLK_FREQ_HZ = 100_000_000, // 100 MHz System Clock
    parameter BAUD_RATE   = 921_600,     // 921,600 Baud (~92.1 KB/s payload)
    parameter DATA_WIDTH  = 64
)(
    input  wire                   clk,
    input  wire                   rst_n,

    // Physical Serial RX Line (from ESP8266 TX pin via PMOD)
    input  wire                   uart_rx,

    // AXI4-Stream Master Interface (into neuroquant_fpga_top)
    output reg  [DATA_WIDTH-1:0]  m_axis_tdata,
    output wire [7:0]             m_axis_tkeep,
    output reg                    m_axis_tvalid,
    input  wire                   m_axis_tready,
    output reg                    m_axis_tlast,

    // Diagnostic & Telemetry Status
    output reg                    rx_frame_sync,    // High when aligned to 0x55AA
    output reg                    rx_byte_valid,    // Pulses on each valid byte
    output reg  [7:0]             rx_byte_out,
    output reg  [31:0]            rx_packet_count,  // Packets successfully framed
    output reg  [31:0]            rx_error_count    // Sync losses / framing errors
);

    // Constant Clocks Per Bit: 100,000,000 / BAUD_RATE
    localparam CLKS_PER_BIT   = CLK_FREQ_HZ / BAUD_RATE;
    localparam TIMEOUT_CYCLES = CLK_FREQ_HZ / 20; // 50 ms watchdog timeout (robust against microcontroller inter-byte jitter)

    assign m_axis_tkeep = 8'hFF;

    // -------------------------------------------------------------------------
    // 1. RX Input Synchronizer & Majority Voter (Glitch Rejection)
    // -------------------------------------------------------------------------
    reg [2:0] rx_sync_reg;
    wire      rx_clean;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rx_sync_reg <= 3'b111;
        end else begin
            rx_sync_reg <= {rx_sync_reg[1:0], uart_rx};
        end
    end

    // Majority voting logic
    assign rx_clean = (rx_sync_reg[2] & rx_sync_reg[1]) |
                      (rx_sync_reg[2] & rx_sync_reg[0]) |
                      (rx_sync_reg[1] & rx_sync_reg[0]);

    // -------------------------------------------------------------------------
    // 2. UART Byte Deserializer State Machine
    // -------------------------------------------------------------------------
    localparam S_UART_IDLE  = 3'b000;
    localparam S_UART_START = 3'b001;
    localparam S_UART_DATA  = 3'b010;
    localparam S_UART_STOP  = 3'b011;

    reg [2:0]  uart_state;
    reg [15:0] baud_counter;
    reg [2:0]  bit_index;
    reg [7:0]  shift_reg;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            uart_state    <= S_UART_IDLE;
            baud_counter  <= 16'd0;
            bit_index     <= 3'd0;
            shift_reg     <= 8'd0;
            rx_byte_valid <= 1'b0;
            rx_byte_out   <= 8'd0;
        end else begin
            rx_byte_valid <= 1'b0; // Default pulse low

            case (uart_state)
                S_UART_IDLE: begin
                    baud_counter <= 16'd0;
                    bit_index    <= 3'd0;
                    if (rx_clean == 1'b0) begin // Start bit detected (falling edge)
                        uart_state <= S_UART_START;
                    end
                end

                S_UART_START: begin
                    // Sample at mid-point of start bit (CLKS_PER_BIT / 2)
                    if (baud_counter == ((CLKS_PER_BIT - 1) / 2)) begin
                        if (rx_clean == 1'b0) begin
                            baud_counter <= 16'd0;
                            uart_state   <= S_UART_DATA;
                        end else begin
                            uart_state   <= S_UART_IDLE; // False glitch start
                        end
                    end else begin
                        baud_counter <= baud_counter + 1'b1;
                    end
                end

                S_UART_DATA: begin
                    if (baud_counter == (CLKS_PER_BIT - 1)) begin
                        baud_counter          <= 16'd0;
                        shift_reg[bit_index]  <= rx_clean; // Sample data bit
                        if (bit_index == 3'd7) begin
                            bit_index  <= 3'd0;
                            uart_state <= S_UART_STOP;
                        end else begin
                            bit_index  <= bit_index + 1'b1;
                        end
                    end else begin
                        baud_counter <= baud_counter + 1'b1;
                    end
                end

                S_UART_STOP: begin
                    if (baud_counter == (CLKS_PER_BIT - 1)) begin
                        baud_counter  <= 16'd0;
                        uart_state    <= S_UART_IDLE;
                        if (rx_clean == 1'b1) begin // Valid stop bit
                            rx_byte_valid <= 1'b1;
                            rx_byte_out   <= shift_reg;
                        end
                    end else begin
                        baud_counter <= baud_counter + 1'b1;
                    end
                end

                default: uart_state <= S_UART_IDLE;
            endcase
        end
    end

    // -------------------------------------------------------------------------
    // 3. Packet Frame Assembler (Sync 0x55AA -> 40 Bytes -> 5 AXI Beats)
    // -------------------------------------------------------------------------
    localparam F_SEEK_SYNC0 = 3'b000;
    localparam F_SEEK_SYNC1 = 3'b001;
    localparam F_INGEST     = 3'b010;

    reg [2:0]  frame_state;
    reg [5:0]  byte_counter;     // 0 to 39 (40 bytes total)
    reg [23:0] watchdog_timer;
    reg [63:0] beat_accumulator;
    reg [2:0]  beat_byte_idx;    // 0 to 7 bytes per 64-bit beat

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            frame_state      <= F_SEEK_SYNC0;
            byte_counter     <= 6'd0;
            beat_byte_idx    <= 3'd0;
            beat_accumulator <= 64'd0;
            watchdog_timer   <= 24'd0;
            m_axis_tdata     <= 64'd0;
            m_axis_tvalid    <= 1'b0;
            m_axis_tlast     <= 1'b0;
            rx_frame_sync    <= 1'b0;
            rx_packet_count  <= 32'd0;
            rx_error_count   <= 32'd0;
        end else begin
            // Clear AXI handshake strobe after 1 clock cycle
            if (m_axis_tvalid && m_axis_tready) begin
                m_axis_tvalid <= 1'b0;
                m_axis_tlast  <= 1'b0;
            end

            // Watchdog Timeout: Auto-resets if stream freezes mid-packet
            if (frame_state == F_INGEST) begin
                if (watchdog_timer >= TIMEOUT_CYCLES) begin
                    frame_state    <= F_SEEK_SYNC0;
                    rx_frame_sync  <= 1'b0;
                    rx_error_count <= rx_error_count + 1'b1;
                    watchdog_timer <= 24'd0;
                end else begin
                    watchdog_timer <= watchdog_timer + 1'b1;
                end
            end

            // Process deserialized UART byte
            if (rx_byte_valid) begin
                watchdog_timer <= 24'd0; // Reset watchdog on active byte

                case (frame_state)
                    F_SEEK_SYNC0: begin
                        if (rx_byte_out == 8'h55) begin
                            frame_state <= F_SEEK_SYNC1;
                        end
                    end

                    F_SEEK_SYNC1: begin
                        if (rx_byte_out == 8'hAA) begin
                            frame_state   <= F_INGEST;
                            rx_frame_sync <= 1'b1;
                            byte_counter  <= 6'd0;
                            beat_byte_idx <= 3'd0;
                        end else begin
                            frame_state   <= F_SEEK_SYNC0;
                        end
                    end

                    F_INGEST: begin
                        // Shift bytes into 64-bit beat (Big-Endian network order)
                        beat_accumulator <= {beat_accumulator[55:0], rx_byte_out};

                        if (beat_byte_idx == 3'd7) begin
                            // Completed a full 64-bit beat! Emit onto AXI bus
                            beat_byte_idx <= 3'd0;
                            m_axis_tdata  <= {beat_accumulator[55:0], rx_byte_out};
                            m_axis_tvalid <= 1'b1;

                            // Byte 39 is the 5th and final beat of ITCH packet
                            if (byte_counter == 6'd39) begin
                                m_axis_tlast    <= 1'b1;
                                rx_packet_count <= rx_packet_count + 1'b1;
                                frame_state     <= F_SEEK_SYNC0;
                                rx_frame_sync   <= 1'b0;
                            end else begin
                                m_axis_tlast    <= 1'b0;
                            end
                        end else begin
                            beat_byte_idx <= beat_byte_idx + 1'b1;
                        end

                        byte_counter <= byte_counter + 1'b1;
                    end

                    default: frame_state <= F_SEEK_SYNC0;
                endcase
            end
        end
    end

endmodule
