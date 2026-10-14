"""Read-only CI gate demonstration endpoint: fixed workspace file, schema-checked."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest

from agent_pilot import web

REPOSITORY = Path(__file__).resolve().parents[2]


class IntegrationEndpointTests(unittest.TestCase):
    def start(self, payload=None, explicit=None):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        (root / 'agent_pilot/ui').mkdir(parents=True)
        (root / 'agent_pilot/fixtures').mkdir(parents=True)
        (root / 'agent_pilot/fixtures/manifest.json').write_text('{"cases": []}', encoding='utf-8')
        if payload is not None:
            (root / 'docs/integration').mkdir(parents=True)
            (root / 'docs/integration/ci-demo.json').write_text(json.dumps(payload), encoding='utf-8')
        self.app = web.Application(root=root, access_mode='view', integration_results=explicit)
        self.server = web.Server(('127.0.0.1', 0), self.app)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.temporary.cleanup()

    def request(self, method, path):
        port = self.server.server_address[1]
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=3)
        connection.request(method, path, headers={'Host': f'127.0.0.1:{port}'})
        response = connection.getresponse()
        body = json.loads(response.read() or b'{}')
        connection.close()
        return response.status, body

    def test_workspace_file_is_discovered_and_served(self):
        self.start({'schema': 'credproof.ci-demo/v1', 'controls': [{'id': 'vulnerable'}]})
        self.assertTrue(self.request('GET', '/api/agent/bootstrap')[1]['integration_available'])
        status, body = self.request('GET', '/api/integration')
        self.assertEqual(status, 200)
        self.assertEqual(body['controls'][0]['id'], 'vulnerable')
        self.assertIn('notice', body)

    def test_missing_and_unsupported_files(self):
        self.start()
        self.assertFalse(self.request('GET', '/api/agent/bootstrap')[1]['integration_available'])
        self.assertEqual(self.request('GET', '/api/integration')[0], 404)
        self.tearDown()
        self.start({'schema': 'other/v1', 'controls': []})
        self.assertEqual(self.request('GET', '/api/integration')[0], 409)

    def test_request_cannot_choose_a_path(self):
        self.start({'schema': 'credproof.ci-demo/v1', 'controls': []})
        for path in ('/api/integration/../bench', '/api/integration?path=/etc/passwd', '/api/integration/x'):
            with self.subTest(path):
                self.assertNotEqual(self.request('GET', path)[1].get('schema'), 'credproof.ci-demo/v1')
        self.assertNotEqual(self.request('POST', '/api/integration')[0], 200)



class DemoDataTests(unittest.TestCase):
    def test_committed_demo_file_matches_its_generator(self):
        import subprocess, sys
        result = subprocess.run([sys.executable, str(REPOSITORY / 'scripts/integration/build_ci_demo.py'), '--check'],
                                capture_output=True, text=True, cwd=REPOSITORY)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == '__main__':
    unittest.main()
