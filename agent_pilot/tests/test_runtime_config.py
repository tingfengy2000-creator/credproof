"""Configuration and read-only preflight tests. No models or candidate execution."""
import hashlib
import json
import os
from pathlib import Path
import platform
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from agent_pilot import isolation, preflight, runtime_config, web


class RuntimeConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'config').mkdir()
        self.clean_env = patch.dict(os.environ, {}, clear=True)
        self.clean_env.start()

    def tearDown(self):
        self.clean_env.stop()
        self.temp.cleanup()

    def test_default_user_and_local_explicit_and_child_override_precedence(self):
        self.assertEqual(runtime_config.load_config(self.root), runtime_config.DEFAULTS)
        self.assertNotIn('-u', runtime_config.wsl_prefix(runtime_config.DEFAULTS))
        local = self.root / 'config/local-runtime.json'
        local.write_text(json.dumps({'wsl_user': 'test_user', 'runtime_root': '/opt/local-runtime'}))
        self.assertIn('test_user', runtime_config.wsl_prefix(runtime_config.load_config(self.root)))
        explicit = self.root / 'chosen.json'
        explicit.write_text(json.dumps({'runtime_root': '/opt/chosen-runtime'}))
        with patch.dict(os.environ, {'CREDPROOF_CONFIG': str(explicit),
                                     'CREDPROOF_RUNTIME_ROOT': '/opt/inherited-runtime'}):
            value = runtime_config.load_config(self.root)
            self.assertEqual(value['runtime_root'], '/opt/inherited-runtime')
            self.assertEqual(value['wsl_user'], '')

    def test_runtime_paths_are_derived_without_author_specific_segments(self):
        value = {**runtime_config.DEFAULTS, 'runtime_root': '/opt/review-runtime'}
        paths = runtime_config.runtime_paths(value)
        self.assertEqual('/opt/review-runtime/isolation/rootfs', paths['rootfs'])
        self.assertEqual('/opt/review-runtime/venv/bin/python', paths['python'])
        self.assertNotIn('tingfeng', '\n'.join(paths.values()))

    def test_execution_runtime_paths_resolve_tilde_inside_wsl(self):
        value = {**runtime_config.DEFAULTS, 'runtime_root': '~/credproof-agent-runtime'}
        response = types.SimpleNamespace(returncode=0, stdout=b'/home/reviewer/credproof-agent-runtime\n')
        with patch.object(runtime_config.subprocess, 'run', return_value=response) as child:
            paths = runtime_config.execution_runtime_paths(value)
        self.assertEqual(paths['bubblewrap'], '/home/reviewer/credproof-agent-runtime/isolation/tools/usr/bin/bwrap')
        self.assertNotIn('~', '\n'.join(paths.values()))
        self.assertIn('python3', child.call_args.args[0])

    def test_execution_runtime_paths_fail_closed_when_wsl_resolution_fails(self):
        value = {**runtime_config.DEFAULTS, 'runtime_root': '~/credproof-agent-runtime'}
        response = types.SimpleNamespace(returncode=1, stdout=b'')
        with patch.object(runtime_config.subprocess, 'run', return_value=response):
            with self.assertRaises(ValueError):
                runtime_config.execution_runtime_paths(value)

    def test_runtime_temp_override_is_explicit(self):
        with patch.dict(os.environ, {'CREDPROOF_RUNTIME_TEMP': str(self.root / 'runs')}):
            self.assertEqual(self.root / 'runs', runtime_config.runtime_temp_root())

    def test_invalid_config_fails_closed_before_any_wsl_call(self):
        for override in ({'shell': 'anything'}, {'runtime_root': 'relative/path'},
                         {'runtime_root': '/tmp/a\ncommand'}, {'wsl_distribution': '--exec'},
                         {'wsl_user': '../someone'}):
            with self.subTest(override=override):
                (self.root / 'config/local-runtime.json').write_text(json.dumps(override))
                with self.assertRaises(ValueError):
                    runtime_config.load_config(self.root)
                with patch.object(preflight.subprocess, 'run') as child:
                    self.assertFalse(preflight.observe(self.root)['ready'])
                    child.assert_not_called()

    def test_windows_bridge_passes_trusted_runtime_without_pinned_username(self):
        response = types.SimpleNamespace(returncode=0, stdout=b'{"status":"TEST_MOCK"}')
        with patch.object(isolation.sys, 'platform', 'win32'), patch.object(isolation.os, 'name', 'nt'), \
                patch.object(isolation.subprocess, 'run', return_value=response) as child:
            result = isolation._dispatch({'operation': 'run'})
        self.assertEqual(result['status'], 'TEST_MOCK')
        argv = child.call_args.args[0]
        self.assertNotIn('-u', argv)
        self.assertNotIn('shell', child.call_args.kwargs)
        packet = json.loads(child.call_args.kwargs['input'])
        self.assertEqual(packet['runtime_root'], '~/credproof-agent-runtime')
        self.assertNotIn('candidate_code', packet['request'])

    def test_linux_bridge_rebases_trusted_runner_without_changing_runner_bytes(self):
        import agent_pilot
        before = isolation.RUNNER.read_bytes()
        stub = types.ModuleType('agent_pilot.sandbox_runner')
        stub.handle = Mock(return_value={'status': 'TEST_MOCK_NO_EXECUTION'})
        configured = self.root / 'dedicated-runtime'
        with patch.object(isolation.sys, 'platform', 'linux'), \
                patch.object(isolation, 'linux_runtime_root', return_value=configured), \
                patch.dict('sys.modules', {'agent_pilot.sandbox_runner': stub}), \
                patch.object(agent_pilot, 'sandbox_runner', stub, create=True):
            isolation._dispatch({'operation': 'run'})
        self.assertEqual(stub.BASE, configured / 'isolation')
        self.assertEqual(stub.handle.call_args.args[1], hashlib.sha256(before).hexdigest())
        self.assertEqual(isolation.RUNNER.read_bytes(), before)

    def test_launch_requires_preflight_and_passes_absolute_root_with_separate_argv(self):
        observation = {'ready': True, 'isolation_ready': True, 'model_ready': True,
                       'runtime_root': '/home/test user/dedicated-runtime'}
        with patch.object(web, 'runtime_observation', return_value=observation):
            argv = web.launch_command(self.root, 'p01', self.root / 'output')
        self.assertIn('CREDPROOF_RUNTIME_ROOT=/home/test user/dedicated-runtime', argv)
        self.assertIn('/home/test user/dedicated-runtime/venv/bin/python', argv)
        self.assertNotIn('tingfeng', argv)
        self.assertNotIn('sh', argv)
        with patch.object(web, 'runtime_observation', return_value={**observation, 'isolation_ready': False}):
            with self.assertRaises(ValueError):
                web.launch_command(self.root, 'p01', self.root / 'output')


class ReadOnlyPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runtime = Path(self.temp.name)
        self.identity = 'trusted-runner-test'
        self.isolation = self.runtime / 'isolation'
        for name, data in {'rootfs/usr/bin/python3': b'trusted runtime placeholder',
                           'tools/usr/bin/bwrap': b'not executed', 'seccomp.bpf': b'filter placeholder'}.items():
            path = self.isolation / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        tree = {'usr/bin/python3': preflight._file_hash(self.isolation / 'rootfs/usr/bin/python3')}
        receipt = {'ready': True, 'runner_id': self.identity, 'kernel': platform.release(),
                   'checks': {key: True for key in preflight.REQUIRED_CHECKS},
                   'rootfs_id': hashlib.sha256(json.dumps(tree, sort_keys=True).encode()).hexdigest(),
                   'bwrap_sha256': preflight._file_hash(self.isolation / 'tools/usr/bin/bwrap'),
                   'seccomp_sha256': preflight._file_hash(self.isolation / 'seccomp.bpf')}
        (self.isolation / 'probe-receipt.json').write_text(json.dumps(receipt))
        for name in ('venv/bin/python', 'ollama/bin/ollama'):
            path = self.runtime / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'never executed')
        descriptors = []
        for data in (b'model configuration', b'fake small weight; never loaded'):
            digest = hashlib.sha256(data).hexdigest()
            blob = self.runtime / 'models/blobs' / ('sha256-' + digest)
            blob.parent.mkdir(parents=True, exist_ok=True)
            blob.write_bytes(data)
            descriptors.append({'digest': 'sha256:' + digest, 'size': len(data)})
        self.manifest = self.runtime / 'models/manifests/registry.ollama.ai/library/qwen3-coder/30b'
        self.manifest.parent.mkdir(parents=True)
        self.manifest.write_text(json.dumps({'config': descriptors[0], 'layers': descriptors[1:]}))
        self.executable = patch.object(preflight.os, 'access', return_value=True)
        self.executable.start()

    def tearDown(self):
        self.executable.stop()
        self.temp.cleanup()

    def observe(self):
        with patch.object(preflight.subprocess, 'run') as child:
            value = preflight._inspect_runtime(self.runtime, self.identity, preflight.REQUIRED_CHECKS)
            child.assert_not_called()
        return value

    def test_observation_is_read_only_and_separates_model_from_isolation(self):
        before = {str(p): p.read_bytes() for p in self.runtime.rglob('*') if p.is_file()}
        value = self.observe()
        self.assertTrue(value['ready'])
        self.assertFalse(value['model_executed'])
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.runtime.rglob('*') if p.is_file()})
        self.manifest.unlink()
        value = self.observe()
        self.assertTrue(value['isolation_ready'])
        self.assertFalse(value['model_ready'])
        self.assertFalse(value['ready'])

    def test_missing_gate_changed_rootfs_and_missing_mandatory_check_block(self):
        path = self.isolation / 'probe-receipt.json'
        original = path.read_bytes()
        path.unlink()
        self.assertFalse(self.observe()['isolation_ready'])
        path.write_bytes(original)
        receipt = json.loads(original)
        receipt['checks'].pop(preflight.REQUIRED_CHECKS[0])
        path.write_text(json.dumps(receipt))
        self.assertFalse(self.observe()['isolation_ready'])
        path.write_bytes(original)
        (self.isolation / 'rootfs/usr/bin/python3').write_bytes(b'changed runtime')
        value = self.observe()
        self.assertFalse(value['isolation_ready'])
        self.assertTrue(value['model_ready'])

    def test_small_blob_exact_hash_is_authority_and_size_discrepancy_is_explicit(self):
        manifest = json.loads(self.manifest.read_text())
        manifest['config']['size'] -= 3
        self.manifest.write_text(json.dumps(manifest))
        value = self.observe()
        self.assertTrue(value['model_ready'])
        warning = value['model_files']['warnings'][0]
        self.assertEqual(warning['code'], 'SMALL_BLOB_SIZE_METADATA_MISMATCH')
        self.assertTrue(warning['sha256_verified'])
        blob = self.runtime / 'models/blobs' / manifest['config']['digest'].replace(':', '-')
        raw = blob.read_bytes()
        blob.write_bytes(b'X' + raw[1:])  # Same size, wrong content identity.
        self.assertFalse(self.observe()['model_ready'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
