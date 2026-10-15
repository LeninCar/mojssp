"""Additional statistics using already installed SciPy (absent from bundled Python).
Reads processed data, plus domain objects for independent feature spot checks.
No algorithms are instantiated or executed.
"""
from pathlib import Path
import sys,json,itertools,math
import numpy as np,pandas as pd
from scipy.stats import wilcoxon,friedmanchisquare,rankdata
OUT=Path(__file__).resolve().parents[1];ROOT=OUT.parents[1];T=OUT/'tables';sys.dont_write_bytecode=True;sys.path.insert(0,str(ROOT/'src'))
from mojssp.io import load_dzn
from mojssp.normalization import compute_instance_bounds
RNG=np.random.default_rng(20261016)
def save(d,n):d.to_csv(T/(n+'.csv'),index=False,encoding='utf-8-sig')
def read(n):return pd.read_csv(T/(n+'.csv'))
def stat(v):
 v=np.asarray(v,float);n=len(v);per=np.array(list(itertools.product([-1,1],repeat=n)));p=np.mean(np.abs((per*v).mean(axis=1))>=abs(v.mean())-1e-12);boot=RNG.choice(v,(20000,n)).mean(axis=1);nz=v[abs(v)>1e-12];r=rankdata(abs(nz));rb=(sum(r[nz>0])-sum(r[nz<0]))/sum(r) if len(nz) else 0.
 ww=wilcoxon(v) if len(nz) else None
 return dict(n_base_clusters=n,mean_delta=v.mean(),median_delta=np.median(v),sd_delta=v.std(ddof=1),ci_low=np.quantile(boot,.025),ci_high=np.quantile(boot,.975),p_signflip=p,p_wilcoxon=ww.pvalue if ww else 1.,rank_biserial=rb,wins=sum(v>1e-12),ties=sum(abs(v)<=1e-12),losses=sum(v< -1e-12))
def holm(d,col='p_signflip'):
 if len(d)==0:return d
 o=np.argsort(d[col].to_numpy());a=np.empty(len(d));prev=0
 for j,i in enumerate(o):prev=max(prev,min(1,d.iloc[i][col]*(len(d)-j)));a[i]=prev
 d['p_holm']=a;return d
hist=read('historical_runs_separated');recent=read('recent_runs');post=[];globaltests=[]
for camp in ['phase1_40_profiles','phase2_pilot','phase2_budget','page_hinkley_final']:
 d=hist[hist.campaign==camp]
 for fe,dd in d.groupby('budget'):
  # Equal profile weight within independent base; seeds averaged first by group means.
  b=dd.groupby(['base_id','method']).hv.mean().unstack().dropna()
  if b.shape[1]>=3:
   r=friedmanchisquare(*[b[c] for c in b]);globaltests.append(dict(campaign=camp,budget=fe,n_base_clusters=len(b),n_methods=len(b.columns),friedman_stat=r.statistic,p_asymptotic=r.pvalue,scope='exploratory; small sample chi-square approximation'))
  rows=[]
  for m,c in itertools.combinations(b.columns,2):rows.append(dict(campaign=camp,budget=fe,treatment=m,control=c,**stat(b[m]-b[c])))
  if rows:post.append(holm(pd.DataFrame(rows)))
for split in ['development','confirmation']:
 dd=recent[recent.split==split];b=dd.groupby(['base_id','method']).hv.mean().unstack().dropna();r=friedmanchisquare(*[b[c] for c in b]);globaltests.append(dict(campaign='loop_'+split,budget=3000,n_base_clusters=len(b),n_methods=len(b.columns),friedman_stat=r.statistic,p_asymptotic=r.pvalue,scope='exploratory omnibus; primary family stays separate'))
 rows=[]
 for m,c in itertools.combinations(b.columns,2):rows.append(dict(campaign='loop_'+split,budget=3000,treatment=m,control=c,**stat(b[m]-b[c])))
 post.append(holm(pd.DataFrame(rows)))
save(pd.concat(post,ignore_index=True),'exploratory_all_pairwise');save(pd.DataFrame(globaltests),'omnibus_tests')

# Paired generator perturbations: effect on algorithm-vs-MOEA/D contrast,
# rather than pretending absolute normalized HV is comparable between instances.
d=hist[hist.campaign=='phase1_40_profiles'];p=d.groupby(['base_id','profile','method']).hv.mean().unstack('method');effects=[];detail=[]
for profile in ['tard_med','tard_high','nrg_strong','btnk_high']:
 for arm in ['NSGA-II','SPEA2']:
  a=(p[arm]-p['MOEA/D']).unstack('profile');v=(a[profile]-a['base']).dropna();effects.append(dict(profile=profile,contrast=arm+' - MOEA/D',**stat(v)))
  for base,value in v.items():detail.append(dict(profile=profile,contrast=arm+' - MOEA/D',base_id=base,delta_relative_advantage=value))
save(holm(pd.DataFrame(effects)),'profile_relative_effects');save(pd.DataFrame(detail),'profile_relative_effects_by_base')

# Source, budget and duplicated-quality audits.
ph=hist[hist.campaign=='page_hinkley_final'];cal=read('ph_calibration_original_values');q=ph[ph.method=='dmab_ph'].merge(cal[cal.config_id=='C5'],left_on=['instance','seed'],right_on=['instance_name','seed'],suffixes=('_final','_calibration'))
pilot=hist[hist.campaign=='phase2_pilot'];budget=hist[(hist.campaign=='phase2_budget')&(hist.budget==1000)];q2=pilot.merge(budget,on=['instance','method','seed'],suffixes=('_pilot','_budget'))
cross={'PH_C5_rows_reused_or_identical':len(q),'PH_C5_max_HV_difference':float(abs(q.hv-q.hv_5000_calibration).max()),'pilot_vs_budget_1000_pairs':len(q2),'pilot_vs_budget_1000_max_HV_difference':float(abs(q2.hv_pilot-q2.hv_budget).max()),'no_optimization_executed':True}
(OUT/'evidence'/'cross_campaign_audit.json').write_text(json.dumps(cross,indent=2),encoding='utf-8')

inv=pd.read_csv(OUT/'05_inventario_instancias.csv');parsed=inv[inv.feature_status=='parsed'];selection=parsed[parsed.instance.str.startswith(('confirmation_','development_'))];selection=pd.concat([selection,parsed[parsed.instance.str.startswith('base_c')].head(5),parsed.sort_values('operations').tail(2)]).drop_duplicates('sha256');checks=[]
for _,row in selection.iterrows():
 ins=load_dzn(row.path);ops=ins.all_operations;dur=np.array([np.mean([m.duration for m in op.modes]) for op in ops]);loads=np.array([sum(p for op,p in zip(ops,dur) if op.machine_id==m) for m in range(1,ins.num_machines+1)]);bound=compute_instance_bounds(ins)
 values=dict(operations=ins.total_operations,processing_mean=dur.mean(),processing_cv=dur.std()/dur.mean(),machine_load_cv=loads.std()/loads.mean(),machine_load_max_mean=loads.max()/loads.mean(),cmax_lower_bound=bound.cmax_min,cmax_upper_bound=bound.cmax_max,energy_lower_bound=bound.energy_min,energy_upper_bound=bound.energy_max,tardiness_upper_bound=bound.tardiness_max)
 for k,v in values.items():checks.append(dict(instance=row.instance,metric=k,inventory_value=float(row[k]),domain_reader_value=v,absolute_error=abs(v-float(row[k]))))
save(pd.DataFrame(checks),'independent_feature_checks')
print('Additional statistics and independent feature audit completed.',cross)
