"""Corre un método del estudio sobre una instancia .dzn y genera sus gráficas.

Usa exactamente las mismas funciones que las campañas finales: con la semilla 100 y
3000 FE el HV coincide con el guardado en el holdout.

Ejemplos (desde la raíz del proyecto):
    .venv\\Scripts\\python.exe scripts\\run_instance.py --instance data\\generated\\expanded_200\\base_c01_5x5_b01.dzn
    .venv\\Scripts\\python.exe scripts\\run_instance.py --instance ruta\\a\\otra.dzn --compare blmr moead
    .venv\\Scripts\\python.exe scripts\\run_instance.py --instance ruta\\a\\otra.dzn --method scaled --select energy
    .venv\\Scripts\\python.exe scripts\\run_instance.py --instance ruta\\a\\otra.dzn --method psmb --cut 900
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

from mojssp.decoder import Decoder
from mojssp.evaluator import Evaluator
from mojssp.io import load_dzn
from mojssp.normalization import compute_instance_bounds
from mojssp.regional_portfolio import run_regional_policy_experiment
from mojssp.solution import Solution
from plots import plot_convergence, plot_fronts_overlay, plot_gantt_chart, plot_pareto_front, print_ascii_gantt
from run_regional_composition_comparison import native_individual
from run_regional_explorer_controls import run_individual

PAIR = ["MOEA/D", "RegionExplorer"]
METHODS = {
    "psmb": ("PS-MB", "#1a1a1a"),
    "scaled": ("UCB escalado", "#8e44ad"),
    "passive": ("Rondas dinámicas", "#16a085"),
    "blmr": ("BLMR solo", "#2f6fd6"),
    "moead": ("MOEA/D solo", "#e0662d"),
    "nsga2": ("NSGA-II", "#c0392b"),
    "spea2": ("SPEA2", "#7f8c8d"),
    "nsga2_ls": ("NSGA-II+LS", "#d4ac0d"),
    "mopso": ("MOPSO", "#6d4c41"),
}
# Nombre del método en run_regional_composition_comparison.native_individual
NATIVE = {"moead": "moead", "nsga2": "nsga2_individual", "spea2": "spea2_individual",
          "nsga2_ls": "nsga2_ls_individual", "mopso": "mopso_individual"}


def run_method(instance, seed, budget, method, cut):
    """Ejecuta un método contando las llamadas reales al evaluador."""
    calls = 0
    original = Evaluator.evaluate

    def counted(self, *a, **kw):
        nonlocal calls
        calls += 1
        return original(self, *a, **kw)

    with patch.object(Evaluator, "evaluate", counted):
        if method == "psmb":
            result = run_regional_policy_experiment(instance, seed, PAIR, "dynamic", False, budget,
                dynamic_options=dict(exclusive_arm="RegionExplorer", exclusive_after=cut))
        elif method == "scaled":
            result = run_regional_policy_experiment(instance, seed, PAIR, "scaled", False, budget)
        elif method == "passive":
            result = run_regional_policy_experiment(instance, seed, PAIR, "dynamic", False, budget)
        elif method == "blmr":
            result = run_individual(instance, seed, "random", budget=budget)
        else:
            result = native_individual(instance, seed, NATIVE[method], budget=budget)
    assert calls == result["evaluations_used"] == budget, (method, calls, result["evaluations_used"])
    return result


def phase_allocations(blocks, budget, cut):
    """FE de cada brazo por fase: rondas de 300 FE hasta el corte y refinamiento después."""
    edges = list(range(0, cut, 300)) + [cut, budget] if cut else list(range(0, budget, 600)) + [budget]
    rows = []
    for k, (lo, hi) in enumerate(zip(edges, edges[1:])):
        used = Counter()
        for b in blocks:
            if lo <= b["fe_after"] - b["evaluations_used"] < hi:
                used[b["arm_name"]] += b["evaluations_used"]
        name = "Refinamiento" if cut and lo == cut else f"Ronda {k + 1}" if cut else f"Tramo {k + 1}"
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Corre un método sobre una instancia .dzn y genera sus gráficas")
    parser.add_argument("--instance", type=Path, required=True, help="Ruta al archivo .dzn")
    parser.add_argument("--method", choices=METHODS, default="psmb", help="Método principal (default: psmb)")
    parser.add_argument("--compare", nargs="+", choices=METHODS, default=[],
                        help="Otros métodos a correr con la misma semilla, p. ej. --compare blmr moead")
    parser.add_argument("--cut", type=int, default=600, help="Corte del PS-MB en FE, múltiplo de 50 (default: 600)")
    parser.add_argument("--seed", type=int, default=100, help="Semilla (default: 100, la primera del holdout)")
    parser.add_argument("--budget", type=int, default=3000, help="Presupuesto en FE, múltiplo de 50 (default: 3000)")
    parser.add_argument("--select", default="all",
                        help="Solución a detallar: 'all', 'cmax', 'tardiness', 'energy', 'balanced' o número 1..N (default: all)")
    parser.add_argument("--show-front", action="store_true", help="Imprime todos los puntos del frente, no solo los destacados")
    parser.add_argument("--output-dir", type=Path,
                        help="Carpeta de salida (default: results/demo/<instancia>_<método>_seed<semilla>)")
    args = parser.parse_args()

    if not args.instance.exists():
        parser.error(f"No existe el archivo de instancia '{args.instance}'")
    if args.budget < 600 or args.budget % 50:
        parser.error("El presupuesto debe ser múltiplo de 50 y al menos 600 FE")
    methods = [args.method] + [m for m in dict.fromkeys(args.compare) if m != args.method]
    cut = args.cut if "psmb" in methods else None
    if cut is not None and (cut % 50 or not 0 < cut <= args.budget):
        parser.error("El corte debe ser múltiplo de 50 y estar entre 50 y el presupuesto")
    if cut is not None and cut != 600:
        METHODS["psmb"] = (f"PS-MB (corte {cut})", METHODS["psmb"][1])
    select = args.select.strip().lower()
    if select not in ("all", "cmax", "tardiness", "energy", "balanced") and not select.isdigit():
        parser.error(f"--select no reconocido: '{args.select}'")

    instance = load_dzn(args.instance)
    bounds = compute_instance_bounds(instance)
    main_label = METHODS[args.method][0]
    out_dir = args.output_dir or ROOT / "results" / "demo" / f"{instance.name}_{args.method}_seed{args.seed}"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 75)
    print(f"{main_label.upper()} SOBRE UNA INSTANCIA")
    print("=" * 75)
    print(f"Instancia:     {args.instance.name}")
    print(f"Estructura:    {len(instance.jobs)} trabajos, {instance.num_machines} máquinas, "
          f"{instance.total_operations} operaciones")
    print(f"Presupuesto:   {args.budget} FE" + (f"  (PS-MB: MOEA/D + BLMR hasta {cut} FE; después solo BLMR)" if cut else ""))
    print(f"Semilla:       {args.seed}")
    print(f"Cotas de normalización: makespan [{bounds.cmax_min}, {bounds.cmax_max}], "
          f"tardanza [{bounds.tardiness_min}, {bounds.tardiness_max}], "
          f"energía [{bounds.energy_min:.2f}, {bounds.energy_max:.2f}]")
    print("-" * 75)

    results = {}
    for method in methods:
        print(f"Corriendo {METHODS[method][0]}...", flush=True)
        started = time.perf_counter()
        results[method] = run_method(instance, args.seed, args.budget, method, cut)
        results[method]["wall_seconds"] = time.perf_counter() - started

    main_result = results[args.method]
    blocks = main_result.get("blocks") or []
    if blocks:
        method_cut = cut if args.method == "psmb" else None
        print(f"\nREPARTO DEL PRESUPUESTO EN {main_label.upper()}:")
        print(f"{'Fase':<14} {'FE':<12} {'MOEA/D':>8} {'BLMR':>8}")
        print("-" * 46)
        for name, lo, hi, used in phase_allocations(blocks, args.budget, method_cut):
            print(f"{name:<14} {f'{lo}-{hi}':<12} {used['MOEA/D']:>8} {used['RegionExplorer']:>8}")
        total = main_result["allocations"]
        print("-" * 46)
        print(f"{'Total':<14} {'':<12} {total.get('MOEA/D', 0):>8} {total.get('RegionExplorer', 0):>8}"
              f"   (MOEA/D {100 * total.get('MOEA/D', 0) / args.budget:.1f} %)")

    print("\nRESULTADO:")
    print(f"{'Método':<18} {'HV':>10} {'Puntos':>8} {'Tiempo (s)':>11}")
    print("-" * 51)
    for method, result in results.items():
        print(f"{METHODS[method][0]:<18} {result['hypervolume']:>10.6f} {len(set(map(tuple, result['pareto_front']))):>8} "
              f"{result['wall_seconds']:>11.2f}")
    for method in methods[1:]:
        diff = main_result["hypervolume"] - results[method]["hypervolume"]
        print(f"  {main_label} menos {METHODS[method][0]}: {diff:+.6f}")

    fronts = {m: rebuild_front(instance, r["front_entries"]) for m, r in results.items()}
    entries = fronts[args.method]
    chosen, key = pick_solutions(entries, bounds, select)
    tags = {}
    for i, label in key.values():
        tags.setdefault(i, []).append(label)

    show_all = args.show_front or len(entries) <= 30
    print(f"\nFRENTE DE PARETO DE {main_label.upper()}: {len(entries)} puntos distintos"
          + ("" if show_all else " (solo los destacados; --show-front para verlos todos)"))
    print(f"{'Opción':<8} {'Makespan':>10} {'Tardanza':>10} {'Energía':>12}  Perfil")
    print("-" * 75)
    for i, e in enumerate(entries):
        if show_all or i in tags:
            o = e.objectives
            print(f"#{i + 1:<7} {o.makespan:>10} {o.tardiness:>10} {o.energy:>12.2f}  {' | '.join(tags.get(i, []))}")

    print()
    curves = [(*METHODS[m], r, m == args.method) for m, r in results.items()]
    plot_convergence(curves, blocks, args.budget, cut if args.method == "psmb" else None,
                     out_dir / "convergencia.png", instance.name)
    plot_pareto_front(entries, [i for i, _ in chosen], out_dir / "frente.png", instance.name, main_label)
    if len(methods) > 1:
        plot_fronts_overlay([(*METHODS[m], f, m == args.method) for m, f in fronts.items()],
                            out_dir / "frentes_comparados.png", instance.name)

    for i, label in chosen:
        o = entries[i].objectives
        print("\n" + "=" * 75)
        print(f"SOLUCIÓN #{i + 1} ({label}): makespan {o.makespan}, tardanza {o.tardiness}, energía {o.energy:.2f}")
        print("=" * 75)
        if instance.num_machines <= 20:
            print_ascii_gantt(entries[i].schedule)
        slug = label.lower().replace(" ", "_").replace("#", "")
        plot_gantt_chart(entries[i].schedule, out_dir / f"gantt_sol{i + 1}_{slug}.png",
                         title=f"Gantt {main_label}: {instance.name}",
                         subtitle=f"Solución #{i + 1} [{label}]: makespan={o.makespan}, tardanza={o.tardiness}, energía={o.energy:.2f}")

    summary = dict(instance=str(args.instance), method=args.method, seed=args.seed, budget=args.budget, cut=cut,
                   normalized_reference=[1.1, 1.1, 1.1],
                   methods={m: dict(hypervolume=r["hypervolume"], evaluations_used=r["evaluations_used"],
                                    front_size=len(fronts[m]), wall_seconds=r["wall_seconds"],
                                    allocations=r.get("allocations"), checkpoints=r["checkpoints"],
                                    pareto_front=r["pareto_front"])
                            for m, r in results.items()})
    (out_dir / "resumen.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    print("\n" + "=" * 75)
    print(f"Archivos generados en: {out_dir.resolve()}")
    print("=" * 75)


if __name__ == "__main__":
    main()
