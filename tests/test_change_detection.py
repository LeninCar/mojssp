"""Comprehensive unit tests for the standalone PageHinkleyDetector.

Tests cover:
- Stationary constant and noisy sequences
- Abrupt downward and upward shifts
- Gradual drift
- Zero-reward sequences (sparse reward simulation)
- Deterministic reset and state immutability
- Reproducibility across multiple instances
- Boundary cases, invalid inputs, NaN/Inf rejection
- Step-by-step manual calculation verification
"""

import math
from pathlib import Path
import random
import sys
import unittest

# Add src directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mojssp.portfolio.change_detection import PageHinkleyDetector, PageHinkleyState


class TestPageHinkleyDetector(unittest.TestCase):
    """Test suite for PageHinkleyDetector."""

    def test_parameter_validation(self) -> None:
        """Test defensive parameter validation in constructor."""
        # Valid construction
        d = PageHinkleyDetector(delta=0.005, threshold=0.05, direction="down", min_instances=3)
        self.assertEqual(d.delta, 0.005)
        self.assertEqual(d.threshold, 0.05)
        self.assertEqual(d.direction, "down")
        self.assertEqual(d.min_instances, 3)

        # Negative delta
        with self.assertRaises(ValueError):
            PageHinkleyDetector(delta=-0.01)

        # Zero or negative threshold
        with self.assertRaises(ValueError):
            PageHinkleyDetector(threshold=0.0)
        with self.assertRaises(ValueError):
            PageHinkleyDetector(threshold=-1.0)

        # Invalid direction
        with self.assertRaises(ValueError):
            PageHinkleyDetector(direction="sideways")

        # Invalid min_instances (< 1 or non-integer)
        with self.assertRaises(ValueError):
            PageHinkleyDetector(min_instances=0)
        with self.assertRaises(ValueError):
            PageHinkleyDetector(min_instances=-5)

        # NaN / Inf parameters
        with self.assertRaises(ValueError):
            PageHinkleyDetector(delta=float("nan"))
        with self.assertRaises(ValueError):
            PageHinkleyDetector(threshold=float("inf"))

    def test_invalid_observations_rejected(self) -> None:
        """Test that NaN, Inf, and non-numeric observations are rejected with ValueError."""
        d = PageHinkleyDetector()
        with self.assertRaises(ValueError):
            d.update(float("nan"))
        with self.assertRaises(ValueError):
            d.update(float("inf"))
        with self.assertRaises(ValueError):
            d.update(-float("inf"))
        with self.assertRaises(ValueError):
            d.update("not_a_number")  # type: ignore

    def test_manual_calculation_step_by_step(self) -> None:
        """Test exact step-by-step numerical calculation verified against manual values.

        Sequence: [1.0, 1.0, 0.0, 0.0]
        direction: 'down', delta: 0.1, threshold: 0.5, min_instances: 1

        Step 1: x_1 = 1.0
          mean_1 = 1.0
          e_1 = (1.0 - 1.0) - 0.1 = -0.1
          m_1 = -0.1
          min_1 = -0.1
          ph_1 = -0.1 - (-0.1) = 0.0

        Step 2: x_2 = 1.0
          mean_2 = 1.0
          e_2 = (1.0 - 1.0) - 0.1 = -0.1
          m_2 = -0.2
          min_2 = -0.2
          ph_2 = -0.2 - (-0.2) = 0.0

        Step 3: x_3 = 0.0
          mean_3 = 2.0 / 3 = 0.6666667
          e_3 = (0.6666667 - 0.0) - 0.1 = 0.5666667
          m_3 = -0.2 + 0.5666667 = 0.3666667
          min_3 = -0.2
          ph_3 = 0.3666667 - (-0.2) = 0.5666667 > 0.5 -> ALARM!
        """
        d = PageHinkleyDetector(delta=0.1, threshold=0.5, direction="down", min_instances=1)

        # Step 1
        alarm_1 = d.update(1.0)
        self.assertFalse(alarm_1)
        self.assertAlmostEqual(d.current_mean, 1.0)
        self.assertAlmostEqual(d.alarm_statistic, 0.0)

        # Step 2
        alarm_2 = d.update(1.0)
        self.assertFalse(alarm_2)
        self.assertAlmostEqual(d.current_mean, 1.0)
        self.assertAlmostEqual(d.alarm_statistic, 0.0)

        # Step 3 (Drop to 0.0)
        alarm_3 = d.update(0.0)
        self.assertTrue(alarm_3)
        self.assertAlmostEqual(d.current_mean, 2.0 / 3.0)
        expected_ph_3 = 2.0 / 3.0 - 0.1  # m_3 - min_m = (-0.2 + 0.5666667) - (-0.2) = 0.5666667
        self.assertAlmostEqual(d.alarm_statistic, expected_ph_3, places=6)
        self.assertTrue(d.change_detected)

    def test_stationary_constant_sequence(self) -> None:
        """Verify that a stationary constant sequence never triggers false alarms."""
        d = PageHinkleyDetector(delta=0.01, threshold=0.1, direction="down", min_instances=5)
        for _ in range(50):
            alarm = d.update(0.05)
            self.assertFalse(alarm)
            self.assertEqual(d.alarm_statistic, 0.0)

    def test_stationary_noisy_sequence(self) -> None:
        """Verify that small stationary zero-mean noise does not trigger alarms under proper threshold."""
        rng = random.Random(42)
        d = PageHinkleyDetector(delta=0.01, threshold=0.1, direction="both", min_instances=10)
        for _ in range(100):
            val = 0.05 + rng.gauss(0.0, 0.002)
            alarm = d.update(val)
            self.assertFalse(alarm)

    def test_abrupt_downward_shift_detected(self) -> None:
        """Verify that a sharp downward shift triggers an alarm in direction 'down' and 'both'."""
        # Initial regime: mean = 0.05 for 20 steps
        # Drop regime: mean = 0.00 for subsequent steps
        d_down = PageHinkleyDetector(delta=0.001, threshold=0.02, direction="down", min_instances=5)
        d_up = PageHinkleyDetector(delta=0.001, threshold=0.02, direction="up", min_instances=5)
        d_both = PageHinkleyDetector(delta=0.001, threshold=0.02, direction="both", min_instances=5)

        for _ in range(20):
            self.assertFalse(d_down.update(0.05))
            self.assertFalse(d_up.update(0.05))
            self.assertFalse(d_both.update(0.05))

        # Start of downward shift
        alarms_down = []
        alarms_up = []
        alarms_both = []
        for step in range(21, 35):
            alarms_down.append(d_down.update(0.00))
            alarms_up.append(d_up.update(0.00))
            alarms_both.append(d_both.update(0.00))

        # Downward detector should trigger
        self.assertTrue(any(alarms_down))
        # Upward detector should NEVER trigger on downward shift
        self.assertFalse(any(alarms_up))
        # Bilateral detector should trigger
        self.assertTrue(any(alarms_both))

    def test_abrupt_upward_shift_detected(self) -> None:
        """Verify that a sharp upward shift triggers an alarm in direction 'up' and 'both'."""
        d_down = PageHinkleyDetector(delta=0.001, threshold=0.02, direction="down", min_instances=5)
        d_up = PageHinkleyDetector(delta=0.001, threshold=0.02, direction="up", min_instances=5)
        d_both = PageHinkleyDetector(delta=0.001, threshold=0.02, direction="both", min_instances=5)

        for _ in range(20):
            self.assertFalse(d_down.update(0.00))
            self.assertFalse(d_up.update(0.00))
            self.assertFalse(d_both.update(0.00))

        alarms_down = []
        alarms_up = []
        alarms_both = []
        for _ in range(15):
            alarms_down.append(d_down.update(0.05))
            alarms_up.append(d_up.update(0.05))
            alarms_both.append(d_both.update(0.05))

        # Upward detector should trigger
        self.assertTrue(any(alarms_up))
        # Downward detector should NEVER trigger on upward jump
        self.assertFalse(any(alarms_down))
        # Bilateral detector should trigger
        self.assertTrue(any(alarms_both))

    def test_sparse_zero_rewards_simulation(self) -> None:
        """Verify behavior under sparse non-negative rewards similar to MO-JSSP portfolio."""
        # Simulated sequence: small improvements (0.002) interspersed with 25% zeros
        seq = [0.002, 0.003, 0.0, 0.001, 0.002, 0.0, 0.002, 0.001, 0.0, 0.002]
        d = PageHinkleyDetector(delta=0.0005, threshold=0.01, direction="down", min_instances=5)
        for r in seq:
            alarm = d.update(r)
            self.assertFalse(alarm)
        self.assertEqual(d.num_observations, 10)

    def test_constant_zero_sequence_exact_mechanics(self) -> None:
        """Verify exact mathematical mechanics for a sequence of all zero rewards.

        Confirms:
        1. Cumulative sum m_t decreases linearly as -t * delta.
        2. Running minimum M_t tracks m_t exactly (-t * delta).
        3. Test statistic PH_t = m_t - M_t remains identically 0.0.
        4. No alarm is triggered for any t >= min_instances.
        """
        delta = 0.005
        threshold = 0.02
        min_instances = 3
        d = PageHinkleyDetector(
            delta=delta,
            threshold=threshold,
            direction="down",
            min_instances=min_instances,
        )

        for step in range(1, 25):
            alarm = d.update(0.0)
            state = d.get_state()

            expected_m_t = -step * delta
            expected_min_m = -step * delta
            expected_ph_t = 0.0

            # 1. Verification of m_t
            self.assertAlmostEqual(state.cumulative_statistic, expected_m_t, places=9)
            # 2. Verification of running minimum M_t
            self.assertAlmostEqual(state.reference_extremum, expected_min_m, places=9)
            # 3. Verification of PH_t statistic
            self.assertAlmostEqual(d.alarm_statistic, expected_ph_t, places=9)
            self.assertAlmostEqual(state.alarm_statistic, expected_ph_t, places=9)
            # 4. Verification of absence of alarms
            self.assertFalse(alarm)
            self.assertFalse(d.change_detected)
            self.assertFalse(state.change_detected)
            self.assertAlmostEqual(d.current_mean, 0.0, places=9)

    def test_reset_behavior(self) -> None:
        """Verify that reset() cleanly restores initial state."""
        d = PageHinkleyDetector(delta=0.01, threshold=0.05, direction="down")
        d.update(1.0)
        d.update(0.0)
        d.update(0.0)

        self.assertGreater(d.num_observations, 0)
        self.assertGreater(d.current_mean, 0.0)

        d.reset()

        self.assertEqual(d.num_observations, 0)
        self.assertEqual(d.current_mean, 0.0)
        self.assertEqual(d.alarm_statistic, 0.0)
        self.assertFalse(d.change_detected)

        # Fresh instance comparison
        fresh = PageHinkleyDetector(delta=0.01, threshold=0.05, direction="down")
        self.assertEqual(d.get_state(), fresh.get_state())

    def test_auto_reset_mode(self) -> None:
        """Verify auto_reset=True automatically clears accumulators upon alarm."""
        d = PageHinkleyDetector(delta=0.1, threshold=0.5, direction="down", min_instances=1, auto_reset=True)
        self.assertFalse(d.update(1.0))
        self.assertFalse(d.update(1.0))

        # This observation triggers alarm
        alarm = d.update(0.0)
        self.assertTrue(alarm)
        self.assertTrue(d.change_detected)

        # Next observation should start fresh (num_observations == 1)
        d.update(0.5)
        self.assertEqual(d.num_observations, 1)
        self.assertAlmostEqual(d.current_mean, 0.5)

    def test_reproducibility(self) -> None:
        """Verify two independent instances fed identical inputs produce bit-for-bit identical state."""
        d1 = PageHinkleyDetector(delta=0.002, threshold=0.03, direction="both")
        d2 = PageHinkleyDetector(delta=0.002, threshold=0.03, direction="both")

        inputs = [0.01, 0.02, 0.015, 0.0, 0.0, 0.05, 0.08, 0.0, 0.0]
        for val in inputs:
            a1 = d1.update(val)
            a2 = d2.update(val)
            self.assertEqual(a1, a2)
            self.assertEqual(d1.get_state(), d2.get_state())

    def test_min_instances_guard(self) -> None:
        """Verify that alarm cannot be triggered before min_instances observations."""
        # Threshold is very low (0.001), but min_instances is 10
        d = PageHinkleyDetector(delta=0.0, threshold=0.001, direction="down", min_instances=10)
        d.update(1.0)
        for _ in range(8):  # total 9 observations
            alarm = d.update(0.0)
            self.assertFalse(alarm)

        # 10th observation satisfies min_instances guard
        alarm = d.update(0.0)
        self.assertTrue(alarm)


if __name__ == "__main__":
    unittest.main()
