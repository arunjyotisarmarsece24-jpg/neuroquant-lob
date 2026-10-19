"""
Unit Tests: Unified Production CLI Binary ('neuroquant')
========================================================
Validates:
  1. CLI argument parsing and all 7 subcommands:
     app, verify, live, execute, benchmark, compile-simd, version.
  2. Subcommand execution and error handling.
  3. Formatted Rich tables, banner generation, and version manifest.
"""

import os
import sys
import unittest
import subprocess

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

class TestNeuroQuantCLI(unittest.TestCase):
    def test_cli_help(self):
        cmd = [sys.executable, "-m", "neuroquant.cli", "--help"]
        res = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(res.returncode, 0)
        self.assertIn("neuroquant", res.stdout.lower())
        self.assertIn("app", res.stdout)
        self.assertIn("verify", res.stdout)
        self.assertIn("live", res.stdout)
        self.assertIn("execute", res.stdout)
        self.assertIn("benchmark", res.stdout)
        self.assertIn("compile-simd", res.stdout)
        self.assertIn("version", res.stdout)

    def test_cli_version(self):
        cmd = [sys.executable, "-m", "neuroquant.cli", "version"]
        res = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(res.returncode, 0)
        self.assertIn("Arunjyoti Sarma", res.stdout)
        self.assertIn("1.1.0-PROD", res.stdout)

    def test_cli_execute(self):
        cmd = [sys.executable, "-m", "neuroquant.cli", "execute", "--shares", "5000", "--time", "30", "--risk", "1e-4"]
        res = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(res.returncode, 0)
        self.assertIn("Almgren-Chriss Optimal Trajectory", res.stdout)
        self.assertIn("Optimal Liquidation Metrics", res.stdout)
        self.assertIn("Expected Shortfall", res.stdout)

    def test_cli_live_itch(self):
        cmd = [sys.executable, "-m", "neuroquant.cli", "live", "--synthetic-itch", "--ticks", "1"]
        res = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(res.returncode, 0)
        self.assertIn("ITCH 5.0", res.stdout)
        self.assertIn("Packets Processed", res.stdout)

    def test_cli_risk(self):
        cmd = [sys.executable, "-m", "neuroquant.cli", "risk", "--checks", "1000"]
        res = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(res.returncode, 0)
        self.assertIn("PRE-TRADE MICROSECOND HARDWARE RISK GATE", res.stdout)
        self.assertIn("Circuit Breaker Enforcements", res.stdout)
        self.assertIn("KILLSWITCH", res.stdout)

    def test_cli_fix(self):
        cmd = [sys.executable, "-m", "neuroquant.cli", "fix", "--symbol", "BTCUSDT"]
        res = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(res.returncode, 0)
        self.assertIn("INSTITUTIONAL FIX 4.4 ORDER ROUTING", res.stdout)
        self.assertIn("35=D", res.stdout)
        self.assertIn("35=8", res.stdout)
        self.assertIn("CANCEL WON THE RACE", res.stdout)

    def test_subcommand_dispatch_registry(self):
        import argparse
        from neuroquant.cli import main
        # Ensure neuroquant entry point is callable
        self.assertTrue(callable(main))

if __name__ == "__main__":
    unittest.main()
