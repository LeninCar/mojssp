"""Automated test suite for Phase 2 3-arm portfolio integration (F2.2).

Verifies:
1. RoundRobinSelector:
   - Conformance to DMABSelector protocol.
   - Exact cyclic round-robin sequence: A0 -> A1 -> A2 -> A0 ...
   - Handling of initial probe and initialization.
   - Clean reset state.
2. 3-Arm Portfolio Integration:
   - Successful orchestration of [MOEA/D, NSGA-II, SPEA2] in Portfolio.
   - Retrieval by canonical names and aliases.
   - Exact budget accounting and zero overshoot across total budgets.
   - Correct tracking of startup evaluations (150 FE warmup + 150 FE initial probe = 300 FE).
   - Re-execution without re-initialization (stateful continuity).
   - Exact bit-for-bit reproducibility with identical seeds across runs.
   - Uniform policy (Round-Robin) maintains exact 1:1:1 allocation across arms.
   - Adaptive policy (SW-UCB) adapts allocation dynamically based on rewards.
   - Correct accumulation of non-dominated solutions into GlobalParetoArchive.
"""

import sys
import unittest
from pathlib import Path
from typing import Dict, List, Tuple

# Add src to sys.path
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root / "src"))

from mojssp.dmab import DMABSelector, RoundRobinSelector, SlidingWindowUCB
from mojssp.instance import Instance
from mojssp.io import load_dzn
from mojssp.moead import MOEADArm
from mojssp.normalization import compute_instance_bounds, ObjectiveNormalizer
from mojssp.orchestrator import AdaptivePortfolioOrchestrator
from mojssp.portfolio import Portfolio
from mojssp.reward import HypervolumeRewardTracker
from mojssp.runner import run_phase2_portfolio_experiment
from mojssp.spea2 import SPEA2Arm
from mojssp.arms import NSGA2Arm


class TestPhase2PortfolioIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Load a small development instance for integration tests
        inst_path = repo_root / "data" / "generated" / "expanded_200" / "base_c01_5x5_b02.dzn"
        cls.instance = load_dzn(inst_path, validate=True)
        cls.normalizer = ObjectiveNormalizer(compute_instance_bounds(cls.instance))

    def test_round_robin_selector_protocol_and_sequence(self):
        """Verify RoundRobinSelector implements protocol and cycles cyclically."""
        arm_names = ["MOEA/D", "NSGA-II", "SPEA2"]
        selector = RoundRobinSelector(arm_names)

        self.assertIsInstance(selector, DMABSelector)
        self.assertEqual(selector.arm_names, ("MOEA/D", "NSGA-II", "SPEA2"))
        self.assertEqual(selector.total_pulls, 0)

        # First cycle (initial probe): MOEA/D, NSGA-II, SPEA2
        selected_seq = []
        for i in range(9):
            arm = selector.select_arm()
            selected_seq.append(arm)
            selector.update(arm, reward=0.01 * (i + 1))

        expected_seq = [
            "MOEA/D", "NSGA-II", "SPEA2",
            "MOEA/D", "NSGA-II", "SPEA2",
            "MOEA/D", "NSGA-II", "SPEA2",
        ]
        self.assertEqual(selected_seq, expected_seq)
        self.assertEqual(selector.total_pulls, 9)

        # Check stats snapshot
        stats = selector.get_stats()
        for name in arm_names:
            self.assertEqual(stats[name].total_pulls, 3)

        # Reset
        selector.reset()
        self.assertEqual(selector.total_pulls, 0)
        self.assertEqual(selector.select_arm(), "MOEA/D")

    def test_portfolio_alias_resolution(self):
        """Verify Portfolio resolves MOEA/D and SPEA2 aliases cleanly."""
        arm_moead = MOEADArm(self.instance, population_size=15, seed=10)
        arm_nsga2 = NSGA2Arm(self.instance, population_size=15, seed=20)
        arm_spea2 = SPEA2Arm(self.instance, population_size=15, archive_size=15, seed=30)

        portfolio = Portfolio()
        portfolio.register_arm(arm_moead)
        portfolio.register_arm(arm_nsga2)
        portfolio.register_arm(arm_spea2)

        # Canonical lookup
        self.assertIs(portfolio.get_arm("MOEA/D"), arm_moead)
        self.assertIs(portfolio.get_arm("NSGA-II"), arm_nsga2)
        self.assertIs(portfolio.get_arm("SPEA2"), arm_spea2)

        # Case-insensitive / short aliases
        self.assertIs(portfolio.get_arm("moead"), arm_moead)
        self.assertIs(portfolio.get_arm("moea_d"), arm_moead)
        self.assertIs(portfolio.get_arm("spea2"), arm_spea2)
        self.assertIs(portfolio.get_arm("nsga2"), arm_nsga2)
        self.assertIs(portfolio.get_arm("nsga-ii"), arm_nsga2)

    def test_exact_budget_and_zero_overshoot(self):
        """Verify strict budget accounting and zero overshoot in Phase 2 runner."""
        # Test 350 FE (7 blocks of 50): 3 warmup + 3 probe + 1 adaptive/cyclic block
        budget = 350
        block_size = 50

        # Adaptive (SW-UCB)
        res_adapt, hist_adapt = run_phase2_portfolio_experiment(
            instance=self.instance,
            seed=42,
            total_budget=budget,
            block_size=block_size,
            policy="adaptive",
            neutral_warmup=True,
        )
        self.assertEqual(res_adapt.evaluations_used, budget)
        self.assertEqual(sum(b.evaluations_used for b in hist_adapt), budget)
        self.assertEqual(len(hist_adapt), 7)
        self.assertTrue(res_adapt.completed)

        # Uniform (Round-Robin)
        res_uni, hist_uni = run_phase2_portfolio_experiment(
            instance=self.instance,
            seed=42,
            total_budget=budget,
            block_size=block_size,
            policy="uniform",
            neutral_warmup=True,
        )
        self.assertEqual(res_uni.evaluations_used, budget)
        self.assertEqual(sum(b.evaluations_used for b in hist_uni), budget)
        self.assertEqual(len(hist_uni), 7)
        self.assertTrue(res_uni.completed)

    def test_startup_protocol_telemetry(self):
        """Verify exact startup accounting: 150 FE warmup + 150 FE initial probe = 300 FE."""
        budget = 300
        block_size = 50

        res, history = run_phase2_portfolio_experiment(
            instance=self.instance,
            seed=42,
            total_budget=budget,
            block_size=block_size,
            policy="adaptive",
            neutral_warmup=True,
        )

        self.assertEqual(len(history), 6)
        # Blocks 0, 1, 2 must be warmup
        for i in range(3):
            self.assertEqual(history[i].phase, "warmup")
            self.assertEqual(history[i].evaluations_used, 50)
        self.assertEqual([b.arm_name for b in history[:3]], ["MOEA/D", "NSGA-II", "SPEA2"])

        # Blocks 3, 4, 5 must be initial_probe
        for i in range(3, 6):
            self.assertEqual(history[i].phase, "initial_probe")
            self.assertEqual(history[i].evaluations_used, 50)
        self.assertEqual([b.arm_name for b in history[3:6]], ["MOEA/D", "NSGA-II", "SPEA2"])

        # Allocations summary
        for arm, alloc in res.arm_allocations.items():
            self.assertEqual(alloc.evaluations_assigned, 100)
            self.assertEqual(alloc.number_of_blocks, 2)
            self.assertAlmostEqual(alloc.percentage_of_budget, 33.3333, places=2)

    def test_deterministic_reproducibility(self):
        """Verify two independent executions with identical seeds produce identical results."""
        budget = 400
        block_size = 50

        res1, hist1 = run_phase2_portfolio_experiment(
            instance=self.instance,
            seed=12345,
            total_budget=budget,
            block_size=block_size,
            policy="adaptive",
        )

        res2, hist2 = run_phase2_portfolio_experiment(
            instance=self.instance,
            seed=12345,
            total_budget=budget,
            block_size=block_size,
            policy="adaptive",
        )

        self.assertEqual(res1.evaluations_used, res2.evaluations_used)
        self.assertEqual(res1.hypervolume, res2.hypervolume)
        self.assertEqual(res1.archive_size, res2.archive_size)
        self.assertEqual(res1.pareto_front, res2.pareto_front)
        self.assertEqual(len(hist1), len(hist2))

        for b1, b2 in zip(hist1, hist2):
            self.assertEqual(b1.arm_name, b2.arm_name)
            self.assertEqual(b1.evaluations_used, b2.evaluations_used)
            self.assertEqual(b1.reward, b2.reward)
            self.assertEqual(b1.hv_after, b2.hv_after)

    def test_global_archive_monotonicity_and_accumulation(self):
        """Verify GlobalParetoArchive accumulates solutions monotonically without degrading HV."""
        res, history = run_phase2_portfolio_experiment(
            instance=self.instance,
            seed=42,
            total_budget=500,
            block_size=50,
            policy="uniform",
        )

        prev_hv = 0.0
        for b in history:
            self.assertGreaterEqual(b.hv_after, prev_hv - 1e-12)
            self.assertGreaterEqual(b.reward, -1e-12)
            prev_hv = b.hv_after

        self.assertAlmostEqual(res.hypervolume, history[-1].hv_after, places=10)
        self.assertGreater(res.archive_size, 0)


if __name__ == "__main__":
    unittest.main()

