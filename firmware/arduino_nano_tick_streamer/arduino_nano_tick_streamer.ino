/*
 * ==============================================================================
 * NEUROQUANT-LOB: ARDUINO NANO TICK STREAMER (AUTONOMOUS HARDWARE DEMO)
 * ==============================================================================
 * Hardware: Arduino Nano (ATmega328P) -> Digilent Arty S7-25
 * Pins:     Nano TX1 -> Arty S7 IO0 | Nano RX0 -> Arty S7 IO1 | GND -> GND
 * Baud:     115,200 Baud (Standard 8-N-1 Serial)
 * ==============================================================================
 */

#include <stdint.h>
#include <string.h>

#define BAUD_RATE             115200
#define PIN_LED               13

#define FRAME_SYNC0_INGRESS   0x55
#define FRAME_SYNC1_INGRESS   0xAA
#define TOTAL_INGRESS_BYTES   42

uint8_t packetBuffer[TOTAL_INGRESS_BYTES];
uint32_t orderCounter = 1;

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

    // Beat 3: Symbol
    for (int i = 0; i < 8; i++) {
        buf[26 + i] = (i < strlen(symbol)) ? symbol[i] : ' ';
    }

    // Beat 4: Price in decicents
    buf[34] = (uint8_t)((priceDecicents >> 24) & 0xFF);
    buf[35] = (uint8_t)((priceDecicents >> 16) & 0xFF);
    buf[36] = (uint8_t)((priceDecicents >> 8) & 0xFF);
    buf[37] = (uint8_t)(priceDecicents & 0xFF);
    buf[38] = 0x00; buf[39] = 0x00; buf[40] = 0x00; buf[41] = 0x00;
}

void sendNormalTick() {
    digitalWrite(PIN_LED, HIGH);
    buildItchPacket(packetBuffer, orderCounter++, 'B', 100, "AAPL    ", 1850000);
    Serial.write(packetBuffer, TOTAL_INGRESS_BYTES);
    delay(10);
    digitalWrite(PIN_LED, LOW);
}

void sendToxicSweep() {
    digitalWrite(PIN_LED, HIGH);
    buildItchPacket(packetBuffer, orderCounter++, 'S', 5000, "AAPL    ", 1800000);
    Serial.write(packetBuffer, TOTAL_INGRESS_BYTES);
    delay(20);
    digitalWrite(PIN_LED, LOW);
}

void sendFatFingerViolation() {
    digitalWrite(PIN_LED, HIGH);
    buildItchPacket(packetBuffer, orderCounter++, 'B', 100, "AAPL    ", 2500000);
    Serial.write(packetBuffer, TOTAL_INGRESS_BYTES);
    delay(20);
    digitalWrite(PIN_LED, LOW);
}

void setup() {
    pinMode(PIN_LED, OUTPUT);
    digitalWrite(PIN_LED, LOW);
    Serial.begin(BAUD_RATE);

    // Initial LED Blink sequence on boot
    for (int i = 0; i < 5; i++) {
        digitalWrite(PIN_LED, HIGH); delay(100);
        digitalWrite(PIN_LED, LOW);  delay(100);
    }
}

unsigned long cycleCounter = 0;

void loop() {
    cycleCounter++;

    // Automatic Autonomous Hardware LED Demonstration:
    // Every 10 ticks, inject a toxic sweep (triggers LD2 LIF Spike)
    // Every 25 ticks, inject a fat-finger breach (triggers RGB0 Red Alert)
    // Otherwise, send normal compliant ticks (triggers LD1 Sync & LD3 Approved)
    if (cycleCounter % 25 == 0) {
        sendFatFingerViolation(); // LD4 flashes RED!
        delay(300);
    } else if (cycleCounter % 10 == 0) {
        sendToxicSweep();         // LD2 flashes GREEN!
        delay(150);
    } else {
        sendNormalTick();          // LD1 & LD3 flash GREEN!
        delay(120);
    }
}
