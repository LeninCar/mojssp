"""Figures of thesis chapter 7 (holdout evaluation), read only from the saved holdout runs.

Run from the project root:
    .venv\\Scripts\\python.exe scripts\\figures\\cap7.py [--out .local/notes/cap7]
"""

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
HOLD = ROOT / "results/experiments/holdout_early_moead_600_20261024"
SPLIT = ROOT / "data/generated/expanded_200/experimental_split.csv"
BLUE, ORANGE, INK, MUTED = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e"
SIZES = ["5x5", "10x10", "20x10", "10x20", "20x20", "30x20", "40x20", "50x50"]
plt.rcParams.update(
    {
        "font.family": "serif",
        "mathtext.fontset": "cm",
        "font.size": 9,
        "axes.edgecolor": MUTED,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "pdf.fonttype": 42,
        "savefig.bbox": "tight",
    }
)


def save(fig, out, name):
    for ext in ("png", "pdf"):
        fig.savefig(out / f"{name}.{ext}", dpi=200)
    plt.close(fig)


# Figure 7.x: BLMR minus MOEA/D per holdout instance, grouped by size (same sign as Figure 6.5)
def figure_moead_blmr_size(out):
    runs = pd.read_csv(HOLD / "runs.csv", encoding="utf-8-sig")
    split = pd.read_csv(SPLIT, encoding="utf-8-sig").set_index("instance_name")
    hv = runs.pivot_table(index="case", columns="method", values="hypervolume", aggfunc="mean")
    assert len(hv) == 80 and (runs.groupby(["case", "method"]).size() == 5).all()
    diff = (hv["explorer_solo"] - hv["moead"]).rename("blmr_minus_moead").to_frame()
    diff["size"] = split.loc[diff.index, "dimensions"]
    diff["operations"] = split.loc[diff.index, "total_operations"]
    diff.to_csv(out / "fig7_moead_blmr_tamano_datos.csv")

    fig, ax = plt.subplots(figsize=(7.0, 3.6))
    top, bottom = 0.11, -0.06
    ax.axhspan(0, top, color=BLUE, alpha=0.07, lw=0)
    ax.axhspan(bottom, 0, color=ORANGE, alpha=0.08, lw=0)
    ax.axhline(0, color=INK, lw=0.9)
    counts = []
    for i, size in enumerate(SIZES):
        d = diff[diff["size"] == size].sort_index()["blmr_minus_moead"].values
        assert len(d) == 10
        x = i + np.linspace(-0.3, 0.3, len(d))
        ax.scatter(
            x,
            d,
            s=22,
            color=[BLUE if v > 0 else ORANGE for v in d],
            edgecolor="white",
            linewidth=0.6,
            zorder=3,
        )
        counts.append((int((d > 0).sum()), int((d < 0).sum())))
    ops = diff.groupby("size")["operations"].first()
    ax.set_xticks(
        range(len(SIZES)),
        [f"{s.replace('x', '×')}\n{ops[s]} op.\n{b} – {m}" for s, (b, m) in zip(SIZES, counts)],
    )
    # Row label for the win counts printed on the third line of each tick label
    ax.annotate(
        "BLMR – MOEA/D",
        xy=(0, 0),
        xycoords="axes fraction",
        xytext=(-4, -34),
        textcoords="offset points",
        ha="right",
        va="center",
        fontsize=8.5,
        color=MUTED,
    )
    ax.set_xlim(-0.6, len(SIZES) - 0.4)
    ax.set_ylim(bottom, top)
    ax.set_ylabel("HV(BLMR) − HV(MOEA/D)")
    ax.grid(axis="y", color="#e6e5e1", lw=0.6)
    ax.text(
        len(SIZES) - 0.45,
        top - 0.004,
        "BLMR obtiene mayor HV",
        ha="right",
        va="top",
        fontsize=8.5,
        color="#1c5cab",
    )
    ax.text(
        len(SIZES) - 0.45,
        bottom + 0.004,
        "MOEA/D obtiene mayor HV",
        ha="right",
        va="bottom",
        fontsize=8.5,
        color="#b4471d",
    )
    save(fig, out, "fig7_moead_blmr_tamano")
    expected = [(9, 1), (9, 1), (8, 2), (8, 2), (0, 10), (0, 10), (0, 10), (0, 10)]
    assert counts == expected, counts

    note = (
        "Campaña \\texttt{holdout\\_early\\_moead\\_600\\_20261024}: 80 instancias \\texttt{holdout\\_test} de "
        "\\texttt{expanded\\_200} (10 por tamaño, 2 bases $\\times$ 5 perfiles), semillas 100 a 500, 3000 FE. "
        "Cada punto es una instancia: HV medio de MOEA/D menos HV medio de BLMR sobre las 5 semillas (diferencia "
        "pareada). Bajo cada tamaño, el número de instancias que gana BLMR y MOEA/D, de 10. Tamaño y base están "
        "confundidos: cada tamaño procede de solo dos bases. Datos en \\texttt{fig7\\_moead\\_blmr\\_tamano\\_datos.csv}."
    )
    (out / "fig7_moead_blmr_tamano.tex").write_text(
        "\\begin{figure}[htbp]\n  \\centering\n"
        "  \\includegraphics[width=\\linewidth]{fig7_moead_blmr_tamano.pdf}\n"
        "  \\caption{Diferencia de hipervolumen entre MOEA/D y BLMR en cada instancia del conjunto holdout, "
        "según su tamaño.}\n  \\label{fig:cap7_moead_blmr_tamano}\n"
        f"  \\par\\smallskip\\begin{{minipage}}{{0.95\\linewidth}}\\footnotesize\\textit{{Nota.}} {note}\\end{{minipage}}\n"
        "\\end{figure}\n",
        encoding="utf-8",
    )
    return counts


# Same colour convention as chapter 6: BLMR blue, MOEA/D orange
COMPARATORS = [
    ("moead", "MOEA/D", ORANGE),
    ("explorer_solo", "BLMR", BLUE),
    ("passive", "Pareja sin corte", "#6b6a66"),
]
PROFILES = [
    ("base", "Referencia (base)"),
    ("tard_med", "Tardanza media (tard\\_med)"),
    ("tard_high", "Tardanza alta (tard\\_high)"),
    ("nrg_strong", "Contraste energético (nrg\\_strong)"),
    ("btnk_high", "Cuello de botella (btnk\\_high)"),
]


def _psmb_differences():
    runs = pd.read_csv(HOLD / "runs.csv", encoding="utf-8-sig")
    split = pd.read_csv(SPLIT, encoding="utf-8-sig").set_index("instance_name")
    hv = runs.pivot_table(index="case", columns="method", values="hypervolume", aggfunc="mean")
    assert len(hv) == 80 and (runs.groupby(["case", "method"]).size() == 5).all()
    diff = pd.DataFrame({m: hv["early_moead_600"] - hv[m] for m, _, _ in COMPARATORS})
    diff["size"] = split.loc[diff.index, "dimensions"]
    diff["profile"] = split.loc[diff.index, "profile"]
    diff["operations"] = split.loc[diff.index, "total_operations"]
    return diff


# Figure 7.x: PS-MB minus each comparator per holdout instance, grouped by size
def figure_psmb_size(out):
    diff = _psmb_differences()
    diff.to_csv(out / "fig7_psmb_tamano_datos.csv")
    means = diff.groupby("size")[[m for m, _, _ in COMPARATORS]].mean().loc[SIZES]

    # Values quoted in section 7.3 of the thesis
    m = means.round(4)
    assert m.loc["10x10", "moead"] == 0.0612
    assert list(means["moead"] > 0) == [True] * 4 + [False] * 4
    assert m.loc[["20x20", "30x20", "40x20", "50x50"], "moead"].between(-0.0075, -0.0009).all()
    assert (means["explorer_solo"] > 0).all()
    assert set(means.index[means["passive"] < 0]) == {"5x5", "50x50"}

    fig, ax = plt.subplots(figsize=(7.0, 3.4))
    ax.axhline(0, color=INK, lw=0.9)
    offsets = [-0.26, 0.0, 0.26]
    for (method, label, color), off in zip(COMPARATORS, offsets):
        for i, size in enumerate(SIZES):
            d = diff.loc[diff["size"] == size, method].values
            assert len(d) == 10
            jitter = np.linspace(-0.07, 0.07, len(d))
            ax.scatter(i + off + jitter, d, s=9, color=color, alpha=0.35, lw=0, zorder=2)
        ax.scatter(
            np.arange(len(SIZES)) + off,
            means[method].values,
            s=46,
            marker="D",
            color=color,
            edgecolor="white",
            linewidth=0.8,
            zorder=4,
            label=f"PS-MB − {label}",
        )
    ops = diff.groupby("size")["operations"].first()
    ax.set_xticks(range(len(SIZES)), [f"{s.replace('x', '×')}\n{ops[s]} op." for s in SIZES])
    for i in range(len(SIZES) - 1):
        ax.axvline(i + 0.5, color="#ecebe7", lw=0.6, zorder=0)
    ax.set_xlim(-0.55, len(SIZES) - 0.45)
    ax.set_ylabel("HV(PS-MB) − HV(comparador)")
    ax.grid(axis="y", color="#e6e5e1", lw=0.6)
    ax.legend(
        loc="lower center",
        bbox_to_anchor=(0.5, 1.0),
        frameon=False,
        fontsize=8.5,
        ncol=3,
        handletextpad=0.3,
        columnspacing=1.5,
    )
    save(fig, out, "fig7_psmb_tamano")

    note = (
        "80 instancias reservadas (10 por tamaño: 2 bases $\\times$ 5 perfiles), semillas 100 a 500 y 3000 FE. "
        "Cada punto claro es una instancia (HV medio de PS-MB menos HV medio del comparador sobre las cinco "
        "semillas); los rombos son la media de las diez instancias de cada tamaño. Valores positivos favorecen a "
        "PS-MB. Cada tamaño procede de solo dos bases, por lo que tamaño y base están confundidos."
    )
    (out / "fig7_psmb_tamano.tex").write_text(
        "\\begin{figure}[htbp]\n  \\centering\n"
        "  \\includegraphics[width=\\linewidth]{fig7_psmb_tamano.pdf}\n"
        "  \\caption{Diferencias de hipervolumen entre PS-MB y MOEA/D, BLMR y la pareja sin corte en las "
        "instancias de evaluación, según su tamaño.}\n  \\label{fig:cap7_psmb_tamano}\n"
        f"  \\par\\smallskip\\begin{{minipage}}{{0.95\\linewidth}}\\footnotesize\\textit{{Nota.}} {note}\\end{{minipage}}\n"
        "\\end{figure}\n",
        encoding="utf-8",
    )
    return means


# Table 7.x: mean PS-MB differences by size and by generation profile
def table_psmb_size_profile(out):
    diff = _psmb_differences()
    cols = [m for m, _, _ in COMPARATORS]
    by_size = diff.groupby("size")[cols].mean().loc[SIZES]
    by_prof = diff.groupby("profile")[cols].mean().loc[[p for p, _ in PROFILES]]
    r = by_prof.round(4)
    assert (r.loc["tard_high", "passive"], r.loc["base", "passive"], r.loc["nrg_strong", "passive"]) == (
        0.0132,
        0.0068,
        -0.0035,
    )
    assert (by_prof[["moead", "explorer_solo"]] > 0).all().all()

    def fmt(v):
        s = f"{v:+.4f}".replace("-", "$-$")
        return f"\\textbf{{{s}}}" if v > 0 else s

    def row(label, vals):
        return f"    {label} & " + " & ".join(fmt(v) for v in vals) + " \\\\\n"

    body = "    \\multicolumn{4}{l}{\\textit{Por tamaño (10 instancias cada uno)}} \\\\\n"
    for s in SIZES:
        body += row(s.replace("x", "$\\times$"), by_size.loc[s].values)
    body += "    \\midrule\n    \\multicolumn{4}{l}{\\textit{Por perfil de generación (16 instancias cada uno)}} \\\\\n"
    for p, label in PROFILES:
        body += row(label, by_prof.loc[p].values)
    tex = (
        "\\begin{table}[htbp]\n  \\centering\\small\n"
        "  \\caption{Diferencia media de hipervolumen de PS-MB respecto a cada comparador, por tamaño y por perfil "
        "de generación.}\n  \\label{tab:cap7_tamano_perfil}\n"
        "  \\begin{tabular}{lrrr}\n    \\toprule\n"
        "    Grupo & vs.\\ MOEA/D & vs.\\ BLMR & vs.\\ pareja sin corte \\\\\n    \\midrule\n"
        f"{body}    \\bottomrule\n  \\end{{tabular}}\n"
        "  \\par\\smallskip\\begin{minipage}{0.92\\linewidth}\\footnotesize\\textit{Nota.} Diferencias de PS-MB "
        "menos el comparador, promediando primero las cinco semillas de cada instancia; en negrita las favorables "
        "a PS-MB. Los grupos comparten bases, por lo que las diferencias se interpretan de forma descriptiva."
        "\\end{minipage}\n\\end{table}\n"
    )
    (out / "tab7_tamano_perfil.tex").write_text(tex, encoding="utf-8")
    pd.concat({"tamano": by_size, "perfil": by_prof}).to_csv(out / "tab7_tamano_perfil_datos.csv")
    return by_size, by_prof


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(ROOT / ".local/notes/cap7"))
    out = Path(parser.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    print(figure_moead_blmr_size(out))
    print(figure_psmb_size(out).round(4))
    for t in table_psmb_size_profile(out):
        print(t.round(4))
    print(f"Figuras en {out}")


if __name__ == "__main__":
    main()
