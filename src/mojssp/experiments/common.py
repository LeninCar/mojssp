"""File helpers, HV trajectory area and an evaluation counter shared by the campaign runners."""

from contextlib import contextmanager
import csv
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np

from mojssp.model.evaluator import Evaluator

ROOT = Path(__file__).resolve().parents[3]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def write_csv(path, rows):
    with path.open('x', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def auc(checkpoints, budget):
    """Area under the HV curve over the budget, divided by the budget."""
    previous_fe, previous_hv, area = 0, 0., 0.
    for fe, hv in checkpoints:
        if fe <= previous_fe or hv < previous_hv - 1e-12:
            raise ValueError('Invalid hypervolume trajectory')
        area += (fe - previous_fe) * (hv + previous_hv) / 2
        previous_fe, previous_hv = fe, hv
    if previous_fe != budget:
        raise ValueError('Incomplete trajectory')
    return area / budget


@contextmanager
def count_evaluations():
    """Counts real calls to Evaluator.evaluate inside the block; read the total from counter[0]."""
    counter = [0]
    original = Evaluator.evaluate

    def counted(self, *args, **kwargs):
        counter[0] += 1
        return original(self, *args, **kwargs)

    with patch.object(Evaluator, 'evaluate', counted):
        yield counter


def independent_hv(points, reference=(1.1, 1.1, 1.1)):
    """HV by a 2D grid and the minimum covering z, without the project's HV code (cross-check)."""
    p = np.unique(np.asarray(points, dtype=float), axis=0)
    p = p[np.all(p < np.asarray(reference), axis=1)]
    if not len(p):
        return 0.
    xs = sorted(set(p[:, 0]) | {reference[0]})
    ys = sorted(set(p[:, 1]) | {reference[1]})
    volume = 0.
    for x, x1 in zip(xs, xs[1:]):
        active = p[p[:, 0] <= x]
        for y, y1 in zip(ys, ys[1:]):
            covered = active[active[:, 1] <= y]
            if len(covered):
                volume += (x1 - x) * (y1 - y) * (reference[2] - float(covered[:, 2].min()))
    return volume
