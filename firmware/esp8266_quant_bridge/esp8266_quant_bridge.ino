/*
 * ==============================================================================
 * NEUROQUANT-LOB: NODEMCU ESP8266 QUANT WIRELESS GATEWAY FIRMWARE
 * ==============================================================================
 * Principal Architect: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
 * Hardware Target:     NodeMCU v2/v3 (ESP8266-12E / ESP8266-12F)
 * Physical Link:       Hardware UART @ 921,600 Baud -> Digilent Arty S7 PMOD JA
 * Standard:            Arduino IDE 2.x / ESP8266 Core 3.1.2+
 *
 * Description:
 *   High-speed IoT network bridge for the NeuroQuant neuromorphic FPGA accelerator:
 *     1. Connects to 2.4 GHz Wi-Fi network.
 *     2. Ingests real-time L2 order book updates or synthetic ITCH 5.0 tick bursts.
 *     3. Packs tick data into deterministic 42-byte binary frames:
 *          [0x55, 0xAA, Beat0(8B), Beat1(8B), Beat2(8B), Beat3(8B), Beat4(8B)]
 *     4. Blasts frames over Hardware UART (GPIO1 TXD0) to Arty S7 (PMOD JA1 L17).
 *     5. Captures 12-byte telemetry returns from Arty S7 (PMOD JA2 L18 -> GPIO3 RXD0).
 *     6. Decodes membrane voltage V_m, action potential spikes, and risk clearance.
 *
 * Physical Pin Connections (3.3V Logic Level Direct Attach):
 *   --------------------------------------------------------------
 *   NodeMCU ESP8266 Pin   | Arty S7 PMOD JA Pin | Signal Function
 *   --------------------------------------------------------------
 *   Pin TX (GPIO1 / TXD0) | PMOD JA Pin 1 (L17) | ESP8266 TX -> FPGA RX
 *   Pin RX (GPIO3 / RXD0) | PMOD JA Pin 2 (L18) | ESP8266 RX <- FPGA TX
 *   Pin GND               | PMOD JA Pin 5 (GND) | Common Reference Ground
 *   Pin 3V3 / VIN         | External 3.3V / 5V  | Board Power
 *   --------------------------------------------------------------
 * ==============================================================================
 */

#include <ESP8266WiFi.h>
#include <WiFiClientSecure.h>

// -----------------------------------------------------------------------------
// Network Configuration
// -----------------------------------------------------------------------------
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// Hardware Serial Baud Rate: 921,600 Baud (108.5 ns per bit)
#define FPGA_BAUD_RATE 921600

// Packet Framing Constants
#define FRAME_SYNC0_INGRESS   0x55
#define FRAME_SYNC1_INGRESS   0xAA
#define FRAME_SYNC0_TELEMETRY 0x55
#define FRAME_SYNC1_TELEMETRY 0xBB

#define ITCH_PAYLOAD_BYTES    40
#define TOTAL_INGRESS_BYTES   42 // 2 Sync bytes + 40 ITCH bytes
#define TELEMETRY_BYTES       12

// Onboard LED for status indication (Active-Low on NodeMCU)
#define LED_HEARTBEAT 2 // GPIO2 / D4

// -----------------------------------------------------------------------------
// Buffer Structures
// -----------------------------------------------------------------------------
uint8_t ingressBuffer[TOTAL_INGRESS_BYTES];
uint8_t telemetryBuffer[TELEMETRY_BYTES];

// Telemetry state tracking
uint32_t packetsSent = 0;
uint32_t telemetryReceived = 0;
uint32_t approvalsCount = 0;
uint32_t rejectionsCount = 0;
uint32_t spikesCount = 0;

// -----------------------------------------------------------------------------
// Build Binary ITCH 5.0 Type 'A' (Add Order) Packet
// -----------------------------------------------------------------------------
void buildItchAddOrderPacket(uint8_t* buf, uint32_t orderRef, char side, uint32_t shares, const char* symbol, uint32_t priceDecicents) {
    // 1. Sync Markers
    buf[0] = FRAME_SYNC0_INGRESS;
    buf[1] = FRAME_SYNC1_INGRESS;

    // 2. Beat 0 (8 bytes): Type 'A' (0x41), Locate (0x0001), Tracking (0x0002), Timestamp_hi (3 bytes)
    buf[2] = 0x41; // 'A'
    buf[3] = 0x00; buf[4] = 0x01; // Locate = 1
    buf[5] = 0x00; buf[6] = 0x02; // Tracking = 2
    buf[7] = 0x00; buf[8] = 0x00; buf[9] = 0x12; // Timestamp_hi

    // 3. Beat 1 (8 bytes): Timestamp_lo (3 bytes), OrderRef_hi (5 bytes)
    buf[10] = 0x34; buf[11] = 0x56; buf[12] = 0x78;
    buf[13] = 0x00; buf[14] = 0x00; buf[15] = 0x00; buf[16] = 0x00; buf[17] = 0x00;

    // 4. Beat 2 (8 bytes): OrderRef_lo (3 bytes), Side ('B'/'S'), Shares (4 bytes Big-Endian)
    buf[18] = (uint8_t)((orderRef >> 16) & 0xFF);
    buf[19] = (uint8_t)((orderRef >> 8) & 0xFF);
    buf[20] = (uint8_t)(orderRef & 0xFF);
    buf[21] = (side == 'S') ? 0x53 : 0x42; // 'B' = 0x42, 'S' = 0x53
    buf[22] = (uint8_t)((shares >> 24) & 0xFF);
    buf[23] = (uint8_t)((shares >> 16) & 0xFF);
    buf[24] = (uint8_t)((shares >> 8) & 0xFF);
    buf[25] = (uint8_t)(shares & 0xFF);

    // 5. Beat 3 (8 bytes): Stock Symbol (e.g., "AAPL    ")
    for (int i = 0; i < 8; i++) {
        buf[26 + i] = (i < strlen(symbol)) ? symbol[i] : ' ';
    }

    // 6. Beat 4 (8 bytes): Price (4 bytes Big-Endian, 4 decimal places), Padding (4 bytes)
    buf[34] = (uint8_t)((priceDecicents >> 24) & 0xFF);
    buf[35] = (uint8_t)((priceDecicents >> 16) & 0xFF);
    buf[36] = (uint8_t)((priceDecicents >> 8) & 0xFF);
    buf[37] = (uint8_t)(priceDecicents & 0xFF);
    buf[38] = 0x00; buf[39] = 0x00; buf[40] = 0x00; buf[41] = 0x00;
}

// -----------------------------------------------------------------------------
// Setup Procedure
// -----------------------------------------------------------------------------
void setup() {
    pinMode(LED_HEARTBEAT, OUTPUT);
    digitalWrite(LED_HEARTBEAT, HIGH); // Off

    // Initialize High-Speed Hardware UART to Arty S7 PMOD
    Serial.begin(FPGA_BAUD_RATE);
    while (!Serial) { delay(10); }

    // Connect to Wi-Fi
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    // Wait for Wi-Fi connection with non-blocking timeout
    uint32_t tStart = millis();
    while (WiFi.status() != WL_CONNECTED && (millis() - tStart < 8000)) {
        delay(250);
        digitalWrite(LED_HEARTBEAT, !digitalRead(LED_HEARTBEAT));
    }
    digitalWrite(LED_HEARTBEAT, (WiFi.status() == WL_CONNECTED) ? LOW : HIGH);
}

// -----------------------------------------------------------------------------
// Read & Process Telemetry Packet from Arty S7
// -----------------------------------------------------------------------------
void processTelemetryFromFpga() {
    while (Serial.available() >= TELEMETRY_BYTES) {
        // Look for Telemetry Sync: 0x55, 0xBB
        if (Serial.peek() != FRAME_SYNC0_TELEMETRY) {
            Serial.read(); // Discard unaligned byte
            continue;
        }

        uint8_t b0 = Serial.read();
        uint8_t b1 = Serial.read();

        if (b0 == FRAME_SYNC0_TELEMETRY && b1 == FRAME_SYNC1_TELEMETRY) {
            // Read remaining 10 bytes
            Serial.readBytes(&telemetryBuffer[2], 10);
            telemetryBuffer[0] = b0;
            telemetryBuffer[1] = b1;

            // Verify XOR Checksum
            uint8_t computedCrc = telemetryBuffer[2] ^ telemetryBuffer[3] ^ 
                                  telemetryBuffer[4] ^ telemetryBuffer[5] ^ 
                                  telemetryBuffer[6] ^ telemetryBuffer[7] ^ 
                                  telemetryBuffer[8] ^ telemetryBuffer[9] ^ telemetryBuffer[10];
            
            if (computedCrc == telemetryBuffer[11]) {
                telemetryReceived++;
                
                uint8_t statusByte = telemetryBuffer[2];
                bool approved      = (statusByte & 0x80) != 0;
                uint8_t code       = (statusByte & 0x7F);
                bool spike         = (telemetryBuffer[3] != 0);

                int32_t rawVoltage = ((int32_t)telemetryBuffer[4] << 24) |
                                     ((int32_t)telemetryBuffer[5] << 16) |
                                     ((int32_t)telemetryBuffer[6] << 8)  |
                                     ((int32_t)telemetryBuffer[7]);
                float voltageMv = (float)rawVoltage / 65536.0f; // Q16.16 -> mV

                uint32_t cycles = ((uint32_t)telemetryBuffer[8] << 16) |
                                  ((uint32_t)telemetryBuffer[9] << 8)  |
                                  ((uint32_t)telemetryBuffer[10]);
                float latencyNs = (float)cycles * 10.0f; // 100 MHz clock = 10 ns per cycle

                if (approved) approvalsCount++;
                else rejectionsCount++;
                if (spike) spikesCount++;
            }
        }
    }
}

// -----------------------------------------------------------------------------
// Main Execution Loop
// -----------------------------------------------------------------------------
void loop() {
    static uint32_t lastTickTime = 0;
    static uint32_t orderCounter = 1;

    // Stream a high-frequency tick every 10 milliseconds (100 Hz wire speed)
    if (millis() - lastTickTime >= 10) {
        lastTickTime = millis();

        // Alternate BUY / SELL with varying prices and share sizes
        char side = (orderCounter % 2 == 0) ? 'B' : 'S';
        uint32_t shares = (orderCounter % 5 == 0) ? 1000 : 200;
        uint32_t priceDecicents = 1500000 + (orderCounter % 50) * 100; // $150.00 to $155.00

        // Build 42-byte binary frame
        buildItchAddOrderPacket(ingressBuffer, orderCounter, side, shares, "AAPL    ", priceDecicents);

        // Transmit over physical PMOD UART to Arty S7
        Serial.write(ingressBuffer, TOTAL_INGRESS_BYTES);
        packetsSent++;
        orderCounter++;

        // Blink heartbeat LED
        if (orderCounter % 20 == 0) {
            digitalWrite(LED_HEARTBEAT, !digitalRead(LED_HEARTBEAT));
        }
    }

    // Process return telemetry from FPGA
    processTelemetryFromFpga();
}
