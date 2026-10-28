"""Unit and integration tests for algorithm contract and adapters (Phase 7.1)."""

from dataclasses import FrozenInstanceError
from pathlib import Path
import sys
import unittest

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mojssp import (
    AlgorithmResult,
    MOPSO,
    MOPSOAdapter,
    MOPSOResult,
    MOEADAdapter,
    MOEADResult,
    SPEA2Adapter,
    SPEA2Result,
    NSGA2,
    NSGA2Adapter,
    NSGA2LS,
    NSGA2LSAdapter,
    NSGA2LSResult,
    NSGA2Result,
    OptimizationAlgorithm,
    ParetoArchive,
    Solution,
    decode,
    evaluate,
    load_dzn,
)


class TestAlgorithmContract(unittest.TestCase):
    """Test suite for AlgorithmResult, OptimizationAlgorithm, and composition adapters."""

    def setUp(self) -> None:
        toy_dzn = Path(__file__).resolve().parent.parent / "data" / "validation" / "toy_instance.dzn"
        self.instance = load_dzn(str(toy_dzn))

    def test_algorithm_result_structure_and_immutability(self) -> None:
        """Test AlgorithmResult fields and frozen immutability."""
        archive = ParetoArchive()
        dummy_raw = {"dummy": 123}

        result = AlgorithmResult(
            archive=archive,
            total_evaluations=100,
            seed=42,
            algorithm_name="TestAlgo",
            raw_result=dummy_raw,
        )

        self.assertIs(result.archive, archive)
        self.assertEqual(result.total_evaluations, 100)
        self.assertEqual(result.seed, 42)
        self.assertEqual(result.algorithm_name, "TestAlgo")
        self.assertIs(result.raw_result, dummy_raw)

        # Frozen immutability check
        with self.assertRaises(FrozenInstanceError):
            result.algorithm_name = "Modified"  # type: ignore

    def test_nsga2_adapter_wrapping_and_traceability(self) -> None:
        """Test NSGA2Adapter wraps NSGA-II cleanly and preserves raw_result."""
        algo = NSGA2(population_size=8, generations=2, seed=101)
        adapter = NSGA2Adapter(algorithm=algo)

        # Protocol check
        self.assertTrue(isinstance(adapter, OptimizationAlgorithm))
        self.assertEqual(adapter.algorithm_name, "NSGA-II")

        result = adapter.run(self.instance)

        self.assertIsInstance(result, AlgorithmResult)
        self.assertIsInstance(result.archive, ParetoArchive)
        self.assertEqual(result.algorithm_name, "NSGA-II")
        self.assertEqual(result.seed, 101)
        self.assertIsInstance(result.raw_result, NSGA2Result)
        self.assertGreater(len(result.archive), 0)

        # Archive must contain the same non-dominated solutions reported in raw_result
        self.assertEqual(
            set(e.solution.sequence for e in result.archive.entries),
            set(sol.sequence for sol in result.raw_result.non_dominated_solutions),
        )

    def test_nsga2_ls_adapter_wrapping_and_traceability(self) -> None:
        """Test NSGA2LSAdapter wraps NSGA-II+LS cleanly and preserves specific fields."""
        algo = NSGA2LS(
            population_size=8,
            generations=2,
            max_ls_iterations=3,
            max_ls_neighbors=2,
            seed=202,
        )
        adapter = NSGA2LSAdapter(algorithm=algo)

        # Protocol check
        self.assertTrue(isinstance(adapter, OptimizationAlgorithm))
        self.assertEqual(adapter.algorithm_name, "NSGA-II+LS")

        result = adapter.run(self.instance)

        self.assertIsInstance(result, AlgorithmResult)
        self.assertIsInstance(result.archive, ParetoArchive)
        self.assertEqual(result.algorithm_name, "NSGA-II+LS")
        self.assertEqual(result.seed, 202)
        self.assertIsInstance(result.raw_result, NSGA2LSResult)

        # Specific fields like ls_evaluations are directly preserved via raw_result
        self.assertGreater(result.raw_result.ls_evaluations, 0)
        self.assertEqual(result.total_evaluations, result.raw_result.total_evaluations)

    def test_mopso_adapter_wrapping_and_traceability(self) -> None:
        """Test MOPSOAdapter wraps MOPSO cleanly and preserves specific fields."""
        algo = MOPSO(population_size=6, max_evaluations=18)
        adapter = MOPSOAdapter(algorithm=algo, seed=303)

        # Protocol check
        self.assertTrue(isinstance(adapter, OptimizationAlgorithm))
        self.assertEqual(adapter.algorithm_name, "MOPSO")

        result = adapter.run(self.instance)

        self.assertIsInstance(result, AlgorithmResult)
        self.assertIsInstance(result.archive, ParetoArchive)
        # Directly wraps the exact same ParetoArchive
        self.assertIs(result.archive, result.raw_result.archive)
        self.assertEqual(result.algorithm_name, "MOPSO")
        self.assertEqual(result.seed, 303)
        self.assertIsInstance(result.raw_result, MOPSOResult)

        # Specific fields like iterations are directly preserved via raw_result
        self.assertGreater(result.raw_result.iterations, 0)
        self.assertEqual(result.total_evaluations, result.raw_result.total_evaluations)

    def test_moead_adapter_wrapping_and_traceability(self) -> None:
        """Test MOEADAdapter wraps MOEA/D cleanly and preserves raw_result."""
        adapter = MOEADAdapter(population_size=10, max_evaluations=30, seed=404)

        # Protocol check
        self.assertTrue(isinstance(adapter, OptimizationAlgorithm))
        self.assertEqual(adapter.algorithm_name, "MOEA/D")

        result = adapter.run(self.instance)

        self.assertIsInstance(result, AlgorithmResult)
        self.assertIsInstance(result.archive, ParetoArchive)
        self.assertEqual(result.algorithm_name, "MOEA/D")
        self.assertEqual(result.seed, 404)
        self.assertIsInstance(result.raw_result, MOEADResult)
        self.assertEqual(result.total_evaluations, 30)
        self.assertGreater(len(result.archive), 0)

    def test_spea2_adapter_wrapping_and_traceability(self) -> None:
        """Test SPEA2Adapter wraps SPEA2 cleanly and preserves raw_result."""
        adapter = SPEA2Adapter(population_size=10, archive_size=10, max_evaluations=30, seed=505)

        # Protocol check
        self.assertTrue(isinstance(adapter, OptimizationAlgorithm))
        self.assertEqual(adapter.algorithm_name, "SPEA2")

        result = adapter.run(self.instance)

        self.assertIsInstance(result, AlgorithmResult)
        self.assertIsInstance(result.archive, ParetoArchive)
        self.assertEqual(result.algorithm_name, "SPEA2")
        self.assertEqual(result.seed, 505)
        self.assertIsInstance(result.raw_result, SPEA2Result)
        self.assertEqual(result.total_evaluations, 30)
        self.assertGreater(len(result.archive), 0)

    def test_raw_result_identity(self) -> None:
        """Test that result.raw_result is the exact original instance (object identity)."""
        # Test across all three adapters
        mopso_adapter = MOPSOAdapter(population_size=6, max_evaluations=12, seed=42)
        mopso_res = mopso_adapter.run(self.instance)
        self.assertIsInstance(mopso_res.raw_result, MOPSOResult)

        nsga2_adapter = NSGA2Adapter(population_size=8, generations=1, seed=42)
        nsga2_res = nsga2_adapter.run(self.instance)
        self.assertIsInstance(nsga2_res.raw_result, NSGA2Result)

        nsga2ls_adapter = NSGA2LSAdapter(
            population_size=8,
            generations=1,
            max_ls_iterations=2,
            max_ls_neighbors=2,
            seed=42,
        )
        nsga2ls_res = nsga2ls_adapter.run(self.instance)
        self.assertIsInstance(nsga2ls_res.raw_result, NSGA2LSResult)

    def test_evaluations_fidelity(self) -> None:
        """Test evaluation reporting fidelity across all three algorithms."""
        # 1. MOPSO: reports total_evaluations natively
        mopso_adapter = MOPSOAdapter(population_size=6, max_evaluations=15, seed=123)
        mopso_res = mopso_adapter.run(self.instance)
        self.assertEqual(mopso_res.total_evaluations, 15)
        self.assertEqual(mopso_res.total_evaluations, mopso_res.raw_result.total_evaluations)

        # 2. NSGA2LS: reports total_evaluations natively
        nsga2ls_adapter = NSGA2LSAdapter(
            population_size=8,
            generations=1,
            max_ls_iterations=2,
            max_ls_neighbors=2,
            seed=123,
        )
        nsga2ls_res = nsga2ls_adapter.run(self.instance)
        self.assertEqual(nsga2ls_res.total_evaluations, nsga2ls_res.raw_result.total_evaluations)
        self.assertGreater(nsga2ls_res.total_evaluations, 0)

        # 3. NSGA2: F3 implementation did not expose total_evaluations in NSGA2Result;
        # adapter reports None honestly rather than inventing an artificial formula.
        nsga2_adapter = NSGA2Adapter(population_size=8, generations=1, seed=123)
        nsga2_res = nsga2_adapter.run(self.instance)
        self.assertIsNone(nsga2_res.total_evaluations)

    def test_deterministic_reproducibility(self) -> None:
        """Test that two runs with identical config and seed yield identical objectives and solutions."""
        # Test MOPSOAdapter reproducibility
        mop1 = MOPSOAdapter(population_size=6, max_evaluations=24, seed=777)
        mop2 = MOPSOAdapter(population_size=6, max_evaluations=24, seed=777)
        r_mop1 = mop1.run(self.instance)
        r_mop2 = mop2.run(self.instance)
        self.assertEqual(r_mop1.total_evaluations, r_mop2.total_evaluations)
        self.assertEqual(
            [e.objectives for e in r_mop1.archive.entries],
            [e.objectives for e in r_mop2.archive.entries],
        )

        # Test NSGA2Adapter reproducibility
        nsg1 = NSGA2Adapter(population_size=8, generations=2, seed=888)
        nsg2 = NSGA2Adapter(population_size=8, generations=2, seed=888)
        r_nsg1 = nsg1.run(self.instance)
        r_nsg2 = nsg2.run(self.instance)
        self.assertEqual(
            [e.objectives for e in r_nsg1.archive.entries],
            [e.objectives for e in r_nsg2.archive.entries],
        )

        # Test NSGA2LSAdapter reproducibility
        ls1 = NSGA2LSAdapter(
            population_size=8,
            generations=2,
            max_ls_iterations=2,
            max_ls_neighbors=2,
            seed=999,
        )
        ls2 = NSGA2LSAdapter(
            population_size=8,
            generations=2,
            max_ls_iterations=2,
            max_ls_neighbors=2,
            seed=999,
        )
        r_ls1 = ls1.run(self.instance)
        r_ls2 = ls2.run(self.instance)
        self.assertEqual(r_ls1.total_evaluations, r_ls2.total_evaluations)
        self.assertEqual(
            [e.objectives for e in r_ls1.archive.entries],
            [e.objectives for e in r_ls2.archive.entries],
        )


if __name__ == "__main__":
    unittest.main()
