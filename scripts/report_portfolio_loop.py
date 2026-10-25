"""Evidence-based Spanish report and explicit prospective gate evaluation."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from run_portfolio_loop import OUT, write_new
from mojssp.project_paths import HISTORICAL_ROOT
from analyze_portfolio_loop import analyze

LABELS={'moead':'MOEA/D','nsga2':'NSGA-II','spea2':'SPEA2','uniform':'Uniforme',
        'adaptive':'SW-UCB original','guidance':'Padre externo, replay',
        'scaled':'UCB escalado','combined':'Escalado + padre externo'}


def table(analysis):
    rows=['| Método | n | HV | AUC-HV | s/corrida | Vectores únicos | Diversidad genotípica |',
          '|---|---:|---:|---:|---:|---:|---:|']
    for m in ['moead','nsga2','spea2','uniform','adaptive','guidance','scaled','combined']:
        if m not in analysis['summary']:
            continue
        s=analysis['summary'][m]
        rows.append(f"| {LABELS[m]} | {s['n_runs']} | {s['hv']:.6f} | {s['auc_hv']:.6f} | {s['seconds']:.3f} | {s['unique_vectors']:.2f} | {s['genetic_diversity']:.4f} |")
    return '\n'.join(rows)


def ci(item):
    return f"{item['mean_delta']:+.6f} [{item['bootstrap95'][0]:+.6f}, {item['bootstrap95'][1]:+.6f}]"


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        parser.error('output directory already exists; choose a new directory')
    if output_dir.is_relative_to(HISTORICAL_ROOT):
        parser.error('output must be outside results/historical')
    output_dir.mkdir(parents=True)
    dev=analyze('development')
    val=analyze('confirmation')
    baseline=val['summary']['adaptive']
    gates={}
    for m in ['scaled','guidance']:
        s=val['summary'].get(m,{})
        c=val['comparisons'].get(f'{m} vs adaptive',{})
        complete=s.get('n_runs')==24 and c.get('hv',{}).get('n_bases')==8 and c['hv']['n_paired_runs']==24
        tests={'full_8_bases_3_seeds':complete}
        if complete:
            tests.update(HV_CI_positive=c['hv']['bootstrap95'][0]>0,
                         AUC_CI_positive=c['auc_hv']['bootstrap95'][0]>0,
                         HV_win_6_of_8=c['hv']['base_wtl'][0]>=6,
                         AUC_win_6_of_8=c['auc_hv']['base_wtl'][0]>=6,
                         genetic_diversity_retained=s['genetic_diversity']/baseline['genetic_diversity']>=.9,
                         runtime_under_1_30=s['seconds']/baseline['seconds']<=1.3)
        gates[m]={'tests':tests,'accepted':all(tests.values()),
                  'comparison':c,'runtime_ratio':s.get('seconds',0)/baseline['seconds'],
                  'genetic_diversity_ratio':s.get('genetic_diversity',0)/baseline['genetic_diversity']}
    integrity=json.loads((OUT/'integrity_audit.json').read_text(encoding='utf-8'))
    reproduction=json.loads((OUT/'reproduction_audit.json').read_text(encoding='utf-8'))
    freeze=json.loads((OUT/'confirmation_freeze.json').read_text(encoding='utf-8'))
    total_fe=integrity['totals']['all_search_fe']
    total_seconds=integrity['totals']['search_seconds']+integrity['totals']['metric_seconds']+integrity['totals']['reproduction_seconds']
    complete_confirm=all(s['n_runs']==24 for s in val['summary'].values()) and len(val['summary'])==7
    manifest=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
    missing=[]
    for case in manifest['cases']:
        if case['split']!='confirmation':
            continue
        for seed in freeze['seeds']:
            for m in freeze['methods']:
                if not (OUT/'runs/confirmation'/f"{case['name']}__{seed}__{m}.json").exists():
                    missing.append({'case':case['name'],'seed':seed,'method':m})
    confirmed=any(g['accepted'] for g in gates.values()) and complete_confirm
    exhausted=total_seconds>=2700 or total_fe+3000>1200000
    decision={'iterations_completed':3,'gates':gates,'frozen_primary':'scaled',
              'confirmation_complete':complete_confirm,
              'confirmation_missing_runs':missing,
              'stop_reason':'reproducible_improvement' if confirmed else ('experimental_budget' if exhausted else 'not_yet_satisfied'),
              'all_search_fe_including_reproduction':total_fe,
              'experimental_seconds_including_final_metrics_and_reproduction':total_seconds,
              'runtime_cap_overshoot_seconds':max(0.,total_seconds-2700),
              'audit_reevaluation_fe_separate':integrity['audit_fe_not_used_for_search'],
              'final_test_accessed':False,'pushes':0,'original_branch_modified':False,
              'integrity_passed':integrity['passed'],'reproduction_passed':reproduction['passed'],
              'default_behavior':'Original public Portfolio/runner defaults preserved; mechanisms are opt-in in experimental runner.',
              'rejected':['combined'],
              'adoptable_research_mechanisms':[m for m,g in gates.items() if g['accepted']]}
    decision['operational_recommendation']={
        'selector':'mojssp.cooperation.ScaleAwareUCB' if gates['scaled']['accepted'] else 'Original selector; no confirmed replacement',
        'window_size':10,'exploration_factor':.07,'enable_live_guidance':False,
        'guidance_scope':'Replay is a causal fixed-allocation experiment. Obtaining its control trace from scratch costs another 3000 FE; not an autonomous equal-budget policy.',
        'combined_live_policy':'Rejected in development; not confirmed or recommended.'}
    write_new(output_dir/'closure_decision.json',decision)
    lines=['# Portafolio MO-JSSP: campaña experimental del 15 de octubre de 2026','',
           f"Se completaron tres iteraciones aisladas. Motivo de cierre: **{decision['stop_reason']}**. "
           'Las conclusiones se limitan al generador, perfiles, presupuestos e instancias evaluados.', '',
           '## Resultado y decisiones','']
    for m,g in gates.items():
        interpretation=('conservar como selector experimental respaldado' if m=='scaled'
                        else 'conservar como evidencia causal bajo asignación externa; no como política autónoma')
        lines.append(f"- **{LABELS[m]}: {interpretation if g['accepted'] else 'no adoptar con la evidencia y los límites actuales'}.** "
                     f"Puertas prospectivas: `{json.dumps(g['tests'])}`.")
        p_holm=g['comparison'].get('hv',{}).get('holm_p',1.)
        if p_holm>=.05:
            lines.append(f"  La permutación exacta de HV con Holm no cruza .05 (p={p_holm:.5f}); "
                         'aunque alguna puerta bootstrap pase, ese respaldo estadístico es limitado '
                         'y no se presenta como superioridad concluyente.')
    lines.extend(['- **Combinación: descartar para adopción.** Frente a UCB escalado en desarrollo, '
                  f"ΔHV {ci(dev['comparisons']['combined vs scaled']['hv'])}; "
                  f"ΔAUC {ci(dev['comparisons']['combined vs scaled']['auc_hv'])}. "
                  'Mezclar dos mecanismos útiles no garantiza sinergia. El tratamiento queda sólo para reproducir el resultado negativo.', '',
                  '**Frente a individuales:** la diferencia pareada de UCB escalado frente a MOEA/D '
                  f"en confirmación es {ci(val['comparisons']['scaled vs moead']['hv'])} de HV. "
                  'Se conserva este contraste incluso si favorece al individual; la aprobación de '
                  'una mejora del portafolio no equivale a vencer a cada algoritmo.', '',
                  '## Auditoría, reproducibilidad y condiciones','',
                  'Checkout experimental independiente, rama `experiment/pareto-archive-cooperation`, '
                  'HEAD inicial `1d695f3`. No se cambió de rama, no se modificó el repositorio original y no hubo push. '
                  'Los dos elementos untracked preexistentes se preservaron. No había procesos Python activos al comenzar.', '',
                  'El archivo global original sólo acumula resultados. En los 18 casos de desarrollo se verificó '
                  'igualdad exacta de los genotipos no dominados del uniforme a 3000 FE con la unión de los '
                  'tres individuales a 1000 FE cada uno: **agregación pasiva, no cooperación activa**. '
                  'Los cinco controles se reprodujeron después de introducir los hooks desactivados: '
                  'mismos frentes, asignaciones, recompensas y métricas en todos los bloques de una base/semilla.', '',
                  'La suite original pasó 361 pruebas y 174 subpruebas. Tras los mecanismos pasó 370 y 174. '
                  'Las pruebas nuevas cubren FE reales, cortes arbitrarios, validación de agendas, invariantes '
                  'de MOEA/D, ausencia de consumo de RNG con el hook desactivado, rechazo de mezcla entre '
                  'instancias, invariancia de escala UCB y revisitas. Véase también la validación final registrada.', '',
                  'Se generaron seis bases de desarrollo y ocho de confirmación interna, independientes y con '
                  'semillas nuevas, sin acceder al test final del proyecto. Las instancias históricas completas '
                  'no estaban disponibles: sus resultados no se usaron como controles. Cada corrida consumió '
                  '3000 FE reales, población 30 y bloques de 50; cotas analíticas originales, referencia '
                  '(1.1,1.1,1.1), inicialización incluida y semillas de brazos master/master+1/master+2. '
                  'Las semillas se promediaron por base antes de inferir. Protocolos, manifiesto, código '
                  'congelado y hashes están en este directorio.', '',
                  '**Procedencia del código:** el proceso de línea base cargó los módulos de HEAD antes '
                  'de los cambios. Su campo raw `source_sha256` leído del disco durante la ejecución '
                  'puede reflejar ediciones posteriores; `baseline_execution_provenance.json` corrige '
                  'esa interpretación sin alterar ninguna corrida, y `code/baseline/` preserva el código. '
                  'Los procesos posteriores capturan hashes al inicio.', '',
                  '## Desarrollo: controles y tres iteraciones','',table(dev),'',
                  'La familia completa de tres candidatos frente al original se ajusta por Holm '
                  'en `analysis_development_final.json`. El desarrollo es exploratorio y selecciona '
                  'candidatos; sus intervalos o valores p interinos no se presentan como confirmación.', '',
                  'I1 cambió exclusivamente el segundo padre cada diez cruces, con donante extranjero '
                  'del Pareto global elegido por máxima distancia mínima normalizada al frente local. '
                  'Reprodujo exactamente la traza de asignación de su control: el cambio de calidad '
                  'no se puede atribuir a más FE por brazo. No hay reemplazo masivo de poblaciones, '
                  'transferencia de objetivos a hijos nuevos ni alteración de pesos; toda descendencia '
                  'pasa por la evaluación y selección nativas.', '',
                  '**Límite del replay:** el control que proporciona la traza consume otras 3000 FE '
                  'en esa instancia/semilla. Ambas corridas se contabilizan en el presupuesto de '
                  'campaña. Las 3000 FE del tratamiento son su coste condicional a una asignación '
                  'externa ya disponible, no el coste de una política autónoma desde cero: control '
                  '+ tratamiento requieren 6000 FE. Sus contrastes contra individuales describen '
                  'calidad bajo asignación controlada, no superioridad desplegable a igual coste '
                  'total. I1 prueba transferencia real de información; no resuelve por sí sola '
                  'su integración online. I3 sí ejecuta feedback cooperativo vivo a 3000 FE.', '',
                  'I2 cambió sólo la escala de explotación UCB: media de ΔHV dividida por el máximo '
                  'absoluto reciente común. Ventana 10 y c=.07 permanecen fijos; los ΔHV registrados '
                  'son crudos. Las observaciones viejas usan el mismo denominador de la decisión '
                  'actual y las ventanas de ceros conservan exploración. Los brazos ausentes de la '
                  'ventana recuperan UCB infinito. No se aplica una preferencia fija por MOEA/D.', '',
                  'I3 añadió el mismo padre externo al selector escalado con feedback vivo. Su control '
                  'es I2. Los cambios de asignación son consecuencia de la intervención; no se presenta '
                  'este contraste como una comparación de reparto fijo. Falló el criterio prospectivo '
                  'de mejorar simultáneamente HV y AUC frente a su padre.', '',
                  '## Confirmación congelada','',table(val),'',
                  'Plan congelado: ocho bases nuevas (5x5 hasta 50x50), tres semillas por base, comparaciones '
                  'prospectivas escalado/original y padre externo/original. Métodos rotados por caso; '
                  'el replay debe seguir al control original. Los siguientes intervalos son bootstrap '
                  'de bases, no de semillas; p es permutación exacta bilateral y Holm cubre los '
                  'dos contrastes HV congelados. HV y AUC están correlacionados; las métricas '
                  'secundarias y los análisis por perfil son exploratorios.', '',
                  '| Mecanismo vs original | ΔHV [IC95%] | ΔAUC [IC95%] | Bases HV G/E/P | p HV Holm | Tiempo relativo | Diversidad relativa |',
                  '|---|---|---|---|---:|---:|---:|'])
    for m,g in gates.items():
        c=g['comparison']
        lines.append(f"| {LABELS[m]} | {ci(c['hv'])} | {ci(c['auc_hv'])} | {c['hv']['base_wtl']} | "
                     f"{c['hv'].get('holm_p',1):.5f} | {g['runtime_ratio']:.3f} | {g['genetic_diversity_ratio']:.3f} |")
    if missing:
        lines.extend(['',f"**Muestra incompleta por presupuesto: {len(missing)} corridas pendientes.** "
                      'No se relajaron los criterios de confirmación. Las medias de métodos con '
                      'distintos casos no son directamente comparables; los contrastes pareados '
                      'usan sólo su intersección. Pendientes:', '',
                      *[f"- `{r['case']}`, semilla {r['seed']}, {LABELS[r['method']]}" for r in missing]])
    lines.extend(['','### Condiciones por base: HV medio','',
                  '| Base | Original | Uniforme | Escalado | Padre externo | Mejor individual observado |',
                  '|---|---:|---:|---:|---:|---|'])
    for case,record in val['by_base'].items():
        ms=record['mean_hv']
        best=record['oracle_best_individual']
        fmt=lambda m: f"{ms[m]:.6f}" if m in ms else 'pendiente'
        lines.append(f"| {case} | {fmt('adaptive')} | {fmt('uniform')} | {fmt('scaled')} | {fmt('guidance')} | {LABELS.get(best,best)} ({fmt(best)}) |")
    lines.append('')
    for m in ['scaled','guidance']:
        losses=[f"`{case}` ({v:+.6f})" for case,v in gates[m]['comparison']['hv']['by_base'].items() if v<0]
        lines.append(f"- Pérdidas de HV observadas de {LABELS[m]} frente al original: "
                     + (', '.join(losses) if losses else 'ninguna en las medias de estas bases') + '.')
    lines.extend(['','| Base | Tiempo escalado/original | Tiempo padre/original | Diversidad escalado/original | Diversidad padre/original |',
                  '|---|---:|---:|---:|---:|'])
    for case,record in val['by_base'].items():
        rs=record['resources']
        if all(m in rs for m in ['adaptive','scaled','guidance']):
            ratio=lambda m,k: rs[m][k]/rs['adaptive'][k] if rs['adaptive'][k] else 0
            lines.append(f"| {case} | {ratio('scaled','seconds'):.3f} | {ratio('guidance','seconds'):.3f} | "
                         f"{ratio('scaled','genetic_diversity'):.3f} | {ratio('guidance','genetic_diversity'):.3f} |")
    lines.extend(['','El mejor individual por base es un **oráculo descriptivo**: se identifica a posteriori, '
                  'no es una política disponible sin información adicional. Los JSON incluyen contrastes '
                  'contra cada individual y contra uniforme. Tamaño y perfil están confundidos; estas '
                  'observaciones no justifican una regla causal basada en tamaño o dificultad.', '',
                  '### Asignación, complementariedad y estancamiento','',
                  '| Método | FE MOEA/D % | FE NSGA-II % | FE SPEA2 % | FE tras dos ΔHV=0 | Recuperaciones positivas | Máximo de bloques ociosos, media |',
                  '|---|---:|---:|---:|---:|---:|---:|'])
    for m in ['adaptive','uniform','guidance','scaled']:
        s=val['summary'].get(m)
        if not s:
            continue
        a=s['mean_allocation']; d=s['stagnation']
        lines.append(f"| {LABELS[m]} | {100*a['MOEA/D']:.1f} | {100*a['NSGA-II']:.1f} | {100*a['SPEA2']:.1f} | "
                     f"{d['fe_after_two_global_zero_gains']:.1f} | {d['positive_recoveries_after_two_zero_gains']:.2f} | {d['max_idle_blocks']:.2f} |")
    lines.extend(['','Un ΔHV global nulo puede indicar redundancia con otro brazo, incluso si hubo '
                  'progreso interno. El gasto tras dos ceros es diagnóstico, no prueba de inutilidad. '
                  'Las revisitas evitan eliminar permanentemente brazos complementarios; la mejora '
                  'de calidad no autoriza afirmar que todo gasto en estancamiento haya disminuido.', '',
                  '| Método | HV exclusivo MOEA/D | HV exclusivo NSGA-II | HV exclusivo SPEA2 |',
                  '|---|---:|---:|---:|'])
    for m in ['adaptive','uniform','guidance','scaled']:
        s=val['summary'].get(m)
        if s:
            a=s['mean_marginal_hv']
            lines.append(f"| {LABELS[m]} | {a['MOEA/D']:.6f} | {a['NSGA-II']:.6f} | {a['SPEA2']:.6f} |")
    lines.extend(['','Se calcula contribución exclusiva como HV(unión) − HV(unión sin el brazo), '
                  'sobre frentes de soluciones realmente evaluadas. Las contribuciones exclusivas '
                  'no suman el HV total, porque hay volumen compartido. Con cooperación, el algoritmo '
                  'receptor genera el hijo; la primera observación de su genotipo no reconstruye '
                  'su ascendencia genética. Una caída del HV exclusivo puede expresar mayor '
                  'solapamiento; no implica por sí sola pérdida de diversidad o de utilidad.', '',
                  '### Eficiencia por FE','',
                  '| Método | Corridas que alcanzan HV final original | FE medios hasta umbral, censura en 3000 | Segundos medios con la misma censura |',
                  '|---|---:|---:|---:|'])
    for m,s in val['FE_to_original_final_HV'].items():
        lines.append(f"| {LABELS[m]} | {s['reached_runs']}/{s['paired_runs']} | {s['mean_fe_capped']:.1f} | {s['mean_seconds_capped']:.3f} |")
    lines.extend(['','El umbral se usa sólo para análisis posterior; nunca guía la búsqueda. Las '
                  'corridas que no lo alcanzan están censuradas y se computan en 3000 FE, no como '
                  'éxitos. AUC integra desde (0,0) por trapecios cada 50 FE. Los tiempos incluyen '
                  'trabajo de los brazos, archivo e instrumentación online; las métricas finales se '
                  'cronometran aparte. Se mide desde el primer bloque; carga de DZN y construcción '
                  'de objetos quedan fuera, por lo que no es tiempo extremo a extremo. Tampoco '
                  'representa una medida aislada de overhead del orquestador. El escritorio compartido '
                  'puede introducir variación temporal; se rotaron los métodos para reducirla.', '',
                  '### Diversidad','',
                  '| Método | Rango Cmax normalizado | Rango tardanza | Rango energía | Vecino medio |',
                  '|---|---:|---:|---:|---:|'])
    for m in ['adaptive','uniform','guidance','scaled']:
        s=val['summary'].get(m)
        if s:
            r=s['mean_objective_range']
            lines.append(f"| {LABELS[m]} | {r[0]:.5f} | {r[1]:.5f} | {r[2]:.5f} | {s['mean_nn_distance']:.5f} |")
    lines.extend(['',
                  'Se conservan número de vectores distintos, rango de cada objetivo, distancia '
                  'media al vecino y distancia Hamming genotípica normalizada de cada población '
                  '(archivo reproductivo en SPEA2). Más distancia entre vecinos puede significar '
                  'dispersión o huecos: no se identifica automáticamente con mejor cobertura. '
                  'Los conteos de procedencia se mantienen separados de diversidad y de ascendencia. '
                  'No se impone una cuota arbitraria de autoría a cada algoritmo. Las distancias '
                  'genotípicas de poblaciones se calcularon en ejecución: no se guardaron las '
                  'poblaciones reproductivas completas. Recalcularlas exige repetir la semilla y '
                  'el código congelado; los archivos Pareto por sí solos no bastan. La fórmula '
                  'se verificó además con un fixture analítico de tres genotipos y las cinco '
                  'reproducciones de control coincidieron en estas medidas.', '',
                  '## Presupuesto, validez y límites','',
                  f"Se consumieron **{total_fe:,} FE de búsqueda** incluyendo 15.000 FE de reproducción; "
                  f"{total_seconds/60:.2f} minutos de tiempo experimental medido. "
                  f"La auditoría independiente realizó {integrity['audit_fe_not_used_for_search']:,} "
                  'reevaluaciones adicionales, separadas y sin alimentar la búsqueda. '
                  f"Se verificaron {integrity['runs']} corridas, sus 60 bloques, todos los genotipos "
                  'de checkpoints y archivos locales, factibilidad de agendas, objetivos, normalización, '
                  'HV, AUC, contribuciones y replay. El techo fue 1.200.000 FE y 45 minutos medidos.', '',
                  f"El control temporal se realiza antes de cada corrida atómica: exceso final "
                  f"de {max(0.,total_seconds-2700):.2f} segundos, sin admitir nuevas corridas tras "
                  'superar el tope. Véase `runtime_cap_accounting_note.json`.', '',
                  'Limitaciones: presupuesto de 3000 FE pequeño para 2500 operaciones; tres semillas '
                  'por base; generador único; perfiles y escala confundidos; sin estudio de sensibilidad '
                  'amplio. I1 no aísla máximo-mínimo frente a donante aleatorio ni demuestra que '
                  'la cadencia de diez cruces sea óptima. Los intervalos bootstrap tienen poca '
                  'resolución con ocho bases. La prueba '
                  'de permutación por cambios de signo requiere simetría bajo la nula. No se afirma '
                  'optimalidad, superioridad universal ni que el portafolio venza a todos los individuales. '
                  'La confirmación es interna y no sustituye el test final independiente. '
                  'No se reajustaron parámetros con la confirmación.', '',
                  '## Fundamento y siguiente hipótesis','',
                  'Li, Fialho, Kwong y Zhang (2014), '
                  '[Adaptive Operator Selection With Bandits for a MOEA Based on Decomposition]'
                  '(https://colalab.ai/publications/LiFKZ14.pdf), DOI 10.1109/TEVC.2013.2239648, '
                  'motiva crédito reciente dependiente de escala y exploración ante recompensas no '
                  'estacionarias. Nuestra normalización por máximo no es una reproducción de FRRMAB. '
                  'La cooperación heterogénea con trazabilidad tiene antecedentes en otros dominios '
                  '([preprint contextual](https://arxiv.org/abs/2607.13200)); no transfiere garantías '
                  'de rendimiento a MO-JSSP.', '',
                  'Primera prueba pendiente, **no ejecutada**: activar el padre externo con SW-UCB '
                  'original y feedback vivo, para distinguir el efecto del replay de la interacción '
                  'con el escalado. Requeriría nueva campaña; no se infiere su éxito a partir de I1. '
                  'Hipótesis adicional, **no ejecutada ni usada para seleccionar**: separar el valor '
                  'del donante del crédito inmediato del receptor podría evitar que la cooperación '
                  'desplace presupuesto hacia brazos que reciben buenas semillas pero no generan '
                  'progreso sostenible. Requeriría trazabilidad de ascendencia real y una nueva '
                  'campaña preregistrada; estas corridas no prueban ese mecanismo.', '',
                  '## Reproducir','',
                  'Desde este checkout con Python 3.12 y las versiones registradas de pytest/numpy/scipy/matplotlib:', '',
                  '```powershell',
                  'python -m venv --system-site-packages .venv',
                  '.\\.venv\\Scripts\\Activate.ps1',
                  'python -m pip install -r results/portfolio_loop_20261015/requirements-experiment.txt',
                  'python -m pytest -q',
                  'python scripts/run_portfolio_loop.py --phase prepare',
                  'python scripts/run_portfolio_loop.py --phase baseline',
                  'python scripts/run_portfolio_loop.py --phase guidance',
                  'python scripts/run_portfolio_loop.py --phase scaled',
                  'python scripts/run_portfolio_loop.py --phase combined',
                  'python scripts/reproduce_portfolio_baseline.py',
                  'python scripts/run_portfolio_loop.py --phase baseline --split confirmation --methods moead nsga2 spea2 uniform adaptive guidance scaled',
                  '```','',
                  'Las corridas completas se omiten sin sobrescribirlas. Para repetir desde cero, '
                  'use una copia aislada del código congelado y un directorio de salida nuevo; '
                  'no borre ni edite los resultados originales. Los análisis y auditorías usan '
                  'creación exclusiva de archivos: cambie la etiqueta/directorio al repetir. '
                  'El protocolo y las hipótesis conservan la secuencia de decisiones.', '',
                  '![Trayectorias de HV](trajectories.png)','',
                  '![Asignación de evaluaciones](allocation.png)',''])
    report=output_dir/'report.md'
    with report.open('x',encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(json.dumps({'stop_reason':decision['stop_reason'],'gates':{m:g['tests'] for m,g in gates.items()},
                      'search_fe':total_fe,'minutes':total_seconds/60},indent=2))


if __name__=='__main__':
    main()
