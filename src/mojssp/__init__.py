"""MO-JSSP domain package.

Multi-Objective Job Shop Scheduling Problem with Speed Scaling.
"""

from .model.mode import ProcessingMode
from .model.operation import Operation
from .model.job import Job
from .model.instance import Instance
from .model.validator import validate_instance, ValidationError
from .model.io import load_dzn
from .model.solution import Solution
from .model.schedule import ScheduledOperation, Schedule
from .model.decoder import Decoder, decode
from .model.evaluator import ObjectiveValues, Evaluator, evaluate
from .model.schedule_validator import (
    ScheduleValidationError,
    ScheduleValidator,
    validate_schedule,
)
from .algorithms.nsga2 import NSGA2, NSGA2Result, nsga2
from .metrics.dominance import dominates
from .metrics.pareto_archive import ArchiveEntry, ParetoArchive
from .metrics.normalization import (
    NormalizationBoundError,
    ObjectiveBounds,
    ObjectiveNormalizer,
    compute_instance_bounds,
)
from .metrics.hypervolume import (
    DEFAULT_REFERENCE_POINT,
    compute_hypervolume,
    compute_archive_hypervolume,
)
from .model.critical_path import (
    get_critical_operations,
    map_operation_to_sequence_index,
    get_critical_sequence_indices,
)
from .algorithms.local_search import (
    ArchiveAddResult,
    LocalParetoArchive,
    LocalSearch,
    LocalSearchResult,
)
from .algorithms.nsga2_ls import (
    NSGA2LS,
    NSGA2LSResult,
    nsga2_ls,
)
from .algorithms.mopso import (
    MOPSO,
    MOPSOResult,
    mopso,
    PersonalParetoArchive,
)
from .algorithms.algorithm_contract import (
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
from .algorithms.moead import (
    MOEAD,
    MOEADResult,
    MOEADArm,
    moead,
    generate_simplex_lattice_weights,
    generate_uniform_weights,
    tchebycheff_scalarizing,
)
from .algorithms.spea2 import (
    SPEA2,
    SPEA2Result,
    SPEA2Arm,
    spea2,
    calculate_spea2_fitness,
    environmental_selection,
)
from .algorithms.arms import ActiveLSState, MOPSOArm, NSGA2Arm, NSGA2LSArm
from .portfolio.portfolio import Portfolio, PortfolioBlockResult
from .portfolio.dmab import (
    ArmStats,
    DMABSelector,
    RoundRobinSelector,
    SlidingWindowUCB,
    UniformRandomSelector,
)
from .metrics.reward import HypervolumeRewardTracker, RewardInvariantError
from .portfolio.orchestrator import (
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
    "BlockExecutionRecord",
    "AdaptiveExecutionResult",
    "AdaptivePortfolioOrchestrator",
]


from .portfolio.page_hinkley import PageHinkleyDMABSelector, PageHinkleyAlarmRecord
