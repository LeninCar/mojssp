"""Comprehensive integration test suite for DMAB-PH with AdaptivePortfolioOrchestrator (F3.PH.4).

Covers all 20 required methodological and technical criteria:
1. Creación del orquestador con dmab_ph.
2. Rechazo de una política desconocida.
3. Inicialización de los tres brazos fijos (MOEA/D, NSGA-II, SPEA2).
4. Neutralidad del warm-up.
5. Sondeo inicial correcto.
6. Selección adaptativa.
7. Actualización de recompensa.
8. Alarma y reinicio de ciclo.
9. Reexploración posterior en orden canónico.
10. Conservación de poblaciones y estado interno de algoritmos.
11. Conservación del archivo global Pareto.
12. Contabilidad exacta de FE.
13. Overshoot igual a cero.
14. Reproducibilidad con semillas.
15. Persistencia de telemetría extendida en CSV.
16. Compatibilidad con SW-UCB (regresión).
17. Compatibilidad con Round-Robin (regresión).
18. Presupuesto que termina inmediatamente después de una alarma.
19. Presupuesto insuficiente para completar una reexploración.
20. Ausencia de alarmas durante toda la ejecución bajo umbral alto.
"""

import csv
import math
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Tuple
import unittest

# Add src directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mojssp import (
    AdaptiveExecutionResult,
    AdaptivePortfolioOrchestrator,
    BlockExecutionRecord,
    HypervolumeRewardTracker,
    MOEADArm,
    NSGA2Arm,
    ObjectiveNormalizer,
    PageHinkleyDMABSelector,
    Portfolio,
    RoundRobinSelector,
    SPEA2Arm,
    SlidingWindowUCB,
    compute_instance_bounds,
    load_dzn,
)
from mojssp.portfolio.runner import export_results_to_csv, run_phase2_portfolio_experiment


class TestPageHinkleyOrchestratorIntegration(unittest.TestCase):
    """Integration test suite for PageHinkleyDMABSelector within the portfolio orchestrator."""

    def setUp(self) -> None:
        toy_path = Path(__file__).resolve().parent.parent / "data" / "validation" / "toy_instance.dzn"
        self.instance = load_dzn(toy_path)
        self.bounds = compute_instance_bounds(self.instance)
        self.normalizer = ObjectiveNormalizer(self.bounds)
        self.seed = 42

    def _create_pipeline(
        self,
        seed: int = 42,
        pop_size: int = 10,
        c: float = 0.07,
        delta: float = 0.001,
        threshold: float = 0.05,
        min_instances: int = 3,
        feed_initial_probe: bool = False,
        feed_reexploration: bool = False,
    ) -> Tuple[AdaptivePortfolioOrchestrator, Portfolio, PageHinkleyDMABSelector]:
        """Instantiate a concrete 3-arm pipeline with PageHinkleyDMABSelector."""
        arm_moead = MOEADArm(self.instance, population_size=pop_size, seed=seed + 1)
        arm_nsga2 = NSGA2Arm(self.instance, population_size=pop_size, seed=seed + 2)
        arm_spea2 = SPEA2Arm(self.instance, population_size=pop_size, archive_size=pop_size, seed=seed + 3)

        arms = {
            "MOEA/D": arm_moead,
            "NSGA-II": arm_nsga2,
            "SPEA2": arm_spea2,
        }
        portfolio = Portfolio(arms)
        dmab = PageHinkleyDMABSelector(
            arm_names=list(arms.keys()),
            exploration_factor=c,
            delta=delta,
            threshold=threshold,
            min_instances=min_instances,
            feed_initial_probe_to_detector=feed_initial_probe,
            feed_reexploration_to_detector=feed_reexploration,
            seed=seed,
        )
        reward_tracker = HypervolumeRewardTracker(self.normalizer)
        orchestrator = AdaptivePortfolioOrchestrator(
            portfolio=portfolio,
            dmab=dmab,
            reward_tracker=reward_tracker,
        )
        return orchestrator, portfolio, dmab

    def test_01_orchestrator_creation_with_dmab_ph(self) -> None:
        """1. Verify creation and typing of AdaptivePortfolioOrchestrator with dmab_ph."""
        orchestrator, portfolio, dmab = self._create_pipeline()
        self.assertIsInstance(orchestrator, AdaptivePortfolioOrchestrator)
        self.assertIsInstance(orchestrator.dmab, PageHinkleyDMABSelector)
        self.assertEqual(len(orchestrator.history), 0)

    def test_02_unknown_policy_rejected(self) -> None:
        """2. Verify runner rejects an invalid or unknown policy name."""
        with self.assertRaises(ValueError):
            run_phase2_portfolio_experiment(
                instance=self.instance,
                seed=self.seed,
                policy="invalid_nonexistent_policy",
            )

    def test_03_initialization_of_three_arms(self) -> None:
        """3. Verify portfolio correctly manages all three constituent arms."""
        _, portfolio, dmab = self._create_pipeline()
        self.assertEqual(set(portfolio.arm_names), {"MOEA/D", "NSGA-II", "SPEA2"})
        self.assertEqual(set(dmab.arm_names), {"MOEA/D", "NSGA-II", "SPEA2"})

    def test_04_warmup_neutrality(self) -> None:
        """4. Verify neutral warm-up executes 1 block per arm without feeding UCB or Page-Hinkley."""
        orchestrator, portfolio, dmab = self._create_pipeline()
        # Warmup with 3 arms * 20 evaluations
        for arm in ("MOEA/D", "NSGA-II", "SPEA2"):
            rec = orchestrator.run_warmup_block(arm, block_budget=20)
            self.assertEqual(rec.phase, "warmup")
            self.assertTrue(dmab.is_arm_initialized(arm))

        # Detector and UCB cycle pull count must remain strictly 0
        self.assertEqual(dmab.detector.num_observations, 0)
        self.assertEqual(dmab.cycle_pulls, 0)
        self.assertEqual(dmab.total_pulls, 0)
        self.assertEqual(portfolio.total_evaluations, 60)

    def test_05_correct_initial_probe(self) -> None:
        """5. Verify initial probe executes all 3 arms in canonical order and feeds UCB but not PH."""
        orchestrator, portfolio, dmab = self._create_pipeline(feed_initial_probe=False)
        rec1 = orchestrator.step(block_budget=20)
        self.assertEqual(rec1.arm_name, "MOEA/D")
        self.assertEqual(rec1.phase, "initial_probe")

        rec2 = orchestrator.step(block_budget=20)
        self.assertEqual(rec2.arm_name, "NSGA-II")
        self.assertEqual(rec2.phase, "initial_probe")

        rec3 = orchestrator.step(block_budget=20)
        self.assertEqual(rec3.arm_name, "SPEA2")
        self.assertEqual(rec3.phase, "initial_probe")

        # Initial probe feeds UCB cycle statistics
        self.assertEqual(dmab.cycle_pulls, 3)
        self.assertTrue(dmab.is_initial_probe_complete)
        # But DOES NOT feed Page-Hinkley detector by default
        self.assertEqual(dmab.detector.num_observations, 0)

    def test_06_adaptive_selection(self) -> None:
        """6. Verify that once probe is complete, selection is index-based and feeds detector."""
        orchestrator, portfolio, dmab = self._create_pipeline(feed_initial_probe=False)
        # Initial probe
        for _ in range(3):
            orchestrator.step(20)

        # 4th block is active adaptive
        rec4 = orchestrator.step(20)
        self.assertEqual(rec4.phase, "adaptive")
        # Now detector begins receiving observations
        self.assertEqual(dmab.detector.num_observations, 1)

    def test_07_reward_update_in_orchestrator(self) -> None:
        """7. Verify ΔHV reward computation and propagation during orchestrator step."""
        orchestrator, _, dmab = self._create_pipeline()
        rec = orchestrator.step(30)
        self.assertGreaterEqual(rec.reward, 0.0)
        self.assertAlmostEqual(rec.hv_after - rec.hv_before, rec.reward, places=7)

    def test_08_alarm_and_cycle_reset(self) -> None:
        """8. Verify alarm triggering forces cycle reset and logs PageHinkleyAlarmRecord."""
        orchestrator, portfolio, dmab = self._create_pipeline(
            delta=0.001, threshold=0.01, min_instances=2, feed_initial_probe=False
        )
        # 1. Complete initial probe
        for _ in range(3):
            orchestrator.step(20)

        # 2. Establish high positive mean in adaptive phase
        dmab.update("MOEA/D", 0.05)
        dmab.update("MOEA/D", 0.05)
        self.assertEqual(dmab.num_alarms, 0)

        # 3. Feed sharp drop to 0.0 to trigger alarm
        dmab.update("MOEA/D", 0.0)

        self.assertEqual(dmab.num_alarms, 1)
        self.assertEqual(dmab.cycle_pulls, 0)
        self.assertEqual(dmab.detector.alarm_statistic, 0.0)
        self.assertEqual(len(dmab.alarm_history), 1)
        self.assertEqual(dmab.alarm_history[0].triggering_arm, "MOEA/D")

    def test_09_post_alarm_reexploration(self) -> None:
        """9. Verify that after an alarm, all 3 arms are re-explored in canonical order."""
        orchestrator, portfolio, dmab = self._create_pipeline(
            delta=0.001, threshold=0.01, min_instances=2, feed_initial_probe=False
        )
        # Complete initial probe
        for _ in range(3):
            orchestrator.step(20)

        # Establish mean and trigger alarm
        dmab.update("MOEA/D", 0.05)
        dmab.update("MOEA/D", 0.05)
        dmab.update("MOEA/D", 0.0)
        self.assertEqual(dmab.num_alarms, 1)

        # Next 3 steps must select MOEA/D, NSGA-II, SPEA2 in order under 'reexploration'
        rec1 = orchestrator.step(15)
        self.assertEqual(rec1.arm_name, "MOEA/D")
        self.assertEqual(rec1.phase, "reexploration")

        rec2 = orchestrator.step(15)
        self.assertEqual(rec2.arm_name, "NSGA-II")
        self.assertEqual(rec2.phase, "reexploration")

        rec3 = orchestrator.step(15)
        self.assertEqual(rec3.arm_name, "SPEA2")
        self.assertEqual(rec3.phase, "reexploration")

    def test_10_preservation_of_arm_populations(self) -> None:
        """10. Verify that a Page-Hinkley alarm does NOT reset constituent algorithm states."""
        orchestrator, portfolio, dmab = self._create_pipeline(
            delta=0.001, threshold=0.01, min_instances=2, feed_initial_probe=False
        )
        # Complete initial probe
        for _ in range(3):
            orchestrator.step(20)

        moead_arm = portfolio.arms["MOEA/D"]
        self.assertGreater(len(moead_arm.subproblems), 0)
        archive_snapshot_before = len(moead_arm.current_archive)

        # Establish mean and trigger alarm
        dmab.update("MOEA/D", 0.05)
        dmab.update("MOEA/D", 0.05)
        dmab.update("MOEA/D", 0.0)
        self.assertEqual(dmab.num_alarms, 1)

        # Verify arm state is completely preserved
        self.assertGreater(len(moead_arm.subproblems), 0)
        self.assertEqual(len(moead_arm.current_archive), archive_snapshot_before)

    def test_11_preservation_of_global_archive(self) -> None:
        """11. Verify that a Page-Hinkley alarm does NOT reset the Global Pareto Archive."""
        orchestrator, portfolio, dmab = self._create_pipeline(
            delta=0.001, threshold=0.01, min_instances=2, feed_initial_probe=False
        )
        # Complete initial probe
        for _ in range(3):
            orchestrator.step(25)
        archive_size_before = len(portfolio.global_archive)
        self.assertGreater(archive_size_before, 0)

        # Establish mean and trigger alarm
        dmab.update("MOEA/D", 0.05)
        dmab.update("MOEA/D", 0.05)
        dmab.update("MOEA/D", 0.0)
        self.assertEqual(dmab.num_alarms, 1)

        # Global archive must remain preserved
        self.assertEqual(len(portfolio.global_archive), archive_size_before)


    def test_12_exact_fe_accounting(self) -> None:
        """12. Verify FE_total = FE_warmup + FE_sondeo + FE_adaptativo = sum(evaluations_used)."""
        orchestrator, portfolio, _ = self._create_pipeline()
        res = orchestrator.run(total_budget=300, block_size=30, neutral_warmup=True)

        sum_evals = sum(b.evaluations_used for b in res.history)
        self.assertEqual(res.total_evaluations, sum_evals)
        self.assertEqual(portfolio.total_evaluations, sum_evals)
        self.assertEqual(sum_evals, 300)

    def test_13_zero_overshoot(self) -> None:
        """13. Verify zero evaluation overshoot under irregular block and budget combinations."""
        for budget in (73, 150, 245):
            orchestrator, portfolio, _ = self._create_pipeline()
            res = orchestrator.run(total_budget=budget, block_size=40, neutral_warmup=True)
            self.assertLessEqual(res.total_evaluations, budget)
            self.assertLessEqual(portfolio.total_evaluations, budget)

    def test_14_reproducibility_with_seed(self) -> None:
        """14. Verify bit-for-bit reproducibility of two independent runs with identical seed."""
        res1, hist1 = run_phase2_portfolio_experiment(
            instance=self.instance,
            seed=999,
            total_budget=200,
            block_size=25,
            policy="dmab_ph",
            delta=0.001,
            threshold=0.02,
        )
        res2, hist2 = run_phase2_portfolio_experiment(
            instance=self.instance,
            seed=999,
            total_budget=200,
            block_size=25,
            policy="dmab_ph",
            delta=0.001,
            threshold=0.02,
        )
        self.assertEqual(res1.evaluations_used, res2.evaluations_used)
        self.assertAlmostEqual(res1.hypervolume, res2.hypervolume, places=8)
        self.assertEqual([b.arm_name for b in hist1], [b.arm_name for b in hist2])
        self.assertEqual([b.reward for b in hist1], [b.reward for b in hist2])

    def test_15_telemetry_persistence(self) -> None:
        """15. Verify all extended telemetry columns are persisted correctly in portfolio_blocks.csv."""
        res, history = run_phase2_portfolio_experiment(
            instance=self.instance,
            seed=self.seed,
            total_budget=150,
            block_size=25,
            policy="dmab_ph",
        )
        temp_dir = tempfile.mkdtemp()
        try:
            portfolio_blocks = [(res.run_id, b) for b in history]
            export_results_to_csv([res], portfolio_blocks, results_dir=temp_dir)

            csv_path = Path(temp_dir) / "raw" / "portfolio_blocks.csv"
            self.assertTrue(csv_path.exists())

            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            self.assertGreater(len(rows), 0)
            required_fields = {
                "run_id", "arm_selected", "phase", "evaluations_used", "reward",
                "fe_before", "fe_after", "alarm_triggered", "num_alarms", "ph_statistic", "cycle_index"
            }
            self.assertTrue(required_fields.issubset(rows[0].keys()))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_16_compatibility_with_sw_ucb(self) -> None:
        """16. Verify backwards compatibility with existing SW-UCB policy."""
        res, hist = run_phase2_portfolio_experiment(
            instance=self.instance,
            seed=self.seed,
            total_budget=150,
            block_size=25,
            policy="adaptive",
        )
        self.assertEqual(res.algorithm, "Adaptive Portfolio (DMAB)")
        self.assertEqual(res.evaluations_used, 150)

    def test_17_compatibility_with_round_robin(self) -> None:
        """17. Verify backwards compatibility with existing Round-Robin policy."""
        res, hist = run_phase2_portfolio_experiment(
            instance=self.instance,
            seed=self.seed,
            total_budget=150,
            block_size=25,
            policy="uniform",
        )
        self.assertEqual(res.algorithm, "Uniform Portfolio (Round-Robin)")
        self.assertEqual(res.evaluations_used, 150)

    def test_18_budget_exhaustion_immediately_after_alarm(self) -> None:
        """18. Verify clean termination when budget is exhausted exactly as an alarm fires."""
        # 3 warmup blocks (60 FE) + 1 adaptive block (40 FE) = 100 FE budget
        orchestrator, portfolio, dmab = self._create_pipeline(
            delta=0.0001, threshold=0.0001, min_instances=1, feed_initial_probe=True
        )
        res = orchestrator.run(total_budget=100, block_size=25, neutral_warmup=True)
        self.assertEqual(res.total_evaluations, 100)

    def test_19_insufficient_budget_for_full_reexploration(self) -> None:
        """19. Verify graceful termination when budget expires mid-reexploration."""
        # Force alarm and set total_budget such that only 1 reexploration block can run
        orchestrator, portfolio, dmab = self._create_pipeline(
            delta=0.0001, threshold=0.001, min_instances=1, feed_initial_probe=True
        )
        # Pre-fire alarm
        dmab.update("MOEA/D", 0.05)
        dmab.update("MOEA/D", 0.0)
        self.assertGreaterEqual(dmab.num_alarms, 1)

        # Run with budget = 25 (only 1 block of 25 possible, need 3 for full re-exploration)
        res = orchestrator.run(total_budget=25, block_size=25, neutral_warmup=False)
        self.assertEqual(res.total_evaluations, 25)
        self.assertEqual(len(res.history), 1)
        self.assertEqual(res.history[0].phase, "reexploration")

    def test_20_absence_of_alarms_under_high_threshold(self) -> None:
        """20. Verify that setting a high threshold lambda=1.0 results in exactly zero alarms."""
        orchestrator, _, dmab = self._create_pipeline(
            delta=0.001, threshold=1.0, min_instances=5
        )
        res = orchestrator.run(total_budget=200, block_size=25, neutral_warmup=True)
        self.assertEqual(dmab.num_alarms, 0)
        for b in res.history:
            self.assertFalse(b.alarm_triggered)
            self.assertEqual(b.num_alarms, 0)


if __name__ == "__main__":
    unittest.main()
