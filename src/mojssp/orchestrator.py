"""Adaptive portfolio orchestrator for MO-JSSP.

Phase 7.5 implementation coordinating Portfolio execution blocks,
HypervolumeRewardTracker feedback, and DMABSelector adaptation under
a strict cumulative evaluation budget.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

from .dmab import DMABSelector
from .pareto_archive import ParetoArchive
from .portfolio import Portfolio, PortfolioBlockResult
from .reward import HypervolumeRewardTracker


@dataclass(frozen=True)
class BlockExecutionRecord:
    """Record of a single block executed by the adaptive orchestrator.

    Attributes:
        block_index: 0-indexed sequence number of this block execution.
        arm_name: Canonical name of the selected algorithm arm.
        budget_allocated: Evaluations budget granted to the arm for this block.
        evaluations_used: Exact number of Evaluator.evaluate() calls consumed.
        reward: Scalar Hypervolume delta reward computed and fed to DMAB.
        hv_after: Hypervolume of the Global Pareto Archive after the block.
        completed: Whether the arm has definitively finished its execution.
    """

    block_index: int
    arm_name: str
    budget_allocated: int
    evaluations_used: int
    reward: float
    hv_before: float
    hv_after: float
    completed: bool
    phase: str = "adaptive"


@dataclass(frozen=True)
class AdaptiveExecutionResult:
    """Result of running an adaptive portfolio execution under a global budget.

    Attributes:
        total_evaluations: Cumulative evaluations consumed by the portfolio across all blocks.
        total_blocks: Total number of blocks executed.
        global_archive: Defensive snapshot of the final Global Pareto Archive.
        history: Chronological tuple of BlockExecutionRecord entries.
    """

    total_evaluations: int
    total_blocks: int
    global_archive: ParetoArchive
    history: Tuple[BlockExecutionRecord, ...]


class AdaptivePortfolioOrchestrator:
    """Orchestrates the adaptive loop connecting Portfolio, DMAB, and RewardTracker.

    Execution cycle per block:
        1. arm_name = dmab.select_arm()
        2. block_budget = min(block_size, remaining_budget)
        3. result = portfolio.run_arm(arm_name, block_budget)
        4. reward = reward_tracker.compute_reward(portfolio.global_archive)
        5. dmab.update(arm_name, reward)
        6. evaluations_used += result.evaluations_used
    """

    def __init__(
        self,
        portfolio: Portfolio,
        dmab: DMABSelector,
        reward_tracker: HypervolumeRewardTracker,
    ) -> None:
        """Initialize the orchestrator with required collaborating components.

        Args:
            portfolio: Portfolio instance managing algorithm arms and Global Archive.
            dmab: Adaptive selector conforming to DMABSelector protocol.
            reward_tracker: HypervolumeRewardTracker instance computing ΔHV.

        Raises:
            TypeError: If any collaborator does not conform to the expected type/protocol.
        """
        if not isinstance(portfolio, Portfolio):
            raise TypeError(f"portfolio must be a Portfolio instance, got {type(portfolio)}")

        if not isinstance(dmab, DMABSelector):
            raise TypeError(f"dmab must implement DMABSelector protocol, got {type(dmab)}")

        if not isinstance(reward_tracker, HypervolumeRewardTracker):
            raise TypeError(
                f"reward_tracker must be a HypervolumeRewardTracker, got {type(reward_tracker)}"
            )

        self._portfolio = portfolio
        self._dmab = dmab
        self._reward_tracker = reward_tracker
        self._history: List[BlockExecutionRecord] = []

    @property
    def portfolio(self) -> Portfolio:
        """The underlying Portfolio instance."""
        return self._portfolio

    @property
    def dmab(self) -> DMABSelector:
        """The underlying DMAB selector."""
        return self._dmab

    @property
    def reward_tracker(self) -> HypervolumeRewardTracker:
        """The underlying Hypervolume reward tracker."""
        return self._reward_tracker

    @property
    def history(self) -> Tuple[BlockExecutionRecord, ...]:
        """Chronological history of all executed blocks."""
        return tuple(self._history)

    @property
    def total_evaluations(self) -> int:
        """Cumulative real evaluations consumed by the portfolio."""
        return self._portfolio.total_evaluations

    def step(self, block_budget: int) -> BlockExecutionRecord:
        """Execute a single adaptive block with the given evaluation budget.

        Args:
            block_budget: Maximum evaluation budget for this single block (> 0).

        Returns:
            BlockExecutionRecord detailing the execution, reward, and state.

        Raises:
            ValueError: If block_budget <= 0.
        """
        if block_budget <= 0:
            raise ValueError(f"block_budget must be positive, got {block_budget}")

        # 1. DMAB selects arm
        arm_name = self._dmab.select_arm()

        # Check if arm is undergoing its initial adaptive probe
        is_probe = False
        if hasattr(self._dmab, "is_in_initial_probe"):
            is_probe = self._dmab.is_in_initial_probe(arm_name)
        elif hasattr(self._dmab, "get_adaptive_pulls"):
            is_probe = (self._dmab.get_adaptive_pulls(arm_name) == 0)

        # 2. Portfolio executes block on selected arm
        block_result: PortfolioBlockResult = self._portfolio.run_arm(
            arm_name, budget=block_budget
        )

        # 3. Compute ΔHV reward on the updated Global Pareto Archive
        hv_before = self._reward_tracker.current_hv
        reward = self._reward_tracker.compute_reward(self._portfolio.global_archive)
        hv_after = self._reward_tracker.current_hv

        # 4. DMAB updates with observed scalar reward
        self._dmab.update(arm_name, reward)

        # 5. Record execution history
        record = BlockExecutionRecord(
            block_index=len(self._history),
            arm_name=arm_name,
            budget_allocated=block_budget,
            evaluations_used=block_result.evaluations_used,
            reward=reward,
            hv_before=hv_before,
            hv_after=hv_after,
            completed=block_result.completed,
            phase="initial_probe" if is_probe else "adaptive",
        )
        self._history.append(record)

        return record

    def run_warmup_block(self, arm_name: str, block_budget: int) -> BlockExecutionRecord:
        """Execute a single neutral warm-up block for a specific arm.

        Consumes block_budget evaluations on the arm, updates the Global Pareto Archive,
        computes ΔHV reward, but DOES NOT feed the reward into DMAB learning statistics.
        Marks the arm as initialized in DMAB without recording observations.

        Args:
            arm_name: Canonical name of the arm to execute during warm-up.
            block_budget: Evaluation budget for this warm-up block (> 0).

        Returns:
            BlockExecutionRecord detailing the warm-up block execution.

        Raises:
            ValueError: If block_budget <= 0.
        """
        if block_budget <= 0:
            raise ValueError(f"block_budget must be positive, got {block_budget}")

        hv_before = self._reward_tracker.current_hv
        block_result: PortfolioBlockResult = self._portfolio.run_arm(
            arm_name, budget=block_budget
        )
        reward = self._reward_tracker.compute_reward(self._portfolio.global_archive)
        hv_after = self._reward_tracker.current_hv

        # Mark arm initialized in DMAB without adding reward observation
        if hasattr(self._dmab, "initialize_arm"):
            self._dmab.initialize_arm(arm_name)

        record = BlockExecutionRecord(
            block_index=len(self._history),
            arm_name=arm_name,
            budget_allocated=block_budget,
            evaluations_used=block_result.evaluations_used,
            reward=reward,
            hv_before=hv_before,
            hv_after=hv_after,
            completed=block_result.completed,
            phase="warmup",
        )
        self._history.append(record)

        return record

    def run(
        self,
        total_budget: int,
        block_size: int,
        neutral_warmup: bool = True,
    ) -> AdaptiveExecutionResult:
        """Run the adaptive portfolio until consuming total_budget evaluations.

        If neutral_warmup is True (default), executes each registered arm in DMAB canonical
        registration order exactly once using block_size evaluations. During warm-up, the
        Global Archive is updated, but DMAB learning statistics are NOT updated with the
        initialization rewards. After warm-up, the active DMAB adaptive selection loop begins.

        If remaining budget does not suffice to complete warm-up across all arms, available
        budget is allocated to arms in order until total_budget is exhausted.

        Args:
            total_budget: Maximum total real evaluations to consume (> 0).
            block_size: Maximum evaluations per block (> 0).
            neutral_warmup: Whether to execute neutral warm-up before active DMAB adaptation.

        Returns:
            AdaptiveExecutionResult containing summary statistics and execution history.

        Raises:
            ValueError: If total_budget <= 0 or block_size <= 0.
        """
        if total_budget <= 0:
            raise ValueError(f"total_budget must be positive, got {total_budget}")
        if block_size <= 0:
            raise ValueError(f"block_size must be positive, got {block_size}")

        run_evaluations_used = 0

        # Phase 1: Neutral Warm-up (if enabled)
        if neutral_warmup:
            warmup_arms = list(self._dmab.arm_names)
            for arm_name in warmup_arms:
                if run_evaluations_used >= total_budget:
                    break
                remaining = total_budget - run_evaluations_used
                warmup_budget = min(block_size, remaining)
                rec = self.run_warmup_block(arm_name, warmup_budget)
                run_evaluations_used += rec.evaluations_used

                if rec.completed and all(
                    arm.is_completed for arm in self._portfolio.arms.values()
                ):
                    break

        # Phase 2: Active DMAB Adaptive Phase
        while run_evaluations_used < total_budget:
            remaining = total_budget - run_evaluations_used
            block_budget = min(block_size, remaining)

            # Check if all registered arms have definitively finished
            if self._portfolio.arms and all(
                arm.is_completed for arm in self._portfolio.arms.values()
            ):
                break

            record = self.step(block_budget)
            run_evaluations_used += record.evaluations_used

            # Guard against potential stalled loop if an arm consumed 0 evals
            if record.evaluations_used == 0 and record.completed:
                if all(arm.is_completed for arm in self._portfolio.arms.values()):
                    break

        return AdaptiveExecutionResult(
            total_evaluations=self._portfolio.total_evaluations,
            total_blocks=len(self._history),
            global_archive=self._portfolio.global_archive,
            history=tuple(self._history),
        )

    def reset(self) -> None:
        """Reset portfolio, dmab, reward tracker, and execution history."""
        self._portfolio.reset()
        self._dmab.reset()
        self._reward_tracker.reset()
        self._history.clear()
