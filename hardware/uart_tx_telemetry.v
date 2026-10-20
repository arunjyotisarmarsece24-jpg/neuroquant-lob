// ==============================================================================
// NEUROQUANT-LOB: HARDWARE UART TELEMETRY TRANSMITTER (FPGA -> ESP8266)
// ==============================================================================
// Principal Architect: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
// Target Hardware: Digilent Arty S7 (Spartan-7) -> NodeMCU ESP8266 Wi-Fi Gateway
// Standard: IEEE 1364-2001 Verilog HDL
//
// Description:
//   Serializes FPGA quant execution decisions, LIF membrane potential readouts,
//   and circuit breaker violation codes back to the ESP8266 NodeMCU.
//
// Frame Format (12 Bytes):
//   Byte 0:  0x55 (Sync 0)
//   Byte 1:  0xBB (Sync 1 - Telemetry)
//   Byte 2:  Status Byte ({order_approved, violation_code[6:0]})
//   Byte 3:  Spike Fired Strobe (0x01 or 0x00)
//   Byte 4-7: Membrane Voltage V_m (Signed Q16.16, Big-Endian)
//   Byte 8-10: Pipelined Latency Cycles (24-bit counter)
//   Byte 11: XOR Checksum (Byte 2 through Byte 10)
// ==============================================================================

`timescale 1ns / 1ps

module uart_tx_telemetry #(
    parameter CLK_FREQ_HZ = 100_000_000,
    parameter BAUD_RATE   = 921_600
)(
    input  wire                   clk,
    input  wire                   rst_n,

    // Telemetry Triggers & Data
    input  wire                   send_trigger,       // High pulse to transmit telemetry
    input  wire                   order_approved,
    input  wire [6:0]             violation_code,
    input  wire                   spike_fired,
    input  wire signed [31:0]     membrane_voltage,
    input  wire [23:0]            latency_cycles,

    // Physical Serial TX Line (connects to ESP8266 RX pin via PMOD)
    output reg                    uart_tx,
    output wire                   tx_busy
);

    localparam CLKS_PER_BIT = CLK_FREQ_HZ / BAUD_RATE;
    localparam TOTAL_BYTES  = 12;

    // Buffer holding the 12-byte packet
    reg [7:0] packet_buf [0:TOTAL_BYTES-1];
    reg [3:0] byte_idx;
    reg [3:0] bit_idx;
    reg [15:0] baud_counter;

    localparam S_TX_IDLE  = 2'b00;
    localparam S_TX_START = 2'b01;
    localparam S_TX_DATA  = 2'b10;
    localparam S_TX_STOP  = 2'b11;

    reg [1:0] tx_state;

    assign tx_busy = (tx_state != S_TX_IDLE);

    // Compute XOR checksum combinational
    wire [7:0] checksum;
    assign checksum = packet_buf[2] ^ packet_buf[3] ^ packet_buf[4] ^ 
                      packet_buf[5] ^ packet_buf[6] ^ packet_buf[7] ^ 
                      packet_buf[8] ^ packet_buf[9] ^ packet_buf[10];

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            tx_state     <= S_TX_IDLE;
            uart_tx      <= 1'b1; // UART idle state is high
            byte_idx     <= 4'd0;
            bit_idx      <= 4'd0;
            baud_counter <= 16'd0;
        end else begin
            case (tx_state)
                S_TX_IDLE: begin
                    uart_tx      <= 1'b1;
                    baud_counter <= 16'd0;
                    bit_idx      <= 4'd0;
                    byte_idx     <= 4'd0;

                    if (send_trigger) begin
                        // Load packet buffer
                        packet_buf[0]  <= 8'h55;
                        packet_buf[1]  <= 8'hBB;
                        packet_buf[2]  <= {order_approved, violation_code};
                        packet_buf[3]  <= {7'd0, spike_fired};
                        packet_buf[4]  <= membrane_voltage[31:24];
                        packet_buf[5]  <= membrane_voltage[23:16];
                        packet_buf[6]  <= membrane_voltage[15:8];
                        packet_buf[7]  <= membrane_voltage[7:0];
                        packet_buf[8]  <= latency_cycles[23:16];
                        packet_buf[9]  <= latency_cycles[15:8];
                        packet_buf[10] <= latency_cycles[7:0];
                        packet_buf[11] <= {order_approved, violation_code} ^ {7'd0, spike_fired} ^
                                          membrane_voltage[31:24] ^ membrane_voltage[23:16] ^
                                          membrane_voltage[15:8]  ^ membrane_voltage[7:0] ^
                                          latency_cycles[23:16]   ^ latency_cycles[15:8] ^ latency_cycles[7:0];
                        tx_state       <= S_TX_START;
                    end
                end

                S_TX_START: begin
                    uart_tx <= 1'b0; // Start bit (low)
                    if (baud_counter == (CLKS_PER_BIT - 1)) begin
                        baud_counter <= 16'd0;
                        tx_state     <= S_TX_DATA;
                    end else begin
                        baud_counter <= baud_counter + 1'b1;
                    end
                end

                S_TX_DATA: begin
                    uart_tx <= packet_buf[byte_idx][bit_idx];
                    if (baud_counter == (CLKS_PER_BIT - 1)) begin
                        baud_counter <= 16'd0;
                        if (bit_idx == 4'd7) begin
                            bit_idx  <= 4'd0;
                            tx_state <= S_TX_STOP;
                        end else begin
                            bit_idx  <= bit_idx + 1'b1;
                        end
                    end else begin
                        baud_counter <= baud_counter + 1'b1;
                    end
                end

                S_TX_STOP: begin
                    uart_tx <= 1'b1; // Stop bit (high)
                    if (baud_counter == (CLKS_PER_BIT - 1)) begin
                        baud_counter <= 16'd0;
                        if (byte_idx == (TOTAL_BYTES - 1)) begin
                            tx_state <= S_TX_IDLE; // Packet complete!
                        end else begin
                            byte_idx <= byte_idx + 1'b1;
                            tx_state <= S_TX_START;
                        end
                    end else begin
                        baud_counter <= baud_counter + 1'b1;
                    end
                end

                default: tx_state <= S_TX_IDLE;
            endcase
        end
    end

endmodule
