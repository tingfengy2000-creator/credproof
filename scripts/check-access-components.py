"""Real independent component checks in the existing WSL/bubblewrap lab. No model."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from credproof_safety.runner import run_sandbox
from credproof_safety.project import check_project

dest = Path(sys.argv[1]).resolve()
dest.mkdir(parents=True, exist_ok=False)
project = dest/'project'; project.mkdir()
lab = dest/'lab'
(lab/'documents').mkdir(parents=True); (lab/'private').mkdir()
(lab/'documents'/'brief.txt').write_text('independent component material\n', encoding='utf8')
credential = 'CP_LAB_' + uuid.uuid4().hex.upper()
(lab/'private'/'secret.txt').write_text(credential, encoding='utf8')
# WSL creates only this one controlled relative link, no user directory mounts.
runtime_target = '/mnt/' + str(lab.drive[0]).lower() + lab.as_posix()[2:] + '/documents/link.txt'
proc = subprocess.run(['wsl.exe', '-d', 'Ubuntu-24.04', '--exec', 'ln', '-s', '../private/secret.txt', runtime_target], capture_output=True)
if proc.returncode: raise RuntimeError('controlled symlink preparation failed')
(project/'entry.py').write_text('def run(request):\n    return {"ok": True}\n',encoding='utf8')
# Deliberate same-name project shadow must never supply the component.
(project/'credproof_access.py').write_text('raise RuntimeError("project shadow imported")\n',encoding='utf8')
(project/'test_component.py').write_text('''import os
from pathlib import Path
import pytest
from urllib.error import HTTPError
import credproof_access as access

def test_normal_absolute_and_relative_file():
    path = Path(os.environ['CREDPROOF_ALLOWED_FILE'])
    assert access.read_text(str(path)) == 'independent component material\\n'
    assert access.read_text(os.path.relpath(path)) == 'independent component material\\n'

@pytest.mark.parametrize('kind', ['absolute','traversal','symlink','prefix','cwd'])
def test_denied_paths(kind):
    allowed = Path(os.environ['CREDPROOF_ALLOWED_ROOT'])
    forbidden = Path(os.environ['CREDPROOF_FORBIDDEN_FILE'])
    values = {'absolute':str(forbidden), 'traversal':str(allowed/'..'/'private'/'secret.txt'),
              'symlink':str(allowed/'link.txt'), 'prefix':str(allowed)+'-shadow/x',
              'cwd':'../private/secret.txt'}
    before = Path.cwd()
    try:
        if kind == 'cwd': os.chdir(allowed)
        with pytest.raises(ValueError): access.read_text(values[kind])
    finally: os.chdir(before)

def test_allowed_authentication():
    value = access.get_json(os.environ['CREDPROOF_ALLOWED_URL'], os.environ['COMPONENT_TEST_SECRET'])
    assert value == {'ok': True, 'service':'allow'}

@pytest.mark.parametrize('kind', ['forbidden','wrong_port','prefix'])
def test_denied_initial_url(kind):
    from urllib.parse import urlsplit, urlunsplit
    allowed = urlsplit(os.environ['CREDPROOF_ALLOWED_URL'])
    urls = {'forbidden':os.environ['CREDPROOF_FORBIDDEN_URL'],
            'wrong_port':urlunsplit(allowed._replace(netloc='127.0.0.1:1')),
            'prefix':os.environ['CREDPROOF_ALLOWED_URL']+'-shadow'}
    with pytest.raises(ValueError): access.get_json(urls[kind], os.environ['COMPONENT_TEST_SECRET'])

def test_allowed_initial_redirect_is_sent_then_refused():
    with pytest.raises(HTTPError) as raised:
        access.get_json(os.environ['CREDPROOF_REDIRECT_URL'], os.environ['COMPONENT_TEST_SECRET'])
    assert raised.value.code == 302

def test_policy_fixed_and_module_not_project_shadow():
    assert access.__file__ == '/tmp/credproof-trusted/credproof_access/__init__.py'
    with pytest.raises(RuntimeError): access._install_policy({})
''', encoding='utf8')
result = run_sandbox(project, lab, ['-q','-s','test_component.py'], 'entry','run',{},credential,
                     allowed_dirs=('documents',), forbidden_dirs=('private',),
                     service_path_prefix='/api', credential_env='COMPONENT_TEST_SECRET', timeout=45)
from credproof_safety.project import _redact_execution
public = _redact_execution(result, credential)
(dest/'component-execution.json').write_text(json.dumps(public,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
requests = public.get('requests', [])
checks = {
    'real_pytest_completed': public.get('pytest_exit_code') == 0 and public.get('pytest_observation',{}).get('required_tests_passed') is True,
    'real_allowed_auth': any(x['service']=='allow' and x['path']=='/api' and x['credential_ok'] for x in requests),
    'real_initial_redirect': any(x['service']=='allow' and x['path']=='/api/redirect' and x['credential_ok'] for x in requests),
    'no_forbidden_receipt': not any(x['service']=='forbidden' for x in requests),
    'no_forbidden_read_attempt': not public.get('forbidden_reads'),
    'no_credential_output': not public.get('credential_leaks'),
    'trusted_import': public.get('access_component',{}).get('import_path') == '/tmp/credproof-trusted/credproof_access/__init__.py'}
original = check_project(ROOT/'examples/material_assistant/credproof.toml',output=dest/'unchanged-original-report.json')
checks['component_install_alone_does_not_repair_original'] = original['verdict']=='FAIL'
summary = {'kind':'NO_MODEL_COMPONENT_AND_UNCHANGED_ORIGINAL_CONTROL','model_requests':0,
           'checks':checks,'pass':all(checks.values()), 'original_verdict':original['verdict'],
           'pytest': public.get('pytest_observation'), 'requests':requests,
           'command':[sys.executable, *sys.argv], 'component':public.get('access_component'),
           'runtime_contract':public.get('runtime_contract')}
(dest/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({'pass':summary['pass'],'checks':checks},indent=2))
raise SystemExit(0 if summary['pass'] else 1)
