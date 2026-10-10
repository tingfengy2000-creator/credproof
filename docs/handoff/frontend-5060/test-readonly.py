"""No-model UI transport test; never a security/candidate acceptance experiment."""
import argparse
import hashlib
import http.client
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('frontend_readonly', HERE/'view-readonly.py')
viewer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(viewer)


def files(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


class ReadOnlyTests(unittest.TestCase):
    def setUp(self):
        self.context = viewer.prepared_view()
        self.app = self.context.__enter__()
        self.before = files(self.app.root)
        self.server = viewer.ReadOnlyServer(('127.0.0.1', 0), self.app)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)
        self.assertEqual(self.before, files(self.app.root))
        self.context.__exit__(None, None, None)

    def request(self, path, method='GET', payload=None, **headers):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_address[1], timeout=10)
        if payload is not None:
            payload = json.dumps(payload)
            headers['Content-Type'] = 'application/json'
        connection.request(method, path, body=payload, headers=headers)
        response = connection.getresponse()
        result = response.status, response.read()
        connection.close()
        return result

    def test_assets_and_explicit_history_notice(self):
        status, body = self.request('/')
        self.assertEqual(status, 200)
        self.assertIn(b'READ_ONLY_HISTORY', body)
        for name in ('app.js', 'styles.css'):
            status, body = self.request('/'+name)
            self.assertEqual(status, 200)
            self.assertEqual(body, (viewer.REPOSITORY/'agent_pilot/ui'/name).read_bytes())

    def test_history_fields_without_model_or_isolation_probe(self):
        status, body = self.request('/api/agent/bootstrap')
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertFalse(data['runtime']['ready'])
        self.assertFalse(data['runtime']['isolation_ready'])
        self.assertEqual(data['frontend_handoff']['mode'], 'READ_ONLY_HISTORY')
        identifier = data['reviews'][0]['id']
        status, body = self.request('/api/review/'+identifier)
        self.assertEqual(status, 200)
        review = json.loads(body)
        self.assertEqual((review['technical_verdict'], review['decision'], review['application_to_original']),
                         ('PASS', 'PENDING', 'NOT_APPLIED'))
        self.assertEqual(review['version']['source'], 'DEVELOPER_REVISION')
        self.assertEqual(review['report']['execution']['pytest_observation']['passed'], 4)

    def test_all_mutations_and_model_operations_are_rejected(self):
        identifier = self.app.review_workspace.list()[0]['id']
        paths = ['/api/agent/runs', '/api/project/check', '/api/project/select', '/api/project/export',
                 '/api/review/open', *['/api/review/'+identifier+'/'+name
                                      for name in ('revise', 'check', 'decide', 'export')]]
        for path in paths:
            status, body = self.request(path, 'POST', {},
                                       **{'X-CredProof-Review-Session': self.app.review_session})
            self.assertEqual(status, 405, path)
            self.assertIn(b'READ_ONLY_HISTORY', body)

    def test_get_cannot_export_or_browse_arbitrary_files(self):
        for path in ('/api/agent/runs/fake/export', '/api/review/../meta.json', '/config/local-runtime.json'):
            self.assertEqual(self.request(path)[0], 405)

    def test_existing_host_origin_boundary_is_retained(self):
        self.assertEqual(self.request('/api/agent/bootstrap', Host='outside.invalid')[0], 403)
        self.assertEqual(self.request('/api/agent/bootstrap', Origin='https://outside.invalid')[0], 403)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('new_transport_receipt_required')
    forbidden = ('agent_pilot.web.runtime_observation', 'agent_pilot.web.Application.start',
                 'credproof_safety.human_review.check_project',
                 'credproof_safety.human_review.ReviewWorkspace.revise',
                 'credproof_safety.human_review.ReviewWorkspace.decide',
                 'credproof_safety.human_review.ReviewWorkspace.export',
                 'subprocess.run', 'subprocess.Popen')
    from contextlib import ExitStack
    with ExitStack() as stack:
        mocked = [stack.enter_context(patch(name, side_effect=AssertionError('forbidden: '+name)))
                  for name in forbidden]
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(ReadOnlyTests)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        calls = {name: mock.call_count for name, mock in zip(forbidden, mocked)}
    receipt = {'kind': 'READ_ONLY_UI_TRANSPORT_TEST', 'tests': result.testsRun,
               'failures': len(result.failures), 'errors': len(result.errors),
               'success': result.wasSuccessful() and not any(calls.values()),
               'forbidden_operations_called': calls, 'model_calls': 0, 'candidate_executions': 0,
               'real_decisions_written': 0, 'real_evidence_exports': 0,
               'package_version': importlib.metadata.version('credproof-safety'),
               'viewer_sha256': hashlib.sha256((HERE/'view-readonly.py').read_bytes()).hexdigest(),
               'note': 'Actual loopback HTTP with copied disclosed history and blocked executor methods; not new security acceptance or model inference.'}
    import agent_pilot.web
    receipt['installed_web_sha256'] = hashlib.sha256(Path(agent_pilot.web.__file__).read_bytes()).hexdigest()
    receipt['installed_web_origin'] = 'site-packages' if 'site-packages' in agent_pilot.web.__file__ else 'SOURCE_CHECKOUT'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    raise SystemExit(0 if receipt['success'] else 1)


if __name__ == '__main__':
    main()
