"""One bounded proposal in the existing model boundary. Never checks/applies code.

Host-selected input, pinned model, no tools, one request and no format retry.
The review workspace owns version creation and revalidates its binding.
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid

from agent_pilot.bounded_patch import build_payload, parse_response
from agent_pilot.model_client import estimate_input_budget
from agent_pilot.model_config import selected_profile
from .agent import (_bounded_initial_context, _bounded_model_script, _MODEL_BOUNDARY_BOOTSTRAP,
                    _model_actionable_failures, _model_readable_paths, _runtime_settings, _wsl_path)
from .config import load_config
from .project import _digest_tree

LIMITS={'model_requests':1,'format_corrections':0,'candidates':1,'verifications':0,
        'context':16384,'output':2048,'safety_reserve':512,'request_seconds':120,'task_seconds':900}


def worker_script():
    # Same reviewed service startup, mounts, GPU and boundary probes. No old
    # native-tool prompt or RPC operations enter the actual generation payload.
    prefix=_bounded_model_script().split(' started=time.monotonic()',1)[0]
    tail=r'''
 client=BoundedPatchClient(artifact/'model-trace',max_calls=1)
 result={'status':'NO_CANDIDATE','reason':'not_started','model_requests':0,'usage':[]}
 try:
  payload=initial_context['proposal_payload']
  response=client.request(payload)
  result.update(status='RESPONSE_RECEIVED',reason=None)
 except Exception as exc:
  result['reason']=type(exc).__name__+': '+str(exc)
 finally:
  result.update(model_requests=client.calls,usage=client.usage,native_tool_calls=0,verifications=0)
  try: result['active_models']=json.loads(api('/api/ps'))
  except Exception: result['active_models']=None
  (artifact/'proposal-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
finally:
 if ollama is not None:
  ollama.terminate()
  try: ollama.wait(timeout=10)
  except subprocess.TimeoutExpired: ollama.kill()
  ollama_stdout.close(); ollama_stderr.close()
 shutil.rmtree(work,ignore_errors=True)
'''
    return prefix+tail


def payload_for(config, report):
    entry=config.entry.module.replace('.','/')+'.py'
    sources={}
    for relative in _model_readable_paths(config):
        p=config.project_root/relative
        if p.is_symlink() or not p.is_file() or p.stat().st_size>65536:
            raise ValueError('proposal_authorised_source_missing_or_oversized')
        sources[relative]=p.read_text('utf8')
    context=_bounded_initial_context(report,config)
    state={'strategy':'bounded_patch','purpose':'REVIEW_PROPOSAL_ONLY',
           'remaining_generations':1,'remaining_requests':1,'remaining_format_corrections':0,
           'automatic_verifications':0,'allowed_actions':['PATCH','STOP']}
    payload=build_payload(context,sources.pop(entry),sources,_model_actionable_failures(report,config),state)
    payload['messages'][0]['content']+=' This operation only proposes a new review version; no automatic check or adoption. A user may separately request program verification.'
    return payload


def generate_proposal(config_path, report, output):
    """Trusted local paths only; the browser supplies no path/model/command."""
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    config=load_config(config_path);profile=selected_profile()
    if os.environ.get('CREDPROOF_BOUNDARY_ONLY','0') not in ('','0'):
        raise ValueError('proposal_boundary_only_mode_forbidden')
    if report.get('verdict')!='FAIL' or report.get('project_tree_sha256')!=_digest_tree(config.project_root):
        raise ValueError('proposal_report_object_mismatch')
    payload=payload_for(config,report);budget=estimate_input_budget(payload,2048)
    def save(name,value):
        (output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    save('planned-request.json',payload);save('input-budget.json',budget);save('limits.json',LIMITS)
    if not budget['within_context_budget'] or not budget['within_wire_limit']:
        return {'status':'NO_CANDIDATE','reason':'proposal_input_budget','model_requests':0,'model':profile}
    stage=output/'model-stage';stage.mkdir();repo=Path(__file__).resolve().parents[1]
    for relative in ('agent_pilot/__init__.py','agent_pilot/tools.py','agent_pilot/model_client.py',
                     'agent_pilot/model_config.py','agent_pilot/bounded_patch.py','agent_pilot/output_format.py'):
        p=stage/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((repo/relative).read_bytes())
    (stage/'worker.py').write_text(worker_script(),encoding='utf8')
    (stage/'model-profile.json').write_text(json.dumps(profile),encoding='utf8')
    (stage/'initial-context.json').write_text(json.dumps({'_generation_strategy':'bounded_patch','proposal_payload':payload},ensure_ascii=False),encoding='utf8')
    sentinel=output/'host-sentinel.txt';sentinel.write_text('synthetic boundary marker\n')
    wsl,paths=_runtime_settings();rpc=paths['root']+'/proposal-rpc-'+uuid.uuid4().hex
    bootstrap=base64.b64encode(_MODEL_BOUNDARY_BOOTSTRAP.encode()).decode()
    command=[*wsl,paths['python'],'-c','import base64;exec(compile(base64.b64decode('+repr(bootstrap)+'),"<credproof-model-boundary>","exec"))',
             paths['root'],_wsl_path(stage),_wsl_path(output),_wsl_path(sentinel),rpc]
    env={k:v for k,v in os.environ.items() if not k.startswith(('CREDPROOF_','OLLAMA_')) and not k.endswith('_API_KEY')}
    proc=None
    try:
        proc=subprocess.run(command,env=env,capture_output=True,timeout=900)
        (output/'supervisor.stdout.bin').write_bytes(proc.stdout);(output/'supervisor.stderr.bin').write_bytes(proc.stderr)
    except (OSError,subprocess.TimeoutExpired) as exc:
        save('supervisor-error.json',{'reason':type(exc).__name__})
    work=output/'model-work';trace=work/'model-trace'
    raw_response=trace/'model-01-response.json';request=trace/'model-01-request.json'
    count=int(request.is_file() and not (trace/'model-01-unsent.json').exists())
    result={'status':'NO_CANDIDATE','reason':'model_boundary_or_execution_incomplete','model':profile,
            'strategy':'bounded_patch','model_requests':count,'native_tool_calls':0,'verifications':0}
    try:
        probe=json.loads((work/'boundary-probe.json').read_text('utf8'))
        service=json.loads((work/'service-boundary.json').read_text('utf8'))
        if (proc is None or proc.returncode or probe['interfaces']!=['lo'] or probe['host_sentinel_visible']
            or probe['model_code_writable'] or probe['mountinfo_has_windows_or_host_mount'] or probe['host_link_visible']
            or any(x['connected'] for x in probe['outside_connect_tests'])
            or service['host_sentinel_via_service_root_visible']
            or any(x['connected'] for x in service['external_probes_after_service_start'])
            or any(x['controller']!=x['ollama'] for x in service['namespace_ids'].values())):
            raise ValueError('model_boundary_evidence_not_accepted')
        result['boundary_status']='VERIFIED_FOR_THIS_CALL'
        worker=json.loads((work/'proposal-result.json').read_text('utf8'))
        result.update(model_requests=worker['model_requests'],usage=worker['usage'],active_models=worker['active_models'])
        if not raw_response.is_file():
            result['reason']=worker['reason']
        else:
            obj=parse_response(json.loads(raw_response.read_text('utf8')))
            result.update(request_sha256=hashlib.sha256(request.read_bytes()).hexdigest(),
                          response_sha256=hashlib.sha256(raw_response.read_bytes()).hexdigest())
            if obj['action']=='PATCH':result.update(status='CANDIDATE',reason=obj['reason'],code=obj['code'],format_receipt=obj.get('_source_format'))
            else:result.update(reason='MODEL_STOP: '+obj['reason'])
    except (OSError,ValueError,TypeError,KeyError) as exc:
        result['reason']='proposal_invalid_or_incomplete: '+type(exc).__name__+': '+str(exc)
    save('result.json',result)
    return result
