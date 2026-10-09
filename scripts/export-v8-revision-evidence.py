"""Publish bounded v8 evidence from saved records; never rerun or alter verdicts."""
import hashlib
import json
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root / 'docs/reusable-tool-safety/acceptance/20261007-return-redirect/context-budget-pilot-v8'
run = base / 'formal-p01-host-authorized'
artifact = run / 'result-artifacts'
trace = artifact / 'model-work/model-trace'
dest = base / 'public-evidence'
dest.mkdir(exist_ok=False)
records = []

def digest(b):
    return hashlib.sha256(b).hexdigest()

def redact(value):
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        # Only exact known host prefixes and synthetic values. No path regex
        # can swallow Python code, Linux lab paths, or URL syntax.
        try:
            nested = json.loads(value)
        except (ValueError, TypeError):
            nested = None
        if isinstance(nested, (dict, list)):
            return json.dumps(redact(nested), ensure_ascii=False, separators=(',', ':'))
        value = value.replace(str(root), '<repository>').replace(root.as_posix(), '<repository>')
        value = re.sub(r'/home/[^/\s"\x27]+/credproof-agent-runtime', '<runtime>', value)
        # pytest abbreviates repr strings; redact both full values and those
        # bounded hex-only fragments without consuming surrounding source.
        value = re.sub(r'CP_LAB_[A-F0-9]{32}', '[SYNTHETIC_CREDENTIAL]', value)
        return re.sub(r'CP_LAB_[A-F0-9]+\.{3}[A-F0-9]+', '[SYNTHETIC_CREDENTIAL_ABBREVIATED]', value)
    return value

def emit(name, value, source=None):
    target = dest/name
    target.parent.mkdir(parents=True, exist_ok=True)
    b = (json.dumps(redact(value), ensure_ascii=False, indent=2)+'\n').encode('utf8')
    target.write_bytes(b)
    records.append({'published': name, 'published_sha256': digest(b), 'published_bytes': len(b),
                    'source': source.relative_to(root).as_posix() if source else 'derived from saved records',
                    'original_sha256': digest(source.read_bytes()) if source else None,
                    'original_bytes': source.stat().st_size if source else None})

result = json.loads((run/'result.json').read_text(encoding='utf8'))
freeze = json.loads((run/'freeze.json').read_text(encoding='utf8'))
emit('freeze.json', freeze, run/'freeze.json')
emit('command-receipt.json', json.loads((run/'command-receipt.json').read_text(encoding='utf8')), run/'command-receipt.json')
emit('pre-model-blocked.json', json.loads((base/'formal-p01-model-result.json').read_text(encoding='utf8')), base/'formal-p01-model-result.json')
requests = sorted(trace.glob('model-*-request.json'))
responses = sorted(trace.glob('model-*-response.json'))
for p in requests + responses + sorted(trace.glob('model-*-input-budget.json')):
    emit('model-trace/'+p.name, json.loads(p.read_text(encoding='utf8')), p)
for p in sorted((artifact/'verification-history').glob('verification-*.json')):
    emit(p.name, json.loads(p.read_text(encoding='utf8')), p)
for p in sorted((artifact/'verification-history').glob('candidate-*.py')):
    b = p.read_bytes()
    text = b.decode('utf8').replace('\r\n', '\n').replace('\r', '\n')
    target = dest/p.name
    target.write_bytes(text.encode('utf8'))
    records.append({'published': p.name, 'published_sha256': digest(target.read_bytes()),
                    'published_bytes': target.stat().st_size, 'source': p.relative_to(root).as_posix(),
                    'original_sha256': digest(b), 'original_bytes': len(b),
                    'transform': 'explicit LF normalization only; no patch modification'})
emit('initial-report.json', result['initial'])
emit('final-report.json', result['final'])
emit('tool-trace.json', result['tool_trace'])
boundary = result['model_boundary']['probe']
emit('model-boundary.json', {
    'status': result['model_boundary']['status'],
    'probe': {k: boundary[k] for k in ('interfaces', 'outside_connect_tests', 'host_sentinel_visible',
             'model_code_writable', 'mountinfo_has_windows_or_host_mount', 'host_link_visible',
             'denied_paths', 'allowed_writable_roots', 'readonly_roots') if k in boundary},
    'omitted': ['full_mountinfo', 'mountinfo_excerpt', 'process identity details'],
    'reason': 'omit unnecessary host identity; original probe retained locally',
})
log = artifact/'model-work/ollama-stderr.txt'
device_lines = [line for line in log.read_text(encoding='utf8', errors='replace').splitlines()
                if any(key in line for key in ('inference compute', 'using device CUDA', 'offloaded ',
                    'CUDA0 model buffer size', 'CUDA0 KV buffer size', 'CUDA0 compute buffer size'))]
emit('device-evidence.json', {'original_log_sha256': digest(log.read_bytes()),
    'lines': device_lines, 'scope': 'same model service as this task; CUDA0/5090'}, log)
model = result['model']
tools = result['tool_trace']
accepted = [t for t in tools if t['result'].get('status') == 'ACCEPTED_FOR_VERIFICATION']
summary = {
    'schema': 'credproof.revision-run-summary/v1', 'tested_source_commit': freeze['tested_source_commit'],
    'run_kind': 'ONE_REAL_LOCAL_MODEL_TASK', 'task': freeze['task'], 'model': freeze['model'],
    'freeze': 'freeze.json', 'actual': {'model_requests': len(requests), 'responses': len(responses),
        'server_usage_records': len(model.get('usage', [])), 'model_tool_requests': len(tools),
        'accepted_candidates': len(accepted), 'program_auto_verifications': len(accepted),
        'format_corrections': model.get('format_correction_attempts'), 'exports': 0,
        'new_directory_rechecks': 0, 'elapsed_s': result.get('elapsed_s'), 'paid_api_used': False},
    'candidate_results': [{'candidate': t['result']['candidate'], 'sha256': t['result']['candidate_sha256'],
         'verdict': t['result']['verification']['report']['verdict'],
         'failed_checks': t['result']['verification']['report']['confirmed_failed_checks']}
         for t in accepted],
    'termination': {'status': result['status'], 'task_status': result['task_status'],
         'last_result': tools[-1]['result'], 'model_error': model.get('error')},
    'handoff_status': 'NOT_READY_FOR_HANDOFF',
    'interpretation': 'Candidate FAIL was supplied; subsequent read/evidence calls were rejected by revision phase. No materially revised second candidate was submitted. Budget was not exhausted. No retry.',
    'pre_model_blocked_attempt': 'pre-model-blocked.json; WSL sandbox access denied; model requests=0, not model failure',
}
emit('summary.json', summary)
for label in ['protocol-preflight', 'protocol-preflight-final']:
    for p in sorted((base/label).glob('*.json')):
        emit(label+'/'+p.name, json.loads(p.read_text(encoding='utf-8-sig')), p)
emit('derivation-receipt.json', {'transforms': ['JSON structural redaction', 'LF UTF8',
     'exact host prefix mapping', 'CP_LAB runtime synthetic values redacted'],
     'source_records_preserved': True, 'records': records})
manifest = {p.relative_to(dest).as_posix(): {'sha256': digest(p.read_bytes()), 'bytes': p.stat().st_size}
            for p in dest.rglob('*') if p.is_file()}
emit('manifest.json', {'schema': 'credproof.public-evidence-manifest/v1', 'files': manifest,
     'excludes_self': True})
print(json.dumps(summary, ensure_ascii=False, indent=2))
