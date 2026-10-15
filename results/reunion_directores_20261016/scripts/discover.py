from pathlib import Path
import csv,json
ROOT=Path(__file__).resolve().parents[3]; OUT=Path(__file__).resolve().parents[1]
records=[]
for repo in ['mojssp-loop-agent','mojssp-dmab','mojssp-dmab - copia','mojssp-pareto-cooperation']:
 p=ROOT.parent/repo
 for f in sorted((p/'results').rglob('*')):
  if not f.is_file() or OUT in f.parents or any(x in str(f).lower() for x in ['holdout','test_final']):continue
  if f.suffix.lower() not in ['.csv','.json','.jsonl','.md']:continue
  if 'runs' in f.parts or 'code' in f.parts:continue
  if f.suffix=='.md' and not any(x in f.name for x in ['report','closure','audit','protocol','decision','specification']):continue
  r={'repo':repo,'path':str(f.relative_to(p)),'bytes':f.stat().st_size}
  if f.suffix=='.csv':
   with f.open(encoding='utf-8-sig',newline='') as stream:
    reader=csv.DictReader(stream);r['columns']=reader.fieldnames;r['sample']=next(reader,None)
  elif f.suffix=='.json' and f.stat().st_size<1500000:
   try:
    d=json.loads(f.read_text(encoding='utf-8-sig'));r['keys']=list(d)[:30] if isinstance(d,dict) else ['list',len(d)]
   except Exception as e:r['error']=str(e)
  elif f.suffix=='.jsonl':
   with f.open(encoding='utf-8') as stream:
    d=json.loads(next(stream));r['keys']=list(d) if isinstance(d,dict) else ['list'];r['sample_header']={k:v for k,v in d.items() if not isinstance(v,(list,dict))}
  records.append(r)
(OUT/'evidence'/'discovery.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
for r in records:
 if r['repo']=='mojssp-loop-agent' and ('runs.csv' in r['path'] or 'fronts.jsonl' in r['path']) or r['repo']=='mojssp-dmab' and any(t in r['path'] for t in ['benchmark_runs','phase1_runs','comparison_runs','calibration_runs']):print(json.dumps(r,ensure_ascii=False))
