"""Product workspace: intake, wizard, project reviews, evidence view, HTTP boundary.

Isolated checks are mocked here (protocol tests, not safety experiments); the real
checker run is covered by docs/ui/product-v1/check-product.mjs against a prepared
runtime.  Recorded reports are the real ones from the material-assistant case.
"""
import copy
import glob
import http.client
import io
import json
from pathlib import Path
import re
import shutil
import stat
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

from agent_pilot import web
from agent_pilot.evidence_view import five_questions
from agent_pilot.intake import (IntakeError, IntakeWorkspace, LIMITS, detect, form_from_config, normalise,
                                render_toml, unpack_archive)
from credproof_safety.config import load_config
from credproof_safety.project import _digest_tree

REPOSITORY = Path(__file__).resolve().parents[2]
CASE = REPOSITORY / 'docs/reusable-tool-safety/acceptance'
REVIEW = Path(glob.glob(str(CASE / '20261010-human-review/public-evidence/workspace/runs/human-review/*/'))[0])
ORIGINAL_REPORT = CASE / '20261007-return-redirect/original-report.json'
V000_REPORT = REVIEW / 'versions/v000/reports/imported.json'
V001_REPORT = REVIEW / 'versions/v001/reports/check-01.json'
FIXED_TOOL = REVIEW / 'versions/v001/project/tool.py'

SAMPLE_TOOL = '''import json, logging, os
from urllib.request import Request, urlopen


def fetch_report(request):
    token = os.environ["REPORT_API_TOKEN"]
    with open(request["path"], encoding="utf-8") as handle:
        template = handle.read()
    return {"template": template}


def _helper(x):
    return x
'''


def zip_bytes(entries, *, symlink=None):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        for name, data in entries.items():
            info = zipfile.ZipInfo(name)
            # Preserve deliberately malformed names in the actual ZIP bytes;
            # ZipInfo's Windows constructor otherwise normalizes backslashes.
            info.filename = name
            archive.writestr(info, data)
        if symlink:
            info = zipfile.ZipInfo(symlink)
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, 'target')
    return buffer.getvalue()


def sample_zip():
    return zip_bytes({'report_fetcher/fetcher.py': SAMPLE_TOOL,
                      'report_fetcher/tests/test_fetcher.py': 'def test_ok():\n    assert True\n',
                      'report_fetcher/.git/config': 'ignored',
                      'report_fetcher/__pycache__/fetcher.cpython-312.pyc': b'\0'})


def expected(view):
    return dict(version_id=view['version']['id'], object_sha256=view['object_sha256'],
                report_sha256=view['report_sha256'], decision_count=len(view['decisions']))


def mock_check_from(recorded):
    """Return a check_project stand-in that re-binds a recorded report to the checked tree."""
    def check(config_path, *, output=None, project_root=None, access_dependency=None):
        report = copy.deepcopy(json.loads(Path(recorded).read_text(encoding='utf-8')))
        report['project_tree_sha256'] = _digest_tree(Path(project_root))
        report['config'] = load_config(config_path, project_root=project_root).to_public_dict()
        Path(output).write_text(json.dumps(report), encoding='utf-8')
        return report
    return check


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_single_top_folder_is_stripped_and_caches_ignored(self):
        target = unpack_archive(sample_zip(), self.root / 'out')
        names = sorted(p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file())
        self.assertEqual(names, ['fetcher.py', 'tests/test_fetcher.py'])

    def test_unsafe_members_are_refused(self):
        for entries in ({'../escape.py': 'x'}, {'/abs.py': 'x'}, {'a\\b.py': 'x'}, {'C:/x.py': 'x'}, {'nul\x00.py': 'x'},
                        {'ok/x.py': 'a', 'ok/X.py': 'b'}):
            with self.assertRaises(IntakeError, msg=entries):
                unpack_archive(zip_bytes(entries), self.root / ('o' + str(len(list(self.root.iterdir())))))
        with self.assertRaises(IntakeError):
            unpack_archive(zip_bytes({'a.py': 'x'}, symlink='link'), self.root / 'sym')
        with self.assertRaises(IntakeError):
            unpack_archive(b'not a zip', self.root / 'bad')
        with self.assertRaises(IntakeError):
            unpack_archive(zip_bytes({'big.py': b'0' * (LIMITS['file_bytes'] + 1)}), self.root / 'big')
        self.assertFalse((self.root.parent / 'escape.py').exists())

    def test_detection_is_static(self):
        target = unpack_archive(sample_zip(), self.root / 'out')
        found = detect(target)
        self.assertEqual(found['test_paths'], ['tests'])
        self.assertEqual(found['entry_candidates'][0]['callable'], 'fetch_report')
        self.assertNotIn('_helper', [c['callable'] for c in found['entry_candidates']])
        self.assertEqual(found['credential_env_candidates'], ['REPORT_API_TOKEN'])


class ConfigTests(unittest.TestCase):
    def form(self, **change):
        base = {'tests': ['tests'], 'optional_tests': [], 'source_scope': ['*.py'],
                'entry': {'module': 'fetcher', 'callable': 'fetch_report',
                          'scenarios': [{'name': 'normal', 'request': {'path': '__CREDPROOF_ALLOWED_FILE__', 'n': [1, True]},
                                         'expected_error': None, 'require_network': False},
                                        {'name': 'redirect', 'request': {'url': '__CREDPROOF_REDIRECT_URL__'},
                                         'expected_error': 'HTTPError', 'require_network': True}]},
                'allowed_dir': 'data', 'forbidden_dir': 'secrets', 'require_allowed_file_read': True,
                'service': {'enabled': True, 'path_prefix': '/api', 'require_credential': True},
                'credential_env': 'REPORT_API_TOKEN', 'timeout_seconds': 30}
        base.update(change)
        return base

    def test_rendered_toml_round_trips_through_the_checker_loader(self):
        with tempfile.TemporaryDirectory() as tmp:
            clean = normalise(self.form())
            path = Path(tmp) / 'credproof.toml'
            path.write_text(render_toml(clean), encoding='utf-8')
            cfg = load_config(path)
            self.assertEqual(form_from_config(cfg), clean)
            self.assertEqual(cfg.mutable_scope, ('fetcher.py',))
            self.assertEqual(cfg.entry.expected_error, None)

    def test_invalid_fields_are_explained(self):
        bad = [self.form(entry={'module': 'a b', 'callable': 'run', 'scenarios': [{'name': 'x'}]}),
               self.form(allowed_dir='same', forbidden_dir='same'),
               self.form(service={'enabled': False, 'require_credential': True}),
               self.form(credential_env='lower_case'),
               self.form(tests=['../outside']),
               self.form(timeout_seconds=0)]
        dup = self.form()
        dup['entry'] = {**dup['entry'], 'scenarios': dup['entry']['scenarios'] * 2}
        null = self.form()
        null['entry'] = {**null['entry'], 'scenarios': [{'name': 'n', 'request': {'x': None}}]}
        for form in bad + [dup, null]:
            with self.assertRaises(IntakeError):
                normalise(form)


class WorkspaceFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'agent_pilot/fixtures').mkdir(parents=True)
        (self.root / 'agent_pilot/fixtures/manifest.json').write_text('{"cases": []}', encoding='utf-8')
        shutil.copytree(REPOSITORY / 'examples/material_assistant', self.root / 'examples/material_assistant')
        shutil.copytree(REPOSITORY / 'examples/bench', self.root / 'examples/bench')
        self.app = web.Application(root=self.root, access_mode='recheck')

    def tearDown(self):
        self.tmp.cleanup()

    def test_every_example_keeps_its_config_bytes_and_opens_a_project_review(self):
        examples = self.app.intake.examples()
        self.assertEqual(len(examples), 9)
        for row in examples:
            view = self.app.intake.from_example(row['id'])
            self.assertTrue(view['valid'], (row['id'], view['errors']))
            self.assertEqual(view['config_origin'], 'existing')
            result = self.app.intake.start(view['id'], self.app.review_workspace)
            review = result['review']
            self.assertEqual(review['meta']['kind'], 'PROJECT')
            self.assertIsNone(review['ai_code'])
            self.assertEqual(review['technical_verdict'], 'UNKNOWN')
            self.assertEqual(review['material_reasons'], [])
            frozen = self.app.review_workspace.folder(review['id']) / 'versions/v000/project/credproof.toml'
            source = (self.root / 'examples/material_assistant/credproof.toml') if row['id'] == 'material-assistant' \
                else self.root / 'examples/bench' / row['id'][6:] / 'project/credproof.toml'
            self.assertEqual(frozen.read_bytes(), source.read_bytes())
            with self.assertRaises(IntakeError):
                self.app.intake.start(view['id'], self.app.review_workspace)
            with self.assertRaises(IntakeError):
                self.app.intake.save_config(view['id'], view['config'])

    def test_uploaded_project_needs_a_valid_config_before_start(self):
        view = self.app.intake.from_upload(sample_zip(), '报表下载工具')
        self.assertEqual(view['config']['entry']['callable'], 'fetch_report')
        self.assertEqual(view['config']['credential_env'], 'REPORT_API_TOKEN')
        self.assertEqual(view['config_origin'], 'form')
        broken = copy.deepcopy(view['config'])
        broken['tests'] = ['missing_tests']
        view = self.app.intake.save_config(view['id'], broken)
        self.assertFalse(view['valid'])
        with self.assertRaises(IntakeError):
            self.app.intake.start(view['id'], self.app.review_workspace)
        fixed = copy.deepcopy(view['config'])
        fixed['tests'] = ['tests']
        view = self.app.intake.save_config(view['id'], fixed)
        self.assertTrue(view['valid'], view['errors'])
        review = self.app.intake.start(view['id'], self.app.review_workspace)['review']
        self.assertEqual(review['version']['source'], 'PROJECT_IMPORT')
        self.assertEqual([r['kind'] for r in self.app.review_workspace.list()], ['PROJECT'])

    def test_check_revise_approve_export_and_recheck(self):
        intake = self.app.intake.from_example('material-assistant')
        review = self.app.intake.start(intake['id'], self.app.review_workspace)['review']
        rw = self.app.review_workspace
        with patch('credproof_safety.human_review.check_project', side_effect=mock_check_from(ORIGINAL_REPORT)):
            failed = self.app.review_public(rw.check(review['id'], expected(review)))
        self.assertEqual(failed['technical_verdict'], 'FAIL')
        self.assertEqual([q['state'] for q in failed['evidence']['questions']], ['bad'] * 5)
        with self.assertRaisesRegex(ValueError, 'approval_requires'):
            rw.decide(review['id'], expected(failed), 'APPROVED', 'cannot', test_operation=True)
        revised = rw.revise(review['id'], expected(failed), FIXED_TOOL.read_text(encoding='utf-8'), 'developer revision')
        self.assertIsNone(self.app.review_public(revised)['evidence'])
        with patch('credproof_safety.human_review.check_project', side_effect=mock_check_from(V001_REPORT)):
            passed = self.app.review_public(rw.check(review['id'], expected(revised)))
        self.assertEqual(passed['technical_verdict'], 'PASS')
        self.assertEqual(passed['evidence']['questions'][-1]['state'], 'missing')
        approved = self.app.review_public(rw.decide(review['id'], expected(passed), 'APPROVED', 'protocol test', test_operation=True))
        self.assertEqual(approved['evidence']['questions'][-1]['state'], 'ok')
        for kind in ('json', 'sarif', 'junit', 'md'):
            body, _ = self.app.review_report(review['id'], kind)
            self.assertTrue(body)
        self.assertEqual(json.loads(self.app.review_report(review['id'], 'sarif')[0])['version'], '2.1.0')
        archive = rw.export(review['id'], expected(approved), adopted=True)
        names = zipfile.ZipFile(archive).namelist()
        self.assertIn('manifest.json', names)
        self.assertNotIn('ai-candidate.py', names)
        with patch('credproof_safety.project_bundle.check_project', side_effect=mock_check_from(V001_REPORT)):
            result = self.app.recheck_upload(archive.read_bytes())
        self.assertEqual(result['status'], 'RECHECKED')
        self.assertEqual(result['validation']['verdict'], 'PASS')
        self.assertTrue(result['prior_report_applicable'])
        self.assertEqual(result['human_review']['kind'], 'ADOPTED_REPAIR')
        self.assertEqual(result['evidence']['questions'][-1]['state'], 'ok')
        rows = self.app.review_summaries()
        self.assertEqual(rows[0]['technical_verdict'], 'PASS')
        self.assertEqual(rows[0]['decision'], 'APPROVED')

    def test_diagnostic_bundle_is_not_a_pass(self):
        intake = self.app.intake.from_example('material-assistant')
        review = self.app.intake.start(intake['id'], self.app.review_workspace)['review']
        archive = self.app.review_workspace.export(review['id'], expected(review))
        result = self.app.recheck_upload(archive.read_bytes())
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertEqual(result['validation']['verdict'], 'UNKNOWN')

    def test_view_mode_refuses_recheck(self):
        app = web.Application(root=self.root, access_mode='view')
        with self.assertRaises(web.Problem):
            app.recheck_upload(sample_zip())
        self.assertFalse(app.workspace_status()['can_check'])


class EvidenceViewTests(unittest.TestCase):
    def test_page_ids_are_unique(self):
        from collections import Counter
        from html.parser import HTMLParser
        identifiers = []
        class IDs(HTMLParser):
            def handle_starttag(self, tag, attrs):
                identifiers.extend(value for key, value in attrs if key == 'id')
        IDs().feed((REPOSITORY / 'agent_pilot/ui/index.html').read_text('utf-8'))
        self.assertEqual([name for name, count in Counter(identifiers).items() if count > 1], [])

    def test_recorded_case_reads_as_the_story(self):
        states = lambda path, **kw: [q['state'] for q in five_questions(json.loads(path.read_text('utf-8')), **kw)['questions']]
        self.assertEqual(states(ORIGINAL_REPORT), ['bad', 'bad', 'bad', 'bad', 'bad'])
        self.assertEqual(states(V000_REPORT, decision='REJECTED'), ['missing', 'missing', 'missing', 'missing', 'bad'])
        self.assertEqual(states(V001_REPORT), ['ok', 'ok', 'ok', 'ok', 'missing'])
        self.assertIsNone(five_questions(None))
        self.assertIsNone(five_questions(json.loads(V001_REPORT.read_text('utf-8')), applicable=False))
        unknown = five_questions({'verdict': 'UNKNOWN', 'reason': 'sandbox_execution_incomplete', 'execution': {}})
        self.assertEqual({q['state'] for q in unknown['questions'][:4]}, {'unknown'})

    def test_credential_values_never_appear(self):
        for path in (ORIGINAL_REPORT, V000_REPORT, V001_REPORT):
            text = json.dumps(five_questions(json.loads(path.read_text('utf-8'))), ensure_ascii=False)
            self.assertNotRegex(text, r'CP_LAB_[0-9A-F]{8}')

    def test_home_story_constant_matches_recorded_reports(self):
        source = (REPOSITORY / 'agent_pilot/ui/app.js').read_text(encoding='utf-8')
        embedded = json.loads(re.search(r'// STORY_EVIDENCE_BEGIN\nconst STORY_EVIDENCE = (.*);\n// STORY_EVIDENCE_END', source).group(1))
        for key, path, decision in (('original', ORIGINAL_REPORT, 'PENDING'), ('v000', V000_REPORT, 'REJECTED'),
                                    ('v001', V001_REPORT, 'PENDING')):
            self.assertEqual(embedded[key], five_questions(json.loads(path.read_text('utf-8')), decision=decision), key)


class HttpBoundaryTests(unittest.TestCase):
    def test_readonly_whitelist_allows_intake_list_but_no_write(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('product_readonly', REPOSITORY / 'docs/handoff/frontend-5060/view-readonly.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.server.RequestHandlerClass = module.ReadOnlyHandler
        status, body = self.call('GET', '/api/intake')
        self.assertEqual((status, body), (200, {'intakes': []}))
        status, _ = self.call('POST', '/api/intake/example', json.dumps({'example_id': 'material-assistant'}),
                              self.session({'Content-Type': 'application/json'}))
        self.assertEqual(status, 405)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'agent_pilot/fixtures').mkdir(parents=True)
        (self.root / 'agent_pilot/fixtures/manifest.json').write_text('{"cases": []}', encoding='utf-8')
        shutil.copytree(REPOSITORY / 'agent_pilot/ui', self.root / 'agent_pilot/ui')
        shutil.copytree(REPOSITORY / 'examples/material_assistant', self.root / 'examples/material_assistant')
        self.app = web.Application(root=self.root, access_mode='recheck')
        self.server = web.Server(('127.0.0.1', 0), self.app)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def call(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=20)
        all_headers = {'Host': f'127.0.0.1:{self.port}', **(headers or {})}
        connection.request(method, path, body=body, headers=all_headers)
        response = connection.getresponse()
        data = response.read()
        connection.close()
        try:
            return response.status, json.loads(data)
        except ValueError:
            return response.status, data

    def session(self, extra=None):
        return {'X-CredProof-Review-Session': self.app.review_session, **(extra or {})}

    def test_writes_require_the_session_and_zip_type(self):
        status, _ = self.call('POST', '/api/intake/upload', sample_zip(), {'Content-Type': 'application/zip'})
        self.assertEqual(status, 403)
        status, _ = self.call('POST', '/api/intake/upload', sample_zip(), self.session({'Content-Type': 'application/json'}))
        self.assertEqual(status, 415)
        status, _ = self.call('POST', '/api/intake/upload', b'', self.session({'Content-Type': 'application/zip', 'Content-Length': str(LIMITS['upload_bytes'] + 1)}))
        self.assertEqual(status, 413)
        status, body = self.call('POST', '/api/intake/upload', sample_zip(),
                                 self.session({'Content-Type': 'application/zip', 'X-CredProof-Label': '%E6%8A%A5%E8%A1%A8'}))
        self.assertEqual(status, 201)
        self.assertEqual(body['label'], '报表')
        status, _ = self.call('POST', f'/api/intake/{body["id"]}/config', json.dumps({'config': body['config']}),
                              {'Content-Type': 'application/json'})
        self.assertEqual(status, 403)
        status, again = self.call('GET', f'/api/intake/{body["id"]}')
        self.assertEqual((status, again['id']), (200, body['id']))
        status, rows = self.call('GET', '/api/intake')
        self.assertEqual(rows['intakes'][0]['id'], body['id'])

    def test_example_start_reports_and_status(self):
        status, intake = self.call('POST', '/api/intake/example', json.dumps({'example_id': 'material-assistant'}),
                                   self.session({'Content-Type': 'application/json'}))
        self.assertEqual(status, 201)
        status, started = self.call('POST', f'/api/intake/{intake["id"]}/start', '{}', self.session({'Content-Type': 'application/json'}))
        self.assertEqual(status, 201)
        review_id = started['review']['id']
        self.assertIn('evidence', started['review'])
        status, _ = self.call('GET', f'/api/review/{review_id}/report.sarif')
        self.assertEqual(status, 409)
        status, view = self.call('GET', f'/api/review/{review_id}')
        self.assertEqual((status, view['meta']['kind']), (200, 'PROJECT'))
        status, rows = self.call('GET', '/api/reviews')
        self.assertEqual(rows['reviews'][0]['id'], review_id)
        status, value = self.call('GET', '/api/workspace/status')
        self.assertEqual(value['schema'], 'credproof.workspace-status/v1')
        status, _ = self.call('POST', '/api/intake/example', json.dumps({'example_id': '../etc'}),
                              self.session({'Content-Type': 'application/json'}))
        self.assertEqual(status, 404)
        status, _ = self.call('GET', '/api/intake/' + '0' * 32)
        self.assertEqual(status, 404)


if __name__ == '__main__':
    unittest.main()
