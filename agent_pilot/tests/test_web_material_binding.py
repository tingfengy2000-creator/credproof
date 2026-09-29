"""Real export/identity tests; fresh judge execution is explicitly mocked.

No model, candidate, WSL, subprocess or isolation facility is executed. All
mutation targets, including the verifier files, are disposable test copies.
"""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from agent_pilot import bundle, web


class MaterialBindingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.package = self.root / 'agent_pilot'
        self.package.mkdir()
        for name in (*bundle.RUNTIME_FILES, 'reliability.py', 'fixtures/requirements.md'):
            target = self.package / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(bundle.PACKAGE / name, target)
        (self.root / 'config').mkdir()
        shutil.copyfile(bundle.PACKAGE.parent / 'config/runtime.example.json',
                        self.root / 'config/runtime.example.json')
        fixture = self.package / 'fixtures/p01'
        fixture.mkdir()
        (fixture / 'tool.py').write_text('# reviewed fixture\n', encoding='utf-8')
        (fixture.parent / 'manifest.json').write_text(json.dumps({'cases': [{'id': 'p01'}]}))
        self.package_patch = patch.object(bundle, 'PACKAGE', self.package)
        self.package_patch.start()
        self.app = web.Application(root=self.root)
        self.counter = 0
        self.fresh_patch = patch.object(bundle, '_fresh', return_value={
            'verdict': 'PASS', 'reasons': [], 'checks': [
                {'name': 'TEST_MOCK_NO_EXECUTION', 'verdict': 'PASS', 'reasons': []}]})
        self.fresh = self.fresh_patch.start()

    def tearDown(self):
        self.fresh_patch.stop()
        self.package_patch.stop()
        self.temporary.cleanup()

    def make_run(self):
        self.counter += 1
        method = self.root / f'runs/history-{self.counter}/comparison/p01/C-agent'
        method.mkdir(parents=True)
        original, candidate = b'# original\n', b'# selected candidate\n'
        (method / 'original.py').write_bytes(original)
        (method / 'final-candidate.py').write_bytes(candidate)
        rules = bundle._rules_hash((self.package / 'fixtures/requirements.md').read_bytes(),
                                  (self.package / 'judge.py').read_bytes(), bundle._trusted_policy())
        record = {'method': 'C-agent', 'source_sha256': hashlib.sha256(original).hexdigest(),
                  'candidate_sha256': hashlib.sha256(candidate).hexdigest(), 'rules_sha256': rules,
                  'final_validation': {'verdict': 'PASS', 'reasons': []},
                  'task': {'task_status': 'COMPLETED_REPAIRED'},
                  'initial_authority': {'confirmed': 'CONFIRMED_LEAK', 'repair_authorized': True}}
        (method / 'result.json').write_text(json.dumps(record), encoding='utf-8')
        (method / 'initial-evidence.json').write_text('[]', encoding='utf-8')
        self.app.add_history(method)
        identifier = next(key for key, run in self.app.runs.items() if run.method == method)
        return identifier, self.app.get(identifier)

    def checked_export(self):
        identifier, run = self.make_run()
        self.app.export(identifier)
        view = self.app.recheck(identifier)
        self.assertEqual(view['recheck']['validation']['verdict'], 'PASS')
        self.assertEqual(view['recheck_applicability']['status'], 'APPLICABLE')
        return identifier, run

    def assert_stale(self, identifier, run):
        previous = run.recheck
        view = self.app.view(identifier)
        self.assertIn(view['material_binding']['status'], ('CHANGED', 'UNAVAILABLE'))
        self.assertIsNone(view['recheck'])
        self.assertEqual(view['validation']['verdict'], 'UNKNOWN')
        self.assertEqual(view['task_status'], 'UNKNOWN')
        self.assertEqual(view['diagnosis']['confirmed'], 'UNKNOWN')
        self.assertFalse(view['diagnosis']['repair_authorized'])
        self.assertEqual(view['historical_recheck']['verdict_at_check'], 'PASS')
        self.assertIs(run.recheck, previous)  # Historical record is retained, not rewritten.
        calls = self.fresh.call_count
        for operation in (self.app.export, self.app.recheck):
            with self.assertRaises(web.Problem) as error:
                operation(identifier)
            self.assertEqual(error.exception.status, 409)
        self.assertEqual(self.fresh.call_count, calls)  # Never verify the old copy as current.

    def test_unchanged_real_package_reused_and_fresh_result_remains_applicable(self):
        with patch.object(bundle, 'export_bundle', wraps=bundle.export_bundle) as exporter:
            identifier, run = self.checked_export()
            package = run.bundle
            first = self.app.view(identifier)['material_binding']['binding_sha256']
            self.assertTrue(self.app.export(identifier).is_file())
            view = self.app.recheck(identifier)
            self.assertEqual(exporter.call_count, 1)
            self.assertEqual(run.bundle, package)
            self.assertEqual(view['material_binding']['binding_sha256'], first)
            self.assertEqual(view['recheck_applicability']['status'], 'APPLICABLE')
            self.assertEqual(self.fresh.call_count, 2)

    def test_original_and_candidate_drift_each_block_reuse_preserving_old_package(self):
        for name in ('original.py', 'final-candidate.py'):
            with self.subTest(file=name):
                identifier, run = self.checked_export()
                archived = (run.bundle / ('original.py' if name == 'original.py' else 'current.py')).read_bytes()
                target = run.method / name
                target.write_bytes(target.read_bytes() + b'# changed after export\n')
                self.assert_stale(identifier, run)
                self.assertEqual((run.bundle / ('original.py' if name == 'original.py' else 'current.py')).read_bytes(), archived)

    def test_rule_requirements_and_each_runtime_module_are_bound(self):
        for name in dict.fromkeys(('reliability.py', 'fixtures/requirements.md', *bundle.RUNTIME_FILES)):
            with self.subTest(file=name):
                identifier, run = self.checked_export()
                target = self.package / name
                before = target.read_bytes()
                try:
                    target.write_bytes(before + b'\n# temporary rule/runtime drift\n')
                    self.assert_stale(identifier, run)
                finally:
                    target.write_bytes(before)

    def test_report_trace_addition_and_removal_change_material_identity(self):
        for change in ('report', 'remove-evidence', 'add-model-record'):
            with self.subTest(change=change):
                identifier, run = self.checked_export()
                if change == 'report':
                    report = web.read_json(run.method / 'result.json')
                    report['tool_trace'] = [{'tool': 'verify_patch', 'arguments': '{}'}]
                    web.save_json(run.method / 'result.json', report)
                elif change == 'remove-evidence':
                    (run.method / 'initial-evidence.json').unlink()
                else:
                    (run.method / 'model').mkdir()
                    (run.method / 'model/model-01-response.json').write_text('{"choices": []}')
                self.assert_stale(identifier, run)

    def test_cached_configuration_candidate_and_trace_cannot_be_substituted(self):
        for name in ('configuration.json', 'current.py', 'trace/initial-evidence.json'):
            with self.subTest(file=name):
                identifier, run = self.checked_export()
                path = run.bundle / name
                path.write_bytes(path.read_bytes() + b' ')
                self.assert_stale(identifier, run)

    def test_missing_required_material_is_unavailable_and_restore_does_not_unlatch(self):
        identifier, run = self.checked_export()
        path = run.method / 'original.py'
        old = path.read_bytes()
        path.unlink()
        self.assert_stale(identifier, run)
        self.assertEqual(self.app.view(identifier)['material_binding']['status'], 'UNAVAILABLE')
        path.write_bytes(old)
        self.assert_stale(identifier, run)

    def test_export_drift_before_commit_does_not_create_reusable_cache(self):
        identifier, run = self.make_run()
        real_export = bundle.export_bundle
        def changed_export(source, destination):
            result = real_export(source, destination)
            (run.method / 'original.py').write_text('# concurrent edit\n')
            return result
        with patch.object(bundle, 'export_bundle', side_effect=changed_export):
            with self.assertRaises(web.Problem) as error:
                self.app.export(identifier)
        self.assertEqual(error.exception.status, 409)
        self.assertIsNone(run.bundle)
        self.assertIsNone(run.material_snapshot)
        self.assertIsNone(self.app.view(identifier)['recheck'])
        self.fresh.assert_not_called()

    def test_drift_during_fresh_check_does_not_publish_new_green(self):
        identifier, run = self.checked_export()
        prior = run.recheck
        def change_while_checking(source):
            (run.method / 'final-candidate.py').write_text('# changed concurrently\n')
            return {'verdict': 'PASS', 'reasons': [], 'checks': [{'name': 'MOCK', 'verdict': 'PASS'}]}
        self.fresh.side_effect = change_while_checking
        with self.assertRaises(web.Problem) as error:
            self.app.recheck(identifier)
        self.assertEqual(error.exception.status, 409)
        self.assertIs(run.recheck, prior)
        self.assert_stale(identifier, run)

    def test_a_legacy_cached_bundle_without_identity_is_not_trusted(self):
        identifier, run = self.make_run()
        run.bundle = self.app.runs_root / 'legacy-package'
        run.bundle.mkdir()
        with self.assertRaises(web.Problem) as error:
            self.app.export(identifier)
        self.assertEqual(error.exception.status, 409)
        self.assertEqual(self.app.view(identifier)['material_binding']['status'], 'UNAVAILABLE')


if __name__ == '__main__':
    unittest.main(verbosity=2)
