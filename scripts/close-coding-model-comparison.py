"""Publish metadata/receipts after the single task. No inference or candidate execution."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/reusable-tool-safety/acceptance/20261009-coding-model-comparison'
PUBLIC = BASE / 'public-evidence'
INSTALL = Path(r'E:\比赛\CredProof-dev33-install')
LEDGER = Path(r'E:\比赛\CredProof-agent-state\coding-model-comparison-20261009')
RUN = BASE / 'formal-page'
final = json.loads((RUN/'page-final.json').read_text('utf8'))
output = INSTALL / 'data/runs/ui' / final['id'] / 'output'
repair = json.loads((output/'repair.json').read_text('utf8'))
artifact = Path(repair['artifact_dir'])
records = []

def sha(data):
    return hashlib.sha256(data).hexdigest()

def redact(value):
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(x) for x in value]
    if not isinstance(value, str):
        return value
    for path, label in ((ROOT, '<repository>'), (INSTALL, '<install-root>'),
                        (LEDGER, '<host-ledger>')):
        value = value.replace(str(path), label).replace(path.as_posix(), label)
    value = value.replace('/home/tingfeng/credproof-agent-runtime', '<runtime>')
    value = value.replace('/比赛/CredProof-dev33-install', '<install-root-drvfs>')
    value = value.replace('/比赛/密证_CredProof-local-agent', '<repository-drvfs>')
    value = re.sub(r'CP_LAB_[A-Fa-f0-9]{32}', '[SYNTHETIC_CREDENTIAL]', value)
    value = re.sub(r'CP_LAB_[A-Fa-f0-9]+(?:\.{3}|…)(?:\[SYNTHETIC_FRAGMENT\]|[A-Fa-f0-9]+)',
                   '[SYNTHETIC_CREDENTIAL_ABBREVIATED]', value)
    return value

def emit(name, source=None, value=None):
    raw = source.read_bytes() if source else None
    if source and source.suffix == '.json':
        value = json.loads(raw.decode('utf-8-sig'))
    if value is None:
        data = redact(raw.decode('utf-8-sig')).replace('\r\n','\n').encode()
    else:
        data = (json.dumps(redact(value), ensure_ascii=False, indent=2)+'\n').encode()
    target = PUBLIC / name
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_bytes() != data:
        raise RuntimeError('Refuse overwritten evidence: '+name)
    target.write_bytes(data)
    records.append({'published': name, 'published_sha256': sha(data), 'published_bytes': len(data),
                    'source': redact(str(source)) if source else 'derived',
                    'original_sha256': sha(raw) if raw is not None else None,
                    'original_bytes': len(raw) if raw is not None else None})

# Older first-pass formal derivatives are local-only; publish additional redaction
# as a separately named version rather than calling it the original wire bytes.
for source in sorted(PUBLIC.rglob('*.json')):
    if source.parts[-2] == 'closure':
        continue
    raw = source.read_bytes()
    revised = (json.dumps(redact(json.loads(raw.decode('utf8'))), ensure_ascii=False, indent=2)+'\n').encode()
    if revised != raw and re.search(rb'CP_LAB_[A-Fa-f0-9]+(?:\.{3}|\xe2\x80\xa6)', raw):
        # These files have not been committed; preserve the first derivative locally.
        backup = ROOT / '_runs/dev33-first-public-derivatives' / source.relative_to(PUBLIC)
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists(): backup.write_bytes(raw)
        tracked = subprocess.run(['git','-c','safe.directory='+str(ROOT),'ls-files','--error-unmatch',str(source.relative_to(ROOT))],cwd=ROOT,capture_output=True).returncode == 0
        target = source.with_name(source.stem+'-redacted-v2.json') if tracked else source
        target.write_bytes(revised)
        records.append({'published':target.relative_to(PUBLIC).as_posix(),
                        'published_sha256':sha(revised),'published_bytes':len(revised),
                        'first_local_derivative_sha256':sha(raw),'first_local_derivative_bytes':len(raw),
                        'change':'remaining synthetic abbreviation redacted before first publication; local first derivative retained'})

for source, name in [
    (ROOT/'_runs/qwen25-native-install.json','preparation/native-model-install.json'),
    (ROOT/'_runs/qwen25-download-continuation.json','preparation/download-continuation.json'),
    (Path(r'E:\比赛\CredProof-model-preparation-qwen25/download-receipt.json'),'preparation/download-receipt.json'),
    (ROOT/'_runs/dev33-installed-preflight.json','preparation/installed-preflight-final.json'),
    (ROOT/'_runs/dev33-origin-final.json','preparation/installed-program-origin-final.json'),
    (INSTALL/'origin-final/origin-receipt.json','preparation/installed-child-origin-final.json'),
    (RUN/'page-stdout.txt','formal-page/page-stdout.txt'),
    (RUN/'page-stderr.txt','formal-page/page-stderr.txt'),
    (artifact/'model-work/model-result.json','formal-page/model-result.json'),
    (artifact/'model-work/ollama-stderr.txt','formal-page/ollama-stderr.txt'),
    (artifact/'candidate/credproof.toml','input-materials/credproof.toml'),
    (artifact/'candidate/tests/test_business.py','input-materials/tests/test_business.py'),
    (INSTALL/'data/examples/material_assistant/tool.py','input-materials/original-tool.py'),
]:
    emit(name, source)
for source in sorted(LEDGER.glob('*.json')):
    emit('registration-state/'+source.name, source)
preflight = BASE/'structured-preflight'
for source in sorted((preflight/'model-work').glob('*')):
    if source.suffix in ('.json','.txt') and not source.is_symlink() and source.is_file():
        emit('structured-preflight/'+source.name, source)
emit('structured-preflight/command-receipt.json',preflight/'command-receipt.json')
emit('structured-preflight/boundary-plan.json',preflight/'boundary-plan.json')
emit('formal-page/boundary-plan.json',artifact/'boundary-plan.json')

request = artifact/'model-work/model-trace/model-01-request.json'
payload = json.loads(request.read_text('utf8'))
wire = json.dumps(payload, ensure_ascii=False).encode('utf8')
candidate = artifact/'verification-history/candidate-01.py'
code = repair['model']['decoded_outputs'][0]['output']['code']
rows = {str(p.relative_to(INSTALL/'venv/Lib/site-packages')).replace('\\','/'): sha(p.read_bytes())
        for p in (INSTALL/'venv/Lib/site-packages/agent_pilot').glob('*.py')}
emit('closure/request-provenance.json',value={
    'saved_request_file_sha256':sha(request.read_bytes()),'saved_request_file_bytes':request.stat().st_size,
    'production_serialization':'json.dumps(payload, ensure_ascii=False).encode(utf8)',
    'reconstructed_http_body_sha256':sha(wire),'reconstructed_http_body_bytes':len(wire),
    'not_a_packet_capture':True,'public_derivative_is_not_wire_bytes':True,
    'model_output_code_utf8_sha256':sha(code.encode()),'model_output_code_utf8_bytes':len(code.encode()),
    'local_candidate_file_sha256':sha(candidate.read_bytes()),'local_candidate_bytes':candidate.stat().st_size,
    'public_candidate_LF_sha256':sha(candidate.read_bytes().replace(b'\r\n',b'\n')),
    'normalization':'only explicit CRLF -> LF publication, no removal of Markdown fences or code changes'})
lines = code.splitlines()
issues = [{'lines':[i+1 for i,line in enumerate(lines) if line.startswith('```')],'type':'GENERATED_SOURCE_FORMAT','fact':'Markdown fences are literal candidate bytes; actual SyntaxError line 1 prevents import/collection.'},
          {'lines':[i+1 for i,line in enumerate(lines) if 'except urllib.' in line or 'HTTP error accessing' in line],'type':'STATIC_ONLY_UNEXECUTED','fact':'except urllib.error.HTTPError references an unbound urllib name and converts required HTTPError into ValueError. Not dynamically reached or repaired.'}]
emit('closure/conclusion.json',value={
    'schema':'credproof.coding-model-comparison/v1',
    'tested_source_commit':json.loads((RUN/'freeze.json').read_text('utf8'))['source_commit'],
    'wheel_build_source':'ad826dae2d43ee0c0ec636f59a48f9325bcd14df',
    'wheel_sha256':'90cbb4f328de855eeb363ac4b13062c44a5d7edf9787a4660ffb76ac7d8648f9',
    'program_changed_after_formal_start':False,'model':repair['model_profile'],
    'preflight_requests':1,'formal_tasks':1,'formal_model_requests':1,'usage_records':1,
    'generation_attempts':1,'different_generated_codes':1,'accepted_candidates':1,
    'program_auto_verifications':1,'native_tool_calls':0,'format_corrections':0,
    'initial_verdict':repair['initial']['verdict'],'candidate_verdict':repair['final']['verdict'],
    'task_status':repair['task_status'],'pytest_exit_code':repair['final']['execution']['pytest_exit_code'],
    'pytest_collected':0,'pytest_executed':0,'entry_scenarios_executed':0,
    'root_failure_class':'MODEL_GENERATED_INVALID_SOURCE_FORMAT',
    'execution_consequence':'collection/import blocked by literal Markdown fences, not environment installation, timeout or input budget',
    'json_schema_valid':True,'python_source_valid':False,'component_import_and_calls_present':True,
    'credential_lookup_expression_correct_statically':True,
    'function_or_safety_success_established':False,'static_issues':issues,
    'same_object_public_PASS_recheck':False,'PASS_export_not_attempted':True,
    'page_task_identity':final['id'],'installed_page_status':final['status'],
    'handoff_status':'NOT_READY_FOR_HANDOFF','comparison_status':'MODEL_COMPARISON_CLOSED_UNSUCCESSFUL',
    'round_closed':True,'remaining_budget_not_used_due_to_unknown_stop':True,
    'next_decision':'Pause automatic-generation effectiveness optimization; await user resources/scope decision.',
    'not_a_semantic_model_ranking':True,'no_second_task_permitted':True})
emit('closure/commands.json',value={
    'environment':{'CREDPROOF_MODEL_PROFILE':'qwen25','CREDPROOF_MODEL_COMPARISON_LEDGER':'<host-ledger>/ledger.json','PYTHONUTF8':'1'},
    'commands':[
        {'argv':'<installed-python> -I -m agent_pilot.preflight','exit_code':0,'kind':'NO_INFERENCE'},
        {'argv':'<installed-python> -I scripts/preflight-coding-model.py --output <registered-output>/structured-preflight','exit_code':0,'kind':'ONE_NON_PROJECT_MODEL_REQUEST'},
        {'argv':'.venv/Scripts/python.exe scripts/run-component-page-task.py --python <installed-python> --workspace <install-root>/data --output <registered-output>/formal-page','exit_code':0,'kind':'ONE_REAL_INSTALLED_PAGE_TASK','task_status':repair['task_status'],'verdict':'UNKNOWN'},
        {'argv':'.venv/Scripts/python.exe scripts/export-component-evidence.py formal --base <registered-output> --workspace <install-root>/data --run <registered-output>/formal-page --install-root <install-root>','exit_code':0,'kind':'POST_RUN_DERIVATION_NO_EXECUTION'}],
    'zero_exit_is_not_candidate_PASS':True,'no_model_after_formal_task':True})
for backup in sorted((ROOT/'_runs/dev33-first-public-derivatives').rglob('*.json')):
    current = PUBLIC/backup.relative_to(ROOT/'_runs/dev33-first-public-derivatives')
    newer = current.with_name(current.stem+'-redacted-v2.json')
    if newer.exists(): current = newer
    records.append({'published':current.relative_to(PUBLIC).as_posix(),
                    'published_sha256':sha(current.read_bytes()),'published_bytes':current.stat().st_size,
                    'first_local_derivative_sha256':sha(backup.read_bytes()),'first_local_derivative_bytes':backup.stat().st_size,
                    'change':'remaining synthetic abbreviation redacted before first publication; local first derivative retained'})
emit('closure/derivation.json',value={'records':records,'originals_preserved':True,
    'transforms':['exact known host prefix mapping','synthetic full values and abbreviations','UTF8 LF'],
    'normal_source_and_candidate_code_preserved_including_invalid_fences':True,
    'generated_metadata_is_not_raw_execution':True,'first_formal_derivation_manifest_superseded_by_final_Git_blob_manifest':True})
print(json.dumps({'closed':True,'formal_requests':1,'verdict':'UNKNOWN','files_added':len(records)}))
