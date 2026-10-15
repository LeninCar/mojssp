"""Input loader for MO-JSSP instances from MiniZinc .dzn data files."""

import re
from pathlib import Path
from typing import List, Tuple, Union
from .instance import Instance
from .job import Job
from .mode import ProcessingMode
from .operation import Operation
from .validator import validate_instance


def _clean_comments(content: str) -> str:
    """Remove line comments starting with %."""
    return re.sub(r"%.*", "", content)


def _parse_dzn_int_scalar(content: str, var_name: str) -> int:
    """Extract a scalar integer or range length like 'JOBS = 1..2;' or 'SPEED = 2;'."""
    cleaned = _clean_comments(content)
    pattern_range = rf"\b{var_name}\b\s*=\s*(\d+)\.\.(\d+)\s*;"
    m_range = re.search(pattern_range, cleaned)
    if m_range:
        start, end = int(m_range.group(1)), int(m_range.group(2))
        return end - start + 1

    pattern_scalar = rf"\b{var_name}\b\s*=\s*(\d+)\s*;"
    m_scalar = re.search(pattern_scalar, cleaned)
    if m_scalar:
        return int(m_scalar.group(1))

    raise ValueError(f"Could not parse parameter '{var_name}' from .dzn content.")


def _parse_dzn_numbers_in_brackets(content: str, array_name: str) -> List[int]:
    """Extract flat integer array from something like array_name = ... [ ... ];"""
    cleaned = _clean_comments(content)
    pattern = rf"\b{array_name}\b\s*=\s*.*?\[(.*?)\]"
    m = re.search(pattern, cleaned, re.DOTALL)
    if not m:
        raise ValueError(f"Could not parse array '{array_name}' from .dzn content.")
    raw_nums = re.findall(r"-?\d+", m.group(1))
    return [int(x) for x in raw_nums]


def load_dzn(file_path: Union[str, Path], validate: bool = True) -> Instance:
    """Load an instance from a MiniZinc .dzn file following the JSP2 format.

    In the MiniZinc reference format:
    - JOBS = 1..n
    - MACHINES = 1..m
    - SPEED = s
    - time, energy are 3D arrays [JOBS, MACHINES, 1..SPEED]
    - precedence, releaseDate, dueDate are 2D arrays [JOBS, MACHINES]

    Methodological adaptation:
    - In this thesis, tardiness is defined per job with due date d_j.
    - If dueDate is present in the .dzn, d_j is set to the due date of the final
      operation in the technological route of job j.
    - If releaseDate is present, r_{j,k} is assigned to each operation.

    Args:
        file_path: Path to the .dzn file.
        validate: Whether to execute semantic validation after loading.

    Returns:
        Instance object.
    """
    path = Path(file_path)
    content = path.read_text(encoding="utf-8")

    num_jobs = _parse_dzn_int_scalar(content, "JOBS")
    num_machines = _parse_dzn_int_scalar(content, "MACHINES")
    num_speeds = _parse_dzn_int_scalar(content, "SPEED")

    raw_times = _parse_dzn_numbers_in_brackets(content, "time")
    raw_energies = _parse_dzn_numbers_in_brackets(content, "energy")
    raw_precedence = _parse_dzn_numbers_in_brackets(content, "precedence")

    raw_release = None
    try:
        raw_release = _parse_dzn_numbers_in_brackets(content, "releaseDate")
    except ValueError:
        raw_release = [0] * (num_jobs * num_machines)

    raw_due = None
    try:
        raw_due = _parse_dzn_numbers_in_brackets(content, "dueDate")
    except ValueError:
        raw_due = [0] * (num_jobs * num_machines)

    expected_3d = num_jobs * num_machines * num_speeds
    if len(raw_times) != expected_3d:
        raise ValueError(f"Expected {expected_3d} values in 'time' array, got {len(raw_times)}.")
    if len(raw_energies) != expected_3d:
        raise ValueError(f"Expected {expected_3d} values in 'energy' array, got {len(raw_energies)}.")

    expected_2d = num_jobs * num_machines
    if len(raw_precedence) != expected_2d:
        raise ValueError(f"Expected {expected_2d} values in 'precedence' array, got {len(raw_precedence)}.")

    jobs_list: List[Job] = []

    for j in range(num_jobs):
        job_tasks = []
        for m in range(num_machines):
            idx_2d = j * num_machines + m
            prec = raw_precedence[idx_2d]
            rel_date = raw_release[idx_2d] if raw_release else 0
            due_d = raw_due[idx_2d] if raw_due else 0

            modes: List[ProcessingMode] = []
            for s in range(num_speeds):
                idx_3d = (j * num_machines + m) * num_speeds + s
                duration = raw_times[idx_3d]
                energy = float(raw_energies[idx_3d])
                modes.append(ProcessingMode(mode_id=s + 1, duration=duration, energy=energy))

            job_tasks.append((prec, m + 1, tuple(modes), rel_date, due_d))

        # Sort operations of this job by precedence order
        job_tasks.sort(key=lambda t: t[0])

        operations_for_job: List[Operation] = []
        for op_idx, (_, machine_id, modes, rel_date, _) in enumerate(job_tasks):
            operations_for_job.append(
                Operation(
                    job_id=j + 1,
                    op_id=op_idx + 1,  # 1-based sequential op_id
                    machine_id=machine_id,
                    modes=modes,
                    release_date=rel_date,
                )
            )

        # Adaptación metodológica de dueDate:
        # En JSP2.mzn, dueDate se definió como matriz 2D [JOBS, MACHINES].
        # En esta tesis, la fecha de entrega d_j es por trabajo.
        # Comprobamos si las tareas del trabajo comparten la misma due date o tomamos la de la última tarea.
        job_due_dates = [task[4] for task in job_tasks]
        if len(set(job_due_dates)) == 1:
            job_due_date = job_due_dates[0]
        else:
            # Si difieren entre operaciones, la fecha de entrega del trabajo corresponde a la de su última operación
            job_due_date = job_tasks[-1][4]

        jobs_list.append(
            Job(
                job_id=j + 1,
                operations=tuple(operations_for_job),
                due_date=job_due_date,
            )
        )

    instance = Instance(
        name=path.stem,
        num_jobs=num_jobs,
        num_machines=num_machines,
        jobs=tuple(jobs_list),
        metadata={"source_file": str(path), "format": "dzn", "num_speeds": num_speeds},
    )

    if validate:
        validate_instance(instance)

    return instance
