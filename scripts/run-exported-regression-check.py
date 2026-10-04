"""Move the generated pytest regression into disposable external projects."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import subprocess
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_pilot.runtime_config import runtime_temp_root


def _junit_counts(path: Path) -> dict:
    if not path.is_file():
        return {"available": False, "reason": "junitxml_missing"}
    root = ET.parse(path).getroot()
    suites = [root] if root.tag.endswith('testsuite') else list(root.iter('testsuite'))
    def total(name):
        return sum(int(s.attrib.get(name, 0)) for s in suites)
    return {
        "available": True,
        "tests": total("tests"),
        "failures": total("failures"),
        "errors": total("errors"),
        "skipped": total("skipped"),
    }


def run_case(root: Path, *, mutate=None, repo_root: Path) -> dict:
    if mutate:
        mutate(root)
    env = dict(os.environ)
    env['CREDPROOF_PROJECT_ROOT'] = str(root)
    env['PYTHONPATH'] = os.pathsep.join([str(repo_root), env.get('PYTHONPATH', '')]).rstrip(os.pathsep)
    junit = root / '.credproof' / 'consumer-junit.xml'
    junit.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, '-m', 'pytest', '-q',
               'tests/credproof-regression/test_credproof_safety.py',
               f'--junitxml={junit}']
    try:
        process = subprocess.run(command, cwd=root, env=env, capture_output=True,
                                 text=True, timeout=180)
        return {'execution_mode': 'pytest_subprocess', 'command': command,
                'cwd_relative': root.name, 'returncode': process.returncode,
                'stdout': process.stdout, 'stderr': process.stderr,
                'test_counts': _junit_counts(junit),
                'pass': process.returncode == 0}
    except subprocess.TimeoutExpired as exc:
        return {'execution_mode': 'pytest_subprocess', 'command': command,
                'cwd_relative': root.name, 'returncode': None,
                'stdout': (exc.stdout or ''), 'stderr': (exc.stderr or ''),
                'test_counts': _junit_counts(junit), 'pass': False,
                'exception_type': 'TimeoutExpired'}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('refuse to overwrite output')
    args.output.mkdir(parents=True)
    repo_root = Path(__file__).resolve().parents[1]
    root = repo_root / 'examples/external/reusable-consumer-fixture'
    runtime_temp_root().mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='credproof-exported-', dir=runtime_temp_root()) as tmp_name:
        tmp = Path(tmp_name)
        fixed = tmp / 'fixed'
        broken = tmp / 'reintroduced-defect'
        unrelated = tmp / 'unrelated-change'
        shutil.copytree(root, fixed)
        shutil.copytree(root, broken)
        shutil.copytree(root, unrelated)
        def break_guard(copy_root):
            path = copy_root / 'tool.py'
            text = path.read_text(encoding='utf-8')
            needle = 'if not path.is_relative_to(allowed) or not path.is_file():'
            if needle not in text:
                raise RuntimeError('external fixture guard not found')
            path.write_text(text.replace(needle, 'if False:'), encoding='utf-8')
        def add_unrelated(copy_root):
            (copy_root / 'REVIEW-NOTE.txt').write_text('unrelated change\n', encoding='utf-8')
        results = {
            'external_fixed': run_case(fixed, repo_root=repo_root),
            'reintroduced_defect': run_case(broken, mutate=break_guard, repo_root=repo_root),
            'unrelated_change': run_case(unrelated, mutate=add_unrelated, repo_root=repo_root),
        }
    summary = {'schema': 'credproof.safety.exported-regression/v1',
               'project': 'examples/external/reusable-consumer-fixture',
               'results': {name: {'returncode': row['returncode'], 'pass': row['pass'],
                                  'test_counts': row.get('test_counts')}
                           for name, row in results.items()},
               'claim': 'The exported check was executed in a separate synthetic consumer fixture; no model or real credential was used.'}
    (args.output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for name, row in results.items():
        (args.output / (name + '.json')).write_text(json.dumps(row, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))
    expected = {'external_fixed': True, 'reintroduced_defect': False, 'unrelated_change': True}
    return 0 if all(results[key]['pass'] == value for key, value in expected.items()) else 2


if __name__ == '__main__':
    raise SystemExit(main())
