"""
Smoke test verifying CLI rendering and layout generation
"""

import unittest
from run_cli import make_layout, generate_market_table, generate_neuro_panel, generate_exec_panel
from neuroquant.strategy import NeuromorphicAlphaSystem

class TestCLIRendering(unittest.TestCase):
    def test_panels_render(self):
        s = NeuromorphicAlphaSystem()
        telemetry = s.step()
        
        m_panel = generate_market_table(telemetry["market"])
        n_panel = generate_neuro_panel(telemetry["neuro"])
        e_panel = generate_exec_panel(telemetry["portfolio"], telemetry["market"])
        
        self.assertIsNotNone(m_panel)
        self.assertIsNotNone(n_panel)
        self.assertIsNotNone(e_panel)

if __name__ == "__main__":
    unittest.main()
