"""
NeuroQuant-LOB: Hardware Latency Distribution Profiler (Root Launcher)
======================================================================
Convenience entry-point delegating to benchmarks/run_latency_distribution.py.

Usage:
  python run_latency_distribution.py
  python run_latency_distribution.py --iterations 1000000
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if __name__ == "__main__":
    from benchmarks.run_latency_distribution import main
    main()
