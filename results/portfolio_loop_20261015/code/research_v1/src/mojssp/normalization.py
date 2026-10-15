"""Objective normalization and instance bounds computation for MO-JSSP."""

from dataclasses import dataclass
from typing import List, Tuple, Union

from .evaluator import ObjectiveValues
from .instance import Instance
from .pareto_archive import ParetoArchive


class NormalizationBoundError(ValueError):
    """Raised when an objective value is outside the allowed bounds beyond numerical tolerance."""

    pass


@dataclass(frozen=True)
class ObjectiveBounds:
    """Fixed, immutable bounds for the three MO-JSSP objectives.

    Attributes:
        cmax_min: Lower bound for makespan (Cmax).
        cmax_max: Upper bound for makespan (Cmax).
        tardiness_min: Lower bound for total tardiness (T).
        tardiness_max: Upper bound for total tardiness (T).
        energy_min: Lower bound for energy consumption (E).
        energy_max: Upper bound for energy consumption (E).
    """

    cmax_min: float
    cmax_max: float
    tardiness_min: float
    tardiness_max: float
    energy_min: float
    energy_max: float

    def __post_init__(self) -> None:
        """Validate that all bounds are non-negative and lower <= upper."""
        if self.cmax_min < 0 or self.cmax_max < self.cmax_min:
            raise ValueError(
                f"Invalid makespan bounds: [{self.cmax_min}, {self.cmax_max}]. "
                "Must satisfy 0 <= cmax_min <= cmax_max."
            )
        if self.tardiness_min < 0 or self.tardiness_max < self.tardiness_min:
            raise ValueError(
                f"Invalid tardiness bounds: [{self.tardiness_min}, {self.tardiness_max}]. "
                "Must satisfy 0 <= tardiness_min <= tardiness_max."
            )
        if self.energy_min < 0 or self.energy_max < self.energy_min:
            raise ValueError(
                f"Invalid energy bounds: [{self.energy_min}, {self.energy_max}]. "
                "Must satisfy 0 <= energy_min <= energy_max."
            )


def compute_instance_bounds(instance: Instance) -> ObjectiveBounds:
    """Compute conservative, instance-derived objective bounds for MO-JSSP.

    Methodological justification:
        - Makespan lower bound (Cmin): The maximum over all operations (j, k) of
          (release_{j,k} + sum_{h=k}^{n_j} duration^{min}_{j,h}). This accounts for
          operations within the same job having differing release dates, ensuring a
          strictly valid lower bound on the completion time of every job in isolation.
        - Makespan upper bound (Cmax_bound): Deliberately conservative upper bound
          derived from a serial execution horizon where all operations are scheduled
          one after another with their maximum duration after the latest release date.
        - Energy bounds: The sum of minimum (resp. maximum) energy modes over all operations.
        - Tardiness bounds: Tmin is 0.0, and Tmax is the sum of max(0, Cmax_bound - due_date)
          over all jobs.

    Args:
        instance: The MO-JSSP instance.

    Returns:
        ObjectiveBounds with valid, immutable bounds.
    """
    # 1. Operation-level min/max durations and energies
    op_min_duration = {}
    op_max_duration = {}
    op_min_energy = {}
    op_max_energy = {}

    for op in instance.all_operations:
        key = (op.job_id, op.op_id)
        op_min_duration[key] = min(m.duration for m in op.modes)
        op_max_duration[key] = max(m.duration for m in op.modes)
        op_min_energy[key] = min(m.energy for m in op.modes)
        op_max_energy[key] = max(m.energy for m in op.modes)

    # 2. Makespan lower bound: max_{j} max_{k} (release_{j,k} + sum_{h=k}^{n_j} min_duration_{j,h})
    op_lbs = []
    for job in instance.jobs:
        n_j = len(job.operations)
        for k in range(n_j):
            op_k = job.operations[k]
            remaining_min_duration = sum(
                op_min_duration[(job.operations[h].job_id, job.operations[h].op_id)]
                for h in range(k, n_j)
            )
            lb_jk = op_k.release_date + remaining_min_duration
            op_lbs.append(lb_jk)

    cmax_min = float(max(op_lbs)) if op_lbs else 0.0

    # 3. Makespan upper bound: max release date + sum of all max durations
    max_release = max((op.release_date for op in instance.all_operations), default=0)
    total_max_duration = sum(
        op_max_duration[(op.job_id, op.op_id)] for op in instance.all_operations
    )
    cmax_max = float(max_release + total_max_duration)

    # 4. Energy bounds
    energy_min = float(
        sum(op_min_energy[(op.job_id, op.op_id)] for op in instance.all_operations)
    )
    energy_max = float(
        sum(op_max_energy[(op.job_id, op.op_id)] for op in instance.all_operations)
    )

    # 5. Tardiness bounds
    tardiness_min = 0.0
    tardiness_max = float(
        sum(max(0.0, cmax_max - float(job.due_date)) for job in instance.jobs)
    )

    return ObjectiveBounds(
        cmax_min=cmax_min,
        cmax_max=cmax_max,
        tardiness_min=tardiness_min,
        tardiness_max=tardiness_max,
        energy_min=energy_min,
        energy_max=energy_max,
    )


class ObjectiveNormalizer:
    """Normalizes MO-JSSP objective values into [0, 1]^3 using fixed instance bounds.

    Strict bounding policy:
        - Real violations where f < lower - tolerance or f > upper + tolerance
          raise NormalizationBoundError.
        - Silent clipping of arbitrary out-of-bounds values is strictly prohibited.
        - Numerical errors within tolerance (e.g. from floating-point arithmetic)
          are mapped coherently to 0.0 or 1.0.
    """

    def __init__(self, bounds: ObjectiveBounds, tolerance: float = 1e-7) -> None:
        """Initialize the normalizer with fixed bounds and floating-point tolerance.

        Args:
            bounds: The fixed ObjectiveBounds.
            tolerance: Numerical tolerance for floating-point comparisons (default 1e-7).
        """
        if tolerance < 0:
            raise ValueError(f"Tolerance must be non-negative, got {tolerance}")
        self._bounds = bounds
        self._tolerance = tolerance

    @property
    def bounds(self) -> ObjectiveBounds:
        """The underlying objective bounds."""
        return self._bounds

    @property
    def tolerance(self) -> float:
        """The numerical tolerance used for boundary checks."""
        return self._tolerance

    def _normalize_value(self, val: float, lower: float, upper: float, name: str) -> float:
        """Normalize a single scalar value into [0, 1] with strict bounds enforcement."""
        # Check for real violations beyond tolerance
        if val < lower - self._tolerance:
            raise NormalizationBoundError(
                f"{name} value {val} is below lower bound {lower} "
                f"(tolerance: {self._tolerance})"
            )
        if val > upper + self._tolerance:
            raise NormalizationBoundError(
                f"{name} value {val} is above upper bound {upper} "
                f"(tolerance: {self._tolerance})"
            )

        # Handle degenerate case where upper == lower
        if upper == lower:
            return 0.0

        # Coherent handling of micro numerical imprecisions within tolerance
        if val < lower:
            return 0.0
        if val > upper:
            return 1.0

        norm_val = (val - lower) / (upper - lower)
        # Prevent micro precision overflow/underflow artifacts
        if norm_val < 0.0:
            norm_val = 0.0
        elif norm_val > 1.0:
            norm_val = 1.0
        return norm_val

    def normalize_tuple(
        self, objectives: Union[Tuple[float, float, float], ObjectiveValues]
    ) -> Tuple[float, float, float]:
        """Normalize an objective vector into [0, 1]^3.

        Args:
            objectives: Either an ObjectiveValues instance or a 3-tuple (cmax, tardiness, energy).

        Returns:
            A tuple of (cmax_norm, tardiness_norm, energy_norm) in [0, 1]^3.

        Raises:
            NormalizationBoundError: If any objective value is strictly out of bounds.
            TypeError: If the input is not a 3-element tuple or ObjectiveValues.
        """
        if isinstance(objectives, ObjectiveValues):
            cmax = float(objectives.makespan)
            tardiness = float(objectives.tardiness)
            energy = float(objectives.energy)
        elif hasattr(objectives, "__len__") and len(objectives) == 3:
            cmax = float(objectives[0])
            tardiness = float(objectives[1])
            energy = float(objectives[2])
        else:
            raise TypeError(
                f"Expected 3-element tuple or ObjectiveValues, got {type(objectives)}"
            )

        cmax_norm = self._normalize_value(
            cmax, self._bounds.cmax_min, self._bounds.cmax_max, "makespan"
        )
        tardiness_norm = self._normalize_value(
            tardiness, self._bounds.tardiness_min, self._bounds.tardiness_max, "tardiness"
        )
        energy_norm = self._normalize_value(
            energy, self._bounds.energy_min, self._bounds.energy_max, "energy"
        )
        return (cmax_norm, tardiness_norm, energy_norm)

    def denormalize_tuple(
        self, normalized: Tuple[float, float, float]
    ) -> Tuple[float, float, float]:
        """Denormalize a [0, 1]^3 objective vector back to original problem scale.

        Args:
            normalized: A 3-tuple of normalized objective values.

        Returns:
            A 3-tuple of original objective values (cmax, tardiness, energy).
        """
        if len(normalized) != 3:
            raise ValueError(f"Expected 3-element normalized tuple, got {len(normalized)}")

        cmax_norm, tardiness_norm, energy_norm = (
            float(normalized[0]),
            float(normalized[1]),
            float(normalized[2]),
        )
        cmax = self._bounds.cmax_min + cmax_norm * (
            self._bounds.cmax_max - self._bounds.cmax_min
        )
        tardiness = self._bounds.tardiness_min + tardiness_norm * (
            self._bounds.tardiness_max - self._bounds.tardiness_min
        )
        energy = self._bounds.energy_min + energy_norm * (
            self._bounds.energy_max - self._bounds.energy_min
        )
        return (cmax, tardiness, energy)

    def normalize_archive(
        self, archive: ParetoArchive
    ) -> List[Tuple[float, float, float]]:
        """Normalize all non-dominated objective vectors contained in a ParetoArchive.

        Args:
            archive: The ParetoArchive instance.

        Returns:
            List of 3-tuples normalized in [0, 1]^3.
        """
        return [self.normalize_tuple(entry.objectives) for entry in archive.entries]

