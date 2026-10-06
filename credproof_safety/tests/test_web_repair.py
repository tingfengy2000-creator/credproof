import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from credproof_safety import web_repair


class WebRepairAdapterTests(unittest.TestCase):
    def test_adapts_real_shape_without_turning_incomplete_into_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'tool.py').write_text('def run(request):\n    return {"ok": True}\n', encoding='utf-8')
            (root / 'credproof.toml').write_text('''schema = "credproof.project-safety/v1"\n\n[project]\nroot = "."\ntests = ["tests"]\nsource_scope = ["tool.py"]\nmutable_scope = ["tool.py"]\n[files]\nallowed_dirs = ["data"]\nforbidden_dirs = ["secrets"]\n[network]\n[credentials]\nenv = "CREDPROOF_TEST_CREDENTIAL"\n[entry]\nmodule = "tool"\ncallable = "run"\nrequest = { resource = "demo" }\n[limits]\ntimeout_seconds = 1\n''', encoding='utf-8')
            (root / 'tests').mkdir()
            (root / 'data').mkdir()
            (root / 'secrets').mkdir()
            output = root / 'out'
            artifact = root / 'repair-artifacts' / 'candidate'
            (artifact).mkdir(parents=True)
            (artifact / 'tool.py').write_text('def run(request):\n    return {"ok": True, "fixed": True}\n', encoding='utf-8')
            report = {'status': 'OK', 'task_status': 'INCOMPLETE',
                      'artifact_dir': str(artifact.parent.parent),
                      'initial': {'verdict': 'FAIL', 'observation_summary': {'classification': 'ACTUAL_VIOLATION'}},
                      'final': {'verdict': 'UNKNOWN', 'reasons': ['budget']},
                      'model': {'status': 'STOPPED_LIMIT', 'model_calls': 12},
                      'tool_trace': []}
            row = web_repair._adapt(root / 'credproof.toml', output, 'assistant-original', 'p01', report)
            self.assertEqual(row['task']['task_status'], 'INCOMPLETE')
            self.assertEqual(row['final_validation']['verdict'], 'UNKNOWN')
            self.assertEqual(row['initial_authority']['confirmed'], 'CONFIRMED_VIOLATION')
            self.assertTrue((output / 'comparison/p01/C-agent/result.json').is_file())
            saved = json.loads((output / 'comparison/p01/C-agent/result.json').read_text(encoding='utf-8'))
            self.assertNotEqual(saved['final_validation']['verdict'], 'PASS')


if __name__ == '__main__':
    unittest.main()
