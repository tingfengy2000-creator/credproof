"""One non-project structured response in the unchanged model boundary. No retries."""
import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from credproof_safety.agent import _bounded_model_script, _MODEL_BOUNDARY_BOOTSTRAP, _runtime_settings, _wsl_path
from agent_pilot.model_config import claim_comparison, finish_comparison, selected_profile

ap = argparse.ArgumentParser()
ap.add_argument('--output', type=Path, required=True)
args = ap.parse_args()
args.output.mkdir(parents=True, exist_ok=False)
claim = claim_comparison('preflight')
prefix = _bounded_model_script().split(' started=time.monotonic()')[0]
tail = r'''
 opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
 payload={'model':selected_profile()['name'],'stream':False,
  'format':{'type':'object','properties':{'ok':{'type':'boolean'}},'required':['ok'],'additionalProperties':False},
  'messages':[{'role':'user','content':'Return a JSON object with ok=true.'}],
  'options':{'num_ctx':16384,'num_predict':2048,'temperature':0,'seed':0}}
 from agent_pilot.model_client import estimate_input_budget
 budget=estimate_input_budget(payload,2048)
 (artifact/'request.json').write_text(json.dumps(payload,indent=2)+'\n')
 (artifact/'input-budget.json').write_text(json.dumps(budget,indent=2)+'\n')
 if not budget['within_context_budget'] or not budget['within_wire_limit']: raise RuntimeError('preflight_input_budget')
 req=urllib.request.Request('http://127.0.0.1:11435/api/chat',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
 start=time.monotonic()
 with opener.open(req,timeout=120) as response: result=json.loads(response.read(2097152))
 (artifact/'response.json').write_text(json.dumps(result,indent=2)+'\n')
 if result.get('done') is not True or json.loads(result['message']['content'])!={'ok':True}: raise RuntimeError('structured_preflight_failed')
 req=urllib.request.Request('http://127.0.0.1:11435/api/show',data=json.dumps({'model':selected_profile()['name']}).encode(),headers={'Content-Type':'application/json'})
 with opener.open(req,timeout=10) as response: show=json.loads(response.read())
 (artifact/'model-show.json').write_text(json.dumps(show,indent=2)+'\n')
 receipt={'kind':'ONE_NON_PROJECT_STRUCTURED_PREFLIGHT','elapsed_s':time.monotonic()-start,'model':selected_profile(),
  'version':json.loads(api('/api/version')),'active_models':json.loads(api('/api/ps')),'model_calls':1,'project_code_provided':False}
 (artifact/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
finally:
 if ollama is not None:
  ollama.terminate()
  try: ollama.wait(timeout=10)
  except subprocess.TimeoutExpired: ollama.kill()
  ollama_stdout.close(); ollama_stderr.close()
 shutil.rmtree(work,ignore_errors=True)
'''
stage = args.output / 'model-stage'
(stage / 'agent_pilot').mkdir(parents=True)
import agent_pilot
installed = Path(agent_pilot.__file__).parent
for name in ('__init__.py', 'tools.py', 'model_client.py', 'model_config.py', 'bounded_patch.py'):
    (stage / 'agent_pilot' / name).write_bytes((installed / name).read_bytes())
(stage / 'worker.py').write_text(prefix + tail, encoding='utf8')
(stage / 'initial-context.json').write_text('{"_generation_strategy":"bounded_patch"}', encoding='utf8')
(stage / 'model-profile.json').write_text(json.dumps(selected_profile()), encoding='utf8')
sentinel = args.output / 'host-sentinel.txt'
sentinel.write_text('synthetic boundary sentinel', encoding='utf8')
wsl, paths = _runtime_settings()
encoded = base64.b64encode(_MODEL_BOUNDARY_BOOTSTRAP.encode()).decode()
cmd = [*wsl, paths['python'], '-c', 'import base64;exec(compile(base64.b64decode(' + repr(encoded) + '),"<model-boundary>","exec"))',
       paths['root'], _wsl_path(stage), _wsl_path(args.output), _wsl_path(sentinel), paths['root'] + '/model-preflight-rpc-' + uuid.uuid4().hex]
env = {k:v for k,v in os.environ.items() if not k.startswith(('CREDPROOF_', 'OLLAMA_')) and not k.endswith('_API_KEY')}
proc = subprocess.run(cmd, capture_output=True, timeout=180, env=env)
(args.output/'stdout.txt').write_bytes(proc.stdout)
(args.output/'stderr.txt').write_bytes(proc.stderr)
receipt = {'returncode':proc.returncode,'model':selected_profile(),'formal_tasks':0,'claim_consumed':True}
(args.output/'command-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
finish_comparison(claim, receipt)
print(json.dumps(receipt))
raise SystemExit(proc.returncode)
