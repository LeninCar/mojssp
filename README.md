# Portafolio algorítmico para el MO-JSSP

Trabajo de grado: portafolio de algoritmos para el problema de programación de
taller (job shop) multiobjetivo con modos de velocidad. Se minimizan a la vez
makespan, tardanza total y energía, y la calidad de un frente de Pareto se mide
con el hipervolumen (HV) normalizado.

## Resultado principal

El **Portafolio secuencial MOEA/D-BLMR (PS-MB)** combina dos algoritmos sobre un
archivo de Pareto compartido: MOEA/D explora durante las primeras 600
evaluaciones y BLMR (búsqueda local multiobjetivo por regiones) refina el
frente con las 2400 restantes.

Con 3000 evaluaciones, en 80 instancias reservadas (holdout) que no se usaron
para decidir, el PS-MB obtiene HV 0,9924 frente a 0,9789 de BLMR solo, el mejor
individual: +0,0136 con intervalo bootstrap del 95 % [+0,0085; +0,0185].
Supera en promedio a los seis individuales; con la pareja MOEA/D + BLMR con UCB
escalado queda estadísticamente empatado.

Detalle en `results/experiments/holdout_early_moead_600_20261024/interpretacion.txt`
y `results/experiments/holdout_policy_comparison_20261025/`.

## Estructura

| Carpeta | Contenido |
| --- | --- |
| `src/mojssp/` | Modelo, decodificador, evaluador, archivo de Pareto, HV, los seis brazos (NSGA-II, NSGA-II+LS, MOPSO, MOEA/D, SPEA2, BLMR en `regional_explorer.py`), selectores y orquestador del portafolio |
| `scripts/` | Runners de campañas, análisis y validaciones |
| `tests/` | Pruebas (`pytest`) |
| `data/` | Instancias `.dzn`: validación, bancos experimentales y `generated/expanded_200` con su partición desarrollo/holdout |
| `configs/` | Configuraciones de algunas campañas |
| `results/experiments/` | Campañas recientes: resúmenes versionados; las corridas detalladas (`runs/`) quedan solo en disco |
| `results/historical/` | Campañas anteriores al 22 de octubre de 2026 |
| `results/index.csv` | Índice de campañas: pregunta, contenido, estado y ubicación |
| `docs/model_formulation.md` | Formulación matemática del modelo |

## Entorno

Python 3.12 con `numpy`, `scipy`, `matplotlib` y `pytest`, en `.venv`.
Los scripts necesitan `src` y `scripts` en la ruta de módulos.

```bash
.venv/Scripts/python.exe -m pytest -q
```

## Reproducir la evaluación final

El código evaluado está congelado en la etiqueta `holdout-v2-freeze`. La
política del PS-MB se invoca así:

```python
run_regional_policy_experiment(instance, seed, ['MOEA/D', 'RegionExplorer'], 'dynamic', False,
    dynamic_options=dict(exclusive_arm='RegionExplorer', exclusive_after=600))
```

Desde PowerShell, en la raíz del proyecto:

```powershell
$env:PYTHONPATH = "src;scripts"
.venv\Scripts\python.exe scripts\run_holdout_evaluation.py --output-dir results\experiments\holdout_early_moead_600_20261024 --resume
.\scripts\run_holdout_policies.ps1
```

El runner del holdout exige que el código sea exactamente el congelado: hay que
ejecutarlo desde `git checkout holdout-v2-freeze`. Con `--resume` las corridas
ya guardadas se reutilizan; sin las carpetas `runs/` locales, se vuelven a
calcular.
