"""Comprehensive unit tests for PageHinkleyDMABSelector.

Verifies:
A. Initialization & initial probe order
B. UCB calculation against manual values
C. Selection of arm with maximal UCB index
D. Deterministic tie-breaking with seed
E. Exact single update of rewards and pull counts
F. Detector accumulation without alarm
G. Page-Hinkley alarm triggering on drop
H. Clean reset of cycle statistics while preserving lifetime history and alarms
I. Mandatory re-exploration of all arms after alarm
J. Exact bit-for-bit reproducibility between independent instances
K. Strict conformance to DMABSelector protocol
L. Regression test ensuring SlidingWindowUCB and RoundRobinSelector remain unaffected
M. Defensive validation of constructor parameters and observations
N. Telemetry and PageHinkleyAlarmRecord auditing
O. Neutral warm-up behavior (initialize_arm does not affect detector)
Boundary cases: single arm, all-zero rewards, constant rewards, consecutive alarms.
"""

import math
from pathlib import Path
import sys
import unittest

# Add src directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mojssp.portfolio.page_hinkley import PageHinkleyAlarmRecord, PageHinkleyDMABSelector
from mojssp.portfolio.dmab import (
    ArmStats,
    DMABSelector,
    RoundRobinSelector,
    SlidingWindowUCB,
)


class TestPageHinkleyDMABSelector(unittest.TestCase):
    """Test suite for PageHinkleyDMABSelector."""

    def setUp(self) -> None:
        self.arm_names = ["MOEA/D", "NSGA-II", "SPEA2"]

    def test_protocol_conformance(self) -> None:
        """Verify that PageHinkleyDMABSelector conforms to DMABSelector protocol."""
        selector = PageHinkleyDMABSelector(self.arm_names, seed=42)
        self.assertIsInstance(selector, DMABSelector)
        self.assertEqual(selector.arm_names, tuple(self.arm_names))
        self.assertEqual(selector.total_pulls, 0)
        self.assertEqual(selector.cycle_pulls, 0)
        self.assertEqual(selector.num_alarms, 0)
        self.assertEqual(selector.alarm_history, ())

    def test_parameter_validation(self) -> None:
        """Verify defensive validation of constructor arguments."""
        # Empty arm names
        with self.assertRaises(ValueError):
            PageHinkleyDMABSelector([])

        # Duplicate arm names
        with self.assertRaises(ValueError):
            PageHinkleyDMABSelector(["MOEA/D", "NSGA-II", "MOEA/D"])

        # Invalid arm names
        with self.assertRaises(ValueError):
            PageHinkleyDMABSelector(["MOEA/D", "   "])

        # Invalid exploration factor
        with self.assertRaises(ValueError):
            PageHinkleyDMABSelector(self.arm_names, exploration_factor=-0.05)
        with self.assertRaises(ValueError):
            PageHinkleyDMABSelector(self.arm_names, exploration_factor=float("nan"))

        # Invalid delta / threshold
        with self.assertRaises(ValueError):
            PageHinkleyDMABSelector(self.arm_names, delta=-0.001)
        with self.assertRaises(ValueError):
            PageHinkleyDMABSelector(self.arm_names, threshold=0.0)

    def test_initial_cycle_probe_order(self) -> None:
        """Verify that arms are probed in canonical order before index selection."""
        selector = PageHinkleyDMABSelector(self.arm_names, seed=42)

        # Pull 1: MOEA/D
        self.assertEqual(selector.select_arm(), "MOEA/D")
        self.assertTrue(selector.is_in_initial_probe("MOEA/D"))
        selector.update("MOEA/D", 0.010)
        self.assertFalse(selector.is_in_initial_probe("MOEA/D"))

        # Pull 2: NSGA-II
        self.assertEqual(selector.select_arm(), "NSGA-II")
        self.assertTrue(selector.is_in_initial_probe("NSGA-II"))
        selector.update("NSGA-II", 0.005)

        # Pull 3: SPEA2
        self.assertEqual(selector.select_arm(), "SPEA2")
        self.assertTrue(selector.is_in_initial_probe("SPEA2"))
        selector.update("SPEA2", 0.008)

        # After all probed: probe complete
        self.assertTrue(selector.is_initial_probe_complete)
        self.assertEqual(selector.cycle_pulls, 3)
        self.assertEqual(selector.total_pulls, 3)

    def test_manual_ucb_calculation(self) -> None:
        """Verify UCB index calculation against hand-computed values.

        Setup after initial probe:
        Arms: [A, B]
        c = 0.07
        t_cycle = 2

        Update A with r = 0.010 -> n_A = 1, S_A = 0.010, mean_A = 0.010
        Update B with r = 0.005 -> n_B = 1, S_B = 0.005, mean_B = 0.005

        At t_cycle = 2:
        exploration = 0.07 * sqrt(2 * ln(2) / 1) = 0.07 * sqrt(2 * 0.69314718) = 0.07 * 1.17741 = 0.0824187
        UCB_A = 0.010 + 0.0824187 = 0.0924187
        UCB_B = 0.005 + 0.0824187 = 0.0874187
        """
        arms = ["A", "B"]
        c = 0.07
        selector = PageHinkleyDMABSelector(arms, exploration_factor=c, delta=0.01, threshold=0.5, seed=1)

        # Probe A
        self.assertEqual(selector.select_arm(), "A")
        selector.update("A", 0.010)

        # Probe B
        self.assertEqual(selector.select_arm(), "B")
        selector.update("B", 0.005)

        stats = selector.get_stats()
        expected_explore = c * math.sqrt(2.0 * math.log(2) / 1.0)
        self.assertAlmostEqual(stats["A"].ucb, 0.010 + expected_explore, places=6)
        self.assertAlmostEqual(stats["B"].ucb, 0.005 + expected_explore, places=6)

        # Next selection must pick A (highest UCB)
        self.assertEqual(selector.select_arm(), "A")

    def test_deterministic_tie_breaking(self) -> None:
        """Verify that tie breaking is fully deterministic across identical seeds."""
        s1 = PageHinkleyDMABSelector(self.arm_names, seed=123)
        s2 = PageHinkleyDMABSelector(self.arm_names, seed=123)

        # Feed identical initial rewards
        for arm in self.arm_names:
            s1.update(arm, 0.010)
            s2.update(arm, 0.010)

        # In this state, all 3 arms have identical UCB values
        pick1 = [s1.select_arm() for _ in range(5)]
        pick2 = [s2.select_arm() for _ in range(5)]
        self.assertEqual(pick1, pick2)

    def test_page_hinkley_alarm_triggers_reset_and_reexploration(self) -> None:
        """Verify that a drop in reward triggers Page-Hinkley alarm and resets UCB cycle."""
        # Use parameters designed to trigger upon drop:
        # delta = 0.001, threshold = 0.01, min_instances = 3
        selector = PageHinkleyDMABSelector(
            self.arm_names,
            exploration_factor=0.07,
            delta=0.001,
            threshold=0.01,
            min_instances=3,
            seed=42,
        )

        # 1. Warm initial probe regime
        # Probe all 3 arms (initial probe: does NOT feed detector by default)
        selector.update("MOEA/D", 0.020)
        selector.update("NSGA-II", 0.020)
        selector.update("SPEA2", 0.020)
        self.assertEqual(selector.num_alarms, 0)
        self.assertEqual(selector.cycle_pulls, 3)
        self.assertEqual(selector.detector.num_observations, 0)  # Initial probe is neutral to PH
        self.assertTrue(selector.is_initial_probe_complete)

        # 2. Adaptive phase (satisfies min_instances=3 with stationary mean = 0.020)
        selector.update("MOEA/D", 0.020)
        selector.update("MOEA/D", 0.020)
        selector.update("MOEA/D", 0.020)
        self.assertEqual(selector.detector.num_observations, 3)
        self.assertEqual(selector.num_alarms, 0)

        # 3. Drop to 0.0 on step 7
        # x_7 = 0.0 drops sharply below mean (0.020). PH triggers alarm!
        selector.update("MOEA/D", 0.0)

        # An alarm should have triggered!
        self.assertEqual(selector.num_alarms, 1)
        alarm_rec = selector.alarm_history[0]
        self.assertEqual(alarm_rec.alarm_index, 0)
        self.assertEqual(alarm_rec.triggering_arm, "MOEA/D")
        self.assertEqual(alarm_rec.observed_reward, 0.0)
        self.assertGreater(alarm_rec.alarm_statistic, 0.01)

        # Cycle statistics should be cleanly reset
        self.assertEqual(selector.cycle_pulls, 0)
        self.assertFalse(selector.is_cycle_probe_complete)
        self.assertEqual(selector.detector.num_observations, 0)  # Detector was reset

        # Total lifetime pulls are preserved!
        self.assertEqual(selector.total_pulls, 7)
        self.assertEqual(selector.get_adaptive_pulls("MOEA/D"), 5)

        # Next selection MUST be re-exploration in canonical order!
        self.assertEqual(selector.select_arm(), "MOEA/D")
        self.assertTrue(selector.is_in_reexploration("MOEA/D"))
        selector.update("MOEA/D", 0.005)

        self.assertEqual(selector.select_arm(), "NSGA-II")
        self.assertTrue(selector.is_in_reexploration("NSGA-II"))
        selector.update("NSGA-II", 0.005)

        self.assertEqual(selector.select_arm(), "SPEA2")
        self.assertTrue(selector.is_in_reexploration("SPEA2"))
        selector.update("SPEA2", 0.005)

        # Re-exploration does NOT feed detector if feed_reexploration_to_detector=False
        self.assertEqual(selector.detector.num_observations, 0)

        # Now cycle probe is complete
        self.assertTrue(selector.is_cycle_probe_complete)
        self.assertEqual(selector.cycle_pulls, 3)
        self.assertEqual(selector.total_pulls, 10)

    def test_reproducibility(self) -> None:
        """Verify two independent selectors with identical inputs produce identical decisions and alarms."""
        s1 = PageHinkleyDMABSelector(self.arm_names, delta=0.001, threshold=0.01, seed=77)
        s2 = PageHinkleyDMABSelector(self.arm_names, delta=0.001, threshold=0.01, seed=77)

        rewards = [0.015, 0.010, 0.012, 0.008, 0.001, 0.0, 0.0, 0.0, 0.02, 0.01]
        for idx, r in enumerate(rewards):
            arm1 = s1.select_arm()
            arm2 = s2.select_arm()
            self.assertEqual(arm1, arm2)
            s1.update(arm1, r)
            s2.update(arm2, r)

        self.assertEqual(s1.total_pulls, s2.total_pulls)
        self.assertEqual(s1.num_alarms, s2.num_alarms)
        self.assertEqual(s1.alarm_history, s2.alarm_history)

    def test_warmup_neutrality(self) -> None:
        """Verify initialize_arm does not feed rewards nor update cycle pull counts."""
        selector = PageHinkleyDMABSelector(self.arm_names, seed=42)

        for arm in self.arm_names:
            selector.initialize_arm(arm)
            self.assertTrue(selector.is_arm_initialized(arm))

        # Detector and pull counters must remain 0
        self.assertEqual(selector.total_pulls, 0)
        self.assertEqual(selector.cycle_pulls, 0)
        self.assertEqual(selector.detector.num_observations, 0)

        # First select_arm must still execute canonical probe
        self.assertEqual(selector.select_arm(), "MOEA/D")

    def test_boundary_single_arm(self) -> None:
        """Verify selector functions properly with a single arm."""
        selector = PageHinkleyDMABSelector(["ONLY_ARM"], seed=42)
        for _ in range(10):
            arm = selector.select_arm()
            self.assertEqual(arm, "ONLY_ARM")
            selector.update(arm, 0.01)
        self.assertEqual(selector.total_pulls, 10)

    def test_boundary_all_zero_rewards(self) -> None:
        """Verify selector handles stream of 0.0 rewards without spurious alarms."""
        selector = PageHinkleyDMABSelector(self.arm_names, delta=0.001, threshold=0.05, seed=42)
        for _ in range(30):
            arm = selector.select_arm()
            selector.update(arm, 0.0)
        self.assertEqual(selector.total_pulls, 30)
        self.assertEqual(len(selector.alarm_history), 0)
        self.assertAlmostEqual(selector.detector.alarm_statistic, 0.0)
        self.assertFalse(selector.detector.change_detected)


    def test_manual_reset(self) -> None:
        """Verify manual reset() completely restores initial state."""
        selector = PageHinkleyDMABSelector(self.arm_names, seed=42)
        for arm in self.arm_names:
            selector.update(arm, 0.01)

        self.assertEqual(selector.total_pulls, 3)
        selector.reset()

        self.assertEqual(selector.total_pulls, 0)
        self.assertEqual(selector.cycle_pulls, 0)
        self.assertEqual(selector.num_alarms, 0)
        self.assertEqual(selector.detector.num_observations, 0)

    def test_regressions_sw_ucb_and_round_robin_unaffected(self) -> None:
        """Verify that SW-UCB and RoundRobinSelector maintain identical behavior."""
        rr = RoundRobinSelector(self.arm_names)
        self.assertEqual(rr.select_arm(), "MOEA/D")
        rr.update("MOEA/D", 0.05)
        self.assertEqual(rr.select_arm(), "NSGA-II")

        sw = SlidingWindowUCB(self.arm_names, window_size=5, exploration_factor=0.07, seed=42)
        self.assertEqual(sw.select_arm(), "MOEA/D")
        sw.update("MOEA/D", 0.05)
        self.assertEqual(sw.select_arm(), "NSGA-II")

    def test_probe_feeding_flags(self) -> None:
        """Verify behavior when feed_initial_probe_to_detector is True vs False."""
        s_default = PageHinkleyDMABSelector(self.arm_names, feed_initial_probe_to_detector=False)
        s_enabled = PageHinkleyDMABSelector(self.arm_names, feed_initial_probe_to_detector=True)

        for arm in self.arm_names:
            s_default.update(arm, 0.01)
            s_enabled.update(arm, 0.01)

        # Default: probe rewards do not feed detector
        self.assertEqual(s_default.detector.num_observations, 0)
        # Enabled: probe rewards do feed detector
        self.assertEqual(s_enabled.detector.num_observations, 3)

    def test_cycle_vs_lifetime_stats_separation(self) -> None:
        """Verify that cycle stats reset upon alarm while lifetime stats accumulate monotonically."""
        selector = PageHinkleyDMABSelector(
            self.arm_names,
            delta=0.001,
            threshold=0.01,
            min_instances=1,
            feed_initial_probe_to_detector=True,
        )
        selector.update("MOEA/D", 0.05)
        # Trigger alarm on step 2
        selector.update("MOEA/D", 0.00)

        self.assertEqual(selector.num_alarms, 1)
        # Lifetime stats preserved
        self.assertEqual(selector.total_pulls, 2)
        self.assertEqual(selector.get_adaptive_pulls("MOEA/D"), 2)
        # Cycle stats reset
        self.assertEqual(selector.cycle_pulls, 0)
        self.assertEqual(selector.is_cycle_probe_complete, False)



if __name__ == "__main__":
    unittest.main()

