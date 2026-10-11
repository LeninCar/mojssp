"""Compute detailed analysis of the 125 pilot runs:
- Instance-by-instance summary (mean, std, min, max, ranking).
- Aggregate comparison across all instances.
- Win-loss / best count per instance.
- Paired comparisons across same seeds.
- Complementarity analysis (union front size, exclusive solutions, marginal HV).
"""

from collections import defaultdict
import csv
from pathlib import Path
import statistics
from typing import Dict, List, Tuple

runs_path = Path("results/experiments/pilot_runs.csv")
comp_path = Path("results/experiments/pilot_complementarity.csv")
summary_path = Path("results/experiments/pilot_summary_by_instance.csv")

with open(runs_path, "r", encoding="utf-8") as f:
    runs = list(csv.DictReader(f))

with open(comp_path, "r", encoding="utf-8") as f:
    comps = list(csv.DictReader(f))

instances = sorted(list(set(r["instance"] for r in runs)))
algorithms = ["NSGA-II", "NSGA-II+LS", "MOPSO", "MOEA/D", "SPEA2"]
seeds = sorted(list(set(int(r["seed"]) for r in runs)))

print("=" * 115)
print("TABLA 1: DESEMPEÑO POR INSTANCIA Y ALGORITMO (Media ± Desv. Est. sobre 5 semillas)")
print("=" * 115)
hdr1 = f"{'Instancia':<14} | {'Algoritmo':<11} | {'Hipervolumen':<22} | {'Tamaño Archivo':<16} | {'Tiempo (s)':<12} | {'Sols. Exclusivas':<18} | {'Delta HV Marginal':<18}"
print(hdr1)
print("-" * 115)

for inst in instances:
    for alg in algorithms:
        m_runs = [r for r in runs if r["instance"] == inst and r["algorithm"] == alg]
        m_comp = [c for c in comps if c["instance"] == inst and c["algorithm"] == alg]

        hvs = [float(r["final_hv"]) for r in m_runs]
        archs = [int(r["archive_size"]) for r in m_runs]
        times = [float(r["runtime_seconds"]) for r in m_runs]
        excls = [int(c["exclusive_solutions_count"]) for c in m_comp]
        deltas = [float(c["marginal_hv_delta"]) for c in m_comp]

        hv_s = f"{statistics.mean(hvs):.4f} ± {statistics.stdev(hvs):.4f}"
        arch_s = f"{statistics.mean(archs):.1f} ± {statistics.stdev(archs):.1f}"
        time_s = f"{statistics.mean(times):.2f} ± {statistics.stdev(times):.2f}"
        excl_s = f"{statistics.mean(excls):.2f} (máx {max(excls)})"
        delta_s = f"{statistics.mean(deltas):.6f}"

        print(f"{inst:<14} | {alg:<11} | {hv_s:<22} | {arch_s:<16} | {time_s:<12} | {excl_s:<18} | {delta_s:<18}")
    print("-" * 115)

print("\n" + "=" * 115)
print("TABLA 2: RANKING Y MEJOR ALGORITMO POR INSTANCIA")
print("=" * 115)
hdr2 = f"{'Instancia':<14} | {'Rank 1 (Mejor)':<24} | {'Rank 2':<24} | {'Rank 3':<24} | {'Rank 4':<24} | {'Rank 5':<24}"
print(hdr2)
print("-" * 115)

best_counts = {alg: 0 for alg in algorithms}
rank_sum = {alg: 0 for alg in algorithms}

for inst in instances:
    means = {}
    for alg in algorithms:
        m_runs = [r for r in runs if r["instance"] == inst and r["algorithm"] == alg]
        means[alg] = statistics.mean(float(r["final_hv"]) for r in m_runs)
    sorted_algs = sorted(means.keys(), key=lambda a: means[a], reverse=True)
    best_counts[sorted_algs[0]] += 1
    for r_idx, a in enumerate(sorted_algs):
        rank_sum[a] += (r_idx + 1)
    ranks_str = [f"{a} ({means[a]:.4f})" for a in sorted_algs]
    print(f"{inst:<14} | {ranks_str[0]:<24} | {ranks_str[1]:<24} | {ranks_str[2]:<24} | {ranks_str[3]:<24} | {ranks_str[4]:<24}")

print("-" * 115)

print("\n" + "=" * 115)
print("TABLA 3: COMPARACIÓN AGREGADA GLOBAL (25 corridas por algoritmo)")
print("=" * 115)
hdr3 = f"{'Algoritmo':<11} | {'HV Global (Media±Std)':<24} | {'Ranking Promedio':<18} | {'Instancias Ganadas':<20} | {'Tiempo Medio (s)':<18} | {'Sols Excl. Totales':<20}"
print(hdr3)
print("-" * 115)

for alg in algorithms:
    a_runs = [r for r in runs if r["algorithm"] == alg]
    a_comp = [c for c in comps if c["algorithm"] == alg]
    hvs = [float(r["final_hv"]) for r in a_runs]
    times = [float(r["runtime_seconds"]) for r in a_runs]
    excls = [int(c["exclusive_solutions_count"]) for c in a_comp]
    hv_glob = f"{statistics.mean(hvs):.4f} ± {statistics.stdev(hvs):.4f}"
    avg_rank = f"{rank_sum[alg] / len(instances):.2f}"
    wins = f"{best_counts[alg]} / {len(instances)}"
    t_glob = f"{statistics.mean(times):.2f} s"
    tot_excl = f"{sum(excls)} (media {statistics.mean(excls):.2f})"
    print(f"{alg:<11} | {hv_glob:<24} | {avg_rank:<18} | {wins:<20} | {t_glob:<18} | {tot_excl:<20}")

print("-" * 115)

print("\n" + "=" * 115)
print("TABLA 4: ANÁLISIS DE COMPLEMENTARIEDAD RESPECTO A LA UNIÓN NO DOMINADA")
print("=" * 115)
hdr4 = f"{'Instancia':<14} | {'HV Unión Medio':<16} | {'Tamaño Unión':<14} | {'NSGA-II Excl.':<14} | {'NSGA-II+LS Excl.':<18} | {'MOPSO Excl.':<14} | {'MOEA/D Excl.':<14} | {'SPEA2 Excl.':<14}"
print(hdr4)
print("-" * 115)

for inst in instances:
    u_hvs = []
    u_sizes = []
    excl_by_alg = defaultdict(list)
    for s in seeds:
        m_comp = [c for c in comps if c["instance"] == inst and int(c["seed"]) == s]
        u_hvs.append(float(m_comp[0]["union_hv"]))
        u_sizes.append(int(m_comp[0]["union_archive_size"]))
        for row in m_comp:
            excl_by_alg[row["algorithm"]].append(int(row["exclusive_solutions_count"]))

    u_hv_s = f"{statistics.mean(u_hvs):.4f} ± {statistics.stdev(u_hvs):.4f}"
    u_sz_s = f"{statistics.mean(u_sizes):.1f} sols"
    e_nsga = f"{statistics.mean(excl_by_alg['NSGA-II']):.1f}"
    e_ls = f"{statistics.mean(excl_by_alg['NSGA-II+LS']):.1f}"
    e_mopso = f"{statistics.mean(excl_by_alg['MOPSO']):.1f}"
    e_moead = f"{statistics.mean(excl_by_alg['MOEA/D']):.1f}"
    e_spea2 = f"{statistics.mean(excl_by_alg['SPEA2']):.1f}"

    print(f"{inst:<14} | {u_hv_s:<16} | {u_sz_s:<14} | {e_nsga:<14} | {e_ls:<18} | {e_mopso:<14} | {e_moead:<14} | {e_spea2:<14}")

print("-" * 115)

print("\n" + "=" * 115)
print("TABLA 5: COMPARACIONES PAREADAS POR INSTANCIA Y SEMILLA (Diferencia de HV: A - B)")
print("=" * 115)
hdr5 = f"{'Par de Algoritmos (A vs B)':<30} | {'Media Delta HV (A - B)':<26} | {'Victorias A':<14} | {'Empates (±0.001)':<18} | {'Victorias B':<14}"
print(hdr5)
print("-" * 115)

pairs = [
    ("SPEA2", "NSGA-II"),
    ("MOEA/D", "NSGA-II"),
    ("SPEA2", "MOEA/D"),
    ("NSGA-II", "NSGA-II+LS"),
    ("NSGA-II", "MOPSO"),
    ("MOEA/D", "MOPSO"),
]

for alg_a, alg_b in pairs:
    deltas = []
    wins_a = 0
    ties = 0
    wins_b = 0
    for inst in instances:
        for s in seeds:
            r_a = next(r for r in runs if r["instance"] == inst and int(r["seed"]) == s and r["algorithm"] == alg_a)
            r_b = next(r for r in runs if r["instance"] == inst and int(r["seed"]) == s and r["algorithm"] == alg_b)
            d = float(r_a["final_hv"]) - float(r_b["final_hv"])
            deltas.append(d)
            if d > 0.001:
                wins_a += 1
            elif d < -0.001:
                wins_b += 1
            else:
                ties += 1
    m_d = f"{statistics.mean(deltas):+.6f} ± {statistics.stdev(deltas):.6f}"
    print(f"{alg_a + ' vs ' + alg_b:<30} | {m_d:<26} | {wins_a:<14} | {ties:<18} | {wins_b:<14}")

print("-" * 115)

