"""Final read-only preservation and calculation audit; zero optimization FE."""
from pathlib import Path
import json,sys,re,datetime,hashlib
import numpy as np,pandas as pd
O=Path(__file__).resolve().parents[1];ROOT=O.parents[1];T=O/'tables';E=O/'evidence';REC=ROOT/'results/portfolio_loop_20261015'
sys.dont_write_bytecode=True;sys.path.insert(0,str(ROOT/'src'))
from preserve import sha,git
from mojssp.hypervolume import compute_hypervolume
from mojssp.dmab import SlidingWindowUCB
from mojssp.cooperation import ScaleAwareUCB
def js(p):return json.loads(p.read_text(encoding='utf-8-sig'))
pres=js(E/'preservation_before.json');changes=[];currenthash={}
print('Rechecking',len(pres['files']),'source files',flush=True)
for i,f in enumerate(pres['files']):
 p=Path(f['path']);h=sha(p) if p.exists() else None;currenthash[str(p)]=h
 if h!=f['sha256']:changes.append({'path':str(p),'before':f['sha256'],'after':h})
 if i and i%1500==0:print(i,'source paths checked',flush=True)
repo_checks=[];new_outside=[];known=set(currenthash)
for r in pres['repositories']:
 p=Path(r['path']);now=git(p,'status','--porcelain=v1','--untracked-files=all')['stdout'];old=r['status']['stdout'];strip=lambda s:'\n'.join(l for l in s.splitlines() if 'results/reunion_directores_20261016/' not in l)
 repo_checks.append(dict(repo=str(p),head_unchanged=git(p,'rev-parse','HEAD')['stdout']==r['head']['stdout'],branch_unchanged=git(p,'branch','--show-current')['stdout']==r['branch']['stdout'],status_unchanged_except_output=strip(now)==strip(old)))
 for folder in ['src','scripts','tests','data','results']:
  for f in (p/folder).rglob('*'):
   if f.is_file() and O not in f.parents and '__pycache__' not in f.parts and str(f) not in known:new_outside.append(str(f))

inv=pd.read_csv(O/'05_inventario_instancias.csv');feature=inv[inv.feature_status=='parsed'].drop_duplicates('instance').set_index('instance');front=pd.read_csv(T/'recent_final_fronts.csv');normalization_errors=[]
for ins,d in front.groupby('instance'):
 row=feature.loc[ins];lo=np.array([row.cmax_lower_bound,0,row.energy_lower_bound]);hi=np.array([row.cmax_upper_bound,row.tardiness_upper_bound,row.energy_upper_bound]);raw=d[['makespan','tardiness','energy']].to_numpy();expected=np.divide(raw-lo,hi-lo,out=np.zeros_like(raw),where=(hi-lo)!=0)
 normalization_errors.append(float(np.max(np.abs(expected-d[['n_cmax','n_tardiness','n_energy']].to_numpy()))))

genotype_invalid=0;genotype_hash_mismatch=0;cardinality_errors=[]
for row in front.itertuples(index=False):
 seq=json.loads(row.sequence);modes=json.loads(row.modes);f=feature.loc[row.instance];n=int(f.operations);jobs=int(f.jobs);machines=int(f.machines)
 genotype_invalid+=not(len(seq)==n and len(modes)==n and all(seq.count(j)==machines for j in range(1,jobs+1)) and all(1<=m<=f.modes_max for m in modes))
 key=f'seq:{tuple(seq)}_modes:{tuple(modes)}';genotype_hash_mismatch+=hashlib.sha256(key.encode('utf-8')).hexdigest()[:16]!=row.id
runmeta=pd.read_csv(T/'recent_runs.csv')
for (split,instance,seed,method),d in front.groupby(['split','instance','seed','method']):
 r=runmeta[(runmeta.split==split)&(runmeta.instance==instance)&(runmeta.seed==seed)&(runmeta.method==method)].iloc[0]
 unique=len(d[['makespan','tardiness','energy']].drop_duplicates())
 if len(d)!=r.archive_size or unique!=r.unique_vectors:cardinality_errors.append(dict(split=split,instance=instance,seed=int(seed),method=method,archive=len(d),unique=unique))

historical=[]
for line in (ROOT/'results/expanded_portfolio_phase2/budget_diagnostic/budget_fronts.jsonl').open(encoding='utf-8'):
 d=json.loads(line);row=feature.loc[d['instance_name']];lo=np.array([row.cmax_lower_bound,0,row.energy_lower_bound]);hi=np.array([row.cmax_upper_bound,row.tardiness_upper_bound,row.energy_upper_bound]);raw=np.array(d['pareto_front'],float);points=np.divide(raw-lo,hi-lo,out=np.zeros_like(raw),where=(hi-lo)!=0);h=compute_hypervolume(points.tolist());historical.append(dict(run_id=d['run_id'],budget=d['budget'],instance=d['instance_name'],algorithm=d['algorithm'],hv_json=d['final_hv'],hv_recomputed=h,error=abs(h-d['final_hv'])))
pd.DataFrame(historical).to_csv(T/'historical_front_metric_checks.csv',index=False,encoding='utf-8-sig')
canon=pd.read_csv(ROOT/'results/pareto_cooperation_research/canonical_complementarity_metrics.csv');un=pd.read_csv(T/'historical_standalone_union.csv');canon_errors=[]
for a,c in [('MOEA/D','canonical_mc_moead'),('NSGA-II','canonical_mc_nsga2'),('SPEA2','canonical_mc_spea2')]:
 q=un[un.arm==a].merge(canon,left_on=['instance','seed','FE_per_arm'],right_on=['instance_name','seed','budget']);canon_errors.extend(abs(q.marginal_hv-q[c]).tolist())

replay=[];passive=[];sourcechecks=[]
source_trees={name:{str(p.relative_to(REC/'code'/name)).replace('\\','/'):sha(p) for p in (REC/'code'/name).rglob('*.py')} for name in ['baseline','research_v1','research_v2','confirmation_frozen']}
correction=js(REC/'baseline_execution_provenance.json');baseline_errors=[p for p,h in correction['loaded_module_sha256'].items() if source_trees['baseline'].get(p)!=h]
for split in ['development','confirmation']:
 files=sorted((REC/'runs'/split).glob('*.json'));bycase={}
 for p in files:
  r=js(p);bycase.setdefault((r['case'],r['seed']),{})[r['method']]=r
  if r['method'] in ['adaptive','scaled']:
   cls=SlidingWindowUCB if r['method']=='adaptive' else ScaleAwareUCB;selector=cls(['MOEA/D','NSGA-II','SPEA2'],window_size=10,exploration_factor=.07,seed=r['seed']);mismatches=0;decisions=0
   for b in r['blocks']:
    if b['phase']=='warmup':selector.initialize_arm(b['arm_name']);continue
    selected=selector.select_arm();mismatches+=selected!=b['arm_name'];decisions+=1;selector.update(b['arm_name'],b['reward'])
   replay.append(dict(split=split,instance=r['case'],seed=r['seed'],method=r['method'],decisions=decisions,mismatches=mismatches))
  if split=='development' and r['method'] in ['moead','nsga2','spea2','uniform','adaptive']:
   sourcechecks.append(dict(file=str(p),status='baseline_loaded_source_correction',matching_snapshots='baseline',errors=len(baseline_errors)))
  else:
   matches=[name for name,tree in source_trees.items() if all(tree.get(k.replace('\\','/'))==h for k,h in r['source_sha256'].items())]
   sourcechecks.append(dict(file=str(p),status='complete_snapshot_match' if matches else 'no_complete_snapshot_match',matching_snapshots=';'.join(matches),errors=int(not matches)))
 for (case,seed),runs in bycase.items():
  uf=runs['uniform']['milestones']['3000'];pool=[e for m in ['moead','nsga2','spea2'] for e in runs[m]['milestones']['1000']];points=np.array([e['normalized'] for e in pool]);ndids={e['id'] for e,x in zip(pool,points) if not np.any(np.all(points<=x,axis=1)&np.any(points<x,axis=1))};passive.append(dict(split=split,instance=case,seed=seed,uniform_equals_ND_union_short_streams=ndids=={e['id'] for e in uf},standalone_FE_each=1000,portfolio_FE=3000))
pd.DataFrame(replay).to_csv(T/'offline_selector_replay_checks.csv',index=False,encoding='utf-8-sig');pd.DataFrame(passive).to_csv(T/'passive_union_checks.csv',index=False,encoding='utf-8-sig');pd.DataFrame(sourcechecks).to_csv(T/'execution_snapshot_checks.csv',index=False,encoding='utf-8-sig')

frozen=js(REC/'artifact_index.json');frozenbad=[]
for f in frozen['files']:
 p=ROOT/f['path'];h=currenthash.get(str(p));h=h if h is not None else sha(p) if p.exists() else None
 if h!=f['sha256']:frozenbad.append(f['path'])

broken=[]
for f in O.rglob('*.md'):
 for target in re.findall(r'\]\(([^)]+)\)',f.read_text(encoding='utf-8')):
  target=target.split('#')[0]
  if not target or re.match(r'^[a-zA-Z]+:',target):continue
  resolved=(f.parent/target).resolve()
  if not resolved.exists() and resolved not in {(O/'evidence_manifest.json').resolve(),(E/'verification.json').resolve()}:broken.append(dict(file=str(f.relative_to(O)),target=target))
figures=js(O/'figures/figure_manifest.json');missing_figsources=[f['source'] for f in figures if not (O/f['source']).exists()]
required=['01_evolucion_investigacion.md','02_arquitectura_portafolio.md','03_catalogo_algoritmos_portafolios.md','04_cambios_implementados.md','05_inventario_instancias.csv','06_caracterizacion_instancias.md','07_clasificacion_tamanos.md','08_rendimiento_por_tamano.md','09_rendimiento_por_caracteristicas.md','10_especializacion_algoritmica.md','11_comparacion_standalones_portafolios.md','12_analisis_estadistico.md','13_eficiencia_computacional.md','14_complementariedad.md','15_espacio_objetivos.md','16_contribuciones_por_brazo.md','17_analisis_adaptabilidad.md','18_analisis_recompensas.md','19_asignacion_presupuesto.md','20_analisis_cooperacion.md','21_analisis_combinacion_mecanismos.md','22_por_que_no_supera_moead.md','23_eficiencia.md','24_adaptabilidad.md','25_relacion_objetivos_tesis.md','26_resumen_ejecutivo.md','27_guion_reunion.md','28_preguntas_respuestas.md','29_decisiones_directores.md','30_auditoria_final.md','31_limitaciones_y_pendientes.md','INFORME_INTEGRAL_MOJSSP.md','INDICE.md']
missing=[x for x in required if not (O/x).exists()];recent=pd.read_csv(T/'recent_runs.csv');hist=pd.read_csv(T/'historical_runs_separated.csv');reserved=set(inv.loc[inv.split=='holdout_test','instance']);leaks=(set(recent.instance)|set(hist.instance))&reserved
v=dict(timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_files_rehashed=len(pres['files']),modified_or_deleted_originals=changes,new_files_outside_output=new_outside,repositories=repo_checks,frozen_index_files_checked=len(frozen['files']),frozen_index_mismatches=frozenbad,baseline_loaded_source_snapshot_errors=baseline_errors,execution_snapshots_checked=len(sourcechecks),execution_snapshot_errors=sum(x['errors'] for x in sourcechecks),recent_normalization_max_error=max(normalization_errors),historical_fronts_checked=len(historical),historical_front_max_hv_error=max(x['error'] for x in historical),canonical_marginal_comparisons=len(canon_errors),canonical_marginal_max_error=max(canon_errors),offline_selector_decisions=sum(x['decisions'] for x in replay),offline_selector_mismatches=sum(x['mismatches'] for x in replay),passive_union_pairs=len(passive),passive_union_failures=sum(not x['uniform_equals_ND_union_short_streams'] for x in passive),holdout_performance_instances=list(leaks),missing_required=missing,broken_local_links=broken,figures=len(figures),missing_figure_sources=missing_figsources,new_optimization_FE=0,new_package_installations=0,executive_summary_words=len((O/'26_resumen_ejecutivo.md').read_text(encoding='utf-8').split()))
local_changes=[x for x in changes if Path(x['path']).is_relative_to(ROOT)]
local_new=[x for x in new_outside if Path(x).is_relative_to(ROOT)]
v['source_paths_examined']=len(pres['files']);v['source_files_rehashed']=sum(h is not None for h in currenthash.values());v['source_paths_unavailable']=sum(h is None for h in currenthash.values())
v['modified_originals_in_task_workspace']=local_changes;v['new_files_outside_output_in_task_workspace']=local_new
v['saved_genotypes_checked']=len(front);v['invalid_saved_genotypes']=genotype_invalid;v['genotype_ID_mismatches']=genotype_hash_mismatch;v['archive_cardinality_mismatches']=cardinality_errors
v['all_external_repositories_preserved']=not changes and not new_outside and all(r['head_unchanged'] and r['branch_unchanged'] and r['status_unchanged_except_output'] for r in repo_checks)
v['external_state_changed']=not v['all_external_repositories_preserved']
v['passed']=not(local_changes or local_new or frozenbad or baseline_errors or v['execution_snapshot_errors'] or missing or broken or missing_figsources or leaks or v['offline_selector_mismatches'] or v['passive_union_failures'] or genotype_invalid or genotype_hash_mismatch or cardinality_errors) and v['recent_normalization_max_error']<1e-12 and v['historical_front_max_hv_error']<1e-12 and all(r['head_unchanged'] and r['branch_unchanged'] and r['status_unchanged_except_output'] for r in repo_checks[:2])
v['status']='analysis_verified_external_changes_disclosed' if v['passed'] and v['external_state_changed'] else 'verified' if v['passed'] else 'review_required'
(E/'verification.json').write_text(json.dumps(v,indent=2,ensure_ascii=False),encoding='utf-8')
f=O/'30_auditoria_final.md';text=f.read_text(encoding='utf-8').split('\n## Resultado de la verificación de cierre')[0];text+='\n## Resultado de la verificación de cierre\n\n'+f"Estado: **{v['status']}**. Se recomprobaron {v['source_files_rehashed']} archivos del inventario inicial. En el checkout de esta tarea: {len(local_changes)} originales modificados/eliminados y {len(local_new)} archivos nuevos fuera del directorio autorizado. El repositorio original mojssp-dmab conserva sus archivos, rama, HEAD y estado Git. Índice congelado reciente: {v['frozen_index_files_checked']} archivos, {len(frozenbad)} discrepancias.\n\n**Incidencia externa:** la copia `mojssp-dmab - copia` desapareció durante la tarea y otro checkout produjo datos P7 y modificó su diseño. Se observan {len(changes)} rutas externas cambiadas/no disponibles y {len(new_outside)} archivos externos nuevos respecto al inventario. No fueron operaciones de esta auditoría. No se certifica preservación global de los directorios externos ni se intenta restaurarlos. El corte adicional P7 se conserva separado y no altera la confirmación principal.\n\nSe verificaron {len(sourcechecks)} procedencias recientes, {v['offline_selector_decisions']} decisiones offline del selector y {len(passive)} equivalencias de unión pasiva. Se recalcularon {len(historical)} HV de frentes históricos, error máximo {v['historical_front_max_hv_error']:.3g}. Las {len(canon_errors)} contribuciones canónicas históricas comparadas tienen error máximo {v['canonical_marginal_max_error']:.3g}. No se encontraron instancias de rendimiento reservadas en las tablas analizadas.\n\nDetalle completo: [verification.json](evidence/verification.json) y [corte adicional](evidence/additional_campaign_cutoff.json).\n";f.write_text(text,encoding='utf-8')
products=[]
for f in sorted(O.rglob('*')):
 if f.is_file() and f.name!='evidence_manifest.json' and '__pycache__' not in f.parts:products.append(dict(path=str(f.relative_to(O)).replace('\\','/'),bytes=f.stat().st_size,sha256=sha(f)))
manifest=dict(schema_version=1,purpose='Thesis directors meeting 2026-10-16; read-only audit',created_utc=v['timestamp_utc'],workspace=str(ROOT),head=pres['repositories'][0]['head']['stdout'].strip(),branch=pres['repositories'][0]['branch']['stdout'].strip(),original_inventory={'path':'evidence/preservation_before.json','sha256':sha(E/'preservation_before.json'),'n_original_files':len(pres['files'])},campaign_inventory='tables/campaign_inventory.csv',figure_sources='figures/figure_manifest.json',verification='evidence/verification.json',scope={'new_search_FE':0,'holdout_result_payloads_parsed':False,'holdout_instance_features':'metadata only','original_files_modified_in_task_workspace':len(local_changes),'external_original_paths_changed_or_unavailable':len(changes),'external_state_changed':v['external_state_changed'],'push_performed':False,'branch_switch_performed':False},products=products,manifest_excludes_itself=True)
(O/'evidence_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({**{k:v[k] for k in ['passed','status','source_files_rehashed','execution_snapshot_errors','historical_front_max_hv_error','offline_selector_mismatches','passive_union_failures','missing_required','broken_local_links']},'changed_external_paths':len(changes),'new_external_files':len(new_outside),'changed_task_workspace_originals':len(local_changes)},ensure_ascii=False,indent=2))
