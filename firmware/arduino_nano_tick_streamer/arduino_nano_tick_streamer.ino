/*
 * ==============================================================================
 * NEUROQUANT-LOB: ARDUINO NANO HARDWARE TICK STREAMER & ADVERSARIAL INJECTOR
 * ==============================================================================
 * Principal Architect: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
 * Hardware Target:     Arduino Nano (ATmega328P, 16 MHz, 5V / 3.3V)
 * Interface:           Hardware UART (115,200 Baud) -> Arty S7 PMOD JA Pin 1 (L17)
 * Standard:            Arduino IDE 2.x
 *
 * Physical Wiring Instructions (CRITICAL):
 *   -------------------------------------------------------------------------
 *   Arduino Nano Pin | Arty S7 PMOD JA Pin | Signal Function
 *   -------------------------------------------------------------------------
 *   Pin TX (Pin D1)  | PMOD JA Pin 1 (L17) | Arduino TX -> FPGA RX (Ticks)
 *   Pin RX (Pin D0)  | PMOD JA Pin 2 (L18) | Arduino RX <- FPGA TX (Telemetry)
 *   Pin GND          | PMOD JA Pin 5 (GND) | MANDATORY COMMON GROUND REFERENCE
 *   -------------------------------------------------------------------------
 *   NOTE: Arduino Nano Pin 13 LED will blink with each transmitted market packet.
 * ==============================================================================
 */

#include <stdint.h>
#include <string.h>

#define BAUD_RATE             115200
#define PIN_LED               13

// Packet Framing Constants
#define FRAME_SYNC0_INGRESS   0x55
#define FRAME_SYNC1_INGRESS   0xAA
#define FRAME_SYNC0_TELEMETRY 0x55
#define FRAME_SYNC1_TELEMETRY 0xBB

#define TOTAL_INGRESS_BYTES   42
#define TELEMETRY_BYTES       12

uint8_t packetBuffer[TOTAL_INGRESS_BYTES];
uint8_t rxBuffer[TELEMETRY_BYTES];

uint32_t orderCounter = 1;
bool streamingActive = false;
unsigned long lastTickTime = 0;
const unsigned long tickIntervalMs = 20; // 50 Hz default stream

void buildItchPacket(uint8_t* buf, uint32_t orderRef, char side, uint32_t shares, const char* symbol, uint32_t priceDecicents) {
    buf[0] = FRAME_SYNC0_INGRESS;
    buf[1] = FRAME_SYNC1_INGRESS;

    // Beat 0: Type 'A', Locate=1, Tracking=2, Timestamp_hi=0x000012
    buf[2] = 0x41; buf[3] = 0x00; buf[4] = 0x01; buf[5] = 0x00; buf[6] = 0x02;
    buf[7] = 0x00; buf[8] = 0x00; buf[9] = 0x12;

    // Beat 1: Timestamp_lo=0x345678, OrderRef_hi
    buf[10] = 0x34; buf[11] = 0x56; buf[12] = 0x78;
    buf[13] = 0x00; buf[14] = 0x00; buf[15] = 0x00; buf[16] = 0x00; buf[17] = 0x00;

    // Beat 2: OrderRef_lo, Side, Shares (Big-Endian)
    buf[18] = (uint8_t)((orderRef >> 16) & 0xFF);
    buf[19] = (uint8_t)((orderRef >> 8) & 0xFF);
    buf[20] = (uint8_t)(orderRef & 0xFF);
    buf[21] = (side == 'S') ? 0x53 : 0x42;
    buf[22] = (uint8_t)((shares >> 24) & 0xFF);
    buf[23] = (uint8_t)((shares >> 16) & 0xFF);
    buf[24] = (uint8_t)((shares >> 8) & 0xFF);
    buf[25] = (uint8_t)(shares & 0xFF);

    // Beat 3: Symbol (padded to 8 chars)
    for (int i = 0; i < 8; i++) {
        buf[26 + i] = (i < strlen(symbol)) ? symbol[i] : ' ';
    }

    // Beat 4: Price in decicents ($185.00 = 1,850,000 = 0x001C3A90)
    buf[34] = (uint8_t)((priceDecicents >> 24) & 0xFF);
    buf[35] = (uint8_t)((priceDecicents >> 16) & 0xFF);
    buf[36] = (uint8_t)((priceDecicents >> 8) & 0xFF);
    buf[37] = (uint8_t)(priceDecicents & 0xFF);
    buf[38] = 0x00; buf[39] = 0x00; buf[40] = 0x00; buf[41] = 0x00;
}

void sendNormalTick() {
    digitalWrite(PIN_LED, HIGH);
    // Normal retail order: 100 shares @ $185.00
    buildItchPacket(packetBuffer, orderCounter++, 'B', 100, "AAPL    ", 1850000);
    Serial.write(packetBuffer, TOTAL_INGRESS_BYTES);
    digitalWrite(PIN_LED, LOW);
}

void sendToxicSweep() {
    digitalWrite(PIN_LED, HIGH);
    // Toxic institutional sweep: 5,000 shares @ $180.00 (triggers LIF spike LD2 & rate limit)
    buildItchPacket(packetBuffer, orderCounter++, 'S', 5000, "AAPL    ", 1800000);
    Serial.write(packetBuffer, TOTAL_INGRESS_BYTES);
    digitalWrite(PIN_LED, LOW);
}

void sendFatFingerViolation() {
    digitalWrite(PIN_LED, HIGH);
    // Fat-finger price breach: $250.00 vs $185.00 mid (triggers Risk Collar LD4 RED)
    buildItchPacket(packetBuffer, orderCounter++, 'B', 100, "AAPL    ", 2500000);
    Serial.write(packetBuffer, TOTAL_INGRESS_BYTES);
    digitalWrite(PIN_LED, LOW);
}

void setup() {
    pinMode(PIN_LED, OUTPUT);
    digitalWrite(PIN_LED, LOW);
    Serial.begin(BAUD_RATE);

    // Initial LED Blink sequence to signal Arduino Nano is alive
    for (int i = 0; i < 3; i++) {
        digitalWrite(PIN_LED, HIGH); delay(100);
        digitalWrite(PIN_LED, LOW);  delay(100);
    }
}

void loop() {
    // 1. Process serial commands from PC USB
    if (Serial.available() > 0) {
        char cmd = Serial.read();
        switch (cmd) {
            case 't': // Single Normal Tick
                sendNormalTick();
                break;
            case 'f': // Toxic Sweep (Spikes LIF LD2)
                sendToxicSweep();
                break;
            case 'k': // Collar Violation (Trips RGB0 RED)
                sendFatFingerViolation();
                break;
            case 's': // Start Continuous Stream
                streamingActive = true;
                break;
            case 'h': // Halt Continuous Stream
                streamingActive = false;
                break;
        }
    }

    // 2. Continuous wire-speed streaming mode
    if (streamingActive) {
        unsigned long currentMillis = millis();
        if (currentMillis - lastTickTime >= tickIntervalMs) {
            lastTickTime = currentMillis;
            sendNormalTick();
        }
    }
}
