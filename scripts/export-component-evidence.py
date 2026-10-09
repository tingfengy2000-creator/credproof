"""Append-only structural public derivatives. Full raw records remain local."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
base=ROOT/'docs/reusable-tool-safety/acceptance/20261009-component-assisted'
ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['preparation','formal']);ap.add_argument('--workspace',type=Path)
args=ap.parse_args();dest=base/'public-evidence';dest.mkdir(exist_ok=True)
mapping=[]
def sha(b):return hashlib.sha256(b).hexdigest()
def redact(value):
    if isinstance(value,dict):return {k:redact(v) for k,v in value.items()}
    if isinstance(value,list):return [redact(x) for x in value]
    if isinstance(value,str):
        value=value.replace(str(ROOT),'<repository>').replace(ROOT.as_posix(),'<repository>')
        value=value.replace('E:\\比赛\\CredProof-dev32-install','<install-root>')
        value=re.sub(r'/home/[^/\s"\x27]+/credproof-agent-runtime','<runtime>',value)
        tails=re.findall(r'CP_LAB_[A-Fa-f0-9]+(?:\.{3}|…)([A-Fa-f0-9]+)',value)
        for tail in tails:
            if len(tail)>=6: value=value.replace(tail,'[SYNTHETIC_FRAGMENT]')
        value=re.sub(r'CP_LAB_[A-Fa-f0-9]+(?:\.{3}|…)\[SYNTHETIC_FRAGMENT\]','[SYNTHETIC_CREDENTIAL_ABBREVIATED]',value)
        value=re.sub(r'CP_LAB_[A-Fa-f0-9]{32}','[SYNTHETIC_CREDENTIAL]',value)
        value=re.sub(r'CP_LAB_[A-Fa-f0-9]+(?:\.{3}|…)[A-Fa-f0-9]+','[SYNTHETIC_CREDENTIAL_ABBREVIATED]',value)
        return value
    return value
def emit(name,source=None,value=None):
    original=source.read_bytes() if source else None
    if source and source.suffix=='.json':value=json.loads(original.decode('utf8'))
    if value is not None:b=(json.dumps(redact(value),ensure_ascii=False,indent=2)+'\n').encode()
    else:b=redact(original.decode('utf8')).replace('\r\n','\n').encode('utf8')
    path=dest/name;path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and path.read_bytes()!=b:raise ValueError('Refuse changed public evidence: '+name)
    path.write_bytes(b)
    mapping.append({'published':name,'published_sha256':sha(b),'published_bytes':len(b),
                    'original_sha256':sha(original) if original else None,
                    'original_bytes':len(original) if original else None,
                    'source':source.relative_to(ROOT).as_posix() if source and source.is_relative_to(ROOT) else str(source) if source else 'derived'})
if args.phase=='preparation':
    for folder in ('component-controls','component-controls-b','component-controls-final'):
        for name in ('component-execution.json','unchanged-original-report.json','summary.json'):
            emit(folder+'/'+name,base/folder/name)
    for file in (base/'preflight').glob('*.json'):emit('preflight/'+file.name,file)
else:
    run=base/'formal-page'
    for f in run.glob('*.json'):emit('formal-page/'+f.name,f)
    workspace=args.workspace
    final=json.loads((run/'page-final.json').read_text(encoding='utf8'))
    task=workspace/'runs/ui'/final['id']/'output'
    repair=json.loads((task/'repair.json').read_text(encoding='utf8'))
    artifact=Path(repair['artifact_dir'])
    emit('formal-page/repair-summary.json',value={k:repair[k] for k in ('schema','status','task_status','strategy','elapsed_s','model','budgets','paid_api_used') if k in repair})
    emit('formal-page/initial-report.json',value=repair['initial']);emit('formal-page/final-report.json',value=repair['final'])
    emit('formal-page/program-trace.json',value=repair.get('program_trace',[]))
    emit('formal-page/installed-child-origin.json',task/'origin-receipt.json')
    emit('formal-page/launch.json',task.parent/'launch.json')
    for file in (artifact/'model-work/model-trace').glob('*.json'):emit('model-trace/'+file.name,file)
    for file in (artifact/'verification-history').glob('*'):
        if file.suffix in ('.json','.py'):emit('candidates/'+file.name,file)
    for name in ('structured-api-service.json','boundary-probe.json'):
        file=artifact/'model-work'/name
        if file.is_file():emit('formal-page/'+name,file)
    log=artifact/'model-work/ollama-stderr.txt'
    lines=[line for line in log.read_text(encoding='utf8',errors='replace').splitlines() if any(x in line for x in ('inference compute','offloaded ','CUDA0 model buffer','CUDA0 KV buffer'))]
    emit('formal-page/device-evidence.json',value={'source_sha256':sha(log.read_bytes()),'actual_log_lines':lines})
    emit('formal-page/model-boundary.json',value=repair.get('model_boundary'))
    receipt=json.loads((run/'command-receipt.json').read_text(encoding='utf8'))
    accepted=[p for p in (artifact/'verification-history').glob('candidate-*.py')]
    verified=[p for p in (artifact/'verification-history').glob('verification-*.json')]
    emit('summary.json',value={'kind':'ONE_REGISTERED_COMPONENT_ASSISTED_PAGE_TASK',
         'source_commit':json.loads((run/'freeze.json').read_text())['source_commit'],
         'model_requests':repair.get('model',{}).get('model_calls',0),
         'usage_records':len(repair.get('model',{}).get('usage',[])),
         'generation_attempts':repair.get('model',{}).get('generations',0),
         'format_corrections':repair.get('model',{}).get('format_correction_attempts',0),
         'native_tool_requests':0,'program_requests':len(repair.get('program_trace',[])),
         'accepted_candidates':len(accepted),'program_verifications':len(verified),
         'candidate_results':[{'file':p.name,'verdict':json.loads(p.read_text(encoding='utf8'))['verdict'],
            'failed_checks':json.loads(p.read_text(encoding='utf8')).get('failed_checks')} for p in sorted(verified)],
         'task_status':repair.get('task_status'),'final_verdict':repair['final']['verdict'],
         'elapsed_s':repair.get('elapsed_s'), 'paid_api_used':False,
         'page_receipt':receipt,'historical_results_unchanged':True})
emit('derivation-'+args.phase+'.json',value={'phase':args.phase,'records':mapping,
     'transforms':['exact host prefix mapping','structured synthetic-value redaction','UTF8 LF'],
     'originals_preserved':True,'warning':'Derived serialized bytes are not the original wire bytes; original digests and sizes are separate.'})
manifest={p.relative_to(dest).as_posix():sha(p.read_bytes()) for p in sorted(dest.rglob('*')) if p.is_file() and not p.name.startswith('manifest-')}
emit('manifest-'+args.phase+'.json',value={'files':manifest,'self_hash_excluded':True})
print(json.dumps({'phase':args.phase,'files':len(manifest)},indent=2))
