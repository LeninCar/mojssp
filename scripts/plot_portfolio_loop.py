"""Static scientific figures from saved runs; per-base means, no seed pseudoreplication."""
from collections import defaultdict
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from mojssp.project_paths import HISTORICAL_ROOT, campaign_path
OUT=campaign_path('portfolio')
LABELS={'moead':'MOEA/D','nsga2':'NSGA-II','spea2':'SPEA2','uniform':'Uniforme',
        'adaptive':'SW-UCB original','guidance':'Padre externo (replay)',
        'scaled':'UCB escalado','combined':'UCB escalado + padre externo'}
COLORS={'moead':'#4477aa','nsga2':'#ee7733','spea2':'#aa3377','uniform':'#999999',
        'adaptive':'#222222','guidance':'#228833','scaled':'#cc3311','combined':'#66ccee'}


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error('output directory already exists; choose a new directory')
    if args.output_dir.resolve().is_relative_to(HISTORICAL_ROOT):
        parser.error('output must be outside the saved campaign')
    args.output_dir.mkdir(parents=True)
    fig,axes=plt.subplots(1,2,figsize=(12,5.2))
    allruns=[]
    for ax,split in zip(axes,['development','confirmation']):
        runs=[json.loads(p.read_text(encoding='utf-8')) for p in (OUT/'runs'/split).glob('*.json')
              if not p.name.endswith('.failed.json')]
        allruns.extend(runs)
        by=defaultdict(lambda:defaultdict(list))
        for r in runs:
            by[r['method']][r['case']].append([0.]+[b['hv_after'] for b in r['blocks']])
        minima=[]
        maxima=[]
        for method,cases in sorted(by.items()):
            values=np.array([np.mean(v,axis=0) for v in cases.values()])
            x=np.arange(61)*50
            mean=values.mean(axis=0)
            minima.append(mean[3:].min()); maxima.append(mean[3:].max())
            ax.plot(x,mean,label=LABELS.get(method,method),lw=1.5,color=COLORS[method],
                    ls='--' if method in ['moead','nsga2','spea2'] else (':' if method=='uniform' else '-'))
        ax.set(title=f'{split}: promedio de {len(next(iter(by.values())))} bases',xlabel='Evaluaciones reales',ylabel='HV normalizado')
        ax.set_xlim(150,3000)
        ax.set_ylim(min(minima)-.01,max(maxima)+.01)
        ax.grid(alpha=.2)
    handles,labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,labels,fontsize=8,loc='lower center',ncol=4)
    fig.suptitle('Después de 150 FE; AUC calculada desde (0, 0)',fontsize=10)
    fig.tight_layout(rect=(0,.13,1,.94))
    fig.savefig(args.output_dir/'trajectories.png',dpi=170)
    plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4.8))
    for ax,split in zip(axes,['development','confirmation']):
        by=defaultdict(list)
        for r in allruns:
            if r['split']==split and len(r['allocation'])==3:
                by[r['method']].append(r)
        methods=sorted(by)
        bottom=np.zeros(len(methods))
        for name in ['MOEA/D','NSGA-II','SPEA2']:
            shares=[np.mean([r['allocation'][name]/3000 for r in by[m]]) for m in methods]
            ax.bar(np.arange(len(methods)),shares,bottom=bottom,label=name)
            bottom+=shares
        ax.set_xticks(np.arange(len(methods)),[LABELS.get(m,m) for m in methods],rotation=20,ha='right',fontsize=8)
        ax.set(title=split,ylabel='Fracción de FE',ylim=(0,1))
    axes[1].legend(loc='upper right',fontsize=8)
    fig.tight_layout()
    fig.savefig(args.output_dir/'allocation.png',dpi=170)
    plt.close(fig)


if __name__=='__main__':
    main()
