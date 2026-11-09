# Portafolio algorítmico para el MO-JSSP

Trabajo de grado (Universidad del Valle, 2026): portafolio de algoritmos para el
problema de programación de taller de trabajos multiobjetivo (MO-JSSP) con modos
discretos de procesamiento. Se minimizan a la vez el makespan, la tardanza total
y la energía de procesamiento. La calidad de cada frente se mide con el
hipervolumen (HV) normalizado con cotas fijas por instancia y punto de
referencia (1.1, 1.1, 1.1).

## Resultado principal

El **Portafolio Secuencial MOEA/D–BLMR (PS-MB)** coordina MOEA/D y BLMR (búsqueda
local multiobjetivo por regiones) en tres etapas y bajo un presupuesto de
3000 evaluaciones (FE). Las dos estrategias cooperan a través de una memoria
global de soluciones no dominadas:

| Etapa | FE | Asignación |
| --- | --- | --- |
| Uniforme | 0–300 | 150 FE por algoritmo, en bloques alternos de 50 (empieza MOEA/D) |
| Adaptativa | 300–600 | Cuotas proporcionales a la mejora de HV por FE de la etapa 1, con un mínimo del 10 % para cada algoritmo |
| Exclusiva | 600–3000 | Solo BLMR |

La cooperación va en un solo sentido: ambos algoritmos aportan soluciones a la
memoria global, pero solo BLMR toma de ella sus puntos de partida. MOEA/D
conserva su población.

**Evaluación independiente:** 80 instancias reservadas que no se usaron para
decidir, cinco semillas (100–500) y 3000 FE. Resultados (capítulo 7 de la tesis):

| Método | HV medio | Δ PS-MB − método [IC 95 % agrupado por base] |
| --- | --- | --- |
| PS-MB | 0.9924 | — |
| Pareja MOEA/D + BLMR, rondas dinámicas sin corte | 0.9876 | +0.0049 [−0.0007; +0.0115] (Holm p = 0.088) |
| BLMR individual | 0.9789 | +0.0136 [+0.0071; +0.0196] |
| MOEA/D individual | 0.9766 | +0.0158 [+0.0040; +0.0287] |

Los intervalos de la tesis remuestrean las 16 instancias base, porque los cinco
perfiles de cada base no son independientes. En `interpretacion.txt` y
`comparisons.csv` aparecen además intervalos por instancia (más estrechos,
p. ej. [+0.0085; +0.0185] frente a BLMR); para citar, usar los agrupados.

- Frente a BLMR y MOEA/D la ventaja se mantiene con corrección de Holm. Frente a
  la pareja sin corte no es concluyente en HV final, pero sí lo es en AUC-HV
  (+0.0036 [+0.0010; +0.0069]).
- Con IGD+ y épsilon normalizados por el frente de referencia, el PS-MB queda
  primero. Con las cotas fijas del HV, MOEA/D obtiene el menor IGD+: el
  resultado depende de la normalización (sección 7.6).
- La pareja con UCB escalado (`moead_blmr_scaled`) se evaluó como
  comparación complementaria y queda estadísticamente empatada con el PS-MB.

Detalle en `results/experiments/holdout_early_moead_600_20261024/` y
`results/experiments/holdout_policy_comparison_20261025/`. El resumen general
está en `results/RESUMEN_RESULTADOS.md`.

## Estructura

| Carpeta | Contenido |
| --- | --- |
| `src/mojssp/model/` | Instancia, lector `.dzn`, solución, decodificador semiactivo, cronograma, ruta crítica y evaluador de los tres objetivos |
| `src/mojssp/metrics/` | Normalización por cotas fijas, dominancia, archivo de Pareto, hipervolumen exacto y recompensa ΔHV |
| `src/mojssp/algorithms/` | Las seis estrategias: NSGA-II, NSGA-II+LS, SPEA2, MOEA/D, MOPSO discreto y BLMR (`regional_explorer.py`) |
| `src/mojssp/portfolio/` | Portafolio con memoria global (`portfolio.py`), orquestador y políticas de reparto (`orchestrator.py`, `selectors.py`, `dynamic_budget.py`) y montaje de MOEA/D + BLMR (`regional_portfolio.py`) |
| `src/mojssp/experiments/` | Los métodos de las campañas finales, con su nombre en los archivos (`methods.py`), más utilidades y resúmenes |
| `scripts/run_instance.py` | Corre cualquier método final sobre una instancia y genera gráficas (`plots.py`) |
| `scripts/campaigns/` | Runners del holdout, de la comparación de políticas, del barrido del corte y de la completitud de la Tabla 6.7; exportación de corridas compactas |
| `scripts/figures/` | Figuras y tablas de los capítulos 6 y 7 (`cap6.py`, `cap7.py`, `instance_sets.py`) |
| `scripts/validation/` | Validación del modelo, el HV, la normalización, el conteo de FE y el holdout |
| `tests/` | Pruebas (`pytest`) |
| `data/validation/` | Instancias pequeñas para verificar el modelo (`toy_instance`, `small_3x2`, `small_3x3`) |
| `data/experimental/` | Banco de 12 instancias experimentales |
| `data/generated/expanded_200/` | 200 instancias (40 bases × 5 perfiles) con su partición en `experimental_split.csv` (120 de desarrollo y 80 reservadas) y su `expanded_manifest.csv` |
| `data/instance_registry.csv` | Registro de las instancias y su procedencia |
| `configs/` | Configuraciones de algunas campañas |
| `results/experiments/` | Campañas desde el 22 de octubre de 2026: resúmenes versionados; las corridas detalladas (`runs/`) solo están en disco |
| `results/historical/` | Campañas anteriores (portafolio inicial, fase 2, selección temprana, contribución marginal) |
| `results/index.csv` | Índice de campañas: pregunta, contenido, estado y ubicación |
| `docs/model_formulation.md` | Formulación matemática del modelo |

Los scripts de las campañas exploratorias anteriores (pilotos, fases 2 a F8.6,
inyecciones, crédito compartido) se retiraron del código actual. Siguen en la
etiqueta `thesis-full-history`, junto con los comandos citados en
`results/commands.csv` y `results/index.csv`.

## Entorno

Python 3.12 en `.venv`. `requirements.txt` fija las versiones. `pandas` hace
falta para los scripts de figuras y para `run_policy_completion.py`; `seaborn` y
`scikit-learn`, solo para análisis anteriores.

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pytest -q
```

`run_instance.py`, las validaciones y `instance_sets.py` agregan `src` a la ruta
por su cuenta. Los runners de `scripts/campaigns/` necesitan
`$env:PYTHONPATH = "src"`.

## Correr el portafolio sobre una instancia

`scripts/run_instance.py` usa las mismas funciones que las campañas finales. Con
la semilla 100 y 3000 FE reproduce el HV guardado en el holdout para los nueve
métodos.

```powershell
# PS-MB con la configuración de la tesis (corte 600, semilla 100, 3000 FE)
.venv\Scripts\python.exe scripts\run_instance.py --instance data\generated\expanded_200\base_c02_10x10_b05_btnk_high.dzn

# PS-MB frente a sus componentes y la pareja sin corte, con la misma semilla
.venv\Scripts\python.exe scripts\run_instance.py --instance data\generated\expanded_200\base_c02_10x10_b05_btnk_high.dzn --compare blmr moead passive

# Otro corte, otra semilla, detalle de la solución de menor energía
.venv\Scripts\python.exe scripts\run_instance.py --instance data\validation\small_3x3.dzn --cut 900 --seed 200 --select energy
```

| Opción | Valores | Por defecto | Uso |
| --- | --- | --- | --- |
| `--instance` | ruta `.dzn` | (obligatoria) | Instancia a resolver |
| `--method` | `psmb`, `scaled`, `passive`, `blmr`, `moead`, `nsga2`, `spea2`, `nsga2_ls`, `mopso` | `psmb` | Método principal |
| `--compare` | uno o más de los anteriores | ninguno | Métodos adicionales, corridos con la misma semilla |
| `--cut` | múltiplo de 300, ≥ 300 y < `--budget` | `600` | FE a partir de las cuales el PS-MB ejecuta solo BLMR (ver la nota) |
| `--seed` | entero | `100` | Semilla (la primera del holdout) |
| `--budget` | entero ≥ 600, múltiplo de 50 | `3000` | Presupuesto total en FE |
| `--select` | `all`, `cmax`, `tardiness`, `energy`, `balanced` o un número 1..N | `all` | Solución del frente que se detalla |
| `--show-front` | bandera | apagada | Imprime todos los puntos del frente |
| `--output-dir` | carpeta | `results/demo/<instancia>_<método>_seed<semilla>/` | Carpeta de salida |

Correspondencia de los métodos con la tesis: `psmb` es el PS-MB, `passive` la
pareja con rondas dinámicas sin corte, `scaled` la pareja con UCB escalado y
`blmr` BLMR individual. El resto son los algoritmos individuales.

El script imprime el reparto del presupuesto por etapa (en los portafolios), el
HV y las soluciones destacadas. En la carpeta de salida guarda la convergencia
del HV, el frente, los frentes comparados, los diagramas de Gantt y
`resumen.json`.

> **Nota sobre `--cut`.** El coordinador reasigna en rondas de 300 FE
> (0, 300, 600, 900…) y solo cambia a BLMR al inicio de una ronda. Por eso
> `run_instance.py` acepta únicamente múltiplos de 300, como los del barrido
> (300, 600, 900, 1200, 1800). `run_psmb` desde Python no hace esta validación:
> un corte que no sea múltiplo de 300 equivale al siguiente múltiplo (450 se
> comporta como 600) y uno menor que 300 produce un error.

## Parámetros del PS-MB

Desde Python, el PS-MB es `run_psmb` en `src/mojssp/experiments/methods.py`:

```python
from mojssp.model.io import load_dzn
from mojssp.experiments.methods import run_psmb, run_method

instance = load_dzn("data/generated/expanded_200/base_c02_10x10_b05_btnk_high.dzn")
result = run_psmb(instance, seed=100, budget=3000, cut=600)
print(result["hypervolume"], result["allocations"])      # HV final y FE por algoritmo
# Mismo resultado por nombre de campaña:
result = run_method(instance, 100, "early_moead_600")    # también 'passive', 'moead_blmr_scaled', 'explorer_solo', 'moead', 'cut_900', ...
```

`run_psmb` llama a `run_regional_policy_experiment(instance, seed,
["MOEA/D", "RegionExplorer"], "dynamic", guidance=False, budget,
dynamic_options={"exclusive_arm": "RegionExplorer", "exclusive_after": cut})`.
Los parámetros fijos son estos:

| Componente | Parámetro | Valor | Dónde |
| --- | --- | --- | --- |
| Coordinador | presupuesto / bloque máximo | 3000 FE / 50 FE | `run_regional_policy_experiment` |
| | ronda de reasignación | 300 FE | `POLICY_PROFILES["dynamic"]` |
| | participación mínima α | 0.1 | `POLICY_PROFILES["dynamic"]` |
| | exponente de las cuotas | 1.0 (proporcional) | `run_dynamic_rounds(share_power)` |
| | calentamiento | primer bloque de cada algoritmo, excluido de la tasa ρ | `run_dynamic_rounds` |
| | cuotas enteras | método de restos mayores | `fixed_budget.evaluation_quotas` |
| | corte | 600 FE, solo BLMR después | `exclusive_after` |
| | guía de padres hacia MOEA/D | desactivada (`guidance=False`) | `RegionalParentGuidance` |
| MOEA/D | población / pesos | 30 / 30 en el simplex | `MOEADArm` |
| | vecindario / prob. de vecindario | 6 / 0.9 | |
| | reemplazos máximos | 2 | |
| | cruce POX / mutación de secuencia | 1.0 / 0.2 | |
| | mutación de modo por gen | 1/N | |
| | escalarización | Tchebycheff sobre objetivos normalizados | |
| BLMR | direcciones | 7 (3 individuales, 3 por parejas, 1 equilibrada), una al azar por bloque | `RegionalExplorerArm(policy="random")` |
| | candidatos de partida | 5, los más cercanos a la dirección en la memoria global | `parent_count=5` |
| | prob. de cambio de modo | 0.8 si la energía domina la dirección, 0.3 si dominan los criterios temporales, 0.5 en otro caso | `RegionalExplorerArm.run` |
| | movimientos de secuencia | intercambio de un trabajo tardío si domina la tardanza; si no, intercambio crítico | `_sequence_move` |
| Semillas | MOEA/D / BLMR | `(seed·10007 + 17)` / `(seed·10007 + 71)` mód 2³¹−1 | `regional_portfolio.py` |

El diccionario que devuelven `run_psmb` y `run_method` contiene `hypervolume`,
`checkpoints` (HV tras cada bloque), `blocks` (algoritmo, FE, ΔHV y ronda de
cada bloque), `allocations`, `pareto_front`, `front_entries` (secuencia, modos y
objetivos) y `region_trace` (dirección y padres de BLMR en cada bloque).

## Validaciones

Desde la raíz, con `.venv\Scripts\python.exe scripts\validation\<script>`:

| Script | Qué comprueba |
| --- | --- |
| `validate_model.py` | Caso 2×2 resuelto a mano (`hand_2x2.dzn`) y lector, decodificador y evaluador independientes |
| `validate_hv.py` | HV frente a dos métodos exactos independientes |
| `validate_normalization.py` | Sesgo de las cotas fijas y repetición con normalización empírica |
| `validate_fe.py` | Exactamente 3000 decodificaciones y evaluaciones por método |
| `validate_experiments.py` | Código congelado, reproducción de una muestra, fugas, semillas, Holm, A12 emparejado e intervalo agrupado |
| `validate_secondary_metrics.py` | IGD+ y épsilon en el holdout, incluido el UCB escalado |

## Reproducir la evaluación final

El código evaluado está congelado en la etiqueta `holdout-v2-freeze`. El código
actual se reorganizó después, pero da los mismos resultados:
`validate_experiments.py` reproduce una muestra de corridas.

Para relanzar el holdout tal como se corrió, hay que usar la etiqueta congelada
(con las rutas de esa versión). El runner exige que el código sea exactamente el
congelado; con `--resume` reutiliza las corridas guardadas en `runs/`.

```powershell
git checkout holdout-v2-freeze
$env:PYTHONPATH = "src;scripts"
.venv\Scripts\python.exe scripts\run_holdout_evaluation.py --output-dir results\experiments\holdout_early_moead_600_20261024 --resume
git checkout master
```

La comparación complementaria de políticas (5 políticas × 4 composiciones en las
mismas 80 instancias) se escribió después de la congelación y se corre desde el
código actual. Reutiliza las corridas congeladas y comprueba el hash de la
partición:

```powershell
.\scripts\campaigns\run_holdout_policies.ps1 -DryRun     # lista lo pendiente
.\scripts\campaigns\run_holdout_policies.ps1 -Compositions moead_blmr -Policies scaled,dynamic -Workers 10
```

## Barrido del corte (análisis de sensibilidad)

El corte de 600 FE se fijó antes de la evaluación independiente.
`scripts/campaigns/run_cut_sweep.py` lo estudió después, sin tocar el holdout
(Tabla 6.12 de la tesis). En las 120 instancias de desarrollo, 900 FE obtiene
el HV medio más alto (0.994292) y 600 FE queda prácticamente igual (0.994188),
con una diferencia no concluyente. Es una comprobación de sensibilidad, no una
justificación a posteriori del corte. Detalle en
`results/experiments/cut_sweep_development_20261028/interpretacion.txt`.

| Subcomando | Qué hace | Opciones |
| --- | --- | --- |
| `develop` | Cortes 300, 600, 900, 1200 y 1800, más la pareja sin corte, el UCB escalado, BLMR y MOEA/D, en las 120 instancias de desarrollo (3 semillas) | `--output-dir` (obligatoria), `--workers` (1–14, 12), `--resume`, `--seeds` (prueba rápida, no escribe decisión) |
| `confirm` | Corre la elección de `develop` una sola vez en instancias nuevas, fuera de `expanded_200` | lo anterior más `--development-dir` e `--instances-dir` (obligatorias) |

```powershell
$env:PYTHONPATH = "src"
.venv\Scripts\python.exe scripts\campaigns\run_cut_sweep.py develop --output-dir results\experiments\cut_sweep_development_20261028 --resume
```

`confirm` no se ha ejecutado. El script exige que el código esté commiteado.

## Completitud de la Tabla 6.7

`scripts/campaigns/run_policy_completion.py` corre las siete celdas de la
Tabla 6.7 que faltaban en el banco de desarrollo: SW-UCB y Page-Hinkley con
MOEA/D + BLMR y con NSGA-II + BLMR, y uniforme, SW-UCB y Page-Hinkley con el
cuarteto. Antes de correrlas comprueba que reproduce corridas guardadas de las
campañas originales. Es un análisis posterior al holdout y solo descriptivo.

```powershell
$env:PYTHONPATH = "src"
.venv\Scripts\python.exe scripts\campaigns\run_policy_completion.py --workers 6   # salida: results\experiments\policy_completion_development_20261103
```

## Figuras de la tesis

Las figuras se reconstruyen solo a partir de los resultados guardados (PDF y PNG,
fragmentos LaTeX y CSV):

```powershell
.venv\Scripts\python.exe scripts\figures\cap6.py --out .local\notes\cap6            # --only <función> para regenerar una sola
.venv\Scripts\python.exe scripts\figures\cap7.py --out .local\notes\cap7
.venv\Scripts\python.exe scripts\figures\instance_sets.py --out .local\notes\cap6   # Tabla 6.1
```

## Corridas compactas

Las carpetas `runs/` (varios GB) no están en git.
`scripts/campaigns/export_compact_runs.py` guarda en el `compact_runs.jsonl.gz`
de cada campaña final (holdout, comparación de políticas, barrido) la curva de
HV, el algoritmo de cada bloque, el reparto y el frente de cada corrida. Con eso
se pueden rehacer las figuras sin los `runs/`.

```python
import gzip, json
runs = [json.loads(l) for l in gzip.open("results/experiments/holdout_early_moead_600_20261024/compact_runs.jsonl.gz", "rt")]
```
