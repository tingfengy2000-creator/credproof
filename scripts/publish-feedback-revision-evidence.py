"""Publish exact-prefix-redacted evidence of the one closed linked revision.

No model requests, candidate execution, or verdict calculation occur here.
"""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import xml.etree.ElementTree as ET


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--installation', type=Path, required=True)
    parser.add_argument('--ledger', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    run = args.installation/'data/runs/linked-feedback-20261010/output'
    local = repo/'_runs/feedback-revision-20261010'
    prior = repo/'docs/reusable-tool-safety/acceptance/20261010-format-normalized'
    public = args.output/'public-evidence'
    public.mkdir(parents=True, exist_ok=True)
    if any(public.iterdir()):
        raise ValueError('refusing_to_overwrite_public_evidence')
    mappings = [(str(args.installation), '<INSTALL>'), (str(args.ledger.parent), '<LOCAL_LEDGER>'),
                (str(repo), '<REPOSITORY>'), ('/home/tingfeng', '<RUNTIME_USER_HOME>'),
                (r'C:\Users\Administrator', '<HOST_USER>'),
                ('/比赛/CredProof-dev34-install', '<INSTALL>'),
                ('9p E:\\\\134 ', '9p REDACTED_DRIVE '), ('path=E:\\\\;', 'path=REDACTED_DRIVE;'),
                (r'9p E:\134 ', '9p REDACTED_DRIVE '), (r'path=E:\;', 'path=REDACTED_DRIVE;'),
                (os.environ.get('COMPUTERNAME', 'UNSET_HOST'), 'REDACTED_HOST')]
    expanded = []
    for prefix, replacement in mappings:
        expanded.extend([(json.dumps(prefix, ensure_ascii=False)[1:-1], replacement),
                         (prefix, replacement), (prefix.replace('\\', '/'), replacement)])
    sources = []

    def redact(value):
        if isinstance(value, str):
            for prefix, replacement in expanded:
                value = value.replace(prefix, replacement)
            return value
        if isinstance(value, list):
            return [redact(v) for v in value]
        if isinstance(value, dict):
            return {redact(k): redact(v) for k, v in value.items()}
        return value

    def write(name, data):
        if isinstance(data, dict) or isinstance(data, list):
            data = json.dumps(redact(data), ensure_ascii=False, indent=2)+'\n'
        if isinstance(data, str):
            data = redact(data).replace('\r\n', '\n').encode('utf8')
        if re.search(rb'CP_(?:LAB|EXEC)_[0-9a-fA-F]{6,}', data):
            raise ValueError('synthetic_secret_or_fragment:' + name)
        # VmPTE:\\t in /proc status is not a Windows drive path.
        if re.search(rb'(?<![A-Za-z])E:\\', data) or b'C:\\Users\\' in data or b'/home/tingfeng' in data:
            raise ValueError('private_prefix_unmapped:' + name)
        target = public/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return data

    def derivative(path, name):
        raw = path.read_bytes()
        text = raw.decode('utf-8-sig')
        if path.suffix == '.xml':
            tree = ET.fromstring(text)
            for node in tree.iter():
                node.attrib = {k: redact(v) for k,v in node.attrib.items()}
                if node.text:
                    node.text = redact(node.text)
                if node.tail:
                    node.tail = redact(node.tail)
            data = write(name, ET.tostring(tree, encoding='utf-8'))
        else:
            data = write(name, json.loads(text) if path.suffix == '.json' else text)
        sources.append({'source': str(path), 'public_path': name, 'raw_sha256': digest(raw),
                        'raw_bytes': len(raw), 'public_sha256': digest(data), 'public_bytes': len(data)})

    derivative(run/'repair.json', 'repair.json')
    derivative(run/'origin.json', 'origin.json')
    for path in sorted((run/'repair-artifacts/model-work/model-trace').glob('*.json')):
        derivative(path, 'model-trace/'+path.name)
    for path in sorted((run/'repair-artifacts/verification-history').glob('*')):
        if path.is_file():
            derivative(path, 'verification-history/'+path.name)
    for path in sorted((run/'repair-artifacts/rpc').glob('*.json')):
        derivative(path, 'rpc/'+path.name)
    for name in ('boundary-probe.json', 'service-boundary.json', 'model-show.json',
                 'structured-api-service.json', 'ollama-stderr.txt', 'model-result.json'):
        derivative(run/'repair-artifacts/model-work'/name, 'runtime/'+name)
    derivative(run/'repair-artifacts/boundary-plan.json', 'runtime/boundary-plan.json')
    for name in ('result.json', 'original.py', 'final-candidate.py', 'initial-evidence.json'):
        derivative(run/'comparison/p01/C-agent'/name, 'page-record/'+name)
    for name in ('registration.json', 'registration.claim.json', 'registration.claim.result.json'):
        derivative(args.ledger/name, name)
    for name in ('preflight-budget.json', 'preflight-payload.json', 'installed-parser-replay.json',
                 'install.json', 'installed-page-view.json', 'formal-command.txt', 'formal-exit.txt',
                 'protocol.txt', 'protocol-junit.xml', 'protocol-privileged.txt',
                 'protocol-privileged-junit.xml', 'wheel-build.txt'):
        derivative(local/name, 'installation-and-protocol/'+name)
    derivative(prior/'report.raw.json', 'source-report.json')
    for name in ('credproof.toml', 'tests/test_business.py', 'tool.py'):
        derivative(args.installation/'data/examples/material_assistant'/name, 'source-project/'+name)
    before = (run/'comparison/p01/C-agent/original.py').read_text(encoding='utf8')
    after = (run/'comparison/p01/C-agent/final-candidate.py').read_text(encoding='utf8')
    write('candidate.diff', ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
          fromfile='source-candidate.py', tofile='feedback-candidate.py')))
    repair = json.loads((run/'repair.json').read_text(encoding='utf8'))
    report = json.loads((run/'repair-artifacts/verification-history/verification-01.json').read_text(encoding='utf8'))
    obs = report['execution']['pytest_observation']
    model = repair['model']
    trace = repair['program_trace']
    accepted = [x for x in trace if x['operation'] == 'submit_patch' and x['result'].get('status') == 'ACCEPTED_FOR_VERIFICATION']
    verifications = [x for x in trace if x['operation'] == 'program_auto_verify']
    # The executor logs auto-verification separately inside accepted results.
    verify_count = len(verifications) or sum('verification' in x['result'] for x in accepted)
    assert model['model_calls'] == 1 and len(accepted) == 1 and verify_count == 1
    assert report['verdict'] == 'FAIL'
    summary = {'kind': 'NEW_FEEDBACK_REVISION_LINKED_TO_HISTORICAL_CANDIDATE',
               'tested_source_commit': '18533454be948d23fc28236aa4070d63e2e3b289',
               'version': '0.3.0.dev34', 'parent_result': 'UNKNOWN unchanged',
               'parent_format_recheck': 'FAIL unchanged', 'model': repair['model_profile'],
               'model_calls': model['model_calls'], 'usage_records': len(model['usage']),
               'generations': model['generations'], 'format_corrections': model['format_correction_attempts'],
               'native_tool_requests': model['native_tool_requests'], 'accepted_candidates': len(accepted),
               'program_auto_verifications': verify_count, 'program_actions': len(trace),
               'task_status': repair['task_status'], 'candidate_verdict': report['verdict'],
               'failed_checks': report['failed_checks'], 'pytest_exit_code': report['execution']['pytest_exit_code'],
               'pytest': {k: obs[k] for k in ('collected', 'executed', 'passed', 'failed', 'skipped')},
               'scenarios': report['execution']['entry_scenarios'],
               'credential_leaks': report['execution']['credential_leaks'],
               'diagnosis': 'Only import os was removed. New NameError occurs before file/service access. urllib reference and HTTPError conversion remain unchanged.',
               'format_reception': 'installed unified parser and host boundary integrated; raw code and receipts retained',
               'bundle_export': 'NOT_EXECUTED: candidate FAIL', 'public_pass_recheck': 'NOT_EXECUTED: candidate FAIL',
               'handoff_status': 'NOT_READY_FOR_HANDOFF', 'round_closed': True}
    write('summary.json', summary)
    write('derivation.json', {'schema': 'credproof.public-derivation/v1', 'files': sources,
          'mapping': [{'prefix': a if not a.startswith(('E:', 'C:', '/home/')) else 'private exact prefix',
                       'replacement': b} for a,b in mappings],
          'policy': 'Exact known host prefixes and hostname only; JSON reserialization/LF publication. No broad path regex, no code semantic edit. Raw sources retained. Raw/public hashes and byte counts are different fields.'})
    for path in public.rglob('*.json'):
        json.loads(path.read_text(encoding='utf8'))
    for path in public.rglob('*.xml'):
        ET.parse(path)
    write('manifest.json', {'schema': 'credproof.public-evidence-manifest/v1', 'files': [
        {'path': p.relative_to(public).as_posix(), 'bytes': len(p.read_bytes()), 'sha256': digest(p.read_bytes())}
        for p in sorted(public.rglob('*')) if p.is_file()]})
    print(json.dumps({'files': len(sources), 'model_calls': model['model_calls'], 'candidate_verdict': report['verdict']}))


if __name__ == '__main__':
    main()
