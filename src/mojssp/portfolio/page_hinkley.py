"""Page-Hinkley selection and its stationary UCB1 control."""

from dataclasses import dataclass
import math
import random
from typing import Dict, List, Literal, Optional, Sequence, Tuple

from mojssp.portfolio.change_detection import PageHinkleyDetector
from mojssp.portfolio.dmab import ArmStats


@dataclass(frozen=True)
class PageHinkleyAlarmRecord:
    """Immutable audit record of a change-point alarm triggered by Page-Hinkley.

    Attributes:
        alarm_index: 0-indexed sequential counter of alarms triggered by this selector.
        total_pulls_at_alarm: Cumulative number of adaptive updates processed by the selector.
        cycle_pulls_at_alarm: Number of adaptive updates processed in the cycle that just concluded.
        triggering_arm: Canonical identifier of the arm whose observed reward triggered the alarm.
        observed_reward: The exact scalar reward that precipitated the alarm.
        alarm_statistic: The value of the Page-Hinkley statistic PH_t at the moment of alarm (> lambda).
        threshold: The decision threshold lambda configured for the detector.
    """

    alarm_index: int
    total_pulls_at_alarm: int
    cycle_pulls_at_alarm: int
    triggering_arm: str
    observed_reward: float
    alarm_statistic: float
    threshold: float


class PageHinkleyDMABSelector:
    """Dynamic Multi-Armed Bandit with Page-Hinkley change detection (DMAB-PH).

    Adapts Multi-Armed Bandit decision making to non-stationary environments by coupling
    a UCB selection policy with a sequential Page-Hinkley change detector (Da Costa et al., 2008).

    Selection Policy:
        1. Cycle Probe Phase: If any registered arm has 0 pulls in the current cycle
           (n_{i, \\gamma} == 0), select that arm in canonical registration order to guarantee
           mandatory exploration before index-based selection.
        2. Index-based UCB Selection: For all arms i where n_{i, \\gamma} >= 1:
               \\bar{r}_i = S_{i, \\gamma} / n_{i, \\gamma}
               exploration = c * \\sqrt{2 * \\ln(t_{cycle}) / n_{i, \\gamma}}   (if t_{cycle} > 1, else 0.0)
               UCB_i = \\bar{r}_i + exploration
        3. Tie-breaking: If multiple arms share the maximal UCB value, ties are broken
           using a seeded pseudo-random generator (self._rng.choice).

    Change Detection & Reset Mechanics:
        - Each observed scalar reward r_t is fed sequentially to the Page-Hinkley detector.
        - If the detector triggers an alarm (PH_t > \\lambda):
            a) A PageHinkleyAlarmRecord is logged in the immutable alarm history.
            b) Cumulative statistics for the current cycle are reset (t_{cycle} <- 0, n_i <- 0, S_i <- 0).
            c) The detector accumulators are reset to 0.
            d) All arms are marked as requiring mandatory re-exploration.
            e) Algorithmic populations, Global Pareto Archive, and total historical pull counts are preserved.

    Attributes:
        arm_names: Canonical tuple of registered arm identifiers.
        exploration_factor: Exploration scaling parameter c >= 0.0.
        delta: Page-Hinkley drift tolerance parameter >= 0.0.
        threshold: Page-Hinkley decision threshold lambda > 0.0.
        direction: Monitored shift direction ('down', 'up', or 'both').
        min_instances: Minimum observations before detector can trigger alarms.
    """

    def __init__(
        self,
        arm_names: Sequence[str],
        exploration_factor: float = 0.07,
        delta: float = 0.001,
        threshold: float = 0.01,
        direction: Literal["down", "up", "both"] = "down",
        min_instances: int = 5,
        feed_initial_probe_to_detector: bool = False,
        feed_reexploration_to_detector: bool = False,
        seed: Optional[int] = None,
    ) -> None:
        """Initialize the PageHinkleyDMABSelector.

        Args:
            arm_names: Non-empty sequence of unique, non-empty arm identifiers.
            exploration_factor: Scaling factor c >= 0.0 for exploration bonus. Default: 0.07.
            delta: Page-Hinkley drift tolerance parameter >= 0.0. Default: 0.001.
            threshold: Page-Hinkley decision threshold lambda > 0.0. Default: 0.01.
            direction: Change direction to monitor ('down', 'up', 'both'). Default: 'down'.
            min_instances: Minimum observations before alarm is active. Default: 5.
            feed_initial_probe_to_detector: Whether rewards from initial probe update PH. Default: False.
            feed_reexploration_to_detector: Whether rewards from post-alarm re-exploration update PH. Default: False.
            seed: Optional integer seed for reproducible tie-breaking.


        Raises:
            ValueError: If arm_names is empty, contains non-strings, or duplicates.
            ValueError: If exploration_factor < 0.0 or non-finite.
            ValueError: If detector parameters are invalid.
        """
        if not isinstance(arm_names, (list, tuple)):
            arm_names = list(arm_names)

        if not arm_names:
            raise ValueError("arm_names sequence cannot be empty.")

        cleaned_names: List[str] = []
        seen = set()
        for idx, name in enumerate(arm_names):
            if not isinstance(name, str) or not name.strip():
                raise ValueError(f"arm_names must contain non-empty strings, got element {idx}: {name!r}")
            if name in seen:
                raise ValueError(f"Duplicate arm name '{name}' in arm_names.")
            seen.add(name)
            cleaned_names.append(name)

        if (
            isinstance(exploration_factor, bool)
            or not isinstance(exploration_factor, (int, float))
            or math.isnan(exploration_factor)
            or math.isinf(exploration_factor)
            or exploration_factor < 0.0
        ):
            raise ValueError(f"exploration_factor must be a finite float >= 0.0, got {exploration_factor!r}")

        self._arm_names: Tuple[str, ...] = tuple(cleaned_names)
        self._c: float = float(exploration_factor)
        self._seed: Optional[int] = seed
        self._rng: random.Random = random.Random(seed)
        self._feed_initial_probe_to_detector: bool = bool(feed_initial_probe_to_detector)
        self._feed_reexploration_to_detector: bool = bool(feed_reexploration_to_detector)

        # Standalone Page-Hinkley detector instance (auto_reset=False for explicit control)
        self._detector: PageHinkleyDetector = PageHinkleyDetector(
            delta=delta,
            threshold=threshold,
            direction=direction,
            min_instances=min_instances,
            auto_reset=False,
        )

        # Lifetime counters (never cleared across alarms)
        self._total_pulls: int = 0
        self._total_counts: Dict[str, int] = {name: 0 for name in self._arm_names}
        self._adaptive_pulls: Dict[str, int] = {name: 0 for name in self._arm_names}
        self._initialized_arms: set[str] = set()

        # Telemetry & cycle tracking
        self._alarm_history: List[PageHinkleyAlarmRecord] = []
        self._reexploration_pulls: int = 0

        # Cycle statistics (reset upon Page-Hinkley alarm)
        self._cycle_pulls: int = 0
        self._cycle_counts: Dict[str, int] = {name: 0 for name in self._arm_names}
        self._cycle_rewards: Dict[str, float] = {name: 0.0 for name in self._arm_names}

    @property
    def arm_names(self) -> Tuple[str, ...]:
        """Registered canonical arm identifiers."""
        return self._arm_names

    @property
    def exploration_factor(self) -> float:
        """Exploration scaling factor c."""
        return self._c

    @property
    def total_pulls(self) -> int:
        """Total lifetime number of updates processed across all arms."""
        return self._total_pulls

    @property
    def cycle_pulls(self) -> int:
        """Number of updates processed in the current cycle since the last reset."""
        return self._cycle_pulls

    @property
    def detector(self) -> PageHinkleyDetector:
        """The underlying PageHinkleyDetector instance."""
        return self._detector

    @property
    def num_alarms(self) -> int:
        """Total number of change-point alarms triggered over the selector lifetime."""
        return len(self._alarm_history)

    @property
    def alarm_history(self) -> Tuple[PageHinkleyAlarmRecord, ...]:
        """Immutable historical log of all triggered Page-Hinkley alarm records."""
        return tuple(self._alarm_history)

    @property
    def feed_initial_probe_to_detector(self) -> bool:
        """Whether initial probe rewards are fed to the Page-Hinkley detector."""
        return self._feed_initial_probe_to_detector

    @property
    def feed_reexploration_to_detector(self) -> bool:
        """Whether post-alarm re-exploration rewards are fed to the Page-Hinkley detector."""
        return self._feed_reexploration_to_detector

    @property
    def reexploration_pulls(self) -> int:
        """Total number of pulls executed during mandatory probe phases (including after alarms)."""
        return self._reexploration_pulls

    def select_arm(self) -> str:
        """Select the next arm to execute according to DMAB-PH policy.

        Returns:
            Canonical arm name of the chosen arm.
        """
        # Cycle probe phase: ensure each arm receives at least one pull in current cycle
        for name in self._arm_names:
            if self._cycle_counts[name] == 0:
                return name

        # Compute UCB index for each arm in the current cycle
        # Formula: I_i(t) = \bar{r}_i + c * \sqrt{2 * \ln(t_cycle) / n_i}
        ucb_values: List[float] = []
        for name in self._arm_names:
            n_i = self._cycle_counts[name]
            mean_i = self._cycle_rewards[name] / n_i
            if self._cycle_pulls > 1:
                exploration = self._c * math.sqrt(2.0 * math.log(self._cycle_pulls) / n_i)
            else:
                exploration = 0.0
            ucb_values.append(mean_i + exploration)

        max_ucb = max(ucb_values)

        best_candidates = [
            name
            for name, val in zip(self._arm_names, ucb_values)
            if val == max_ucb or (math.isinf(max_ucb) and math.isinf(val))
        ]

        if len(best_candidates) == 1:
            return best_candidates[0]

        return self._rng.choice(best_candidates)

    def update(self, arm_name: str, reward: float) -> None:
        """Update the bandit statistics and feed reward to Page-Hinkley detector.

        Args:
            arm_name: Identifier of the executed arm. Must be registered.
            reward: Finite real scalar representing the feedback signal.

        Raises:
            KeyError: If arm_name is not registered.
            ValueError: If reward is not a finite real number.
        """
        if arm_name not in self._total_counts:
            raise KeyError(f"Unknown arm '{arm_name}'. Registered arms: {list(self._arm_names)}")

        if isinstance(reward, bool) or not isinstance(reward, (int, float)) or not math.isfinite(reward):
            raise ValueError(f"reward must be a finite real number, got {reward!r}")

        rew = float(reward)

        # Determine probe vs adaptive status BEFORE updating counters
        is_initial_probe = self._adaptive_pulls[arm_name] == 0
        is_reexploring = len(self._alarm_history) > 0 and self._cycle_counts[arm_name] == 0

        # Track re-exploration pull count if arm had 0 pulls in current cycle
        if self._cycle_counts[arm_name] == 0:
            self._reexploration_pulls += 1

        # 1. Update lifetime counters
        self._total_pulls += 1
        self._total_counts[arm_name] += 1
        self._adaptive_pulls[arm_name] += 1
        self._initialized_arms.add(arm_name)

        # 2. Update current cycle UCB statistics
        self._cycle_pulls += 1
        self._cycle_counts[arm_name] += 1
        self._cycle_rewards[arm_name] += rew

        # 3. Determine whether to feed Page-Hinkley detector
        feed_ph = True
        if is_initial_probe and not self._feed_initial_probe_to_detector:
            feed_ph = False
        elif is_reexploring and not self._feed_reexploration_to_detector:
            feed_ph = False

        alarm_triggered = False
        if feed_ph:
            alarm_triggered = self._detector.update(rew)

        # 4. Handle change-point alarm and reset
        if alarm_triggered:
            # Record alarm audit event
            alarm_record = PageHinkleyAlarmRecord(
                alarm_index=len(self._alarm_history),
                total_pulls_at_alarm=self._total_pulls,
                cycle_pulls_at_alarm=self._cycle_pulls,
                triggering_arm=arm_name,
                observed_reward=rew,
                alarm_statistic=self._detector.alarm_statistic,
                threshold=self._detector.threshold,
            )
            self._alarm_history.append(alarm_record)

            # Reset cycle statistics (forcing full re-exploration on subsequent selections)
            self._cycle_pulls = 0
            for name in self._arm_names:
                self._cycle_counts[name] = 0
                self._cycle_rewards[name] = 0.0

            # Reset detector accumulators
            self._detector.reset()

    def initialize_arm(self, arm_name: str) -> None:
        """Mark an arm as initialized by neutral warm-up without updating reward statistics."""
        if arm_name not in self._total_counts:
            raise KeyError(f"Unknown arm '{arm_name}'. Registered arms: {list(self._arm_names)}")
        self._initialized_arms.add(arm_name)

    def is_arm_initialized(self, arm_name: str) -> bool:
        """Return whether an arm has completed warm-up or initialization."""
        if arm_name not in self._total_counts:
            raise KeyError(f"Unknown arm '{arm_name}'. Registered arms: {list(self._arm_names)}")
        return arm_name in self._initialized_arms

    def get_adaptive_pulls(self, arm_name: str) -> int:
        """Return the lifetime count of adaptive updates executed for the given arm."""
        if arm_name not in self._adaptive_pulls:
            raise KeyError(f"Unknown arm '{arm_name}'. Registered arms: {list(self._arm_names)}")
        return self._adaptive_pulls[arm_name]

    def is_in_initial_probe(self, arm_name: str) -> bool:
        """Return True if the arm has not yet completed its initial lifetime adaptive probe."""
        if arm_name not in self._adaptive_pulls:
            raise KeyError(f"Unknown arm '{arm_name}'. Registered arms: {list(self._arm_names)}")
        return self._adaptive_pulls[arm_name] == 0

    @property
    def is_initial_probe_complete(self) -> bool:
        """Return True if all registered arms have completed their initial lifetime probe."""
        return all(count > 0 for count in self._adaptive_pulls.values())

    def is_in_reexploration(self, arm_name: str) -> bool:
        """Return True if the arm is undergoing post-alarm mandatory re-exploration in this cycle."""
        if arm_name not in self._cycle_counts:
            raise KeyError(f"Unknown arm '{arm_name}'. Registered arms: {list(self._arm_names)}")
        return len(self._alarm_history) > 0 and self._cycle_counts[arm_name] == 0

    @property
    def is_cycle_probe_complete(self) -> bool:
        """Return True if all registered arms have completed their probe in the current cycle."""
        return all(count > 0 for count in self._cycle_counts.values())

    def get_stats(self) -> Dict[str, ArmStats]:
        """Return a defensive snapshot of statistics for all registered arms.

        In DMAB-PH, window_pulls and window_mean correspond to the active cycle statistics.
        """
        stats: Dict[str, ArmStats] = {}
        for name in self._arm_names:
            n_i = self._cycle_counts[name]
            if n_i == 0:
                mean_i = 0.0
                ucb_val = float("inf")
            else:
                mean_i = self._cycle_rewards[name] / n_i
                if self._cycle_pulls > 1:
                    exp = self._c * math.sqrt(2.0 * math.log(self._cycle_pulls) / n_i)
                else:
                    exp = 0.0
                ucb_val = mean_i + exp

            stats[name] = ArmStats(
                arm_name=name,
                total_pulls=self._total_counts[name],
                window_pulls=n_i,
                window_mean=mean_i,
                ucb=ucb_val,
            )
        return stats

    def reset(self) -> None:
        """Reset all lifetime counters, cycle statistics, alarm history, and detector state."""
        self._total_pulls = 0
        self._total_counts = {name: 0 for name in self._arm_names}
        self._adaptive_pulls = {name: 0 for name in self._arm_names}
        self._initialized_arms.clear()

        self._alarm_history.clear()
        self._reexploration_pulls = 0

        self._cycle_pulls = 0
        self._cycle_counts = {name: 0 for name in self._arm_names}
        self._cycle_rewards = {name: 0.0 for name in self._arm_names}

        self._detector.reset()
        self._rng = random.Random(self._seed)


class ClassicalUCB1Selector:
    """Classical Upper Confidence Bound (UCB1) selector without change detection or sliding window.

    Maintains cumulative reward sums and pull counts over the entire lifetime of the execution.
    Conforms to the DMABSelector protocol for seamless integration with AdaptivePortfolioOrchestrator.

    Selection Policy:
        1. Initial Probe Phase: If any arm has 0 adaptive pulls (n_i == 0), select that arm
           in canonical registration order.
        2. UCB1 Index Selection: For all arms i where n_i >= 1:
               \\bar{r}_i = S_i / n_i
               exploration = c * \\sqrt{2 * \\ln(t) / n_i}   (if t > 1, else 0.0)
               UCB_i = \\bar{r}_i + exploration
        3. Tie-breaking: If multiple arms share the maximal UCB value, ties are broken
           using a seeded pseudo-random generator (self._rng.choice).
    """

    def __init__(
        self,
        arm_names: Sequence[str],
        exploration_factor: float = 0.07,
        seed: Optional[int] = None,
    ) -> None:
        if not isinstance(arm_names, (list, tuple)):
            arm_names = list(arm_names)

        if not arm_names:
            raise ValueError("arm_names sequence cannot be empty.")

        cleaned_names: List[str] = []
        seen = set()
        for idx, name in enumerate(arm_names):
            if not isinstance(name, str) or not name.strip():
                raise ValueError(f"arm_names must contain non-empty strings, got element {idx}: {name!r}")
            if name in seen:
                raise ValueError(f"Duplicate arm name '{name}' in arm_names.")
            seen.add(name)
            cleaned_names.append(name)

        if (
            isinstance(exploration_factor, bool)
            or not isinstance(exploration_factor, (int, float))
            or math.isnan(exploration_factor)
            or math.isinf(exploration_factor)
            or exploration_factor < 0.0
        ):
            raise ValueError(f"exploration_factor must be a finite float >= 0.0, got {exploration_factor!r}")

        self._arm_names: Tuple[str, ...] = tuple(cleaned_names)
        self._c: float = float(exploration_factor)
        self._seed: Optional[int] = seed
        self._rng: random.Random = random.Random(seed)

        self._total_pulls: int = 0
        self._total_counts: Dict[str, int] = {name: 0 for name in self._arm_names}
        self._adaptive_pulls: Dict[str, int] = {name: 0 for name in self._arm_names}
        self._total_rewards: Dict[str, float] = {name: 0.0 for name in self._arm_names}
        self._initialized_arms: set[str] = set()

    @property
    def arm_names(self) -> Tuple[str, ...]:
        return self._arm_names

    @property
    def exploration_factor(self) -> float:
        return self._c

    @property
    def total_pulls(self) -> int:
        return self._total_pulls

    def select_arm(self) -> str:
        # Initial probe: ensure each arm gets at least 1 adaptive pull
        for name in self._arm_names:
            if self._adaptive_pulls[name] == 0:
                return name

        ucb_values: List[float] = []
        for name in self._arm_names:
            n_i = self._adaptive_pulls[name]
            mean_i = self._total_rewards[name] / n_i
            if self._total_pulls > 1:
                exploration = self._c * math.sqrt(2.0 * math.log(self._total_pulls) / n_i)
            else:
                exploration = 0.0
            ucb_values.append(mean_i + exploration)

        max_ucb = max(ucb_values)
        best_candidates = [
            name
            for name, val in zip(self._arm_names, ucb_values)
            if val == max_ucb or (math.isinf(max_ucb) and math.isinf(val))
        ]

        if len(best_candidates) == 1:
            return best_candidates[0]

        return self._rng.choice(best_candidates)

    def update(self, arm_name: str, reward: float) -> None:
        if arm_name not in self._total_counts:
            raise KeyError(f"Unknown arm '{arm_name}'")
        if isinstance(reward, bool) or not isinstance(reward, (int, float)) or not math.isfinite(reward):
            raise ValueError(f"reward must be a finite real number, got {reward!r}")

        rew = float(reward)
        self._total_pulls += 1
        self._total_counts[arm_name] += 1
        self._adaptive_pulls[arm_name] += 1
        self._total_rewards[arm_name] += rew
        self._initialized_arms.add(arm_name)

    def initialize_arm(self, arm_name: str) -> None:
        if arm_name not in self._total_counts:
            raise KeyError(f"Unknown arm '{arm_name}'")
        self._initialized_arms.add(arm_name)

    def is_arm_initialized(self, arm_name: str) -> bool:
        if arm_name not in self._total_counts:
            raise KeyError(f"Unknown arm '{arm_name}'")
        return arm_name in self._initialized_arms

    def get_adaptive_pulls(self, arm_name: str) -> int:
        if arm_name not in self._adaptive_pulls:
            raise KeyError(f"Unknown arm '{arm_name}'")
        return self._adaptive_pulls[arm_name]

    def is_in_initial_probe(self, arm_name: str) -> bool:
        if arm_name not in self._adaptive_pulls:
            raise KeyError(f"Unknown arm '{arm_name}'")
        return self._adaptive_pulls[arm_name] == 0

    @property
    def is_initial_probe_complete(self) -> bool:
        return all(count > 0 for count in self._adaptive_pulls.values())

    def get_stats(self) -> Dict[str, ArmStats]:
        stats: Dict[str, ArmStats] = {}
        for name in self._arm_names:
            n_i = self._adaptive_pulls[name]
            if n_i == 0:
                mean_i = 0.0
                ucb_val = float("inf")
            else:
                mean_i = self._total_rewards[name] / n_i
                if self._total_pulls > 1:
                    exp = self._c * math.sqrt(2.0 * math.log(self._total_pulls) / n_i)
                else:
                    exp = 0.0
                ucb_val = mean_i + exp
            stats[name] = ArmStats(
                arm_name=name,
                total_pulls=self._total_counts[name],
                window_pulls=n_i,
                window_mean=mean_i,
                ucb=ucb_val,
            )
        return stats

    def reset(self) -> None:
        self._total_pulls = 0
        self._total_counts = {name: 0 for name in self._arm_names}
        self._adaptive_pulls = {name: 0 for name in self._arm_names}
        self._total_rewards = {name: 0.0 for name in self._arm_names}
        self._initialized_arms.clear()
        self._rng = random.Random(self._seed)
