"""Run the published review instructions; write new records, never overwrite history."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pilot-repeats', type=int, default=3, choices=(1, 3))
    args = parser.parse_args()
    run = ROOT / 'runs/review-checks' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8])
    run.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
    # The review package must work without workspace-specific import/search paths.
    env.pop('PYTHONPATH', None)
    env.pop('PYTHONHOME', None)
    record = {'schema': 'credproof-review-reproduction/1',
              'started_at': datetime.now(timezone.utc).isoformat(),
              'environment': {'python': platform.python_version(), 'platform': platform.platform(),
                              'implementation': platform.python_implementation()},
              'historical_results_overwritten': False, 'commands': [], 'complete': False}

    def save():
        (run / 'reproduction.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    def execute(name, arguments, expected=0, python=True):
        command = ([sys.executable] if python else []) + arguments
        start = time.perf_counter()
        completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=300)
        # Preserve private originals locally; publish only a path-portable view of logs.
        stdout = completed.stdout.decode('utf-8', errors='replace')
        stderr = completed.stderr.decode('utf-8', errors='replace')
        def portable(text):
            for candidate in (str(ROOT), str(ROOT).replace('\\', '\\\\'), ROOT.as_posix()):
                text = text.replace(candidate, '<REVIEW_ROOT>')
            return text
        row = {'name': name, 'command': (['python'] if python else []) + arguments,
               'exit_code': completed.returncode, 'expected_exit_code': expected,
               'elapsed_seconds': round(time.perf_counter() - start, 3),
               'stdout': portable(stdout), 'stderr': portable(stderr),
               'log_transform': 'Only the extracted package absolute root is replaced by <REVIEW_ROOT>; statuses and messages unchanged.'}
        record['commands'].append(row)
        (run / (name + '-stdout.txt')).write_bytes(completed.stdout)
        (run / (name + '-stderr.txt')).write_bytes(completed.stderr)
        save()
        print(json.dumps({'step': name, 'exit_code': completed.returncode, 'expected': expected}), flush=True)
        if completed.returncode != expected:
            raise RuntimeError('Unexpected exit status in ' + name)
        return stdout, stderr

    try:
        output, _ = execute('git-version', ['git', '--version'], python=False)
        record['environment']['git'] = output.strip()
        exe = ROOT / '.tools/gitleaks-8.28.0' / ('gitleaks.exe' if sys.platform == 'win32' else 'gitleaks')
        if not exe.is_file():
            raise RuntimeError('Run python scripts/get_gitleaks.py first; missing scanners must not become skipped success')
        output, _ = execute('gitleaks-version', [str(exe.relative_to(ROOT)), 'version'], python=False)
        record['environment']['gitleaks'] = output.strip()
        env['CREDPROOF_GITLEAKS'] = str(exe)
        stdout, stderr = execute('unit-tests', ['-m', 'unittest', 'discover', '-s', 'tests', '-v'])
        combined = stdout + stderr
        if not re.search(r'Ran 10 tests\b', combined) or re.search(r'\bskipped\b', combined, re.I):
            raise RuntimeError('Expected all ten independent tests without skips')
        output, _ = execute('demo', ['scripts/demo.py', '--output', (run / 'demo').relative_to(ROOT).as_posix()])
        last = json.loads(output.strip().splitlines()[-1])
        bundle = Path(last['bundle']).resolve()
        if not bundle.is_relative_to(run) or not last['original_unchanged']:
            raise RuntimeError('Unexpected demo material or modified original')
        relative_bundle = bundle.relative_to(ROOT).as_posix()
        evidence = (bundle.parent / 'public/02-valid-repair-evidence.json').relative_to(ROOT).as_posix()
        execute('old-evidence', ['-m', 'credproof', 'validate-evidence', '--bundle', relative_bundle, '--evidence', evidence], expected=2)
        execute('fresh-drift-recheck', ['-m', 'credproof', 'recheck', '--bundle', relative_bundle], expected=1)
        good = (run / 'good-bundle').relative_to(ROOT).as_posix()
        source = (bundle.parent / 'source').relative_to(ROOT).as_posix()
        execute('new-good-copy', ['-m', 'credproof', 'freeze', '--repo', source, '--bundle', good, '--allow-fixture'])
        execute('fresh-good-recheck', ['-m', 'credproof', 'recheck', '--bundle', good])
        output, _ = execute('pilot-reproduction', ['experiments/pilot.py', '--gitleaks', exe.relative_to(ROOT).as_posix(),
                            '--output', (run / 'pilot').relative_to(ROOT).as_posix(), '--repeats', str(args.pilot_repeats)])
        outputs = sorted((run / 'pilot').glob('*/results.json'))
        if len(outputs) != 1:
            raise RuntimeError('Expected one complete new pilot record')
        result = json.loads(outputs[0].read_text(encoding='utf-8'))
        if not result['frozen_inputs_unchanged'] or result['summary']['case_count'] != 16:
            raise RuntimeError('Pilot provenance/count differs from documented review scope')
        record['new_pilot_results'] = outputs[0].relative_to(ROOT).as_posix()
        record['new_pilot_summary'] = result['summary']
        record['complete'] = True
    except Exception as error:
        record['error'] = {'type': type(error).__name__, 'message': str(error)}
        print(json.dumps(record['error']), flush=True)
    finally:
        record['completed_at'] = datetime.now(timezone.utc).isoformat()
        save()
        print(json.dumps({'record': (run / 'reproduction.json').relative_to(ROOT).as_posix(), 'complete': record['complete']}), flush=True)
    return 0 if record['complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
