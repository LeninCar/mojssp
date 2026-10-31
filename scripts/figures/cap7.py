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


# Figure 7.x: MOEA/D minus BLMR per holdout instance, grouped by size
def figure_moead_blmr_size(out):
    runs = pd.read_csv(HOLD / "runs.csv", encoding="utf-8-sig")
    split = pd.read_csv(SPLIT, encoding="utf-8-sig").set_index("instance_name")
    hv = runs.pivot_table(index="case", columns="method", values="hypervolume", aggfunc="mean")
    assert len(hv) == 80 and (runs.groupby(["case", "method"]).size() == 5).all()
    diff = (hv["moead"] - hv["explorer_solo"]).rename("moead_minus_blmr").to_frame()
    diff["size"] = split.loc[diff.index, "dimensions"]
    diff["operations"] = split.loc[diff.index, "total_operations"]
    diff.to_csv(out / "fig7_moead_blmr_tamano_datos.csv")

    fig, ax = plt.subplots(figsize=(7.0, 3.6))
    top, bottom = 0.06, -0.11
    ax.axhspan(0, top, color=ORANGE, alpha=0.08, lw=0)
    ax.axhspan(bottom, 0, color=BLUE, alpha=0.07, lw=0)
    ax.axhline(0, color=INK, lw=0.9)
    counts = []
    for i, size in enumerate(SIZES):
        d = diff[diff["size"] == size].sort_index()["moead_minus_blmr"].values
        assert len(d) == 10
        x = i + np.linspace(-0.3, 0.3, len(d))
        ax.scatter(
            x,
            d,
            s=22,
            color=[ORANGE if v > 0 else BLUE for v in d],
            edgecolor="white",
            linewidth=0.6,
            zorder=3,
        )
        counts.append((int((d < 0).sum()), int((d > 0).sum())))
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
    ax.set_ylabel("HV(MOEA/D) − HV(BLMR)")
    ax.grid(axis="y", color="#e6e5e1", lw=0.6)
    ax.text(
        len(SIZES) - 0.45,
        top - 0.004,
        "Arriba de 0: MOEA/D mejor",
        ha="right",
        va="top",
        fontsize=8.5,
        color="#b4471d",
    )
    ax.text(
        len(SIZES) - 0.45,
        bottom + 0.004,
        "Abajo de 0: BLMR mejor",
        ha="right",
        va="bottom",
        fontsize=8.5,
        color="#1c5cab",
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(ROOT / ".local/notes/cap7"))
    out = Path(parser.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    print(figure_moead_blmr_size(out))
    print(f"Figuras en {out}")


if __name__ == "__main__":
    main()
