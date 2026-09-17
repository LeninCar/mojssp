"""Representation of an operational processing mode (speed/mode scaling)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProcessingMode:
    """Processing mode of an operation, characterizing its duration and energy consumption.

    Attributes:
        mode_id: Identifier of the mode (e.g. 1, 2, ... corresponding to available speed/processing modes).
        duration: Processing time required under this mode (must be strictly positive).
        energy: Energy consumed when executing under this mode (must be non-negative).
    """

    mode_id: int
    duration: int
    energy: float

    def __post_init__(self) -> None:
        if self.duration <= 0:
            raise ValueError(f"duration must be strictly positive, got {self.duration}")
        if self.energy < 0:
            raise ValueError(f"energy must be non-negative, got {self.energy}")
