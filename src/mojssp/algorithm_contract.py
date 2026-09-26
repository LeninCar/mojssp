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

