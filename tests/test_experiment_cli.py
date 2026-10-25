"""End-to-end checks of the common experiment command."""
import json
import math
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('algorithm,policy', [
    ('moead', None), ('nsga2', None), ('spea2', None),
    ('portfolio', 'uniform'), ('portfolio', 'adaptive'),
    ('portfolio', 'sw_ucb'), ('portfolio', 'scaled'), ('portfolio', 'ph'),
    ('portfolio', 'weighted'), ('portfolio', 'dynamic')])
def test_cli_budget_and_output(tmp_path, algorithm, policy):
    output = tmp_path / 'run.json'
    command = [sys.executable, str(ROOT / 'scripts/run_experiment.py'),
               '--instance', str(ROOT / 'data/validation/small_3x3.dzn'),
               '--algorithm', algorithm, '--budget', '120', '--population-size', '10',
               '--block-size', '20', '--output', str(output)]
    if policy:
        command.extend(['--policy', policy])
    completed = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    result = json.loads(output.read_text(encoding='utf-8'))
    assert result['evaluations_used'] == 120
    assert result['completed']
    assert result['pareto_front']
    assert math.isfinite(result['hypervolume'])
    assert 0 <= result['hypervolume'] <= 1.1 ** 3
    if policy:
        assert len(result['arm_allocations']) == 3
        assert sum(block['evaluations_used'] for block in result['blocks']) == 120
        assert result['config']['policy'] == ('sw_ucb' if policy == 'adaptive' else policy)
        if policy == 'weighted':
            actual = {name: sum(block['evaluations_used'] for block in result['blocks'] if block['arm_name'] == name)
                      for name in result['config']['evaluation_quotas']}
            assert actual == result['config']['evaluation_quotas']
    assert result['source_sha256']
    assert result['instance_sha256']
    original = output.read_bytes()
    repeated = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True)
    assert repeated.returncode != 0
    assert output.read_bytes() == original


def test_cli_accepts_two_selected_algorithms(tmp_path):
    output = tmp_path / 'pair.json'
    command = [sys.executable, str(ROOT/'scripts/run_experiment.py'),
               '--instance', str(ROOT/'data/validation/small_3x3.dzn'),
               '--algorithm', 'portfolio', '--policy', 'uniform', '--arms', 'nsga2', 'spea2',
               '--budget', '240', '--population-size', '10', '--block-size', '20', '--output', str(output)]
    result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    data = json.loads(output.read_text(encoding='utf-8'))
    assert data['config']['arms'] == ['nsga2','spea2']
    assert {name: value['evaluations_assigned'] for name,value in data['arm_allocations'].items()} == {'NSGA-II':120,'SPEA2':120}
