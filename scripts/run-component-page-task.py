"""One registered task through installed HTTP page -> supervisor -> bounded_patch.

Requires a prepared new data workspace and installed interpreter. Never retries.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser()
ap.add_argument('--python',type=Path,required=True)
ap.add_argument('--workspace',type=Path,required=True)
ap.add_argument('--output',type=Path,required=True)
args=ap.parse_args()
args.output.mkdir(parents=True,exist_ok=False)
def save(name,value):
    (args.output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
paths=[*list((ROOT/'credproof_safety').glob('*.py')), *list((ROOT/'credproof_access').glob('*.py')),
       ROOT/'agent_pilot/bounded_patch.py',ROOT/'agent_pilot/web.py',ROOT/'agent_pilot/ui/app.js',ROOT/'pyproject.toml',
       *list((args.workspace/'examples/material_assistant').rglob('*.py')),args.workspace/'examples/material_assistant/credproof.toml']
save('freeze.json',{'registered_at':datetime.now(timezone.utc).isoformat(),'source_commit':source,
     'task':'assistant-original/p01','strategy':'bounded_patch','profile':'component_assisted',
     'model':'qwen3-coder:30b','model_digest':'06c1097efce0431c2045fe7b2e5108366e43bee1b4603a7aded8f21689e90bca',
     'budget':{'generations':3,'requests':4,'format_corrections':1,'candidates':3,'program_verifications':3,
               'context':16384,'output':2048,'input_limit':13824,'request_seconds':120,'task_seconds':900},
     'files':{str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else 'data/'+p.relative_to(args.workspace).as_posix():sha(p) for p in paths},
     'program_python':str(args.python),'workspace':str(args.workspace),
     'independent_task':True,'restart_after_failure':False,'reference_patch_provided':False})
with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
env=dict(os.environ);env.pop('PYTHONPATH',None);env.pop('PYTHONHOME',None)
env['CREDPROOF_INSTALLED_PYTHON']=str(args.python)
command=[str(args.python),'-I','-m','agent_pilot.launch','--workspace',str(args.workspace),'--mode','live','--port',str(port)]
save('page-command.json',{'argv':command,'cwd':str(args.output),'kind':'NEW_REAL_PAGE_MODEL_TASK'})
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def request(path,body=None,raw=False):
    req=urllib.request.Request(f'http://127.0.0.1:{port}'+path,
          data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
    with opener.open(req,timeout=180) as response:data=response.read()
    return data if raw else json.loads(data)
process=None
try:
    with (args.output/'page-stdout.txt').open('wb') as stdout,(args.output/'page-stderr.txt').open('wb') as stderr:
        process=subprocess.Popen(command,cwd=args.output,env=env,stdout=stdout,stderr=stderr,stdin=subprocess.DEVNULL)
        for attempt in range(30):
            if process.poll() is not None:raise RuntimeError('installed_page_start_failed')
            try:
                bootstrap=request('/api/agent/bootstrap');break
            except Exception:time.sleep(1)
        else:raise RuntimeError('page_bootstrap_unavailable')
        save('bootstrap.json',bootstrap)
        if not bootstrap['runtime']['ready']:raise RuntimeError('page_preflight_blocked')
        page=request('/',raw=True);save('page-read.json',{'bytes':len(page),'contains_workbench':b'task-identity' in page})
        start=request('/api/agent/runs',{'case_id':'p01'});save('page-start.json',start)
        identifier=start['id'];began=time.monotonic()
        while time.monotonic()-began<1000:
            result=request('/api/agent/runs/'+identifier)
            if result['status'] not in ('QUEUED','RUNNING'):break
            time.sleep(2)
        else:raise RuntimeError('page_task_wait_exceeded; do not retry task')
        save('page-final.json',result)
        if result['validation']['verdict']=='PASS':
            archive=request('/api/agent/runs/'+identifier+'/export',raw=True)
            (args.output/'page-export.zip').write_bytes(archive)
            save('page-export-receipt.json',{'bytes':len(archive),'sha256':hashlib.sha256(archive).hexdigest()})
            recheck=request('/api/agent/runs/'+identifier+'/recheck',{})
            save('page-recheck.json',recheck)
        save('command-receipt.json',{'completed':True,'task_count':1,'status':result['status'],
              'task_status':result['task_status'],'verdict':result['validation']['verdict'],
              'run_id':identifier,'elapsed_s':time.monotonic()-began})
finally:
    if process is not None and process.poll() is None:
        process.terminate();process.wait(timeout=15)
