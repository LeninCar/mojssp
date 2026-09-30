"""Dynamic Multi-Armed Bandit (DMAB) selector for algorithm portfolios.

Phase 7.4 implementation providing domain-independent adaptive selection
using Sliding-Window UCB (SW-UCB) for non-stationary environments.
"""

from collections import deque
from dataclasses import dataclass
import math
import random
from typing import Dict, List, Optional, Protocol, Sequence, Tuple, runtime_checkable


@dataclass(frozen=True)
class ArmStats:
    """Immutable snapshot of statistics for an arm in the bandit selector.

    Attributes:
        arm_name: Identifier of the arm.
        total_pulls: Cumulative number of times this arm has been updated.
        window_pulls: Number of observations of this arm in the current sliding window.
        window_mean: Empirical mean reward within the sliding window (0.0 if window_pulls == 0).
        ucb: Upper Confidence Bound value (float('inf') if window_pulls == 0).
    """

    arm_name: str
    total_pulls: int
    window_pulls: int
    window_mean: float
    ucb: float


@runtime_checkable
class DMABSelector(Protocol):
    """Protocol for dynamic multi-armed bandit selectors in algorithm portfolios."""

    @property
    def arm_names(self) -> Tuple[str, ...]:
        """Registered canonical arm identifiers."""
        ...

    @property
    def total_pulls(self) -> int:
        """Total number of pulls (updates) executed across all arms."""
        ...

    def select_arm(self) -> str:
        """Select the next arm to execute according to the selection policy."""
        ...

    def update(self, arm_name: str, reward: float) -> None:
        """Update the bandit statistics with the reward observed from the executed arm."""
        ...

    def get_stats(self) -> Dict[str, ArmStats]:
        """Return a defensive snapshot of statistics for all registered arms."""
        ...

    def reset(self) -> None:
        """Reset internal counters, sliding window, and pseudo-random generator state."""
        ...


class SlidingWindowUCB:
    """Sliding-Window Upper Confidence Bound (SW-UCB) selector.

    Adapts Multi-Armed Bandit decision making to non-stationary environments by maintaining
    a bounded sliding window of the most recent W observations.

    Selection Policy:
        1. Warm-up: If any arm has never been updated (total_pulls for that arm == 0),
           select the first unpulled arm in registration order.
        2. Window-based UCB: For each arm i:
           - If arm i has 0 observations in the current sliding window (N_{i, W} == 0),
             its UCB is set to +inf to ensure immediate re-exploration.
           - Otherwise:
               mu_{i, W} = (sum of rewards for i in window) / N_{i, W}
               t_eff = min(total_pulls, window_size)
               exploration = c * sqrt(ln(t_eff) / N_{i, W})   (if t_eff > 1, else 0.0)
               UCB_i = mu_{i, W} + exploration
        3. Tie-breaking: If multiple arms share the maximal UCB value, ties are broken
           using a seeded pseudo-random generator (self._rng.choice).
    """

    def __init__(
        self,
        arm_names: Sequence[str],
        window_size: int = 10,
        exploration_factor: float = math.sqrt(2),
        seed: Optional[int] = None,
    ) -> None:
        """Initialize the SlidingWindowUCB selector.

        Args:
            arm_names: Non-empty sequence of unique, non-empty arm identifiers.
            window_size: Maximum number of recent observations retained in the sliding window (> 0).
            exploration_factor: Scaling factor c >= 0.0 for exploration bonus.
            seed: Optional integer seed for reproducible tie-breaking.

        Raises:
            ValueError: If arm_names is empty, contains non-strings, empty strings, or duplicates.
            ValueError: If window_size <= 0 or not an integer.
            ValueError: If exploration_factor < 0.0 or not a finite number.
        """
        if not isinstance(arm_names, (list, tuple)):
            arm_names = list(arm_names)

        if not arm_names:
            raise ValueError("arm_names sequence cannot be empty.")

        cleaned_names: List[str] = []
        seen = set()
        for idx, name in enumerate(arm_names):
            if not isinstance(name, str) or not name.strip():
                raise ValueError(
                    f"arm_names must contain non-empty strings, got element {idx}: {name!r}"
                )
            if name in seen:
                raise ValueError(f"Duplicate arm name '{name}' in arm_names.")
            seen.add(name)
            cleaned_names.append(name)

        if isinstance(window_size, bool) or not isinstance(window_size, int) or window_size <= 0:
            raise ValueError(f"window_size must be an integer > 0, got {window_size!r}")

        if (
            isinstance(exploration_factor, bool)
            or not isinstance(exploration_factor, (int, float))
            or math.isnan(exploration_factor)
            or math.isinf(exploration_factor)
            or exploration_factor < 0.0
        ):
            raise ValueError(
                f"exploration_factor must be a finite float >= 0.0, got {exploration_factor!r}"
            )

        self._arm_names: Tuple[str, ...] = tuple(cleaned_names)
        self._window_size: int = window_size
        self._c: float = float(exploration_factor)
        self._seed: Optional[int] = seed
        self._rng: random.Random = random.Random(seed)

        self._total_pulls: int = 0
        self._total_counts: Dict[str, int] = {name: 0 for name in self._arm_names}
        self._window: deque[Tuple[str, float]] = deque(maxlen=window_size)

    @property
    def arm_names(self) -> Tuple[str, ...]:
        """Registered canonical arm identifiers."""
        return self._arm_names

    @property
    def window_size(self) -> int:
        """Size of the sliding window."""
        return self._window_size

    @property
    def exploration_factor(self) -> float:
        """Exploration scaling factor c."""
        return self._c

    @property
    def total_pulls(self) -> int:
        """Total number of updates across all arms."""
        return self._total_pulls

    def select_arm(self) -> str:
        """Select the next arm to execute according to SW-UCB policy.

        Returns:
            Canonical arm name of the chosen arm.
        """
        # Warm-up phase: ensure every arm has been pulled at least once in registration order
        for name in self._arm_names:
            if self._total_counts[name] == 0:
                return name

        # Compute UCB for each arm
        ucb_values: List[float] = []
        for name in self._arm_names:
            stats = self._compute_arm_stats(name)
            ucb_values.append(stats.ucb)

        max_ucb = max(ucb_values)

        # Collect all candidates matching the maximum UCB (handling inf correctly)
        best_candidates = [
            name
            for name, val in zip(self._arm_names, ucb_values)
            if val == max_ucb or (math.isinf(max_ucb) and math.isinf(val))
        ]

        if len(best_candidates) == 1:
            return best_candidates[0]

        return self._rng.choice(best_candidates)

    def update(self, arm_name: str, reward: float) -> None:
        """Update the bandit statistics with an observed reward.

        Args:
            arm_name: Identifier of the executed arm. Must be registered.
            reward: Finite real scalar representing the feedback signal.

        Raises:
            KeyError: If arm_name is not registered.
            ValueError: If reward is not a finite real number (NaN or +/-Inf).
        """
        if arm_name not in self._total_counts:
            raise KeyError(
                f"Unknown arm '{arm_name}'. Registered arms: {list(self._arm_names)}"
            )

        if (
            isinstance(reward, bool)
            or not isinstance(reward, (int, float))
            or not math.isfinite(reward)
        ):
            raise ValueError(f"reward must be a finite real number, got {reward!r}")

        self._total_pulls += 1
        self._total_counts[arm_name] += 1
        self._window.append((arm_name, float(reward)))

    def _compute_arm_stats(self, arm_name: str) -> ArmStats:
        """Internal helper to compute ArmStats for a given arm."""
        window_rewards = [r for (name, r) in self._window if name == arm_name]
        window_pulls = len(window_rewards)

        if window_pulls == 0:
            window_mean = 0.0
            ucb = float("inf")
        else:
            window_mean = sum(window_rewards) / window_pulls
            t_eff = min(self._total_pulls, self._window_size)
            if t_eff > 1:
                exploration = self._c * math.sqrt(math.log(t_eff) / window_pulls)
            else:
                exploration = 0.0
            ucb = window_mean + exploration

        return ArmStats(
            arm_name=arm_name,
            total_pulls=self._total_counts[arm_name],
            window_pulls=window_pulls,
            window_mean=window_mean,
            ucb=ucb,
        )

    def get_stats(self) -> Dict[str, ArmStats]:
        """Return a defensive snapshot of statistics for all registered arms.

        Returns:
            Mapping from arm_name to ArmStats.
        """
        return {name: self._compute_arm_stats(name) for name in self._arm_names}

    def reset(self) -> None:
        """Reset internal counters, sliding window, and pseudo-random generator state."""
        self._total_pulls = 0
        self._total_counts = {name: 0 for name in self._arm_names}
        self._window.clear()
        self._rng = random.Random(self._seed)
