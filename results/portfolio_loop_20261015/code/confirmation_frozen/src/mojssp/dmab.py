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

    def initialize_arm(self, arm_name: str) -> None:
        """Mark an arm as initialized by neutral warm-up without updating reward statistics."""
        ...

    def is_arm_initialized(self, arm_name: str) -> bool:
        """Return whether an arm has completed warm-up or initialization."""
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
        self._adaptive_pulls: Dict[str, int] = {name: 0 for name in self._arm_names}
        self._initialized_arms: set[str] = set()
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
        # Initial probe phase: guarantee each arm receives exactly one adaptive block before ordinary SW-UCB
        for name in self._arm_names:
            if self._adaptive_pulls[name] == 0:
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
        self._adaptive_pulls[arm_name] += 1
        self._initialized_arms.add(arm_name)
        self._window.append((arm_name, float(reward)))

    def initialize_arm(self, arm_name: str) -> None:
        """Mark an arm as initialized by neutral warm-up without updating reward statistics.

        Args:
            arm_name: Identifier of the arm to mark as initialized.

        Raises:
            KeyError: If arm_name is not registered.
        """
        if arm_name not in self._total_counts:
            raise KeyError(
                f"Unknown arm '{arm_name}'. Registered arms: {list(self._arm_names)}"
            )
        self._initialized_arms.add(arm_name)

    def mark_warmup_complete(self, arm_name: Optional[str] = None) -> None:
        """Convenience method to mark one or all arms as having completed warm-up."""
        if arm_name is not None:
            self.initialize_arm(arm_name)
        else:
            for name in self._arm_names:
                self.initialize_arm(name)

    def is_arm_initialized(self, arm_name: str) -> bool:
        """Return whether an arm has completed warm-up or initialization."""
        if arm_name not in self._total_counts:
            raise KeyError(
                f"Unknown arm '{arm_name}'. Registered arms: {list(self._arm_names)}"
            )
        return arm_name in self._initialized_arms

    def get_adaptive_pulls(self, arm_name: str) -> int:
        """Return the count of adaptive updates executed for the given arm."""
        if arm_name not in self._adaptive_pulls:
            raise KeyError(
                f"Unknown arm '{arm_name}'. Registered arms: {list(self._arm_names)}"
            )
        return self._adaptive_pulls[arm_name]

    def is_in_initial_probe(self, arm_name: str) -> bool:
        """Return True if the arm has not yet completed its initial adaptive probe block."""
        if arm_name not in self._adaptive_pulls:
            raise KeyError(
                f"Unknown arm '{arm_name}'. Registered arms: {list(self._arm_names)}"
            )
        return self._adaptive_pulls[arm_name] == 0

    @property
    def is_initial_probe_complete(self) -> bool:
        """Return True if all registered arms have completed their initial adaptive probe."""
        return all(count > 0 for count in self._adaptive_pulls.values())

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
        self._adaptive_pulls = {name: 0 for name in self._arm_names}
        self._initialized_arms.clear()
        self._window.clear()
        self._rng = random.Random(self._seed)


class RoundRobinSelector:
    """Deterministic cyclical selector allocating budget blocks uniformly across arms.

    Conforms to DMABSelector protocol so it can be seamlessly orchestrated by
    AdaptivePortfolioOrchestrator to serve as the uniform round-robin baseline.
    """

    def __init__(self, arm_names: Sequence[str], seed: Optional[int] = None) -> None:
        if not arm_names:
            raise ValueError("arm_names cannot be empty")
        self._arm_names: Tuple[str, ...] = tuple(arm_names)
        self._seed = seed
        self._total_pulls: int = 0
        self._total_counts: Dict[str, int] = {name: 0 for name in self._arm_names}
        self._adaptive_pulls: Dict[str, int] = {name: 0 for name in self._arm_names}
        self._initialized_arms: set[str] = set()
        self._current_idx: int = 0

    @property
    def arm_names(self) -> Tuple[str, ...]:
        return self._arm_names

    @property
    def total_pulls(self) -> int:
        return self._total_pulls

    def select_arm(self) -> str:
        selected = self._arm_names[self._current_idx % len(self._arm_names)]
        self._current_idx += 1
        return selected

    def update(self, arm_name: str, reward: float) -> None:
        if arm_name not in self._total_counts:
            raise KeyError(f"Unknown arm '{arm_name}'")
        self._total_pulls += 1
        self._total_counts[arm_name] += 1
        self._adaptive_pulls[arm_name] += 1
        self._initialized_arms.add(arm_name)

    def initialize_arm(self, arm_name: str) -> None:
        if arm_name not in self._total_counts:
            raise KeyError(f"Unknown arm '{arm_name}'")
        self._initialized_arms.add(arm_name)

    def is_arm_initialized(self, arm_name: str) -> bool:
        return arm_name in self._initialized_arms

    def get_adaptive_pulls(self, arm_name: str) -> int:
        return self._adaptive_pulls[arm_name]

    def is_in_initial_probe(self, arm_name: str) -> bool:
        return self._adaptive_pulls[arm_name] == 0

    @property
    def is_initial_probe_complete(self) -> bool:
        return all(count > 0 for count in self._adaptive_pulls.values())

    def get_stats(self) -> Dict[str, ArmStats]:
        return {
            name: ArmStats(
                arm_name=name,
                total_pulls=self._total_counts[name],
                window_pulls=self._total_counts[name],
                window_mean=0.0,
                ucb=0.0,
            )
            for name in self._arm_names
        }

    def reset(self) -> None:
        self._total_pulls = 0
        self._total_counts = {name: 0 for name in self._arm_names}
        self._adaptive_pulls = {name: 0 for name in self._arm_names}
        self._initialized_arms.clear()
        self._current_idx = 0


class UniformRandomSelector:
    """Random allocation selector sampling arms uniformly at random.

    During the initial probe phase, guarantees each arm is probed once to ensure
    identical initial conditions across all portfolio methods, and then samples
    arms uniformly at random (p = 1/K).
    Conforms to DMABSelector protocol for direct orchestration.
    """

    def __init__(self, arm_names: Sequence[str], seed: Optional[int] = None) -> None:
        if not arm_names:
            raise ValueError("arm_names cannot be empty")
        self._arm_names: Tuple[str, ...] = tuple(arm_names)
        self._seed = seed
        self._rng = random.Random(seed)
        self._total_pulls: int = 0
        self._total_counts: Dict[str, int] = {name: 0 for name in self._arm_names}
        self._adaptive_pulls: Dict[str, int] = {name: 0 for name in self._arm_names}
        self._initialized_arms: set[str] = set()

    @property
    def arm_names(self) -> Tuple[str, ...]:
        return self._arm_names

    @property
    def total_pulls(self) -> int:
        return self._total_pulls

    def select_arm(self) -> str:
        for name in self._arm_names:
            if self._adaptive_pulls[name] == 0:
                return name
        return self._rng.choice(self._arm_names)

    def update(self, arm_name: str, reward: float) -> None:
        if arm_name not in self._total_counts:
            raise KeyError(f"Unknown arm '{arm_name}'")
        self._total_pulls += 1
        self._total_counts[arm_name] += 1
        self._adaptive_pulls[arm_name] += 1
        self._initialized_arms.add(arm_name)

    def initialize_arm(self, arm_name: str) -> None:
        if arm_name not in self._total_counts:
            raise KeyError(f"Unknown arm '{arm_name}'")
        self._initialized_arms.add(arm_name)

    def is_arm_initialized(self, arm_name: str) -> bool:
        return arm_name in self._initialized_arms

    def get_adaptive_pulls(self, arm_name: str) -> int:
        return self._adaptive_pulls[arm_name]

    def is_in_initial_probe(self, arm_name: str) -> bool:
        return self._adaptive_pulls[arm_name] == 0

    @property
    def is_initial_probe_complete(self) -> bool:
        return all(count > 0 for count in self._adaptive_pulls.values())

    def get_stats(self) -> Dict[str, ArmStats]:
        return {
            name: ArmStats(
                arm_name=name,
                total_pulls=self._total_counts[name],
                window_pulls=self._total_counts[name],
                window_mean=0.0,
                ucb=0.0,
            )
            for name in self._arm_names
        }

    def reset(self) -> None:
        self._total_pulls = 0
        self._total_counts = {name: 0 for name in self._arm_names}
        self._adaptive_pulls = {name: 0 for name in self._arm_names}
        self._initialized_arms.clear()
        self._rng = random.Random(self._seed)


class RoundRobinSelector:
    """Deterministic Round-Robin selector cycling cyclically through arms.

    Conforms to the DMABSelector protocol for seamless drop-in integration with
    AdaptivePortfolioOrchestrator. Guarantees uniform allocation across arms:
        A_0 -> A_1 -> ... -> A_{K-1} -> A_0 -> ...
    Preserves exact startup protocol equivalence with SW-UCB (identifies initial probe
    phase for the first cycle through the arms).
    """

    def __init__(self, arm_names: Sequence[str]) -> None:
        """Initialize RoundRobinSelector with a sequence of arm names.

        Args:
            arm_names: Non-empty sequence of unique, non-empty arm identifiers.

        Raises:
            ValueError: If arm_names is empty, contains non-strings, or duplicates.
        """
        if not arm_names:
            raise ValueError("arm_names cannot be empty")

        cleaned: List[str] = []
        seen = set()
        for idx, name in enumerate(arm_names):
            if not isinstance(name, str) or not name.strip():
                raise ValueError(
                    f"arm_names must contain non-empty strings, got element {idx}: {name!r}"
                )
            if name in seen:
                raise ValueError(f"Duplicate arm name '{name}' in arm_names.")
            seen.add(name)
            cleaned.append(name)

        self._arm_names: Tuple[str, ...] = tuple(cleaned)
        self._current_index: int = 0
        self._total_pulls: int = 0
        self._total_counts: Dict[str, int] = {name: 0 for name in self._arm_names}
        self._adaptive_pulls: Dict[str, int] = {name: 0 for name in self._arm_names}
        self._initialized_arms: set[str] = set()

    @property
    def arm_names(self) -> Tuple[str, ...]:
        return self._arm_names

    @property
    def total_pulls(self) -> int:
        return self._total_pulls

    def select_arm(self) -> str:
        """Select the next arm in cyclic round-robin sequence."""
        # Initial probe phase: ensure each arm gets its first adaptive pull in order
        for name in self._arm_names:
            if self._adaptive_pulls[name] == 0:
                return name

        # Cyclic selection
        selected = self._arm_names[self._current_index]
        return selected

    def update(self, arm_name: str, reward: float) -> None:
        """Update pull count and advance cyclic index to the next arm."""
        if arm_name not in self._total_counts:
            raise KeyError(f"Unknown arm '{arm_name}'")
        self._total_pulls += 1
        self._total_counts[arm_name] += 1
        self._adaptive_pulls[arm_name] += 1
        self._initialized_arms.add(arm_name)

        # Advance cyclic index
        arm_idx = self._arm_names.index(arm_name)
        self._current_index = (arm_idx + 1) % len(self._arm_names)

    def initialize_arm(self, arm_name: str) -> None:
        if arm_name not in self._total_counts:
            raise KeyError(f"Unknown arm '{arm_name}'")
        self._initialized_arms.add(arm_name)

    def is_arm_initialized(self, arm_name: str) -> bool:
        return arm_name in self._initialized_arms

    def get_adaptive_pulls(self, arm_name: str) -> int:
        return self._adaptive_pulls[arm_name]

    def is_in_initial_probe(self, arm_name: str) -> bool:
        return self._adaptive_pulls[arm_name] == 0

    @property
    def is_initial_probe_complete(self) -> bool:
        return all(count > 0 for count in self._adaptive_pulls.values())

    def get_stats(self) -> Dict[str, ArmStats]:
        return {
            name: ArmStats(
                arm_name=name,
                total_pulls=self._total_counts[name],
                window_pulls=self._total_counts[name],
                window_mean=0.0,
                ucb=0.0,
            )
            for name in self._arm_names
        }

    def reset(self) -> None:
        self._current_index = 0
        self._total_pulls = 0
        self._total_counts = {name: 0 for name in self._arm_names}
        self._adaptive_pulls = {name: 0 for name in self._arm_names}
        self._initialized_arms.clear()


