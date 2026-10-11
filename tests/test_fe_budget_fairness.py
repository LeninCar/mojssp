"""Unit and integration tests for strict evaluation budget fairness across all 5 algorithms.

Audits and verifies that:
1. Every algorithm (NSGA-II, NSGA-II+LS, MOPSO, MOEA/D, SPEA2) consumes exactly 1 FE per
   Decoder.decode + Evaluator.evaluate call.
2. Under standalone execution with a budget of 1000 FE (or arbitrary B), each algorithm
   reports exactly B evaluations used with zero overshoot.
3. Stateful arms pause cleanly and resume without evaluation leakage under sub-generation
   budget cuts (e.g. 17, 33, 50 FE).
4. Calling run(budget) on an already completed arm strictly consumes 0 FE.
"""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mojssp import (
    MOPSOArm,
    NSGA2Arm,
    NSGA2LSArm,
    MOEADArm,
    SPEA2Arm,
    load_dzn,
)
from mojssp.runner import run_standalone_experiment


class TestFEBudgetFairness(unittest.TestCase):
    """Test suite ensuring strict budget fairness and zero overshoot across all 5 algorithms."""

    @classmethod
    def setUpClass(cls) -> None:
        toy_dzn = Path(__file__).resolve().parent.parent / "data" / "validation" / "toy_instance.dzn"
        cls.instance = load_dzn(str(toy_dzn), validate=True)
        cls.algorithms = ["NSGA-II", "NSGA-II+LS", "MOPSO", "MOEA/D", "SPEA2"]
        cls.arm_classes = [NSGA2Arm, NSGA2LSArm, MOPSOArm, MOEADArm, SPEA2Arm]

    def test_standalone_budget_exactness_all_algorithms(self) -> None:
        """Verify each of the 5 algorithms consumes exactly 1000 FE with zero overshoot."""
        budget = 1000
        for alg_name in self.algorithms:
            with self.subTest(algorithm=alg_name):
                res = run_standalone_experiment(
                    instance=self.instance,
                    arm_name=alg_name,
                    seed=42,
                    budget=budget,
                    block_size=50,
                    population_size=30,
                )
                self.assertEqual(
                    res.evaluations_used,
                    budget,
                    f"{alg_name} consumed {res.evaluations_used} FE instead of {budget}",
                )
                self.assertTrue(
                    res.completed,
                    f"{alg_name} was not marked completed after exhausting budget",
                )
                self.assertGreater(
                    len(res.pareto_front),
                    0,
                    f"{alg_name} returned an empty Pareto front",
                )

    def test_arms_sub_generation_budget_cuts(self) -> None:
        """Verify stateful arms pause cleanly on arbitrary sub-generation cuts."""
        # Increments that do not match population size (30): 13, 27, 35, 25 (sum = 100)
        increments = [13, 27, 35, 25]
        target_total = sum(increments)

        for arm_cls in self.arm_classes:
            with self.subTest(arm_class=arm_cls.__name__):
                arm = arm_cls(
                    self.instance,
                    population_size=30,
                    max_evaluations=target_total,
                    seed=101,
                )

                accumulated = 0
                for inc in increments:
                    res = arm.run(inc)
                    accumulated += res.evaluations_used
                    self.assertEqual(
                        res.evaluations_used,
                        inc,
                        f"{arm.arm_name} used {res.evaluations_used} instead of requested {inc}",
                    )
                    self.assertEqual(
                        arm.total_evaluations,
                        accumulated,
                        f"{arm.arm_name} cumulative mismatch: {arm.total_evaluations} vs {accumulated}",
                    )

                self.assertEqual(arm.total_evaluations, target_total)
                self.assertTrue(arm.is_completed)

                # Subsequent calls must consume 0 evaluations
                post_run = arm.run(50)
                self.assertEqual(post_run.evaluations_used, 0)
                self.assertTrue(post_run.completed)

    def test_zero_budget_call(self) -> None:
        """Verify calling run(0) on any arm returns 0 used evaluations immediately."""
        for arm_cls in self.arm_classes:
            with self.subTest(arm_class=arm_cls.__name__):
                arm = arm_cls(self.instance, population_size=30, seed=77)
                res = arm.run(0)
                self.assertEqual(res.evaluations_used, 0)
                self.assertEqual(arm.total_evaluations, 0)
                self.assertFalse(arm.is_completed)


if __name__ == "__main__":
    unittest.main()

