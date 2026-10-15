"""Add the parallel-cooperation lineage and external preservation incident.
Run after report.py, before verify.py. Uses a fixed snapshot, never refreshes P7.
"""
from pathlib import Path
import json
import pandas as pd,numpy as np
O=Path(__file__).resolve().parents[1];T=O/'tables';E=O/'evidence'
def read(n):return pd.read_csv(T/(n+'.csv'))
def table(d,cols=None):
 if cols is not None:d=d[cols]
 def f(v):return 'No disponible' if pd.isna(v) else f'{v:.6f}' if isinstance(v,(float,np.floating)) else str(v).replace('|','/')
 return '\n| '+' | '.join(d.columns)+' |\n| '+' | '.join(['---']*len(d.columns))+' |\n'+'\n'.join('| '+' | '.join(f(x) for x in row)+' |' for row in d.itertuples(index=False,name=None))+'\n'
if (E/'verification.json').exists() and not (E/'verification_initial_external_incident.json').exists():(E/'verification_initial_external_incident.json').write_bytes((E/'verification.json').read_bytes())
cut=json.loads((E/'additional_campaign_cutoff.json').read_text(encoding='utf-8'));p5=read('p5_selector_sensitivity');p6=read('p6_injection_pilot');p6fixed=read('p6_injection_fixed_control');p7=read('p7_partial_descriptive')
text=f"""# Línea paralela P5/P6/P7: sensibilidad e inyección de incumbentes

Esta línea está en `mojssp-pareto-cooperation`, distinta de la campaña reciente de padre externo en `mojssp-loop-agent`. Sus artefactos P5/P6 ya estaban en el inventario inicial. P7 siguió produciendo datos durante esta auditoría y se capturó una instantánea **a {cut['cutoff_utc']}**. No se ejecutó, detuvo ni modificó esa campaña. No se actualiza silenciosamente este corte.

## P5: disminuir c no equivale a escalar recompensas

Dos bases, semilla 42, 1000 FE: RR y c=.01/.03/.07 con W=10. En 5×5 c=.01 concentra 71.43% de **las FE adaptativas**, pero sólo 600/1000 FE totales en MOEA/D. En 20×10 asigna 35.71% de FE adaptativas a MOEA/D y su HV es inferior al RR. Por tanto, la frase de un diseño “más del 70% al dominante” describe una base y un denominador, no un resultado general.

{table(p5,['instance_name','policy_name','total_fe','final_hv','auc_hv','adapt_pct_moead','adapt_pct_nsga2','adapt_pct_spea2'])}

## P6: transferencia directa de soluciones evaluadas

El código `CooperativePortfolio` del checkout paralelo ofrece hasta dos soluciones **ya evaluadas** a las estructuras internas del receptor antes del bloque, desde índice 6. No cobra una segunda FE por reutilizar los objetivos deterministas del incumbente; cada nuevo hijo sí se evalúa. Es diferente del padre externo: éste cambia el segundo padre de cruce y no inserta incumbentes en poblaciones.

La selección efectiva de ofertas ordena lexicográficamente Cmax,T,E y toma primero/último. El diseño proponía criterios diferentes por algoritmo, que no deben confundirse con la implementación observada. Se exige procedencia extranjera activa; el receptor filtra duplicados y decide supervivencia conforme a sus estructuras. No se afirma que esos extremos lexicográficos maximicen cobertura del frente.

Piloto de dos bases y una semilla:
{table(p6,['instance_name','condition','final_hv','auc_hv','moead_fe','nsga2_fe','spea2_fe'])}

Control posterior de secuencia fija:
{table(p6fixed,['instance_name','condition','final_hv','auc_hv','moead_fe','nsga2_fe','spea2_fe'])}

En 5×5 el control fijo alcanza .995187 frente a .987354 pasivo, pero MOEA/D logra 1.011508. En 20×10 .818510 frente a .814190, con MOEA/D .846003. Los incrementos no convierten dos bases/una semilla en validación general. Las fracciones 42.4%/57.6% de un informe son particiones aritméticas de una corrida, no una descomposición causal identificada. Sumar eventos de supervivencia por bloques tampoco cuenta genotipos únicos retenidos al final.

## P7: corte parcial, separado de la confirmación principal

Plan: 10 bases nominales de desarrollo × 5 semillas × 7 condiciones =350 corridas de 1000 FE, c=.01, bloques50, población30, κ=2 desde bloque6. El corte contiene **{cut['observed_p7_rows']}/350 filas**, {cut['n_observed_bases']} bases observadas y **{cut['n_complete_bases']} bases completas** en las siete condiciones y cinco semillas ({cut['included_balanced_rows']} filas). Se resume sólo ese subconjunto equilibrado; el criterio es completitud, no rendimiento. La última geometría incompleta limita representatividad por tamaño. No se calculan p confirmatorias ni se mezcla con 3000 FE.

{table(p7)}

En este corte, coop online − pasivo es +.011598 HV medio y fijo − pasivo +.011551. MOEA/D mantiene mayor HV medio (.912168) que coop online (.897042). Son cifras **provisionales de nueve bases**, no el resultado final P7. NSGA-II tiene mayor AUC media que MOEA/D en este subconjunto a 1000 FE: presupuesto y cohorte importan al hablar de eficiencia.

Las columnas P7 `marginal_loo_hv_*` eliminan del **archivo global final** las soluciones etiquetadas por primera observación en un brazo. Miden marginalidad de esa partición de procedencia, sin recuperar archivos locales completos. No equivalen al MC de retirar el archivo del algoritmo entero y no se mezclan con él. La etiqueta tampoco es ascendencia genética.

## Inconsistencias narrativas pendientes

El protocolo declara 100 holdout, pero el split preservado contiene 80 variantes/16 bases. Describe MOEA/D como “límite superior” aunque sólo es un control empírico. El tamaño genotípico tampoco es N!×5ᴺ para una secuencia de trabajos repetidos: con M operaciones por trabajo el número de secuencias es N!/∏ⱼ(M!) antes de considerar equivalencias fenotípicas. Los informes originales se preservan sin corregirlos aquí.

Fuente y hashes: [corte adicional](evidence/additional_campaign_cutoff.json); [copia de archivos usados](evidence/additional_campaign_snapshot/). Datos completos del corte: [p7_partial_snapshot.csv](tables/p7_partial_snapshot.csv); medias equilibradas: [p7_partial_complete_base_means.csv](tables/p7_partial_complete_base_means.csv). Se verificó split de desarrollo y 1000 FE. Todas las lecturas permanecieron estables durante la captura. No se certificaron aún fuentes cargadas por corrida, telemetría completa de inyección ni cierre final. Cuando termine P7 corresponde otra auditoría en otro corte/directorio, conservando éste.
"""
(O/'32_linea_paralela_P5_P6_P7.md').write_text(text,encoding='utf-8')

camp=read('campaign_inventory');pres_text=f"""# Preservación, trazabilidad y corte de evidencia

Se inició en el checkout experimental `mojssp-loop-agent`, rama `experiment/pareto-archive-cooperation`, HEAD `1d695f3efa45d261da89bd7ba832730c33c9d4ca`. Git registra sólo este worktree: el checkout es una copia independiente. No se cambió de rama ni se hizo push.

Antes del análisis se registraron 5236 archivos de fuente, scripts, tests, datos y resultados en cuatro checkouts. El estado Git ya contenía cambios de la campaña reciente: tres brazos modificados, cooperación, scripts y resultados sin seguimiento. Se conserva el [diff inicial](evidence/preexisting_algorithm_changes.diff). Los scripts de esta auditoría sólo escriben en el directorio de reunión.

| Checkout | Rama / HEAD inicial | Conservación observada |
|---|---|---|
| mojssp-loop-agent | experiment/pareto-archive-cooperation / 1d695f3 | Fuente y resultados previos sin cambios; sólo nuevos productos de reunión |
| mojssp-dmab | experiment/page-hinkley-dmab / 47af7eb | Consulta en lectura; estado inicial conservado |
| mojssp-dmab - copia | experiment/page-hinkley-dmab / 47af7eb | Desapareció externamente durante la tarea; no se restauró |
| mojssp-pareto-cooperation | experiment/pareto-archive-cooperation / 1d695f3 | Otro proceso produjo P7 y actualizó su diseño; corte adicional separado |

La [preservación inicial](evidence/preservation_before.json) no se sobrescribe. La [verificación final](evidence/verification.json) distingue integridad del checkout autorizado, del repositorio original y cambios externos observados. No se certifica inmutabilidad global de directorios externos. El recuento de 1336 contenidos/2746 copias corresponde al inicio; algunas rutas de copias desaparecidas ya no existen, aunque sus hashes permanecen registrados.

{table(camp,['campaign','date','code_version','FE','n_instances','n_base_clusters','n_seeds','n_records'])}

El [inventario completo](tables/campaign_inventory.csv) contiene métodos, FE, semillas, configuración, métricas, rutas y limitaciones. Los 450 cortes históricos son 150 trayectorias; las 30 filas PH C5 se reutilizan de calibración. Las fuentes recientes están congeladas en cuatro árboles y un índice SHA-256, con una corrección explícita del código cargado de la base. Un commit histórico no garantiza capturar cambios sucios usados al ejecutar.

Las instancias reservadas sólo se inventarían con metadatos/hashes. No se analizó rendimiento de holdout. P7 tiene una instantánea fija a {cut['cutoff_utc']}, sin iniciar ni esperar nuevas optimizaciones. Sus resultados provisionales no sustituyen la confirmación reciente de 3000 FE.
"""
(O/'00_preservacion_trazabilidad.md').write_text(pres_text,encoding='utf-8')

note="""\n\n## Línea paralela y estado externo

Existe además una línea P5/P6 de sensibilidad de c e inyección directa de incumbentes, distinta del padre externo. P7 seguía produciendo resultados durante la auditoría. Se documenta en [apéndice 32](32_linea_paralela_P5_P6_P7.md), con un corte parcial fijo, sin mezclar presupuestos ni incorporarlo como confirmación. El conteo de instancias corresponde al inicio: desapareció externamente `mojssp-dmab - copia`, mientras el repositorio original `mojssp-dmab` y este checkout conservaron su estado. Véase [preservación](00_preservacion_trazabilidad.md).
"""
for n in ['01_evolucion_investigacion.md','04_cambios_implementados.md','06_caracterizacion_instancias.md','11_comparacion_standalones_portafolios.md','14_complementariedad.md','20_analisis_cooperacion.md','26_resumen_ejecutivo.md','31_limitaciones_y_pendientes.md']:
 p=O/n;s=p.read_text(encoding='utf-8').split('\n\n## Línea paralela y estado externo')[0];p.write_text(s+note,encoding='utf-8')
p=O/'30_auditoria_final.md';s=p.read_text(encoding='utf-8');s=s.replace('No se hizo checkout, commit, push ni modificación de algoritmos o resultados originales. Todo lo nuevo está en este directorio.','Esta auditoría no hizo checkout, commit, push ni modificó algoritmos o resultados originales. Sus productos nuevos están en este directorio. Otros procesos sí cambiaron directorios externos, como registra la verificación final.');p.write_text(s,encoding='utf-8')
p=O/'INDICE.md';s=p.read_text(encoding='utf-8').split('\n## Ampliación de trazabilidad y línea paralela')[0];s+='\n## Ampliación de trazabilidad y línea paralela\n\n- [Preservación y corte inicial](00_preservacion_trazabilidad.md)\n- [P5/P6 y P7 parcial externo](32_linea_paralela_P5_P6_P7.md)\n- [AUC histórica recalculada](tables/historical_auc_recomputed.csv)\n- [Reparto por etapas](tables/allocation_by_stage.csv)\n- [Verificación final](evidence/verification.json)\n';p.write_text(s,encoding='utf-8')
p=O/'INFORME_INTEGRAL_MOJSSP.md';s=p.read_text(encoding='utf-8').split('\n## Ampliación: preservación y línea paralela')[0];s+='\n## Ampliación: preservación y línea paralela\n\n'+pres_text.replace('# Preservación, trazabilidad y corte de evidencia','### Preservación, trazabilidad y corte de evidencia',1)+'\n\n'+text.replace('# Línea paralela P5/P6/P7: sensibilidad e inyección de incumbentes','### Línea paralela P5/P6/P7: sensibilidad e inyección de incumbentes',1)+'\n\nEsta ampliación no cambia las conclusiones de la cohorte principal. La nueva campaña observada no fue iniciada por esta auditoría y su cierre queda pendiente.\n';p.write_text(s,encoding='utf-8')

# Include the newly available historical AUC in the relevant comparison chapter.
auc=read('historical_auc_recomputed').groupby(['budget','algorithm']).auc_hv.mean().reset_index();p=O/'11_comparacion_standalones_portafolios.md';s=p.read_text(encoding='utf-8').split('\n## AUC histórica reconstruida')[0];s+='\n## AUC histórica reconstruida\n\nSe integraron los checkpoints de 50 FE de las 150 trayectorias continuas, desde (0,0), por separado para cada presupuesto. Las filas no son réplicas nuevas y conservan redondeo de origen de los checkpoints.\n'+table(auc)+'\nFuente: [historical_auc_recomputed.csv](tables/historical_auc_recomputed.csv).\n';p.write_text(s,encoding='utf-8')

p=O/'scripts/README.md';s=p.read_text(encoding='utf-8');s+='\n## Ampliaciones de la sesión\n\nDespués de `analyze.py` y `supplement.py`, ejecutar `catalog.py` para completar metadatos, etapas y AUC histórica. `late_campaigns.py` captura fuentes externas una sola vez: se niega a refrescar el corte P7 existente. Tras `report.py`, ejecutar `appendix.py` para incorporar esa instantánea y la incidencia externa; finalmente `verify.py`. La captura de P7 nunca ejecuta ni espera el runner.\n';p.write_text(s,encoding='utf-8')
print('External incident and fixed partial P7 appendix incorporated.')
