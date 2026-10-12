"""Run the unmodified bench-v1 scripts through a restricted local transport.

Only the HTTP transport is bridged into the existing GPU/bubblewrap profile.
The frozen scripts still construct all prompts, options, patches and verdicts.
No retry, download, reference repair injection or native model tool execution.
"""
from __future__ import annotations
import argparse
import hashlib
import http.server
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
import common
from agent_pilot.model_config import PROFILES
from agent_pilot.runtime_config import execution_runtime_paths, load_config, wsl_prefix

MODELS = [PROFILES[k]['name'] for k in ('qwen25', 'qwen3')]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1)+'\n', encoding='utf8', newline='\n')


def wsl_path(path):
    path = path.resolve()
    return '/mnt/'+path.drive.rstrip(':').lower()+path.as_posix()[2:]


class Bridge:
    def __init__(self, rpc, evidence, supervisor):
        self.rpc, self.evidence, self.supervisor = rpc, evidence, supervisor
        self.lock = threading.Lock()
        self.phase, self.maximum, self.inferences, self.sequence = 'generation', 96, 0, 0
        self.totals = {'generation': 0, 'judge': 0}

    def forward(self, method, path, body):
        with self.lock:
            if (method, path) not in {('POST', '/api/chat'), ('POST', '/api/show')}:
                return 403, b'{"error":"unsupported bridge route"}'
            try:
                data = json.loads(body)
                if not isinstance(data, dict) or data.get('model') not in MODELS:
                    raise ValueError('unpinned model')
                if path == '/api/show':
                    if set(data) != {'model'}:
                        raise ValueError('unexpected show fields')
                else:
                    expected = common.GEN_OPTIONS if self.phase == 'generation' else common.JUDGE_OPTIONS
                    opts = dict(data.get('options') or {})
                    if self.phase == 'generation':
                        if opts.pop('seed', None) not in (1, 2, 3):
                            raise ValueError('unexpected generation seed')
                    if (opts != expected or set(data) != {'model', 'messages', 'stream', 'options'}
                            or data['stream'] is not False or not isinstance(data['messages'], list)
                            or len(data['messages']) != 1 or set(data['messages'][0]) != {'role', 'content'}
                            or data['messages'][0]['role'] != 'user'
                            or not isinstance(data['messages'][0]['content'], str)):
                        raise ValueError('frozen request protocol mismatch')
                    if self.inferences >= self.maximum:
                        raise ValueError('registered inference budget exhausted')
            except (TypeError, ValueError, KeyError) as exc:
                return 400, json.dumps({'error': str(exc)}).encode()
            if path == '/api/chat':
                self.inferences += 1
                self.totals[self.phase] += 1
                write(self.evidence/'inference-ledger.json', {'phase': self.phase, 'counts': self.totals,
                                                             'maximum_this_phase': self.maximum})
            self.sequence += 1
            key = f'{self.sequence:04d}'
            payload = {'method': method, 'path': path, 'body': body.decode('utf8')}
            write(self.rpc/f'request-{key}.json', payload)
            write(self.evidence/'transport'/f'{key}.request.json',
                  {'phase': self.phase, 'method': method, 'path': path,
                   'raw_body_utf8': body.decode('utf8'), 'body_bytes': len(body),
                   'body_sha256': hashlib.sha256(body).hexdigest()})
            response = self.rpc/f'response-{key}.json'
            deadline = time.monotonic()+(615 if path == '/api/chat' else 30)
            while time.monotonic() < deadline:
                if self.supervisor.poll() is not None:
                    return 502, b'{"error":"isolated model supervisor exited"}'
                try:
                    result = json.loads(response.read_text(encoding='utf8'))
                except (OSError, ValueError):
                    time.sleep(.025); continue
                write(self.evidence/'transport'/f'{key}.response.json', result)
                if path == '/api/chat':
                    raw = json.loads(result['body'])
                    print(json.dumps({'phase': self.phase, 'count': self.inferences, 'model': data['model'],
                                      'status': result['status'], 'seconds': round(result['seconds'], 2),
                                      'prompt_eval_count': raw.get('prompt_eval_count'),
                                      'eval_count': raw.get('eval_count')}, ensure_ascii=False), flush=True)
                return result['status'], result['body'].encode('utf8')
            write(self.evidence/'transport'/f'{key}.bridge-timeout.json',
                  {'phase': self.phase, 'reason': 'RPC response not received before transport deadline',
                   'server_cancel_confirmed': False})
            return 504, b'{"error":"isolated transport deadline exceeded"}'


class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get('Content-Length', '0'))
        if self.path not in ('/api/chat', '/api/show') or not 0 < length <= 256*1024:
            code, body = 400, b'{"error":"unsupported path or body size"}'
        else:
            code, body = self.server.bridge.forward('POST', self.path, self.rfile.read(length))
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--private-work', type=Path, required=True)
    args = parser.parse_args()
    if args.run.exists() or args.evidence.exists() or args.private_work.exists():
        raise SystemExit('new run, evidence and private-work directories required; no restart/resampling')
    args.evidence.mkdir(parents=True)
    args.private_work.mkdir(parents=True)
    stage, rpc = args.private_work/'stage', args.private_work/'rpc'
    stage.mkdir(); rpc.mkdir()
    (stage/'isolated_worker.py').write_bytes((HERE/'isolated_worker.py').read_bytes())
    commit = subprocess.run(['git', '-c', f'safe.directory={ROOT.as_posix()}', 'rev-parse', 'HEAD'],
                            cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    files = [*HERE.glob('*.py'), *(ROOT/'docs/bench/prompts').glob('*.md')]
    registration = {'kind': 'PRE_REGISTERED_BENCH_V1_WINDOWS', 'source_commit': commit,
                    'run': str(args.run), 'models': [PROFILES[k] for k in ('qwen25', 'qwen3')],
                    'generation_options': common.GEN_OPTIONS, 'judge_options': common.JUDGE_OPTIONS,
                    'samples': common.SAMPLES, 'generation_maximum': 96, 'judge_maximum': 224,
                    'request_timeout_seconds': 600, 'supervisor_timeout_seconds': 200000,
                    'new_model_probes': 0, 'native_tool_calls': 0, 'retries': 0,
                    'file_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                    'note': 'Only transport differs. Frozen generate.py/judge.py/common.py and prompts are unchanged.'}
    write(stage/'registration.json', registration)
    write(args.evidence/'registration.json', registration)
    sentinel = args.private_work/'host-sentinel.txt'
    sentinel.write_text('Harmless model isolation marker; not a credential.\n')
    config = load_config()
    runtime = execution_runtime_paths(config)
    command = [*wsl_prefix(config), '--exec', runtime['python'], wsl_path(HERE/'isolated_service.py'),
               runtime['root'], wsl_path(stage), wsl_path(args.private_work), wsl_path(rpc), wsl_path(sentinel)]
    stdout = (args.private_work/'supervisor-stdout.txt').open('wb')
    stderr = (args.private_work/'supervisor-stderr.txt').open('wb')
    supervisor = subprocess.Popen(command, stdout=stdout, stderr=stderr)
    server = None
    result = {'source_commit': commit, 'generation_exit_code': None, 'judge_exit_code': None}
    try:
        deadline = time.monotonic()+90
        while not (rpc/'ready.json').exists():
            if supervisor.poll() is not None or time.monotonic() >= deadline:
                raise RuntimeError('isolated model service not ready; no model request started')
            time.sleep(.1)
        ready = json.loads((rpc/'ready.json').read_text(encoding='utf8'))
        if not ready['boundary']['passed']:
            raise RuntimeError('model boundary not verified')
        write(args.evidence/'boundary-readiness.json', ready)
        bridge = Bridge(rpc, args.evidence, supervisor)
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.bridge = bridge
        threading.Thread(target=server.serve_forever, daemon=True).start()
        host = f'http://127.0.0.1:{server.server_address[1]}'
        environment = dict(os.environ, PYTHONUTF8='1', NO_PROXY='127.0.0.1,localhost',
                           GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='safe.directory', GIT_CONFIG_VALUE_0=ROOT.as_posix())
        for phase, script, pairs in (
                ('generation', 'generate.py', ['--output', str(args.run), '--model', MODELS[0], '--model', MODELS[1]]),
                ('judge', 'judge.py', ['--run', str(args.run), '--judge', MODELS[0], '--judge', MODELS[1]])):
            if phase == 'judge':
                bridge.phase, bridge.inferences = 'judge', 0
                bridge.maximum = 2*(16+len(list((args.run/'patches').glob('*/patch.py'))))
            argv = [sys.executable, '-I', str(HERE/script), *pairs, '--host', host]
            write(args.evidence/(phase+'-command.json'), {'command': argv, 'maximum_requests': bridge.maximum,
                                                         'source_commit': commit})
            with (args.evidence/(phase+'-stdout.txt')).open('w', encoding='utf8') as out, \
                 (args.evidence/(phase+'-stderr.txt')).open('w', encoding='utf8') as err:
                p = subprocess.run(argv, cwd=ROOT, env=environment, stdout=out, stderr=err)
            result[phase+'_exit_code'] = p.returncode
            write(args.evidence/'progress.json', {**result, 'model_request_counts': bridge.totals})
            if p.returncode != 0:
                raise RuntimeError(phase+' script failed; no automatic restart')
        result.update(status='COMPLETE', model_request_counts=bridge.totals)
    except Exception as exc:
        result.update(status='BLOCKED_OR_INTERRUPTED', error=type(exc).__name__+': '+str(exc))
        raise
    finally:
        write(args.evidence/'completion.json', result)
        (rpc/'stop').write_text('stop\n')
        if server is not None:
            server.shutdown(); server.server_close()
        try:
            supervisor.wait(timeout=40)
        except subprocess.TimeoutExpired:
            supervisor.terminate(); supervisor.wait(timeout=15)
        stdout.close(); stderr.close()
        for name in ('boundary-plan.json', 'boundary-stdout.txt', 'boundary-stderr.txt',
                     'model-work/boundary-probe.json', 'model-work/ollama-stderr.txt'):
            source = args.private_work/name
            if source.is_file():
                destination = args.evidence/'boundary'/Path(name).name
                destination.parent.mkdir(exist_ok=True)
                destination.write_bytes(source.read_bytes())


if __name__ == '__main__':
    main()
