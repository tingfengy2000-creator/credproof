"""Launch the local model and experiment inside an already isolated network namespace.

Usage: unshare --user --map-root-user --net --fork <venv>/bin/python -m
agent_pilot.offline_run --output <new-record-directory> [--handshake-only]
This does not alter the host firewall, proxy, or interfaces.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import urllib.request

from .tools import write_json_new

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = Path('/home/tingfeng/credproof-agent-runtime')
BASE = 'http://127.0.0.1:11435'


def api(path, data=None, timeout=15):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    encoded = json.dumps(data).encode() if data is not None else None
    request = urllib.request.Request(BASE + path, data=encoded, headers={'Content-Type': 'application/json'})
    with opener.open(request, timeout=timeout) as response:
        return json.loads(response.read())


def network_receipt():
    # Existing sysfs mounts can reflect the parent namespace. Netlink queries
    # describe the actual current network namespace without remounting sysfs.
    links = json.loads(subprocess.check_output(['/usr/sbin/ip', '-j', 'link', 'show']))
    interfaces = sorted(item['ifname'] for item in links)
    attempts = []
    for address, family in [('1.1.1.1', socket.AF_INET), ('8.8.8.8', socket.AF_INET), ('2606:4700:4700::1111', socket.AF_INET6)]:
        with socket.socket(family, socket.SOCK_STREAM) as connection:
            connection.settimeout(1)
            started = time.perf_counter()
            try:
                connection.connect((address, 443))
                attempts.append({'address': address, 'port': 443, 'connected': True})
            except OSError as exc:
                attempts.append({'address': address, 'port': 443, 'connected': False,
                                 'errno': exc.errno, 'reason': type(exc).__name__, 'elapsed_s': time.perf_counter() - started})
    return {'at_utc': datetime.now(timezone.utc).isoformat(), 'network_namespace': os.readlink('/proc/self/ns/net'),
            'interfaces': interfaces, 'ipv4_routes': Path('/proc/net/route').read_text(),
            'ipv6_routes': Path('/proc/net/ipv6_route').read_text(), 'outside_connect_tests': attempts,
            'boundary': 'Local child network namespace; no host firewall/proxy or Codex network change'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--handshake-only', action='store_true')
    parser.add_argument('--cases', nargs='+', default=['p01', 'p02', 'p03', 'p04', 'p05', 'p06'])
    parser.add_argument('--reliability', action='store_true', help='Use shared evidence gate and executor completion pilot')
    parser.add_argument('--agent-only', action='store_true', help='One reviewed UI task; reliability mode only')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    before = network_receipt()
    write_json_new(output / 'network-before.json', before)
    if before['interfaces'] != ['lo'] or any(x['connected'] for x in before['outside_connect_tests']):
        raise SystemExit('Refuse to run: expected fresh namespace with only loopback and no external route')
    subprocess.run(['/usr/sbin/ip', 'link', 'set', 'lo', 'up'], check=True)
    home = RUNTIME / 'service-home'
    home.mkdir(exist_ok=True)
    env = {'PATH': '/usr/bin:/bin:/usr/lib/wsl/lib', 'HOME': str(home), 'LANG': 'C.UTF-8',
           'LD_LIBRARY_PATH': '/usr/lib/wsl/lib', 'OLLAMA_HOST': '127.0.0.1:11435',
           'OLLAMA_MODELS': str(RUNTIME / 'models'), 'OLLAMA_NO_CLOUD': '1',
           'OLLAMA_CONTEXT_LENGTH': '16384', 'OLLAMA_NUM_PARALLEL': '1',
           'OLLAMA_MAX_LOADED_MODELS': '1', 'OLLAMA_KEEP_ALIVE': '-1',
           'OLLAMA_FLASH_ATTENTION': '1', 'OLLAMA_KV_CACHE_TYPE': 'q8_0'}
    binary = RUNTIME / 'ollama/bin/ollama'
    write_json_new(output / 'service-config.json', {'environment': env, 'binary': str(binary),
                   'policy': 'No cloud fallback, credentials, proxy inheritance, RAG or arbitrary execution tools',
                   'paid_api_budget': 0, 'model': 'qwen3-coder:30b'})
    stop = threading.Event()
    resources = []
    def sample():
        while not stop.is_set():
            proc = subprocess.run(['/usr/lib/wsl/lib/nvidia-smi', '--query-gpu=memory.used,memory.free,utilization.gpu', '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=5)
            resources.append({'at_utc': datetime.now(timezone.utc).isoformat(), 'gpu': proc.stdout.strip(), 'exit_code': proc.returncode})
            stop.wait(2)
    stdout = (output / 'ollama-stdout.txt').open('x')
    stderr = (output / 'ollama-stderr.txt').open('x')
    server = subprocess.Popen([str(binary), 'serve'], env=env, cwd=RUNTIME, stdout=stdout, stderr=stderr, start_new_session=True)
    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    status = {'complete': False, 'commands': []}
    try:
        for _ in range(30):
            if server.poll() is not None:
                raise RuntimeError('Ollama exited during startup')
            try:
                version = api('/api/version', timeout=1)
                break
            except OSError:
                time.sleep(1)
        else:
            raise RuntimeError('Ollama startup timed out')
        write_json_new(output / 'model-show.json', api('/api/show', {'model': 'qwen3-coder:30b'}))
        write_json_new(output / 'model-tags.json', api('/api/tags'))
        write_json_new(output / 'service-version.json', version)
        # Warmup is recorded separately; never count it as a repair model call.
        warmup = api('/api/generate', {'model': 'qwen3-coder:30b', 'prompt': 'Reply READY.', 'stream': False,
                      'options': {'num_ctx': 16384, 'num_predict': 4, 'temperature': 0, 'seed': 0}}, timeout=180)
        write_json_new(output / 'warmup.json', warmup)
        write_json_new(output / 'model-ps.json', api('/api/ps'))
        write_json_new(output / 'namespace-membership.json', {
            'orchestrator': os.readlink('/proc/self/ns/net'), 'ollama': os.readlink(f'/proc/{server.pid}/ns/net'),
            'same_namespace': os.readlink('/proc/self/ns/net') == os.readlink(f'/proc/{server.pid}/ns/net')})
        commands = [[sys.executable, '-m', 'agent_pilot.handshake', '--output', str(output / 'handshake')]]
        if not args.handshake_only:
            module = 'agent_pilot.reliability' if args.reliability else 'agent_pilot.experiment'
            comparison = [sys.executable, '-m', module, '--output', str(output / 'comparison'), '--cases', *args.cases]
            comparison += ['--methods', 'C-agent'] if args.agent_only and args.reliability else ['--no-feedback']
            commands.append(comparison)
        child_env = {'PATH': env['PATH'], 'HOME': str(home), 'LANG': 'C.UTF-8', 'PYTHONIOENCODING': 'utf-8',
                     'PYTHONDONTWRITEBYTECODE': '1', 'HF_HUB_OFFLINE': '1', 'HF_HUB_DISABLE_TELEMETRY': '1', 'DO_NOT_TRACK': '1'}
        for i, command in enumerate(commands):
            started = time.perf_counter()
            proc = subprocess.run(command, cwd=ROOT, env=child_env, capture_output=True, timeout=14400)
            (output / f'command-{i}-stdout.txt').write_bytes(proc.stdout)
            (output / f'command-{i}-stderr.txt').write_bytes(proc.stderr)
            status['commands'].append({'command': command, 'exit_code': proc.returncode, 'elapsed_s': time.perf_counter() - started})
            print(json.dumps(status['commands'][-1]), flush=True)
            if proc.returncode:
                raise RuntimeError('Child step failed; raw output preserved without automatic retry')
        status['complete'] = True
    except Exception as exc:
        status['error'] = {'type': type(exc).__name__, 'message': str(exc)}
    finally:
        write_json_new(output / 'network-after.json', network_receipt())
        server.terminate()
        try:
            server.wait(timeout=15)
        except subprocess.TimeoutExpired:
            # Only the process group created by this supervisor is stopped.
            import signal
            os.killpg(server.pid, signal.SIGKILL)
            server.wait(timeout=5)
        stop.set()
        sampler.join(timeout=6)
        stdout.close()
        stderr.close()
        write_json_new(output / 'resources.json', resources)
        write_json_new(output / 'supervisor-result.json', status)
    print(json.dumps(status), flush=True)
    return 0 if status['complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
