"""Demonstration script for NSGA-II on MO-JSSP (Phase 3).

Executes NSGA-II on the toy instance, displays the evolutionary progression,
reports the discovered non-dominated front (Cmax, T, E), and validates all
phenotypes with ScheduleValidator.
"""

import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from mojssp import (
    NSGA2,
    load_dzn,
    validate_schedule,
)


def run_demo() -> None:
    instance_path = project_root / "data" / "toy_instance.dzn"
    print("=" * 70)
    print("DEMOSTRACIÓN DE NSGA-II PARA MO-JSSP (FASE 3)")
    print("=" * 70)

    print(f"\n1. Cargando instancia desde: {instance_path.name}")
    instance = load_dzn(instance_path)
    print(f"   - Nombre: {instance.name}")
    print(f"   - Trabajos: {instance.num_jobs}")
    print(f"   - Máquinas: {instance.num_machines}")
    print(f"   - Total operaciones: {instance.total_operations}")

    # Parámetros de ejecución
    pop_size = 20
    generations = 15
    seed = 42
    cx_prob = 0.9
    mut_seq_prob = 0.2
    mut_mode_prob = 0.25

    print("\n2. Parámetros de configuración del algoritmo:")
    print(f"   - Tamaño inicial de la población: {pop_size}")
    print(f"   - Número de generaciones: {generations}")
    print(f"   - Probabilidad de crossover (POX): {cx_prob}")
    print(f"   - Probabilidad mutación secuencia (Swap): {mut_seq_prob}")
    print(f"   - Probabilidad mutación modos (por gen): {mut_mode_prob}")
    print(f"   - Semilla aleatoria (seed): {seed}")

    algo = NSGA2(
        population_size=pop_size,
        generations=generations,
        crossover_probability=cx_prob,
        mutation_sequence_probability=mut_seq_prob,
        mutation_mode_per_gene_probability=mut_mode_prob,
        seed=seed,
    )

    print("\n3. Ejecutando NSGA-II...")
    result = algo.run(instance)

    print("\n4. Estado final de la evolución:")
    print(f"   - Tamaño final de la población: {len(result.population)}")
    print(f"   - Soluciones no dominadas encontradas en Frente 1: {len(result.non_dominated_solutions)}")

    print("\n5. Detalle del Frente no dominado (Aproximación de Pareto):")
    print("-" * 70)
    print(f"{'#':<3} | {'Makespan (Cmax)':<15} | {'Tardiness (T)':<15} | {'Energía (E)':<12} | {'Secuencia':<14} | {'Modos'}")
    print("-" * 70)

    for i, (sol, sched, obj) in enumerate(
        zip(
            result.non_dominated_solutions,
            result.non_dominated_schedules,
            result.non_dominated_objectives,
        ),
        start=1,
    ):
        seq_str = str(sol.sequence)
        modes_str = str(sol.modes)
        print(f"{i:<3} | {obj.makespan:<15} | {obj.tardiness:<15} | {obj.energy:<12.1f} | {seq_str:<14} | {modes_str}")

    print("-" * 70)

    print("\n6. Auditoría formal independiente con ScheduleValidator:")
    all_valid = True
    for i, sched in enumerate(result.non_dominated_schedules, start=1):
        errors = validate_schedule(instance, sched, raise_on_error=False)
        if errors:
            all_valid = False
            print(f"   [FALLO] Solución #{i} tiene errores: {errors}")
        else:
            print(f"   [VÁLIDO] Schedule #{i} cumple al 100% las restricciones de máquina, precedencia y tiempos.")

    if all_valid:
        print("\nResultado: Todos los schedules no dominados fueron verificados como válidos.")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()

