"""
NeuroQuant-LOB: Brutal Real-World Verification Harness (Root Launcher)
======================================================================
Convenience entry-point delegating to benchmarks/run_brutal_real_world_verification.py.

Usage:
  python run_brutal_real_world_verification.py
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if __name__ == "__main__":
    from benchmarks.run_brutal_real_world_verification import main
    main()
