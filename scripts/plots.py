"""Gráficas y Gantt en texto para una corrida sobre una instancia."""

from pathlib import Path
from typing import List

import matplotlib.pyplot as plt
import numpy as np

ARM_LABELS = {"MOEA/D": "MOEA/D", "RegionExplorer": "BLMR"}
ARM_COLORS = {"MOEA/D": "#e0662d", "RegionExplorer": "#2f6fd6"}


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



def plot_convergence(curves, blocks, budget, cut, output_path, instance_name):
    """HV contra FE de cada método y, si el principal es un portafolio, qué brazo ejecutó cada bloque.

    curves: lista de (etiqueta, color, resultado, es_principal).
    """
    if blocks:
        fig, (ax, bar) = plt.subplots(2, 1, figsize=(12, 7), height_ratios=[4, 1], sharex=True)
    else:
        fig, ax = plt.subplots(figsize=(12, 5.5))
    for label, color, result, main in curves:
        fe, hv = zip(*result["checkpoints"])
        ax.plot(fe, hv, color=color, linewidth=2.4 if main else 1.6, linestyle="--" if main else "-",
                label=f"{label} (HV final {result['hypervolume']:.4f})")
    if cut:
        ax.axvline(cut, color="grey", linestyle=":", linewidth=1)
        ax.text(cut, ax.get_ylim()[0], f"  corte {cut} FE", color="grey", va="bottom", fontsize=9)
    ax.set_ylabel("Hipervolumen normalizado", fontweight="bold")
    ax.set_title(f"Convergencia del HV: {instance_name}", fontsize=13, fontweight="bold")
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="lower right")

    if blocks:
        for b in blocks:
            start = b["fe_after"] - b["evaluations_used"]
            bar.barh(0, b["evaluations_used"], left=start, color=ARM_COLORS[b["arm_name"]],
                     edgecolor="white", linewidth=0.5)
        for arm, color in ARM_COLORS.items():
            bar.barh(0, 0, color=color, label=ARM_LABELS[arm])
        if cut:
            bar.axvline(cut, color="grey", linestyle=":", linewidth=1)
        bar.set_yticks([])
        bar.set_xlim(0, budget)
        bar.set_xlabel("Evaluaciones usadas (FE)", fontweight="bold")
        bar.set_title(f"Brazo que ejecutó cada bloque de 50 FE en {curves[0][0]}", fontsize=10)
        bar.legend(loc="upper right", ncol=2, fontsize=9)
    else:
        ax.set_xlabel("Evaluaciones usadas (FE)", fontweight="bold")
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()
    print(f"-> Gráfico de convergencia guardado en: {output_path}")


def plot_fronts_overlay(fronts, output_path, instance_name):
    """Proyecciones 2D de los frentes finales de cada método, superpuestos.

    fronts: lista de (etiqueta, color, entradas, es_principal); el principal se dibuja encima.
    """
    pairs = [("makespan", "tardiness", "Makespan", "Tardanza"),
             ("makespan", "energy", "Makespan", "Energía"),
             ("tardiness", "energy", "Tardanza", "Energía")]
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    for ax, (x, y, xl, yl) in zip(axes, pairs):
        for label, color, entries, main in sorted(fronts, key=lambda f: f[3]):
            ax.scatter([getattr(e.objectives, x) for e in entries], [getattr(e.objectives, y) for e in entries],
                       s=50 if main else 30, color=color, alpha=0.75, edgecolors="none",
                       marker="D" if main else "o", label=f"{label} ({len(entries)} sol.)")
        ax.set_xlabel(xl, fontweight="bold")
        ax.set_ylabel(yl, fontweight="bold")
        ax.grid(True, linestyle="--", alpha=0.5)
    axes[0].legend(loc="best", framealpha=0.9)
    plt.suptitle(f"Frentes finales superpuestos: {instance_name}", fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()
    print(f"-> Gráfico de frentes superpuestos guardado en: {output_path}")
