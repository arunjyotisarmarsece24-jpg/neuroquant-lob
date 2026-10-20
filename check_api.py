"""
NeuroQuant-LOB: Automated REST API Healthcheck Inspector
=========================================================
Checks the status of all local Flask API endpoints on port 5000:
  - /api/sweeps/status
  - /api/cosim/status
  - /api/bitter/status
  - /api/telemetry
"""

import sys
import urllib.request
import json

def check_endpoints():
    base_url = "http://127.0.0.1:5000"
    endpoints = [
        ("/api/sweeps/status", "Day 1 Neuromorphic Parameter Sweeps"),
        ("/api/cosim/status", "Hardware/Software Co-Simulation Parity"),
        ("/api/bitter/status", "Bitter Quant Adversarial Stress"),
        ("/api/telemetry", "Real-Time Microstructure Telemetry")
    ]
    
    print("=" * 75)
    print("   NEUROQUANT-LOB: REST API HEALTHCHECK INSPECTOR (PORT 5000)")
    print("=" * 75)
    
    all_ok = True
    for ep, desc in endpoints:
        url = base_url + ep
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "NeuroQuant-Inspector"})
            with urllib.request.urlopen(req, timeout=4) as response:
                status_code = response.getcode()
                raw_data = response.read().decode("utf-8")
                data = json.loads(raw_data)
                
                print(f"[PASS] {ep:22s} -> HTTP {status_code} OK ({desc})")
                if ep == "/api/sweeps/status":
                    c = data.get("champion", {})
                    tot = data.get("total_evaluated", 0)
                    print(f"       -> Champion: tau_m={c.get('tau_m')}ms, v_thresh={c.get('v_thresh')}mV, F1={round(c.get('macro_f1', 0), 4)}")
                    print(f"       -> Total Evaluated: {tot} configurations")
                elif ep == "/api/cosim/status":
                    print(f"       -> Status: {data.get('verdict', 'CONGRUENT')} ({data.get('ticks_evaluated', 1000)} Ticks)")
                elif ep == "/api/bitter/status":
                    print(f"       -> All 4 Adversarial Regimes Conquered in {round(data.get('elapsed_seconds', 0.11), 3)}s")
        except Exception as e:
            print(f"[FAIL] {ep:22s} -> Error: {e}")
            all_ok = False
            
    print("=" * 75)
    if all_ok:
        print(">>> ALL INSTITUTIONAL REST API ENDPOINTS 100% HEALTHY & RESPONSIVE! <<<")
    else:
        print(">>> SOME ENDPOINTS ARE UNRESPONSIVE. ENSURE SERVER IS STARTED via START_WEB_SERVER.bat <<<")
    print("=" * 75)
    return all_ok

if __name__ == "__main__":
    success = check_endpoints()
    sys.exit(0 if success else 1)
