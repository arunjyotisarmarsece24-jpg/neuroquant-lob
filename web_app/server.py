"""
NeuroQuant Web Server
======================
Flask backend streaming real-time asynchronous neuromorphic spikes,
order book depths, and trade fills via Server-Sent Events (SSE).
"""

import json
import time
import numpy as np
from flask import Flask, render_template, Response, request, jsonify
from neuroquant.strategy import NeuromorphicAlphaSystem
from config import CONFIG_NEURO, CONFIG_MARKET, CONFIG_EXEC

app = Flask(__name__, template_folder="templates", static_folder="static")

# Singleton Neuromorphic System Instance
system = NeuromorphicAlphaSystem()
is_paused = False
playback_delay_sec = 0.04  # 25 Hz default

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/telemetry")
def get_telemetry():
    """Single-shot telemetry snapshot."""
    global system, is_paused
    if not is_paused:
        data = system.step()
    else:
        # Static view without advancing time
        data = {
            "step": system.sim_step_count,
            "sim_time_ms": round(system.sim_time_ms, 2),
            "market": system.book.get_snapshot(),
            "portfolio": system.executor.get_portfolio_status(),
            "neuro": {
                "signals": system.brain.get_motor_readout_signals(),
                "sensory_v_mean": round(system.brain.sensory.get_mean_voltage(), 2),
                "hidden_v_mean": round(system.brain.hidden.get_mean_voltage(), 2),
                "motor_v": [round(float(v), 2) for v in system.brain.motor.voltage],
                "motor_weights_norm": round(float(np.linalg.norm(system.brain.plasticity_motor.weights)), 4)
            }
        }
    return jsonify(data)

@app.route("/api/stream")
def stream():
    """Server-Sent Events (SSE) high-frequency stream."""
    def event_generator():
        global system, is_paused, playback_delay_sec
        while True:
            if not is_paused:
                telemetry = system.step()
                payload = f"data: {json.dumps(telemetry)}\n\n"
                yield payload
            time.sleep(playback_delay_sec)
            
    return Response(event_generator(), mimetype="text/event-stream")

@app.route("/api/control", methods=["POST"])
def control():
    """Control simulation state and neuromorphic parameters."""
    global system, is_paused, playback_delay_sec
    req = request.json or {}
    
    action = req.get("action")
    if action == "toggle_pause":
        is_paused = not is_paused
        return jsonify({"status": "ok", "paused": is_paused})
        
    elif action == "reset":
        system.reset()
        return jsonify({"status": "ok", "message": "Simulation reset"})
        
    elif action == "set_speed":
        hz = float(req.get("hz", 25))
        playback_delay_sec = 1.0 / max(1.0, min(100.0, hz))
        return jsonify({"status": "ok", "delay_sec": playback_delay_sec})
        
    elif action == "trigger_toxic_sweep":
        side = req.get("side", "BUY")
        system.feed.toxic_steps_remaining = 5
        system.feed.toxic_direction = side
        return jsonify({"status": "ok", "message": f"Triggered toxic sweep {side}"})
        
    elif action == "tune_neuromorphic":
        # Dynamic tuning of physical membrane parameters
        tau_m = float(req.get("tau_m", system.neuro_cfg.tau_m))
        system.brain.sensory.cfg.tau_m = tau_m
        system.brain.sensory.decay = float(np.exp(-system.neuro_cfg.time_step_ms / tau_m))
        system.brain.hidden.cfg.tau_m = tau_m
        system.brain.hidden.decay = float(np.exp(-system.neuro_cfg.time_step_ms / tau_m))
        return jsonify({"status": "ok", "tau_m": tau_m})
        
    return jsonify({"status": "error", "message": "Unknown action"}), 400

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
