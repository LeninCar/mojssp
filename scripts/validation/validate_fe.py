"""Expert review step 5: every method pays one evaluation per decoded schedule, and uses exactly the budget."""

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src")]
from mojssp.model.decoder import Decoder
from mojssp.model.evaluator import Evaluator
from mojssp.model.io import load_dzn
from mojssp.experiments import methods as m

inst = load_dzn(ROOT / "data/generated/expanded_200/base_c02_10x10_b02.dzn")  # development split
methods = [
    "moead",
    "nsga2_individual",
    "spea2_individual",
    "nsga2_ls_individual",
    "mopso_individual",
    "explorer_solo",
    "passive",
    "moead_blmr_scaled",
    "early_moead_600",
]
orig_d, orig_e = Decoder.decode, Evaluator.evaluate
for meth in methods:
    counts = {"decode": 0, "evaluate": 0}

    def d(self, *a, **k):
        counts["decode"] += 1
        return orig_d(self, *a, **k)

    def e(self, *a, **k):
        counts["evaluate"] += 1
        return orig_e(self, *a, **k)

    with patch.object(Decoder, "decode", d), patch.object(Evaluator, "evaluate", e):
        r = m.run_method(inst, 100, meth)
    ok = counts["decode"] == counts["evaluate"] == r["evaluations_used"] == 3000
    print(
        f"{meth:22s} decodificaciones={counts['decode']:5d} evaluaciones={counts['evaluate']:5d} "
        f"reportadas={r['evaluations_used']:5d} {'OK' if ok else 'REVISAR'}"
    )
