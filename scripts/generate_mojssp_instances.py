"""Generator script for 25 diverse MO-JSSP instances (Phase F8.6.3).

Generates MiniZinc .dzn data files adhering strictly to the JSP2 format parsed by load_dzn:
- JOBS = 1..n
- MACHINES = 1..m
- SPEED = 5
- time, energy (3D arrays)
- precedence, releaseDate, dueDate (2D arrays)

Organized into 3 groups:
1. Base (5 instances): multi-scale balanced benchmarks.
2. Factors (12 instances): OFAT variation of duration CV, bottleneck,
   tardiness pressure, energy conflict, release dispersion, and machine load.
3. Interactions (8 instances): controlled 2-factor combinations.
"""

import csv
import os
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@dataclass
class InstanceConfig:
    name: str
    group: str  # "base", "factors", "interactions"
    profile: str
    num_jobs: int
    num_machines: int
    num_speeds: int = 5
    seed: int = 1000
    duration_profile: str = "balanced"   # "balanced", "dur_low", "dur_high"
    energy_profile: str = "balanced"     # "balanced", "nrg_weak", "nrg_strong"
    tardiness_profile: str = "balanced"  # "balanced", "tard_low", "tard_high"
    release_profile: str = "balanced"    # "balanced", "rel_zero", "rel_high"
    load_profile: str = "balanced"       # "balanced", "load_low", "load_high"
    bottleneck_profile: str = "balanced" # "balanced", "btnk_low", "btnk_high"
    generator_version: str = "1.0.0"


# Exact definitions of the 25 instances
INSTANCES_CONFIG: List[InstanceConfig] = [
    # Group 1: Base (5 instances)
    InstanceConfig(
        name="base_01_5x10", group="base", profile="base_balanced_small",
        num_jobs=5, num_machines=10, seed=1001,
    ),
    InstanceConfig(
        name="base_02_10x10", group="base", profile="base_balanced_medium",
        num_jobs=10, num_machines=10, seed=1002,
    ),
    InstanceConfig(
        name="base_03_15x10", group="base", profile="base_balanced_rectangular",
        num_jobs=15, num_machines=10, seed=1003,
    ),
    InstanceConfig(
        name="base_04_20x10", group="base", profile="base_balanced_high_load",
        num_jobs=20, num_machines=10, seed=1004,
    ),
    InstanceConfig(
        name="base_05_20x20", group="base", profile="base_balanced_large_square",
        num_jobs=20, num_machines=20, seed=1005,
    ),

    # Group 2: Factors / OFAT (12 instances)
    InstanceConfig(
        name="dur_low_10x10", group="factors", profile="dur_low",
        num_jobs=10, num_machines=10, seed=2001,
        duration_profile="dur_low",
    ),
    InstanceConfig(
        name="dur_high_10x10", group="factors", profile="dur_high",
        num_jobs=10, num_machines=10, seed=2002,
        duration_profile="dur_high",
    ),
    InstanceConfig(
        name="btnk_low_10x10", group="factors", profile="btnk_low",
        num_jobs=10, num_machines=10, seed=2003,
        bottleneck_profile="btnk_low",
    ),
    InstanceConfig(
        name="btnk_high_10x10", group="factors", profile="btnk_high",
        num_jobs=10, num_machines=10, seed=2004,
        bottleneck_profile="btnk_high",
    ),
    InstanceConfig(
        name="tard_low_10x10", group="factors", profile="tard_low",
        num_jobs=10, num_machines=10, seed=2005,
        tardiness_profile="tard_low",
    ),
    InstanceConfig(
        name="tard_high_10x10", group="factors", profile="tard_high",
        num_jobs=10, num_machines=10, seed=2006,
        tardiness_profile="tard_high",
    ),
    InstanceConfig(
        name="nrg_weak_10x10", group="factors", profile="nrg_weak",
        num_jobs=10, num_machines=10, seed=2007,
        energy_profile="nrg_weak",
    ),
    InstanceConfig(
        name="nrg_strong_10x10", group="factors", profile="nrg_strong",
        num_jobs=10, num_machines=10, seed=2008,
        energy_profile="nrg_strong",
    ),
    InstanceConfig(
        name="rel_zero_10x10", group="factors", profile="rel_zero",
        num_jobs=10, num_machines=10, seed=2009,
        release_profile="rel_zero",
    ),
    InstanceConfig(
        name="rel_high_10x10", group="factors", profile="rel_high",
        num_jobs=10, num_machines=10, seed=2010,
        release_profile="rel_high",
    ),
    InstanceConfig(
        name="load_low_10x20", group="factors", profile="load_low",
        num_jobs=10, num_machines=20, seed=2011,
        load_profile="load_low",
    ),
    InstanceConfig(
        name="load_high_20x10", group="factors", profile="load_high",
        num_jobs=20, num_machines=10, seed=2012,
        load_profile="load_high",
    ),

    # Group 3: Interactions (8 instances)
    InstanceConfig(
        name="int_tard_btnk_10x10", group="interactions", profile="int_tard_btnk",
        num_jobs=10, num_machines=10, seed=3001,
        tardiness_profile="tard_high", bottleneck_profile="btnk_high",
    ),
    InstanceConfig(
        name="int_dur_btnk_10x10", group="interactions", profile="int_dur_btnk",
        num_jobs=10, num_machines=10, seed=3002,
        duration_profile="dur_high", bottleneck_profile="btnk_high",
    ),
    InstanceConfig(
        name="int_tard_nrg_10x10", group="interactions", profile="int_tard_nrg",
        num_jobs=10, num_machines=10, seed=3003,
        tardiness_profile="tard_high", energy_profile="nrg_strong",
    ),
    InstanceConfig(
        name="int_rel_btnk_10x10", group="interactions", profile="int_rel_btnk",
        num_jobs=10, num_machines=10, seed=3004,
        release_profile="rel_high", bottleneck_profile="btnk_high",
    ),
    InstanceConfig(
        name="int_dur_nrg_10x10", group="interactions", profile="int_dur_nrg",
        num_jobs=10, num_machines=10, seed=3005,
        duration_profile="dur_high", energy_profile="nrg_strong",
    ),
    InstanceConfig(
        name="int_tard_load_20x10", group="interactions", profile="int_tard_load",
        num_jobs=20, num_machines=10, seed=3006,
        tardiness_profile="tard_high", load_profile="load_high",
    ),
    InstanceConfig(
        name="int_btnk_load_20x10", group="interactions", profile="int_btnk_load",
        num_jobs=20, num_machines=10, seed=3007,
        bottleneck_profile="btnk_high", load_profile="load_high",
    ),
    InstanceConfig(
        name="int_nrg_load_20x10", group="interactions", profile="int_nrg_load",
        num_jobs=20, num_machines=10, seed=3008,
        energy_profile="nrg_strong", load_profile="load_high",
    ),
]


def generate_single_instance(cfg: InstanceConfig) -> Tuple[str, dict]:
    """Generates the .dzn content and summary characteristics for the given configuration."""
    rng = random.Random(cfg.seed)
    n = cfg.num_jobs
    m = cfg.num_machines
    s = cfg.num_speeds

    # 1. Routing / Precedence
    routes: List[List[int]] = []
    for j in range(n):
        if cfg.bottleneck_profile == "btnk_high":
            # For bottleneck high, operations on machines 1 and 2 are visited in early steps
            other_machines = list(range(3, m + 1))
            rng.shuffle(other_machines)
            btnk_order = [1, 2]
            rng.shuffle(btnk_order)
            route = btnk_order + other_machines
        else:
            machs = list(range(1, m + 1))
            rng.shuffle(machs)
            route = machs
        routes.append(route)

    # precedence_flat: precedence[j, m_idx] = position in route (0-based)
    precedence_flat = [0] * (n * m)
    for j in range(n):
        route = routes[j]
        for step, mach_id in enumerate(route):
            m_idx = mach_id - 1
            precedence_flat[j * m + m_idx] = step

    # 2. Base Durations and Energies per operation
    time_flat = [0] * (n * m * s)
    energy_flat = [0] * (n * m * s)

    # Scaling multipliers across modes (1..5)
    # Mode 1 is slowest / low energy, Mode 5 is fastest / high energy
    if cfg.energy_profile == "nrg_weak":
        # Weak conflict: time decreases, energy barely increases (ratio ~ 1.3)
        time_mults = [1.25, 1.05, 0.88, 0.72, 0.58]
        energy_mults = [0.85, 0.90, 0.96, 1.02, 1.10]
    elif cfg.energy_profile == "nrg_strong":
        # Strong conflict: time decreases, energy escalates drastically (ratio ~ 35+)
        time_mults = [1.40, 1.00, 0.70, 0.48, 0.32]
        energy_mults = [0.20, 0.60, 1.50, 3.50, 7.50]
    else:  # balanced
        # Moderate conflict: ratio ~ 3.0
        time_mults = [1.20, 1.00, 0.80, 0.65, 0.50]
        energy_mults = [0.60, 0.80, 1.00, 1.30, 1.80]

    for j in range(n):
        for m_idx in range(m):
            mach_id = m_idx + 1

            # Base duration selection
            if cfg.bottleneck_profile == "btnk_high" and mach_id in (1, 2):
                p_base = rng.randint(150, 210)
            elif cfg.bottleneck_profile == "btnk_high":
                p_base = rng.randint(25, 45)
            elif cfg.duration_profile == "dur_low":
                p_base = rng.randint(47, 53)
            elif cfg.duration_profile == "dur_high":
                if rng.random() < 0.5:
                    p_base = rng.randint(8, 18)
                else:
                    p_base = rng.randint(120, 180)
            elif cfg.bottleneck_profile == "btnk_low":
                p_base = rng.randint(45, 55)
            else:  # balanced
                p_base = rng.randint(30, 70)

            # Base energy selection
            e_base = rng.randint(40, 80)

            for s_idx in range(s):
                dur = max(1, int(round(p_base * time_mults[s_idx])))
                nrg = max(1, int(round(e_base * energy_mults[s_idx])))
                idx_3d = (j * m + m_idx) * s + s_idx
                time_flat[idx_3d] = dur
                energy_flat[idx_3d] = nrg

    # 3. Release Dates
    release_flat = [0] * (n * m)
    for j in range(n):
        route = routes[j]
        first_mach = route[0]
        if cfg.release_profile == "rel_zero":
            r_first = 0
        elif cfg.release_profile == "rel_high":
            r_first = rng.randint(50, 250)
        else:  # balanced
            r_first = rng.randint(0, 40)

        # Assign release date to the first operation
        first_m_idx = first_mach - 1
        release_flat[j * m + first_m_idx] = r_first

        # Subsequent operations
        if cfg.release_profile == "rel_high":
            current_r = r_first
            for step in range(1, m):
                curr_mach = route[step]
                curr_m_idx = curr_mach - 1
                current_r += rng.randint(15, 45)
                release_flat[j * m + curr_m_idx] = current_r

    # 4. Due Dates (Job-level)
    due_flat = [0] * (n * m)
    for j in range(n):
        route = routes[j]
        first_m_idx = route[0] - 1
        r_start = release_flat[j * m + first_m_idx]

        # Minimum duration across all operations of job j
        p_min_sum = 0
        for m_idx in range(m):
            min_mode_dur = min(time_flat[(j * m + m_idx) * s + s_idx] for s_idx in range(s))
            p_min_sum += min_mode_dur

        job_p_min = r_start + p_min_sum

        if cfg.tardiness_profile == "tard_high":
            # Tight: d_j < P_min guarantees 100% positive tardiness pressure
            d_j = max(1, int(round(job_p_min * 0.85)))
        elif cfg.tardiness_profile == "tard_low":
            # Generous: d_j >> P_min gives ample slack
            d_j = int(round(job_p_min * 2.00)) + 60
        else:  # balanced
            # Moderate slack
            d_j = int(round(job_p_min * 1.35)) + rng.randint(10, 30)

        # Set d_j across all machines of job j so load_dzn reads it cleanly
        for m_idx in range(m):
            due_flat[j * m + m_idx] = d_j

    # 5. Build .dzn string
    lines = [
        "%SETS",
        f"JOBS     = 1..{n};",
        f"MACHINES = 1..{m};",
        f"SPEED    = {s};",
        "",
        f"time               = array3d(JOBS,MACHINES,1..SPEED,[{', '.join(map(str, time_flat))}]);",
        "",
        f"energy             = array3d(JOBS,MACHINES,1..SPEED,[{', '.join(map(str, energy_flat))}]);",
        "",
        f"precedence         = array2d(JOBS,MACHINES,[{', '.join(map(str, precedence_flat))}]);",
        "",
        f"releaseDate        = array2d(JOBS,MACHINES,[{', '.join(map(str, release_flat))}]);",
        "",
        f"dueDate            = array2d(JOBS,MACHINES,[{', '.join(map(str, due_flat))}]);",
        "",
    ]
    dzn_content = "\n".join(lines)
    return dzn_content, {}


def generate_all_instances(
    base_output_dir: str = "data/generated/f86_3",
    registry_path: str = "data/instance_registry.csv",
) -> List[Tuple[InstanceConfig, Path]]:
    """Generates all 25 instances and writes the instance registry CSV."""
    base_dir = Path(base_output_dir)
    generated: List[Tuple[InstanceConfig, Path]] = []

    for cfg in INSTANCES_CONFIG:
        group_dir = base_dir / cfg.group
        group_dir.mkdir(parents=True, exist_ok=True)
        file_path = group_dir / f"{cfg.name}.dzn"

        dzn_text, _ = generate_single_instance(cfg)
        file_path.write_text(dzn_text, encoding="utf-8")
        generated.append((cfg, file_path))

    # Write instance_registry.csv
    reg_file = Path(registry_path)
    reg_file.parent.mkdir(parents=True, exist_ok=True)

    # Compute characteristics for registry enrichment
    from scripts.analyze_generated_instances import calculate_instance_characteristics
    from src.mojssp.io import load_dzn

    fieldnames = [
        "instance_name",
        "group",
        "profile",
        "jobs",
        "machines",
        "operations",
        "speeds",
        "seed",
        "duration_profile",
        "energy_profile",
        "tardiness_profile",
        "release_profile",
        "load_profile",
        "bottleneck_profile",
        "generator_version",
        "duration_cv",
        "energy_cv",
        "release_cv",
        "tardiness_pressure",
        "bottleneck_concentration",
        "time_energy_conflict",
        "relative_path",
    ]

    with open(reg_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for cfg, p in generated:
            rel_path = p.relative_to(Path("data")).as_posix()
            inst = load_dzn(p, validate=True)
            chars = calculate_instance_characteristics(inst)
            writer.writerow({
                "instance_name": cfg.name,
                "group": cfg.group,
                "profile": cfg.profile,
                "jobs": cfg.num_jobs,
                "machines": cfg.num_machines,
                "operations": cfg.num_jobs * cfg.num_machines,
                "speeds": cfg.num_speeds,
                "seed": cfg.seed,
                "duration_profile": cfg.duration_profile,
                "energy_profile": cfg.energy_profile,
                "tardiness_profile": cfg.tardiness_profile,
                "release_profile": cfg.release_profile,
                "load_profile": cfg.load_profile,
                "bottleneck_profile": cfg.bottleneck_profile,
                "generator_version": cfg.generator_version,
                "duration_cv": chars["duration_cv"],
                "energy_cv": chars["energy_cv"],
                "release_cv": chars["release_cv"],
                "tardiness_pressure": chars["tardiness_pressure"],
                "bottleneck_concentration": chars["bottleneck_concentration"],
                "time_energy_conflict": chars["time_energy_conflict"],
                "relative_path": rel_path,
            })

    print(f"Generated {len(generated)} instances in {base_dir}")
    print(f"Registry written to {reg_file}")
    return generated


if __name__ == "__main__":
    generate_all_instances()

