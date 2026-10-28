import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mojssp.portfolio.page_hinkley import ClassicalUCB1Selector
from mojssp.portfolio.dmab import DMABSelector, ArmStats

class TestClassicalUCB1Selector(unittest.TestCase):
    def test_protocol_conformance(self):
        selector = ClassicalUCB1Selector(["A", "B", "C"], exploration_factor=0.07, seed=42)
        self.assertIsInstance(selector, DMABSelector)

    def test_initial_probe_sequence(self):
        selector = ClassicalUCB1Selector(["MOEA/D", "NSGA-II", "SPEA2"], seed=42)
        # First 3 pulls must cycle in registration order
        self.assertEqual(selector.select_arm(), "MOEA/D")
        selector.update("MOEA/D", 0.1)
        self.assertEqual(selector.select_arm(), "NSGA-II")
        selector.update("NSGA-II", 0.05)
        self.assertEqual(selector.select_arm(), "SPEA2")
        selector.update("SPEA2", 0.02)
        self.assertTrue(selector.is_initial_probe_complete)

    def test_ucb_calculation_and_exploitation(self):
        selector = ClassicalUCB1Selector(["A", "B"], exploration_factor=0.0, seed=42)
        selector.update("A", 1.0)
        selector.update("B", 0.1)
        # With c=0, arm A has higher empirical mean (1.0 vs 0.1)
        self.assertEqual(selector.select_arm(), "A")

    def test_invalid_parameters(self):
        with self.assertRaises(ValueError):
            ClassicalUCB1Selector([])
        with self.assertRaises(ValueError):
            ClassicalUCB1Selector(["A", "A"])
        with self.assertRaises(ValueError):
            ClassicalUCB1Selector(["A"], exploration_factor=-1.0)

    def test_reset(self):
        selector = ClassicalUCB1Selector(["A", "B"], seed=42)
        selector.update("A", 1.0)
        selector.reset()
        self.assertEqual(selector.total_pulls, 0)
        self.assertFalse(selector.is_initial_probe_complete)

if __name__ == "__main__":
    unittest.main()
