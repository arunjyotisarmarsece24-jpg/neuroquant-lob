/*
 * ==============================================================================
 * NEUROQUANT-LOB: NODEMCU ESP8266 WIRELESS QUANT GATEWAY & WEB TELEMETRY
 * ==============================================================================
 * Principal Architect: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
 * Hardware Target:     NodeMCU v2/v3 (ESP8266-12E / ESP8266-12F)
 * Physical Link:       Hardware UART @ 921,600 Baud -> Digilent Arty S7 PMOD JA
 * Standard:            Arduino IDE 2.x / ESP8266 Core 3.1.2+
 * URL Access:          http://neuroquant.local or http://<ESP8266_IP>
 *
 * Physical Pin Connections (3.3V Logic Level Direct Attach):
 *   --------------------------------------------------------------
 *   NodeMCU ESP8266 Pin   | Arty S7 PMOD JA Pin | Signal Function
 *   --------------------------------------------------------------
 *   Pin TX (GPIO1 / TXD0) | PMOD JA Pin 1 (L17) | ESP8266 TX -> FPGA RX
 *   Pin RX (GPIO3 / RXD0) | PMOD JA Pin 2 (L18) | ESP8266 RX <- FPGA TX
 *   Pin GND               | PMOD JA Pin 5 (GND) | Common Reference Ground
 *   --------------------------------------------------------------
 * ==============================================================================
 */

#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <ESP8266mDNS.h>

// Network Configuration (Update with your Wi-Fi credentials)
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// Hardware Serial Baud Rate
#define FPGA_BAUD_RATE 921600

// Packet Framing Constants
#define FRAME_SYNC0_INGRESS   0x55
#define FRAME_SYNC1_INGRESS   0xAA
#define FRAME_SYNC0_TELEMETRY 0x55
#define FRAME_SYNC1_TELEMETRY 0xBB

#define TOTAL_INGRESS_BYTES   42 // 2 Sync bytes + 40 ITCH bytes
#define TELEMETRY_BYTES       12
#define LED_HEARTBEAT         2  // GPIO2 / D4 (Active-Low)

ESP8266WebServer server(80);

// Buffers & Telemetry Tracking
uint8_t ingressBuffer[TOTAL_INGRESS_BYTES];
uint8_t telemetryBuffer[TELEMETRY_BYTES];

volatile uint32_t packetsSent       = 0;
volatile uint32_t telemetryReceived = 0;
volatile uint32_t approvalsCount    = 0;
volatile uint32_t rejectionsCount   = 0;
volatile uint32_t spikesCount       = 0;
volatile float    lastVoltageMv     = -70.0f;
volatile float    lastLatencyNs     = 25.0f;
volatile uint8_t  lastViolationCode = 0;
volatile bool     lastApproval      = true;

// Build Binary ITCH 5.0 Type 'A' Packet
void buildItchAddOrderPacket(uint8_t* buf, uint32_t orderRef, char side, uint32_t shares, const char* symbol, uint32_t priceDecicents) {
    buf[0] = FRAME_SYNC0_INGRESS;
    buf[1] = FRAME_SYNC1_INGRESS;

    // Beat 0: Type 'A', Locate=1, Tracking=2, Timestamp_hi=0x000012
    buf[2] = 0x41; buf[3] = 0x00; buf[4] = 0x01; buf[5] = 0x00; buf[6] = 0x02;
    buf[7] = 0x00; buf[8] = 0x00; buf[9] = 0x12;

    // Beat 1: Timestamp_lo=0x345678, OrderRef_hi
    buf[10] = 0x34; buf[11] = 0x56; buf[12] = 0x78;
    buf[13] = 0x00; buf[14] = 0x00; buf[15] = 0x00; buf[16] = 0x00; buf[17] = 0x00;

    // Beat 2: OrderRef_lo, Side, Shares
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

void sendOrderToFpga(uint32_t ref, char side, uint32_t shares, uint32_t priceDecicents) {
    buildItchAddOrderPacket(ingressBuffer, ref, side, shares, "AAPL    ", priceDecicents);
    Serial.write(ingressBuffer, TOTAL_INGRESS_BYTES);
    packetsSent++;
}

void processTelemetryFromFpga() {
    while (Serial.available() >= TELEMETRY_BYTES) {
        if (Serial.peek() != FRAME_SYNC0_TELEMETRY) {
            Serial.read();
            continue;
        }

        uint8_t b0 = Serial.read();
        uint8_t b1 = Serial.read();

        if (b0 == FRAME_SYNC0_TELEMETRY && b1 == FRAME_SYNC1_TELEMETRY) {
            Serial.readBytes(&telemetryBuffer[2], 10);
            telemetryBuffer[0] = b0;
            telemetryBuffer[1] = b1;

            uint8_t computedCrc = telemetryBuffer[2] ^ telemetryBuffer[3] ^ 
                                  telemetryBuffer[4] ^ telemetryBuffer[5] ^ 
                                  telemetryBuffer[6] ^ telemetryBuffer[7] ^ 
                                  telemetryBuffer[8] ^ telemetryBuffer[9] ^ telemetryBuffer[10];

            if (computedCrc == telemetryBuffer[11]) {
                telemetryReceived++;
                uint8_t statusByte = telemetryBuffer[2];
                lastApproval       = (statusByte & 0x80) != 0;
                lastViolationCode  = (statusByte & 0x7F);
                bool spike         = (telemetryBuffer[3] != 0);

                int32_t rawV = ((int32_t)telemetryBuffer[4] << 24) |
                               ((int32_t)telemetryBuffer[5] << 16) |
                               ((int32_t)telemetryBuffer[6] << 8)  |
                               ((int32_t)telemetryBuffer[7]);
                lastVoltageMv = (float)rawV / 65536.0f;

                uint32_t cycles = ((uint32_t)telemetryBuffer[8] << 16) |
                                  ((uint32_t)telemetryBuffer[9] << 8)  |
                                  ((uint32_t)telemetryBuffer[10]);
                lastLatencyNs = (float)cycles * 10.0f;

                if (lastApproval) approvalsCount++;
                else rejectionsCount++;
                if (spike) spikesCount++;
            }
        }
    }
}

// -----------------------------------------------------------------------------
// Web Portal Endpoints
// -----------------------------------------------------------------------------
const char INDEX_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NeuroQuant-LOB | ESP8266 FPGA Portal</title>
  <style>
    :root { --bg:#0b0f19; --card:#151d30; --cyan:#00f2fe; --green:#00ff87; --red:#ff4b4b; --text:#e2e8f0; }
    body { background:var(--bg); color:var(--text); font-family:-apple-system,sans-serif; margin:0; padding:16px; }
    .header { text-align:center; padding:12px; border-bottom:1px solid #1e293b; }
    h1 { margin:0; font-size:1.4rem; color:var(--cyan); }
    .badge { display:inline-block; padding:4px 8px; border-radius:12px; font-size:0.75rem; background:rgba(0,242,254,0.15); color:var(--cyan); border:1px solid var(--cyan); margin-top:6px; }
    .grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:16px; }
    .card { background:var(--card); padding:14px; border-radius:8px; border:1px solid rgba(255,255,255,0.06); }
    .lbl { font-size:0.75rem; color:#94a3b8; }
    .val { font-size:1.3rem; font-weight:bold; margin-top:4px; font-family:monospace; }
    .green { color:var(--green); } .cyan { color:var(--cyan); } .red { color:var(--red); }
    .actions { margin-top:20px; display:flex; flex-direction:column; gap:10px; }
    button { background:#1e293b; color:#fff; border:1px solid #334155; padding:12px; border-radius:6px; font-size:0.9rem; font-weight:bold; cursor:pointer; }
    button.primary { background:linear-gradient(135deg, #00f2fe, #4facfe); color:#0b0f19; border:none; }
    button.danger { background:rgba(255,75,75,0.2); border-color:var(--red); color:var(--red); }
  </style>
</head>
<body>
  <div class="header">
    <h1>⚡ NeuroQuant Arty S7 Bridge</h1>
    <div class="badge">921,600 BAUD PHYSICAL UART</div>
  </div>
  <div class="grid">
    <div class="card"><div class="lbl">PACKETS BLASTED</div><div id="v-sent" class="val cyan">0</div></div>
    <div class="card"><div class="lbl">TRADES APPROVED</div><div id="v-app" class="val green">0</div></div>
    <div class="card"><div class="lbl">RISK REJECTIONS</div><div id="v-rej" class="val red">0</div></div>
    <div class="card"><div class="lbl">LIF SPIKES FIRED</div><div id="v-spk" class="val cyan">0</div></div>
    <div class="card"><div class="lbl">MEMBRANE VOLTAGE</div><div id="v-vm" class="val">-70.0 mV</div></div>
    <div class="card"><div class="lbl">WIRE LATENCY</div><div id="v-lat" class="val green">25.0 ns</div></div>
  </div>
  <div class="actions">
    <button class="primary" onclick="inject('normal')">🚀 INJECT CLEAN ORDER (1,000 AAPL)</button>
    <button class="danger" onclick="inject('toxic')">⚠️ INJECT FAT-FINGER BREACH (50,000 AAPL)</button>
    <button onclick="inject('burst')">⚡ BLAST 50-TICK WIRE BURST</button>
  </div>
  <script>
    function update() {
      fetch('/api/status').then(r => r.json()).then(d => {
        document.getElementById('v-sent').innerText = d.sent;
        document.getElementById('v-app').innerText = d.approved;
        document.getElementById('v-rej').innerText = d.rejected;
        document.getElementById('v-spk').innerText = d.spikes;
        document.getElementById('v-vm').innerText = d.voltage_mv.toFixed(2) + ' mV';
        document.getElementById('v-lat').innerText = d.latency_ns.toFixed(1) + ' ns';
      });
    }
    setInterval(update, 500);
    function inject(t) { fetch('/api/inject?type=' + t, {method:'POST'}); }
  </script>
</body>
</html>
)rawliteral";

void handleRoot() {
    server.send(200, "text/html", INDEX_HTML);
}

void handleStatus() {
    String json = "{";
    json += "\"sent\":" + String(packetsSent) + ",";
    json += "\"telemetry\":" + String(telemetryReceived) + ",";
    json += "\"approved\":" + String(approvalsCount) + ",";
    json += "\"rejected\":" + String(rejectionsCount) + ",";
    json += "\"spikes\":" + String(spikesCount) + ",";
    json += "\"voltage_mv\":" + String(lastVoltageMv, 2) + ",";
    json += "\"latency_ns\":" + String(lastLatencyNs, 1) + ",";
    json += "\"last_approved\":" + String(lastApproval ? "true" : "false") + ",";
    json += "\"violation_code\":\"0x" + String(lastViolationCode, HEX) + "\"";
    json += "}";
    server.send(200, "application/json", json);
}

void handleInject() {
    String type = server.arg("type");
    static uint32_t webOrderRef = 9000;
    webOrderRef++;

    if (type == "normal") {
        sendOrderToFpga(webOrderRef, 'B', 1000, 1500000); // 1,000 shares @ $150.00
    } else if (type == "toxic") {
        sendOrderToFpga(webOrderRef, 'B', 50000, 1500000); // 50,000 shares (Fat-finger breach!)
    } else if (type == "burst") {
        for (int i = 0; i < 50; i++) {
            webOrderRef++;
            sendOrderToFpga(webOrderRef, (i % 2 == 0) ? 'B' : 'S', 200, 1500000 + i * 10);
            delay(1);
        }
    }
    server.send(200, "application/json", "{\"status\":\"ok\"}");
}

// -----------------------------------------------------------------------------
// Setup & Loop
// -----------------------------------------------------------------------------
void setup() {
    pinMode(LED_HEARTBEAT, OUTPUT);
    digitalWrite(LED_HEARTBEAT, HIGH);

    Serial.begin(FPGA_BAUD_RATE);
    while (!Serial) { delay(10); }

    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    uint32_t tStart = millis();
    while (WiFi.status() != WL_CONNECTED && (millis() - tStart < 8000)) {
        delay(200);
        digitalWrite(LED_HEARTBEAT, !digitalRead(LED_HEARTBEAT));
    }
    digitalWrite(LED_HEARTBEAT, (WiFi.status() == WL_CONNECTED) ? LOW : HIGH);

    if (MDNS.begin("neuroquant")) {
        MDNS.addService("http", "tcp", 80);
    }

    server.on("/", handleRoot);
    server.on("/api/status", handleStatus);
    server.on("/api/inject", HTTP_POST, handleInject);
    server.begin();
}

void loop() {
    server.handleClient();
    MDNS.update();

    static uint32_t lastAutoTick = 0;
    static uint32_t autoRef = 1;

    // Stream an autonomous live market tick every 20 ms (50 Hz wire speed)
    if (millis() - lastAutoTick >= 20) {
        lastAutoTick = millis();
        autoRef++;
        char side = (autoRef % 2 == 0) ? 'B' : 'S';
        uint32_t shares = (autoRef % 7 == 0) ? 1000 : 200;
        sendOrderToFpga(autoRef, side, shares, 1500000 + (autoRef % 30) * 100);
    }

    processTelemetryFromFpga();
}
