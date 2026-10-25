"""Shared locations for project inputs and historical result campaigns."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESULTS_ROOT = PROJECT_ROOT / 'results'
HISTORICAL_ROOT = RESULTS_ROOT / 'historical'
EXPERIMENTS_ROOT = RESULTS_ROOT / 'experiments'
CAMPAIGNS = {
    'portfolio': 'portfolio_loop_20261015',
    'phase2': 'expanded_portfolio_phase2',
    'early_selection': 'seleccion_temprana_20261016',
    'contribution': 'recomendacion_contribucion_20261016',
    'contribution_control': 'control_uniforme_contribucion_20261016',
}


def campaign_path(name):
    """Return a registered location without creating directories or reading data."""
    return HISTORICAL_ROOT / CAMPAIGNS[name]


def input_path(relative_path, data_root=PROJECT_ROOT):
    """Resolve a dataset entry inside an explicitly selected repository root."""
    root = Path(data_root).resolve()
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root):
        raise ValueError('Input path must stay inside the selected data root')
    if root == PROJECT_ROOT and not path.exists():
        relative = path.relative_to(root)
        if len(relative.parts) >= 2 and relative.parts[0] == 'results' and relative.parts[1] in CAMPAIGNS.values():
            return HISTORICAL_ROOT.joinpath(*relative.parts[1:])
    return path
