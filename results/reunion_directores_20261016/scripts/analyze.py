"""Offline meeting audit. Never initializes arms, generates instances, or optimizes.
Run with the bundled Python. All generated files are confined to OUT.
"""
from pathlib import Path
import sys,json,hashlib,itertools,math,csv,platform,re
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[3]; OUT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'src'))
from mojssp.io import load_dzn
from mojssp.normalization import compute_instance_bounds
TAB=OUT/'tables'; EVI=OUT/'evidence'; REC=ROOT/'results/portfolio_loop_20261015'; ORIGINAL=ROOT.parent/'mojssp-dmab'
RNG=np.random.default_rng(20261016)
ARMS=['MOEA/D','NSGA-II','SPEA2']; METHODS=['moead','nsga2','spea2','uniform','adaptive','scaled','guidance','combined']
def save(df,name):df.to_csv(TAB/(name+'.csv'),index=False,encoding='utf-8-sig')
def js(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def dump(name,x):(EVI/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=lambda x:x.item() if hasattr(x,'item') else str(x)),encoding='utf-8')
def hv(points,ref=(1.1,1.1,1.1)):
    """Independent exact box-union sweep. Dominated points need no special removal."""
    p=np.array(list(set(tuple(map(float,p)) for p in points)),dtype=float)
    if p.size==0:return 0.
    p=p[np.all(p<=ref,axis=1)]
    if not len(p):return 0.
    xs=sorted(set(p[:,0])|{ref[0]}); v=0.
    for x,x2 in zip(xs,xs[1:]):
        active=p[p[:,0]<=x,1:]; area=0.; z=ref[2]; last=None
        for y,zz in sorted(map(tuple,active)):
            if last is not None:area+=(y-last)*(ref[2]-z)
            z=min(z,zz);last=y
        if last is not None:area+=(ref[1]-last)*(ref[2]-z)
        v+=(x2-x)*area
    return float(v)
def nd(points):
    p=np.unique(np.asarray(points,dtype=float),axis=0)
    if not len(p):return p
    return p[[not np.any(np.all(p<=x,axis=1)&np.any(p<x,axis=1)) for x in p]]
def summary_ci(v):
    v=np.asarray(v,float); b=RNG.choice(v,(20000,len(v))).mean(axis=1)
    return float(np.quantile(b,.025)),float(np.quantile(b,.975))
def paired_stats(v):
    v=np.asarray(v,float);lo,hi=summary_ci(v)
    perms=np.array(list(itertools.product([-1,1],repeat=len(v)))) if len(v)<=16 else RNG.choice([-1,1],(100000,len(v)))
    p=float(np.mean(np.abs((perms*v).mean(axis=1))>=abs(v.mean())-1e-13))
    sd=float(v.std(ddof=1)) if len(v)>1 else float('nan')
    nonzero=v[np.abs(v)>1e-12];n=len(nonzero);w=int(sum(nonzero>0));p_sign=min(1.,2*sum(math.comb(n,k) for k in range(min(w,n-w)+1))/2**n) if n else 1.
    return dict(n_bases=len(v),mean_delta=float(v.mean()),median_delta=float(np.median(v)),sd_delta=sd,ci_low=lo,ci_high=hi,p_signflip=p,p_exact_sign=p_sign,
        wins=int(sum(v>1e-12)),ties=int(sum(abs(v)<=1e-12)),losses=int(sum(v< -1e-12)),cohen_dz=float(v.mean()/sd) if sd else float('nan'))
def holm(df,p='p_signflip',out='p_holm'):
    vals=df[p].to_numpy();order=np.argsort(vals);adj=np.empty(len(vals));last=0.
    for rank,i in enumerate(order):last=max(last,min(1,vals[i]*(len(vals)-rank)));adj[i]=last
    df[out]=adj;return df
def size(n):return 'pequena' if n<=200 else 'mediana' if n<=1600/3 else 'grande'
def features_object_reference(path):
    ins=load_dzn(str(path));ops=ins.all_operations
    pt=np.array([np.mean([m.duration for m in o.modes]) for o in ops]);en=np.array([np.mean([m.energy for m in o.modes]) for o in ops])
    dur=np.array([m.duration for o in ops for m in o.modes]); energy=np.array([m.energy for o in ops for m in o.modes])
    loads=np.array([sum(p for o,p in zip(ops,pt) if o.machine_id==i) for i in range(1,ins.num_machines+1)])
    counts=np.array([sum(o.machine_id==i for o in ops) for i in range(1,ins.num_machines+1)])
    release=np.array([o.release_date for o in ops]);due=np.array([j.due_date for j in ins.jobs]);chain=np.array([len(j.operations) for j in ins.jobs])
    earliest=[];paths=[]
    for j in ins.jobs:
        t=0;total=0
        for o in j.operations:p=min(m.duration for m in o.modes);t=max(t,o.release_date)+p;total+=p
        earliest.append(t);paths.append(total)
    slack=(due-np.array(earliest))/np.array(paths)
    corrs=[];trade=[];contr=[];speedup=[]; pairs=[]
    for o in ops:
        t=np.array([m.duration for m in o.modes]); e=np.array([m.energy for m in o.modes]);a=int(np.argmin(t));b=int(np.argmax(t))
        corrs.append(float(np.corrcoef(t,e)[0,1]) if np.std(t)>0 and np.std(e)>0 else np.nan)
        trade.append(float(e[a]-e[b]));contr.append(float(max(e)/min(e)) if min(e)>0 else np.nan);speedup.append(max(t)/min(t))
        pairs.extend([(o.machine_id,m.mode_id,m.duration,m.energy) for m in o.modes])
    b=compute_instance_bounds(ins)
    row=dict(jobs=ins.num_jobs,machines=ins.num_machines,operations=ins.total_operations,modes_min=min(len(o.modes) for o in ops),modes_max=max(len(o.modes) for o in ops),jobs_machines_ratio=ins.num_jobs/ins.num_machines,
      operations_per_job_mean=chain.mean(),operations_per_machine_mean=counts.mean(),processing_mean=pt.mean(),processing_sd=pt.std(),processing_cv=pt.std()/pt.mean(),all_modes_duration_mean=dur.mean(),duration_min=dur.min(),duration_max=dur.max(),
      machine_load_mean=loads.mean(),machine_load_max=loads.max(),machine_load_cv=loads.std()/loads.mean(),machine_load_max_mean=loads.max()/loads.mean(),operation_count_hhi=sum((counts/counts.sum())**2),
      release_mean=release.mean(),release_sd=release.std(),release_max=release.max(),release_nonzero_fraction=np.mean(release>0),due_mean=due.mean(),due_sd=due.std(),due_min=due.min(),due_max=due.max(),
      relative_slack_mean=slack.mean(),relative_slack_sd=slack.std(),tight_due_fraction=np.mean(slack<=0),precedence_chain_max=chain.max(),energy_mean=en.mean(),energy_cv=en.std()/en.mean() if en.mean() else np.nan,
      all_modes_energy_mean=energy.mean(),energy_mode_contrast_mean=np.nanmean(contr),time_energy_within_operation_correlation=np.nanmean(corrs),energy_fast_minus_slow_mean=np.mean(trade),duration_mode_speedup_mean=np.mean(speedup),
      cmax_lower_bound=b.cmax_min,cmax_upper_bound=b.cmax_max,tardiness_upper_bound=b.tardiness_max,energy_lower_bound=b.energy_min,energy_upper_bound=b.energy_max,
      geometry_category=size(ins.total_operations),machine_loads=json.dumps(loads.tolist()),machine_operation_counts=json.dumps(counts.tolist()),mode_counts=json.dumps(sorted(set(len(o.modes) for o in ops))))
    bounds=np.array([[b.cmax_min,b.cmax_max],[0,b.tardiness_max],[b.energy_min,b.energy_max]])
    return row,bounds,pairs

def features(path):
    """Vectorized equivalent of JSP2 reader for the large archival inventory.
    Rechecked against the domain-object implementation in supplemental audit.
    """
    txt=re.sub(r'%[^\n]*','',path.read_text(encoding='utf-8'))
    def scalar(k):
        m=re.search(r'\b'+k+r'\s*=\s*(\d+)(?:\.\.(\d+))?\s*;',txt)
        if not m:raise ValueError('Missing scalar '+k)
        return int(m[2])-int(m[1])+1 if m[2] else int(m[1])
    nj=scalar('JOBS');nm=scalar('MACHINES');ns=scalar('SPEED');n=nj*nm
    def array(k,shape,optional=False):
        m=re.search(r'\b'+k+r'\s*=.*?\[(.*?)\]',txt,re.S)
        if not m:
            if optional:return np.zeros(shape)
            raise ValueError('Missing array '+k)
        arr=np.array(re.findall(r'-?\d+',m[1]),dtype=float)
        return arr.reshape(shape)
    time=array('time',(nj,nm,ns));energy=array('energy',(nj,nm,ns));prec=array('precedence',(nj,nm));release=array('releaseDate',(nj,nm),True);dueall=array('dueDate',(nj,nm),True)
    if np.any(time<=0) or np.any(energy<0) or np.any(release<0):raise ValueError('Invalid duration/energy/release')
    pt=time.mean(axis=2);en=energy.mean(axis=2);loads=pt.sum(axis=0);counts=np.full(nm,nj);order=np.argsort(prec,axis=1,kind='stable');idx=np.arange(nj)[:,None]
    mint=time.min(axis=2);maxt=time.max(axis=2);mine=energy.min(axis=2);maxe=energy.max(axis=2)
    sorted_min=mint[idx,order];sorted_release=release[idx,order];due=dueall[idx,order][:,-1];earliest=np.zeros(nj)
    for k in range(nm):earliest=np.maximum(earliest,sorted_release[:,k])+sorted_min[:,k]
    pathmin=mint.sum(axis=1);slack=(due-earliest)/pathmin
    suffix=np.cumsum(sorted_min[:,::-1],axis=1)[:,::-1];lb=float(np.max(sorted_release+suffix));ub=float(release.max()+maxt.sum());tub=float(np.maximum(0,ub-due).sum());elo=float(mine.sum());ehi=float(maxe.sum())
    tc=time-time.mean(axis=2,keepdims=True);ec=energy-energy.mean(axis=2,keepdims=True);den=np.sqrt((tc**2).sum(axis=2)*(ec**2).sum(axis=2));cors=np.divide((tc*ec).sum(axis=2),den,out=np.full((nj,nm),np.nan),where=den>0)
    fast=np.take_along_axis(energy,time.argmin(axis=2)[:,:,None],axis=2)[:,:,0];slow=np.take_along_axis(energy,time.argmax(axis=2)[:,:,None],axis=2)[:,:,0]
    contrasts=np.divide(maxe,mine,out=np.full((nj,nm),np.nan),where=mine>0)
    row=dict(jobs=nj,machines=nm,operations=n,modes_min=ns,modes_max=ns,jobs_machines_ratio=nj/nm,operations_per_job_mean=nm,operations_per_machine_mean=nj,
        processing_mean=pt.mean(),processing_sd=pt.std(),processing_cv=pt.std()/pt.mean(),all_modes_duration_mean=time.mean(),duration_min=time.min(),duration_max=time.max(),machine_load_mean=loads.mean(),machine_load_max=loads.max(),machine_load_cv=loads.std()/loads.mean(),machine_load_max_mean=loads.max()/loads.mean(),operation_count_hhi=1/nm,
        release_mean=release.mean(),release_sd=release.std(),release_max=release.max(),release_nonzero_fraction=np.mean(release>0),due_mean=due.mean(),due_sd=due.std(),due_min=due.min(),due_max=due.max(),relative_slack_mean=slack.mean(),relative_slack_sd=slack.std(),tight_due_fraction=np.mean(slack<=0),precedence_chain_max=nm,energy_mean=en.mean(),energy_cv=en.std()/en.mean() if en.mean() else np.nan,all_modes_energy_mean=energy.mean(),energy_mode_contrast_mean=np.nanmean(contrasts),time_energy_within_operation_correlation=np.nanmean(cors),energy_fast_minus_slow_mean=np.mean(fast-slow),duration_mode_speedup_mean=np.mean(maxt/mint),cmax_lower_bound=lb,cmax_upper_bound=ub,tardiness_upper_bound=tub,energy_lower_bound=elo,energy_upper_bound=ehi,geometry_category=size(n),machine_loads=json.dumps(loads.tolist()),machine_operation_counts=json.dumps(counts.tolist()),mode_counts=json.dumps([ns]))
    pairs=[]
    if path.stem.startswith(('development_','confirmation_')) or path.stem=='base_c02_10x10_b03_tard_high':
        pairs=[(m+1,s+1,time[j,m,s],energy[j,m,s]) for j in range(nj) for m in range(nm) for s in range(ns)]
    return row,np.array([[lb,ub],[0,tub],[elo,ehi]]),pairs

def inventory():
    print('Inventory and features',flush=True)
    pres=js(EVI/'preservation_before.json'); splits={}; metas={}; names={}
    sf=ORIGINAL/'data/generated/expanded_200/experimental_split.csv'
    for r in csv.DictReader(sf.open(encoding='utf-8-sig')):splits[r['file_sha256']]=r;names[r['instance_name']]=r
    for r in csv.DictReader((ORIGINAL/'data/instance_registry.csv').open(encoding='utf-8-sig')):metas[r['instance_name']]=r
    for c in js(REC/'manifest.json')['cases']:metas[c['name']]={**c['config'],'assigned_split':c['split'],'base_id':c['name']}
    unique={};copies=[]
    for f in pres['files']:
        if not f['path'].lower().endswith('.dzn'):continue
        if f['relative'].startswith('results') and 'instances' not in Path(f['relative']).parts:continue
        p=Path(f['path']);h=f['sha256'];meta=splits.get(h,metas.get(p.stem,{})); split=meta.get('assigned_split','validation' if 'validation' in p.parts or 'invalid' in p.parts else 'historical_or_unassigned')
        copies.append({**f,'split':split})
        if h in unique:unique[h]['copies'].append(str(p));continue
        r=dict(instance=p.stem,sha256=h,path=str(p),copies=[str(p)],split=split,base_id=meta.get('base_id',p.stem),profile=meta.get('profile','unknown'),origin=f['relative'],repo=f['repo'],metadata=json.dumps(meta,ensure_ascii=False))
        if split=='holdout_test':
            # Metadata-only inventory. No held-out .dzn payload parsed for feature hypotheses.
            r.update(jobs=meta.get('dimensions','x').split('x')[0],machines=meta.get('dimensions','x').split('x')[-1],operations=meta.get('total_operations'),feature_status='reserved_metadata_only')
        else:
            try:
                feat,b,pairs=features(p);r.update(feat);r['feature_status']='parsed';BOUNDS[p.stem]=b
                if p.stem.startswith(('development_','confirmation_')) or p.stem=='base_c02_10x10_b03_tard_high':
                    MODES.extend([dict(instance=p.stem,machine=m,mode=s,duration=t,energy=e) for m,s,t,e in pairs])
            except Exception as e:r.update(feature_status='parse_error',parse_error=str(e))
        unique[h]=r
        if len(unique)%50==0:print('Unique instances inventoried:',len(unique),flush=True)
    df=pd.DataFrame(unique.values());df['copy_count']=df['copies'].map(len);df['copies']=df['copies'].map(lambda x:json.dumps(x,ensure_ascii=False))
    df.to_csv(OUT/'05_inventario_instancias.csv',index=False,encoding='utf-8-sig');save(pd.DataFrame(copies),'instance_file_copies');save(pd.DataFrame(MODES),'mode_values')
    save(df.groupby(['split','feature_status'],dropna=False).agg(n_unique=('sha256','size'),n_copies=('copy_count','sum')).reset_index(),'instance_inventory_counts')
    return df

BOUNDS={};MODES=[]; inv=inventory();FEAT=inv[inv.feature_status=='parsed'].drop_duplicates('instance').set_index('instance')

# Cohorts are never pooled. Historical phase1 variants share a base_id.
campaigns=[];rawtables=[]
def register(campaign,path,config=None,kind='standard'):
    d=pd.read_csv(path,encoding='utf-8-sig');d['source_file']=str(path);d['campaign']=campaign
    if kind=='ph':
        d=d.rename(columns={'policy':'method','runtime_seconds':'seconds','instance_name':'instance'});d['hv']=d.hv_5000;d['budget']=5000;d['base_id']=d.instance
    else:
        d=d.rename(columns={'algorithm':'method','runtime_seconds':'seconds','final_hv':'hv','hypervolume':'hv','instance_name':'instance','total_budget':'budget'})
        if 'method' not in d:d['method']=d['configuration']
        if 'base_id' not in d:d['base_id']=d.instance
    if 'budget' not in d and 'fe_used' in d:d['budget']=d.fe_used
    if 'budget' not in d:return
    if config:
        cfg=js(config);allowed={r['instance_name'] for r in cfg.get('instances',[]) if r.get('assigned_split')=='development'}
        if allowed:
            assert set(d.instance)<=allowed,'Unexpected split in '+campaign
        provenance=cfg.get('git_commit','not_recorded');date=cfg.get('date_started',cfg.get('date_executed','not_recorded'))
    else:provenance='not_recorded';date='metadata/file_times_only'
    # No held-out instance may enter performance analysis.
    forbidden=set(inv.loc[inv.split=='holdout_test','instance']);assert not set(d.instance)&forbidden
    rawtables.append(d)
    campaigns.append(dict(campaign=campaign,date=date,code_version=provenance,methods=';'.join(sorted(map(str,d.method.unique()))),FE=';'.join(map(str,sorted(d.budget.unique()))),n_instances=d.instance.nunique(),n_base_clusters=d.base_id.nunique(),seeds=';'.join(map(str,sorted(d.seed.unique()))),n_records=len(d),source=str(path),configuration=str(config),validation='schema_and_split_checked',limitations='separate cohort; commit alone does not freeze dirty source'))
    return d

print('Historical cohorts',flush=True)
phase1=register('phase1_40_profiles',ORIGINAL/'results/expanded_complementarity_phase1/phase1_runs.csv',ORIGINAL/'results/expanded_complementarity_phase1/phase1_config.json')
bench=register('technical_benchmark',ORIGINAL/'results/expanded_benchmark/benchmark_runs.csv',ORIGINAL/'results/expanded_benchmark/benchmark_config.json')
pilot=register('phase2_pilot',ROOT/'results/expanded_portfolio_phase2/pilot/pilot_runs.csv',ROOT/'results/expanded_portfolio_phase2/pilot/pilot_config.json')
budget=register('phase2_budget',ROOT/'results/expanded_portfolio_phase2/budget_diagnostic/budget_runs.csv',ROOT/'results/expanded_portfolio_phase2/budget_diagnostic/budget_config.json')
ph=register('page_hinkley_final',ORIGINAL/'results/page_hinkley_research/final_comparison/final_comparison_runs.csv',kind='ph')
cal=pd.read_csv(ORIGINAL/'results/page_hinkley_research/calibration/calibration_runs.csv');save(cal,'ph_calibration_original_values')
for name,path in [('legacy_raw','results/raw/runs.csv'),('legacy_pilot','results/experiments/pilot_runs.csv'),('legacy_f86','results/experiments/f86_runs.csv'),('legacy_f865','results/experiments/f865_runs.csv'),('legacy_f86_uniform','results/experiments/f86_uniform_runs.csv'),('legacy_c_calibration','results/diagnostics/c_calibration_105_runs.csv')]:register(name,ROOT/path)
save(pd.concat(rawtables,ignore_index=True),'historical_runs_separated')

print('Recent runs, exact offline HV/AUC audit',flush=True)
recent=[];blocks=[];alloc=[];checks=[];fronts=[];overlap=[];comp=[];runtime_threshold=[];trajectcomp=[];events=[];ucb=[];stale=[]
for split in ['development','confirmation']:
    for p in sorted((REC/'runs'/split).glob('*.json')):
        r=js(p);case=r['case'];method=r['method'];seed=r['seed']; ident=dict(campaign='loop_'+split,split=split,instance=case,base_id=case,method=method,seed=seed,budget=r['search_fe'])
        rr={**ident,**{k:r[k] for k in ['hv','auc_hv','seconds','unique_vectors','archive_size','mean_nn_distance','zero_gain_blocks']},'genetic_diversity':np.mean(list(r['genetic_diversity_final'].values())),'source_file':str(p),'operations':FEAT.loc[case,'operations']}
        rr['geometry_category']=size(rr['operations']);recent.append(rr)
        bs=r['blocks'];ys=np.array([0]+[b['hv_after'] for b in bs]);xs=np.array([0]+[b['fe'] for b in bs]);auc=float(np.sum((ys[1:]+ys[:-1])*np.diff(xs)/2)/xs[-1]);front=r['milestones']['3000']
        calc=hv([e['normalized'] for e in front]);checks.append({**ident,'hv_error':abs(calc-r['hv']),'auc_error':abs(auc-r['auc_hv']),'actual_FE':sum(b['evaluations_used'] for b in bs),'n_blocks':len(bs)})
        for e in front:fronts.append({**ident,'id':e['id'],**e['objectives'],'n_cmax':e['normalized'][0],'n_tardiness':e['normalized'][1],'n_energy':e['normalized'][2],'sequence':json.dumps(e['sequence']),'modes':json.dumps(e['modes'])})
        window=[];pulls={a:0 for a in ARMS};zeros={a:0 for a in ARMS};last={a:-1 for a in ARMS};stale_fe=0;recover=0;gaps=[]
        for b in bs:
            bi={**ident,**b};blocks.append(bi);a=b['arm_name'];reward=b['reward'];idx=b['block_index']
            if zeros[a]>=2:stale_fe+=b['evaluations_used'];recover+=reward>1e-14
            zeros[a]=zeros[a]+1 if reward<=1e-14 else 0;gaps.append(idx-last[a]-1);last[a]=idx
            if method in ['adaptive','scaled'] and b['phase']!='warmup':
                scale=max([abs(x[1]) for x in window],default=0) or 1
                for arm in ARMS:
                    ws=[v for n,v in window if n==arm];mean=np.mean(ws) if ws else np.nan;t=min(sum(pulls.values()),10);bonus=.07*np.sqrt(np.log(t)/len(ws)) if t>1 and ws else np.nan
                    ucb.append({**ident,'block_index':idx,'fe_before':b['fe']-b['evaluations_used'],'arm':arm,'window_mean':mean,'scale':scale,'exploitation':mean/scale if method=='scaled' else mean,'exploration':bonus,'selected':arm==a,'probe':any(v==0 for v in pulls.values())})
                window=(window+[(a,reward)])[-10:];pulls[a]+=1
        gaps.extend(len(bs)-v-1 for v in last.values());stale.append({**ident,'FE_after_two_own_zero_gains':stale_fe,'positive_recoveries':recover,'max_idle_blocks':max(gaps)})
        for a,n in r['allocation'].items():alloc.append({**ident,'arm':a,'FE':n,'FE_share':n/r['search_fe'],'marginal_hv_recorded':r['marginal_hv'][a],'first_observed_final':r['first_observed_final'].get(a,0),'genetic_diversity':r['genetic_diversity_final'][a]})
        for e in r['guidance_events']:events.append({**ident,**e})
        armfront={a:v for a,v in r['arm_archives'].items()};union=[e for es in armfront.values() for e in es];pts=[e['normalized'] for e in union];hvu=hv(pts);un=nd(pts)
        for a,es in armfront.items():
            others=[e for aa,v in armfront.items() if aa!=a for e in v];mc=hvu-hv([e['normalized'] for e in others]);ids={e['id'] for e in es};o_ids={e['id'] for e in others};vecs={tuple(e['normalized']) for e in es};o_vecs={tuple(e['normalized']) for e in others}
            exclusive_nd=sum(tuple(e['normalized']) in set(map(tuple,un)) and e['id'] not in o_ids for e in es)
            comp.append({**ident,'arm':a,'union_hv':hvu,'marginal_hv':mc,'recorded_marginal_error':abs(mc-r['marginal_hv'][a]),'exclusive_genotypes_in_union_nd':exclusive_nd,'shared_genotypes':len(ids&o_ids),'shared_objective_vectors':len(vecs&o_vecs),'local_archive_size':len(es)})
            for aa,ee in armfront.items():
                id2={e['id'] for e in ee};v2={tuple(e['normalized']) for e in ee}
                overlap.append({**ident,'arm1':a,'arm2':aa,'genotype_jaccard':len(ids&id2)/len(ids|id2) if ids|id2 else np.nan,'objective_jaccard':len(vecs&v2)/len(vecs|v2) if vecs|v2 else np.nan})
    sub=[r for r in recent if r['split']==split];campaigns.append(dict(campaign='loop_'+split,date='2026-10-15',code_version='1d695f3 + frozen source snapshots; baseline provenance correction',methods=';'.join(sorted(set(r['method'] for r in sub))),FE=3000,n_instances=len(set(r['instance'] for r in sub)),n_base_clusters=len(set(r['instance'] for r in sub)),seeds=';'.join(map(str,sorted(set(r['seed'] for r in sub)))),n_records=len(sub),source=str(REC/'runs'/split),configuration=str(REC/'manifest.json'),validation='offline exact HV/AUC/FE audited',limitations='one base per size/profile; internal confirmation only; guidance uses external replay'))

recent=pd.DataFrame(recent);block=pd.DataFrame(blocks);allocation=pd.DataFrame(alloc);check=pd.DataFrame(checks);com=pd.DataFrame(comp);uc=pd.DataFrame(ucb)
save(recent,'recent_runs');save(block,'recent_blocks');save(allocation,'recent_allocations');save(check,'recent_metric_checks');save(pd.DataFrame(fronts),'recent_final_fronts');save(pd.DataFrame(overlap),'archive_overlap');save(com,'recent_complementarity');save(pd.DataFrame(events),'guidance_events');save(uc,'ucb_terms');save(pd.DataFrame(stale),'stagnation');save(pd.DataFrame(campaigns),'campaign_inventory')

# Descriptive summaries respect base weighting and budget boundaries.
metrics=['hv','auc_hv','seconds','unique_vectors','archive_size','mean_nn_distance','genetic_diversity']
base=recent.groupby(['campaign','split','instance','method','budget','operations','geometry_category'])[metrics].mean().reset_index();save(base,'recent_base_means')
su=[]
for (split,m),d in base.groupby(['split','method']):
 for met in metrics:
  x=d[met].to_numpy();lo,hi=summary_ci(x);su.append(dict(split=split,method=m,metric=met,n_bases=len(x),n_runs=int(len(recent[(recent.split==split)&(recent.method==m)])),mean=x.mean(),median=np.median(x),sd=x.std(ddof=1),ci_low=lo,ci_high=hi))
save(pd.DataFrame(su),'recent_summary')
pair=[];details=[]
for split in ['development','confirmation']:
 for met in metrics:
  piv=base[base.split==split].pivot(index='instance',columns='method',values=met)
  for t,c in [('scaled','adaptive'),('guidance','adaptive'),('combined','scaled'),('combined','adaptive'),('scaled','uniform'),('adaptive','uniform'),('scaled','moead'),('guidance','moead'),('nsga2','moead'),('spea2','moead')]:
   if t not in piv or c not in piv:continue
   delta=(piv[t]-piv[c]).dropna();pair.append(dict(split=split,treatment=t,control=c,metric=met,**paired_stats(delta)))
   for i,v in delta.items():details.append(dict(split=split,instance=i,treatment=t,control=c,metric=met,delta=v))
pair=pd.DataFrame(pair);pair['p_holm_confirmatory_hv']=np.nan
mask=(pair.split=='confirmation')&(pair.metric=='hv')&(pair.control=='adaptive')&pair.treatment.isin(['scaled','guidance'])
pair.loc[mask,'p_holm_confirmatory_hv']=holm(pair[mask].copy()).p_holm
save(pair,'recent_paired_statistics');save(pd.DataFrame(details),'recent_paired_by_base')

# Historical summaries separately at each FE, seed-averaged within variant then base.
hist_summ=[];best=[]
for d in rawtables:
 if 'hv' not in d:continue
 b=d.groupby(['campaign','budget','base_id','method'],dropna=False)[['hv','seconds']].mean().reset_index()
 for (camp,fe,m),g in b.groupby(['campaign','budget','method']):
  x=g.hv.to_numpy();lo,hi=summary_ci(x);hist_summ.append(dict(campaign=camp,budget=fe,method=m,n_base_clusters=len(g),mean_hv=x.mean(),median_hv=np.median(x),sd_hv=x.std(ddof=1) if len(x)>1 else np.nan,ci_low=lo,ci_high=hi,mean_seconds=g.seconds.mean()))
save(pd.DataFrame(hist_summ),'historical_summary')

# Winners/size/features: do not pool seeds or phenotype variants as independent bases.
all_performance=pd.concat([phase1,budget,pilot,bench],ignore_index=True)
all_performance=all_performance[all_performance.method.isin(ARMS)]
all_performance['operations']=all_performance['instance'].map(FEAT.operations)
all_performance['geometry_category']=all_performance.operations.map(size)
stand_recent=recent[recent.method.isin(['moead','nsga2','spea2'])].copy();stand_recent['method']=stand_recent.method.map(dict(zip(METHODS[:3],ARMS)))
stand=pd.concat([all_performance,stand_recent],ignore_index=True)
stand=stand.groupby(['campaign','budget','base_id','instance','method','operations','geometry_category'],dropna=False).agg(mean_hv=('hv','mean'),seed_sd=('hv','std'),n_seeds=('seed','nunique')).reset_index()
save(stand,'standalone_per_instance')
for (camp,fe,ins),d in stand.groupby(['campaign','budget','instance']):
 if len(d)<3:continue
 top=d.loc[d.mean_hv.idxmax()];best.append(dict(campaign=camp,budget=fe,instance=ins,base_id=top.base_id,operations=top.operations,geometry_category=top.geometry_category,winner=top.method,n_seeds=top.n_seeds,**{r.method:r.mean_hv for _,r in d.iterrows()}))
best=pd.DataFrame(best);save(best,'best_algorithm_by_instance')
by_size=[]
for (camp,fe,cat),d in stand.groupby(['campaign','budget','geometry_category']):
 for m,g in d.groupby('method'):
  x=g.groupby('base_id').mean_hv.mean().to_numpy();lo,hi=summary_ci(x);by_size.append(dict(campaign=camp,budget=fe,size=cat,method=m,n_base_clusters=len(x),n_variants=len(g),mean_hv=x.mean(),sd_base=np.std(x,ddof=1) if len(x)>1 else np.nan,ci_low=lo,ci_high=hi))
save(pd.DataFrame(by_size),'algorithm_by_size')

cor=[];spatial=[]
features_cols=['operations','jobs_machines_ratio','machine_load_cv','relative_slack_mean','processing_cv','energy_mode_contrast_mean','release_mean','time_energy_within_operation_correlation','modes_max']
for (camp,fe),d in stand.groupby(['campaign','budget']):
 piv=d.pivot(index='instance',columns='method',values='mean_hv')
 if not set(ARMS)<=set(piv):continue
 # For phase1 feature association use only nominal base profile, n=8, not 40 variants.
 if camp=='phase1_40_profiles':piv=piv.loc[[i for i in piv.index if i in FEAT.index and str(FEAT.loc[i,'profile'])=='base']]
 for alg in ARMS[1:]:
  delta=piv[alg]-piv['MOEA/D']
  for f in features_cols:
   x=delta.index.to_series().map(FEAT[f]);valid=x.notna()&delta.notna();xx=x[valid].astype(float);yy=delta[valid]
   rho=xx.rank().corr(yy.rank()) if xx.nunique()>1 and yy.nunique()>1 else np.nan
   cor.append(dict(campaign=camp,budget=fe,contrast=alg+' - MOEA/D',feature=f,n_bases=len(xx),spearman_rho=rho,status='exploratory; no causal claim' if np.isfinite(rho) else 'constant_or_missing_feature'))
  for ins,v in delta.items():
   if ins in FEAT.index:spatial.append(dict(campaign=camp,budget=fe,instance=ins,contrast=alg+' - MOEA/D',hv_delta=v,**{f:FEAT.loc[ins,f] for f in features_cols}))
save(pd.DataFrame(cor),'exploratory_feature_correlations');save(pd.DataFrame(spatial),'feature_performance_scatter')

# Passive standalone union, budget cost explicitly 3B; phase2 raw objective fronts.
union=[];obj=[]
bf=ROOT/'results/expanded_portfolio_phase2/budget_diagnostic/budget_fronts.jsonl'
rawfront=[json.loads(line) for line in bf.open(encoding='utf-8')]
group={}
for r in rawfront:
 if r['algorithm'] in ARMS:group.setdefault((r['instance_name'],r['seed'],r['budget']),{})[r['algorithm']]=r
for (ins,seed,fe),runs in group.items():
 if len(runs)!=3 or ins not in BOUNDS:continue
 b=BOUNDS[ins];den=b[:,1]-b[:,0];den=np.where(den==0,1,den)
 pts={a:np.array(r['pareto_front'],float) for a,r in runs.items()};norm={a:(p-b[:,0])/den for a,p in pts.items()};allp=np.vstack(list(norm.values()));h=hv(allp);front=nd(allp);frontset=set(map(tuple,front));hbest=max(hv(p) for p in norm.values())
 for a,p in norm.items():
  other=np.vstack([pp for aa,pp in norm.items() if aa!=a]);s=set(map(tuple,p));o=set(map(tuple,other));union.append(dict(campaign='phase2_budget',instance=ins,seed=seed,FE_per_arm=fe,total_FE_union=3*fe,arm=a,union_hv=h,best_individual_hv=hbest,union_gain=h-hbest,marginal_hv=h-hv(other),exclusive_nd_vectors=len((s-o)&frontset),shared_nd_vectors=len(s&o&frontset),union_nd_vectors=len(front)))
  for xyz,nxyz in zip(pts[a],p):obj.append(dict(instance=ins,seed=seed,FE_per_arm=fe,total_FE_union=3*fe,arm=a,cmax=xyz[0],tardiness=xyz[1],energy=xyz[2],n_cmax=nxyz[0],n_tardiness=nxyz[1],n_energy=nxyz[2],in_union_nd=tuple(nxyz) in frontset))
save(pd.DataFrame(union),'historical_standalone_union');save(pd.DataFrame(obj),'historical_front_projections')

# Unique objective coverage per region (descriptive normalized octants within each union bounding box).
regions=[]
for (split,case,seed,m),d in pd.DataFrame(fronts).groupby(['split','instance','seed','method']):
 for a in ['n_cmax','n_tardiness','n_energy']:
  regions.append(dict(split=split,instance=case,seed=seed,method=m,objective=a,min=d[a].min(),max=d[a].max(),range=d[a].max()-d[a].min()))
save(pd.DataFrame(regions),'objective_ranges')

# Threshold time and FE right-censoring; each target is paired baseline final HV.
for split in ['development','confirmation']:
 d=recent[recent.split==split]
 for _,r in d.iterrows():
  control=d[(d.instance==r.instance)&(d.seed==r.seed)&(d.method=='adaptive')].iloc[0]
  bs=block[(block.split==split)&(block.instance==r.instance)&(block.seed==r.seed)&(block.method==r.method)]
  hit=bs[bs.hv_after>=control.hv-1e-12]
  runtime_threshold.append(dict(split=split,instance=r.instance,seed=r.seed,method=r.method,target_hv=control.hv,reached=bool(len(hit)),FE=int(hit.iloc[0].fe) if len(hit) else 3000,seconds=float(hit.iloc[0].elapsed) if len(hit) else r.seconds))
save(pd.DataFrame(runtime_threshold),'threshold_baseline_final_hv')
save(pd.DataFrame(campaigns),'campaign_inventory')
dump('analysis_audit.json',{'python':sys.version,'numpy':np.__version__,'pandas':pd.__version__,'random_seed':20261016,'bootstrap_samples':20000,'n_recent_runs':len(recent),'max_hv_error':check.hv_error.max(),'max_auc_error':check.auc_error.max(),'max_marginal_error':com.recorded_marginal_error.max(),'all_FE_3000':bool((check.actual_FE==3000).all()),'holdout_performance_rows':0,'size_definition':'empirical tertiles of 8 phase2 configuration operation counts [25,100,200,200,400,600,800,2500]; q1=200 q2=533.333; validation excluded','reserved_instance_features':'metadata only; payload unparsed','new_optimization_FE':0})
print('DONE',len(recent),'recent runs;',len(inv),'unique instances; max HV error',check.hv_error.max(),flush=True)
