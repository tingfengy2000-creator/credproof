from __future__ import annotations

"""Run the bounded local Qwen repair loop for a registered project.

The model runs in the existing WSL network namespace and communicates with the
trusted Windows executor through one-way JSON files on the mounted run folder.
The model never executes project code.  Candidate verification is delegated to
``check_project`` and its bubblewrap lab; only that verifier owns the verdict.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
import uuid

from .config import load_config
from .project import check_project

_WSL = ("wsl.exe", "-d", "Ubuntu-24.04", "--exec")
_RUNTIME = "/home/tingfeng/credproof-agent-runtime"

_MODEL_SCRIPT = r'''
import json, os, pathlib, shutil, subprocess, sys, time, urllib.request, uuid
from pathlib import Path
repo, artifact = map(Path, sys.argv[1:])
sys.path.insert(0, str(repo))
from agent_pilot.tools import StrictTool
from agent_pilot.model_client import LocalAgentClient
rpc_dir = artifact / 'rpc'; rpc_dir.mkdir(parents=True, exist_ok=True)
audit, state = [], {'terminal': None, 'last': None}
def rpc(name, args):
    ident = uuid.uuid4().hex; request = rpc_dir / ('request-' + ident + '.json')
    response = rpc_dir / ('response-' + ident + '.json')
    payload = {'id': ident, 'tool': name, 'arguments': args}
    tmp = request.with_suffix('.tmp'); tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8'); tmp.replace(request)
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        if response.is_file():
            value = json.loads(response.read_text(encoding='utf-8')); response.unlink(missing_ok=True)
            if isinstance(value, dict):
                state['last'] = value.get('report', state['last'])
                if name == 'verify_patch' and value.get('report', {}).get('verdict') == 'PASS': state['terminal'] = 'COMPLETED_REPAIRED'
                return value
            return {'status': 'REJECTED', 'reason': 'invalid_executor_response'}
        time.sleep(.05)
    return {'status': 'REJECTED', 'reason': 'executor_response_timeout'}
def read_code(_): return rpc('read_code', {})
def get_evidence(_): return rpc('get_evidence', {})
def submit_patch(data): return rpc('submit_patch', data)
def verify_patch(_): return rpc('verify_patch', {})
tools = [
 StrictTool('read_code', 'Read only the configured entry source.', {}, [], read_code, audit),
 StrictTool('get_evidence', 'Read redacted controlled observations.', {}, [], get_evidence, audit),
 StrictTool('submit_patch', 'Submit one bounded source candidate.', {'code': {'type':'string','maxLength':65536}}, ['code'], submit_patch, audit),
 StrictTool('verify_patch', 'Run trusted tests and observations.', {}, [], verify_patch, audit),
]
system = ('Repair the authorised Python tool using native tool calls only. Read the source and evidence, '
          'submit a minimal patch, then verify it. Preserve tests and business behaviour. Never change '
          'the contract or checks. Stop after the trusted executor reports completion.')
work = Path('/tmp/credproof-agent-model-' + str(os.getpid())); work.mkdir(parents=True, exist_ok=False)
# A fresh user/network namespace starts with loopback down. Bring up only its
# private loopback device; there is still no route to the host or Internet.
subprocess.run(['/usr/sbin/ip', 'link', 'set', 'lo', 'up'], check=True,
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
env = {'PATH':'/usr/bin:/bin:/usr/lib/wsl/lib','HOME':str(work/'home'),
 'OLLAMA_HOST':'127.0.0.1:11435','OLLAMA_MODELS':'/home/tingfeng/credproof-agent-runtime/models',
 'OLLAMA_NO_CLOUD':'1','OLLAMA_CONTEXT_LENGTH':'16384','OLLAMA_NUM_PARALLEL':'1',
 'OLLAMA_MAX_LOADED_MODELS':'1','OLLAMA_KEEP_ALIVE':'-1','OLLAMA_FLASH_ATTENTION':'1',
 'OLLAMA_KV_CACHE_TYPE':'q8_0','HTTP_PROXY':'','HTTPS_PROXY':'','ALL_PROXY':'','LANG':'C.UTF-8'}
(work/'home').mkdir(parents=True, exist_ok=True); ollama = None
def api(path):
 opener=urllib.request.build_opener(urllib.request.ProxyHandler({})); req=urllib.request.Request('http://127.0.0.1:11435'+path)
 with opener.open(req, timeout=1) as r: return r.read()
try:
 try: api('/api/version')
 except Exception:
  ollama=subprocess.Popen(['/home/tingfeng/credproof-agent-runtime/ollama/bin/ollama','serve'],env=env,cwd='/home/tingfeng/credproof-agent-runtime',stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
  for _ in range(45):
   try: api('/api/version'); break
   except Exception: time.sleep(1)
  else: raise RuntimeError('local Ollama did not start')
 started=time.monotonic()
 client=LocalAgentClient(tools=tools,system_message=system,log_dir=artifact/'model-trace',max_model_calls=12,
   request_timeout_s=120,task_budget_s=900,max_output_tokens=4096,seed=0,
   execution_completion=lambda: ({'task_status':state['terminal']} if state['terminal'] else None),max_format_corrections=1)
 model=client.run([{'role':'user','content':'Inspect the source and controlled evidence; propose and verify a safe repair.'}])
 result={'schema':'credproof.safety.agent/v2','status':'OK' if state['terminal']=='COMPLETED_REPAIRED' else 'INCOMPLETE',
  'task_status':state['terminal'] or 'INCOMPLETE','tool_trace':audit,'model':model,
  'elapsed_s':round(time.monotonic()-started,3),'model_stack':'Qwen-Agent + Ollama local qwen3-coder:30b',
  'execution_boundary':'WSL unshare network namespace + bubblewrap check_project','paid_api_used':False}
 (artifact/'model-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
finally:
 if ollama is not None:
  ollama.terminate()
  try: ollama.wait(timeout=10)
  except subprocess.TimeoutExpired: ollama.kill()
 shutil.rmtree(work,ignore_errors=True)
'''


def _wsl_path(path: Path) -> str:
    path = path.resolve()
    drive = path.drive.rstrip(":").lower()
    if not drive:
        raise ValueError(f"Only Windows paths can be mounted into WSL: {path}")
    return f"/mnt/{drive}{path.as_posix()[2:]}"


def _save(result: dict, output: str | Path | None):
    if output:
        path = Path(output).resolve()
        if path.exists():
            raise ValueError("Refuse to overwrite an existing repair report")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def _artifact_dir(output: str | Path | None) -> tuple[Path, Path | None]:
    if output:
        result = Path(output).resolve()
        if result.exists():
            raise ValueError("Refuse to overwrite an existing repair report")
        artifact = result.with_name(result.stem + '-artifacts')
        if artifact.exists():
            raise ValueError("Refuse to overwrite existing repair artifacts")
    else:
        root = Path(os.environ.get('CREDPROOF_RUNTIME_TEMP', 'E:/CredProof-local-runtime/credproof-runs'))
        root.mkdir(parents=True, exist_ok=True)
        artifact, result = root / ('agent-repair-' + uuid.uuid4().hex), None
    artifact.mkdir(parents=True, exist_ok=False)
    return artifact, result


def _write_response(path: Path, value: dict) -> None:
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    tmp.replace(path)


def _host_repair(config_path: Path, output: str | Path | None, initial: dict) -> dict:
    config = load_config(config_path)
    artifact, _ = _artifact_dir(output)
    candidate = artifact / 'candidate'
    shutil.copytree(config.project_root, candidate, symlinks=True,
                    ignore=shutil.ignore_patterns('.git', '.venv', '__pycache__', '.credproof'))
    config_rel = config_path.resolve().relative_to(config.project_root.resolve())
    candidate_config = candidate / config_rel
    module_rel = Path(config.entry.module.replace('.', '/') + '.py')
    module_file = candidate / module_rel
    if not module_file.is_file() or not config.matches_mutable(module_rel.as_posix()):
        return _save({'schema':'credproof.safety.agent/v2','status':'BLOCKED','reason':'entry_outside_mutable_scope',
                      'initial':initial,'paid_api_used':False,'artifact_dir':str(artifact)}, output)
    rpc = artifact / 'rpc'; rpc.mkdir()
    history = artifact / 'verification-history'; history.mkdir()
    stop = threading.Event(); handled: set[str] = set(); current = initial; patch_no = 0; verify_no = 0
    def serve():
        nonlocal current, patch_no, verify_no
        while not stop.is_set():
            for req in sorted(rpc.glob('request-*.json')):
                ident = req.stem.removeprefix('request-')
                if ident in handled: continue
                handled.add(ident)
                try: data=json.loads(req.read_text(encoding='utf-8')); name=data.get('tool'); args=data.get('arguments',{})
                except Exception: name,args='__invalid__',{}
                try:
                    if name == 'read_code': value={'status':'OK','path':module_rel.as_posix(),'code':module_file.read_text(encoding='utf-8')}
                    elif name == 'get_evidence':
                        execution=current.get('execution',{}); value={'status':'OK','verdict':current.get('verdict'),
                          'confirmed_failed_checks':current.get('failed_checks',[]),'forbidden_reads':execution.get('forbidden_reads',[]),
                          'requests':execution.get('requests',[]),'credential_leaks':execution.get('credential_leaks',[]),
                          'observation_summary':current.get('observation_summary',{})}
                    elif name == 'submit_patch':
                        code=args.get('code') if isinstance(args,dict) else None
                        if not isinstance(code,str) or len(code.encode())>65536: value={'status':'REJECTED','reason':'candidate_size_or_type'}
                        else:
                            patch_no += 1
                            value={'status':'ACCEPTED_FOR_VERIFICATION','candidate':patch_no}
                            module_file.write_text(code,encoding='utf-8')
                            (history / ('candidate-%02d.py' % patch_no)).write_text(code, encoding='utf-8')
                    elif name == 'verify_patch':
                        verify_no += 1
                        current=check_project(candidate_config, project_root=candidate)
                        (history / ('verification-%02d.json' % verify_no)).write_text(
                            json.dumps(current, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
                        value={'status':'OK','report':current}
                    else: value={'status':'REJECTED','reason':'unknown_tool'}
                except Exception as exc: value={'status':'REJECTED','reason':'executor_error','detail':type(exc).__name__}
                _write_response(rpc / ('response-' + ident + '.json'), value)
            time.sleep(.05)
    thread=threading.Thread(target=serve,daemon=True); thread.start()
    encoded_script = __import__('base64').b64encode(_MODEL_SCRIPT.encode()).decode()
    repo=Path(__file__).resolve().parents[1]; env={k:v for k,v in os.environ.items() if not k.startswith(('CREDPROOF_','OLLAMA_')) and not k.endswith('_API_KEY')}
    command=[*_WSL,'/usr/bin/env','CREDPROOF_RUNTIME_ROOT='+_RUNTIME,'unshare','--user','--map-root-user','--net','--fork',_RUNTIME+'/venv/bin/python','-c',
      'import base64;exec(compile(base64.b64decode('+repr(encoded_script)+'),"<credproof-agent>","exec"))',_wsl_path(repo),_wsl_path(artifact)]
    try: proc=subprocess.run(command,env=env,capture_output=True,timeout=960)
    except (OSError,subprocess.TimeoutExpired) as exc: proc=None; error={'reason':'local_wsl_model_runtime_unavailable','detail':type(exc).__name__}
    finally: stop.set(); thread.join(timeout=2)
    model_result=artifact/'model-result.json'
    if proc is not None and proc.returncode==0 and model_result.is_file():
        value=json.loads(model_result.read_text(encoding='utf-8')); value.update({'initial':initial,'final':current,'artifact_dir':str(artifact),'paid_api_used':False})
        return _save(value,output)
    if proc is not None: error={'reason':'local_model_process_failed','returncode':proc.returncode,'stderr':proc.stderr.decode('utf-8','replace')[-4000:]}
    error.update({'schema':'credproof.safety.agent/v2','status':'BLOCKED','initial':initial,'paid_api_used':False,'artifact_dir':str(artifact),
                  'execution_boundary':'WSL unshare network namespace + bubblewrap check_project'})
    return _save(error,output)


def request_repair(config_path: str | Path, *, output: str | Path | None = None) -> dict:
    config=load_config(config_path); initial=check_project(config.config_path)
    if (initial.get('verdict') != 'FAIL' or
            initial.get('observation_summary', {}).get('classification') != 'ACTUAL_VIOLATION'):
        return _save({'schema':'credproof.safety.agent/v2','status':'BLOCKED','reason':'no_current_confirmed_violation','initial':initial,'paid_api_used':False},output)
    return _host_repair(Path(config.config_path),output,initial)
