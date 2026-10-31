"""Figures and tables of thesis chapter 6, read only from the saved campaign results.

Run from the project root:
    .venv\\Scripts\\python.exe scripts\\figures\\cap6.py [--out .local/notes/cap6]

Writes figures (PDF + PNG) and LaTeX snippets (booktabs) to the output folder. No search is run.
Paired confidence intervals resample instances or bases (never seeds) with a fixed seed.
"""

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "results"
BOOT, RNG_SEED = 20000, 20261029

BLUE, ORANGE, GRAY, INK, MUTED = "#2a78d6", "#eb6834", "#8a8984", "#0b0b0b", "#52514e"
plt.rcParams.update(
    {
        "font.family": "serif",
        "mathtext.fontset": "cm",
        "font.size": 9,
        "axes.edgecolor": MUTED,
        "axes.labelcolor": INK,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": "#e6e5e1",
        "grid.linewidth": 0.6,
        "pdf.fonttype": 42,
        "savefig.bbox": "tight",
    }
)


def boot_ci(values, groups=None):
    """Mean and 95% bootstrap CI; with groups, resample whole groups (cluster bootstrap)."""
    rng = np.random.default_rng(RNG_SEED)
    values = np.asarray(values, dtype=float)
    if groups is None:
        idx = rng.integers(0, len(values), size=(BOOT, len(values)))
        means = values[idx].mean(axis=1)
    else:
        keys = sorted(set(groups))
        sums = np.array([values[np.asarray(groups) == k].sum() for k in keys])
        sizes = np.array([(np.asarray(groups) == k).sum() for k in keys])
        idx = rng.integers(0, len(keys), size=(BOOT, len(keys)))
        means = sums[idx].sum(axis=1) / sizes[idx].sum(axis=1)
    lo, hi = np.quantile(means, [0.025, 0.975])
    return values.mean(), lo, hi


def save(fig, out, name):
    for ext in ("png", "pdf"):
        fig.savefig(out / f"{name}.{ext}", dpi=200)
    plt.close(fig)


def write_figure_tex(out, name, caption, note, label, width="0.95\\linewidth"):
    (out / f"{name}.tex").write_text(
        "\\begin{figure}[htbp]\n  \\centering\n"
        f"  \\includegraphics[width={width}]{{{name}.pdf}}\n"
        f"  \\caption{{{caption}}}\n  \\label{{{label}}}\n"
        f"  \\par\\smallskip\\begin{{minipage}}{{0.95\\linewidth}}\\footnotesize\\textit{{Nota.}} {note}\\end{{minipage}}\n"
        "\\end{figure}\n",
        encoding="utf-8",
    )


def write_table_tex(out, name, df, caption, label, note, align, group_header=""):
    # booktabs written directly (pandas.to_latex needs jinja2, not in requirements)
    lines = [" & ".join(map(str, df.columns)) + " \\\\"]
    lines += [" & ".join(map(str, row)) + " \\\\" for row in df.itertuples(index=False)]
    body = (
        f"  \\begin{{tabular}}{{{align}}}\n  \\toprule\n{group_header}  {lines[0]}\n  \\midrule\n"
        + "".join(f"  {line}\n" for line in lines[1:])
        + "  \\bottomrule\n  \\end{tabular}\n"
    )
    (out / f"{name}.tex").write_text(
        "\\begin{table}[htbp]\n  \\centering\n  \\footnotesize\n  \\setlength{\\tabcolsep}{4pt}\n"
        f"  \\caption{{{caption}}}\n  \\label{{{label}}}\n"
        f"{body}"
        f"  \\par\\smallskip\\begin{{minipage}}{{0.95\\linewidth}}\\footnotesize\\textit{{Nota.}} {note}\\end{{minipage}}\n"
        "\\end{table}\n",
        encoding="utf-8",
    )


def fmt(x, digits=4, sign=False):
    return f"{x:+.{digits}f}" if sign else f"{x:.{digits}f}"


def ci_text(lo, hi):
    return f"[{lo:+.4f}; {hi:+.4f}]"


# Figure 6.a: final HV by cut point (development sweep, after the holdout)
def figure_cut_sweep(out):
    camp = RES / "experiments/cut_sweep_development_20261028"
    d = pd.read_csv(camp / "by_instance.csv", encoding="utf-8-sig")
    hv = d.pivot(index="case", columns="method", values="mean_hypervolume")
    base = ["_".join(c.split("_")[:4]) for c in hv.index]
    rows = [
        ("Corte 300", "cut_300"),
        ("Corte 600 (PS-MB)", "cut_600"),
        ("Corte 900", "cut_900"),
        ("Corte 1200", "cut_1200"),
        ("Corte 1800", "cut_1800"),
        ("Pareja sin corte", "passive"),
        ("UCB escalado", "moead_blmr_scaled"),
        ("BLMR solo", "explorer_solo"),
        ("MOEA/D solo", "moead"),
    ]
    stats = []
    for name, m in rows:
        diff = hv[m] - hv["cut_600"]
        mean, lo, hi = (0.0, 0.0, 0.0) if m == "cut_600" else boot_ci(diff.values, base)
        stats.append((name, m, mean, lo, hi, int((diff > 0).sum()), hv[m].mean()))

    fig, ax = plt.subplots(figsize=(6.3, 3.4))
    y = np.arange(len(stats))[::-1]
    for yi, (name, m, mean, lo, hi, _, _) in zip(y, stats):
        cut = m.startswith("cut")
        color = BLUE if cut else GRAY
        ax.plot([lo, hi], [yi, yi], color=color, lw=2, solid_capstyle="round")
        ax.plot(mean, yi, "o", ms=6, color=color if m != "cut_600" else INK, mec="white", mew=1)
    ax.axvline(0, color=INK, lw=0.8)
    ax.axhline(y[4] - 0.5, color="#c9c8c3", lw=0.8, ls="--")
    ax.set_yticks(y, [s[0] for s in stats])
    ax.set_xlabel("Diferencia de HV frente al corte de 600 FE (IC 95 %, agrupado por base)")
    ax.grid(axis="y", visible=False)
    for yi, s in zip(y, stats):
        ax.text(
            1.01, yi, f"{s[6]:.4f}", transform=ax.get_yaxis_transform(), va="center", fontsize=8, color=MUTED
        )
    ax.text(1.01, y[0] + 0.9, "HV medio", transform=ax.get_yaxis_transform(), fontsize=8, color=MUTED)
    save(fig, out, "fig6_corte")
    table = pd.DataFrame(
        [
            dict(
                Método=s[0],
                HV=fmt(s[6]),
                **{
                    "$\\Delta$ vs 600": "—" if s[1] == "cut_600" else fmt(s[2], sign=True),
                    "IC 95 \\%": "—" if s[1] == "cut_600" else ci_text(s[3], s[4]),
                    "Inst. a favor": "—" if s[1] == "cut_600" else f"{s[5]}/120",
                },
            )
            for s in stats
        ]
    )
    note = (
        "Campaña \\texttt{cut\\_sweep\\_development\\_20261028}: 120 instancias de desarrollo de "
        "\\texttt{expanded\\_200} (24 bases $\\times$ 5 perfiles, 8 tamaños), semillas 100, 200 y 300, 3000 FE. "
        "Diferencias pareadas por instancia (media de las tres semillas); IC bootstrap agrupado por base "
        "(24 grupos, 20\\,000 remuestreos). El barrido se ejecutó después de la evaluación holdout y no "
        "intervino en la elección del corte de 600 FE, fijado de antemano."
    )
    write_figure_tex(
        out, "fig6_corte", "Hipervolumen final según el punto de corte de PS-MB.", note, "fig:cap6_corte"
    )
    write_table_tex(
        out,
        "tab6_corte",
        table,
        "Barrido del punto de corte en el banco de desarrollo.",
        "tab:cap6_corte",
        note,
        "lrrrr",
    )


# Figure 6.b: BLMR vs MOEA/D by instance size (paired per seed)
def figure_blmr_vs_moead(out):
    e = pd.read_csv(RES / "experiments/regional_explorer_individual_development_20261023/runs.csv")
    m = pd.read_csv(
        RES / "experiments/moead_pairs_and_80_development_20261023/runs.csv", encoding="utf-8-sig"
    )
    e = e[e.method == "explorer_random_individual"]
    m = m[m.method == "moead"]
    j = e.merge(m, on=["case", "master_seed"], suffixes=("_b", "_m"))
    j["diff"] = j.hypervolume_b - j.hypervolume_m
    j["size"] = j.case.str.split("_").str[-1].str.replace("x", "×")
    order = ["5×5", "10×10", "20×10", "10×20", "20×20", "30×20"]
    assert len(j) == 18 and set(j["size"]) == set(order)

    j["order"] = j["size"].map(order.index)
    j = j.sort_values(["order", "master_seed"])
    j[["case", "size", "master_seed", "hypervolume_b", "hypervolume_m", "diff"]].rename(
        columns={"hypervolume_b": "hv_blmr", "hypervolume_m": "hv_moead", "diff": "hv_blmr_minus_moead"}
    ).to_csv(out / "fig6_blmr_moead_tamano_datos.csv", index=False)

    fig, ax = plt.subplots(figsize=(6.3, 3.6))
    top = max(0.13, j["diff"].max() + 0.015)
    bottom = min(-0.07, j["diff"].min() - 0.015)
    ax.axhspan(0, top, color=BLUE, alpha=0.07, lw=0)
    ax.axhspan(bottom, 0, color=ORANGE, alpha=0.08, lw=0)
    ax.axhline(0, color=INK, lw=0.9)
    offsets = np.array([-0.12, 0.0, 0.12])
    for i, size in enumerate(order):
        s = j[j["size"] == size]
        colors = [BLUE if v > 0 else ORANGE for v in s["diff"]]
        ax.scatter(
            i + offsets,
            s["diff"],
            s=34,
            color=colors,
            edgecolor="white",
            linewidth=0.9,
            zorder=3,
            label="Semilla (42, 43, 44)" if i == 0 else None,
        )
        mean = s["diff"].mean()
        ax.plot(
            [i - 0.24, i + 0.24],
            [mean, mean],
            color=INK,
            lw=1.8,
            zorder=4,
            solid_capstyle="butt",
            label="Media de las tres semillas (valor entre paréntesis)" if i == 0 else None,
        )
    ax.text(
        0.99,
        0.97,
        "BLMR obtiene mayor HV",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=8.5,
        color="#1c5cab",
    )
    ax.text(
        0.99,
        0.03,
        "MOEA/D obtiene mayor HV",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=8.5,
        color="#b4471d",
    )
    ax.set_ylim(bottom, top)
    ax.set_xlim(-0.6, len(order) - 0.3)
    means = j.groupby("size")["diff"].mean()
    ax.set_xticks(range(len(order)), [f"{s}\n({means[s]:+.3f})".replace("-", "−") for s in order])
    ax.set_xlabel("Tamaño de la instancia (trabajos × máquinas)")
    ax.set_ylabel("HV(BLMR) − HV(MOEA/D)")
    ax.set_title("Diferencia pareada de hipervolumen por tamaño de instancia", fontsize=9.5, loc="left")
    ax.grid(axis="x", visible=False)
    leg = ax.legend(
        loc="upper center", bbox_to_anchor=(0.5, -0.24), ncol=2, fontsize=8, frameon=False, handlelength=1.4
    )
    for h in leg.legend_handles[:1]:
        h.set_color(MUTED)
    save(fig, out, "fig6_blmr_moead_tamano")
    note = (
        "BLMR individual con regiones aleatorias (\\texttt{regional\\_explorer\\_individual\\_development\\_20261023}) "
        "frente a MOEA/D individual (\\texttt{moead\\_pairs\\_and\\_80\\_development\\_20261023}). Seis bases de "
        "desarrollo, una por tamaño, semillas 42, 43 y 44, 3000 FE. Cada punto es la diferencia de una semilla (azul si favorece a BLMR, naranja si favorece a MOEA/D); la línea negra y el valor entre paréntesis son la media de las tres semillas. Datos de la figura en \\texttt{fig6\\_blmr\\_moead\\_tamano\\_datos.csv}. Diferencias pareadas por instancia y semilla. "
        "Cada tamaño está representado por una sola base, por lo que tamaño y base están confundidos; varias "
        "semillas contradicen la tendencia media."
    )
    write_figure_tex(
        out,
        "fig6_blmr_moead_tamano",
        "Diferencia de hipervolumen entre BLMR y MOEA/D según el tamaño de la instancia.",
        note,
        "fig:cap6_blmr_moead",
    )


# Figure 6.2: SW-UCB against uniform, MOEA/D and the per-run best individual (phase 2 budget campaign)
def figure_swucb_budget(out):
    r = pd.read_csv(RES / "historical/expanded_portfolio_phase2/budget_diagnostic/budget_runs.csv")
    assert (r.status == "SUCCESS").all() and (r.evaluations_used == r.budget).all()
    hv = r.pivot_table(index=["budget", "base_id", "seed"], columns="algorithm", values="final_hv")
    ucb, uniform = "Adaptive Portfolio (DMAB)", "Uniform Portfolio (Round-Robin)"
    methods = [
        ("MOEA/D", "MOEA/D", BLUE),
        ("NSGA-II", "NSGA-II", BLUE),
        ("SPEA2", "SPEA2", BLUE),
        (ucb, "Portafolio\nSW-UCB", ORANGE),
        (uniform, "Portafolio\nuniforme", "#f5b08f"),
    ]
    expected = {
        (3000, uniform): 0.0054,
        (3000, "MOEA/D"): -0.0472,
        (5000, uniform): 0.0033,
        (5000, "MOEA/D"): -0.0542,
    }
    budgets, annex, means = (3000, 5000), [], {}
    for budget in budgets:
        h = hv.loc[budget]
        # Same 10 instances x 3 seeds for every method of this budget
        assert len(h) == 30 and h.index.get_level_values(0).nunique() == 10 and not h.isna().any().any()
        for col in (uniform, "MOEA/D"):
            diff = (h[ucb] - h[col]).mean()
            assert round(diff, 4) == expected[(budget, col)], (budget, col, diff)
        for col, label, _ in methods:
            means[(budget, col)] = h[col].mean()
            annex += [
                {
                    "budget": budget,
                    "method": label.replace("\n", " "),
                    "instance": b,
                    "seed": s,
                    "final_hv": v,
                }
                for (b, s), v in h[col].items()
            ]
    pd.DataFrame(annex).to_csv(out / "fig6_swucb_presupuesto_datos.csv", index=False)

    fig, axes = plt.subplots(1, 2, figsize=(6.6, 3.6), sharey=True)
    for ax, budget in zip(axes, budgets):
        per_instance = hv.loc[budget].groupby(level=0).mean()
        for k, (col, label, color) in enumerate(methods):
            mean = means[(budget, col)]
            ax.bar(k, mean, width=0.68, color=color, edgecolor="white", linewidth=0)
            ax.scatter(
                k + np.linspace(-0.18, 0.18, len(per_instance)), per_instance[col], s=7, color=INK, zorder=3
            )
            # Inside the bar base, as in fig6_portafolio_inicial, so it never sits on a point
            ax.text(
                k,
                0.04,
                f"{mean:.4f}",
                ha="center",
                va="bottom",
                fontsize=8,
                rotation=90,
                color="white" if color != "#f5b08f" else INK,
                fontweight="bold",
            )
        ax.set_xticks(range(len(methods)), [m[1] for m in methods], fontsize=7.5)
        ax.set_title(f"{budget} FE", fontsize=9.5)
        ax.grid(axis="x", visible=False)
    axes[0].set_ylim(0, 1.25)
    axes[0].set_ylabel("HV final (media de 30 corridas)")
    handles = [
        plt.Rectangle((0, 0), 1, 1, color=BLUE),
        plt.Rectangle((0, 0), 1, 1, color=ORANGE),
        plt.Rectangle((0, 0), 1, 1, color="#f5b08f"),
        plt.Line2D([], [], marker="o", ls="", ms=3.5, color=INK),
    ]
    fig.legend(
        handles,
        [
            "Algoritmo individual",
            "Portafolio SW-UCB",
            "Portafolio uniforme",
            "Media por instancia (3 semillas)",
        ],
        loc="lower center",
        bbox_to_anchor=(0.5, -0.06),
        ncol=4,
        fontsize=8,
        frameon=False,
    )
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    save(fig, out, "fig6_swucb_presupuesto")
    note = (
        "Campaña de presupuesto de la fase 2 (\\texttt{results/historical/expanded\\_portfolio\\_phase2/budget\\_diagnostic/"
        "budget\\_runs.csv}): portafolio de MOEA/D, NSGA-II y SPEA2; 10 instancias de \\texttt{expanded\\_200}, semillas "
        "42 a 44, corridas independientes de 3000 y 5000 FE, bloques de 50 FE, SW-UCB con $W=10$ y $c=0{.}07$. "
        "Los cinco métodos usan las mismas instancias y semillas en cada presupuesto, con población 30; los portafolios "
        "reparten el mismo presupuesto entre MOEA/D, NSGA-II y SPEA2. Barras: media de 30 corridas; "
        "puntos: media de cada instancia. Diferencias pareadas de SW-UCB: +0.0054 y +0.0033 frente al uniforme, "
        "$-$0.0472 y $-$0.0542 frente a MOEA/D (3000 y 5000 FE). El HV normalizado puede superar 1 (máximo 1.331). "
        "Datos por corrida en \\texttt{fig6\\_swucb\\_presupuesto\\_datos.csv}."
    )
    write_figure_tex(
        out,
        "fig6_swucb_presupuesto",
        "Hipervolumen final de MOEA/D, NSGA-II, SPEA2 y de los portafolios SW-UCB y uniforme con 3000 y "
        "5000 FE.",
        note,
        "fig:cap6_swucb_presupuesto",
    )
    return means


# Figure 6.5: BLMR alone against MOEA/D, NSGA-II and SPEA2 on the six development bases
def figure_blmr_individuals(out):
    e = pd.read_csv(RES / "experiments/regional_explorer_individual_development_20261023/runs.csv")
    w = pd.read_csv(RES / "experiments/weighted_pilot_development_20261023/runs.csv", encoding="utf-8-sig")
    e = e[e.method == "explorer_random_individual"].assign(method="BLMR")
    w = w[w.method.isin(["moead", "nsga2", "spea2"])].replace(
        {"method": {"moead": "MOEA/D", "nsga2": "NSGA-II", "spea2": "SPEA2"}}
    )
    runs = pd.concat([e, w])[["case", "master_seed", "method", "hypervolume"]]
    hv = runs.pivot_table(index=["case", "master_seed"], columns="method", values="hypervolume")
    # Same 6 bases x seeds 42-44 for the four algorithms (identical model and HV code, checked in config.json hashes)
    assert hv.shape == (18, 4) and not hv.isna().any().any()
    assert sorted(hv.index.get_level_values(1).unique()) == [42, 43, 44]
    expected = {"BLMR": 0.9847, "MOEA/D": 0.9651, "NSGA-II": 0.9360, "SPEA2": 0.9373}
    assert all(round(hv[m].mean(), 4) == v for m, v in expected.items()), hv.mean()
    runs.rename(columns={"hypervolume": "final_hv"}).to_csv(
        out / "fig6_blmr_individuales_datos.csv", index=False
    )

    by_instance = hv.groupby(level=0).mean()
    bars = [("BLMR", ORANGE), ("MOEA/D", BLUE), ("NSGA-II", "#9db9dd"), ("SPEA2", "#9db9dd")]
    fig, ax = plt.subplots(figsize=(5.4, 3.4))
    for i, (name, color) in enumerate(bars):
        mean = hv[name].mean()
        ax.bar(i, mean, width=0.62, color=color, edgecolor="white", linewidth=0)
        ax.scatter(
            i + np.linspace(-0.16, 0.16, len(by_instance)), by_instance[name], s=12, color=INK, zorder=3
        )
        ax.text(
            i,
            0.04,
            f"{mean:.4f}",
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
            color="white" if color != "#9db9dd" else INK,
        )
    ax.set_xticks(range(len(bars)), [b[0] for b in bars])
    ax.set_ylim(0, 1.2)
    ax.set_ylabel("HV final (media de 18 corridas)")
    ax.grid(axis="x", visible=False)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in (ORANGE, BLUE, "#9db9dd")]
    handles.append(plt.Line2D([], [], marker="o", ls="", ms=4, color=INK))
    ax.legend(
        handles,
        ["BLMR", "MOEA/D", "Otros individuales", "Media por instancia (3 semillas)"],
        loc="upper center",
        bbox_to_anchor=(0.5, -0.12),
        ncol=2,
        fontsize=8,
        frameon=False,
    )
    save(fig, out, "fig6_blmr_individuales")
    note = (
        "BLMR individual con regiones aleatorias (\\texttt{regional\\_explorer\\_individual\\_development\\_20261023}, "
        "30 soluciones aleatorias iniciales y 2970 FE de búsqueda) y MOEA/D, NSGA-II y SPEA2 individuales "
        "(\\texttt{weighted\\_pilot\\_development\\_20261023}, reutilizados sin cambios en "
        "\\texttt{moead\\_pairs\\_and\\_80\\_development\\_20261023}). Seis bases de desarrollo (5$\\times$5 a 30$\\times$20), "
        "semillas 42, 43 y 44, 3000 FE, población 30; las tres campañas usan el mismo código del modelo, decodificador, "
        "evaluador, normalización e HV. Barras: media de 18 corridas; puntos: media de cada base. Datos por corrida en "
        "\\texttt{fig6\\_blmr\\_individuales\\_datos.csv}. Resultados de desarrollo, sin confirmación independiente."
    )
    write_figure_tex(
        out,
        "fig6_blmr_individuales",
        "Hipervolumen final de BLMR y de MOEA/D, NSGA-II y SPEA2 individuales en el banco de desarrollo.",
        note,
        "fig:cap6_blmr_individuales",
        width="0.8\\linewidth",
    )


# Figure 6.c: SW-UCB exploration and exploitation terms (selected arm)
def figure_swucb(out):
    d = pd.read_csv(RES / "historical/expanded_portfolio_phase2/closure_audit/adaptation_audit.csv")
    assert len(d) == 2820
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.6, 2.9), gridspec_kw={"width_ratios": [1, 1.15]})
    a1.scatter(d.exploitation_term, d.exploration_term, s=4, alpha=0.25, color=BLUE, linewidth=0)
    a1.plot([0, 0.1], [0, 0.1], color=INK, lw=0.8, ls="--")
    a1.text(0.062, 0.052, "exploración = explotación", rotation=45, fontsize=7.5, color=MUTED, ha="center")
    a1.set_xlim(0, 0.1)
    a1.set_ylim(0, 0.1)
    a1.set_aspect("equal")
    a1.set_xlabel("Término de explotación")
    a1.set_ylabel("Término de exploración")
    a1.set_title("(a) Cada decisión (n = 2820)", fontsize=9, loc="left")

    pos = d[d.exploitation_term > 0]
    ratio = np.log10(pos.exploration_term / pos.exploitation_term)
    a2.hist(ratio, bins=40, color=BLUE, edgecolor="white", linewidth=0.5)
    med = np.median(ratio)
    a2.axvline(med, color=INK, lw=0.9)
    a2.text(med + 0.08, a2.get_ylim()[1] * 0.92, f"mediana {10**med:.0f}×", fontsize=8, color=INK)
    a2.set_xlabel("log$_{10}$(exploración / explotación)")
    a2.set_ylabel("Decisiones")
    a2.set_title(f"(b) Explotación > 0 (n = {len(pos)})", fontsize=9, loc="left")
    a2.grid(axis="x", visible=False)
    fig.tight_layout()
    save(fig, out, "fig6_swucb")
    zero = int((d.exploitation_term <= 0).sum())
    ratio_means = d.exploration_term.mean() / d.exploitation_term.mean()
    note = (
        "Fase 2 (\\texttt{expanded\\_portfolio\\_phase2/closure\\_audit/adaptation\\_audit.csv}): 10 instancias de "
        "\\texttt{expanded\\_200}, semillas 42 a 44, 5000 FE, SW-UCB con $W=10$ y $c=0{.}07$; 2820 decisiones adaptativas. "
        "Solo se registraron los términos del brazo elegido. La exploración supera a la explotación en todas las "
        f"decisiones; {zero} tienen explotación nula y se omiten en (b). Con estos datos el cociente de medias es "
        f"{ratio_means:.1f}; el valor de 35.4 y el 64.11~\\% de decisiones invertidas proceden de la reconstrucción "
        "completa del índice descrita en \\texttt{final\\_closure/f2\\_6\\_validation\\_report.md}."
    )
    write_figure_tex(
        out,
        "fig6_swucb",
        "Magnitud de los términos de exploración y explotación de SW-UCB.",
        note,
        "fig:cap6_swucb",
    )


# Table: early selection (development cohort, 200 FE per arm)
def table_early_selection(out):
    a = pd.read_csv(
        RES / "historical/seleccion_temprana_20261016/tables/v3/accuracy_regret_matrix.csv",
        encoding="utf-8-sig",
    )
    a = a[(a.cohort == "loop_development") & (a.cut_per_arm == 200)]
    names = {
        "A_local_HV": "A. Mayor HV a 200 FE",
        "B0_gain_from_zero": "B0. Ganancia desde 0",
        "B50_gain_after_first_checkpoint": "B50. Ganancia desde 50 FE",
        "C_recent_100_FE_slope": "C. Pendiente reciente",
        "D_margin_005_fallback_MOEAD": "D. A con margen; si no, MOEA/D",
        "E_always_MOEAD": "E. Siempre MOEA/D",
    }
    rows = []
    for _, r in a.iterrows():
        hits = round(r.accuracy * r.n_decisions)
        rows.append(
            {
                "Criterio": names[r.criterion],
                "Aciertos": f"{hits}/{r.n_decisions}",
                "IC aciertos": f"[{r.accuracy_ci_low:.2f}; {r.accuracy_ci_high:.2f}]",
                "Pérdida media": fmt(r.mean_regret),
                "IC pérdida": f"[{r.regret_ci_low:.4f}; {r.regret_ci_high:.4f}]",
                "FE de prueba": int(r.total_probe_FE),
            }
        )
    assert rows[0]["Aciertos"] == "6/18" and rows[-1]["Aciertos"] == "13/18"
    note = (
        "Análisis retrospectivo \\texttt{seleccion\\_temprana\\_20261016} (tablas \\texttt{v3}), sin FE nuevas: "
        "trayectorias individuales de MOEA/D, NSGA-II y SPEA2 de la campaña del 15 de octubre, 6 bases de desarrollo "
        "$\\times$ semillas 42 a 44, 3000 FE. Acierto: el criterio elige el algoritmo con mayor HV individual final en "
        "la misma semilla; pérdida: HV del ganador menos HV del elegido. Las 18 decisiones son 6 bases con 3 semillas, "
        "no 18 instancias independientes. IC bootstrap exploratorios por base. La pérdida no descuenta el costo de "
        "las FE de prueba."
    )
    write_table_tex(
        out,
        "tab6_seleccion_temprana",
        pd.DataFrame(rows),
        "Selección anticipada del algoritmo tras 200 FE por algoritmo.",
        "tab:cap6_seleccion",
        note,
        "lrrrrr",
    )


# Table: marginal contribution under scaled UCB and uniform allocation
def table_marginal_contribution(out):
    p = pd.read_csv(
        RES / "historical/control_uniforme_contribucion_20261016/tables/policy_runs.csv", encoding="utf-8-sig"
    )
    arms = ["MOEA/D", "NSGA-II", "SPEA2"]
    scaled, uniform = p[p.policy == "scaled"], p[p.policy == "uniform"]
    assert len(scaled) == len(uniform) == 18
    rows = [
        {
            "Algoritmo": a,
            "FE": f"{scaled[f'{a}_fe'].mean():.0f}",
            "MC máxima": f"{int((scaled.winner == a).sum())}/18",
            "MC nula": int((scaled[f"{a}_mc"] <= 0).sum()),
            "FE ": f"{uniform[f'{a}_fe'].mean():.0f}",
            "MC máxima ": f"{int((uniform.winner == a).sum())}/18",
            "MC nula ": int((uniform[f"{a}_mc"] <= 0).sum()),
        }
        for a in arms
    ]
    assert [r["MC máxima"] for r in rows] == ["8/18", "7/18", "3/18"]
    changed = (
        scaled.set_index(["base_id", "seed"]).winner != uniform.set_index(["base_id", "seed"]).winner
    ).sum()
    better = (
        scaled.set_index(["base_id", "seed"]).global_hv > uniform.set_index(["base_id", "seed"]).global_hv
    ).sum()
    df = pd.DataFrame(rows)
    note = (
        "Campañas \\texttt{recomendacion\\_contribucion\\_20261016} y \\texttt{control\\_uniforme\\_contribucion\\_20261016}, "
        "sin FE nuevas: portafolios de la campaña del 15 de octubre, 6 bases de desarrollo $\\times$ semillas 42 a 44, "
        "3000 FE. $MC(a)=HV(P_{\\mathrm{global}})-HV(ND(\\bigcup_{b\\neq a}A_b))$. FE: media por corrida. "
        "MC máxima: corridas en que el algoritmo tiene la mayor contribución; MC nula: corridas en que no aporta. "
        f"Comparación pareada por base y semilla: el algoritmo de mayor MC cambia en {changed} de 18 corridas al igualar "
        f"el presupuesto, aunque el HV global del UCB escalado es mayor en {better} de 18. La MC refleja también las "
        "oportunidades que dio la política, no solo la capacidad del algoritmo."
    )
    write_table_tex(
        out,
        "tab6_contribucion",
        df,
        "Contribución marginal por algoritmo según la política de asignación.",
        "tab:cap6_contribucion",
        note,
        "lrrrrrr",
        group_header="  & \\multicolumn{3}{c}{UCB escalado} & \\multicolumn{3}{c}{Uniforme} \\\\\n"
        "  \\cmidrule(lr){2-4} \\cmidrule(lr){5-7}\n",
    )


# Table 6.4: individual and shared configurations on the six development bases
def table_shared_configurations(out):
    camp = RES / "experiments/moead_pairs_and_80_development_20261023"
    d = pd.read_csv(camp / "by_instance.csv", encoding="utf-8-sig")
    u = pd.read_csv(
        RES / "experiments/moead_pairs_uniform_development_20261023/by_instance.csv", encoding="utf-8-sig"
    )
    d = pd.concat([d, u[u.method.str.endswith("_uniform")]])
    hv = d.pivot_table(index="case", columns="method", values="mean_hypervolume")
    rows = [
        ("MOEA/D", "moead", "100 \\%"),
        ("NSGA-II", "nsga2", "100 \\%"),
        ("SPEA2", "spea2", "100 \\%"),
        ("Trío", "uniform", "uniforme"),
        ("Trío", "scaled", "UCB esc."),
        ("MOEA/D+NSGA-II", "moead_nsga2_uniform", "uniforme"),
        ("MOEA/D+SPEA2", "moead_spea2_uniform", "uniforme"),
        ("MOEA/D+NSGA-II", "moead_nsga2_scaled", "UCB esc."),
        ("MOEA/D+SPEA2", "moead_spea2_scaled", "UCB esc."),
        ("MOEA/D+NSGA-II", "moead_nsga2_80_20", "80/20"),
        ("MOEA/D+SPEA2", "moead_spea2_80_20", "80/20"),
        ("Trío", "trio_moead_80_10_10", "80/10/10"),
    ]
    out_rows = []
    for name, m, quota in rows:
        diff = hv[m] - hv["moead"]
        mean, lo, hi = boot_ci(diff.values)
        out_rows.append(
            {
                "Configuración": name,
                "Reparto": quota,
                "HV": fmt(hv[m].mean()),
                "$\\Delta$ vs MOEA/D": "—" if m == "moead" else fmt(mean, sign=True),
                "IC 95 \\%": "—" if m == "moead" else ci_text(lo, hi),
                "Bases a favor": "—" if m == "moead" else f"{int((diff > 0).sum())}/6",
            }
        )
    assert out_rows[0]["HV"] == "0.9651" and out_rows[10]["HV"] == "0.9477"
    note = (
        "Campañas \\texttt{moead\\_pairs\\_and\\_80\\_development\\_20261023} y "
        "\\texttt{moead\\_pairs\\_uniform\\_development\\_20261023} (controles reutilizados de "
        "\\texttt{weighted\\_pilot\\_development\\_20261023}): 6 bases de desarrollo $\\times$ semillas 42 a 44, 3000 FE, "
        "bloques de 50 FE. HV: media de semillas por base y luego media de bases. Diferencias pareadas por base; "
        "IC bootstrap por base (6 bases, 20\\,000 remuestreos), exploratorios. Estos valores provienen de una versión del "
        "código posterior a la campaña del 15 de octubre y no se combinan con ella."
    )
    write_table_tex(
        out,
        "tab6_configuraciones",
        pd.DataFrame(out_rows),
        "Configuraciones individuales y compartidas en el banco de seis bases.",
        "tab:cap6_configuraciones",
        note,
        "llrrrr",
    )


# Table 6.7: finalists before the holdout (3 and 5 seeds, development and additional banks)
def table_finalists(out):
    sources = [
        ("3", RES / "experiments/allocation_variants_moead_blmr_20261024"),
        ("5", RES / "experiments/multiea_selection_moead_blmr_20261024"),
    ]
    methods = [
        ("BLMR solo", "explorer_solo"),
        ("Pareja dinámica sin corte", "passive"),
        ("Pareja codiciosa ($p=3$)", "greedy_p3"),
        ("MultiEA (archivo propio)", "multiea_own"),
        ("MultiEA (crédito)", "multiea_credit"),
        ("PS-MB (corte 600)", "early_moead_600"),
    ]
    rows = []
    for seeds, camp in sources:
        for bank, label in [("development", "Desarrollo (6)"), ("transfer", "Adicional (13)")]:
            d = pd.read_csv(camp / bank / "by_instance.csv", encoding="utf-8-sig")
            hv = d.pivot_table(index="case", columns="method", values="mean_hypervolume")
            for name, m in methods:
                if m not in hv:
                    continue
                diff = hv[m] - hv["explorer_solo"]
                mean, lo, hi = boot_ci(diff.values)
                rows.append(
                    {
                        "Semillas": seeds,
                        "Banco": label,
                        "Método": name,
                        "HV": fmt(hv[m].mean()),
                        "$\\Delta$ vs BLMR": "—" if m == "explorer_solo" else fmt(mean, sign=True),
                        "IC 95 \\%": "—" if m == "explorer_solo" else ci_text(lo, hi),
                        "A favor": "—" if m == "explorer_solo" else f"{int((diff > 0).sum())}/{len(diff)}",
                    }
                )
    df = pd.DataFrame(rows)
    ps = df[df["Método"] == "PS-MB (corte 600)"]["HV"].tolist()
    assert ps == ["0.9928", "0.9980", "0.9960", "1.0007"], ps
    note = (
        "Campañas \\texttt{allocation\\_variants\\_moead\\_blmr\\_20261024} (semillas 100 a 300) y "
        "\\texttt{multiea\\_selection\\_moead\\_blmr\\_20261024} (semillas 100 a 500), 3000 FE, bloques de 50 FE. "
        "Desarrollo: 6 bases; adicional: 13 instancias. HV: media de semillas por instancia y luego media de "
        "instancias. Diferencias pareadas por instancia frente a BLMR solo; IC bootstrap por instancia (20\\,000 "
        "remuestreos). Las variantes y la regla de decisión se fijaron antes de correr, pero ambos bancos ya se habían "
        "observado en campañas anteriores: son resultados de selección, no de confirmación. Ninguna instancia del "
        "holdout interviene."
    )
    write_table_tex(
        out,
        "tab6_finalistas",
        df,
        "Configuraciones finalistas antes de la evaluación holdout.",
        "tab:cap6_finalistas",
        note,
        "cllrrrr",
    )


# Figure 6.1: initial portfolio (F8.6 of mojssp-dmab) against its individual algorithms
def figure_initial_portfolio(out):
    src = RES / "historical/initial_portfolio_dmab"
    d = pd.read_csv(src / "f86_runs.csv")
    u = pd.read_csv(src / "f86_uniform_runs.csv").assign(configuration="Uniforme")
    runs = pd.concat(
        [
            d[["instance", "seed", "configuration", "final_hv"]],
            u[["instance", "seed", "configuration", "final_hv"]],
        ]
    )
    hv = runs.pivot_table(index=["instance", "seed"], columns="configuration", values="final_hv")
    assert len(hv) == 50 and not hv.isna().any().any()
    by_instance = hv.groupby(level=0).mean()
    bars = [
        ("NSGA-II", "NSGA-II", BLUE),
        ("NSGA-II+LS", "NSGA-II+LS", BLUE),
        ("MOPSO", "MOPSO", BLUE),
        ("Portafolio\nSW-UCB", "Portfolio+DMAB", ORANGE),
        ("Portafolio\nuniforme", "Uniforme", ORANGE),
    ]
    fig, ax = plt.subplots(figsize=(6.0, 3.4))
    for i, (label, col, color) in enumerate(bars):
        mean = hv[col].mean()
        ax.bar(i, mean, width=0.62, color=color, alpha=0.85, edgecolor="white", linewidth=0)
        ax.scatter(
            i + np.linspace(-0.16, 0.16, 5),
            by_instance[col],
            s=12,
            color=INK,
            zorder=3,
            label="Media por instancia (10 semillas)" if i == 0 else None,
        )
        ax.text(
            i, 0.04, f"{mean:.4f}", ha="center", va="bottom", fontsize=9, color="white", fontweight="bold"
        )
    ax.set_xticks(range(len(bars)), [b[0] for b in bars])
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("HV final (media de 50 corridas)")
    ax.grid(axis="x", visible=False)
    handles = [
        plt.Rectangle((0, 0), 1, 1, color=BLUE, alpha=0.85),
        plt.Rectangle((0, 0), 1, 1, color=ORANGE, alpha=0.85),
        plt.Line2D([], [], marker="o", ls="", ms=4, color=INK),
    ]
    ax.legend(
        handles,
        ["Algoritmo individual", "Portafolio de los tres", "Media por instancia (10 semillas)"],
        loc="upper center",
        bbox_to_anchor=(0.5, -0.17),
        ncol=3,
        fontsize=8,
        frameon=False,
    )
    save(fig, out, "fig6_portafolio_inicial")
    note = (
        "Campaña F8.6 del repositorio \\texttt{mojssp-dmab} (copia en \\texttt{results/historical/initial\\_portfolio\\_dmab}): "
        "5 instancias (\\texttt{5\\_10}, \\texttt{10\\_10}, \\texttt{15\\_10}, \\texttt{20\\_10} y \\texttt{20\\_20}), semillas 0 a 9, "
        "1000 FE por corrida, población 30, bloques de 50 FE. SW-UCB con $W=10$ y $c=0{.}07$ tras 150 FE de calentamiento "
        "(50 por algoritmo). Barras: media de las 50 corridas; puntos: media de cada instancia. Comparación pareada por "
        "instancia y semilla: NSGA-II individual supera a ambos portafolios en las 50 corridas. Las instancias y la versión "
        "del código son anteriores al resto del capítulo, por lo que estos HV no se comparan numéricamente con los de las "
        "secciones siguientes."
    )
    write_figure_tex(
        out,
        "fig6_portafolio_inicial",
        "Hipervolumen del portafolio inicial y de sus algoritmos individuales.",
        note,
        "fig:cap6_portafolio_inicial",
        width="0.85\\linewidth",
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(ROOT / ".local/notes/cap6"))
    parser.add_argument("--only", nargs="*", help="Function names to run (default: all)")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    steps = [
        figure_initial_portfolio,
        figure_swucb_budget,
        figure_blmr_individuals,
        figure_cut_sweep,
        figure_blmr_vs_moead,
        figure_swucb,
        table_early_selection,
        table_marginal_contribution,
        table_shared_configurations,
        table_finalists,
    ]
    for step in steps:
        if not args.only or step.__name__ in args.only:
            step(out)
    print(f"Figuras y tablas en {out}")


if __name__ == "__main__":
    main()
