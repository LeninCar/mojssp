"""Sequential change detection algorithms for non-stationary data streams.

This module provides standalone statistical change detectors, focusing on the
Page-Hinkley Test (PHT) for detecting shifts in the mean of real-valued sequential signals.
It is entirely decoupled from MO-JSSP domain logic, evaluators, and portfolio selectors.
"""

from dataclasses import dataclass
import math
from typing import Literal, Optional, Tuple


@dataclass(frozen=True)
class PageHinkleyState:
    """Defensive, immutable snapshot of the internal state of PageHinkleyDetector.

    Attributes:
        num_observations: Number of observations processed since the last reset.
        current_mean: Empirical mean of all observations since the last reset.
        cumulative_statistic: Current value of the cumulative deviation statistic m_t.
        reference_extremum: Reference extreme value (min m_t for upward/downward, max for Da Costa).
        alarm_statistic: Current non-negative test statistic PH_t compared against threshold lambda.
        change_detected: Boolean indicating whether an alarm was triggered on the most recent update.
        direction: Direction of change monitored ('down', 'up', or 'both').
        delta: Tolerance/drift parameter.
        threshold: Decision threshold lambda.
        min_instances: Minimum observations required before change detection is active.
    """

    num_observations: int
    current_mean: float
    cumulative_statistic: float
    reference_extremum: float
    alarm_statistic: float
    change_detected: bool
    direction: str
    delta: float
    threshold: float
    min_instances: int


class PageHinkleyDetector:
    """Sequential Page-Hinkley Test for detecting shifts in the mean of data streams.

    Formulation:
        Let x_1, x_2, ..., x_t be the incoming sequential observations.
        The cumulative sample mean is updated recursively:
            \\bar{x}_t = \\bar{x}_{t-1} + (x_t - \\bar{x}_{t-1}) / t

        Depending on the configured direction:

        1. Direction 'down' (detection of downward shift / collapse in mean):
           Under stationarity, (\\bar{x}_t - x_t) oscillates around 0.
           With tolerance \\delta > 0, the deviation increment is:
               e_t = (\\bar{x}_t - x_t) - \\delta
           Cumulative sum:
               m_t = m_{t-1} + e_t  (with m_0 = 0)
           Running minimum:
               M_t = \\min_{1 \\le i \\le t} m_i
           Test statistic:
               PH_t = m_t - M_t >= 0
           When a drop occurs (x_t < \\bar{x}_t), e_t becomes positive, causing m_t
           to increase above its running minimum M_t.

        2. Direction 'up' (detection of upward shift / jump in mean):
           The deviation increment is:
               e_t = (x_t - \\bar{x}_t) - \\delta
           Cumulative sum:
               m_t = m_{t-1} + e_t  (with m_0 = 0)
           Running minimum:
               M_t = \\min_{1 \\le i \\le t} m_i
           Test statistic:
               PH_t = m_t - M_t >= 0

        3. Direction 'both' (bilateral detection):
           Maintains two parallel accumulators (m_down, m_up) and evaluates:
               PH_t = \\max(PH_down, PH_up)

        Alarm Condition:
            If t >= min_instances and PH_t > threshold (\\lambda):
                change_detected = True

    State upon Alarm:
        By default, auto_reset=False preserves the alarm state and statistic until
        explicitly reset by the caller via reset(). If auto_reset=True, the detector
        resets its accumulators immediately upon triggering.
    """

    def __init__(
        self,
        delta: float = 0.001,
        threshold: float = 0.01,
        direction: Literal["down", "up", "both"] = "down",
        min_instances: int = 5,
        auto_reset: bool = False,
    ) -> None:
        """Initialize the Page-Hinkley detector with validation of mathematical parameters.

        Args:
            delta: Non-negative tolerance/drift parameter (\\delta >= 0.0).
            threshold: Positive decision threshold (\\lambda > 0.0).
            direction: Change direction to monitor ('down', 'up', or 'both'). Default: 'down'.
            min_instances: Minimum observations required before change detection is active (>= 1).
            auto_reset: Whether to automatically reset internal accumulators upon alarm.

        Raises:
            ValueError: If parameters violate mathematical constraints or contain NaN/Inf.
        """
        self._validate_params(delta, threshold, direction, min_instances)

        self._delta: float = float(delta)
        self._threshold: float = float(threshold)
        self._direction: Literal["down", "up", "both"] = direction
        self._min_instances: int = int(min_instances)
        self._auto_reset: bool = bool(auto_reset)

        # Internal state variables
        self._num_observations: int = 0
        self._current_mean: float = 0.0

        # Downward monitoring accumulators
        self._m_down: float = 0.0
        self._min_m_down: float = 0.0
        self._ph_down: float = 0.0

        # Upward monitoring accumulators
        self._m_up: float = 0.0
        self._min_m_up: float = 0.0
        self._ph_up: float = 0.0

        # Overall alarm state
        self._ph_stat: float = 0.0
        self._change_detected: bool = False

    @staticmethod
    def _validate_params(
        delta: float,
        threshold: float,
        direction: str,
        min_instances: int,
    ) -> None:
        """Validate detector parameters defensively."""
        if isinstance(delta, bool) or not isinstance(delta, (int, float)):
            raise ValueError(f"delta must be a real number, got {delta!r}")
        if not math.isfinite(delta) or delta < 0.0:
            raise ValueError(f"delta must be a finite real number >= 0.0, got {delta!r}")

        if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
            raise ValueError(f"threshold must be a real number, got {threshold!r}")
        if not math.isfinite(threshold) or threshold <= 0.0:
            raise ValueError(f"threshold must be a finite real number > 0.0, got {threshold!r}")

        if direction not in ("down", "up", "both"):
            raise ValueError(f"direction must be one of ('down', 'up', 'both'), got {direction!r}")

        if isinstance(min_instances, bool) or not isinstance(min_instances, int):
            raise ValueError(f"min_instances must be an integer, got {min_instances!r}")
        if min_instances < 1:
            raise ValueError(f"min_instances must be an integer >= 1, got {min_instances!r}")

    @property
    def delta(self) -> float:
        """The drift/tolerance parameter delta."""
        return self._delta

    @property
    def threshold(self) -> float:
        """The detection threshold lambda."""
        return self._threshold

    @property
    def direction(self) -> str:
        """The monitored change direction ('down', 'up', or 'both')."""
        return self._direction

    @property
    def min_instances(self) -> int:
        """The minimum observation count before detection becomes active."""
        return self._min_instances

    @property
    def auto_reset(self) -> bool:
        """Whether auto-reset upon alarm is enabled."""
        return self._auto_reset

    @property
    def num_observations(self) -> int:
        """Total number of observations ingested since the last reset."""
        return self._num_observations

    @property
    def current_mean(self) -> float:
        """Empirical mean of all observations since the last reset."""
        return self._current_mean

    @property
    def alarm_statistic(self) -> float:
        """Current value of the test statistic PH_t."""
        return self._ph_stat

    @property
    def change_detected(self) -> bool:
        """Whether a change was detected on the most recent update."""
        return self._change_detected

    def update(self, value: float) -> bool:
        """Ingest a new scalar observation and update the detector state.

        Args:
            value: Finite real observation from the sequential data stream.

        Returns:
            Boolean indicating whether a change was detected (True if alarm triggered).

        Raises:
            ValueError: If value is not a finite real number (NaN or +/-Inf).
        """
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"Observation must be a finite real number, got {value!r}")

        val = float(value)
        self._num_observations += 1
        t = self._num_observations

        # Recursive update of the sample mean
        # \bar{x}_t = \bar{x}_{t-1} + (x_t - \bar{x}_{t-1}) / t
        prev_mean = self._current_mean
        self._current_mean = prev_mean + (val - prev_mean) / t
        cur_mean = self._current_mean

        # 1. Downward shift accumulator
        if self._direction in ("down", "both"):
            # Deviation: (mean - value) - delta
            e_down = (cur_mean - val) - self._delta
            self._m_down += e_down
            if self._m_down < self._min_m_down:
                self._min_m_down = self._m_down
            self._ph_down = self._m_down - self._min_m_down

        # 2. Upward shift accumulator
        if self._direction in ("up", "both"):
            # Deviation: (value - mean) - delta
            e_up = (val - cur_mean) - self._delta
            self._m_up += e_up
            if self._m_up < self._min_m_up:
                self._min_m_up = self._m_up
            self._ph_up = self._m_up - self._min_m_up

        # 3. Overall statistic
        if self._direction == "down":
            self._ph_stat = self._ph_down
        elif self._direction == "up":
            self._ph_stat = self._ph_up
        else:  # 'both'
            self._ph_stat = max(self._ph_down, self._ph_up)

        # 4. Alarm condition
        if t >= self._min_instances and self._ph_stat > self._threshold:
            self._change_detected = True
        else:
            self._change_detected = False

        alarm = self._change_detected

        # Auto-reset if configured
        if alarm and self._auto_reset:
            self.reset()
            # Restore alarm flag for the return value of this step
            self._change_detected = True

        return alarm

    def get_state(self) -> PageHinkleyState:
        """Return an immutable defensive snapshot of the internal detector state."""
        if self._direction == "down":
            cum_stat = self._m_down
            ref_ext = self._min_m_down
        elif self._direction == "up":
            cum_stat = self._m_up
            ref_ext = self._min_m_up
        else:
            cum_stat = self._m_down if self._ph_down >= self._ph_up else self._m_up
            ref_ext = self._min_m_down if self._ph_down >= self._ph_up else self._min_m_up

        return PageHinkleyState(
            num_observations=self._num_observations,
            current_mean=self._current_mean,
            cumulative_statistic=cum_stat,
            reference_extremum=ref_ext,
            alarm_statistic=self._ph_stat,
            change_detected=self._change_detected,
            direction=self._direction,
            delta=self._delta,
            threshold=self._threshold,
            min_instances=self._min_instances,
        )

    def reset(self) -> None:
        """Reset internal accumulators, sample mean, and alarm state to initial conditions."""
        self._num_observations = 0
        self._current_mean = 0.0

        self._m_down = 0.0
        self._min_m_down = 0.0
        self._ph_down = 0.0

        self._m_up = 0.0
        self._min_m_up = 0.0
        self._ph_up = 0.0

        self._ph_stat = 0.0
        self._change_detected = False
