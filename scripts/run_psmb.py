"""Corre el Portafolio secuencial MOEA/D-BLMR (PS-MB) sobre una instancia y genera sus gráficas.

Usa exactamente las mismas funciones que la evaluación del holdout: con la semilla y el
presupuesto del holdout (3000 FE) el HV coincide con el guardado en
results/experiments/holdout_early_moead_600_20261024/runs/.

Ejemplos (desde la raíz del proyecto):
    .venv\\Scripts\\python.exe scripts\\run_psmb.py --instance data\\generated\\expanded_200\\base_c01_5x5_b01.dzn
    .venv\\Scripts\\python.exe scripts\\run_psmb.py --instance data\\generated\\expanded_200\\base_c01_5x5_b01.dzn --compare
    .venv\\Scripts\\python.exe scripts\\run_psmb.py --instance ruta\\a\\otra.dzn --seed 7 --select energy
"""

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import matplotlib.pyplot as plt

from mojssp.decoder import Decoder
from mojssp.evaluator import Evaluator
from mojssp.io import load_dzn
from mojssp.normalization import compute_instance_bounds
from mojssp.regional_portfolio import run_regional_policy_experiment
from mojssp.solution import Solution
from run_instance import plot_gantt_chart, plot_pareto_front, print_ascii_gantt
from run_regional_composition_comparison import native_individual
from run_regional_explorer_controls import run_individual

CUT = 600
METHODS = {
    "psmb": ("PS-MB", "#1a1a1a"),
    "blmr": ("BLMR solo", "#2f6fd6"),
    "moead": ("MOEA/D solo", "#e0662d"),
}
ARM_LABELS = {"MOEA/D": "MOEA/D", "RegionExplorer": "BLMR"}
ARM_COLORS = {"MOEA/D": "#e0662d", "RegionExplorer": "#2f6fd6"}


def run_method(instance, seed, budget, method):
    """Ejecuta un método contando las llamadas reales al evaluador."""
    calls = 0
    original = Evaluator.evaluate

    def counted(self, *a, **kw):
        nonlocal calls
        calls += 1
        return original(self, *a, **kw)

    with patch.object(Evaluator, "evaluate", counted):
        if method == "psmb":
            result = run_regional_policy_experiment(
                instance, seed, ["MOEA/D", "RegionExplorer"], "dynamic", False, budget,
                dynamic_options=dict(exclusive_arm="RegionExplorer", exclusive_after=CUT))
        elif method == "blmr":
            result = run_individual(instance, seed, "random", budget=budget)
        else:
            result = native_individual(instance, seed, "moead", budget=budget)
    assert calls == result["evaluations_used"] == budget, (method, calls, result["evaluations_used"])
    return result


def phase_allocations(blocks, budget):
    """FE de cada brazo en ronda 1 (0-300), ronda 2 (300-600) y refinamiento (600-fin)."""
    phases = [("Ronda 1", 0, 300), ("Ronda 2", 300, CUT), ("Refinamiento", CUT, budget)]
    rows = []
    for name, lo, hi in phases:
        used = Counter()
        for b in blocks:
            start = b["fe_after"] - b["evaluations_used"]
            if lo <= start < hi:
                used[b["arm_name"]] += b["evaluations_used"]
        rows.append((name, lo, hi, used))
    return rows


def rebuild_front(instance, front_entries):
    """Decodifica cada punto distinto del frente para tener su agenda (no cuenta como FE de la corrida).

    El archivo guarda genotipos distintos con los mismos objetivos; aquí se deja uno por punto.
    """
    decoder, evaluator = Decoder(), Evaluator()
    entries, seen = [], set()
    for row in front_entries:
        if tuple(row["objectives"]) in seen:
            continue
        seen.add(tuple(row["objectives"]))
        solution = Solution(tuple(row["sequence"]), tuple(row["modes"]))
        schedule = decoder.decode(instance, solution)
        objectives = evaluator.evaluate(instance, schedule)
        assert list(objectives) == row["objectives"]
        entries.append(SimpleNamespace(solution=solution, schedule=schedule, objectives=objectives))
    return sorted(entries, key=lambda e: (e.objectives.makespan, e.objectives.energy))


def pick_solutions(entries, bounds, select):
    """Índices de las soluciones a detallar según --select."""
    def norm_dist(e):
        o = e.objectives
        c = (o.makespan - bounds.cmax_min) / max(1, bounds.cmax_max - bounds.cmax_min)
        t = (o.tardiness - bounds.tardiness_min) / max(1, bounds.tardiness_max - bounds.tardiness_min)
        n = (o.energy - bounds.energy_min) / max(1e-5, bounds.energy_max - bounds.energy_min)
        return c * c + t * t + n * n

    idx = range(len(entries))
    key = {
        "cmax": (min(idx, key=lambda i: entries[i].objectives.makespan), "Mínimo makespan"),
        "tardiness": (min(idx, key=lambda i: entries[i].objectives.tardiness), "Mínima tardanza"),
        "energy": (min(idx, key=lambda i: entries[i].objectives.energy), "Mínima energía"),
        "balanced": (min(idx, key=lambda i: norm_dist(entries[i])), "Compromiso equilibrado"),
    }
    if select == "all":
        chosen, seen = [], set()
        for i, label in key.values():
            if i not in seen:
                chosen.append((i, label))
                seen.add(i)
        return chosen, key
    if select in key:
        return [key[select]], key
    number = int(select) - 1
    if not 0 <= number < len(entries):
        raise SystemExit(f"La opción {select} está fuera de rango (1..{len(entries)})")
    return [(number, f"Opción #{number + 1}")], key


def plot_convergence(results, psmb_blocks, budget, output_path, instance_name):
    """HV contra FE de cada método y, debajo, qué brazo ejecutó cada bloque del PS-MB."""
    fig, (ax, bar) = plt.subplots(2, 1, figsize=(12, 7), height_ratios=[4, 1], sharex=True)
    for method, result in results.items():
        label, color = METHODS[method]
        fe, hv = zip(*result["checkpoints"])
        ax.plot(fe, hv, color=color, linewidth=2.4 if method == "psmb" else 1.6,
                linestyle="--" if method == "psmb" else "-", label=f"{label} (HV final {result['hypervolume']:.4f})")
    ax.axvline(CUT, color="grey", linestyle=":", linewidth=1)
    ax.text(CUT, ax.get_ylim()[0], f"  corte {CUT} FE", color="grey", va="bottom", fontsize=9)
    ax.set_ylabel("Hipervolumen normalizado", fontweight="bold")
    ax.set_title(f"Convergencia del HV: {instance_name}", fontsize=13, fontweight="bold")
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="lower right")

    for b in psmb_blocks:
        start = b["fe_after"] - b["evaluations_used"]
        bar.barh(0, b["evaluations_used"], left=start, color=ARM_COLORS[b["arm_name"]], edgecolor="white", linewidth=0.5)
    for arm, color in ARM_COLORS.items():
        bar.barh(0, 0, color=color, label=ARM_LABELS[arm])
    bar.axvline(CUT, color="grey", linestyle=":", linewidth=1)
    bar.set_yticks([])
    bar.set_xlim(0, budget)
    bar.set_xlabel("Evaluaciones usadas (FE)", fontweight="bold")
    bar.set_title("Brazo que ejecutó cada bloque de 50 FE en el PS-MB", fontsize=10)
    bar.legend(loc="upper right", ncol=2, fontsize=9)
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()
    print(f"-> Gráfico de convergencia y reparto guardado en: {output_path}")


def plot_fronts_overlay(fronts, output_path, instance_name):
    """Proyecciones 2D de los frentes finales de cada método, superpuestos."""
    pairs = [("makespan", "tardiness", "Makespan", "Tardanza"),
             ("makespan", "energy", "Makespan", "Energía"),
             ("tardiness", "energy", "Tardanza", "Energía")]
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    for ax, (x, y, xl, yl) in zip(axes, pairs):
        for method in ("moead", "blmr", "psmb"):
            if method not in fronts:
                continue
            label, color = METHODS[method]
            ax.scatter([getattr(e.objectives, x) for e in fronts[method]], [getattr(e.objectives, y) for e in fronts[method]],
                       s=50 if method == "psmb" else 30, color=color, alpha=0.75, edgecolors="none",
                       marker="D" if method == "psmb" else "o", label=f"{label} ({len(fronts[method])} sol.)")
        ax.set_xlabel(xl, fontweight="bold")
        ax.set_ylabel(yl, fontweight="bold")
        ax.grid(True, linestyle="--", alpha=0.5)
    axes[0].legend(loc="best", framealpha=0.9)
    plt.suptitle(f"Frentes finales superpuestos: {instance_name}", fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()
    print(f"-> Gráfico de frentes superpuestos guardado en: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Corre el PS-MB sobre una instancia .dzn y genera sus gráficas")
    parser.add_argument("--instance", type=Path, required=True, help="Ruta al archivo .dzn")
    parser.add_argument("--seed", type=int, default=100, help="Semilla (default: 100, la primera del holdout)")
    parser.add_argument("--budget", type=int, default=3000, help="Presupuesto en FE, múltiplo de 50 y >= 600 (default: 3000)")
    parser.add_argument("--compare", action="store_true", help="Corre también BLMR solo y MOEA/D solo con la misma semilla")
    parser.add_argument("--select", default="all",
                        help="Solución a detallar: 'all', 'cmax', 'tardiness', 'energy', 'balanced' o número 1..N (default: all)")
    parser.add_argument("--show-front", action="store_true", help="Imprime todos los puntos del frente, no solo los destacados")
    parser.add_argument("--output-dir", type=Path, help="Carpeta de salida (default: results/demo/<instancia>_seed<semilla>)")
    args = parser.parse_args()

    if not args.instance.exists():
        parser.error(f"No existe el archivo de instancia '{args.instance}'")
    if args.budget < CUT or args.budget % 50:
        parser.error(f"El presupuesto debe ser múltiplo de 50 y al menos {CUT} FE")
    select = args.select.strip().lower()
    if select not in ("all", "cmax", "tardiness", "energy", "balanced") and not select.isdigit():
        parser.error(f"--select no reconocido: '{args.select}'")

    instance = load_dzn(args.instance)
    bounds = compute_instance_bounds(instance)
    out_dir = args.output_dir or ROOT / "results" / "demo" / f"{instance.name}_seed{args.seed}"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 75)
    print("PORTAFOLIO SECUENCIAL MOEA/D-BLMR (PS-MB)")
    print("=" * 75)
    print(f"Instancia:     {args.instance.name}")
    print(f"Estructura:    {len(instance.jobs)} trabajos, {instance.num_machines} máquinas, "
          f"{instance.total_operations} operaciones")
    print(f"Presupuesto:   {args.budget} FE  (MOEA/D + BLMR hasta {CUT} FE; después solo BLMR)")
    print(f"Semilla:       {args.seed}")
    print(f"Cotas de normalización: makespan [{bounds.cmax_min}, {bounds.cmax_max}], "
          f"tardanza [{bounds.tardiness_min}, {bounds.tardiness_max}], "
          f"energía [{bounds.energy_min:.2f}, {bounds.energy_max:.2f}]")
    print("-" * 75)

    methods = ["psmb", "blmr", "moead"] if args.compare else ["psmb"]
    results = {}
    for method in methods:
        print(f"Corriendo {METHODS[method][0]}...", flush=True)
        started = time.perf_counter()
        results[method] = run_method(instance, args.seed, args.budget, method)
        results[method]["wall_seconds"] = time.perf_counter() - started

    psmb = results["psmb"]
    print("\nREPARTO DEL PRESUPUESTO EN EL PS-MB:")
    print(f"{'Fase':<14} {'FE':<12} {'MOEA/D':>8} {'BLMR':>8}")
    print("-" * 46)
    for name, lo, hi, used in phase_allocations(psmb["blocks"], args.budget):
        print(f"{name:<14} {f'{lo}-{hi}':<12} {used['MOEA/D']:>8} {used['RegionExplorer']:>8}")
    total = psmb["allocations"]
    print("-" * 46)
    print(f"{'Total':<14} {'':<12} {total.get('MOEA/D', 0):>8} {total.get('RegionExplorer', 0):>8}"
          f"   (MOEA/D {100 * total.get('MOEA/D', 0) / args.budget:.1f} %)")

    print("\nRESULTADO:")
    print(f"{'Método':<14} {'HV':>10} {'Puntos':>8} {'Tiempo (s)':>11}")
    print("-" * 47)
    for method, result in results.items():
        print(f"{METHODS[method][0]:<14} {result['hypervolume']:>10.6f} {len(set(map(tuple, result['pareto_front']))):>8} "
              f"{result['wall_seconds']:>11.2f}")
    if args.compare:
        for method in ("blmr", "moead"):
            diff = psmb["hypervolume"] - results[method]["hypervolume"]
            print(f"  PS-MB menos {METHODS[method][0]}: {diff:+.6f}")

    entries = rebuild_front(instance, psmb["front_entries"])
    chosen, key = pick_solutions(entries, bounds, select)
    tags = {}
    for i, label in key.values():
        tags.setdefault(i, []).append(label)

    show_all = args.show_front or len(entries) <= 30
    print(f"\nFRENTE DE PARETO DEL PS-MB: {len(entries)} puntos distintos"
          + ("" if show_all else " (solo los destacados; --show-front para verlos todos)"))
    print(f"{'Opción':<8} {'Makespan':>10} {'Tardanza':>10} {'Energía':>12}  Perfil")
    print("-" * 75)
    for i, e in enumerate(entries):
        if show_all or i in tags:
            o = e.objectives
            print(f"#{i + 1:<7} {o.makespan:>10} {o.tardiness:>10} {o.energy:>12.2f}  {' | '.join(tags.get(i, []))}")

    print()
    plot_convergence(results, psmb["blocks"], args.budget, out_dir / "convergencia_y_reparto.png", instance.name)
    plot_pareto_front(entries, [i for i, _ in chosen], out_dir / "frente_psmb.png", instance.name, "PS-MB")
    if args.compare:
        fronts = {m: rebuild_front(instance, r["front_entries"]) for m, r in results.items()}
        plot_fronts_overlay(fronts, out_dir / "frentes_comparados.png", instance.name)

    for i, label in chosen:
        o = entries[i].objectives
        print("\n" + "=" * 75)
        print(f"SOLUCIÓN #{i + 1} ({label}): makespan {o.makespan}, tardanza {o.tardiness}, energía {o.energy:.2f}")
        print("=" * 75)
        if instance.num_machines <= 20:
            print_ascii_gantt(entries[i].schedule)
        slug = label.lower().replace(" ", "_").replace("#", "")
        plot_gantt_chart(entries[i].schedule, out_dir / f"gantt_sol{i + 1}_{slug}.png",
                         title=f"Gantt PS-MB: {instance.name}",
                         subtitle=f"Solución #{i + 1} [{label}]: makespan={o.makespan}, tardanza={o.tardiness}, energía={o.energy:.2f}")

    summary = dict(instance=str(args.instance), seed=args.seed, budget=args.budget, cut=CUT,
                   normalized_reference=[1.1, 1.1, 1.1],
                   methods={m: dict(hypervolume=r["hypervolume"], evaluations_used=r["evaluations_used"],
                                    front_size=len(r["pareto_front"]), wall_seconds=r["wall_seconds"],
                                    allocations=r.get("allocations"), checkpoints=r["checkpoints"],
                                    pareto_front=r["pareto_front"])
                            for m, r in results.items()})
    (out_dir / "resumen.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    print("\n" + "=" * 75)
    print(f"Archivos generados en: {out_dir.resolve()}")
    print("=" * 75)


if __name__ == "__main__":
    main()
