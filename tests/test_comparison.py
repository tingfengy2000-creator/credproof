import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('comparison_generator',ROOT/'scripts/compare/build_comparison.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def test_frozen_counts_and_method_coverage_are_preserved():
    data=json.loads(m.INPUT.read_text('utf8'));out=m.build(data,'test-digest')
    assert out['denominators']['total']==88
    assert [(x['id'],x['denominators']['total']) for x in out['batches']]==[('ai',51),('anchors',16),('history',21)]
    assert out['denominators']['unknown']==1
    for batch in out['batches']:
        source=data['summary'][batch['id']]
        for method in batch['methods']:
            if method['id']=='credproof':continue
            key='static_credential_rules' if method['id']=='static' else method['id']
            for field in ['accepted_unsafe','rejected_good']:
                assert method[field]==source['methods'][key][field]
            if key.startswith('judge:'):assert method['invalid']==source['methods'][key]['invalid']
    history=out['batches'][2]
    assert all(x['missing']==21 and x['coverage']['rows']==0 for x in history['methods'] if x['id'].startswith('judge:'))
    ids={x['id'] for x in data['patches']}
    assert all(x['example_patch_id'] in ids for x in out['methods'])

def test_invalid_not_silently_removed_from_good_denominator():
    rows=[{'id':'sample','credproof':{'verdict':'PASS'},'judges':{'model':{'verdict':'INVALID'}}}]
    result=m.metrics(rows,'judge:model')
    assert result['coverage']['good']==1 and result['rejected_good']==1
    assert result['invalid']==1 and result['explicit_rejected_good']==0

def test_check_is_offline_and_rejects_stale_output(tmp_path):
    script=tmp_path/'scripts/compare/build_comparison.py';script.parent.mkdir(parents=True)
    shutil.copyfile(ROOT/'scripts/compare/build_comparison.py',script)
    src=tmp_path/'docs/bench/bench-results.json';src.parent.mkdir(parents=True);shutil.copyfile(m.INPUT,src)
    def run(*args):return subprocess.run([sys.executable,str(script),*args],cwd=tmp_path,capture_output=True)
    assert run().returncode==0
    assert run('--check').returncode==0
    output=tmp_path/'docs/compare/comparison.json';output.write_text('{}\n',encoding='utf8')
    assert run('--check').returncode!=0
