"""One bounded candidate release check. Run from a fixed clean snapshot.

Only registered synthetic tasks are exercised. --live-case is optional and runs
exactly one new inference task, with the existing 12-call / 3-patch policy.
No retry-to-green, no historical overwrite and no host candidate execution.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent_pilot.web import Application, Server
from agent_pilot.presentation import install_demonstrations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--live-case', choices=['h01'])
    args = parser.parse_args()
    output = args.output.absolute()
    output.mkdir(parents=True, exist_ok=False)
    records = []

    def save(name, data):
        (output / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    def command(name, argv, cwd=ROOT, timeout=180):
        started = time.monotonic()
        result = subprocess.run(argv, cwd=cwd, capture_output=True, timeout=timeout)
        (output / (name + '-stdout.txt')).write_bytes(result.stdout)
        (output / (name + '-stderr.txt')).write_bytes(result.stderr)
        records.append({'name': name, 'command': argv, 'cwd': str(cwd), 'exit_code': result.returncode,
                        'elapsed_s': time.monotonic() - started})
        save('commands.json', records)
        return result

    def hashes():
        return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for base in ('agent_pilot', 'config') for p in (ROOT / base).rglob('*')
                if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}

    before = hashes()
    save('source-freeze-before.json', before)
    preflight = command('preflight', [sys.executable, '-m', 'agent_pilot.preflight'])
    if preflight.returncode:
        raise RuntimeError('Preflight blocked; no model or candidate was executed')
    for pattern in ('test_bundle.py', 'test_runtime_config.py', 'test_web*.py', 'test_presentation.py'):
        result = command('unit-' + pattern.replace('*', 'all'), [sys.executable, '-m', 'unittest', 'discover',
                         '-s', 'agent_pilot/tests', '-p', pattern, '-v'])
        if result.returncode:
            raise RuntimeError('Targeted regression failed; raw output retained')
    app = Application(ROOT)
    install_demonstrations(app)
    server = Server(('127.0.0.1', 0), app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = 'http://127.0.0.1:' + str(server.server_address[1])
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def request(path, body=None, json_response=True):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(base + path, data=data, headers={'Content-Type': 'application/json'})
        with opener.open(req, timeout=180) as response:
            content = response.read()
            return json.loads(content) if json_response else content

    try:
        html = request('/', json_response=False)
        assert b'demo-cards' in html
        bootstrap = request('/api/agent/bootstrap')
        save('bootstrap.json', bootstrap)
        for story in bootstrap['demonstrations']:
            case, identifier = story['case_id'], story['run_id']
            route = '/api/agent/runs/' + identifier
            view = request(route)
            assert view['mode'] == 'REPLAY' and view['presentation']['case_id'] == case
            save(case + '-replay.json', view)
            archive = output / (case + '-export.zip')
            archive.write_bytes(request(route + '/export', json_response=False))
            fresh = request(route + '/recheck', {})
            save(case + '-ui-recheck.json', fresh)
            assert fresh['recheck']['validation']['verdict'] == 'PASS'
            extracted = output / (case + '-direct-material')
            with zipfile.ZipFile(archive) as z:
                z.extractall(extracted)  # Own just-generated fixed export, no untrusted upload.
            checked = command(case + '-direct-recheck', [sys.executable, '-m', 'agent_pilot.bundle',
                              'recheck', '--bundle', '.', '--output', str(output / (case + '-direct-recheck.json'))], extracted)
            assert checked.returncode == 0
        if args.live_case:
            started = time.monotonic()
            live = request('/api/agent/runs', {'case_id': args.live_case})
            save('live-initial.json', live)
            while live['status'] in ('QUEUED', 'RUNNING') and time.monotonic() - started < 1200:
                time.sleep(2)
                live = request('/api/agent/runs/' + live['id'])
            save('live-final.json', live)
            # Record every outcome. A model failure is not a packaging test failure.
            save('live-release-observation.json', {'attempts': 1, 'elapsed_s': time.monotonic() - started,
                 'status': live['status'], 'task_status': live['task_status'], 'model_calls': live['model']['calls'],
                 'validation': live['validation'], 'record_directory': str(app.get(live['id']).folder),
                 'not_a_new_batch_performance_claim': True})
        selected = bootstrap['demonstrations'][0]
        run = app.get(selected['run_id'])
        old_bundle_sha = hashlib.sha256((output / (selected['case_id'] + '-export.zip')).read_bytes()).hexdigest()
        target = run.method / 'final-candidate.py'
        target.write_text(target.read_text(encoding='utf-8') + '\n# controlled release-check drift\n', encoding='utf-8')
        codes = {}
        for operation, body in [('export', None), ('recheck', {})]:
            try:
                request('/api/agent/runs/' + run.id + '/' + operation, body, json_response=False)
                codes[operation] = 200
            except urllib.error.HTTPError as error:
                codes[operation] = error.code
        changed = request('/api/agent/runs/' + run.id)
        save('changed-copy-ui.json', changed)
        save('changed-copy-result.json', {'responses': codes, 'current_verdict': changed['validation']['verdict'],
             'recheck_applicability': changed['recheck_applicability'], 'original_export_sha256': old_bundle_sha,
             'original_export_unchanged': old_bundle_sha == hashlib.sha256((output / (selected['case_id'] + '-export.zip')).read_bytes()).hexdigest()})
        assert codes == {'export': 409, 'recheck': 409}
        assert changed['recheck'] is None and changed['validation']['verdict'] == 'UNKNOWN'
    finally:
        server.shutdown()
        server.server_close()
        after = hashes()
        save('source-freeze-after.json', after)
        save('source-freeze-result.json', {'unchanged': before == after,
             'changed_paths': sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))})
    assert before == after
    print(json.dumps({'status': 'PASS', 'output': str(output), 'source_files_frozen': len(before),
                      'live_attempts': 1 if args.live_case else 0}))


if __name__ == '__main__':
    main()
