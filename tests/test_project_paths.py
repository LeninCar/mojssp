from pathlib import Path
import subprocess
import sys

import pytest

from mojssp.project_paths import PROJECT_ROOT, campaign_path, input_path


def test_campaign_does_not_depend_on_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert campaign_path('portfolio') == PROJECT_ROOT / 'results/historical/portfolio_loop_20261015'
    assert not (tmp_path / 'results').exists()


def test_external_input_root_is_explicit(tmp_path):
    assert input_path('data/example.dzn', tmp_path) == tmp_path / 'data/example.dzn'
    with pytest.raises(ValueError):
        input_path('../outside.dzn', tmp_path)
    with pytest.raises(KeyError):
        campaign_path('unknown')


def test_historical_manifest_paths_resolve_after_relocation():
    assert input_path('results/portfolio_loop_20261015/manifest.json') == campaign_path('portfolio') / 'manifest.json'


@pytest.mark.parametrize('script', ['run_phase2_pilot.py', 'run_phase2_budget_diagnostic.py'])
def test_historical_runner_help_and_output_protection(tmp_path, script):
    command = [sys.executable, str(PROJECT_ROOT / 'scripts' / script)]
    help_result = subprocess.run(command + ['--help'], cwd=tmp_path, capture_output=True)
    assert help_result.returncode == 0
    assert not list(tmp_path.iterdir())
    existing = tmp_path / 'existing'
    existing.mkdir()
    result = subprocess.run(command + ['--output-dir', str(existing)],
                            cwd=tmp_path, capture_output=True)
    assert result.returncode != 0
    assert b'output directory already exists' in result.stderr
    assert not list(existing.iterdir())


@pytest.mark.parametrize('script,option', [
    ('analyze_portfolio_loop.py', '--output'),
    ('audit_portfolio_loop.py', '--output'),
    ('reproduce_portfolio_baseline.py', '--output'),
    ('validate_portfolio_loop.py', '--output'),
    ('plot_portfolio_loop.py', '--output-dir'),
    ('analyze_phase2_pilot.py', '--output-dir'),
    ('analyze_phase2_budget_diagnostic.py', '--output-dir'),
    ('audit_phase2_closure.py', '--output-dir'),
    ('report_portfolio_loop.py', '--output-dir'),
    ('verify_portfolio_closure.py', '--output'),
])
def test_reproduction_commands_do_not_overwrite_existing_outputs(tmp_path, script, option):
    command = [sys.executable, str(PROJECT_ROOT / 'scripts' / script)]
    help_result = subprocess.run(command + ['--help'], cwd=tmp_path, capture_output=True)
    assert help_result.returncode == 0
    assert not list(tmp_path.iterdir())
    existing = tmp_path / 'existing'
    if option == '--output-dir':
        existing.mkdir()
    else:
        existing.write_text('original', encoding='utf-8')
    result = subprocess.run(command + [option, str(existing)], cwd=tmp_path, capture_output=True)
    assert result.returncode != 0
    assert b'already exists' in result.stderr
    if existing.is_file():
        assert existing.read_text(encoding='utf-8') == 'original'
