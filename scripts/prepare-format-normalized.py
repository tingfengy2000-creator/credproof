"""Prepare a non-semantic derivation; no model calls or candidate execution."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_pilot.bounded_patch import parse_response
from agent_pilot.output_format import normalize_python_source, check_python_syntax


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--project', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if (args.output / 'normalization.json').exists() or args.project.exists():
        raise ValueError('refuse_existing_derivation')
    raw_path = args.artifacts / 'model-work/model-trace/model-01-response.json'
    old_path = args.artifacts / 'verification-history/candidate-01.py'
    report_path = args.artifacts / 'verification-history/verification-01.json'
    raw = raw_path.read_bytes()
    response = json.loads(raw.decode('utf-8-sig'))
    obj = parse_response(response)
    assert obj['action'] == 'PATCH'
    code = obj['code']
    candidate = old_path.read_bytes()
    # No implicit newline mapping: this task's saved candidate must be exact.
    assert candidate == code.encode('utf8'), 'saved_candidate_not_exact_code_field'
    old_report = json.loads(report_path.read_text(encoding='utf-8-sig'))
    assert old_report['verdict'] == 'UNKNOWN'
    files = {'model-response': raw_path, 'original-candidate': old_path,
             'original-unknown-report': report_path}
    diagnosis = {
        'kind': 'HISTORICAL_OUTPUT_INSPECTION', 'new_model_calls': 0,
        'original_task_id': 'live-c5e9217f868f4681a94bdda49c914e6e',
        'original_tested_source': 'a780b9e6543355c2108c1d41e43a8dccd7c2e0c1',
        'original_delivery': 'c956b1f7f050df6d9aa707ab71fb3fa9cff7fc31',
        'model': response['model'], 'strict_json_action': obj['action'],
        'fence_origin': 'original_model_code_field',
        'saved_candidate_equals_code_utf8_exactly': True,
        'original_code_sha256': sha(code.encode()), 'original_code_bytes': len(code.encode()),
        'original_files': {name: {'source_relative': str(path.relative_to(args.artifacts)).replace('\\', '/'),
            'sha256': sha(path.read_bytes()), 'bytes': path.stat().st_size} for name, path in files.items()},
        'old_verdict': old_report['verdict'], 'old_reason': old_report.get('reason'),
        'old_raised': old_report['execution'].get('raised'),
        'old_pytest_exit_code': old_report['execution']['pytest_exit_code'],
        'old_stop': 'STOPPED_UNKNOWN_VERIFICATION',
        'stop_source': 'credproof_safety/agent.py:_bounded_model_script; UNKNOWN branch',
        'explanation': 'JSON parser accepted a code string without compiling it; program auto verification returned UNKNOWN and terminated the generation loop. No budget is resumed.',
    }
    save(args.output / 'diagnosis.json', diagnosis)
    normalized, receipt = normalize_python_source(code)
    save(args.output / 'normalization.json', receipt)
    (args.output / 'original-code.txt').write_bytes(code.encode())
    (args.output / 'normalized-candidate.py').write_bytes(normalized.encode())
    diff = ''.join(difflib.unified_diff(code.splitlines(keepends=True), normalized.splitlines(keepends=True),
                                       fromfile='original-code-field', tofile='format-normalized-code'))
    (args.output / 'normalization.diff').write_bytes(diff.encode())
    syntax = check_python_syntax(normalized)
    save(args.output / 'syntax.json', {**syntax, 'model_calls': 0, 'python': sys.version})
    if syntax['status'] != 'VALID_SYNTAX':
        print(json.dumps(syntax)); return 2
    args.project.mkdir(parents=True, exist_ok=False)
    source_project = args.artifacts / 'candidate'
    copied = {}
    for relative in ('credproof.toml', 'tests/test_business.py', 'README.md'):
        src = source_project / relative
        dst = args.project / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())
        copied[relative] = {'sha256': sha(src.read_bytes()), 'bytes': src.stat().st_size,
                            'unchanged_from_original_candidate': True}
    (args.project / 'tool.py').write_bytes(normalized.encode())
    repo = Path(__file__).resolve().parents[1]
    source_head = subprocess.check_output(['git', '-c', 'safe.directory='+repo.as_posix(),
        'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    source_files = ('agent_pilot/output_format.py', 'scripts/prepare-format-normalized.py',
                    'scripts/run-format-normalized-check.py', 'credproof_safety/project.py',
                    'credproof_safety/runner.py', 'credproof_access/__init__.py', 'credproof_access/contract.py')
    save(args.output / 'freeze.json', {
        'kind': 'POSTHOC_FORMAT_NORMALIZED_RECHECK', 'new_model_calls': 0,
        'check_calls_allowed': 1, 'baseline_head': source_head,
        'rule_sha256': sha((args.output / 'normalization-rule.md').read_bytes()),
        'source_files': {p: sha((repo / p).read_bytes()) for p in source_files},
        'source_note': 'New normalization/helpers may be uncommitted at preparation; exact file digests are frozen. Original checker and installed dev33 remain unchanged.',
        'original_immutable_files': diagnosis['original_files'],
        'project_files': {**copied, 'tool.py': {'sha256': sha(normalized.encode()), 'bytes': len(normalized.encode()),
                                               'source': 'model_generated_then_format_normalized'}},
        'constraints': 'Same original component, policy, tests, scenes and checker; no model, no business edits, no retries.',
    })
    print(json.dumps({'status': 'PREPARED', 'syntax': syntax['status'],
                      'normalized_sha256': receipt['normalized_code_sha256'], 'model_calls': 0}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
