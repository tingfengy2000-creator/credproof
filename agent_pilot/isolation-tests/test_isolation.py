"""Gate and retained-observation checks; this test does not execute candidates."""
from pathlib import Path
import hashlib
import json
import platform
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from agent_pilot import sandbox_runner as runner


class IsolationTests(unittest.TestCase):
    def test_retained_normal_and_nested_boundaries(self):
        folder = Path(__file__).parent / 'observations-20260929T062810Z'
        identity = hashlib.sha256((ROOT / 'agent_pilot/sandbox_runner.py').read_bytes()).hexdigest()
        for name in ('probe-normal.json', 'probe-nested.json'):
            record = json.loads((folder / name).read_text())
            self.assertTrue(record['ready'])
            self.assertFalse(record['candidate_executed'])
            self.assertEqual(record['runner_id'], identity)
            self.assertGreaterEqual(len(record['checks']), 25)
            self.assertTrue(all(value is True for value in record['checks'].values()))
            for ns in ('user', 'mnt', 'pid', 'net', 'ipc', 'uts'):
                self.assertNotEqual(record['initial_namespace_ids'][ns],
                                    record['namespace_observation']['namespaces'][ns])
            self.assertEqual(record['probe_processes']['basic']['returncode'], 0)
            self.assertNotEqual(record['probe_processes']['cpu']['returncode'], 0)
            self.assertEqual(record['probe_processes']['wall']['status'], 'TIMEOUT')

    def test_runtime_location_does_not_follow_service_home(self):
        self.assertEqual(str(runner.BASE), '/home/tingfeng/credproof-agent-runtime/isolation')

    def fake_facilities(self, base):
        (base / 'tools/usr/bin').mkdir(parents=True)
        (base / 'rootfs').mkdir()
        (base / 'tools/usr/bin/bwrap').write_bytes(b'trusted-test-placeholder-not-executable')
        (base / 'rootfs/runtime').write_bytes(b'original-runtime')
        (base / 'seccomp.bpf').write_bytes(b'trusted-test-filter-placeholder')
        receipt = {'ready': True, 'runner_id': 'test-runner',
            'bwrap_sha256': runner.digest((base / 'tools/usr/bin/bwrap').read_bytes()),
            'rootfs_id': runner.tree_identity(base / 'rootfs'),
            'seccomp_sha256': runner.digest((base / 'seccomp.bpf').read_bytes()),
            'kernel': platform.release()}
        (base / 'probe-receipt.json').write_text(json.dumps(receipt))
        return receipt

    def assert_gate_closed(self, base, identity='test-runner'):
        with patch.object(runner, 'BASE', base), patch.object(runner, 'execute') as execution:
            result = runner.handle({'operation': 'run', 'candidate_code': '# never executed',
                'harness_code': '# never executed', 'input_data': {}}, identity)
        execution.assert_not_called()
        self.assertEqual(result['status'], 'ISOLATION_ERROR')
        self.assertEqual(result['stdout'], '')

    def test_missing_or_failed_probe_cannot_execute(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            self.assert_gate_closed(base)
            receipt = self.fake_facilities(base)
            receipt['ready'] = False
            (base / 'probe-receipt.json').write_text(json.dumps(receipt))
            self.assert_gate_closed(base)

    def test_changed_facility_or_supervisor_invalidates_gate(self):
        for relative in ('rootfs/runtime', 'tools/usr/bin/bwrap', 'seccomp.bpf'):
            with self.subTest(changed=relative), tempfile.TemporaryDirectory() as temp:
                base = Path(temp)
                self.fake_facilities(base)
                (base / relative).write_bytes(b'changed')
                self.assert_gate_closed(base)
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            self.fake_facilities(base)
            self.assert_gate_closed(base, 'other-runner')

    def test_oversize_or_out_of_profile_inputs_do_not_start_a_process(self):
        inputs = [
            {'candidate_code': 'x' * 65537, 'harness_code': '', 'input_data': {}},
            {'candidate_code': '', 'harness_code': 'x' * 131073, 'input_data': {}},
            {'candidate_code': '', 'harness_code': '', 'input_data': {'x': 'y' * 32768}},
            {'candidate_code': '', 'harness_code': '', 'input_data': {}, 'timeout_seconds': 0.1},
        ]
        with patch.object(runner, 'verify_prepared', return_value={}), patch.object(runner.subprocess, 'Popen') as process:
            for data in inputs:
                result = runner.handle({'operation': 'run', **data}, 'ignored')
                self.assertEqual(result['status'], 'ISOLATION_ERROR')
        process.assert_not_called()

    def test_failed_or_incomplete_basic_probe_cannot_be_outvoted_by_limit_checks(self):
        names = ('user', 'mnt', 'pid', 'net', 'ipc', 'uts')
        incomplete = {key: True for key in runner.REQUIRED_CHECKS if key != 'no_host_home'}
        variants = [
            {'status': 'PROCESS_ERROR', 'stdout': '', 'returncode': 1, 'duration_ms': 1},
            {'status': 'OK', 'stdout': json.dumps({'checks': incomplete,
                'namespaces': {name: 'different-child-id' for name in names}}),
                'returncode': 0, 'duration_ms': 1},
        ]
        for basic in variants:
            results = [basic,
                {'status': 'OUTPUT_LIMIT', 'stdout': '', 'returncode': -9, 'duration_ms': 1},
                {'status': 'PROCESS_ERROR', 'stdout': '', 'returncode': -9, 'duration_ms': 1},
                {'status': 'TIMEOUT', 'stdout': '', 'returncode': -9, 'duration_ms': 1}]
            with patch.object(runner, 'verify_prepared', return_value={}), \
                    patch.object(runner, 'atomic_json'), patch.object(runner, 'execute', side_effect=results):
                result = runner.probe('ignored')
            self.assertFalse(result['ready'])
            self.assertTrue(result['checks']['output_bounded'])
            self.assertTrue(result['checks']['cpu_limited'])
            self.assertTrue(result['checks']['wall_time_limited'])

    def test_interrupted_reprobe_does_not_leave_previous_green_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            (base / 'probe-receipt.json').write_text('{"ready":true}')
            with patch.object(runner, 'BASE', base), \
                    patch.object(runner, 'verify_prepared', return_value={'ready': True}), \
                    patch.object(runner, 'execute', side_effect=RuntimeError('fixed test interruption')):
                result = runner.handle({'operation': 'probe'}, 'ignored')
            self.assertEqual(result['status'], 'ISOLATION_ERROR')
            self.assertFalse(json.loads((base / 'probe-receipt.json').read_text())['ready'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
