"""One-time read-only cutoff of additional P5/P6 and live P7 evidence.
Does not start, stop, modify or wait for any external experiment.
"""
from pathlib import Path
import json,hashlib,datetime,io
import pandas as pd,numpy as np
O=Path(__file__).resolve().parents[1];ROOT=O.parents[1];P=ROOT.parent/'mojssp-pareto-cooperation';T=O/'tables';E=O/'evidence';S=E/'additional_campaign_snapshot';S.mkdir(exist_ok=True)
if (E/'additional_campaign_cutoff.json').exists():raise SystemExit('Cutoff already exists; do not refresh a live cohort silently')
pres=json.loads((E/'preservation_before.json').read_text(encoding='utf-8'));old={x['path']:x for x in pres['files']};records=[]
paths=[P/'results/pareto_cooperation_research'/s for s in ['p5_selector_sensitivity/sensitivity_summary.csv','p6_pilot/p6_pilot_summary.csv','p6_pilot/p6_causal_audit_summary.csv','p7_validation/p7_validation_summary.csv','p7_validation/p7_validation_blocks_detail.csv','p7_validation_design.md','p6_cooperation_design.md','p6_implementation_validation.md']]+[P/'scripts/run_p7_validation.py',P/'src/mojssp/cooperation.py']
copied={}
for p in paths:
 if not p.exists():continue
 data=p.read_bytes();h=hashlib.sha256(data).hexdigest();after=hashlib.sha256(p.read_bytes()).hexdigest();dest=S/p.relative_to(P);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data);copied[p.name]=dest
 records.append(dict(source=str(p),snapshot=str(dest.relative_to(O)).replace('\\','/'),bytes=len(data),sha256=h,stable_during_capture=h==after,present_at_initial_inventory=str(p) in old,unchanged_from_initial=old.get(str(p),{}).get('sha256')==h))
cut={'cutoff_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'policy':'Do not update this snapshot during the same audit. P7 remains a separate partial exploratory cohort. No experiment started by this analysis.','files':records}
(E/'additional_campaign_cutoff.json').write_text(json.dumps(cut,ensure_ascii=False,indent=2),encoding='utf-8')
p5=pd.read_csv(copied['sensitivity_summary.csv']);p6=pd.read_csv(copied['p6_pilot_summary.csv']);p6fixed=pd.read_csv(copied['p6_causal_audit_summary.csv']);p7=pd.read_csv(copied['p7_validation_summary.csv'])
split=pd.read_csv(ROOT.parent/'mojssp-dmab/data/generated/expanded_200/experimental_split.csv');allowed=set(split.loc[(split.assigned_split=='development')&(split.profile=='base'),'instance_name']);assert set(p7.instance_name)<=allowed
for d in [p5,p6,p6fixed,p7]:assert (d.total_fe==1000).all()
for d,name in [(p5,'p5_selector_sensitivity'),(p6,'p6_injection_pilot'),(p6fixed,'p6_injection_fixed_control'),(p7,'p7_partial_snapshot')]:d.to_csv(T/(name+'.csv'),index=False,encoding='utf-8-sig')
expected=['MOEAD_Standalone','NSGA2_Standalone','SPEA2_Standalone','Portfolio_RoundRobin_Passive','Portfolio_SWUCB_Passive','Portfolio_SWUCB_Cooperative','Portfolio_Coop_FixedSequence'];seeds=[42,101,202,303,404];complete=[]
for ins,d in p7.groupby('instance_name'):
 if all(len(d[(d.seed==s)&(d.condition==m)])==1 for s in seeds for m in expected):complete.append(ins)
balanced=p7[p7.instance_name.isin(complete)];base=balanced.groupby(['instance_name','condition'])[['final_hv','auc_hv','runtime_seconds','total_injections_accepted']].mean().reset_index();base.to_csv(T/'p7_partial_complete_base_means.csv',index=False,encoding='utf-8-sig')
summ=base.groupby('condition').agg(n_complete_bases=('instance_name','nunique'),mean_hv=('final_hv','mean'),mean_auc=('auc_hv','mean'),mean_seconds=('runtime_seconds','mean')).reset_index();summ.to_csv(T/'p7_partial_descriptive.csv',index=False,encoding='utf-8-sig')
cut.update(observed_p7_rows=len(p7),expected_p7_rows=350,n_observed_bases=p7.instance_name.nunique(),complete_bases=complete,n_complete_bases=len(complete),included_balanced_rows=len(balanced),all_stable_during_capture=all(r['stable_during_capture'] for r in records))
(E/'additional_campaign_cutoff.json').write_text(json.dumps(cut,ensure_ascii=False,indent=2),encoding='utf-8')
c=pd.read_csv(T/'campaign_inventory.csv');new=[]
for camp,d,source,methods,ns in [('p5_c_sensitivity',p5,copied['sensitivity_summary.csv'],';'.join(p5.policy_name.unique()),1),('p6_injection_pilot',p6,copied['p6_pilot_summary.csv'],';'.join(p6.condition.unique()),1),('p6_fixed_control',p6fixed,copied['p6_causal_audit_summary.csv'],'Cooperative_FixedSequence_Control',1),('p7_partial_external',p7,copied['p7_validation_summary.csv'],';'.join(p7.condition.unique()),5)]:
 new.append(dict(campaign=camp,date=cut['cutoff_utc'],code_version='Sibling checkout 1d695f3 + P6 working tree; snapshot of current source, loaded-state not certified',methods=methods,FE=1000,n_instances=d.instance_name.nunique(),n_base_clusters=d.instance_name.nunique(),seeds='42' if ns==1 else ';'.join(map(str,seeds)),n_seeds=ns,n_records=len(d),n_continuous_trajectories=len(d),source=str(source),configuration='c=.01 P6/P7; injection kappa2 from block6; P5 c=.01/.03/.07/RR',portfolio_configuration='Bounded evaluated-incumbent injection; different from external-parent guidance',metrics_available='HV; AUC; runtime; FE; archive; accepted injections; provenance-labelled volume (not canonical arm-removal MC)',validation='snapshot; development split/FE checked; '+('incomplete ongoing external campaign' if camp.startswith('p7') else 'small exploratory pilot'),limitations='Do not pool with recent 3000 FE; no independent final test; snapshot is a cutoff',code_validation_status='Current source snapshot, not fingerprint of every loaded execution'))
pd.concat([c,pd.DataFrame(new)],ignore_index=True).to_csv(T/'campaign_inventory.csv',index=False,encoding='utf-8-sig')
print({k:cut[k] for k in ['cutoff_utc','observed_p7_rows','n_observed_bases','n_complete_bases','all_stable_during_capture']})
