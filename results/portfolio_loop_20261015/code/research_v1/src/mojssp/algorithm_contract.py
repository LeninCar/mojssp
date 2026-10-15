"""Common algorithm contract and composition-based adapters for MO-JSSP algorithms.

Phase 7.1 implementation defining a unified output structure (AlgorithmResult)
and lightweight wrappers (NSGA2Adapter, NSGA2LSAdapter, MOPSOAdapter) for portfolio
integration without altering existing scientific implementations.
"""

from dataclasses import dataclass
from typing import Any, Optional, Protocol, runtime_checkable

from .instance import Instance
from .mopso import MOPSO, MOPSOResult
from .nsga2 import NSGA2, NSGA2Result
from .nsga2_ls import NSGA2LS, NSGA2LSResult
from .pareto_archive import ParetoArchive


@dataclass(frozen=True)
class AlgorithmResult:
    """Unified optimization algorithm result container for portfolio integration.

    Attributes:
        archive: ParetoArchive containing the non-dominated front discovered by the algorithm.
        total_evaluations: Real evaluation count reported by the algorithm, or None if the
            underlying algorithm does not report it natively (e.g. NSGA-II in F3).
        seed: Random seed used during execution.
        algorithm_name: Descriptive identifier ('NSGA-II', 'NSGA-II+LS', 'MOPSO').
        raw_result: Direct reference to the specific original algorithm result
            (NSGA2Result, NSGA2LSResult, or MOPSOResult).
    """

    archive: ParetoArchive
    total_evaluations: Optional[int]
    seed: Optional[int]
    algorithm_name: str
    raw_result: Any


@runtime_checkable
class OptimizationAlgorithm(Protocol):
    """Common protocol for algorithms executable by the portfolio."""

    @property
    def algorithm_name(self) -> str:
        """Descriptive identifier of the algorithm."""
        ...

    def run(self, instance: Instance) -> AlgorithmResult:
        """Execute the algorithm on the given instance and return a unified AlgorithmResult."""
        ...


class NSGA2Adapter:
    """Lightweight adapter wrapping NSGA2 into the OptimizationAlgorithm contract."""

    def __init__(self, algorithm: Optional[NSGA2] = None, **kwargs: Any) -> None:
        self._algorithm = algorithm if algorithm is not None else NSGA2(**kwargs)

    @property
    def algorithm(self) -> NSGA2:
        return self._algorithm

    @property
    def algorithm_name(self) -> str:
        return "NSGA-II"

    def run(self, instance: Instance) -> AlgorithmResult:
        raw: NSGA2Result = self._algorithm.run(instance)
        archive = ParetoArchive()
        archive.update(
            list(
                zip(
                    raw.non_dominated_solutions,
                    raw.non_dominated_schedules,
                    raw.non_dominated_objectives,
                )
            )
        )
        return AlgorithmResult(
            archive=archive,
            total_evaluations=getattr(raw, "total_evaluations", None),
            seed=getattr(self._algorithm, "seed", None),
            algorithm_name=self.algorithm_name,
            raw_result=raw,
        )


class NSGA2LSAdapter:
    """Lightweight adapter wrapping NSGA2LS into the OptimizationAlgorithm contract."""

    def __init__(self, algorithm: Optional[NSGA2LS] = None, **kwargs: Any) -> None:
        self._algorithm = algorithm if algorithm is not None else NSGA2LS(**kwargs)

    @property
    def algorithm(self) -> NSGA2LS:
        return self._algorithm

    @property
    def algorithm_name(self) -> str:
        return "NSGA-II+LS"

    def run(self, instance: Instance) -> AlgorithmResult:
        raw: NSGA2LSResult = self._algorithm.run(instance)
        archive = ParetoArchive()
        archive.update(
            list(
                zip(
                    raw.non_dominated_solutions,
                    raw.non_dominated_schedules,
                    raw.non_dominated_objectives,
                )
            )
        )
        return AlgorithmResult(
            archive=archive,
            total_evaluations=raw.total_evaluations,
            seed=getattr(self._algorithm, "seed", None),
            algorithm_name=self.algorithm_name,
            raw_result=raw,
        )


class MOPSOAdapter:
    """Lightweight adapter wrapping MOPSO into the OptimizationAlgorithm contract."""

    def __init__(
        self,
        algorithm: Optional[MOPSO] = None,
        seed: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        self._algorithm = algorithm if algorithm is not None else MOPSO(**kwargs)
        self._seed = seed

    @property
    def algorithm(self) -> MOPSO:
        return self._algorithm

    @property
    def algorithm_name(self) -> str:
        return "MOPSO"

    def run(self, instance: Instance) -> AlgorithmResult:
        raw: MOPSOResult = self._algorithm.run(instance, seed=self._seed)
        return AlgorithmResult(
            archive=raw.archive,
            total_evaluations=raw.total_evaluations,
            seed=raw.seed,
            algorithm_name=self.algorithm_name,
            raw_result=raw,
        )


class MOEADAdapter:
    """Lightweight adapter wrapping MOEAD into the OptimizationAlgorithm contract."""

    def __init__(self, algorithm: Optional[Any] = None, **kwargs: Any) -> None:
        from .moead import MOEAD
        self._algorithm = algorithm if algorithm is not None else MOEAD(**kwargs)

    @property
    def algorithm(self) -> Any:
        return self._algorithm

    @property
    def algorithm_name(self) -> str:
        return "MOEA/D"

    def run(self, instance: Instance) -> AlgorithmResult:
        from .moead import MOEADResult
        raw: MOEADResult = self._algorithm.run(instance)
        return AlgorithmResult(
            archive=raw.archive,
            total_evaluations=raw.total_evaluations,
            seed=raw.seed,
            algorithm_name=self.algorithm_name,
            raw_result=raw,
        )


class SPEA2Adapter:
    """Lightweight adapter wrapping SPEA2 into the OptimizationAlgorithm contract."""

    def __init__(self, algorithm: Optional[Any] = None, **kwargs: Any) -> None:
        from .spea2 import SPEA2
        self._algorithm = algorithm if algorithm is not None else SPEA2(**kwargs)

    @property
    def algorithm(self) -> Any:
        return self._algorithm

    @property
    def algorithm_name(self) -> str:
        return "SPEA2"

    def run(self, instance: Instance) -> AlgorithmResult:
        from .spea2 import SPEA2Result
        raw: SPEA2Result = self._algorithm.run(instance)
        return AlgorithmResult(
            archive=raw.archive,
            total_evaluations=raw.total_evaluations,
            seed=raw.seed,
            algorithm_name=self.algorithm_name,
            raw_result=raw,
        )


@dataclass(frozen=True)
class AlgorithmBlockResult:
    """Result of executing an algorithm arm for an evaluation budget block.

    Attributes:
        solutions: Defensive snapshot of the arm's current ParetoArchive of
            non-dominated solutions discovered by the arm up to the end of this block.
        evaluations_used: Exact number of real Evaluator.evaluate() calls consumed
            during this run(budget) call (evaluations_used <= budget).
        completed: True if the arm has definitively finished its execution budget or
            iterations, False otherwise.
    """

    solutions: ParetoArchive
    evaluations_used: int
    completed: bool


@runtime_checkable
class PortfolioArm(Protocol):
    """Common protocol for stateful algorithm arms in the portfolio."""

    @property
    def arm_name(self) -> str:
        """Descriptive identifier of the arm ('NSGA-II', etc.)."""
        ...

    @property
    def total_evaluations(self) -> int:
        """Cumulative real evaluations consumed across all blocks executed so far."""
        ...

    @property
    def is_completed(self) -> bool:
        """True if the arm has definitively finished its execution budget/generations."""
        ...

    def run(self, budget: int) -> AlgorithmBlockResult:
        """Execute up to `budget` real evaluations and return the block result.

        Args:
            budget: Maximum number of calls to Evaluator.evaluate() permitted in this block.

        Returns:
            AlgorithmBlockResult with the updated archive snapshot, evaluations consumed,
            and completion status.
        """
        ...

