"""Frozen dev35 data + actual demo startup; no candidate execution/inference."""
import hashlib
import errno
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from agent_pilot import launch, presentation, web

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / presentation.REVIEW_SNAPSHOT


def frozen_bytes():
    return {p.relative_to(SNAPSHOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in SNAPSHOT.rglob('*') if p.is_file()}


class DemoReviewTests(unittest.TestCase):
    def test_busy_port_falls_back_without_changing_application(self):
        app = object()
        with patch.object(launch, 'Server', side_effect=[OSError(errno.EADDRINUSE, 'busy'), 'server']) as server:
            self.assertEqual(launch.server_for(app, 8765, True), 'server')
            self.assertEqual(server.call_args.args, (('127.0.0.1', 0), app))

    def test_windows_exclusive_listener_falls_back_only_when_confirmed(self):
        error = OSError(errno.EACCES, 'exclusive listener')
        error.winerror = 10013
        with patch.object(launch, 'Server', side_effect=[error, 'server']), \
             patch.object(launch.socket, 'create_connection'):
            self.assertEqual(launch.server_for(object(), 8765, True), 'server')
        with patch.object(launch, 'Server', side_effect=error), \
             patch.object(launch.socket, 'create_connection', side_effect=OSError('no listener')):
            with self.assertRaises(OSError):
                launch.server_for(object(), 8765, True)

    def test_explicit_port_without_auto_does_not_fallback(self):
        with patch.object(launch, 'Server', side_effect=OSError(errno.EADDRINUSE, 'busy')) as server:
            with self.assertRaises(OSError):
                launch.server_for(object(), 8765, False)
            self.assertEqual(server.call_count, 1)

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
                seen['temporary'] = Path(self.app._review_demo_temporary.name)
                owner = json.loads((seen['temporary']/presentation.DEMO_OWNER).read_text(encoding='utf-8'))
                self_test.assertEqual(owner['pid'], os.getpid())
                self_test.assertEqual(owner['schema'], presentation.DEMO_OWNER_SCHEMA)
                self_test.assertLess(abs(owner['started_at']-time.time()), 60)

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

    def test_process_probe_is_read_only_and_detects_exited_child(self):
        self.assertTrue(presentation._process_running(os.getpid()))
        child = subprocess.Popen([sys.executable, '-S', '-c', 'pass'])
        self.assertEqual(child.wait(timeout=15), 0)
        self.assertFalse(presentation._process_running(child.pid))

    def test_startup_removes_dead_owner_and_preserves_live_instance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dead = root/(presentation.DEMO_PREFIX+'dead')
            live = root/(presentation.DEMO_PREFIX+'live')
            for folder, pid in [(dead, 12345), (live, os.getpid())]:
                folder.mkdir()
                (folder/presentation.DEMO_OWNER).write_text(json.dumps({
                    'schema': presentation.DEMO_OWNER_SCHEMA, 'pid': pid,
                    'started_at': time.time()-13*3600,
                }), encoding='utf-8')
                (folder/'preserve.txt').write_text('original', encoding='utf-8')
            app = web.Application(root=root)
            app.root = ROOT
            cleanup = presentation.cleanup_stale_review_demonstrations
            with patch.object(presentation, '_process_running', side_effect=lambda pid: pid == os.getpid()), \
                 patch.object(presentation, 'cleanup_stale_review_demonstrations',
                              side_effect=lambda: cleanup(root)) as sweep:
                try:
                    presentation.install_review_demonstration(app)
                    self.assertEqual(sweep.call_count, 1)
                    self.assertFalse(dead.exists())
                    self.assertEqual((live/'preserve.txt').read_text(), 'original')
                    self.assertEqual(app.review_demonstration['stale_demo_directories_removed'], 1)
                finally:
                    presentation.close_review_demonstration(app)

    def test_unmarked_invalid_and_unrelated_temp_directories_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cases = [('unrelated', {'schema': presentation.DEMO_OWNER_SCHEMA, 'pid': 12345, 'started_at': time.time()}),
                     (presentation.DEMO_PREFIX+'unmarked', None),
                     (presentation.DEMO_PREFIX+'invalid', {'schema': 'not-ours', 'pid': 12345, 'started_at': time.time()}),
                     (presentation.DEMO_PREFIX+'bad-pid', {'schema': presentation.DEMO_OWNER_SCHEMA, 'pid': True, 'started_at': time.time()}),
                     (presentation.DEMO_PREFIX+'bad-json', 'not-json')]
            for name, owner in cases:
                folder = root/name
                folder.mkdir()
                if owner is not None:
                    (folder/presentation.DEMO_OWNER).write_text(
                        owner if isinstance(owner, str) else json.dumps(owner), encoding='utf-8')
            with patch.object(presentation, '_process_running', return_value=False) as probe:
                self.assertEqual(presentation.cleanup_stale_review_demonstrations(root), [])
                probe.assert_not_called()
            self.assertEqual(len(list(root.iterdir())), len(cases))

    def test_unknown_process_access_is_conservative(self):
        if os.name == 'nt':
            with patch('ctypes.WinDLL') as library, patch('ctypes.get_last_error', return_value=5):
                library.return_value.OpenProcess.return_value = 0
                self.assertTrue(presentation._process_running(12345))
        else:
            with patch.object(presentation.os, 'kill', side_effect=PermissionError('denied')):
                self.assertTrue(presentation._process_running(12345))

    def test_default_cmd_runs_bundled_python_without_powershell_bypass(self):
        script = (ROOT/'start-credproof.cmd').read_text(encoding='utf-8')
        direct, fallback = script.split(') else (', 1)
        self.assertIn('"%~dp0runtime\\python\\python.exe" -S -m agent_pilot.launch', direct)
        self.assertNotIn('powershell', direct.lower())
        self.assertIn('powershell.exe -NoProfile -File', fallback)
        self.assertNotIn('executionpolicy', script.lower())
        self.assertIn('pause', script.lower())


if __name__ == '__main__':
    unittest.main()
