# Línea paralela P5/P6/P7: sensibilidad e inyección de incumbentes

Esta línea está en `mojssp-pareto-cooperation`, distinta de la campaña reciente de padre externo en `mojssp-loop-agent`. Sus artefactos P5/P6 ya estaban en el inventario inicial. P7 siguió produciendo datos durante esta auditoría y se capturó una instantánea **a 2026-10-15T20:55:37.499964+00:00**. No se ejecutó, detuvo ni modificó esa campaña. No se actualiza silenciosamente este corte.

## P5: disminuir c no equivale a escalar recompensas

Dos bases, semilla 42, 1000 FE: RR y c=.01/.03/.07 con W=10. En 5×5 c=.01 concentra 71.43% de **las FE adaptativas**, pero sólo 600/1000 FE totales en MOEA/D. En 20×10 asigna 35.71% de FE adaptativas a MOEA/D y su HV es inferior al RR. Por tanto, la frase de un diseño “más del 70% al dominante” describe una base y un denominador, no un resultado general.


| instance_name | policy_name | total_fe | final_hv | auc_hv | adapt_pct_moead | adapt_pct_nsga2 | adapt_pct_spea2 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| base_c01_5x5_b03 | Round-Robin | 1000 | 0.990285 | 0.897325 | 35.710000 | 35.710000 | 28.570000 |
| base_c01_5x5_b03 | SW-UCB_c0.01 | 1000 | 0.987354 | 0.908745 | 71.430000 | 14.290000 | 14.290000 |
| base_c01_5x5_b03 | SW-UCB_c0.03 | 1000 | 0.987504 | 0.908043 | 57.140000 | 21.430000 | 21.430000 |
| base_c01_5x5_b03 | SW-UCB_c0.07 | 1000 | 0.989177 | 0.898276 | 42.860000 | 28.570000 | 28.570000 |
| base_c03_20x10_b04 | Round-Robin | 1000 | 0.821503 | 0.763838 | 35.710000 | 35.710000 | 28.570000 |
| base_c03_20x10_b04 | SW-UCB_c0.01 | 1000 | 0.814190 | 0.761402 | 35.710000 | 28.570000 | 35.710000 |
| base_c03_20x10_b04 | SW-UCB_c0.03 | 1000 | 0.815910 | 0.765144 | 28.570000 | 28.570000 | 42.860000 |
| base_c03_20x10_b04 | SW-UCB_c0.07 | 1000 | 0.814190 | 0.765088 | 35.710000 | 28.570000 | 35.710000 |


## P6: transferencia directa de soluciones evaluadas

El código `CooperativePortfolio` del checkout paralelo ofrece hasta dos soluciones **ya evaluadas** a las estructuras internas del receptor antes del bloque, desde índice 6. No cobra una segunda FE por reutilizar los objetivos deterministas del incumbente; cada nuevo hijo sí se evalúa. Es diferente del padre externo: éste cambia el segundo padre de cruce y no inserta incumbentes en poblaciones.

La selección efectiva de ofertas ordena lexicográficamente Cmax,T,E y toma primero/último. El diseño proponía criterios diferentes por algoritmo, que no deben confundirse con la implementación observada. Se exige procedencia extranjera activa; el receptor filtra duplicados y decide supervivencia conforme a sus estructuras. No se afirma que esos extremos lexicográficos maximicen cobertura del frente.

Piloto de dos bases y una semilla:

| instance_name | condition | final_hv | auc_hv | moead_fe | nsga2_fe | spea2_fe |
| --- | --- | --- | --- | --- | --- | --- |
| base_c01_5x5_b03 | MOEAD_Standalone | 1.011508 | 0.923114 | 1000 | 0 | 0 |
| base_c01_5x5_b03 | Portfolio_RoundRobin | 0.990285 | 0.897325 | 350 | 350 | 300 |
| base_c01_5x5_b03 | Portfolio_SWUCB_Passive | 0.987354 | 0.908745 | 600 | 200 | 200 |
| base_c01_5x5_b03 | Portfolio_SWUCB_Cooperative | 0.988580 | 0.899499 | 650 | 200 | 150 |
| base_c03_20x10_b04 | MOEAD_Standalone | 0.846003 | 0.778802 | 1000 | 0 | 0 |
| base_c03_20x10_b04 | Portfolio_RoundRobin | 0.821503 | 0.763838 | 350 | 350 | 300 |
| base_c03_20x10_b04 | Portfolio_SWUCB_Passive | 0.814190 | 0.761402 | 350 | 300 | 350 |
| base_c03_20x10_b04 | Portfolio_SWUCB_Cooperative | 0.824371 | 0.767441 | 400 | 250 | 350 |


Control posterior de secuencia fija:

| instance_name | condition | final_hv | auc_hv | moead_fe | nsga2_fe | spea2_fe |
| --- | --- | --- | --- | --- | --- | --- |
| base_c01_5x5_b03 | Cooperative_FixedSequence_Control | 0.995187 | 0.899787 | 600 | 200 | 200 |
| base_c03_20x10_b04 | Cooperative_FixedSequence_Control | 0.818510 | 0.764400 | 350 | 300 | 350 |


En 5×5 el control fijo alcanza .995187 frente a .987354 pasivo, pero MOEA/D logra 1.011508. En 20×10 .818510 frente a .814190, con MOEA/D .846003. Los incrementos no convierten dos bases/una semilla en validación general. Las fracciones 42.4%/57.6% de un informe son particiones aritméticas de una corrida, no una descomposición causal identificada. Sumar eventos de supervivencia por bloques tampoco cuenta genotipos únicos retenidos al final.

## P7: corte parcial, separado de la confirmación principal

Plan: 10 bases nominales de desarrollo × 5 semillas × 7 condiciones =350 corridas de 1000 FE, c=.01, bloques50, población30, κ=2 desde bloque6. El corte contiene **317/350 filas**, 10 bases observadas y **9 bases completas** en las siete condiciones y cinco semillas (315 filas). Se resume sólo ese subconjunto equilibrado; el criterio es completitud, no rendimiento. La última geometría incompleta limita representatividad por tamaño. No se calculan p confirmatorias ni se mezcla con 3000 FE.


| condition | n_complete_bases | mean_hv | mean_auc | mean_seconds |
| --- | --- | --- | --- | --- |
| MOEAD_Standalone | 9 | 0.912168 | 0.842305 | 1.486693 |
| NSGA2_Standalone | 9 | 0.906653 | 0.843554 | 1.728498 |
| Portfolio_Coop_FixedSequence | 9 | 0.896995 | 0.827392 | 1.760202 |
| Portfolio_RoundRobin_Passive | 9 | 0.874743 | 0.815889 | 1.683967 |
| Portfolio_SWUCB_Cooperative | 9 | 0.897042 | 0.827550 | 1.768300 |
| Portfolio_SWUCB_Passive | 9 | 0.885444 | 0.822243 | 1.705627 |
| SPEA2_Standalone | 9 | 0.902645 | 0.839068 | 1.760251 |


En este corte, coop online − pasivo es +.011598 HV medio y fijo − pasivo +.011551. MOEA/D mantiene mayor HV medio (.912168) que coop online (.897042). Son cifras **provisionales de nueve bases**, no el resultado final P7. NSGA-II tiene mayor AUC media que MOEA/D en este subconjunto a 1000 FE: presupuesto y cohorte importan al hablar de eficiencia.

Las columnas P7 `marginal_loo_hv_*` eliminan del **archivo global final** las soluciones etiquetadas por primera observación en un brazo. Miden marginalidad de esa partición de procedencia, sin recuperar archivos locales completos. No equivalen al MC de retirar el archivo del algoritmo entero y no se mezclan con él. La etiqueta tampoco es ascendencia genética.

## Inconsistencias narrativas pendientes

El protocolo declara 100 holdout, pero el split preservado contiene 80 variantes/16 bases. Describe MOEA/D como “límite superior” aunque sólo es un control empírico. El tamaño genotípico tampoco es N!×5ᴺ para una secuencia de trabajos repetidos: con M operaciones por trabajo el número de secuencias es N!/∏ⱼ(M!) antes de considerar equivalencias fenotípicas. Los informes originales se preservan sin corregirlos aquí.

Fuente y hashes: [corte adicional](evidence/additional_campaign_cutoff.json); [copia de archivos usados](evidence/additional_campaign_snapshot/). Datos completos del corte: [p7_partial_snapshot.csv](tables/p7_partial_snapshot.csv); medias equilibradas: [p7_partial_complete_base_means.csv](tables/p7_partial_complete_base_means.csv). Se verificó split de desarrollo y 1000 FE. Todas las lecturas permanecieron estables durante la captura. No se certificaron aún fuentes cargadas por corrida, telemetría completa de inyección ni cierre final. Cuando termine P7 corresponde otra auditoría en otro corte/directorio, conservando éste.
