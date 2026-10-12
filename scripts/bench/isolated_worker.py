"""Trusted, fixed-address file RPC -> private Ollama adapter. No tools or exec."""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import urllib.error
import urllib.request

RPC = Path('/rpc')
HOST = 'http://127.0.0.1:11435'


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False)+'\n', encoding='utf8')


def probe(service):
    results = []
    for ip in ('192.0.2.1', '198.51.100.1', '203.0.113.1'):
        try:
            with socket.create_connection((ip, 443), timeout=.3):
                results.append({'target': ip, 'connected': True})
        except OSError as exc:
            results.append({'target': ip, 'connected': False, 'error': type(exc).__name__, 'errno': exc.errno})
    namespaces = {name: {'controller': os.readlink('/proc/self/ns/'+name),
                         'ollama': os.readlink(f'/proc/{service.pid}/ns/'+name)} for name in ('net', 'mnt', 'pid')}
    sentinel = os.environ['CREDPROOF_HOST_SENTINEL']
    info = {'interfaces': sorted(p.name for p in Path('/sys/class/net').iterdir()) if Path('/sys/class/net').exists()
            else [line.split(':')[0].strip() for line in Path('/proc/net/dev').read_text().splitlines()[2:]],
            'outside_connect_tests': results, 'namespaces': namespaces,
            'host_sentinel_visible': Path(sentinel).exists(),
            'host_link_visible': Path('/work/escape-host-sentinel').exists(),
            'host_mnt_visible': Path('/mnt').exists(),
            'ollama_host_sentinel_visible': Path(f'/proc/{service.pid}/root'+sentinel).exists(),
            'cuda_device_visible': Path('/dev/dxg').exists()}
    info['passed'] = (info['interfaces'] == ['lo'] and not any(x['connected'] for x in results)
                      and all(x['controller'] == x['ollama'] for x in namespaces.values())
                      and not any(info[k] for k in ('host_sentinel_visible', 'host_link_visible', 'host_mnt_visible',
                                                   'ollama_host_sentinel_visible')) and info['cuda_device_visible'])
    return info


def main():
    log = Path('/work/ollama-stderr.txt').open('wb')
    service = subprocess.Popen(['/runtime/ollama/bin/ollama', 'serve'], stdout=log, stderr=log)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        for _ in range(300):
            if service.poll() is not None:
                raise RuntimeError('Ollama exited before readiness')
            try:
                with opener.open(HOST+'/api/version', timeout=1) as r:
                    version = json.loads(r.read())
                break
            except OSError:
                time.sleep(.1)
        else:
            raise RuntimeError('Ollama readiness timeout')
        boundary = probe(service)
        write(Path('/work/boundary-probe.json'), boundary)
        if not boundary['passed']:
            raise RuntimeError('model boundary probe failed')
        write(RPC/'ready.json', {'version': version, 'boundary': boundary})
        processed = set()
        while not (RPC/'stop').exists():
            if service.poll() is not None:
                raise RuntimeError('Ollama stopped unexpectedly')
            pending = sorted(p for p in RPC.glob('request-*.json') if p.name not in processed)
            if not pending:
                time.sleep(.025); continue
            source = pending[0]
            try:
                item = json.loads(source.read_text(encoding='utf8'))
            except (OSError, ValueError):
                time.sleep(.025); continue
            processed.add(source.name)
            path, method = item['path'], item['method']
            if (method, path) not in {('POST', '/api/chat'), ('POST', '/api/show'),
                                     ('GET', '/api/tags'), ('GET', '/api/ps'), ('GET', '/api/version')}:
                raise RuntimeError('unsupported RPC route')
            body = item['body'].encode('utf8') if item.get('body') else None
            req = urllib.request.Request(HOST+path, data=body, method=method,
                                         headers={'Content-Type': 'application/json'})
            started = time.monotonic()
            try:
                with opener.open(req, timeout=600 if path == '/api/chat' else 25) as r:
                    code, text = r.status, r.read().decode('utf8')
            except urllib.error.HTTPError as exc:
                code, text = exc.code, exc.read().decode('utf8', errors='replace')
            except Exception as exc:
                code, text = 502, json.dumps({'error': type(exc).__name__+': '+str(exc)})
            ps = None
            if path == '/api/chat':
                try:
                    with opener.open(HOST+'/api/ps', timeout=10) as r:
                        ps = json.loads(r.read())
                except OSError as exc:
                    ps = {'error': str(exc)}
            write(RPC/source.name.replace('request-', 'response-', 1),
                  {'status': code, 'body': text, 'seconds': time.monotonic()-started, 'ps': ps,
                   'request_sha256': hashlib.sha256((item.get('body') or '').encode()).hexdigest()})
    finally:
        service.terminate()
        try:
            service.wait(timeout=15)
        except subprocess.TimeoutExpired:
            service.kill(); service.wait()
        log.close()


if __name__ == '__main__':
    main()
