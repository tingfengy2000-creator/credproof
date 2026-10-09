"""Freeze and execute one registered bounded_patch task; never auto retry."""
import hashlib
import json
import platform
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
dest=Path(sys.argv[1]).resolve();dest.mkdir(parents=True,exist_ok=False)
paths=['credproof_safety/agent.py','credproof_safety/cli.py','agent_pilot/bounded_patch.py',
       'agent_pilot/model_client.py','agent_pilot/requirements-lock.txt','pyproject.toml',
       'examples/material_assistant/credproof.toml','examples/material_assistant/tool.py',
       'examples/material_assistant/tests/test_business.py']
freeze={'registered_at':datetime.now(timezone.utc).isoformat(),
        'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'task':'assistant-original/p01','strategy':'bounded_patch','model':'qwen3-coder:30b',
        'python':platform.python_version(), 'retry':False,
        'budgets':{'generations':3,'requests_including_format_correction':4,'format_corrections':1,
                   'candidates':3,'program_verifications':3,'context':16384,'output_tokens':2048,
                   'input_upper_limit':13824,'request_seconds':120,'task_seconds':900},
        'files':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in paths},
        'command':['.venv/Scripts/python.exe','-m','credproof_safety','repair','--strategy','bounded_patch',
                   '--config','examples/material_assistant/credproof.toml','--output',dest.relative_to(ROOT).as_posix()+'/result.json'],
        'scope':'5090 existing model/candidate isolation; no 5060; fixed rules; no reference patch'}
(dest/'freeze.json').write_text(json.dumps(freeze,indent=2)+'\n',encoding='utf8')
with (dest/'stdout.txt').open('wb') as out,(dest/'stderr.txt').open('wb') as err:
    p=subprocess.run([sys.executable,*freeze['command'][1:]],cwd=ROOT,stdout=out,stderr=err,timeout=1000)
(dest/'command-receipt.json').write_text(json.dumps({'exit_code':p.returncode,'ended_at':datetime.now(timezone.utc).isoformat(),'tasks':1},indent=2)+'\n',encoding='utf8')
print('source='+freeze['source_commit']+' exit='+str(p.returncode))
raise SystemExit(p.returncode)
