"""Exactly one isolated original check using an installed interpreter (-I)."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import time
import traceback


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not sys.flags.isolated:
        raise RuntimeError('installed_interpreter_requires_I')
    import credproof_safety.project as project_module
    import credproof_safety.runner as runner_module
    import credproof_access
    import credproof_access.contract as contract
    freeze = json.loads((args.output / 'freeze.json').read_text(encoding='utf-8-sig'))
    for relative, detail in freeze['project_files'].items():
        assert sha(args.project / relative) == detail['sha256'], 'frozen_project_changed:' + relative
    modules = {'credproof_safety/project.py': project_module,
               'credproof_safety/runner.py': runner_module,
               'credproof_access/__init__.py': credproof_access,
               'credproof_access/contract.py': contract}
    origin = {'interpreter': sys.executable, 'python': sys.version,
              'cwd': str(Path.cwd()), 'isolated': bool(sys.flags.isolated),
              'distribution_version': importlib.metadata.version('credproof-safety'),
              'modules': {key: {'path': module.__file__, 'sha256': sha(Path(module.__file__))}
                          for key, module in modules.items()}}
    save(args.output / 'installed-origin.raw.json', origin)
    for key, module in modules.items():
        assert 'site-packages' in module.__file__, 'source_shadowing:' + key
        assert sha(Path(module.__file__)) == freeze['source_files'][key], 'checker_or_component_changed:' + key
    # Claim before dispatch. A crash cannot silently repeat the dynamic check.
    with (args.output / 'one-check.claim').open('x', encoding='utf8') as handle:
        handle.write('POSTHOC_FORMAT_NORMALIZED_RECHECK; check_calls=1; model_calls=0\n')
    started = time.monotonic()
    try:
        report = project_module.check_project(args.project / 'credproof.toml',
            project_root=args.project, output=args.output / 'report.raw.json')
    except Exception as exc:
        save(args.output / 'check-error.raw.json', {'type': type(exc).__name__, 'detail': str(exc),
            'traceback': traceback.format_exc(), 'check_calls': 1, 'model_calls': 0})
        raise
    exit_code = {'PASS': 0, 'FAIL': 2, 'UNKNOWN': 3}[report['verdict']]
    unchanged = {rel: sha(args.project / rel) == item['sha256']
                 for rel, item in freeze['project_files'].items()}
    save(args.output / 'execution-receipt.raw.json', {
        'kind': 'POSTHOC_FORMAT_NORMALIZED_RECHECK', 'model_calls': 0, 'check_calls': 1,
        'verdict': report['verdict'], 'reason': report.get('reason'), 'exit_code': exit_code,
        'elapsed_seconds': round(time.monotonic()-started, 3),
        'project_unchanged_after': unchanged, 'report_sha256': sha(args.output / 'report.raw.json'),
        'original_formal_task_conclusion': 'UNKNOWN (unchanged)',
        'installed_parser_integration': 'not attempted before posthoc result',
    })
    print(json.dumps({'kind': 'POSTHOC_FORMAT_NORMALIZED_RECHECK', 'verdict': report['verdict'],
                      'exit_code': exit_code, 'check_calls': 1, 'new_model_calls': 0}))
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
