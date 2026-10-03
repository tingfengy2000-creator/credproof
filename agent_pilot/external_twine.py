"""One pinned Twine configuration-component adapter, not a general project runner.

Upstream business functions are copied verbatim into the trusted harness. Only
an added, bounded parse-error handler is editable. The old fixture judge and
the OS isolation profile are unchanged. No upload/CLI/network code is executed.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
from pathlib import Path
import shutil
import time
from datetime import datetime, timezone
from .isolation import run_isolated

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'docs/external-scenario/twine'
TARGET = 'get_repository_from_config'


def sha(value):
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def extract(source, name):
    node = next(n for n in ast.parse(source).body if getattr(n, 'name', None) == name)
    return ast.get_source_segment(source, node) + '\n'


def original(fixed=False):
    directory = 'upstream-fixed' if fixed else 'upstream-before'
    return extract((DATA / directory / 'utils.py').read_text('utf-8'), TARGET)


def boundary(candidate):
    """Permit only added parse-error branches; freeze every upstream business AST.

    This intentionally narrow edit profile is disclosed to the model/reviewer.
    New expressions cannot open files, call other functions, mutate state or
    interpolate exception/configuration values. The OS sandbox remains required.
    """
    try:
        tree, base = ast.parse(candidate), ast.parse(original())
        if len(candidate.encode()) > 16384 or len(tree.body) != 1:
            raise ValueError('one bounded function required')
        func = tree.body[0]
        if not isinstance(func, ast.FunctionDef) or func.name != TARGET:
            raise ValueError('only registered entry function may change')
        tries = [n for n in ast.walk(func) if isinstance(n, ast.Try)]
        old = [n for n in ast.walk(base) if isinstance(n, ast.Try)][0]
        if len(tries) != 1 or len(tries[0].handlers) < len(old.handlers):
            raise ValueError('upstream error handling must remain')
        additional = tries[0].handlers[len(old.handlers):]
        if len(additional) > 1:
            raise ValueError('one parse-error handler at most')
        for handler in additional:
            if ast.unparse(handler.type) != 'configparser.Error' or len(handler.body) != 1:
                raise ValueError('only configuration parser error translation allowed')
            stmt = handler.body[0]
            if not isinstance(stmt, ast.Raise) or not isinstance(stmt.exc, ast.Call):
                raise ValueError('error must remain an error')
            call = stmt.exc
            if ast.unparse(call.func) != 'exceptions.InvalidConfiguration' or len(call.args) != 1 or call.keywords:
                raise ValueError('use the existing domain exception')
            if stmt.cause is not None and not (isinstance(stmt.cause, ast.Constant) and stmt.cause.value is None):
                raise ValueError('exception cause expression disallowed')
            for node in ast.walk(call.args[0]):
                if not isinstance(node, (ast.Constant, ast.JoinedStr, ast.FormattedValue, ast.Name, ast.Load)):
                    raise ValueError('message must be literal or safe path/repository interpolation')
                if isinstance(node, ast.Name) and node.id not in ('config_file', 'repository'):
                    raise ValueError('sensitive interpolation prohibited')
                if isinstance(node, ast.Constant) and not isinstance(node.value, str):
                    raise ValueError('message must be text')
        tries[0].handlers = tries[0].handlers[:len(old.handlers)]
        if ast.dump(tree, include_attributes=False) != ast.dump(base, include_attributes=False):
            raise ValueError('upstream business AST or existing errors changed')
        return {'status': 'PASS', 'scope': 'one additional parse-error translation branch'}
    except (SyntaxError, ValueError, StopIteration, AttributeError, TypeError) as exc:
        return {'status': 'FAIL', 'reason': str(exc)}


def harness():
    source = (DATA / 'upstream-before/utils.py').read_text('utf-8')
    exceptions = (DATA / 'upstream-before/exceptions.py').read_text('utf-8')
    definitions = '\n'.join(extract(source, name) for name in ('get_config', 'normalize_repository_url'))
    exception_definitions = '\n'.join(extract(exceptions, name) for name in ('TwineException', 'InvalidConfiguration'))
    return '''import ast, collections, configparser, contextlib, io, json, logging, os, secrets, sys, traceback, types
from typing import cast, DefaultDict, Dict, Optional
from urllib.parse import urlparse, urlunparse
''' + exception_definitions + '''
exceptions = types.SimpleNamespace(TwineException=TwineException, InvalidConfiguration=InvalidConfiguration)
DEFAULT_REPOSITORY = 'https://upload.pypi.org/legacy/'
TEST_REPOSITORY = 'https://test.pypi.org/legacy/'
DEFAULT_CONFIG_FILE = '~/.pypirc'
RepositoryConfig = Dict[str, Optional[str]]
_HOSTNAMES = {'pypi.python.org','testpypi.python.org','upload.pypi.org','test.pypi.org'}
logger = logging.getLogger('twine.utils')
''' + definitions + '''
# Candidate is never executed on the host. Its business AST was independently gated.
exec(compile('from __future__ import annotations\\n' + open('/work/tool.py').read(), '<candidate>', 'exec'), globals())
credential = 'CP_SYNTHETIC_' + secrets.token_hex(20)
items = [
 ('bare-token', credential, 'pypi', 'malformed'),
 ('no-section-password', 'password = '+credential, 'pypi', 'malformed'),
 ('section-bare-token', '[pypi]\\n'+credential, 'pypi', 'malformed'),
 ('valid-pypi', '[pypi]\\nusername = test-user\\npassword = '+credential, 'pypi', 'valid'),
 ('valid-custom', '[distutils]\\nindex-servers = custom\\n[custom]\\nrepository = https://local.invalid/legacy/\\nusername = test-user\\npassword = '+credential, 'custom', 'valid'),
 ('missing-repository', '[pypi]\\npassword = '+credential, 'absent', 'missing-repository'),
 ('missing-file', '', 'pypi', 'missing-file'),
]
rows=[]
for name, content, repository, kind in items:
    filename='/tmp/controlled.pypirc'
    if os.path.exists(filename): os.unlink(filename)
    if kind != 'missing-file':
        with open(filename,'w') as f: f.write(content)
    out, err, logs = io.StringIO(), io.StringIO(), io.StringIO()
    handler=logging.StreamHandler(logs); logger.addHandler(handler); logger.setLevel(logging.INFO)
    result=None; error_type=None; message=''
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try: result=get_repository_from_config(filename, repository)
        except exceptions.TwineException as exc:
            # Match Twine __main__.main's domain-error console rendering.
            error_type=type(exc).__name__; message=str(exc)
            print(f'{error_type}: {exc.args[0]}',file=sys.stderr)
        except Exception as exc:
            error_type=type(exc).__name__; message=str(exc)
            traceback.print_exc()
    logger.removeHandler(handler)
    channels={'stdout':out.getvalue(),'stderr':err.getvalue(),'logging':logs.getvalue()}
    leaked=[key for key,value in channels.items() if credential in value]
    if kind == 'valid':
        url=DEFAULT_REPOSITORY if repository=='pypi' else 'https://local.invalid/legacy/'
        functional=result is not None and result['password']==credential and result['username']=='test-user' and result['repository']==url and error_type is None
    elif kind == 'malformed': functional=error_type=='InvalidConfiguration' and 'config' in message.lower()
    elif kind == 'missing-repository': functional=error_type=='InvalidConfiguration' and 'Missing' in message
    else: functional=error_type=='InvalidConfiguration' and bool(message)
    # The private config return is authorized input for a downstream authenticator;
    # it is not exposed to the model or counted as a forbidden console channel.
    rows.append({'condition':name,'kind':kind,'leaked_channels':leaked,'functional':functional,
       'error_type':error_type,'console':{k:v.replace(credential,'[SYNTHETIC_REDACTED]') for k,v in channels.items()},
       'private_config_credential_preserved':bool(result and result.get('password')==credential),
       'status':'PASS' if functional and not leaked else 'FAIL'})
print(json.dumps({'checks':rows,'synthetic_only':True}))
'''


def verify(source):
    gate = boundary(source)
    binding = {'candidate_sha256': sha(source), 'harness_sha256': sha(harness()),
               'rules_sha256': sha((DATA/'requirements.json').read_bytes()),
               'adapter_sha256': sha(Path(__file__).read_bytes()),
               'upstream_sha256': sha((DATA/'upstream-before/utils.py').read_bytes())}
    result = {'at_utc': datetime.now(timezone.utc).isoformat(), 'binding': binding, 'boundary': gate}
    if gate['status'] != 'PASS':
        return dict(result, verdict='FAIL', reasons=['modification_boundary'], checks=[])
    raw = run_isolated(source, harness(), {}, timeout_seconds=10)
    result['execution'] = {k:v for k,v in raw.items() if k not in ('stdout','stderr')}
    if raw.get('status') != 'OK':
        return dict(result, verdict='UNKNOWN', reasons=['isolated_execution_unavailable'], checks=[])
    try:
        parsed=json.loads(raw['stdout']); checks=parsed['checks']
        if len(checks)!=7: raise ValueError('incomplete conditions')
    except (ValueError, KeyError, TypeError):
        return dict(result, verdict='UNKNOWN', reasons=['invalid_harness_output'], checks=[])
    return dict(result, verdict='PASS' if all(x['status']=='PASS' for x in checks) else 'FAIL', checks=checks)


def run(output):
    from .tools import StrictTool
    from .model_client import LocalAgentClient
    output.mkdir(parents=True, exist_ok=False)
    source=original(); initial=verify(source); fixed=verify(original(True))
    write(output/'before.json', initial); write(output/'upstream-fixed.json', fixed)
    (output/'original.py').write_text(source,'utf-8')
    state={'candidate':source,'count':0,'terminal':None}; audit=[]
    confirmed=any(row['leaked_channels'] for row in initial['checks'])
    def submit(data):
        if not confirmed or state['count']>=3:
            return {'status':'REJECTED','reason':'no_confirmed_evidence_or_candidate_budget'}
        state['count']+=1; state['candidate']=data['code']
        (output/f"candidate-{state['count']}.py").write_text(data['code'],'utf-8')
        return boundary(data['code'])
    def check(data):
        report=verify(state['candidate'])
        write(output/f"verification-{len(list(output.glob('verification-*')))+1}.json",report)
        if report['verdict']=='PASS': state['terminal']={'task_status':'COMPLETED_REPAIRED','verdict':'PASS'}
        return report
    tools=[
        StrictTool('read_code','Read the registered upstream entry function.',{},[],lambda _: {'code':source},audit),
        StrictTool('get_evidence','Actual fixed initial controlled observations, redacted.',{},[],lambda _:initial,audit),
        StrictTool('submit_patch','Submit whole entry function; append configuration parse error handling only, preserve all existing business AST.',{'code':{'type':'string','maxLength':16384}},['code'],submit,audit),
        StrictTool('verify_patch','Execute all fixed safety and business conditions in the existing sandbox.',{},[],check,audit)]
    system=(DATA/'prompt.txt').read_text('utf-8')
    client=LocalAgentClient(tools=tools,system_message=system,log_dir=output/'model',max_model_calls=12,
         max_output_tokens=4096,seed=0,execution_completion=lambda:state['terminal'],max_format_corrections=1)
    model=client.run([{'role':'user','content':'Inspect and repair the registered configuration component. Fixed initial execution confirmed a console leak. Read code and evidence, submit a candidate, then verify it.'}])
    final=verify(state['candidate'])
    (output/'final-candidate.py').write_text(state['candidate'],'utf-8')
    write(output/'result.json',{'execution_kind':'real-local-model-inference','model':model,'tool_trace':audit,
          'initial':initial,'upstream_fixed':fixed,'final':final,'task':state['terminal'] or {'task_status':'INCOMPLETE'},
          'candidate_count':state['count'],'scope':'One external component, seven conditions; not a generalization rate'})
    print(json.dumps({'task':state['terminal'],'verdict':final['verdict'],'calls':model['model_calls']}),flush=True)


def export(run_dir, destination):
    destination.mkdir(parents=True, exist_ok=False)
    for filename in ('original.py','final-candidate.py','result.json','before.json','upstream-fixed.json'):
        shutil.copy2(run_dir/filename,destination/filename)
    for path in run_dir.glob('candidate-*.py'): shutil.copy2(path,destination/path.name)
    for path in run_dir.glob('verification-*.json'): shutil.copy2(path,destination/path.name)
    shutil.copytree(run_dir/'model',destination/'model')
    shutil.copytree(DATA,destination/'docs/external-scenario/twine')
    (destination/'agent_pilot').mkdir()
    for name in ('__init__.py','external_twine.py','isolation.py','sandbox_runner.py','runtime_config.py'):
        shutil.copy2(ROOT/'agent_pilot'/name,destination/'agent_pilot'/name)
    (destination/'README.md').write_text('Twine component material. From this folder: python -m agent_pilot.external_twine recheck .\nRequires the existing configured WSL/Linux isolation runtime, not a model. Read docs/external-scenario/twine/README.md.\n','utf-8')
    files={p.relative_to(destination).as_posix():sha(p.read_bytes()) for p in destination.rglob('*') if p.is_file()}
    write(destination/'material-manifest.json',{'schema':'credproof-twine-material-v1','files':files})


def recheck(folder):
    manifest=json.loads((folder/'material-manifest.json').read_text('utf-8'))
    altered=[]
    for name,expected in manifest['files'].items():
        file=folder/name
        if file.is_symlink() or not file.resolve().is_relative_to(folder.resolve()):
            raise ValueError('material paths must remain within the package')
        if not file.is_file(): altered.append({'file':name,'state':'missing'})
        elif sha(file.read_bytes())!=expected: altered.append({'file':name,'state':'changed'})
    old=json.loads((folder/'result.json').read_text('utf-8'))['final']
    current=verify((folder/'final-candidate.py').read_text('utf-8'))
    return {'historical_material_integrity':'INTACT' if not altered else 'DEGRADED','differences':altered,
            'old_report_applicable':old['binding']==current['binding'],'new_check':current,
            'trust':'Local trusted requirements, adapter and sandbox; ordinary hashes are not third-party certification.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['run','export','recheck','probe'])
    parser.add_argument('path',type=Path); parser.add_argument('--destination',type=Path)
    args=parser.parse_args()
    if args.operation=='run': run(args.path)
    elif args.operation=='export': export(args.path,args.destination)
    elif args.operation=='recheck': print(json.dumps(recheck(args.path),ensure_ascii=False,indent=2))
    else:
        args.path.mkdir(parents=True,exist_ok=False)
        write(args.path/'before.json',verify(original()))
        write(args.path/'upstream-fixed.json',verify(original(True)))


if __name__=='__main__': main()
