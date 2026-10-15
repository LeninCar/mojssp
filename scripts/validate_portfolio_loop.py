"""Run regression suite and separately count real evaluator calls used by tests."""
import functools
import importlib.metadata
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from mojssp.evaluator import Evaluator
from run_portfolio_loop import OUT, write_new
import pytest


class SummaryPlugin:
    def pytest_sessionfinish(self, session, exitstatus):
        reporter=session.config.pluginmanager.get_plugin('terminalreporter')
        self.stats={k:len(v) for k,v in reporter.stats.items()}


def main():
    original=Evaluator.evaluate
    calls=0
    @functools.wraps(original)
    def counted(self,*args,**kwargs):
        nonlocal calls
        calls+=1
        return original(self,*args,**kwargs)
    plugin=SummaryPlugin()
    start=time.perf_counter()
    with patch.object(Evaluator,'evaluate',counted):
        result=pytest.main(['-q',str(ROOT/'tests')],plugins=[plugin])
    record={'exit_code':int(result),'seconds':time.perf_counter()-start,
            'test_report_counts':plugin.stats,'real_test_evaluator_calls_parent_process':calls,
            'scope':'Test evaluations only, excluded from experimental search budget; no results feed optimization.',
            'versions':{p:importlib.metadata.version(p) for p in ['pytest','numpy','scipy','matplotlib']}}
    write_new(OUT/'final_test_audit.json',record)
    print(json.dumps(record,indent=2))
    sys.exit(int(result))


if __name__=='__main__':
    main()
