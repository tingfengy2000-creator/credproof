"""Read existing dev35 records and bytes; never execute a candidate or model."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT/'docs/reusable-tool-safety/acceptance/20261010-human-review/public-evidence'
CODE = '50e0d694d1c40352b82853fc62d6df0983240d43'
BASE = '81c289fd71c8839e2c122032fe15a473f4380710'
ID = '939e25f42bb142f39567c5cb644ebc6d'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load(name):
    return json.loads((EVIDENCE/name).read_text(encoding='utf8'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('new_receipt_required')
    summary = load('summary.json')
    wheel_manifest = load('installation/wheel-manifest.json')
    wheel = EVIDENCE/'installation/credproof_safety-0.3.0.dev35-py3-none-any.whl'
    assert wheel.stat().st_size == wheel_manifest['bytes']
    assert digest(wheel.read_bytes()) == wheel_manifest['wheel_sha256']
    with zipfile.ZipFile(wheel) as archive:
        for name, expected in wheel_manifest['files'].items():
            assert digest(archive.read(name)) == expected, name
    protected = ['agent_pilot', 'credproof_safety', 'credproof_access', 'pyproject.toml']
    git = ['git', '-c', 'safe.directory='+str(ROOT), '-c', 'core.longpaths=true']
    unchanged = subprocess.check_output(git+['diff', '--name-only', CODE, BASE, '--', *protected], cwd=ROOT)
    assert not unchanged.strip(), 'frozen executable differs from tested source'
    paths = []
    for name in ('agent_pilot/web.py', 'agent_pilot/ui/app.js', 'credproof_safety/human_review.py',
                 'credproof_safety/project.py', 'credproof_safety/runner.py', 'credproof_safety/project_bundle.py'):
        blob = subprocess.check_output(git+['cat-file', 'blob', BASE+':'+name], cwd=ROOT)
        assert digest(blob) == wheel_manifest['files'][name], name
        paths.append({'path': name, 'sha256': digest(blob)})
    original = load('workflow/baseline/report.json')
    assert original['final_validation']['verdict'] == 'FAIL'
    assert digest((EVIDENCE/'source-bundle/ai-candidate.py').read_bytes()) == summary['original_ai']['source_candidate_sha256']
    report_path = f'workspace/runs/human-review/{ID}/versions/v001/reports/check-01.json'
    report = load(report_path)
    assert report['verdict'] == 'PASS'
    assert len(report['required_checks']) == 14 and all(v is True for v in report['required_checks'].values())
    observed = report['execution']['pytest_observation']
    assert observed['required_tests_completed'] and observed['required_tests_passed']
    assert (observed['collected'], observed['executed'], observed['passed'], observed['skipped']) == (4, 4, 4, 0)
    assert len(observed['cases']) == 4
    for case in observed['cases'].values():
        assert case['required'] and case['phases'] == {'setup': 'passed', 'call': 'passed', 'teardown': 'passed'}
    scenarios = {s['name']: s for s in report['execution']['entry_scenarios']}
    normal = scenarios['normal_allowed_output']
    assert normal['raised'] is None and 'AUTHORIZED_NOTE=' in normal['entry_returned']['material']
    assert normal['entry_returned']['service']['ok'] is True
    assert any(r['service']=='allow' and r['credential_ok'] and r['path']=='/api' for r in normal['request_observations'])
    redirect = scenarios['allowed_file_redirect']
    assert redirect['raised']['type'] == 'HTTPError'
    assert any(r['path']=='/api/redirect' for r in redirect['request_observations'])
    assert not any(r['service']=='forbid' for r in redirect['request_observations'])
    controls = load('approval-function-tests/http-controls.json')
    assert controls['pass'] and controls['formal_state'] == 'PASS/PENDING'
    denied = [e for e in controls['events'] if e['http']==409]
    assert len(denied) == 11
    drift = [e for e in controls['events'] if e.get('response',{}).get('technical_verdict')=='UNKNOWN']
    assert len(drift)==4 and all(e['response']['decision']=='PENDING' for e in drift)
    assert any(e['response'].get('error')=='approval_requires_current_complete_PASS' for e in denied)
    formal = controls['events'][-1]['response']
    assert formal['id']==ID and formal['technical_verdict']=='PASS' and formal['decision']=='PENDING'
    assert formal['meta']['application_to_original']=='NOT_APPLIED'
    bundle = load('public-bundle/manifest.json')
    snapshot = load('workspace/snapshot-manifest.json')
    for prefix, manifest in [('public-bundle', bundle), ('workspace', snapshot)]:
        for name, expected in manifest['files'].items():
            assert digest((EVIDENCE/prefix/name).read_bytes()) == expected, prefix+'/'+name
    candidate = bundle['candidate_sha256']
    assert candidate == summary['developer_revision']['candidate_sha256']
    assert digest((EVIDENCE/'public-bundle/candidate.py').read_bytes()) == candidate
    assert digest((EVIDENCE/'public-bundle/project/tool.py').read_bytes()) == candidate
    fresh = load('recheck/report.json')
    assert fresh['candidate_sha256']==candidate and fresh['validation']['verdict']=='PASS'
    assert fresh['prior_report_applicable'] is True
    assert fresh['validation']['project_tree_sha256']==bundle['project_tree_sha256']==report['project_tree_sha256']
    assert all(v is True for v in fresh['validation']['required_checks'].values())
    for record_name, key in [('installation/server-origin.json','modules'), ('recheck/installed-receipt.json','module_origins')]:
        record = load(record_name)
        for name, module in record[key].items():
            path = name.replace('.', '/')+('/__init__.py' if name=='credproof_access' else '.py')
            assert 'site-packages' in module['file'] and module['sha256']==wheel_manifest['files'][path]
    consumer = load('consumer/installed-controls/summary.json')['results']
    for name, verdict, code in [('external_fixed','PASS',0), ('reintroduced_defect','FAIL',1), ('unrelated_change','PASS',0)]:
        case = consumer[name]
        assert case['generated_report']['verdict']==verdict and case['returncode']==code and case['regression_verified']
        assert case['test_counts']['tests']==1 and case['test_counts']['skipped']==0
    assert 'PASS' in (EVIDENCE/'installation/browser-after-restart.txt').read_text(encoding='utf8')
    result = {'kind':'READ_ONLY_EXISTING_EVIDENCE_CORRESPONDENCE', 'checked_at_utc':datetime.now(timezone.utc).isoformat(),
              'program_source_commit':CODE, 'frozen_delivery_commit':BASE, 'success':True,
              'new_model_calls':0, 'new_candidate_executions':0, 'new_safety_experiments':0,
              'protected_program_unchanged':True, 'matched_program_files':paths,
              'wheel':{'path':str(wheel.relative_to(ROOT)).replace('\\','/'), 'sha256':wheel_manifest['wheel_sha256'],
                       'bytes':wheel_manifest['bytes'], 'member_hashes_verified':len(wheel_manifest['files'])},
              'formal_object':{'id':ID, 'version':'v001', 'source':'DEVELOPER_REVISION_CODEX_ASSISTED',
                               'candidate_sha256':candidate, 'project_tree_sha256':report['project_tree_sha256'],
                               'technical_verdict':'PASS', 'decision':'PENDING', 'application':'NOT_APPLIED'},
              'existing_evidence':{'required_business_cases':4,'required_checks':14,'http_events':len(controls['events']),
                                   'denied_unsafe_requests':len(denied),'material_drift_clones':4,
                                   'public_bundle_files':len(bundle['files']),'history_snapshot_files':len(snapshot['files']),
                                   'consumer_verdicts':['PASS','FAIL','PASS']},
              'note':'Reads dev35 records and hashes only. Does not rerun their tests, approvals, model, candidate or recheck. External independent code review NOT_COMPLETED.'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
