"""Frozen dev35 data + actual demo startup; no candidate execution/inference."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agent_pilot import launch, presentation, web

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / presentation.REVIEW_SNAPSHOT


def frozen_bytes():
    return {p.relative_to(SNAPSHOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in SNAPSHOT.rglob('*') if p.is_file()}


class DemoReviewTests(unittest.TestCase):
    def test_launch_demo_has_real_review_and_frozen_data_survives_writes(self):
        before = frozen_bytes()
        seen = {}

        class ObservedServer:
            def __init__(self, address, app):
                self.server_address = address
                self.app = app

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def serve_forever(self):
                bootstrap = self.app.bootstrap()
                self_test.assertGreaterEqual(len(bootstrap['reviews']), 1)
                self_test.assertEqual(bootstrap['review_demonstration']['mode'], 'REPLAY')
                review = self.app.review_workspace
                identifier = bootstrap['reviews'][0]['id']
                state = review.view(identifier)
                self_test.assertEqual((state['technical_verdict'], state['decision'], state['application_to_original']),
                                      ('PASS', 'PENDING', 'NOT_APPLIED'))
                self_test.assertEqual([v['id'] for v in state['versions']], ['v000', 'v001'])
                self_test.assertEqual(json.loads((review.folder(identifier)/'versions/v000/reports/imported.json').read_text(encoding='utf-8'))['verdict'], 'FAIL')
                self_test.assertTrue(any(d['test_operation'] for d in state['decisions']))
                self_test.assertFalse(review.root.is_relative_to(SNAPSHOT))
                expected = {'version_id': state['version']['id'], 'object_sha256': state['object_sha256'],
                            'report_sha256': state['report_sha256'], 'decision_count': len(state['decisions'])}
                # The same write methods used by view-mode HTTP endpoints touch only temp data.
                review.export(identifier, expected)
                approved = review.decide(identifier, expected, 'APPROVED', 'disposable approval test', test_operation=True)
                expected['decision_count'] = len(approved['decisions'])
                changed = review.revise(identifier, expected, state['code']+'\n# disposable UI revision\n', 'temporary edit')
                self_test.assertEqual(changed['technical_verdict'], 'UNKNOWN')
                seen['temporary'] = review.root.parent

        self_test = self
        with patch('sys.argv', ['launch', '--demo', '--mode', 'view', '--workspace', str(ROOT)]), \
             patch.object(launch, 'Server', ObservedServer), \
             patch('agent_pilot.web.runtime_observation', side_effect=AssertionError('view must not inspect WSL')):
            launch.main()
        self.assertFalse(seen['temporary'].exists())
        self.assertEqual(frozen_bytes(), before)

    def test_missing_temp_directory_is_not_silently_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            app = web.Application(root=Path(directory))
            app.root = ROOT
            with patch.object(presentation.tempfile, 'TemporaryDirectory', side_effect=PermissionError('temp_unwritable')):
                with self.assertRaisesRegex(PermissionError, 'temp_unwritable'):
                    presentation.install_review_demonstration(app)

    def test_packaged_config_is_same_portable_default(self):
        from agent_pilot import bundle
        self.assertEqual(bundle.runtime_example_path(), bundle.PACKAGE/'data/runtime.example.json')
        self.assertEqual(bundle.runtime_example_path().read_bytes(), (ROOT/'config/runtime.example.json').read_bytes())


if __name__ == '__main__':
    unittest.main()
