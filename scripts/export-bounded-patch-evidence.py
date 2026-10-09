"""Publish structural derived evidence of the one saved generation task."""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
base=ROOT/'docs/reusable-tool-safety/acceptance/20261009-bounded-patch'
run=base/'formal-p01';artifact=run/'result-artifacts'
dest=base/'public-evidence';dest.mkdir(exist_ok=False)
records=[]


def sha(data):return hashlib.sha256(data).hexdigest()


def redact(value):
    if isinstance(value,dict):return {k:redact(v) for k,v in value.items()}
    if isinstance(value,list):return [redact(x) for x in value]
    if isinstance(value,str):
        try:nested=json.loads(value)
        except (ValueError,TypeError):nested=None
        if isinstance(nested,(dict,list)):return json.dumps(redact(nested),ensure_ascii=False,separators=(',',':'))
        value=value.replace(str(ROOT),'<repository>').replace(ROOT.as_posix(),'<repository>')
        value=re.sub(r'/home/[^/\s"\x27]+/credproof-agent-runtime','<runtime>',value)
        value=re.sub(r'CP_LAB_[A-F0-9]{32}','[SYNTHETIC_CREDENTIAL]',value)
        return re.sub(r'CP_LAB_[A-F0-9]+\.{3}[A-F0-9]+','[SYNTHETIC_CREDENTIAL_ABBREVIATED]',value)
    return value


def emit(name,value,original=None):
    f=dest/name;f.parent.mkdir(parents=True,exist_ok=True)
    b=(json.dumps(redact(value),ensure_ascii=False,indent=2)+'\n').encode('utf8');f.write_bytes(b)
    records.append({'published':name,'published_sha256':sha(b),'published_bytes':len(b),
                    'source':original.relative_to(ROOT).as_posix() if original else 'derived from saved records',
                    'original_sha256':sha(original.read_bytes()) if original else None,
                    'original_bytes':original.stat().st_size if original else None})


r=json.loads((run/'result.json').read_text(encoding='utf8'));freeze=json.loads((run/'freeze.json').read_text(encoding='utf8'))
emit('freeze.json',freeze,run/'freeze.json')
emit('command-receipt.json',json.loads((run/'command-receipt.json').read_text(encoding='utf8')),run/'command-receipt.json')
emit('initial-report.json',r['initial']);emit('final-report.json',r['final'])
emit('program-trace.json',r['program_trace'])
for f in sorted((artifact/'model-work/model-trace').glob('*.json')):
    emit('model-trace/'+f.name,json.loads(f.read_text(encoding='utf8')),f)
for f in sorted((artifact/'verification-history').glob('*.json')):
    emit(f.name,json.loads(f.read_text(encoding='utf8')),f)
for f in sorted((artifact/'verification-history').glob('candidate-*.py')):
    b=f.read_bytes().replace(b'\r\n',b'\n').replace(b'\r',b'\n');target=dest/f.name;target.write_bytes(b)
    records.append({'published':f.name,'published_sha256':sha(b),'published_bytes':len(b),
                    'source':f.relative_to(ROOT).as_posix(),'original_sha256':sha(f.read_bytes()),'original_bytes':f.stat().st_size})
emit('structured-api-service.json',json.loads((artifact/'model-work/structured-api-service.json').read_text(encoding='utf8')),artifact/'model-work/structured-api-service.json')
probe=r['model_boundary']['probe']
emit('model-boundary.json',{'status':r['model_boundary']['status'],
    'probe':{k:probe[k] for k in ['interfaces','outside_connect_tests','host_sentinel_visible','model_code_writable',
             'mountinfo_has_windows_or_host_mount','host_link_visible','denied_paths'] if k in probe},
    'code_allowlist':r['model_boundary']['plan']['allowlist']['code'],
    'omitted':'full mounts/process identity retained locally'})
log=artifact/'model-work/ollama-stderr.txt'
lines=[s for s in log.read_text(encoding='utf8',errors='replace').splitlines() if any(x in s for x in
    ['inference compute','offloaded ','CUDA0 model buffer','CUDA0 KV buffer','CUDA0 compute buffer'])]
emit('device-evidence.json',{'original_log_sha256':sha(log.read_bytes()),'actual_lines':lines},log)
for f in sorted((base/'protocol-preflight').glob('*.json')):
    emit('protocol-preflight/'+f.name,json.loads(f.read_text(encoding='utf8')),f)
accepted=[a for a in r['program_trace'] if a['result'].get('status')=='ACCEPTED_FOR_VERIFICATION']
rows=[]
for a in accepted:
    n=a['result']['candidate'];full=json.loads((artifact/f'verification-history/verification-{n:02d}.json').read_text(encoding='utf8'))
    obs=full['execution']['pytest_observation']
    rows.append({'candidate':n,'sha256':a['result']['candidate_sha256'],'verdict':full['verdict'],
       'failed_checks':a['result']['verification']['report']['confirmed_failed_checks'],
       'pytest':{k:obs[k] for k in ('collected','executed','passed','failed','skipped','required_unmet_cases')},
       'scenarios':full['execution']['entry_scenarios'],
       'interpretation':'Normal allowed file wrongly rejected before file/service/log stage; no observed output/network is not successful repair.'})
summary={'schema':'credproof.bounded-patch-run-summary/v1','source_commit':freeze['source_commit'],
 'strategy':'bounded_patch','task':'assistant-original/p01','model':'qwen3-coder:30b',
 'actual':{'model_requests':r['model']['model_calls'],'usage_records':len(r['model']['usage']),
          'generation_attempts':r['model']['generations'],'format_corrections':r['model']['format_correction_attempts'],
          'native_tool_requests':0,'program_preparation_operations':3,'program_submission_attempts':3,
          'accepted_candidates':len(accepted),'program_auto_verifications':len(accepted),'model_candidate_PASS':0,
          'exports':0,'new_directory_rechecks':0,'elapsed_s':r['elapsed_s'],'paid_api_used':False},
 'candidate_results':rows,'third_proposal':'REJECTED/NO_CHANGE; bytes equal candidate 2; no new candidate or verification',
 'usage':r['model']['usage'],'task_status':r['task_status'],'status':r['status'],
 'error':r['model'].get('error'),'handoff_status':'NOT_READY_FOR_HANDOFF',
 'failure_classification':{'output_format':'3 complete schema-valid PATCH responses; no truncation or correction',
   'input_organization':'Current source/tests/rules/feedback were present. Feedback summary did not include raised.message or explicitly map configured data to runtime /tmp/lab/data; this limits attribution solely to model capability.',
   'model_code_semantics':'Invented CREDPROOF_ALLOWED_DIRS/FORBIDDEN_DIRS not supplied by runner; rejects normal file; abspath/text prefix does not resolve symlink ownership; leaves sensitive logging and urlopen redirect/port blind spot; third code unchanged.',
   'environment_and_verification':'CUDA0 local structured API returned three responses; two host-accepted candidates ran existing check_project; pytest actually executed 4 cases, 2 passed/2 failed each; no executor error.'},
 'decision':'End this round without more inference. Recommend user-authorised validated file/HTTP access components for assisted generation before any further effect comparison; not implemented or approved here.'}
emit('summary.json',summary)
emit('derivation-receipt.json',{'source_records_preserved':True,'transforms':['structural JSON redaction','exact host prefix mapping','full/abbreviated synthetic-value redaction','UTF8 LF'], 'records':records})
print(json.dumps(summary['actual'],indent=2))
