"""MO-JSSP domain package.

Multi-Objective Job Shop Scheduling Problem with Speed Scaling.
"""

from .mode import ProcessingMode
from .operation import Operation
from .job import Job
from .instance import Instance
from .validator import validate_instance, ValidationError
from .io import load_dzn
from .solution import Solution
from .schedule import ScheduledOperation, Schedule
from .decoder import Decoder, decode
from .evaluator import ObjectiveValues, Evaluator, evaluate
from .schedule_validator import (
    ScheduleValidationError,
    ScheduleValidator,
    validate_schedule,
)
from .nsga2 import NSGA2, NSGA2Result, nsga2
from .dominance import dominates
from .pareto_archive import ArchiveEntry, ParetoArchive
from .normalization import (
    NormalizationBoundError,
    ObjectiveBounds,
    ObjectiveNormalizer,
    compute_instance_bounds,
)
from .hypervolume import (
    DEFAULT_REFERENCE_POINT,
    compute_hypervolume,
    compute_archive_hypervolume,
)
from .critical_path import (
    get_critical_operations,
    map_operation_to_sequence_index,
    get_critical_sequence_indices,
)
from .local_search import (
    ArchiveAddResult,
    LocalParetoArchive,
    LocalSearch,
    LocalSearchResult,
)
from .nsga2_ls import (
    NSGA2LS,
    NSGA2LSResult,
    nsga2_ls,
)
from .mopso import (
    MOPSO,
    MOPSOResult,
    mopso,
    PersonalParetoArchive,
)
from .algorithm_contract import (
    AlgorithmResult,
    OptimizationAlgorithm,
    NSGA2Adapter,
    NSGA2LSAdapter,
    MOPSOAdapter,
    MOEADAdapter,
    SPEA2Adapter,
    AlgorithmBlockResult,
    PortfolioArm,
)
from .moead import (
    MOEAD,
    MOEADResult,
    MOEADArm,
    moead,
    generate_simplex_lattice_weights,
    generate_uniform_weights,
    tchebycheff_scalarizing,
)
from .spea2 import (
    SPEA2,
    SPEA2Result,
    SPEA2Arm,
    spea2,
    calculate_spea2_fitness,
    environmental_selection,
)
from .arms import ActiveLSState, MOPSOArm, NSGA2Arm, NSGA2LSArm
from .portfolio import Portfolio, PortfolioBlockResult
from .dmab import (
    ArmStats,
    DMABSelector,
    RoundRobinSelector,
    SlidingWindowUCB,
    UniformRandomSelector,
)
from .reward import HypervolumeRewardTracker, RewardInvariantError
from .igd import (
    build_empirical_reference_front,
    compute_archive_contribution_rate,
    compute_archive_igd,
    compute_archive_igd_plus,
    compute_contribution_rate,
    compute_euclidean_distance,
    compute_igd,
    compute_igd_plus,
    compute_modified_distance,
    filter_non_dominated_points,
)
from .orchestrator import (
    AdaptiveExecutionResult,
    AdaptivePortfolioOrchestrator,
    BlockExecutionRecord,
)
try:
    from .pairing import (
        CheckResult,
        RawDznData,
        ReferenceSample,
        ValidationReport,
        derive_btnk_high,
        derive_nrg_strong,
        derive_tard_high,
        derive_tard_med,
        derive_tardiness_variant,
        format_validation_report,
        generate_reference_sample,
        read_dzn_raw,
        validate_pairing,
        write_dzn_raw,
    )
    _PAIRING_SYMBOLS = [
        "RawDznData",
        "ReferenceSample",
        "read_dzn_raw",
        "write_dzn_raw",
        "generate_reference_sample",
        "derive_tardiness_variant",
        "derive_tard_high",
        "derive_tard_med",
        "derive_nrg_strong",
        "derive_btnk_high",
        "validate_pairing",
        "ValidationReport",
        "CheckResult",
        "format_validation_report",
    ]
except ModuleNotFoundError as _err:
    if _err.name not in (f"{__name__}.pairing", "mojssp.pairing"):
        raise
    _PAIRING_SYMBOLS = []


__all__ = _PAIRING_SYMBOLS + [
    "ProcessingMode",
    "Operation",
    "Job",
    "Instance",
    "validate_instance",
    "ValidationError",
    "load_dzn",
    "Solution",
    "ScheduledOperation",
    "Schedule",
    "Decoder",
    "decode",
    "ObjectiveValues",
    "Evaluator",
    "evaluate",
    "ScheduleValidationError",
    "ScheduleValidator",
    "validate_schedule",
    "NSGA2",
    "NSGA2Result",
    "nsga2",
    "dominates",
    "ArchiveEntry",
    "ParetoArchive",
    "NormalizationBoundError",
    "ObjectiveBounds",
    "ObjectiveNormalizer",
    "compute_instance_bounds",
    "DEFAULT_REFERENCE_POINT",
    "compute_hypervolume",
    "compute_archive_hypervolume",
    "get_critical_operations",
    "map_operation_to_sequence_index",
    "get_critical_sequence_indices",
    "ArchiveAddResult",
    "LocalParetoArchive",
    "LocalSearch",
    "LocalSearchResult",
    "NSGA2LS",
    "NSGA2LSResult",
    "nsga2_ls",
    "MOPSO",
    "MOPSOResult",
    "mopso",
    "PersonalParetoArchive",
    "AlgorithmResult",
    "OptimizationAlgorithm",
    "NSGA2Adapter",
    "NSGA2LSAdapter",
    "MOPSOAdapter",
    "MOEADAdapter",
    "MOEAD",
    "MOEADResult",
    "moead",
    "MOEADArm",
    "generate_simplex_lattice_weights",
    "generate_uniform_weights",
    "tchebycheff_scalarizing",
    "SPEA2Adapter",
    "SPEA2",
    "SPEA2Result",
    "spea2",
    "SPEA2Arm",
    "calculate_spea2_fitness",
    "environmental_selection",
    "AlgorithmBlockResult",
    "PortfolioArm",
    "NSGA2Arm",
    "MOPSOArm",
    "ActiveLSState",
    "NSGA2LSArm",
    "Portfolio",
    "PortfolioBlockResult",
    "ArmStats",
    "DMABSelector",
    "SlidingWindowUCB",
    "RoundRobinSelector",
    "UniformRandomSelector",
    "RewardInvariantError",
    "HypervolumeRewardTracker",
    "compute_euclidean_distance",
    "compute_igd",
    "compute_archive_igd",
    "compute_modified_distance",
    "compute_igd_plus",
    "compute_archive_igd_plus",
    "compute_contribution_rate",
    "compute_archive_contribution_rate",
    "filter_non_dominated_points",
    "build_empirical_reference_front",
    "BlockExecutionRecord",
    "AdaptiveExecutionResult",
    "AdaptivePortfolioOrchestrator",
]










