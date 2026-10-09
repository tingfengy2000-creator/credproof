"""Structural public derivatives of one saved recheck; never runs a check/model."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import xml.etree.ElementTree as ET


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--installation', type=Path, required=True)
    parser.add_argument('--project', type=Path, required=True)
    args = parser.parse_args()
    public = args.evidence / 'public-evidence'
    public.mkdir(exist_ok=False)
    repo = Path(__file__).resolve().parents[1]
    mappings = [(str(args.installation.resolve()), '<INSTALL>'),
                (str(args.project.resolve().parent), '<POSTHOC_WORKSPACE>'),
                (str(repo), '<REPOSITORY>')]
    hostname = os.environ.get('COMPUTERNAME')
    if hostname:
        # Plain attribute-safe text also keeps the JUnit XML parseable.
        mappings.append((hostname, 'REDACTED_HOST'))
    sources = []

    def redact(value):
        if isinstance(value, str):
            for prefix, target in mappings:
                value = value.replace(prefix, target).replace(prefix.replace('\\', '/'), target)
            return value
        if isinstance(value, list):
            return [redact(v) for v in value]
        if isinstance(value, dict):
            return {redact(k): redact(v) for k, v in value.items()}
        return value

    def write(name, data):
        if re.search(rb'CP_LAB_[A-Fa-f0-9]{6,}', data):
            raise ValueError('synthetic_value_or_fragment_not_redacted:' + name)
        if b'E:\\' in data or b'C:\\Users\\' in data:
            raise ValueError('unmapped_private_path:' + name)
        dst = public / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(data)

    def derivative(path, name, kind):
        raw = path.read_bytes()
        if kind == 'json':
            data = (json.dumps(redact(json.loads(raw.decode('utf-8-sig'))), ensure_ascii=False, indent=2)+'\n').encode()
        else:
            data = redact(raw.decode('utf-8-sig')).replace('\r\n', '\n').encode()
        write(name, data)
        sources.append({'source': path.name if path.parent == args.evidence else name,
                        'public_path': name, 'raw_sha256': sha(raw), 'raw_bytes': len(raw),
                        'derived_sha256': sha(data), 'derived_bytes': len(data),
                        'transform': 'exact known host-prefix mapping; JSON reserialization / LF text publication; no code semantic edit'})

    for name in ('diagnosis', 'normalization', 'syntax', 'freeze'):
        derivative(args.evidence / (name+'.json'), name+'.json', 'json')
    for src, dst in [('report.raw.json', 'report.json'),
                     ('installed-origin.raw.json', 'installed-origin.json'),
                     ('execution-receipt.raw.json', 'execution-receipt.json')]:
        derivative(args.evidence / src, dst, 'json')
    for src, dst in [('original-code.txt', 'original-code.txt'),
                     ('normalized-candidate.py', 'normalized-candidate.py'),
                     ('normalization.diff', 'normalization.diff'),
                     ('protocol-junit.xml', 'protocol-junit.xml'),
                     ('protocol-pytest.txt', 'protocol-pytest.txt'),
                     ('check-command.raw.txt', 'check-command.txt')]:
        derivative(args.evidence / src, dst, 'text')
    for relative in ('credproof.toml', 'tests/test_business.py', 'tool.py'):
        derivative(args.project / relative, 'project/'+relative, 'text')
    original_artifacts = args.installation / 'data/runs/ui/live-c5e9217f868f4681a94bdda49c914e6e/output/repair-artifacts'
    derivative(original_artifacts / 'model-work/model-trace/model-01-response.json', 'original-model-response.json', 'json')
    derivative(original_artifacts / 'verification-history/verification-01.json', 'original-unknown-report.json', 'json')
    diagnosis = json.loads((args.evidence / 'diagnosis.json').read_text(encoding='utf-8-sig'))
    immutable = diagnosis['original_files']
    preserved = {name: sha((original_artifacts / value['source_relative']).read_bytes()) == value['sha256']
                 for name, value in immutable.items()}
    assert all(preserved.values())
    report = json.loads((public / 'report.json').read_text())
    observation = report['execution']['pytest_observation']
    junit = ET.parse(public / 'protocol-junit.xml').getroot().find('testsuite')
    summary = {
        'kind': 'POSTHOC_FORMAT_NORMALIZED_RECHECK', 'original_model_task_result': 'UNKNOWN',
        'new_model_calls': 0, 'derived_candidate_count': 1, 'dynamic_check_calls': 1,
        'check_exit_code': int((args.evidence / 'check-exit.txt').read_text().strip()),
        'derived_verdict': report['verdict'], 'failed_checks': report.get('failed_checks'),
        'pytest': {k: observation[k] for k in ('collected', 'executed', 'passed', 'failed', 'skipped',
                                               'required_tests_completed', 'required_tests_passed')},
        'entry_scenarios': [{'name': s['name'], 'expected_error': s['expected_error'],
                            'actual_error': s['raised'], 'returned': s['entry_returned'],
                            'receipts': s['request_observations']} for s in report['execution']['entry_scenarios']],
        'credential_leaks': report['execution']['credential_leaks'],
        'access_summary': report['execution']['access_summary'],
        'protocol_tests': {'tests': int(junit.get('tests')), 'failures': int(junit.get('failures')),
                           'errors': int(junit.get('errors')), 'skipped': int(junit.get('skipped')), 'exit_code': 0,
                           'scope': 'format/syntax protocol only; not model or safety task success'},
        'original_files_unchanged': preserved,
        'installed_parser_integration': 'NOT_PERFORMED: posthoc FAIL stops this round; installed dev33 unchanged',
        'bundle_export': 'NOT_PERFORMED: no PASS', 'public_pass_recheck': 'NOT_PERFORMED: no PASS',
        'historical_response_inspection': 'strict JSON parser replay only; no inference or page success',
        'handoff_status': 'NOT_READY_FOR_HANDOFF', 'round_closed': True,
    }
    write('summary.json', (json.dumps(summary, ensure_ascii=False, indent=2)+'\n').encode())
    derivation = {'schema': 'credproof.public-derivation/v1', 'files': sources,
                  'redaction': 'Known absolute installation/workspace/repository prefixes and host name only. No broad path regex or code substitution. Original raw files retained locally.',
                  'synthetic_values': 'check_project redacted full values/abbreviations; additional full-value/fragment scan passed.',
                  'hash_policy': 'Raw and public derivative hashes separate. All public text published as UTF-8 LF. project files are evidence snapshots, not an exported PASS bundle.',
                  'original_immutability_check': preserved}
    write('derivation.json', (json.dumps(derivation, ensure_ascii=False, indent=2)+'\n').encode())
    print(json.dumps({'public_files': len(list(public.rglob('*'))), 'verdict': report['verdict'],
                      'model_calls': 0, 'original_preserved': all(preserved.values())}))


if __name__ == '__main__':
    main()
