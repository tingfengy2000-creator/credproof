"""Read-only benchmark endpoints: operator-selected file only, no request-supplied paths."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest

from agent_pilot import web


def results(path):
    path.write_text(json.dumps({
        'schema': 'credproof.bench-results/v1', 'summary': {'ai': {'patches': 1}}, 'targets': [],
        'patches': [{'id': 'b01-ticket-digest__m__s1__r0', 'credproof': {'verdict': 'FAIL'},
                     'code': 'print(1)\n', 'diff': '--- a\n+++ b\n'}]}), encoding='utf-8')


class BenchEndpointTests(unittest.TestCase):
    def start(self, bench):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        (root / 'agent_pilot/ui').mkdir(parents=True)
        (root / 'agent_pilot/fixtures').mkdir(parents=True)
        (root / 'agent_pilot/fixtures/manifest.json').write_text('{"cases": []}', encoding='utf-8')
        path = None
        if bench:
            path = root / 'bench-results.json'
            results(path)
        self.app = web.Application(root=root, access_mode='view', bench_results=path)
        self.server = web.Server(('127.0.0.1', 0), self.app)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.temporary.cleanup()

    def get(self, path):
        port = self.server.server_address[1]
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=3)
        connection.request('GET', path, headers={'Host': f'127.0.0.1:{port}'})
        response = connection.getresponse()
        body = json.loads(response.read())
        connection.close()
        return response.status, body

    def test_overview_omits_code_and_patch_returns_it(self):
        self.start(True)
        status, body = self.get('/api/bench')
        self.assertEqual(status, 200)
        self.assertEqual(body['schema'], 'credproof.bench-results/v1')
        self.assertNotIn('code', body['patches'][0])
        self.assertNotIn('diff', body['patches'][0])
        status, row = self.get('/api/bench/patches/b01-ticket-digest__m__s1__r0')
        self.assertEqual(status, 200)
        self.assertEqual(row['code'], 'print(1)\n')
        self.assertEqual(self.get('/api/bench/patches/unknown')[0], 404)

    def test_paths_and_queries_are_refused(self):
        self.start(True)
        self.assertEqual(self.get('/api/bench/patches/..%2Fsecret')[0], 404)
        self.assertEqual(self.get('/api/bench?file=/etc/passwd')[0], 400)

    def test_without_results_file_endpoint_reports_absence(self):
        self.start(False)
        self.assertEqual(self.get('/api/bench')[0], 404)
        status, body = self.get('/api/agent/bootstrap')
        self.assertEqual(status, 200)
        self.assertFalse(body['bench_available'])

    def test_missing_selected_file_is_409_instead_of_empty_cache(self):
        self.start(True)
        self.app.bench_path.unlink()
        self.assertEqual(self.get('/api/bench')[0], 409)

    def test_deleted_cached_file_is_not_served_as_current(self):
        self.start(True)
        self.assertEqual(self.get('/api/bench')[0], 200)
        self.app.bench_path.unlink()
        self.assertEqual(self.get('/api/bench')[0], 409)

    def test_malformed_patch_rows_are_409(self):
        self.start(True)
        self.app.bench_path.write_text(json.dumps({
            'schema': 'credproof.bench-results/v1', 'patches': [None]}), encoding='utf-8')
        self.assertEqual(self.get('/api/bench')[0], 409)


if __name__ == '__main__':
    unittest.main()
