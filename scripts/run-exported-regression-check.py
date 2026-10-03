"""Move the generated pytest regression into disposable external projects."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
import types
import runpy
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_pilot.runtime_config import runtime_temp_root


def run_case(root: Path, *, mutate=None) -> dict:
    if mutate:
        mutate(root)
    env = dict(__import__('os').environ)
    env['CREDPROOF_PROJECT_ROOT'] = str(root)
    # The exported file is a pytest assertion.  Invoke that assertion directly
    # so this check only needs the package and the reviewed WSL runtime; a host
    # pytest installation is not silently treated as part of the isolation.
    pytest_stub = types.ModuleType('pytest')
    pytest_stub.mark = types.SimpleNamespace(credproof_safety=lambda function: function)
    pytest_stub.skip = lambda message: (_ for _ in ()).throw(RuntimeError(message))
    stdout, stderr = __import__('io').StringIO(), __import__('io').StringIO()
    try:
        with patch.dict(__import__('os').environ, env, clear=True), patch.dict(sys.modules, {'pytest': pytest_stub}):
            generated = runpy.run_path(str(root / 'tests/credproof-regression/test_credproof_safety.py'))
            generated['test_credproof_safety_regression']()
        return {'execution_mode': 'direct_exported_assertion', 'returncode': 0,
                'stdout': stdout.getvalue(), 'stderr': stderr.getvalue(), 'pass': True}
    except Exception as exc:
        return {'execution_mode': 'direct_exported_assertion', 'returncode': 1,
                'stdout': stdout.getvalue(), 'stderr': stderr.getvalue(),
                'exception_type': type(exc).__name__, 'exception': str(exc), 'pass': False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('refuse to overwrite output')
    args.output.mkdir(parents=True)
    root = Path(__file__).resolve().parents[1] / 'examples/external/reusable-consumer-fixture'
    runtime_temp_root().mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='credproof-exported-', dir=runtime_temp_root()) as tmp_name:
        tmp = Path(tmp_name)
        broken = tmp / 'reintroduced-defect'
        unrelated = tmp / 'unrelated-change'
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
            'external_fixed': run_case(root),
            'reintroduced_defect': run_case(broken, mutate=break_guard),
            'unrelated_change': run_case(unrelated, mutate=add_unrelated),
        }
    summary = {'schema': 'credproof.safety.exported-regression/v1',
               'project': 'examples/external/reusable-consumer-fixture',
               'results': {name: {'returncode': row['returncode'], 'pass': row['pass']}
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
