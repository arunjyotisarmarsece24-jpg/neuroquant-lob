"""
NeuroQuant Web Server & Mobile API Backend
==========================================
Flask backend streaming real-time asynchronous neuromorphic spikes,
order book depths, trade fills, interactive Almgren-Chriss simulations,
adversarial mathematical proofs, and technical whitepaper reader.
Author: Arunjyoti Sarma
"""

import os
import sys
import json
import time
import numpy as np
from flask import Flask, render_template, Response, request, jsonify, send_from_directory

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from neuroquant.strategy import NeuromorphicAlphaSystem
from neuroquant.execution.almgren_chriss import AlmgrenChrissOptimizer, AlmgrenChrissConfig
from neuroquant.execution.market_impact import NonLinearMarketImpactEngine, MarketImpactConfig
from neuroquant.execution.fee_model import TieredExchangeFeeModel, FeeModelConfig
from config import CONFIG_NEURO, CONFIG_MARKET, CONFIG_EXEC

app = Flask(__name__, template_folder="templates", static_folder="static")

# Singleton Neuromorphic System Instance
system = NeuromorphicAlphaSystem()
is_paused = False
playback_delay_sec = 0.04  # 25 Hz default

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/manifest.json")
def manifest():
    return send_from_directory(os.path.join(PROJECT_ROOT, "web_app", "static"), "manifest.json")

@app.route("/paper/page/<int:page_num>")
def paper_page(page_num):
    page_num = max(1, min(6, page_num))
    rendered_dir = os.path.join(PROJECT_ROOT, "paper", "rendered_pages")
    return send_from_directory(rendered_dir, f"page_{page_num}.png")

@app.route("/paper/download")
def download_paper():
    paper_dir = os.path.join(PROJECT_ROOT, "paper")
    return send_from_directory(paper_dir, "neuroquant_lob.pdf", as_attachment=True, download_name="neuroquant_lob_whitepaper.pdf")

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
                "motor_weights_norm": round(float(np.linalg.norm(system.brain.plasticity_motor.weights)), 4),
                "sensory_firing_indices": system.brain.sensory_spikes.tolist() if hasattr(system.brain, "sensory_spikes") else [],
                "hidden_firing_indices": system.brain.hidden_spikes.tolist() if hasattr(system.brain, "hidden_spikes") else [],
                "motor_firing_indices": system.brain.motor_spikes.tolist() if hasattr(system.brain, "motor_spikes") else []
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

@app.route("/api/almgren_simulate", methods=["POST"])
def almgren_simulate():
    """
    Solves optimal execution schedule under non-linear square-root impact
    and tiered fee accounting with comparison against standard TWAP.
    """
    req = request.json or {}
    total_shares = float(req.get("shares", 10_000.0))
    time_horizon_sec = float(req.get("time_sec", 60.0))
    num_intervals = int(req.get("intervals", 20))
    risk_aversion = float(req.get("lambda_risk", 1e-4))
    volatility = float(req.get("sigma", 0.25))
    eta = float(req.get("eta", 5e-5))
    alpha = float(req.get("alpha", 0.5))
    maker_rebate = float(req.get("maker_rebate", -0.00002))
    taker_fee = float(req.get("taker_fee", 0.00005))
    maker_pct = float(req.get("maker_pct", 0.65))

    cfg = AlmgrenChrissConfig(
        total_shares=total_shares,
        time_horizon_sec=time_horizon_sec,
        num_intervals=num_intervals,
        risk_aversion_lambda=risk_aversion,
        volatility_sigma=volatility,
        eta=eta,
        alpha=alpha
    )
    optimizer = AlmgrenChrissOptimizer(cfg)
    sched = optimizer.calculate_optimal_schedule()
    
    # TWAP schedule
    tau = time_horizon_sec / num_intervals
    twap_holdings = [total_shares * (1.0 - j / num_intervals) for j in range(num_intervals + 1)]
    twap_trades = [total_shares / num_intervals] * num_intervals

    # Cost calculations
    time_points = [round(float(t), 2) for t in sched.time_points]
    ac_holdings = [round(float(h), 1) for h in sched.holdings]
    ac_trades = [round(float(n), 1) for n in sched.trades]
    twap_holdings = [round(float(h), 1) for h in twap_holdings]

    # Non-linear temporary slippage: sum_j eta * (n_j / tau)^alpha * n_j
    ac_slippage = sum(eta * ((n / tau) ** alpha) * n for n in sched.trades)
    twap_slippage = sum(eta * ((n / tau) ** alpha) * n for n in twap_trades)

    # Permanent impact: 0.5 * gamma * X_0^2
    gamma = cfg.gamma
    perm_impact = 0.5 * gamma * (total_shares ** 2)

    # Fee model: effective fee per share
    eff_fee_rate = maker_pct * maker_rebate + (1.0 - maker_pct) * taker_fee
    nominal_price = 18500.0  # reference mid price
    ac_fees = eff_fee_rate * total_shares * nominal_price
    maker_rebates_harvested = max(0.0, -maker_rebate * (maker_pct * total_shares) * nominal_price)

    # Total implementation shortfall
    ac_total_shortfall = ac_slippage + perm_impact + ac_fees
    twap_total_shortfall = twap_slippage + perm_impact + (taker_fee * total_shares * nominal_price)

    savings_dollars = twap_total_shortfall - ac_total_shortfall
    savings_pct = (savings_dollars / max(1e-6, twap_total_shortfall)) * 100.0

    return jsonify({
        "status": "ok",
        "kappa": round(sched.kappa, 4),
        "half_life_sec": round(sched.half_life_sec, 2),
        "time_points": time_points,
        "ac_holdings": ac_holdings,
        "ac_trades": ac_trades,
        "twap_holdings": twap_holdings,
        "metrics": {
            "ac_shortfall": round(ac_total_shortfall, 2),
            "twap_shortfall": round(twap_total_shortfall, 2),
            "savings_dollars": round(savings_dollars, 2),
            "savings_pct": round(savings_pct, 1),
            "maker_rebates_harvested": round(maker_rebates_harvested, 2),
            "ac_slippage": round(ac_slippage, 2),
            "twap_slippage": round(twap_slippage, 2)
        }
    })

def sanitize_for_json(obj):
    """Recursively replaces inf and nan with 0.0 for strict RFC 8259 JSON compliance."""
    import math
    if isinstance(obj, float):
        if math.isinf(obj) or math.isnan(obj):
            return 0.0
        return obj
    elif isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [sanitize_for_json(v) for v in obj]
    return obj

@app.route("/api/run_proof_attack", methods=["POST"])
def run_proof_attack():
    """Executes live adversarial proof attack and returns mathematical verification metrics."""
    req = request.json or {}
    theorem_id = int(req.get("theorem_id", 1))
    trials = int(req.get("trials", 10_000))

    from benchmarks.run_adversarial_proof_attacks import (
        attack_theorem_1_bibo_invariance,
        attack_theorem_2_variational_convexity,
        attack_theorem_3_lyapunov_stability,
        attack_lemma_1_adverse_selection_crossover,
        attack_lemma_2_poisson_noise_audit
    )

    t0 = time.perf_counter()
    if theorem_id == 1:
        res = attack_theorem_1_bibo_invariance(n_steps=trials)
    elif theorem_id == 2:
        res = attack_theorem_2_variational_convexity(n_perturbations=trials)
    elif theorem_id == 3:
        res = attack_theorem_3_lyapunov_stability(n_matrices=min(1000, trials))
    elif theorem_id == 4:
        res = attack_lemma_1_adverse_selection_crossover(n_points=min(1000, trials))
    elif theorem_id == 5:
        res = attack_lemma_2_poisson_noise_audit(n_trials=min(10000, trials))
    else:
        return jsonify({"status": "error", "message": "Invalid theorem ID"}), 400
    
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    res["elapsed_ms"] = round(elapsed_ms, 2)
    return jsonify(sanitize_for_json(res))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
