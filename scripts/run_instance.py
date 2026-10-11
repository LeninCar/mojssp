"""CLI tool to run an individual MO-JSSP instance with Portfolio or standalone algorithms.

Allows selecting solutions from the Pareto front (e.g. Min Cmax, Min Tardiness, Min Energy, Balanced)
and generating both the Gantt schedule and the Pareto trade-off plot.

Usage examples:
    python scripts/run_instance.py --instance data/experimental/10_10_2-5_1.dzn --budget 300 --select cmax
    python scripts/run_instance.py --instance data/experimental/10_10_2-5_1.dzn --budget 300 --select tardiness
    python scripts/run_instance.py --instance data/experimental/10_10_2-5_1.dzn --budget 300 --select energy
    python scripts/run_instance.py --instance data/experimental/10_10_2-5_1.dzn --budget 300 --select balanced
    python scripts/run_instance.py --instance data/experimental/10_10_2-5_1.dzn --budget 300 --select all
    python scripts/run_instance.py --instance data/experimental/10_10_2-5_1.dzn --budget 300 --select interactive
"""

import argparse
from pathlib import Path
import sys
import time
from typing import Dict, List, Optional, Tuple

# Ensure src/ is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import matplotlib.pyplot as plt
import numpy as np

from mojssp import (
    AdaptivePortfolioOrchestrator,
    HypervolumeRewardTracker,
    MOPSOArm,
    NSGA2Arm,
    NSGA2LSArm,
    ObjectiveNormalizer,
    ParetoArchive,
    Portfolio,
    SlidingWindowUCB,
    compute_archive_hypervolume,
    compute_instance_bounds,
    load_dzn,
)


def print_ascii_gantt(schedule, max_width: int = 60) -> None:
    """Print a clean text-based Gantt chart of machine allocations."""
    makespan = schedule.makespan
    if makespan == 0:
        print("Empty schedule.")
        return

    scale = max_width / max(1, makespan)
    print("\n--- CRONOGRAMA POR MÁQUINA (DIAGRAMA DE GANTT EN TERMINAL) ---")
    for m in schedule.machine_ids:
        ops = schedule.get_operations_by_machine(m)
        timeline = ["."] * max_width
        for op in ops:
            s_col = min(max_width - 1, int(op.start * scale))
            e_col = min(max_width, max(s_col + 1, int(op.completion * scale)))
            label = f"J{op.job_id}"
            for c in range(s_col, e_col):
                char_idx = c - s_col
                timeline[c] = label[char_idx % len(label)]
        print(f"M{m:02d} |" + "".join(timeline) + f"| (Ops: {len(ops)})")
    print("     " + "-" * max_width)
    print(f"     0{' ' * (max_width - 10)}Cmax={makespan}\n")


def plot_gantt_chart(schedule, output_path: Path, title: str, subtitle: str = "") -> None:
    """Save an aesthetic Gantt chart image."""
    fig, ax = plt.subplots(figsize=(13, 6.5))
    colors = plt.cm.tab20.colors

    for op in schedule.operations:
        color = colors[op.job_id % len(colors)]
        ax.barh(
            y=op.machine_id,
            width=op.duration,
            left=op.start,
            height=0.65,
            align="center",
            color=color,
            edgecolor="black",
            linewidth=0.8,
            alpha=0.85,
        )
        if op.duration > schedule.makespan * 0.025:
            text_color = "white" if np.mean(color[:3]) < 0.5 else "black"
            ax.text(
                op.start + op.duration / 2,
                op.machine_id,
                f"J{op.job_id}.{op.op_id}\n(m{op.mode_id})",
                ha="center",
                va="center",
                fontsize=7,
                color=text_color,
                weight="bold",
            )

    full_title = title if not subtitle else f"{title}\n{subtitle}"
    ax.set_xlabel("Tiempo de Proceso", fontsize=11, fontweight="bold")
    ax.set_ylabel("Máquina", fontsize=11, fontweight="bold")
    ax.set_title(full_title, fontsize=12, fontweight="bold", pad=12)
    ax.set_yticks(schedule.machine_ids)
    ax.set_yticklabels([f"Máquina {m}" for m in schedule.machine_ids])
    ax.grid(axis="x", linestyle="--", alpha=0.5)
    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=200)
    plt.close()
    print(f"-> Grafico Gantt guardado en: {output_path}")


def plot_pareto_front(
    entries,
    selected_indices: List[int],
    output_path: Path,
    instance_name: str,
    algo_name: str,
) -> None:
    """Save a 2D projection multi-panel chart of the Pareto front."""
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    cmax_vals = [e.objectives.makespan for e in entries]
    tard_vals = [e.objectives.tardiness for e in entries]
    nrg_vals = [e.objectives.energy for e in entries]

    plots = [
        (axes[0], cmax_vals, tard_vals, "Makespan (Cmax)", "Tardiness (T)", "Trade-off Makespan vs Tardiness"),
        (axes[1], cmax_vals, nrg_vals, "Makespan (Cmax)", "Energía (E)", "Trade-off Makespan vs Energía"),
        (axes[2], tard_vals, nrg_vals, "Tardiness (T)", "Energía (E)", "Trade-off Tardiness vs Energía"),
    ]

    for ax, x_vals, y_vals, x_lbl, y_lbl, title in plots:
        ax.scatter(x_vals, y_vals, color="#2b5c8f", s=50, alpha=0.7, edgecolors="none", label="Frente de Pareto")
        # Highlight selected
        for s_idx in selected_indices:
            e = entries[s_idx]
            sx = getattr(e.objectives, "makespan" if "Makespan" in x_lbl else "tardiness")
            sy = getattr(e.objectives, "tardiness" if "Tardiness" in y_lbl else "energy")
            ax.scatter([sx], [sy], color="#d9381e", s=130, edgecolors="black", linewidth=1.5, zorder=5, label=f"Solución #{s_idx+1}")

        ax.set_xlabel(x_lbl, fontweight="bold")
        ax.set_ylabel(y_lbl, fontweight="bold")
        ax.set_title(title, fontsize=11, fontweight="bold")
        ax.grid(True, linestyle="--", alpha=0.5)

    # Unique handles for legend
    handles, labels = axes[0].get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    axes[0].legend(by_label.values(), by_label.keys(), loc="best", framealpha=0.9)

    plt.suptitle(f"Frente de Pareto MO-JSSP: {instance_name} ({algo_name.upper()})", fontsize=14, fontweight="bold")
    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=200)
    plt.close()
    print(f"-> Grafico de Frente de Pareto guardado en: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ejecutar una instancia MO-JSSP y seleccionar opciones de Schedule")
    parser.add_argument("--instance", type=str, required=True, help="Ruta al archivo .dzn de la instancia")
    parser.add_argument(
        "--algo",
        type=str,
        default="portfolio",
        choices=["portfolio", "nsga2", "mopso", "nsga2_ls"],
        help="Algoritmo a ejecutar (default: portfolio)",
    )
    parser.add_argument("--budget", type=int, default=300, help="Presupuesto en evaluaciones (FE, default: 300)")
    parser.add_argument("--block-size", type=int, default=50, help="Tamaño de bloque para DMAB (default: 50)")
    parser.add_argument("--seed", type=int, default=42, help="Semilla pseudoaleatoria (default: 42)")
    parser.add_argument(
        "--select",
        type=str,
        default="interactive",
        help="Qué solución graficar: 'interactive', 'cmax', 'tardiness', 'energy', 'balanced', 'all', o número 1..N (default: interactive)",
    )
    parser.add_argument("--output-dir", type=str, default="results/runs", help="Directorio para salidas")

    args = parser.parse_args()
    inst_path = Path(args.instance)
    if not inst_path.exists():
        print(f"Error: No existe el archivo de instancia '{inst_path}'")
        sys.exit(1)

    print("=" * 75)
    print("EJECUTOR Y EXPLORADOR DE SCHEDULES MO-JSSP")
    print("=" * 75)
    print(f"Instancia:     {inst_path.name}")
    print(f"Algoritmo:     {args.algo.upper()}")
    print(f"Presupuesto:   {args.budget} FE")
    print(f"Semilla:       {args.seed}")
    print("-" * 75)

    # 1. Cargar instancia y cotas
    instance = load_dzn(inst_path)
    bounds = compute_instance_bounds(instance)
    normalizer = ObjectiveNormalizer(bounds)

    print(f"Estructura:    {len(instance.jobs)} Jobs, {instance.num_machines} Máquinas, "
          f"{instance.total_operations} Operaciones")
    print(f"Límites objetivos (Min-Max teóricos):")
    print(f"  Makespan:  [{bounds.cmax_min}, {bounds.cmax_max}]")
    print(f"  Tardiness: [{bounds.tardiness_min}, {bounds.tardiness_max}]")
    print(f"  Energía:   [{bounds.energy_min:.2f}, {bounds.energy_max:.2f}]")
    print("-" * 75)

    t0 = time.perf_counter()

    # 2. Ejecutar optimización
    if args.algo == "portfolio":
        seed_nsga2 = (args.seed * 10007 + 11) % (2**31 - 1)
        seed_mopso = (args.seed * 10007 + 23) % (2**31 - 1)
        seed_ls = (args.seed * 10007 + 37) % (2**31 - 1)

        arm1 = NSGA2Arm(instance, population_size=30, seed=seed_nsga2)
        arm2 = MOPSOArm(instance, population_size=30, seed=seed_mopso)
        arm3 = NSGA2LSArm(instance, population_size=30, seed=seed_ls, max_ls_iterations=10, max_ls_neighbors=10)

        portfolio = Portfolio(arms={"NSGA-II": arm1, "MOPSO": arm2, "NSGA-II+LS": arm3})
        dmab = SlidingWindowUCB(
            arm_names=portfolio.arm_names,
            window_size=10,
            exploration_factor=0.07,
            seed=args.seed,
        )
        tracker = HypervolumeRewardTracker(normalizer)
        orch = AdaptivePortfolioOrchestrator(portfolio, dmab, tracker)

        exec_res = orch.run(total_budget=args.budget, block_size=args.block_size)
        elapsed = time.perf_counter() - t0

        archive = exec_res.global_archive
        final_hv = tracker.current_hv

        print("\nHISTORIAL DE SELECCIÓN DMAB POR BLOQUES:")
        print(f"{'Bloque':<8} {'Brazo':<14} {'FE Usadas':<10} {'HV Previo':<12} {'HV Posterior':<14} {'Reward (dHV)':<12}")
        print("-" * 75)
        for h in exec_res.history:
            print(f"{h.block_index + 1:<8} {h.arm_name:<14} {h.evaluations_used:<10} "
                  f"{h.hv_before:<12.5f} {h.hv_after:<14.5f} {h.reward:<12.5f}")

        arm_counts = {}
        for h in exec_res.history:
            arm_counts[h.arm_name] = arm_counts.get(h.arm_name, 0) + h.evaluations_used
        print("\nDISTRIBUCIÓN DEL PRESUPUESTO:")
        for arm_name, used in arm_counts.items():
            pct = (used / args.budget) * 100
            print(f"  - {arm_name:<12}: {used:>4} FE ({pct:>5.1f}%)")

    else:
        if args.algo == "nsga2":
            arm = NSGA2Arm(instance, population_size=30, seed=args.seed, max_evaluations=args.budget)
        elif args.algo == "mopso":
            arm = MOPSOArm(instance, population_size=30, seed=args.seed, max_evaluations=args.budget)
        else:
            arm = NSGA2LSArm(instance, population_size=30, seed=args.seed, max_evaluations=args.budget)

        blk = arm.run(args.budget)
        elapsed = time.perf_counter() - t0
        archive = blk.solutions
        final_hv = compute_archive_hypervolume(archive, normalizer)

    print("\n" + "=" * 75)
    print("RESUMEN DE OPTIMIZACIÓN")
    print("=" * 75)
    print(f"Evaluaciones realizadas: {args.budget} FE")
    print(f"Tiempo de cómputo:        {elapsed:.2f} s")
    print(f"Soluciones en Pareto:     {len(archive)}")
    print(f"Hypervolume (HV):         {final_hv:.6f}")
    print("-" * 75)

    if len(archive) == 0:
        print("No se encontraron soluciones válidas.")
        return

    # 3. Analizar y etiquetar las opciones en el Frente de Pareto
    entries = sorted(archive.entries, key=lambda e: (e.objectives.makespan, e.objectives.energy))

    # Identificar extremos y solución equilibrada
    min_cmax_idx = min(range(len(entries)), key=lambda i: entries[i].objectives.makespan)
    min_tard_idx = min(range(len(entries)), key=lambda i: entries[i].objectives.tardiness)
    min_nrg_idx = min(range(len(entries)), key=lambda i: entries[i].objectives.energy)

    # Solución equilibrada (mínima distancia al origen en espacio normalizado [0,1])
    def norm_dist(e):
        c_n = (e.objectives.makespan - bounds.cmax_min) / max(1, (bounds.cmax_max - bounds.cmax_min))
        t_n = (e.objectives.tardiness - bounds.tardiness_min) / max(1, (bounds.tardiness_max - bounds.tardiness_min))
        e_n = (e.objectives.energy - bounds.energy_min) / max(1e-5, (bounds.energy_max - bounds.energy_min))
        return c_n**2 + t_n**2 + e_n**2

    balanced_idx = min(range(len(entries)), key=lambda i: norm_dist(entries[i]))

    special_tags: Dict[int, List[str]] = {}
    special_tags.setdefault(min_cmax_idx, []).append("MÍNIMO MAKESPAN (Más Rápido)")
    special_tags.setdefault(min_tard_idx, []).append("MÍNIMO TARDINESS (Menor Retraso)")
    special_tags.setdefault(min_nrg_idx, []).append("MÍNIMA ENERGÍA (Más Ecológico/Barato)")
    special_tags.setdefault(balanced_idx, []).append("EQUILIBRADO / COMPROMISO")

    print("\nOPCIONES DISPONIBLES EN EL FRENTE DE PARETO:")
    print(f"{'Opción':<8} {'Makespan (Cmax)':<18} {'Tardiness (T)':<16} {'Energía (E)':<14} {'Perfil de la Solución'}")
    print("-" * 85)
    for idx, e in enumerate(entries):
        cmax = e.objectives.makespan
        tard = e.objectives.tardiness
        nrg = e.objectives.energy
        tags = " | ".join(special_tags.get(idx, []))
        tag_str = f"[{tags}]" if tags else ""
        print(f"#{idx+1:<7} {cmax:<18} {tard:<16} {nrg:<14.2f} {tag_str}")
    print("-" * 85)

    # 4. Determinar qué soluciones graficar según --select
    selected_to_plot: List[Tuple[int, str]] = []
    sel_arg = args.select.strip().lower()

    if sel_arg == "interactive":
        print("\n¿Qué solución deseas graficar y detallar?")
        print("  - Escribe el número de la opción (ej. 1, 2, 5...)")
        print("  - O escribe: 'cmax' (más rápido), 'tardiness' (menor retraso), 'energy' (más ahorro), 'balanced' (equilibrado), 'all' (todas las clave)")
        print("  - O presiona ENTER para elegir la solución equilibrada por defecto.")
        try:
            user_choice = input("Tu elección: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            user_choice = "balanced"

        if not user_choice:
            user_choice = "balanced"
        sel_arg = user_choice

    if sel_arg in ["cmax", "makespan", "fast"]:
        selected_to_plot.append((min_cmax_idx, "Mínimo Makespan"))
    elif sel_arg in ["tardiness", "tard", "delay"]:
        selected_to_plot.append((min_tard_idx, "Mínimo Tardiness"))
    elif sel_arg in ["energy", "nrg", "eco"]:
        selected_to_plot.append((min_nrg_idx, "Mínima Energía"))
    elif sel_arg in ["balanced", "compromise", "eq"]:
        selected_to_plot.append((balanced_idx, "Compromiso Equilibrado"))
    elif sel_arg == "all":
        seen_indices = set()
        for idx, lbl in [
            (min_cmax_idx, "Mínimo Makespan"),
            (min_tard_idx, "Mínimo Tardiness"),
            (min_nrg_idx, "Mínima Energía"),
            (balanced_idx, "Compromiso Equilibrado"),
        ]:
            if idx not in seen_indices:
                selected_to_plot.append((idx, lbl))
                seen_indices.add(idx)
    else:
        # Intentar parsear como número
        try:
            choice_num = int(sel_arg) - 1
            if 0 <= choice_num < len(entries):
                selected_to_plot.append((choice_num, f"Opción #{choice_num+1}"))
            else:
                print(f"Opción #{choice_num+1} fuera de rango. Seleccionando la opción equilibrada.")
                selected_to_plot.append((balanced_idx, "Compromiso Equilibrado"))
        except ValueError:
            print(f"Entrada '{sel_arg}' no reconocida. Seleccionando la opción equilibrada.")
            selected_to_plot.append((balanced_idx, "Compromiso Equilibrado"))

    # 5. Generar y mostrar las soluciones seleccionadas
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Primero: Gráfico global del Frente de Pareto
    plot_pareto_front(
        entries=entries,
        selected_indices=[idx for idx, _ in selected_to_plot],
        output_path=out_dir / f"pareto_front_{instance.name}_{args.algo}.png",
        instance_name=instance.name,
        algo_name=args.algo,
    )

    # Segundo: Para cada solución seleccionada, mostrar tabla, Gantt ASCII e imagen
    for s_idx, label in selected_to_plot:
        entry = entries[s_idx]
        obj = entry.objectives
        print("\n" + "=" * 75)
        print(f"CRONOGRAMA DETALLADO: SOLUCIÓN #{s_idx+1} ({label})")
        print(f"Makespan (Cmax): {obj.makespan} | Tardiness (T): {obj.tardiness} | Energía (E): {obj.energy:.2f}")
        print("=" * 75)

        # Métrica de confianza y cercanía a las cotas teóricas
        gap_cmax = ((obj.makespan - bounds.cmax_min) / max(1, bounds.cmax_min)) * 100
        gap_energy = ((obj.energy - bounds.energy_min) / max(1e-5, bounds.energy_min)) * 100
        tard_worst = max(1, bounds.tardiness_max)
        tard_reduction = max(0.0, (1.0 - (obj.tardiness / tard_worst)) * 100)

        print("\nDIAGNÓSTICO DE CALIDAD Y CONFIANZA:")
        print(f"  * Eficiencia temporal (Makespan): A +{gap_cmax:.1f}% de la cota mínima física absoluta ({bounds.cmax_min})")
        print(f"  * Eficiencia energética:          A +{gap_energy:.1f}% del consumo mínimo teórico posible ({bounds.energy_min:.1f})")
        print(f"  * Mitigación de retrasos:         {tard_reduction:.1f}% de reducción frente al peor retraso posible ({bounds.tardiness_max})")
        print(f"  * Hypervolume del Frente:         {final_hv:.5f} (Calidad global de cobertura y convergencia)")

        print_ascii_gantt(entry.schedule)

        clean_lbl = label.replace(" ", "_").replace("/", "_").replace("#", "")
        out_gantt = out_dir / f"gantt_{instance.name}_{args.algo}_sol{s_idx+1}_{clean_lbl}.png"
        plot_gantt_chart(
            entry.schedule,
            out_gantt,
            title=f"Cronograma Gantt MO-JSSP - {instance.name} ({args.algo.upper()})",
            subtitle=f"Solución #{s_idx+1} [{label}] -> Cmax={obj.makespan}, Tardiness={obj.tardiness}, Energía={obj.energy:.2f}",
        )

    print("\n" + "=" * 75)
    print(f"Archivos generados en la carpeta: {out_dir.resolve()}")
    print("=" * 75)


if __name__ == "__main__":
    main()
