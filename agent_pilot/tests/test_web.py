"""HTTP boundary/integration tests with explicitly mocked child and bundle APIs.

No local model, candidate, WSL command or isolation probe is executed here.
"""
import http.client
import io
import json
from pathlib import Path
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch
import zipfile

from agent_pilot import web


class WebTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        fixture = self.root / 'agent_pilot/fixtures'
        (fixture / 'p01').mkdir(parents=True)
        (fixture / 'p01/tool.py').write_text('# reviewed synthetic test source\n', encoding='utf-8')
        (fixture / 'manifest.json').write_text(json.dumps({'cases': [
            {'id': 'p01', 'expected_initial': 'PRIVATE_LABEL', 'structure': 'PRIVATE_CONSTRUCTION',
             'path': 'p01/tool.py', 'required_trigger': 'PRIVATE_TRIGGER'}]}), encoding='utf-8')
        ui = self.root / 'agent_pilot/ui'
        ui.mkdir()
        for name in ('index.html', 'app.js', 'styles.css'):
            (ui / name).write_text('test static asset', encoding='utf-8')
        self.app = web.Application(root=self.root)
        self.observation = patch.object(web, 'runtime_observation', return_value={
            'ready': True, 'isolation_ready': True, 'model_ready': True,
            'runtime_root': '/home/test/credproof-agent-runtime',
            'reasons': [], 'model_label': 'TEST MOCK, no model executed'})
        self.observation.start()
        self.server = web.Server(('127.0.0.1', 0), self.app)
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=2)
        self.observation.stop()
        self.temporary.cleanup()

    def call(self, method, path, body=None, headers=None, raw=False):
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=3)
        supplied = {'Host': f'127.0.0.1:{self.port}'}
        if body is not None:
            body = json.dumps(body).encode()
            supplied['Content-Type'] = 'application/json'
        supplied.update(headers or {})
        connection.request(method, path, body=body, headers=supplied)
        response = connection.getresponse()
        data, result_headers = response.read(), dict(response.getheaders())
        code = response.status
        connection.close()
        return code, data if raw else json.loads(data), result_headers

    def historical(self):
        method = self.root / 'runs/explicit-history/comparison/p01/C-agent'
        method.mkdir(parents=True)
        source = '# frozen original\n'
        candidate = '# frozen candidate\n'
        (method / 'original.py').write_text(source, encoding='utf-8')
        (method / 'final-candidate.py').write_text(candidate, encoding='utf-8')
        value = {'method': 'C-agent', 'source_sha256': web.sha(source),
                 'candidate_sha256': web.sha(candidate),
                 'model': {'status': 'COMPLETED', 'model_calls': 2},
                 'diagnosis': {'diagnosis': 'Model-only suspicion', 'initially_leaking': True},
                 'initial_authority': {'confirmed': 'UNKNOWN', 'repair_authorized': False},
                 'final_validation': {'verdict': 'FAIL', 'reasons': ['RESPONSE_CONTRACT']},
                 'task': {'task_status': 'INCOMPLETE'},
                 'observations': [{'id': 'evidence-1', 'hypothesis': 'test hypothesis',
                    'observation': {'verdict': 'UNKNOWN', 'actual': 'CP_EXEC_' + 'a' * 48}}],
                 'tool_trace': [{}, {}]}
        (method / 'result.json').write_text(json.dumps(value), encoding='utf-8')
        self.app.add_history(method)
        return next(iter(self.app.runs)), method

    def test_bootstrap_discloses_public_scope_not_private_labels(self):
        status, value, headers = self.call('GET', '/api/agent/bootstrap')
        self.assertEqual(status, 200)
        self.assertEqual(value['cases'][0]['id'], 'p01')
        self.assertEqual(value['cases'][0]['source_code'], '# reviewed synthetic test source\n')
        self.assertNotIn('PRIVATE_', json.dumps(value))
        self.assertIn('no-store', headers['Cache-Control'])
        self.assertIn("frame-ancestors 'none'", headers['Content-Security-Policy'])

    def test_project_modes_are_read_only_and_do_not_accept_paths(self):
        status, value, headers = self.call('GET', '/api/project/modes')
        self.assertEqual(status, 200)
        self.assertEqual(value['schema'], 'credproof.project-modes/v1')
        self.assertEqual([item['id'] for item in value['modes']], ['connect', 'check', 'repair', 'export'])
        self.assertIn('credproof.toml', value['modes'][1]['command'])
        self.assertTrue(value['modes'][2]['requires_model'])
        self.assertNotIn(str(self.root), json.dumps(value))
        self.assertIn('no-store', headers['Cache-Control'])
        status, _, _ = self.call('GET', '/api/project/modes?path=../outside')
        self.assertEqual(status, 400)

    def test_host_origin_body_and_path_restrictions_never_launch(self):
        with patch.object(web.subprocess, 'Popen') as child:
            for headers in ({'Host': f'evil.example:{self.port}'},
                            {'Origin': 'https://evil.example'}, {'Origin': 'null'},
                            {'Sec-Fetch-Site': 'cross-site'}):
                status, _, _ = self.call('POST', '/api/agent/runs', {'case_id': 'p01'}, headers)
                self.assertEqual(status, 403)
            status, _, _ = self.call('POST', '/api/agent/runs', {'case_id': 'p01'}, {'Content-Type': 'text/plain'})
            self.assertEqual(status, 415)
            status, _, _ = self.call('POST', '/api/agent/runs', {'case_id': 'x' * 5000})
            self.assertEqual(status, 413)
            for path in ('/../agent_pilot/fixtures/manifest.json', '/%2e%2e/private_data', '/runs/private.json'):
                status, _, _ = self.call('GET', path)
                self.assertEqual(status, 404)
            child.assert_not_called()

    def test_only_fixed_case_selection_is_accepted(self):
        with patch.object(web.subprocess, 'Popen') as child:
            for body in ({'case_id': '../p01'}, {'case_id': 'unregistered'},
                         {'case_id': 'p01', 'verdict': 'PASS'}, {'path': 'tool.py'}):
                status, _, _ = self.call('POST', '/api/agent/runs', body)
                self.assertEqual(status, 400)
            child.assert_not_called()

    def test_live_worker_retains_mock_streams_exit_and_blocks_concurrency(self):
        release = threading.Event()
        class FakeChild:
            def __init__(self, argv, **kwargs):
                self.argv = argv
                kwargs['stdout'].write(b'TEST MOCK supervisor stdout\n')
                kwargs['stderr'].write(b'TEST MOCK supervisor stderr\n')
            def wait(self):
                release.wait(2)
                return 7
        with patch.object(web.subprocess, 'Popen', side_effect=FakeChild) as child:
            try:
                status, value, _ = self.call('POST', '/api/agent/runs', {'case_id': 'p01'})
                self.assertEqual(status, 202)
                self.assertEqual(value['mode'], 'LIVE')
                self.assertIsNone(value['validation'])
                identifier = value['id']
                status, _, _ = self.call('POST', '/api/agent/runs', {'case_id': 'p01'})
                self.assertEqual(status, 409)
            finally:
                release.set()
            for _ in range(50):
                status, value, _ = self.call('GET', '/api/agent/runs/' + identifier)
                if value['status'] == 'ERROR':
                    break
                time.sleep(.01)
            self.assertEqual(value['status'], 'ERROR')
            self.assertEqual(value['process']['exit_code'], 7)
            self.assertIsNone(value['validation'])
            self.assertNotIn('TEST MOCK supervisor stderr', json.dumps(value))
            run = self.app.get(identifier)
            self.assertEqual((run.folder / 'supervisor-stdout.txt').read_bytes(), b'TEST MOCK supervisor stdout\n')
            self.assertEqual((run.folder / 'supervisor-stderr.txt').read_bytes(), b'TEST MOCK supervisor stderr\n')
            argv = child.call_args.args[0]
            self.assertIn('credproof_safety.web_repair', argv)
            self.assertEqual(argv[argv.index('--case-id') + 1], 'p01')
            self.assertEqual(argv[argv.index('--project-id') + 1], 'assistant-original')
            self.assertNotIn('shell', child.call_args.kwargs)

    def test_replay_keeps_model_suspicion_separate_and_redacts_values(self):
        identifier, _ = self.historical()
        status, value, _ = self.call('GET', '/api/agent/runs/' + identifier)
        self.assertEqual(status, 200)
        self.assertEqual(value['mode'], 'REPLAY')
        self.assertEqual(value['diagnosis']['model_suspicion'], 'Model-only suspicion')
        self.assertEqual(value['diagnosis']['confirmed'], 'UNKNOWN')
        self.assertFalse(value['diagnosis']['repair_authorized'])
        self.assertEqual(value['validation']['verdict'], 'FAIL')
        self.assertEqual(value['task_status'], 'INCOMPLETE')
        self.assertNotIn('CP_EXEC_', json.dumps(value))

    def test_changed_frozen_candidate_does_not_reuse_saved_verdict(self):
        identifier, method = self.historical()
        (method / 'final-candidate.py').write_text('# extra drift\n', encoding='utf-8')
        _, value, _ = self.call('GET', '/api/agent/runs/' + identifier)
        self.assertIsNone(value['validation'])
        self.assertEqual(value['diagnosis']['confirmed'], 'UNKNOWN')
        self.assertIn('saved_record_incomplete_or_material_changed', value['remaining_uncertainty'])

    def test_unfinished_model_suspicions_and_denied_proposals_remain_visible(self):
        identifier, method = self.historical()
        record = json.loads((method / 'result.json').read_text())
        record['diagnosis'] = None
        record['model'] = {'status': 'STOPPED_LIMIT', 'model_calls': 1, 'messages': []}
        record['tool_trace'] = [{'tool': 'submit_patch',
            'arguments': json.dumps({'rationale': 'Unconfirmed model suspicion', 'content': 'not executed'}),
            'result': {'status': 'REJECTED', 'reason': 'no_current_confirmed_leak_evidence'}}]
        record['denied_proposals'] = [{'rationale': 'Unconfirmed model suspicion'}]
        (method / 'result.json').write_text(json.dumps(record))
        (method / 'model').mkdir()
        (method / 'model/model-01-response.json').write_text(json.dumps({'choices': [
            {'message': {'role': 'assistant', 'content': 'I suspect a leak, without confirmation.'}}]}))
        _, value, _ = self.call('GET', '/api/agent/runs/' + identifier)
        self.assertIsNone(value['diagnosis']['model_suspicion'])
        self.assertEqual(value['diagnosis']['confirmed'], 'UNKNOWN')
        self.assertEqual(value['model']['raw_notes'][0]['text'], 'I suspect a leak, without confirmation.')
        self.assertEqual(value['model']['proposals'][0]['status'], 'REJECTED')
        self.assertEqual(value['model']['denied_proposal_count'], 1)

    def test_bundle_check_shape_preserves_unknown_and_reasons(self):
        result = web.validation_view({'verdict': 'UNKNOWN', 'reasons': ['missing'],
            'checks': [{'name': 'trial_01', 'verdict': 'UNKNOWN', 'reasons': ['ISOLATION_ERROR']}]})
        self.assertEqual(result['checks'][0]['id'], 'trial_01')
        self.assertEqual(result['checks'][0]['status'], 'UNKNOWN')
        self.assertEqual(result['checks'][0]['reason'], 'ISOLATION_ERROR')

    def test_all_tool_judgments_survive_later_assessment_without_changing_confirmation(self):
        identifier, method = self.historical()
        record = json.loads((method / 'result.json').read_text())
        record['diagnosis'] = {'diagnosis': 'Later corrected assessment', 'initially_leaking': False}
        early = {'diagnosis': 'Earlier false positive', 'initially_leaking': True, 'candidate_id': 'original'}
        record['tool_trace'] = [
            {'tool': 'verify_patch', 'arguments': json.dumps(early), 'result': {'verdict': 'PASS'}},
            {'tool': 'run_controlled_case', 'arguments': {'hypothesis': 'Original runtime suspicion'}, 'result': {}},
            {'tool': 'verify_patch', 'arguments': early, 'result': {'verdict': 'PASS'}},
            {'tool': 'submit_patch', 'arguments': {'rationale': 'Unconfirmed repair proposal'},
             'result': {'status': 'REJECTED', 'reason': 'no_current_confirmed_leak_evidence'}},
            {'tool': 'verify_patch', 'arguments': record['diagnosis'], 'result': {'verdict': 'PASS'}},
        ]
        (method / 'result.json').write_text(json.dumps(record))
        _, value, _ = self.call('GET', '/api/agent/runs/' + identifier)
        notes = value['model']['raw_notes']
        judgments = [json.loads(note['text']) for note in notes if 'verify_patch' in note['source']]
        self.assertEqual([item['initially_leaking'] for item in judgments], [True, True, False])
        self.assertEqual(judgments[0]['diagnosis'], 'Earlier false positive')
        self.assertTrue(any(note['text'] == 'Original runtime suspicion' for note in notes))
        self.assertEqual(value['model']['proposals'][0]['rationale'], 'Unconfirmed repair proposal')
        self.assertEqual(value['model']['proposals'][0]['tool_call_index'], 4)
        self.assertEqual(value['diagnosis']['model_suspicion'], 'Later corrected assessment')
        self.assertEqual(value['diagnosis']['confirmed'], 'UNKNOWN')
        self.assertFalse(value['diagnosis']['repair_authorized'])

    def test_bundle_export_and_recheck_are_called_and_do_not_overwrite_old_verdict(self):
        from agent_pilot import bundle as real_bundle
        identifier, _ = self.historical()
        calls = []
        module = types.ModuleType('agent_pilot.bundle')
        for name in ('PACKAGE', 'RUNTIME_FILES', 'TOP_RECORD', 'MODEL_RECORD'):
            setattr(module, name, getattr(real_bundle, name))
        def export_bundle(run_path, out_path):
            calls.append(('export', run_path))
            out_path.mkdir()
            (out_path / 'manifest.json').write_text('{"test":"MOCK bundle"}')
            return {'test': 'MOCK export'}
        def recheck_bundle(bundle_path, output_path):
            calls.append(('recheck', bundle_path))
            result = {'status': 'COMPLETED', 'checked_at': '2026-09-29T00:00:00Z',
                      'validation': {'verdict': 'PASS', 'reasons': [], 'checks': []},
                      'prior_report_applicable': False, 'candidate_sha256': 'TEST-MOCK'}
            output_path.write_text(json.dumps(result))
            return result
        module.export_bundle, module.recheck_bundle = export_bundle, recheck_bundle
        with patch.dict('sys.modules', {'agent_pilot.bundle': module}):
            status, data, headers = self.call('GET', f'/api/agent/runs/{identifier}/export', raw=True)
            self.assertEqual(status, 200)
            self.assertEqual(headers['Content-Type'], 'application/zip')
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                self.assertEqual(archive.namelist(), ['manifest.json'])
            status, value, _ = self.call('POST', f'/api/agent/runs/{identifier}/recheck', {})
            self.assertEqual(status, 200)
            self.assertEqual(value['validation']['verdict'], 'FAIL')
            self.assertEqual(value['recheck']['validation']['verdict'], 'PASS')
            self.assertFalse(value['recheck']['prior_report_applicable'])
            self.assertEqual([x[0] for x in calls], ['export', 'recheck'])
            run = self.app.get(identifier)
            (run.method / 'final-candidate.py').write_text('# drift after checked export\n')
            status, value, _ = self.call('GET', f'/api/agent/runs/{identifier}')
            self.assertEqual(status, 200)
            self.assertEqual(value['material_binding']['status'], 'CHANGED')
            self.assertIsNone(value['recheck'])
            self.assertEqual(value['historical_recheck']['verdict_at_check'], 'PASS')
            self.assertEqual(value['validation']['verdict'], 'UNKNOWN')
            status, _, _ = self.call('GET', f'/api/agent/runs/{identifier}/export')
            self.assertEqual(status, 409)
            status, _, _ = self.call('POST', f'/api/agent/runs/{identifier}/recheck', {})
            self.assertEqual(status, 409)
            self.assertEqual([x[0] for x in calls], ['export', 'recheck'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
