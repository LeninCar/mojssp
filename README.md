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

La validación experta confirma el resultado y lo precisa:

- Con corrección de Holm para las siete comparaciones, la ventaja sobre BLMR solo
  y MOEA/D se mantiene; sobre la pareja con rondas dinámicas (+0,0049) no es
  significativa (p = 0,088; el intervalo agrupado por instancia base incluye el cero).
- Con IGD+ y épsilon normalizados por el frente de referencia (los tres objetivos
  pesan igual), el PS-MB es primero. Con las cotas fijas del HV, que pesan sobre
  todo la energía, MOEA/D es primero: cubre mejor la zona de bajo consumo,
  mientras el PS-MB y BLMR son mejores en makespan y tardanza.
- El PS-MB supera a BLMR solo con todas las métricas y normalizaciones.

Detalle en `results/experiments/holdout_early_moead_600_20261024/` (`interpretacion.txt`,
`expert_validation.json`, `secondary_metrics.json`) y
`results/experiments/holdout_policy_comparison_20261025/`.

## Estructura

| Carpeta | Contenido |
| --- | --- |
| `src/mojssp/` | Modelo, decodificador, evaluador, archivo de Pareto, HV, los seis brazos (NSGA-II, NSGA-II+LS, MOPSO, MOEA/D, SPEA2, BLMR en `regional_explorer.py`), selectores y orquestador del portafolio |
| `scripts/` | Runners de campañas y análisis; `run_psmb.py` corre el PS-MB sobre una instancia |
| `scripts/validation/` | Validación experta del código, el modelo y el holdout |
| `tests/` | Pruebas (`pytest`) |
| `data/` | Instancias `.dzn`: validación, bancos experimentales y `generated/expanded_200` con su partición desarrollo/holdout |
| `configs/` | Configuraciones de algunas campañas |
| `results/experiments/` | Campañas recientes: resúmenes versionados; las corridas detalladas (`runs/`) quedan solo en disco |
| `results/historical/` | Campañas anteriores al 22 de octubre de 2026 |
| `results/index.csv` | Índice de campañas: pregunta, contenido, estado y ubicación |
| `docs/model_formulation.md` | Formulación matemática del modelo |

## Entorno

Python 3.12 en `.venv`. `requirements.txt` fija las versiones usadas;
`pandas`, `seaborn` y `scikit-learn` solo hacen falta para scripts de análisis
anteriores. Los runners de campañas necesitan `src` y `scripts` en la ruta de
módulos (`$env:PYTHONPATH = "src;scripts"`).

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pytest -q
```

## Correr el PS-MB sobre una instancia

`scripts/run_psmb.py` usa las mismas funciones que el holdout: con la semilla 100
y 3000 FE reproduce el HV guardado.

```powershell
.venv\Scripts\python.exe scripts\run_psmb.py --instance data\generated\expanded_200\base_c02_10x10_b05_btnk_high.dzn --compare
```

Imprime el reparto del presupuesto por fase, el HV y las soluciones destacadas
del frente, y guarda en `results/demo/<instancia>_seed<semilla>/` la convergencia
del HV con el brazo de cada bloque, el frente, los Gantt y `resumen.json`.
`--compare` corre también BLMR solo y MOEA/D solo y agrega sus frentes
superpuestos; `--select` elige qué solución detallar (`all`, `cmax`,
`tardiness`, `energy`, `balanced` o un número).

## Validaciones

Desde la raíz, con `.venv\Scripts\python.exe scripts\validation\<script>`:

| Script | Qué comprueba |
| --- | --- |
| `validate_model.py` | Caso 2x2 resuelto a mano y lector, decodificador y evaluador independientes |
| `validate_hv.py` | HV contra dos métodos exactos independientes |
| `validate_normalization.py` | Sesgo de las cotas fijas y repetición con normalización empírica |
| `validate_fe.py` | Exactamente 3000 decodificaciones y evaluaciones por método |
| `validate_experiments.py` | Código congelado, reproducción de una muestra, fugas, semillas, Holm, A12 emparejado e intervalo agrupado |
| `validate_secondary_metrics.py` | IGD+ y épsilon en el holdout, incluido el UCB escalado |

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

## Barrido del corte

El corte en 600 FE no se optimizó. `scripts/run_cut_sweep.py` lo estudia sin
tocar el holdout ya usado. Resultado de `develop`: el corte de 600 queda
justificado (empata con 900, el mejor fijo, y supera a 300, 1200 y 1800). Un
corte por tamaño gana fuera de muestra unos +0,002 de HV sobre el PS-MB; solo
lo reemplazaría si `confirm` lo valida en instancias nuevas. Detalle en
`results/experiments/cut_sweep_development_20261028/interpretacion.txt`.

1. `develop`: cortes en 300, 600, 900, 1200 y 1800 FE, la pareja sin corte, el
   UCB escalado, BLMR solo y MOEA/D solo en las 120 instancias de desarrollo de
   `expanded_200` (3 semillas). Elige un corte fijo o por tamaño con una regla
   fijada antes de correr y dice si 600 queda justificado.
2. `confirm`: corre la elección contra el PS-MB, el UCB escalado y los controles
   una sola vez en instancias nuevas que no estén en `expanded_200`.

```powershell
$env:PYTHONPATH = "src;scripts"
.venv\Scripts\python.exe scripts\run_cut_sweep.py develop --output-dir results\experiments\cut_sweep_development_20261028
```

Exige el código commiteado; `--resume` continúa una corrida interrumpida.

## Corridas compactas

Las carpetas `runs/` (varios GB) no están en git. `scripts/export_compact_runs.py`
guarda en `compact_runs.jsonl.gz` de cada campaña final (holdout, comparación de
políticas, barrido) la curva de HV, el brazo de cada bloque, el reparto y el
frente de cada corrida, suficiente para rehacer figuras sin los `runs/`.

```python
import gzip, json
runs = [json.loads(l) for l in gzip.open('results/experiments/holdout_early_moead_600_20261024/compact_runs.jsonl.gz', 'rt')]
```
