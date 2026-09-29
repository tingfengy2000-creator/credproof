"""Review.2 policy and portable material regression checks, not evaluation cases."""
import copy
import json
from pathlib import Path
import shutil
import unittest

import test_core as fixtures
from credproof import core
from credproof.portable import export_package, recheck_package


class Review2CoreTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.CoreMechanismTests.setUpClass.__func__)
    setUp = fixtures.CoreMechanismTests.setUp
    git = fixtures.CoreMechanismTests.git
    repository = fixtures.CoreMechanismTests.repository

    def bundle(self, **kwargs):
        repo = self.repository()
        target = self.root / f'copy-{self.serial}'
        core.freeze(repo, target, self.scanner, allow_fixture=True, edit_policy='python-env-v2', **kwargs)
        return target

    def test_three_legal_forms_and_format_change(self):
        for form in ('subscript', 'get', 'getenv'):
            with self.subTest(form=form):
                bundle = self.bundle()
                path = bundle / 'candidate/config.py'
                code = path.read_text(encoding='utf-8')
                rhs = {'subscript': 'os.environ["CP_DEMO_TOKEN"]',
                       'get': 'os.environ.get("CP_DEMO_TOKEN")',
                       'getenv': 'os.getenv("CP_DEMO_TOKEN")'}[form]
                guard = '' if form == 'subscript' else '\nif SERVICE_TOKEN is None:\n    raise KeyError("CP_DEMO_TOKEN")'
                code = code.replace('os.environ["CP_DEMO_TOKEN"]', rhs + guard)
                path.write_text('# allowed comment and formatting\n' + code, encoding='utf-8')
                self.assertEqual('PASS', core.recheck(bundle, self.scanner)['verdict'])

    def test_guard_and_companion_changes_are_not_unconditionally_allowed(self):
        bundle = self.bundle()
        path = bundle / 'candidate/config.py'
        path.write_text(path.read_text(encoding='utf-8').replace('os.environ["CP_DEMO_TOKEN"]', 'os.environ.get("CP_DEMO_TOKEN")'), encoding='utf-8')
        self.assertEqual('FAIL', core.recheck(bundle, self.scanner)['verdict'])
        bundle = self.bundle()
        (bundle / 'candidate/notes.txt').write_text('Unapproved documentation edit.\n')
        result = core.recheck(bundle, self.scanner)
        self.assertEqual('PASS', result['obligations']['function']['status'])
        self.assertEqual('FAIL', result['obligations']['allowed_changes']['status'])

    def test_stale_can_become_fresh_pass_and_missing_differs_from_unknown(self):
        bundle = self.bundle()
        evidence = core.collect(bundle, self.scanner)
        partial = copy.deepcopy(evidence)
        partial['checks'].pop('function')
        self.assertEqual('INSUFFICIENT', core.evidence_applicability(bundle, partial, self.scanner)['status'])
        unknown = copy.deepcopy(evidence)
        unknown['checks']['function']['status'] = 'UNKNOWN'
        self.assertEqual('APPLICABLE', core.evidence_applicability(bundle, unknown, self.scanner)['status'])
        path = bundle / 'candidate/config.py'
        path.write_bytes(path.read_bytes() + b'\n# approved source comment\n')
        self.assertEqual('INAPPLICABLE', core.evidence_applicability(bundle, evidence, self.scanner)['status'])
        self.assertEqual('PASS', core.recheck(bundle, self.scanner)['verdict'])

    def test_portable_move_reexecutes_and_keeps_old_object(self):
        bundle = self.bundle()
        evidence = core.collect(bundle, self.scanner)
        report = core.assess(bundle, evidence, self.scanner)
        files, _ = core._tree(bundle / 'candidate')
        history = [{'label': 'actual-good-check', 'evidence': evidence, 'report': report, 'candidate_files': files}]
        (bundle / 'candidate/notes.txt').write_text('Changed after the old PASS.\n')
        exported = export_package(bundle, self.scanner, self.root / 'export', history=history, synthetic_confirmed=True)
        relocated = self.root / 'separate/relocated'
        shutil.copytree(exported, relocated)
        result = recheck_package(relocated, self.executable)
        self.assertEqual('INAPPLICABLE', result['old_evidence_applicability']['status'])
        self.assertEqual('FAIL', result['fresh_report']['verdict'])
        self.assertTrue(result['history'][0]['old_object_material_matches_receipt'])
        self.assertEqual('EXPORTED_SNAPSHOT_NOT_LIVE', result['fresh_report']['remaining_risks']['index']['observation'])
        # Forged saved PASS cannot change a freshly executed failure.
        core.write_json(relocated / 'history/000/report.json', {'verdict': 'PASS'})
        again = recheck_package(relocated, self.executable)
        self.assertEqual('FAIL', again['fresh_report']['verdict'])
        self.assertIn('history/000/report.json', again['material_inventory_differences'])
        self.assertNotIn(str(self.root), (exported / 'bundle/private.json').read_text())

    def test_portable_rejects_live_source_or_custom_rules(self):
        package = export_package(self.bundle(), self.scanner, self.root / 'package', synthetic_confirmed=True)
        private = package / 'bundle/private.json'
        data = json.loads(private.read_text())
        data['repo'] = str(self.root)
        core.write_json(private, data)
        with self.assertRaisesRegex(ValueError, 'live repository'):
            recheck_package(package, self.executable)
        data.pop('repo')
        core.write_json(private, data)
        (package / 'rules.toml').write_text('[extend]\npath="outside.toml"\n')
        with self.assertRaisesRegex(ValueError, 'reviewed synthetic rules'):
            recheck_package(package, self.executable)
