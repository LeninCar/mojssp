"""Read-only source inventory; all writes confined to this meeting directory."""
from pathlib import Path
import hashlib,json,subprocess,datetime,sys
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parents[1]
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def git(p,*args):
    r=subprocess.run(['git','-C',str(p),*args],capture_output=True,encoding='utf-8',errors='replace')
    return {'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr}
def main():
    dest=OUT/'evidence'/'preservation_before.json'
    if dest.exists(): raise SystemExit('Preservation already captured; do not overwrite')
    repos=[]; files=[]
    for name in ['mojssp-loop-agent','mojssp-dmab','mojssp-dmab - copia','mojssp-pareto-cooperation']:
        p=ROOT.parent/name
        if not p.exists(): continue
        repos.append({'path':str(p),'branch':git(p,'branch','--show-current'),'head':git(p,'rev-parse','HEAD'),
          'status':git(p,'status','--porcelain=v1','--untracked-files=all'),'worktrees':git(p,'worktree','list','--porcelain')})
        # Hash without interpreting any held-out objective/results payload.
        for folder in ['src','scripts','tests','data','results']:
            d=p/folder
            if not d.exists():continue
            for f in sorted(d.rglob('*')):
                if not f.is_file() or OUT in f.parents or '__pycache__' in f.parts:continue
                s=f.stat()
                files.append({'path':str(f),'relative':str(f.relative_to(p)),'repo':name,'bytes':s.st_size,
                  'mtime_utc':datetime.datetime.fromtimestamp(s.st_mtime,datetime.timezone.utc).isoformat(),'sha256':sha(f)})
    data={'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'python':sys.version,
       'root':str(ROOT),'repositories':repos,'files':files,'policy':'Hashes read bytes only. Reserved test result payloads not parsed.'}
    dest.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'repositories':[{k:r[k] for k in ['path','branch','head']} for r in repos],'files_hashed':len(files),'evidence':str(dest)},ensure_ascii=False))
if __name__=='__main__': main()
