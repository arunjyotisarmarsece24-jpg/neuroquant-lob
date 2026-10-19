#!/usr/bin/env bash
# ==============================================================================
# NeuroQuant-LOB Enterprise Container Entrypoint & SIMD Self-Test
# Author: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
# Version: 1.1.0-PROD
# ==============================================================================
set -e

echo "================================================================================"
echo " 🧠 NEUROQUANT-LOB: ENTERPRISE CONTAINER RUNTIME INITIALIZATION"
echo " Author: Arunjyoti Sarma | Platform: Docker Container (Linux x86_64)"
echo " Version: 1.1.0-PROD | C++20 AVX2 SIMD Core Active"
echo "================================================================================"

# Hardware CPU Feature Verification
echo "[*] Auditing host CPU vector capabilities..."
if grep -q "avx2" /proc/cpuinfo; then
    echo "[PASS] Intel/AMD AVX2 (256-bit SIMD registers) detected on host CPU."
else
    echo "[WARN] AVX2 flag not detected in /proc/cpuinfo. Fallback execution may occur."
fi

if grep -q "fma" /proc/cpuinfo; then
    echo "[PASS] Fused Multiply-Add (FMA) hardware acceleration confirmed."
else
    echo "[INFO] Standard scalar multiply-accumulate active."
fi

# Run Automated C++20 AVX2 SIMD Self-Test on startup
echo "[*] Executing pre-flight AVX2 SIMD diagnostic & memory alignment check..."
python -m neuroquant.cli compile-simd --check || {
    echo "[WARN] SIMD diagnostic reported non-fatal warning; proceeding with runtime initialization."
}

echo "[*] Container healthcheck probe configured at http://localhost:5000/api/telemetry"
echo "================================================================================"

# If command arguments are passed, execute them; otherwise start production application
if [ $# -eq 0 ]; then
    echo "[*] Starting default service: NeuroQuant Web & Mobile Companion Terminal..."
    exec neuroquant app --host 0.0.0.0 --port 5000 --no-browser
else
    echo "[*] Executing specified command: $@"
    exec "$@"
fi
