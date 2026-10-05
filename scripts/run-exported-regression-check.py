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


def _read_generated_report(root: Path) -> dict:
    reports = sorted((root / '.credproof').glob('consumer-report-*.json'))
    if len(reports) != 1:
        return {'available': False, 'reason': 'generated_report_count', 'count': len(reports)}
    try:
        report = json.loads(reports[0].read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {'available': False, 'reason': 'generated_report_invalid'}
    if not isinstance(report, dict) or report.get('schema') != 'credproof.safety.report/v1':
        return {'available': False, 'reason': 'generated_report_schema'}
    verdict = report.get('verdict')
    failed_checks = report.get('failed_checks')
    if verdict not in {'PASS', 'FAIL', 'UNKNOWN'} or not isinstance(failed_checks, list):
        return {'available': False, 'reason': 'generated_report_shape'}
    return {'available': True, 'path': reports[0].name, 'verdict': verdict,
            'failed_checks': [str(item) for item in failed_checks]}


def run_case(root: Path, *, mutate=None, repo_root: Path,
             expected_verdict: str, expected_failure_check: str | None = None) -> dict:
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
        counts = _junit_counts(junit)
        report = _read_generated_report(root)
        complete_test = (counts.get('available') is True and counts.get('tests') == 1
                         and counts.get('skipped', 0) == 0 and counts.get('errors', 0) == 0)
        report_matches = (report.get('available') is True and report.get('verdict') == expected_verdict
                          and (expected_failure_check is None or expected_failure_check in report.get('failed_checks', [])))
        if not complete_test:
            verification_status = 'INCOMPLETE_OR_SKIPPED' if counts.get('available') else 'ENVIRONMENT_FAILURE'
            verified = False
        elif not report.get('available'):
            verification_status = 'ENVIRONMENT_FAILURE'
            verified = False
        elif not report_matches:
            verification_status = 'REPORT_MISMATCH'
            verified = False
        elif expected_verdict == 'PASS' and process.returncode == 0:
            verification_status = 'PASS'
            verified = True
        elif expected_verdict == 'FAIL' and process.returncode != 0:
            verification_status = 'EXPECTED_SECURITY_FAILURE'
            verified = True
        elif expected_verdict == 'PASS':
            verification_status = 'TEST_FAILURE'
            verified = False
        else:
            verification_status = 'EXPECTED_FAILURE_NOT_OBSERVED'
            verified = False
        if not counts.get('available'):
            verification_status = 'ENVIRONMENT_FAILURE'
        return {'execution_mode': 'pytest_subprocess', 'command': command,
                'cwd_relative': root.name, 'returncode': process.returncode,
                'stdout': process.stdout, 'stderr': process.stderr,
                'test_counts': counts, 'generated_report': report,
                'expected_report_verdict': expected_verdict,
                'expected_failure_check': expected_failure_check,
                'verification_status': verification_status,
                'regression_verified': verified,
                'pass': expected_verdict == 'PASS' and verified}
    except subprocess.TimeoutExpired as exc:
        return {'execution_mode': 'pytest_subprocess', 'command': command,
                'cwd_relative': root.name, 'returncode': None,
                'stdout': (exc.stdout or ''), 'stderr': (exc.stderr or ''),
                'test_counts': _junit_counts(junit), 'generated_report': _read_generated_report(root),
                'expected_report_verdict': expected_verdict,
                'expected_failure_check': expected_failure_check,
                'verification_status': 'ENVIRONMENT_FAILURE', 'regression_verified': False, 'pass': False,
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
            'external_fixed': run_case(fixed, repo_root=repo_root, expected_verdict='PASS'),
            'reintroduced_defect': run_case(broken, mutate=break_guard, repo_root=repo_root,
                                            expected_verdict='FAIL', expected_failure_check='no_forbidden_file_read'),
            'unrelated_change': run_case(unrelated, mutate=add_unrelated, repo_root=repo_root,
                                         expected_verdict='PASS'),
        }
    summary = {'schema': 'credproof.safety.exported-regression/v2',
               'project': 'examples/external/reusable-consumer-fixture',
               'results': {name: {'returncode': row['returncode'], 'pass': row['pass'],
                                  'regression_verified': row.get('regression_verified'),
                                  'verification_status': row.get('verification_status'),
                                  'test_counts': row.get('test_counts'),
                                  'generated_report': row.get('generated_report'),
                                  'expected_report_verdict': row.get('expected_report_verdict'),
                                  'expected_failure_check': row.get('expected_failure_check')}
                           for name, row in results.items()},
               'claim': 'The exported check was executed in a separate synthetic consumer fixture; pytest execution and a newly generated internal safety report were checked; no model or real credential was used.'}
    (args.output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for name, row in results.items():
        (args.output / (name + '.json')).write_text(json.dumps(row, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if all(results[key].get('regression_verified') is True for key in results) else 2


if __name__ == '__main__':
    raise SystemExit(main())
