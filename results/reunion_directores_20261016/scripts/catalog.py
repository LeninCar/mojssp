"""Enrich campaign metadata and preserve a file-level historical evidence index."""
from pathlib import Path
import csv,json
import pandas as pd
O=Path(__file__).resolve().parents[1];T=O/'tables';ROOT=O.parents[1];P=ROOT.parent/'mojssp-dmab'
c=pd.read_csv(T/'campaign_inventory.csv');cal=pd.read_csv(T/'ph_calibration_original_values.csv')
if 'page_hinkley_calibration' not in set(c.campaign):
 c=pd.concat([c,pd.DataFrame([dict(campaign='page_hinkley_calibration',date='October 2026; exact runtime date not recorded',code_version='experiment/page-hinkley-dmab; loaded source snapshot absent',methods=';'.join(cal.config_id.unique()),FE='5000',n_instances=cal.instance_name.nunique(),n_base_clusters=cal.instance_name.nunique(),seeds=';'.join(map(str,sorted(cal.seed.unique()))),n_records=len(cal),source=str(P/'results/page_hinkley_research/calibration/calibration_runs.csv'),configuration='delta .0001/.0005/.001 x lambda .01/.02/.05; c .07; block 50; pop 30',validation='raw data and calibration/final reuse checked',limitations='exploratory tuning; same development bases as final comparison; C5 reused')])],ignore_index=True)
c['n_seeds']=c.seeds.astype(str).map(lambda x:len(x.split(';')))
c['n_continuous_trajectories']=c.n_records;c.loc[c.campaign=='phase2_budget','n_continuous_trajectories']=150
c['metrics_available']='HV final; FE; runtime; archive metrics where recorded; see artifact catalog'
c.loc[c.campaign.str.startswith('loop_'),'metrics_available']='HV; AUC-HV; FE; time; objective ranges/NN; archive/unique vectors; genetic diversity recorded; marginal HV; allocation; blocks; genotype/objective archives; guidance events'
c.loc[c.campaign=='phase2_budget','metrics_available']='HV at 1000/3000/5000; per-block HV; FE; time; archive/unique vectors; objective fronts; allocation; offline canonical marginal HV'
c.loc[c.campaign.str.startswith('page_hinkley'),'metrics_available']='HV init/1000/3000/5000; FE; time; archive; alarms; reexploration; arm FE/rewards/blocks'
c['portfolio_configuration']='See source/configuration; do not assume equality between campaigns'
c.loc[c.campaign.isin(['phase2_pilot','phase2_budget']),'portfolio_configuration']='MOEA/D, NSGA-II, SPEA2; pop30; block50; W10;c.07; RR or SW-UCB; historical seed hash'
c.loc[c.campaign.str.startswith('loop_'),'portfolio_configuration']='MOEA/D, NSGA-II, SPEA2; pop30; block50; W10;c.07; seeds s/s+1/s+2; guidance every10 crossovers; scale only in scaled/combined'
c.loc[c.campaign.str.startswith('page_hinkley'),'portfolio_configuration']='MOEA/D, NSGA-II, SPEA2; pop30; block50; UCB1 c.07; PH C5 delta.0005 lambda.020 or SW-UCB W10'
c['code_validation_status']='Recorded commit/report does not prove loaded working-tree state'
c.loc[c.campaign.str.startswith('loop_'),'code_validation_status']='Frozen source trees; baseline loaded-source correction; historical prior reproduction; hashes checked in final verifier'
c.to_csv(T/'campaign_inventory.csv',index=False,encoding='utf-8-sig')

dis=json.loads((O/'evidence/discovery.json').read_text(encoding='utf-8'));rows=[]
for r in dis:
 if r['repo']!='mojssp-loop-agent' and not any(s in r['path'] for s in ['page_hinkley','expanded_benchmark','expanded_complementarity']):continue
 rows.append(dict(repository=r['repo'],path=r['path'],bytes=r['bytes'],columns_or_keys=';'.join(r.get('columns') or r.get('keys') or []),role='report' if r['path'].endswith('.md') else 'data_or_metadata',validation='indexed only; authoritative vs derived must be checked per campaign'))
pd.DataFrame(rows).to_csv(T/'historical_artifact_catalog.csv',index=False,encoding='utf-8-sig')

# Population and temporal diagnostics derived from preserved blocks, with explicit units.
b=pd.read_csv(T/'recent_blocks.csv');b['stage']=pd.cut(b.fe,[0,1000,2000,3000],labels=['early_0_1000','middle_1000_2000','late_2000_3000'],include_lowest=True)
ag=b.groupby(['split','instance','seed','method','stage','arm_name'],observed=True).agg(FE=('evaluations_used','sum'),selections=('block_index','size'),reward_sum=('reward','sum'),positive_blocks=('reward',lambda x:(x>1e-14).sum()),zero_blocks=('reward',lambda x:(x<=1e-14).sum())).reset_index();ag['HV_gain_per_FE']=ag.reward_sum/ag.FE
ag.to_csv(T/'allocation_by_stage.csv',index=False,encoding='utf-8-sig')

# AUC historical is recalculated from continuous checkpoint traces, separately for each budget.
cp=pd.read_csv(ROOT/'results/expanded_portfolio_phase2/budget_diagnostic/budget_checkpoints.csv');rows=[]
for (run,ins,alg,seed),g in cp.groupby(['run_id','instance_name','algorithm','seed']):
 for fe in [1000,3000,5000]:
  d=g[g.evaluations_used<=fe].sort_values('evaluations_used');xs=[0]+d.evaluations_used.tolist();ys=[0]+d.hypervolume.tolist()
  area=sum((xs[i]-xs[i-1])*(ys[i]+ys[i-1])/2 for i in range(1,len(xs)))/fe
  rows.append(dict(campaign='phase2_budget',run_id=run,instance=ins,algorithm=alg,seed=seed,budget=fe,auc_hv=area,n_checkpoints=len(d),source_file=str(ROOT/'results/expanded_portfolio_phase2/budget_diagnostic/budget_checkpoints.csv')))
pd.DataFrame(rows).to_csv(T/'historical_auc_recomputed.csv',index=False,encoding='utf-8-sig')
print('Campaign and historical artifact inventory enriched;',len(rows),'historical AUC milestones.')
