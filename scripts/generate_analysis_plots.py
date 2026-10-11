"""Script to generate comprehensive analysis plots from experimental and diagnostic CSVs.

Generates:
1. 01_performance_comparison_f865.png: Performance comparison (F8.6.5 1,480 runs + pairwise differences)
2. 02_convergence_dynamics.png: Dynamic convergence curves (HV vs FE) & stagnation points
3. 03_dmab_c_calibration.png: Impact of exploration factor c on budget allocation & HV
4. 04_adaptive_vs_uniform.png: DMAB adaptive vs Uniform portfolio paired comparison
5. 05_summary_dashboard.png: 4-panel executive dashboard summarizing all key findings
"""

import os
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

# Configure style
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
plt.rcParams['font.sans-serif'] = 'Arial'
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['figure.dpi'] = 300

OUTPUT_DIR = Path('results/plots')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Palette
PALETTE = {
    'NSGA-II': '#2b5c8f',       # Blue
    'Portfolio+DMAB': '#d95f02', # Vermilion / Orange
    'NSGA-II+LS': '#7570b3',    # Purple
    'MOPSO': '#1b9e77',         # Teal / Green
    'Uniform': '#66a61e',       # Olive
}


def plot_01_performance_f865():
    """Figure 1: Macro performance across 1,480 runs and pairwise deltas."""
    runs_path = Path('results/experiments/f865_runs.csv')
    pairwise_path = Path('results/experiments/f865_pairwise.csv')
    if not runs_path.exists() or not pairwise_path.exists():
        print("Skipping Fig 1: data missing")
        return

    runs = pd.read_csv(runs_path)
    pairwise = pd.read_csv(pairwise_path)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))

    # Panel A: Boxplot + Stripplot of HV
    order = ['NSGA-II', 'Portfolio+DMAB', 'NSGA-II+LS', 'MOPSO']
    sns.boxplot(
        data=runs,
        x='configuration',
        y='final_hv',
        order=order,
        palette=[PALETTE[c] for c in order],
        ax=ax1,
        width=0.45,
        boxprops=dict(alpha=0.7),
        showmeans=True,
        meanprops=dict(marker='D', markeredgecolor='black', markerfacecolor='white', markersize=6)
    )
    sns.stripplot(
        data=runs,
        x='configuration',
        y='final_hv',
        order=order,
        palette=[PALETTE[c] for c in order],
        ax=ax1,
        size=2.5,
        alpha=0.25,
        jitter=0.2
    )
    ax1.set_title('(A) Distribución Global de Hypervolume (1,480 Corridas)', fontsize=12, fontweight='bold', pad=10)
    ax1.set_xlabel('Configuración Algorítmica', fontsize=11, fontweight='bold')
    ax1.set_ylabel('Hypervolume Normalizado [0, 1.331]', fontsize=11, fontweight='bold')
    ax1.set_ylim(0.55, 1.0)

    # Annotate means
    means = runs.groupby('configuration')['final_hv'].mean()
    for idx, name in enumerate(order):
        m = means[name]
        ax1.text(idx, 0.57, f"μ = {m:.4f}", ha='center', fontsize=10, fontweight='bold',
                 bbox=dict(boxstyle='round,pad=0.2', facecolor='white', edgecolor=PALETTE[name], alpha=0.9))

    # Panel B: Pairwise difference (Portfolio - NSGA-II)
    diffs = pairwise['portfolio_minus_nsga2']
    sns.histplot(
        diffs,
        ax=ax2,
        color=PALETTE['Portfolio+DMAB'],
        kde=True,
        bins=25,
        alpha=0.6,
        edgecolor='black'
    )
    ax2.axvline(0, color='red', linestyle='--', linewidth=1.5, label='Paridad (ΔHV = 0)')
    mean_diff = diffs.mean()
    ax2.axvline(mean_diff, color='black', linestyle='-', linewidth=2, label=f'Media: {mean_diff:.4f}')

    # Percentage of wins
    losses = (diffs < -1e-6).sum()
    total = len(diffs)
    pct_loss = (losses / total) * 100

    ax2.set_title('(B) Diferencia Pareada por Semilla (Portfolio - NSGA-II)', fontsize=12, fontweight='bold', pad=10)
    ax2.set_xlabel('ΔHV (Portfolio - NSGA-II)', fontsize=11, fontweight='bold')
    ax2.set_ylabel('Frecuencia (Total: 370 pares)', fontsize=11, fontweight='bold')
    ax2.text(0.05, 0.85, f"Derrotas Portfolio: {losses}/{total} ({pct_loss:.1f}%)\nVictorias: {total-losses}/{total} ({100-pct_loss:.1f}%)",
             transform=ax2.transAxes, fontsize=10, fontweight='bold',
             bbox=dict(boxstyle='round,pad=0.4', facecolor='#fee0d2', edgecolor='#de2d26'))
    ax2.legend(loc='upper right', frameon=True)

    plt.tight_layout()
    out_file = OUTPUT_DIR / '01_performance_comparison_f865.png'
    plt.savefig(out_file, dpi=300)
    plt.close()
    print(f"Saved: {out_file}")


def plot_02_convergence_checkpoints():
    """Figure 2: Dynamic convergence curves (HV vs FE) from checkpoint audit."""
    cp_path = Path('results/diagnostics/mopso_audit_checkpoints.csv')
    if not cp_path.exists():
        print("Skipping Fig 2: data missing")
        return

    df = pd.read_csv(cp_path)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))

    # Panel A: HV vs FE
    for algo, color in [('NSGA-II', PALETTE['NSGA-II']),
                        ('NSGA-II+LS', PALETTE['NSGA-II+LS']),
                        ('MOPSO', PALETTE['MOPSO'])]:
        sub = df[df['algorithm'] == algo]
        agg = sub.groupby('fe')['hv'].agg(['mean', 'std']).reset_index()
        ax1.plot(agg['fe'], agg['mean'], label=algo, color=color, linewidth=2.5)
        ax1.fill_between(agg['fe'], agg['mean'] - agg['std'], agg['mean'] + agg['std'],
                         color=color, alpha=0.15)

    ax1.set_title('(A) Trayectoria de Convergencia: Hypervolume vs FE', fontsize=12, fontweight='bold', pad=10)
    ax1.set_xlabel('Evaluaciones de Función (FE)', fontsize=11, fontweight='bold')
    ax1.set_ylabel('Hypervolume Promedio', fontsize=11, fontweight='bold')
    ax1.axvline(280, color='gray', linestyle=':', alpha=0.7)
    ax1.text(290, 0.672, 'Estancamiento prematuro de MOPSO y LS (~280 FE)', fontsize=9, color='#333333', style='italic')
    ax1.legend(loc='lower right', frameon=True)

    # Panel B: Archive Size vs FE
    for algo, color in [('NSGA-II', PALETTE['NSGA-II']),
                        ('NSGA-II+LS', PALETTE['NSGA-II+LS']),
                        ('MOPSO', PALETTE['MOPSO'])]:
        sub = df[df['algorithm'] == algo]
        agg = sub.groupby('fe')['archive_size'].agg(['mean', 'std']).reset_index()
        ax2.plot(agg['fe'], agg['mean'], label=algo, color=color, linewidth=2.5)
        ax2.fill_between(agg['fe'], agg['mean'] - agg['std'], agg['mean'] + agg['std'],
                         color=color, alpha=0.15)

    ax2.set_title('(B) Crecimiento del Archivo: Soluciones No Dominadas vs FE', fontsize=12, fontweight='bold', pad=10)
    ax2.set_xlabel('Evaluaciones de Función (FE)', fontsize=11, fontweight='bold')
    ax2.set_ylabel('Tamaño Medio del Archivo (|A|)', fontsize=11, fontweight='bold')
    ax2.legend(loc='lower right', frameon=True)

    plt.tight_layout()
    out_file = OUTPUT_DIR / '02_convergence_dynamics.png'
    plt.savefig(out_file, dpi=300)
    plt.close()
    print(f"Saved: {out_file}")


def plot_03_dmab_c_calibration():
    """Figure 3: Impact of exploration factor c on DMAB budget allocation and final HV."""
    calib_path = Path('results/diagnostics/c_calibration_105_runs.csv')
    if not calib_path.exists():
        print("Skipping Fig 3: data missing")
        return

    df = pd.read_csv(calib_path)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))

    # Panel A: Stacked bar / line of pulls per c
    agg = df.groupby('c')[['nsga2_pulls', 'mopso_pulls', 'ls_pulls']].mean()
    c_vals = agg.index.astype(str)
    x = np.arange(len(c_vals))

    width = 0.55
    p1 = ax1.bar(x, agg['nsga2_pulls'], width, label='NSGA-II', color=PALETTE['NSGA-II'], alpha=0.85)
    p2 = ax1.bar(x, agg['mopso_pulls'], width, bottom=agg['nsga2_pulls'], label='MOPSO', color=PALETTE['MOPSO'], alpha=0.85)
    p3 = ax1.bar(x, agg['ls_pulls'], width, bottom=agg['nsga2_pulls'] + agg['mopso_pulls'], label='NSGA-II+LS', color=PALETTE['NSGA-II+LS'], alpha=0.85)

    ax1.set_xticks(x)
    ax1.set_xticklabels([f"c = {c}" for c in c_vals], fontsize=10, fontweight='bold')
    ax1.set_title('(A) Asignación de Bloques Adaptativos según c (17 Bloques)', fontsize=12, fontweight='bold', pad=10)
    ax1.set_xlabel('Factor de Exploración c', fontsize=11, fontweight='bold')
    ax1.set_ylabel('Promedio de Bloques Asignados (sobre 17)', fontsize=11, fontweight='bold')
    ax1.set_ylim(0, 22)
    ax1.legend(loc='upper left', frameon=True, fontsize=9)

    # Highlight c=0.07 (over-exploration) vs c=0.003 (optimal exploitation)
    ax1.annotate('c=0.07 original:\nSobre-exploración forzada\n(NSGA-II: 41%)',
                 xy=(4, 15), xytext=(3.1, 18.2),
                 arrowprops=dict(facecolor='black', shrink=0.05, width=1, headwidth=5),
                 fontsize=8.5, fontweight='bold', bbox=dict(boxstyle='round,pad=0.2', facecolor='#fee0d2'))
    ax1.annotate('c=0.003 óptimo:\nExplotación inteligente\n(NSGA-II: 85%)',
                 xy=(2, 15), xytext=(1.3, 18.2),
                 arrowprops=dict(facecolor='black', shrink=0.05, width=1, headwidth=5),
                 fontsize=8.5, fontweight='bold', bbox=dict(boxstyle='round,pad=0.2', facecolor='#e5f5e0'))

    # Panel B: Final HV vs c
    sns.boxplot(data=df, x='c', y='final_hv', ax=ax2, color='#fed976', width=0.45,
                showmeans=True, meanprops=dict(marker='o', markeredgecolor='black', markerfacecolor='red', markersize=7))
    sns.stripplot(data=df, x='c', y='final_hv', ax=ax2, color='black', alpha=0.4, size=4, jitter=0.15)

    ax2.set_title('(B) Hypervolume Final del Portfolio según Factor c', fontsize=12, fontweight='bold', pad=10)
    ax2.set_xlabel('Factor de Exploración c', fontsize=11, fontweight='bold')
    ax2.set_ylabel('Hypervolume Final', fontsize=11, fontweight='bold')

    plt.tight_layout()
    out_file = OUTPUT_DIR / '03_dmab_c_calibration.png'
    plt.savefig(out_file, dpi=300)
    plt.close()
    print(f"Saved: {out_file}")


def plot_04_adaptive_vs_uniform():
    """Figure 4: DMAB Adaptive vs Uniform Portfolio (F8.6.2 experiment)."""
    f862_path = Path('results/experiments/f86_adaptive_vs_uniform.csv')
    if not f862_path.exists():
        print("Skipping Fig 4: data missing")
        return

    df = pd.read_csv(f862_path)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))

    # Panel A: Scatter plot DMAB vs Uniform
    min_v = min(df['uniform_hv'].min(), df['dmab_hv'].min()) - 0.01
    max_v = max(df['uniform_hv'].max(), df['dmab_hv'].max()) + 0.01

    ax1.scatter(df['uniform_hv'], df['dmab_hv'], color='#2b5c8f', edgecolors='black', s=50, alpha=0.75)
    ax1.plot([min_v, max_v], [min_v, max_v], 'r--', linewidth=1.5, label='Paridad (DMAB = Uniforme)')

    wins = (df['hv_difference'] > 1e-6).sum()
    ties = (df['hv_difference'].abs() <= 1e-6).sum()
    losses = (df['hv_difference'] < -1e-6).sum()
    total = len(df)

    ax1.set_title('(A) Comparación Pareada: DMAB vs Uniforme (50 Corridas)', fontsize=12, fontweight='bold', pad=10)
    ax1.set_xlabel('Hypervolume Portafolio Uniforme', fontsize=11, fontweight='bold')
    ax1.set_ylabel('Hypervolume DMAB Adaptativo', fontsize=11, fontweight='bold')
    ax1.set_xlim(min_v, max_v)
    ax1.set_ylim(min_v, max_v)
    ax1.text(0.05, 0.82, f"DMAB > Uniforme: {wins}/{total} (80%)\nEmpates: {ties}/{total} (20%)\nUniforme > DMAB: {losses}/{total} (0%)",
             transform=ax1.transAxes, fontsize=10, fontweight='bold',
             bbox=dict(boxstyle='round,pad=0.3', facecolor='#e5f5e0', edgecolor='#31a354'))
    ax1.legend(loc='lower right', frameon=True)

    # Panel B: Distribution of Difference
    sns.histplot(df['hv_difference'], ax=ax2, color='#31a354', kde=True, bins=15, alpha=0.6, edgecolor='black')
    ax2.axvline(0, color='red', linestyle='--', linewidth=1.5, label='Cero Diferencia')
    mean_d = df['hv_difference'].mean()
    ax2.axvline(mean_d, color='black', linestyle='-', linewidth=2, label=f'Ganancia Media: +{mean_d:.4f}')

    ax2.set_title('(B) Ganancia Neta de Hypervolume (DMAB - Uniforme)', fontsize=12, fontweight='bold', pad=10)
    ax2.set_xlabel('Diferencia de Hypervolume (ΔHV)', fontsize=11, fontweight='bold')
    ax2.set_ylabel('Frecuencia de Corridas', fontsize=11, fontweight='bold')
    ax2.legend(loc='upper right', frameon=True)

    plt.tight_layout()
    out_file = OUTPUT_DIR / '04_adaptive_vs_uniform.png'
    plt.savefig(out_file, dpi=300)
    plt.close()
    print(f"Saved: {out_file}")


def plot_05_summary_dashboard():
    """Figure 5: 4-Panel Executive Dashboard unifying the 4 core stories of the thesis."""
    runs_path = Path('results/experiments/f865_runs.csv')
    cp_path = Path('results/diagnostics/mopso_audit_checkpoints.csv')
    calib_path = Path('results/diagnostics/c_calibration_105_runs.csv')
    f862_path = Path('results/experiments/f86_adaptive_vs_uniform.csv')

    fig, axs = plt.subplots(2, 2, figsize=(16, 12))

    # Panel 1: F8.6.5 Macro Performance
    if runs_path.exists():
        runs = pd.read_csv(runs_path)
        order = ['NSGA-II', 'Portfolio+DMAB', 'NSGA-II+LS', 'MOPSO']
        sns.boxplot(data=runs, x='configuration', y='final_hv', order=order,
                    palette=[PALETTE[c] for c in order], ax=axs[0, 0], width=0.45, showmeans=True,
                    meanprops=dict(marker='D', markeredgecolor='black', markerfacecolor='white', markersize=6))
        axs[0, 0].set_title('1. Desempeño Comparativo Global (1,480 Corridas)', fontsize=12, fontweight='bold')
        axs[0, 0].set_xlabel('')
        axs[0, 0].set_ylabel('Hypervolume Final')
        axs[0, 0].text(0.03, 0.08, 'NSGA-II > Portfolio > LS > MOPSO', transform=axs[0, 0].transAxes,
                       fontsize=10, fontweight='bold', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    # Panel 2: Convergence curves
    if cp_path.exists():
        df_cp = pd.read_csv(cp_path)
        for algo, color in [('NSGA-II', PALETTE['NSGA-II']), ('NSGA-II+LS', PALETTE['NSGA-II+LS']), ('MOPSO', PALETTE['MOPSO'])]:
            sub = df_cp[df_cp['algorithm'] == algo].groupby('fe')['hv'].mean().reset_index()
            axs[0, 1].plot(sub['fe'], sub['hv'], label=algo, color=color, linewidth=2.5)
        axs[0, 1].set_title('2. Dinámica de Convergencia: Progresión vs Estancamiento', fontsize=12, fontweight='bold')
        axs[0, 1].set_xlabel('Evaluaciones (FE)')
        axs[0, 1].set_ylabel('Hypervolume Promedio')
        axs[0, 1].legend(loc='lower right')
        axs[0, 1].text(0.03, 0.85, 'NSGA-II progresa sostenido;\nMOPSO y LS se estancan a ~300 FE',
                       transform=axs[0, 1].transAxes, fontsize=10, fontweight='bold',
                       bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    # Panel 3: DMAB c calibration
    if calib_path.exists():
        df_cal = pd.read_csv(calib_path)
        agg = df_cal.groupby('c')[['nsga2_pulls', 'mopso_pulls', 'ls_pulls']].mean()
        c_vals = agg.index.astype(str)
        x = np.arange(len(c_vals))
        width = 0.5
        axs[1, 0].bar(x, agg['nsga2_pulls'], width, label='NSGA-II', color=PALETTE['NSGA-II'])
        axs[1, 0].bar(x, agg['mopso_pulls'], width, bottom=agg['nsga2_pulls'], label='MOPSO', color=PALETTE['MOPSO'])
        axs[1, 0].bar(x, agg['ls_pulls'], width, bottom=agg['nsga2_pulls'] + agg['mopso_pulls'], label='NSGA-II+LS', color=PALETTE['NSGA-II+LS'])
        axs[1, 0].set_xticks(x)
        axs[1, 0].set_xticklabels([f"c={c}" for c in c_vals], fontweight='bold')
        axs[1, 0].set_title('3. Calibración de c en DMAB: Transición a Explotación', fontsize=12, fontweight='bold')
        axs[1, 0].set_xlabel('Factor de Exploración c')
        axs[1, 0].set_ylabel('Bloques Asignados (sobre 17)')
        axs[1, 0].legend(loc='upper right')

    # Panel 4: DMAB vs Uniform
    if f862_path.exists():
        df_uni = pd.read_csv(f862_path)
        sns.histplot(df_uni['hv_difference'], ax=axs[1, 1], color='#31a354', kde=True, bins=15, alpha=0.6, edgecolor='black')
        axs[1, 1].axvline(0, color='red', linestyle='--', linewidth=1.5, label='Paridad (0)')
        mean_d = df_uni['hv_difference'].mean()
        axs[1, 1].axvline(mean_d, color='black', linestyle='-', linewidth=2, label=f'Ganancia Media (+{mean_d:.4f})')
        axs[1, 1].set_title('4. Adaptabilidad Demostrada: DMAB vs Portafolio Uniforme', fontsize=12, fontweight='bold')
        axs[1, 1].set_xlabel('ΔHV (DMAB - Uniforme)')
        axs[1, 1].set_ylabel('Frecuencia')
        axs[1, 1].legend(loc='upper right')
        axs[1, 1].text(0.03, 0.85, 'DMAB vence a Uniforme en 80% de corridas\n(0 derrotas en 50 casos)',
                       transform=axs[1, 1].transAxes, fontsize=10, fontweight='bold',
                       bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    plt.tight_layout()
    out_file = OUTPUT_DIR / '05_summary_dashboard.png'
    plt.savefig(out_file, dpi=300)
    plt.close()
    print(f"Saved: {out_file}")


if __name__ == '__main__':
    print("Generating all analytical figures...")
    plot_01_performance_f865()
    plot_02_convergence_checkpoints()
    plot_03_dmab_c_calibration()
    plot_04_adaptive_vs_uniform()
    plot_05_summary_dashboard()
    print("Done!")
