"""Reward evaluation for the MO-JSSP algorithm portfolio based on Hypervolume improvement.

Phase 7.5 implementation providing HypervolumeRewardTracker to compute
reward = HV_after - HV_before from the Global Pareto Archive.
"""

from typing import Optional, Tuple

from .hypervolume import DEFAULT_REFERENCE_POINT, compute_archive_hypervolume
from .normalization import ObjectiveNormalizer
from .pareto_archive import ParetoArchive


class RewardInvariantError(ValueError):
    """Raised when the cumulative archive hypervolume decreases beyond numerical tolerance."""

    pass


class HypervolumeRewardTracker:
    """Tracks and evaluates rewards based on cumulative Hypervolume improvement.

    Calculates:
        reward_t = HV_after_t - HV_before_t
    where HV_before_t = HV_after_(t-1), and HV_before_0 = 0.0.

    Ensures read-only access to the ParetoArchive and explicit handling of micro-numerical
    floating-point fluctuations without silent clipping of real invariant violations.
    """

    def __init__(
        self,
        normalizer: ObjectiveNormalizer,
        reference_point: Tuple[float, float, float] = DEFAULT_REFERENCE_POINT,
        tolerance: float = 1e-12,
    ) -> None:
        """Initialize the HypervolumeRewardTracker.

        Args:
            normalizer: ObjectiveNormalizer configured with instance bounds.
            reference_point: 3D reference point in normalized space (default: (1.1, 1.1, 1.1)).
            tolerance: Numerical tolerance for floating-point comparisons (default: 1e-12).

        Raises:
            TypeError: If normalizer is not an instance of ObjectiveNormalizer.
            ValueError: If reference_point does not have 3 coordinates or tolerance < 0.
        """
        if not isinstance(normalizer, ObjectiveNormalizer):
            raise TypeError(
                f"normalizer must be an instance of ObjectiveNormalizer, got {type(normalizer)}"
            )

        if len(reference_point) != 3:
            raise ValueError(
                f"reference_point must have 3 dimensions, got {len(reference_point)}"
            )

        if tolerance < 0.0:
            raise ValueError(f"tolerance must be non-negative, got {tolerance}")

        self._normalizer = normalizer
        self._reference_point = (
            float(reference_point[0]),
            float(reference_point[1]),
            float(reference_point[2]),
        )
        self._tolerance = float(tolerance)
        self._previous_hv: float = 0.0

    @property
    def current_hv(self) -> float:
        """The hypervolume of the most recently evaluated archive state."""
        return self._previous_hv

    @property
    def normalizer(self) -> ObjectiveNormalizer:
        """The underlying objective normalizer."""
        return self._normalizer

    @property
    def reference_point(self) -> Tuple[float, float, float]:
        """The reference point in normalized objective space."""
        return self._reference_point

    @property
    def tolerance(self) -> float:
        """The numerical tolerance used for boundary checks."""
        return self._tolerance

    def compute_reward(self, archive: ParetoArchive) -> float:
        """Compute the hypervolume delta (HV_after - HV_before) for the given archive.

        The archive is accessed strictly in read-only mode and is never mutated.

        Args:
            archive: The Global Pareto Archive to evaluate.

        Returns:
            The non-negative hypervolume delta reward.

        Raises:
            TypeError: If archive is not a ParetoArchive instance.
            RewardInvariantError: If HV_after < HV_before beyond the numerical tolerance.
        """
        if not isinstance(archive, ParetoArchive):
            raise TypeError(
                f"archive must be an instance of ParetoArchive, got {type(archive)}"
            )

        if archive.is_empty:
            hv_after = 0.0
        else:
            hv_after = compute_archive_hypervolume(
                archive,
                self._normalizer,
                reference_point=self._reference_point,
            )

        delta = hv_after - self._previous_hv

        # Handle micro numerical fluctuations within tolerance
        if -self._tolerance <= delta < 0.0:
            # The archive mathematically did not degrade; treat as exact 0.0
            delta = 0.0
            hv_after = self._previous_hv
        elif delta < -self._tolerance:
            raise RewardInvariantError(
                f"Hypervolume monotonicity invariant violated: HV decreased from "
                f"{self._previous_hv:.10e} to {hv_after:.10e} "
                f"(delta = {delta:.10e} < -{self._tolerance:.10e})"
            )

        self._previous_hv = hv_after
        return float(delta)

    def reset(self) -> None:
        """Reset the tracker's state so the next call behaves like the first execution."""
        self._previous_hv = 0.0
