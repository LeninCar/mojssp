"""Portfolio coordinator and Global Pareto Archive integration for MO-JSSP.

Phase 7.3 implementation defining Portfolio and PortfolioBlockResult to coordinate
stateful algorithm arms and maintain an unbounded cumulative Global Pareto Archive.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple, Union

from .algorithm_contract import AlgorithmBlockResult, PortfolioArm
from .pareto_archive import ArchiveEntry, ParetoArchive


@dataclass(frozen=True)
class PortfolioBlockResult:
    """Result of executing an algorithm arm block from the Portfolio.

    Attributes:
        arm_name: Canonical identifier of the arm that executed.
        evaluations_used: Number of real Evaluator.evaluate() calls consumed in this block.
        completed: Whether the executed arm has definitively finished its execution.
        global_archive: Defensive snapshot of the Portfolio's Global Pareto Archive after the block.
        arm_result: The raw AlgorithmBlockResult returned by the arm.
    """

    arm_name: str
    evaluations_used: int
    completed: bool
    global_archive: ParetoArchive
    arm_result: Optional[AlgorithmBlockResult] = None


class Portfolio:
    """Algorithm Portfolio managing multiple stateful arms and a Global Pareto Archive.

    Coordinates the execution of PortfolioArms under discrete evaluation budgets B.
    Maintains a persistent, cumulative Global Pareto Archive across all arms and blocks.
    Reuses the existing ParetoArchive implementation without altering domain logic.
    """

    def __init__(
        self,
        arms: Optional[Union[Sequence[PortfolioArm], Dict[str, PortfolioArm]]] = None,
    ) -> None:
        self._arms: Dict[str, PortfolioArm] = {}
        self._aliases: Dict[str, str] = {}
        self._global_archive = ParetoArchive()
        self._total_evaluations = 0

        if arms is not None:
            if isinstance(arms, dict):
                for name, arm in arms.items():
                    self.register_arm(arm, name=name)
            else:
                for arm in arms:
                    self.register_arm(arm)

    @property
    def global_archive(self) -> ParetoArchive:
        """Return a defensive copy of the current Global Pareto Archive."""
        return ParetoArchive(initial_entries=self._global_archive.entries)

    @property
    def total_evaluations(self) -> int:
        """Cumulative real evaluations consumed across all arms and blocks executed so far."""
        return self._total_evaluations

    @property
    def arm_names(self) -> Tuple[str, ...]:
        """Names of all registered arms."""
        return tuple(self._arms.keys())

    @property
    def arms(self) -> Dict[str, PortfolioArm]:
        """Mapping of registered arm names to their PortfolioArm instances."""
        return dict(self._arms)

    def register_arm(self, arm: PortfolioArm, name: Optional[str] = None) -> None:
        """Register an arm in the portfolio.

        Args:
            arm: Stateful algorithm arm implementing PortfolioArm.
            name: Optional explicit name. Defaults to arm.arm_name.

        Raises:
            TypeError: If arm does not conform to PortfolioArm.
            ValueError: If an arm with the resolved name is already registered.
        """
        if not isinstance(arm, PortfolioArm):
            raise TypeError(f"arm must implement PortfolioArm protocol, got {type(arm)}")

        reg_name = name if name is not None else arm.arm_name
        if reg_name in self._arms:
            raise ValueError(f"Arm '{reg_name}' is already registered in portfolio.")

        self._arms[reg_name] = arm

        # Register convenient lookup aliases (case-insensitive and common short names)
        norm_key = reg_name.strip().lower()
        self._aliases[norm_key] = reg_name

        canon = norm_key.replace("-", "").replace("_", "").replace("+", "").replace(" ", "")
        self._aliases[canon] = reg_name

        if "nsga" in canon and "ls" in canon:
            for extra in ("nsga2ls", "nsga2_ls", "nsga-ii+ls", "nsga2+ls", "nsgaiils"):
                self._aliases[extra] = reg_name
        elif "nsga" in canon:
            for extra in ("nsga2", "nsga_2", "nsga-ii", "nsgaii"):
                self._aliases[extra] = reg_name
        elif "mopso" in canon or "pso" in canon:
            for extra in ("mopso", "pso"):
                self._aliases[extra] = reg_name
        elif "moead" in canon or "moea" in canon:
            for extra in ("moead", "moea_d", "moea/d", "moea-d"):
                self._aliases[extra] = reg_name
        elif "spea" in canon:
            for extra in ("spea2", "spea_2", "spea-2", "speaii"):
                self._aliases[extra] = reg_name

    def get_arm(self, name: str) -> PortfolioArm:
        """Retrieve a registered arm by name or alias.

        Args:
            name: Registered name or alias.

        Returns:
            The corresponding PortfolioArm.

        Raises:
            KeyError: If the arm is not found.
        """
        if name in self._arms:
            return self._arms[name]

        norm_name = name.strip().lower()
        if norm_name in self._aliases:
            return self._arms[self._aliases[norm_name]]

        canon = norm_name.replace("-", "").replace("_", "").replace("+", "").replace(" ", "")
        if canon in self._aliases:
            return self._arms[self._aliases[canon]]

        raise KeyError(
            f"Arm '{name}' not found in portfolio. Available arms: {list(self._arms.keys())}"
        )

    def run_arm(self, name: str, budget: int) -> PortfolioBlockResult:
        """Execute a budget block on the specified arm and update the Global Pareto Archive.

        Args:
            name: Name or alias of the arm to execute.
            budget: Maximum number of calls to Evaluator.evaluate() permitted in this block.

        Returns:
            PortfolioBlockResult containing execution details and a snapshot of the Global Archive.

        Raises:
            KeyError: If the arm is not found in the portfolio.
        """
        arm = self.get_arm(name)
        canonical_name = arm.arm_name

        # Execute block on the arm
        result: AlgorithmBlockResult = arm.run(budget)

        # Update global archive with non-dominated solutions discovered by the arm
        if result.solutions and not result.solutions.is_empty:
            self._global_archive.update(result.solutions.entries)

        # Accumulate total evaluations consumed
        self._total_evaluations += result.evaluations_used

        return PortfolioBlockResult(
            arm_name=canonical_name,
            evaluations_used=result.evaluations_used,
            completed=result.completed,
            global_archive=self.global_archive,
            arm_result=result,
        )

    def reset(self) -> None:
        """Reset the portfolio's global archive, evaluation counter, and all registered arms."""
        self._global_archive = ParetoArchive()
        self._total_evaluations = 0
        for arm in self._arms.values():
            if hasattr(arm, "reset"):
                arm.reset()
