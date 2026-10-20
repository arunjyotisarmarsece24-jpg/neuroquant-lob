"""
Unit Tests for Hardware/Software Co-Simulation Parity Benchmark
==============================================================
Validates 1,000-tick continuous co-simulation between Python reference models
and cycle-accurate Verilog HDL RTL simulation.

Author: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
"""

import unittest
import os
import json
from benchmarks.run_cosim_hardware_software_audit import run_hardware_cosim, run_software_model, main as run_audit_main


class TestCosimParity(unittest.TestCase):

    def test_software_reference_model(self):
        """Test software LIF and Risk Gate models under 1,000-tick stream."""
        res = run_software_model(1000)
        self.assertEqual(res["approvals"] + res["rejections"], 1000)
        self.assertGreater(res["spikes"], 0)
        self.assertGreater(res["approvals"], 0)
        self.assertGreater(res["rejections"], 0)

    def test_hardware_cosim_simulation(self):
        """Test Verilog RTL execution under 1,000-tick stream."""
        res = run_hardware_cosim()
        self.assertEqual(res["approvals"] + res["rejections"], 1000)
        self.assertGreater(res["spikes"], 0)
        self.assertIn("BIT-FOR-BIT HARDWARE CO-SIMULATION STREAM COMPLETED!", res["stdout"])

    def test_full_cosim_audit(self):
        """Test complete co-simulation parity benchmark and JSON output."""
        run_audit_main()
        json_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "benchmarks",
            "cosim_parity_results.json"
        )
        self.assertTrue(os.path.exists(json_path), "cosim_parity_results.json missing!")
        with open(json_path, "r") as f:
            data = json.load(f)
        self.assertEqual(data["status"], "PASS")
        self.assertEqual(data["ticks_evaluated"], 1000)


if __name__ == "__main__":
    unittest.main()
