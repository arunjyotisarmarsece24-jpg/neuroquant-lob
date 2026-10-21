"""
Unit Tests for Verilog RTL Neuromorphic Hardware Simulation
===========================================================
Compiles and executes the hardware Leaky Integrate-and-Fire core via
Icarus Verilog (`iverilog`) and validates cycle-accurate hardware pass.

Author: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
"""

import unittest
import os
import subprocess
import shutil

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HARDWARE_DIR = os.path.join(PROJECT_ROOT, "hardware")
IVERILOG_BIN = r"C:\iverilog\bin\iverilog.exe"
VVP_BIN = r"C:\iverilog\bin\vvp.exe"

if not os.path.exists(IVERILOG_BIN):
    IVERILOG_BIN = shutil.which("iverilog") or "iverilog"
if not os.path.exists(VVP_BIN):
    VVP_BIN = shutil.which("vvp") or "vvp"


class TestVerilogHardwareSimulation(unittest.TestCase):

    def test_iverilog_compile_and_vvp_simulation(self):
        """Test that the Verilog LIF core compiles and passes all cycle-accurate assertions."""
        rtl_file = os.path.join(HARDWARE_DIR, "lif_neuron_core.v")
        tb_file = os.path.join(HARDWARE_DIR, "tb_lif_neuron.v")
        out_vvp = os.path.join(HARDWARE_DIR, "lif_sim.vvp")

        self.assertTrue(os.path.exists(rtl_file), "lif_neuron_core.v missing!")
        self.assertTrue(os.path.exists(tb_file), "tb_lif_neuron.v missing!")

        # 1. Compile
        res_compile = subprocess.run(
            [IVERILOG_BIN, "-o", out_vvp, rtl_file, tb_file],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        self.assertEqual(res_compile.returncode, 0, f"iverilog compilation failed:\n{res_compile.stderr}")
        self.assertTrue(os.path.exists(out_vvp), "Simulation binary lif_sim.vvp was not created!")

        # 2. Run cycle-accurate simulation
        res_sim = subprocess.run(
            [VVP_BIN, out_vvp],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        self.assertEqual(res_sim.returncode, 0, f"vvp simulation failed:\n{res_sim.stderr}")
        self.assertIn("100% VERILOG HARDWARE SYNTHESIS & RTL SIMULATION VERIFIED!", res_sim.stdout)
        self.assertIn("5 / 5 CHECKS PASSED (100.0% SUCCESS)", res_sim.stdout)

        # 3. Verify VCD waveform trace was generated
        vcd_path = os.path.join(HARDWARE_DIR, "neuroquant_lif_trace.vcd")
        self.assertTrue(os.path.exists(vcd_path), "VCD waveform trace was not generated!")
        self.assertGreater(os.path.getsize(vcd_path), 500, "VCD waveform file is empty or corrupted!")

    def test_iverilog_itch_parser_simulation(self):
        """Test that the AXI4-Stream NASDAQ ITCH 5.0 parser compiles and decodes packets."""
        rtl_file = os.path.join(HARDWARE_DIR, "itch_parser_axi.v")
        tb_file = os.path.join(HARDWARE_DIR, "tb_itch_parser.v")
        out_vvp = os.path.join(HARDWARE_DIR, "itch_sim.vvp")

        self.assertTrue(os.path.exists(rtl_file), "itch_parser_axi.v missing!")
        self.assertTrue(os.path.exists(tb_file), "tb_itch_parser.v missing!")

        # 1. Compile
        res_compile = subprocess.run(
            [IVERILOG_BIN, "-o", out_vvp, rtl_file, tb_file],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        self.assertEqual(res_compile.returncode, 0, f"iverilog compilation failed:\n{res_compile.stderr}")

        # 2. Run simulation
        res_sim = subprocess.run(
            [VVP_BIN, out_vvp],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        self.assertEqual(res_sim.returncode, 0, f"vvp simulation failed:\n{res_sim.stderr}")
        self.assertIn("3 / 3 CHECKS PASSED (100.0%)", res_sim.stdout)
        self.assertIn("NASDAQ ITCH 5.0 AXI4-STREAM HARDWARE PARSER VERIFIED!", res_sim.stdout)

        # 3. Verify VCD trace
        vcd_path = os.path.join(HARDWARE_DIR, "neuroquant_itch_trace.vcd")
        self.assertTrue(os.path.exists(vcd_path), "ITCH VCD trace was not generated!")
        self.assertGreater(os.path.getsize(vcd_path), 500, "ITCH VCD trace is empty!")

    def test_iverilog_risk_gate_simulation(self):
        """Test that the Pre-Trade Hardware Risk Gate evaluates all 8 circuit breaker scenarios."""
        rtl_file = os.path.join(HARDWARE_DIR, "risk_gate_core.v")
        tb_file = os.path.join(HARDWARE_DIR, "tb_risk_gate.v")
        out_vvp = os.path.join(HARDWARE_DIR, "risk_sim.vvp")

        self.assertTrue(os.path.exists(rtl_file), "risk_gate_core.v missing!")
        self.assertTrue(os.path.exists(tb_file), "tb_risk_gate.v missing!")

        # 1. Compile
        res_compile = subprocess.run(
            [IVERILOG_BIN, "-o", out_vvp, rtl_file, tb_file],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        self.assertEqual(res_compile.returncode, 0, f"iverilog compilation failed:\n{res_compile.stderr}")

        # 2. Run simulation
        res_sim = subprocess.run(
            [VVP_BIN, out_vvp],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        self.assertEqual(res_sim.returncode, 0, f"vvp simulation failed:\n{res_sim.stderr}")
        self.assertIn("8 / 8 CHECKS PASSED (100.0%)", res_sim.stdout)
        self.assertIn("PRE-TRADE HARDWARE RISK GATE VERIFIED IN 1 CLOCK CYCLE!", res_sim.stdout)

        # 3. Verify VCD trace
        vcd_path = os.path.join(HARDWARE_DIR, "neuroquant_risk_trace.vcd")
        self.assertTrue(os.path.exists(vcd_path), "Risk Gate VCD trace was not generated!")
        self.assertGreater(os.path.getsize(vcd_path), 500, "Risk Gate VCD trace is empty!")

    def test_iverilog_top_level_simulation(self):
        """Test unified top-level FPGA accelerator integration (LIF + ITCH + Risk Gate)."""
        rtl_files = [
            os.path.join(HARDWARE_DIR, "lif_neuron_core.v"),
            os.path.join(HARDWARE_DIR, "itch_parser_axi.v"),
            os.path.join(HARDWARE_DIR, "risk_gate_core.v"),
            os.path.join(HARDWARE_DIR, "neuroquant_fpga_top.v"),
        ]
        tb_file = os.path.join(HARDWARE_DIR, "tb_neuroquant_fpga_top.v")
        out_vvp = os.path.join(HARDWARE_DIR, "top_sim.vvp")

        # Compile
        res_compile = subprocess.run(
            [IVERILOG_BIN, "-o", out_vvp] + rtl_files + [tb_file],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        self.assertEqual(res_compile.returncode, 0, f"iverilog compilation failed:\n{res_compile.stderr}")

        # Run simulation
        res_sim = subprocess.run(
            [VVP_BIN, out_vvp],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        self.assertEqual(res_sim.returncode, 0, f"vvp simulation failed:\n{res_sim.stderr}")
        self.assertIn("5 / 5 CHECKS PASSED (100.0%)", res_sim.stdout)
        self.assertIn("100% VERILOG HARDWARE SYNTHESIS TOP-LEVEL VERIFIED!", res_sim.stdout)

    def test_iverilog_formal_invariance_simulation(self):
        """Test brutal formal mathematical invariance audit (21,514 property assertions)."""
        rtl_files = [
            os.path.join(HARDWARE_DIR, "lif_neuron_core.v"),
            os.path.join(HARDWARE_DIR, "itch_parser_axi.v"),
            os.path.join(HARDWARE_DIR, "risk_gate_core.v"),
            os.path.join(HARDWARE_DIR, "neuroquant_fpga_top.v"),
        ]
        tb_file = os.path.join(HARDWARE_DIR, "tb_formal_invariance.v")
        out_vvp = os.path.join(HARDWARE_DIR, "formal_sim.vvp")

        # Compile with -g2005-sv
        res_compile = subprocess.run(
            [IVERILOG_BIN, "-g2005-sv", "-o", out_vvp] + rtl_files + [tb_file],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        self.assertEqual(res_compile.returncode, 0, f"iverilog compilation failed:\n{res_compile.stderr}")

        # Run simulation
        res_sim = subprocess.run(
            [VVP_BIN, out_vvp],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        self.assertEqual(res_sim.returncode, 0, f"vvp simulation failed:\n{res_sim.stderr}")
        self.assertIn("VERIFIED MATHEMATICALLY IMMUTABLE", res_sim.stdout)
        self.assertIn("Failed Assertions:         0", res_sim.stdout)

    def test_iverilog_uart_bridge_simulation(self):
        """Test physical Digilent Arty S7 + NodeMCU ESP8266 serial bridge (921,600 baud)."""
        rtl_files = [
            os.path.join(HARDWARE_DIR, "lif_neuron_core.v"),
            os.path.join(HARDWARE_DIR, "itch_parser_axi.v"),
            os.path.join(HARDWARE_DIR, "risk_gate_core.v"),
            os.path.join(HARDWARE_DIR, "neuroquant_fpga_top.v"),
            os.path.join(HARDWARE_DIR, "uart_rx_bridge.v"),
            os.path.join(HARDWARE_DIR, "uart_tx_telemetry.v"),
            os.path.join(HARDWARE_DIR, "neuroquant_arty_s7_top.v"),
        ]
        tb_file = os.path.join(HARDWARE_DIR, "tb_uart_bridge.v")
        out_vvp = os.path.join(HARDWARE_DIR, "uart_sim.vvp")

        # Compile
        res_compile = subprocess.run(
            [IVERILOG_BIN, "-g2005-sv", "-o", out_vvp] + rtl_files + [tb_file],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        self.assertEqual(res_compile.returncode, 0, f"iverilog compilation failed:\n{res_compile.stderr}")

        # Run simulation
        res_sim = subprocess.run(
            [VVP_BIN, out_vvp],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        self.assertEqual(res_sim.returncode, 0, f"vvp simulation failed:\n{res_sim.stderr}")
        self.assertIn("5 / 5 CHECKS PASSED", res_sim.stdout)
        self.assertIn("100% ARTY S7 + ESP8266 SERIAL BRIDGE VERIFIED!", res_sim.stdout)

    def test_iverilog_cosim_parity_simulation(self):
        """Test continuous 1,000-tick hardware/software co-simulation stream."""
        rtl_files = [
            os.path.join(HARDWARE_DIR, "lif_neuron_core.v"),
            os.path.join(HARDWARE_DIR, "risk_gate_core.v"),
        ]
        tb_file = os.path.join(HARDWARE_DIR, "tb_cosim_parity.v")
        out_vvp = os.path.join(HARDWARE_DIR, "cosim_sim.vvp")

        # Compile
        res_compile = subprocess.run(
            [IVERILOG_BIN, "-g2005-sv", "-o", out_vvp] + rtl_files + [tb_file],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        self.assertEqual(res_compile.returncode, 0, f"iverilog compilation failed:\n{res_compile.stderr}")

        # Run simulation
        res_sim = subprocess.run(
            [VVP_BIN, out_vvp],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        self.assertEqual(res_sim.returncode, 0, f"vvp simulation failed:\n{res_sim.stderr}")
        self.assertIn("BIT-FOR-BIT HARDWARE CO-SIMULATION STREAM COMPLETED!", res_sim.stdout)
        self.assertIn("CO-SIMULATION SUMMARY: 1,000 TICKS EVALUATED", res_sim.stdout)

        # Check VCD
        vcd_path = os.path.join(HARDWARE_DIR, "neuroquant_cosim_trace.vcd")
        self.assertTrue(os.path.exists(vcd_path), "Cosim VCD trace was not generated!")
        self.assertGreater(os.path.getsize(vcd_path), 500, "Cosim VCD trace is empty!")

    def test_iverilog_champion_lif_simulation(self):
        """Test Day 1 Pareto Champion LIF hardware simulation with optimal_neuromorphic_params.vh."""
        rtl_file = os.path.join(HARDWARE_DIR, "lif_neuron_core.v")
        header_file = os.path.join(HARDWARE_DIR, "optimal_neuromorphic_params.vh")
        tb_file = os.path.join(HARDWARE_DIR, "tb_optimal_champion_lif.v")
        out_vvp = os.path.join(HARDWARE_DIR, "champion_lif_sim.vvp")

        self.assertTrue(os.path.exists(rtl_file), "lif_neuron_core.v missing!")
        self.assertTrue(os.path.exists(header_file), "optimal_neuromorphic_params.vh missing!")
        self.assertTrue(os.path.exists(tb_file), "tb_optimal_champion_lif.v missing!")

        # 1. Compile with include directory
        res_compile = subprocess.run(
            [IVERILOG_BIN, "-g2005-sv", "-I", HARDWARE_DIR, "-o", out_vvp, rtl_file, tb_file],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        self.assertEqual(res_compile.returncode, 0, f"iverilog compilation failed:\n{res_compile.stderr}")

        # 2. Run simulation
        res_sim = subprocess.run(
            [VVP_BIN, out_vvp],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        self.assertEqual(res_sim.returncode, 0, f"vvp simulation failed:\n{res_sim.stderr}")
        self.assertIn("100% VERILOG HARDWARE DAY 1 CHAMPION LIF SIMULATION VERIFIED!", res_sim.stdout)
        self.assertIn("Passed Assertions:      5", res_sim.stdout)
        self.assertIn("Failed Assertions:      0", res_sim.stdout)

        # 3. Check VCD trace
        vcd_path = os.path.join(HARDWARE_DIR, "neuroquant_champion_lif_trace.vcd")
        self.assertTrue(os.path.exists(vcd_path), "Champion LIF VCD trace was not generated!")
        self.assertGreater(os.path.getsize(vcd_path), 500, "Champion LIF VCD trace is empty!")

    def test_iverilog_multilevel_ofi_hawkes_simulation(self):
        """Test Day 2 Multi-Level OFI & Cross-Level Hawkes RTL simulation with optimal_ofi_params.vh."""
        rtl_file = os.path.join(HARDWARE_DIR, "multilevel_ofi_hawkes.v")
        header_file = os.path.join(HARDWARE_DIR, "optimal_ofi_params.vh")
        tb_file = os.path.join(HARDWARE_DIR, "tb_multilevel_ofi_hawkes.v")
        out_vvp = os.path.join(HARDWARE_DIR, "ofi_sim.vvp")

        self.assertTrue(os.path.exists(rtl_file), "multilevel_ofi_hawkes.v missing!")
        self.assertTrue(os.path.exists(header_file), "optimal_ofi_params.vh missing!")
        self.assertTrue(os.path.exists(tb_file), "tb_multilevel_ofi_hawkes.v missing!")

        # 1. Compile with SystemVerilog switch and include directory
        res_compile = subprocess.run(
            [IVERILOG_BIN, "-g2005-sv", "-I", HARDWARE_DIR, "-o", out_vvp, rtl_file, tb_file],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        self.assertEqual(res_compile.returncode, 0, f"iverilog compilation failed:\n{res_compile.stderr}")

        # 2. Run simulation
        res_sim = subprocess.run(
            [VVP_BIN, out_vvp],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        self.assertEqual(res_sim.returncode, 0, f"vvp simulation failed:\n{res_sim.stderr}")
        self.assertIn("100% MULTI-LEVEL OFI & HAWKES RTL VERIFIED!", res_sim.stdout)
        self.assertIn("5 / 5 PASSED", res_sim.stdout)

        # 3. Check VCD trace
        vcd_path = os.path.join(HARDWARE_DIR, "neuroquant_ofi_trace.vcd")
        self.assertTrue(os.path.exists(vcd_path), "OFI VCD trace was not generated!")
        self.assertGreater(os.path.getsize(vcd_path), 500, "OFI VCD trace is empty!")


if __name__ == "__main__":
    unittest.main()
