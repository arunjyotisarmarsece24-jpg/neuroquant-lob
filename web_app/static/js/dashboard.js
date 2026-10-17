/**
 * NeuroQuant-LOB: Real-Time Visualization & Telemetry Engine
 * High-performance HTML5 Canvas rendering for Raster Plots & Oscilloscope
 */

const MAX_HISTORY = 120;
const rasterBuffer = []; // array of { s: [], h: [], m: [] }
const voltageHistory = []; // array of { sensory: float, hidden: float, motor: [] }

// DOM Elements
const hdrMid = document.getElementById("hdr-mid");
const hdrSpread = document.getElementById("hdr-spread");
const hdrOfi = document.getElementById("hdr-ofi");
const hdrPnl = document.getElementById("hdr-pnl");
const hdrInv = document.getElementById("hdr-inv");
const lastEventTag = document.getElementById("last-event-tag");
const lobLadder = document.getElementById("lob-ladder");

const sigSkew = document.getElementById("sig-skew");
const sigTox = document.getElementById("sig-tox");
const sigVol = document.getElementById("sig-vol");

const execQuoteActive = document.getElementById("exec-quote-active");
const execBid = document.getElementById("exec-bid");
const execAsk = document.getElementById("exec-ask");
const execPnl = document.getElementById("exec-pnl");
const execInv = document.getElementById("exec-inv");
const execCash = document.getElementById("exec-cash");
const execTrades = document.getElementById("exec-trades");
const execAvoided = document.getElementById("exec-avoided");
const execHits = document.getElementById("exec-hits");

// Canvases
const rasterCanvas = document.getElementById("rasterCanvas");
const rasterCtx = rasterCanvas.getContext("2d");
const voltageCanvas = document.getElementById("voltageCanvas");
const voltageCtx = voltageCanvas.getContext("2d");

function resizeCanvases() {
  rasterCanvas.width = rasterCanvas.parentElement.clientWidth;
  rasterCanvas.height = rasterCanvas.parentElement.clientHeight;
  voltageCanvas.width = voltageCanvas.parentElement.clientWidth;
  voltageCanvas.height = voltageCanvas.parentElement.clientHeight;
}
window.addEventListener("resize", resizeCanvases);
resizeCanvases();

// Connect Server-Sent Events (SSE)
const eventSource = new EventSource("/api/stream");

eventSource.onmessage = function(event) {
  const data = JSON.parse(event.data);
  updateDashboard(data);
};

eventSource.onerror = function() {
  document.getElementById("conn-badge").innerText = "● RECONNECTING";
  document.getElementById("conn-badge").style.color = "var(--accent-red)";
};

function updateDashboard(t) {
  const mkt = t.market;
  const neuro = t.neuro;
  const port = t.portfolio;

  // 1. Update Header Stats
  hdrMid.innerText = `$${mkt.mid_price.toFixed(2)}`;
  hdrSpread.innerText = `$${mkt.spread.toFixed(2)}`;
  hdrOfi.innerText = `${mkt.ofi > 0 ? "+" : ""}${mkt.ofi.toFixed(1)}`;
  hdrOfi.className = `stat-val ${mkt.ofi >= 0 ? "positive" : "negative"}`;

  hdrPnl.innerText = `${port.pnl >= 0 ? "+" : ""}$${port.pnl.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
  hdrPnl.className = `stat-val ${port.pnl >= 0 ? "positive" : "negative"}`;

  hdrInv.innerText = `${port.inventory > 0 ? "+" : ""}${port.inventory}`;
  hdrInv.className = `stat-val ${Math.abs(port.inventory) > 10 ? "warning" : ""}`;

  lastEventTag.innerText = t.event.split("_")[0];

  // 2. Render Limit Order Book Depth Ladder
  renderLadder(mkt, port);

  // 3. Update Readout Signals
  const skew = neuro.signals.skew || 0;
  sigSkew.innerText = `${skew >= 0 ? "+" : ""}${skew.toFixed(3)}`;
  sigSkew.style.color = skew >= 0 ? "var(--accent-green)" : "var(--accent-red)";

  const tox = (neuro.signals.toxicity_prob || 0) * 100;
  sigTox.innerText = `${tox.toFixed(1)}%`;
  sigTox.style.color = tox > 60 ? "var(--accent-red)" : "var(--accent-green)";

  const vol = neuro.signals.volatility_pulse || 0;
  sigVol.innerText = vol.toFixed(2);

  // 4. Update Execution Telemetry
  if (!port.quote_active) {
    execQuoteActive.innerText = "PULLED (TOXIC DEFENSE)";
    execQuoteActive.style.color = "var(--accent-red)";
  } else if (port.inventory_state === "EMERGENCY_UNWIND_LONG") {
    execQuoteActive.innerText = "UNWINDING LONG (BID PULLED)";
    execQuoteActive.style.color = "var(--accent-yellow)";
  } else if (port.inventory_state === "EMERGENCY_UNWIND_SHORT") {
    execQuoteActive.innerText = "UNWINDING SHORT (ASK PULLED)";
    execQuoteActive.style.color = "var(--accent-yellow)";
  } else if (port.inventory_state === "SKEWED_LONG" || port.inventory_state === "SKEWED_SHORT") {
    execQuoteActive.innerText = `ACTIVE (${port.inventory_state})`;
    execQuoteActive.style.color = "var(--accent-cyan)";
  } else {
    execQuoteActive.innerText = "ACTIVE (BALANCED TWO-SIDED)";
    execQuoteActive.style.color = "var(--accent-green)";
  }

  execBid.innerText = port.my_bid ? `$${port.my_bid.toFixed(2)}` : "— (PULLED)";
  execAsk.innerText = port.my_ask ? `$${port.my_ask.toFixed(2)}` : "— (PULLED)";
  execPnl.innerText = `${port.pnl >= 0 ? "+" : ""}$${port.pnl.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
  execPnl.className = port.pnl >= 0 ? "positive" : "negative";

  execInv.innerText = `${port.inventory > 0 ? "+" : ""}${port.inventory} / ±50 [${port.inventory_state || "BALANCED"}]`;
  execCash.innerText = `$${port.cash.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
  execTrades.innerText = port.total_trades;
  execAvoided.innerText = port.adverse_selections_avoided;
  execHits.innerText = port.toxic_hits_taken;

  // 5. Append Spikes to Raster Buffer
  rasterBuffer.push({
    s: neuro.sensory_firing_indices,
    h: neuro.hidden_firing_indices,
    m: neuro.motor_firing_indices
  });
  if (rasterBuffer.length > MAX_HISTORY) rasterBuffer.shift();

  // 6. Append Voltage to Oscilloscope Buffer
  voltageHistory.push({
    sensory: neuro.sensory_v_mean,
    hidden: neuro.hidden_v_mean,
    motor: neuro.motor_v
  });
  if (voltageHistory.length > MAX_HISTORY) voltageHistory.shift();

  drawRaster();
  drawOscilloscope();
}

function renderLadder(mkt, port) {
  let html = "";
  const asks = (mkt.asks || []).slice(0, 6).reverse(); // lowest ask closest to mid
  const bids = (mkt.bids || []).slice(0, 6);

  // Max volume for relative bar sizing
  let maxVol = 50.0;
  asks.forEach(a => { if (a[1] > maxVol) maxVol = a[1]; });
  bids.forEach(b => { if (b[1] > maxVol) maxVol = b[1]; });

  // Render Asks
  asks.forEach(([price, vol]) => {
    const pct = Math.min(100, (vol / maxVol) * 100);
    const isMyAsk = port.my_ask && Math.abs(port.my_ask - price) < 0.01;
    html += `
      <div class="ladder-row ask" style="${isMyAsk ? 'border: 1px solid var(--accent-yellow);' : ''}">
        <div class="bar" style="width: ${pct}%;"></div>
        <span class="price">$${price.toFixed(2)}</span>
        <span>${vol.toFixed(1)}</span>
        <span style="font-size: 0.7rem; color: var(--accent-yellow);">${isMyAsk ? '★ MY ASK' : ''}</span>
      </div>
    `;
  });

  // Mid Price Barrier
  html += `
    <div class="ladder-mid">
      MID: $${mkt.mid_price.toFixed(2)} | SPREAD: $${mkt.spread.toFixed(2)}
    </div>
  `;

  // Render Bids
  bids.forEach(([price, vol]) => {
    const pct = Math.min(100, (vol / maxVol) * 100);
    const isMyBid = port.my_bid && Math.abs(port.my_bid - price) < 0.01;
    html += `
      <div class="ladder-row bid" style="${isMyBid ? 'border: 1px solid var(--accent-yellow);' : ''}">
        <div class="bar" style="width: ${pct}%;"></div>
        <span class="price">$${price.toFixed(2)}</span>
        <span>${vol.toFixed(1)}</span>
        <span style="font-size: 0.7rem; color: var(--accent-yellow);">${isMyBid ? '★ MY BID' : ''}</span>
      </div>
    `;
  });

  lobLadder.innerHTML = html;
}

function drawRaster() {
  const w = rasterCanvas.width;
  const h = rasterCanvas.height;
  rasterCtx.clearRect(0, 0, w, h);

  const totalNeurons = 100;
  const stepX = w / MAX_HISTORY;
  const rowH = h / totalNeurons;

  // Background divider lines
  rasterCtx.strokeStyle = "rgba(255, 255, 255, 0.04)";
  rasterCtx.beginPath();
  rasterCtx.moveTo(0, 32 * rowH);
  rasterCtx.lineTo(w, 32 * rowH);
  rasterCtx.moveTo(0, 96 * rowH);
  rasterCtx.lineTo(w, 96 * rowH);
  rasterCtx.stroke();

  // Draw spikes
  for (let t = 0; t < rasterBuffer.length; t++) {
    const x = t * stepX;
    const entry = rasterBuffer[t];

    // Sensory Spikes (0..31) in Neon Cyan
    rasterCtx.fillStyle = "#00f2fe";
    for (let id of entry.s) {
      rasterCtx.fillRect(x, id * rowH, Math.max(2, stepX - 1), Math.max(2, rowH - 0.5));
    }

    // Hidden Spikes (32..95) in Neon Purple
    rasterCtx.fillStyle = "#9d4edd";
    for (let id of entry.h) {
      rasterCtx.fillRect(x, (32 + id) * rowH, Math.max(2, stepX - 1), Math.max(2, rowH - 0.5));
    }

    // Motor Spikes (96..99) in Gold
    rasterCtx.fillStyle = "#ffd166";
    for (let id of entry.m) {
      rasterCtx.fillRect(x, (96 + id) * rowH, Math.max(2, stepX - 1), Math.max(3, rowH));
    }
  }
}

function drawOscilloscope() {
  const w = voltageCanvas.width;
  const h = voltageCanvas.height;
  voltageCtx.clearRect(0, 0, w, h);

  if (voltageHistory.length < 2) return;

  // Voltage scale: -80mV to -45mV
  const vMin = -80.0;
  const vMax = -45.0;
  const toY = (v) => h - ((v - vMin) / (vMax - vMin)) * h;

  // Reference lines (V_thresh = -55mV, V_rest = -70mV, V_reset = -75mV)
  voltageCtx.setLineDash([4, 4]);
  voltageCtx.strokeStyle = "rgba(255, 51, 102, 0.4)"; // Threshold
  voltageCtx.beginPath();
  voltageCtx.moveTo(0, toY(-55.0));
  voltageCtx.lineTo(w, toY(-55.0));
  voltageCtx.stroke();

  voltageCtx.strokeStyle = "rgba(126, 141, 166, 0.3)"; // Rest
  voltageCtx.beginPath();
  voltageCtx.moveTo(0, toY(-70.0));
  voltageCtx.lineTo(w, toY(-70.0));
  voltageCtx.stroke();
  voltageCtx.setLineDash([]);

  const stepX = w / MAX_HISTORY;

  // 1. Draw Sensory Mean Vm (Cyan)
  voltageCtx.strokeStyle = "#00f2fe";
  voltageCtx.lineWidth = 1.5;
  voltageCtx.beginPath();
  for (let i = 0; i < voltageHistory.length; i++) {
    const x = i * stepX;
    const y = toY(voltageHistory[i].sensory);
    if (i === 0) voltageCtx.moveTo(x, y);
    else voltageCtx.lineTo(x, y);
  }
  voltageCtx.stroke();

  // 2. Draw Hidden Mean Vm (Purple)
  voltageCtx.strokeStyle = "#9d4edd";
  voltageCtx.lineWidth = 1.5;
  voltageCtx.beginPath();
  for (let i = 0; i < voltageHistory.length; i++) {
    const x = i * stepX;
    const y = toY(voltageHistory[i].hidden);
    if (i === 0) voltageCtx.moveTo(x, y);
    else voltageCtx.lineTo(x, y);
  }
  voltageCtx.stroke();
}

// User Control Interactivity
document.getElementById("btn-pause").addEventListener("click", () => {
  fetch("/api/control", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action: "toggle_pause" })
  });
});

document.getElementById("btn-reset").addEventListener("click", () => {
  fetch("/api/control", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action: "reset" })
  });
  rasterBuffer.length = 0;
  voltageHistory.length = 0;
});

document.getElementById("slider-taum").addEventListener("input", (e) => {
  const val = parseFloat(e.target.value);
  document.getElementById("lbl-taum").innerText = `${val.toFixed(1)} ms`;
  fetch("/api/control", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action: "tune_neuromorphic", tau_m: val })
  });
});

document.getElementById("slider-speed").addEventListener("input", (e) => {
  const val = parseInt(e.target.value);
  document.getElementById("lbl-speed").innerText = `${val} Hz`;
  fetch("/api/control", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action: "set_speed", hz: val })
  });
});

document.getElementById("btn-sweep-buy").addEventListener("click", () => {
  fetch("/api/control", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action: "trigger_toxic_sweep", side: "BUY" })
  });
});

document.getElementById("btn-sweep-sell").addEventListener("click", () => {
  fetch("/api/control", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action: "trigger_toxic_sweep", side: "SELL" })
  });
});
