"""Run regional portfolios with the project's existing budget policies."""
import argparse
from pathlib import Path
from unittest.mock import patch

from run_weighted_pilot import ROOT,digest,write_json
from mojssp.evaluator import Evaluator
from mojssp.io import load_dzn
from mojssp.regional_portfolio import POLICY_PROFILES,SUPPORTED_ARMS,run_regional_policy_experiment


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--instance',type=Path,required=True)
    parser.add_argument('--arms',nargs='+',choices=SUPPORTED_ARMS,required=True)
    parser.add_argument('--policy',choices=POLICY_PROFILES,default='scaled')
    parser.add_argument('--guide-native-regions',action='store_true')
    parser.add_argument('--budget',type=int,default=3000)
    parser.add_argument('--population-size',type=int,default=30)
    parser.add_argument('--block-size',type=int,default=50)
    parser.add_argument('--seed',type=int,default=42)
    parser.add_argument('--minimum-share',type=float,help='Minimum share per arm in dynamic rounds; default 0.10')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    output=args.output.resolve()
    if output.exists() or not output.is_relative_to(ROOT) or output.is_relative_to(ROOT/'results/historical'):
        parser.error('Choose a new output inside the workspace, outside historical results')
    instance=load_dzn(args.instance)
    calls=0
    evaluate=Evaluator.evaluate
    def counted(self,*a,**kw):
        nonlocal calls
        calls+=1
        return evaluate(self,*a,**kw)
    with patch.object(Evaluator,'evaluate',counted):
        result=run_regional_policy_experiment(instance,args.seed,args.arms,args.policy,
            args.guide_native_regions,args.budget,args.block_size,args.population_size,
            minimum_share=args.minimum_share)
    assert calls==result['evaluations_used']==args.budget
    result.update(master_seed=args.seed,actual_evaluator_calls=calls,
        instance_sha256=digest(args.instance),source_sha256={
            str(p.relative_to(ROOT)):digest(p) for p in sorted((ROOT/'src/mojssp').glob('*.py'))})
    write_json(output,result)
    print(f"HV={result['hypervolume']:.6f}; FE={calls}; allocations={result['allocations']}")


if __name__=='__main__': main()
