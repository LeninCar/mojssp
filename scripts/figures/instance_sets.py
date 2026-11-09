"""Table of the instance sets used in thesis chapters 6 and 7, read from the .dzn files and the split.

Run from the project root:
    .venv\\Scripts\\python.exe scripts\\figures\\instance_sets.py [--out .local/notes/cap6]
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from mojssp.model.io import load_dzn

EXP = ROOT / "results/experiments"
DEV6 = EXP / "weighted_pilot_development_20261023/instances"
TRANSFER = EXP / "allocation_variants_moead_blmr_20261024/transfer/by_instance.csv"
REGISTRY = ROOT / "data/instance_registry.csv"
SPLIT = ROOT / "data/generated/expanded_200/experimental_split.csv"


def describe(paths):
    rows = []
    for p in paths:
        inst = load_dzn(p)
        modes = {len(op.modes) for op in inst.all_operations}
        rows.append(
            {
                "name": inst.name,
                "size": f"{inst.num_jobs}x{inst.num_machines}",
                "ops": inst.total_operations,
                "modes": modes,
            }
        )
    return pd.DataFrame(rows)


def sizes_text(series):
    seen = list(dict.fromkeys(series))
    return ", ".join(s.replace("x", "$\\times$") for s in seen)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(ROOT / ".local/notes/cap6"))
    out = Path(parser.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)

    dev6 = describe(sorted(DEV6.glob("*.dzn")))
    assert len(dev6) == 6

    reg = pd.read_csv(REGISTRY).drop_duplicates("instance_name").set_index("instance_name")
    cases = sorted(pd.read_csv(TRANSFER)["case"].unique())
    assert len(cases) == 13
    transfer = describe([ROOT / "data" / reg.loc[c, "relative_path"] for c in cases])
    groups = reg.loc[cases, "group"].value_counts().to_dict()
    assert groups == {"interactions": 8, "base": 5}, groups

    split = pd.read_csv(SPLIT, encoding="utf-8-sig")
    big = describe([ROOT / p for p in split["file_path"]])
    split = split.merge(big, left_on="instance_name", right_on="name")
    assert len(split) == 200 and split.groupby("base_id").size().eq(5).all()
    parts = {}
    for name, g in split.groupby("assigned_split"):
        per_size = g.groupby("dimensions")["base_id"].nunique()
        assert per_size.nunique() == 1
        parts[name] = {"n": len(g), "bases": g["base_id"].nunique(), "per_size": int(per_size.iloc[0])}
    assert parts["development"] == {"n": 120, "bases": 24, "per_size": 3}
    assert parts["holdout_test"] == {"n": 80, "bases": 16, "per_size": 2}
    profiles = sorted(split["profile"].unique())
    assert profiles == sorted(["base", "tard_med", "tard_high", "nrg_strong", "btnk_high"])

    all_modes = set().union(*dev6.modes, *transfer.modes, *split.modes)
    assert all_modes == {5}, all_modes

    order = ["5x5", "10x10", "20x10", "10x20", "20x20", "30x20", "40x20", "50x50"]
    assert sorted(big["size"].unique()) == sorted(order)
    big_sizes = "8 tamaños, de 5$\\times$5 a 50$\\times$50"
    rows = [
        (
            "Desarrollo inicial",
            "6",
            "6 instancias, una por tamaño",
            sizes_text(dev6["size"]),
            f"{dev6.ops.min()}--{dev6.ops.max()}",
            "Secciones 6.3--6.7",
        ),
        (
            "Banco adicional",
            "13",
            "5 balanceadas y 8 que combinan dos factores",
            sizes_text(transfer.sort_values("ops")["size"]),
            f"{transfer.ops.min()}--{transfer.ops.max()}",
            "Secciones 6.6.2 y 6.7",
        ),
        (
            "Ampliado, desarrollo",
            "120",
            "24 bases $\\times$ 5 perfiles (3 bases por tamaño)",
            big_sizes,
            f"{big.ops.min()}--{big.ops.max()}",
            "Barrido de corte (6.7)",
        ),
        (
            "Ampliado, reservado",
            "80",
            "16 bases $\\times$ 5 perfiles (2 bases por tamaño)",
            big_sizes,
            f"{big.ops.min()}--{big.ops.max()}",
            "Capítulo 7",
        ),
    ]
    body = "".join(
        f"    {a} & {b} & {c} & {d} & {e} & {f} \\\\\n" + ("    \\addlinespace\n" if i < 3 else "")
        for i, (a, b, c, d, e, f) in enumerate(rows)
    )
    note = (
        "Todas las instancias tienen cinco modos de procesamiento por operación. Los perfiles del conjunto "
        "ampliado son: referencia (\\texttt{base}), tardanza media y alta (\\texttt{tard\\_med}, "
        "\\texttt{tard\\_high}), contraste energético fuerte (\\texttt{nrg\\_strong}) y cuello de botella "
        "(\\texttt{btnk\\_high}); cada base da lugar a sus cinco perfiles. La partición se hizo por base, de modo "
        "que ninguna base del conjunto reservado aparece en desarrollo. Las ocho instancias del banco adicional "
        "que combinan factores cruzan tardanza alta, cuello de botella, variabilidad de duraciones, contraste "
        "energético, liberaciones y carga. Las campañas de las secciones 6.1 y 6.2 utilizaron conjuntos de una versión "
        "anterior del generador, descritos en esas secciones."
    )
    rag = ">{\\raggedright\\arraybackslash}p"
    tex = (
        "% Requiere los paquetes array y booktabs\n"
        "\\begin{table}[htbp]\n  \\centering\\footnotesize\n"
        "  \\caption{Conjuntos de instancias utilizados en el desarrollo y en la evaluación independiente.}\n"
        "  \\label{tab:conjuntos_instancias}\n"
        f"  \\begin{{tabular}}{{{rag}{{2.1cm}}r {rag}{{3.4cm}} {rag}{{3.2cm}} c {rag}{{2.1cm}}}}\n    \\toprule\n"
        "    Conjunto & $n$ & Composición & Tamaños ($J\\times M$) & Operaciones & Uso \\\\\n    \\midrule\n"
        f"{body}    \\bottomrule\n  \\end{{tabular}}\n"
        f"  \\par\\smallskip\\begin{{minipage}}{{0.95\\linewidth}}\\footnotesize\\textit{{Nota.}} {note}"
        "\\end{minipage}\n\\end{table}\n"
    )
    (out / "tab_conjuntos_instancias.tex").write_text(tex, encoding="utf-8")
    summary = {
        "desarrollo_inicial": dev6.drop(columns="modes").to_dict("records"),
        "banco_adicional": transfer.drop(columns="modes")
        .assign(group=list(reg.loc[cases, "group"]))
        .to_dict("records"),
        "ampliado": parts,
        "perfiles": profiles,
    }
    (out / "tab_conjuntos_instancias_datos.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=1, ensure_ascii=False)[:2500])


if __name__ == "__main__":
    main()
