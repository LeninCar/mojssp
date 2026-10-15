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
OUT=ROOT/'results/portfolio_loop_20261015'
LABELS={'moead':'MOEA/D','nsga2':'NSGA-II','spea2':'SPEA2','uniform':'Uniforme',
        'adaptive':'SW-UCB original','guidance':'Padre externo (replay)',
        'scaled':'UCB escalado','combined':'UCB escalado + padre externo'}


def main():
    fig,axes=plt.subplots(1,2,figsize=(12,4.5))
    allruns=[]
    for ax,split in zip(axes,['development','confirmation']):
        runs=[json.loads(p.read_text(encoding='utf-8')) for p in (OUT/'runs'/split).glob('*.json')
              if not p.name.endswith('.failed.json')]
        allruns.extend(runs)
        by=defaultdict(lambda:defaultdict(list))
        for r in runs:
            by[r['method']][r['case']].append([0.]+[b['hv_after'] for b in r['blocks']])
        for method,cases in sorted(by.items()):
            values=np.array([np.mean(v,axis=0) for v in cases.values()])
            x=np.arange(61)*50
            ax.plot(x,values.mean(axis=0),label=LABELS.get(method,method),lw=1.5)
        ax.set(title=f'{split}: promedio de bases',xlabel='Evaluaciones reales',ylabel='HV normalizado')
        ax.set_xlim(0,3000)
        ax.grid(alpha=.2)
    axes[1].legend(fontsize=8,loc='lower right')
    fig.tight_layout()
    fig.savefig(OUT/'trajectories.png',dpi=170)
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
    fig.savefig(OUT/'allocation.png',dpi=170)
    plt.close(fig)


if __name__=='__main__':
    main()
