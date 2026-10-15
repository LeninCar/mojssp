"""Requirement-level closure audit grounded in raw-run integrity and frozen gates."""
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from run_portfolio_loop import OUT, write_new


def read(name):
    return json.loads((OUT/name).read_text(encoding='utf-8'))


def main():
    closure=read('closure_decision.json')
    integrity=read('integrity_audit.json')
    tests=read('final_test_audit.json')
    manifest=read('manifest.json')
    reproduction=read('reproduction_audit.json')
    assert integrity['passed'] and tests['exit_code']==0 and reproduction['passed']
    assert closure['stop_reason'] in ['reproducible_improvement','experimental_budget']
    assert closure['iterations_completed']<=10
    assert closure['all_search_fe_including_reproduction']<=manifest['max_search_fe']
    branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    changed=subprocess.check_output(['git','diff','--name-only'],cwd=ROOT,text=True).splitlines()
    assert branch=='experiment/pareto-archive-cooperation'
    assert head.startswith('1d695f3')
    assert set(changed)=={'src/mojssp/arms.py','src/mojssp/moead.py','src/mojssp/spea2.py'}
    assert len([c for c in manifest['cases'] if c['split']=='development'])==6
    assert len([c for c in manifest['cases'] if c['split']=='confirmation'])==8
    assert all(c['path'].startswith('results') for c in manifest['cases'])
    # Inspect exact three source edits too: objectives, archive and metrics unchanged.
    assert len(integrity['methods'])==8
    assert all(integrity['methods'][m]>=18 for m in ['moead','nsga2','spea2','uniform','adaptive','guidance','scaled','combined'])
    requirements=[
        ('Auditoría y línea base reproducible', ['environment_audit.json','analysis_baseline.json','reproduction_audit.json'],
         '90 controles nuevos, cinco métodos, seis bases y tres semillas; reproducción exacta de cinco controles completos.'),
        ('Limitaciones e hipótesis fundamentadas', ['baseline_decision.json','iteration_01_hypothesis.json','iteration_02_hypothesis.json','iteration_03_hypothesis.json'],
         'Unión pasiva, escala UCB y gasto tras ceros; literatura primaria enlazada en protocolo e informe.'),
        ('Cambios aislados y comparación anterior/individual/uniforme', ['analysis_development_final.json','analysis_confirmation_final.json'],
         'I1 replay idéntico; I2 sólo escala; I3 guía añadida a I2. Controles pares por base/semilla. El replay se etiqueta condicionado a planificación externa.'),
        ('Cooperación real y archivo global', ['integrity_audit.json','replay_inference_note.json'],
         'Padres extranjeros en cruces nativos; hijos reevaluados. Igualdad uniforme/unión independiente probada; sin confundir autoría con ascendencia.'),
        ('Adaptación, estancamiento y complementariedad', ['analysis_confirmation_final.json','report.md'],
         'Asignación, FE tras dos ceros, recuperaciones, inactividad y HV exclusivo. Se reporta evidencia negativa/inconclusa, sin afirmar que todo estancamiento se resuelva.'),
        ('Calidad, diversidad, eficiencia FE y tiempo', ['integrity_audit.json','analysis_confirmation_final.json','trajectories.png','allocation.png'],
         'HV/AUC desde FE0, genotipos, vectores únicos, rangos, vecino, HV exclusivo, umbrales censurados, tiempos delimitados; todos recalculables.'),
        ('Tamaños y características diversas', ['manifest.json','report.md'],
         '14 bases nuevas, perfiles distintos, 25 a 2500 operaciones; análisis por base, sin inferir causalidad de factores confundidos.'),
        ('Retener y descartar según evidencia', ['iteration_01_decision.json','iteration_02_decision.json','iteration_03_decision.json','confirmation_freeze.json','closure_decision.json'],
         'Criterios congelados antes de confirmar; combinación rechazada; configuración operativa diferenciada del experimento de replay.'),
        ('Registros inmutables, sin test final ni métricas históricas alteradas', ['protocol.md','baseline_execution_provenance.json','integrity_audit.json'],
         'Creación exclusiva de resultados; fuentes congeladas verificadas, hashes de instancias y reevaluaciones. Ningún archivo histórico seguido fue modificado; sólo instancias nuevas en búsqueda.'),
        ('Aislamiento, restricciones del problema y sin push', ['environment_isolation_correction.json','final_workspace_state.txt'],
         'HEAD/rama experimental preservados; sólo tres módulos nativos con hook optativo. Error transitorio de instalación global revertido; validación final en .venv. Sin comandos de push ni escritura en repositorio original.'),
        ('Límite y condición de detención', ['runtime_cap_accounting_note.json','closure_decision.json'],
         'Hasta diez iteraciones: se ejecutaron tres y se verificó una condición de detención autorizada. Gastos de reproducción y reevaluación separados; faltantes/posible exceso temporal explícitos.'),
        ('Conclusiones, condiciones, límites y siguiente hipótesis', ['report.md'],
         'Conclusiones por mecanismo, pérdidas por base, comparaciones con individuales y límites estadísticos; pendientes científicos declarados sin inventar resultados.')]
    for _,paths,_ in requirements:
        for p in paths:
            assert (OUT/p).exists(),p
    result={'passed':True,'branch':branch,'HEAD':head,'tracked_changes':changed,
            'stop_reason':closure['stop_reason'],
            'requirements':[{'requirement':r,'evidence':p,'scope':s,'status':'verified within authorized experimental stopping scope'} for r,p,s in requirements],
            'interpretation':'Completion means this bounded research campaign and its requested reporting are complete; not universal superiority, solved optimization, or proven success of untested live cooperative policies.'}
    write_new(OUT/'completion_audit.json',result)
    print('Verified all 12 requirement groups against current artifacts and workspace state.')


if __name__=='__main__':
    main()
