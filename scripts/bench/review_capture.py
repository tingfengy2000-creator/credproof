"""Capture frozen preflight scripts without changing their checker or protocol.

The wrapper saves full reports otherwise discarded by validate_targets.py.
It does not change prompts, options, extraction, verdicts or control inputs.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import io
import json
from pathlib import Path
import platform
import runpy
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import check_variant


class Tee(io.TextIOBase):
    def __init__(self, stream):
        self.stream, self.parts = stream, []

    def write(self, value):
        self.parts.append(value)
        self.stream.write(value)
        self.stream.flush()
        return len(value)

    def flush(self):
        self.stream.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('script', choices=['validate_targets', 'recheck_history'])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    receipt = args.output.with_name(args.output.name+'-execution')
    if receipt.exists() or args.output.exists():
        raise SystemExit('refuse to overwrite run evidence')
    receipt.mkdir(parents=True)
    original = check_variant.check
    calls = []

    def recorded_check(target, source, label=''):
        report, record = original(target, source, label)
        index = len(calls)+1
        name = f'{index:03d}.report.json'
        (receipt/name).write_text(json.dumps(report, ensure_ascii=False, indent=1)+'\n', encoding='utf8')
        calls.append({'index': index, 'target': str(target), 'source': str(source),
                      'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                      'label': label, 'record': record, 'report': name})
        return report, record

    check_variant.check = recorded_check
    out, err = Tee(sys.stdout), Tee(sys.stderr)
    script = HERE/(args.script+'.py')
    command = [sys.executable, '-I', str(script.relative_to(ROOT)), '--output', str(args.output)]
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    clock = time.monotonic()
    exit_code = 0
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            sys.argv = command[2:]
            runpy.run_path(str(script), run_name='__main__')
    except SystemExit as exc:
        exit_code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    except Exception:
        import traceback
        traceback.print_exc(file=err)
        exit_code = 1
    finally:
        check_variant.check = original
    commit = subprocess.run(['git', '-c', f'safe.directory={ROOT.as_posix()}', 'rev-parse', 'HEAD'],
                            cwd=ROOT, capture_output=True, text=True).stdout.strip()
    value = {'kind': 'WINDOWS_REAL_ISOLATED_PREFLIGHT', 'script_source_commit': commit,
             'script_sha256': hashlib.sha256(script.read_bytes()).hexdigest(),
             'wrapper_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             'equivalent_command': command, 'actual_wrapper': [sys.executable, '-I', *sys.orig_argv[2:]],
             'python': platform.python_version(), 'platform': platform.platform(),
             'started_at': started, 'seconds': round(time.monotonic()-clock, 3), 'exit_code': exit_code,
             'new_model_calls': 0, 'checks': calls, 'stdout': ''.join(out.parts), 'stderr': ''.join(err.parts)}
    (receipt/'command.json').write_text(json.dumps(value, ensure_ascii=False, indent=1)+'\n', encoding='utf8')
    raise SystemExit(exit_code)


if __name__ == '__main__':
    main()
