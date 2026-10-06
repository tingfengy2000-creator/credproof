import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from credproof_safety import project_bundle
from credproof_safety.config import load_config
from credproof_safety.project import _digest_tree


class ProjectBundleProtocolTests(unittest.TestCase):
    def make_material(self, root: Path, verdict='FAIL'):
        candidate = root / 'artifacts' / 'candidate'
        candidate.mkdir(parents=True)
        (candidate / 'tool.py').write_text('def run(request):\n    return {"ok": True}\n', encoding='utf-8')
        (candidate / 'credproof.toml').write_text(
            'schema = "credproof.project-safety/v1"\n[project]\nroot = "."\ntests = ["tests"]\nsource_scope = ["tool.py"]\nmutable_scope = ["tool.py"]\n'
            '[files]\nallowed_dirs = ["data"]\nforbidden_dirs = ["secrets"]\n[network]\n[credentials]\nenv = "CREDPROOF_TEST_CREDENTIAL"\n[entry]\nmodule = "tool"\ncallable = "run"\n', encoding='utf-8')
        (candidate / 'tests').mkdir(); (candidate / 'data').mkdir(); (candidate / 'secrets').mkdir()
        method = root / 'method'; method.mkdir()
        (method / 'original.py').write_text('def run(request):\n    return {}\n', encoding='utf-8')
        (method / 'final-candidate.py').write_text((candidate / 'tool.py').read_text(), encoding='utf-8')
        final = {'verdict': verdict, 'project_tree_sha256': _digest_tree(candidate),
                 'config': load_config(candidate / 'credproof.toml', project_root=candidate).to_public_dict()}
        (method / 'result.json').write_text(json.dumps({
            'schema': 'credproof.web-live-record/v1', 'project_id': 'p', 'case_id': 'p01',
            'artifact_dir': str(root / 'artifacts'), 'final_validation': final,
            'task': {'task_status': 'INCOMPLETE'},
        }), encoding='utf-8')
        return method

    def test_schema_is_separate_and_material_change_is_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); method = self.make_material(root)
            bundle = root / 'bundle'; project_bundle.export_project_bundle(method, bundle)
            self.assertEqual(json.loads((bundle / 'manifest.json').read_text())['schema'], project_bundle.SCHEMA)
            (bundle / 'project/tool.py').write_text('def run(request):\n    return {"changed": True}\n', encoding='utf-8')
            result = project_bundle.recheck_project_bundle(bundle, root / 'changed.json')
            self.assertEqual(result['validation']['verdict'], 'UNKNOWN')
            self.assertIn('PROJECT_OBJECT_CHANGED', result['prior_report_reasons'])

    def test_current_fail_is_preserved_and_pass_protocol_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); method = self.make_material(root, verdict='FAIL')
            bundle = root / 'bundle'; project_bundle.export_project_bundle(method, bundle)
            with patch.object(project_bundle, 'check_project', return_value={'verdict': 'FAIL', 'checks': [], 'reasons': ['business']}):
                result = project_bundle.recheck_project_bundle(bundle, root / 'fresh.json')
            self.assertEqual(result['validation']['verdict'], 'FAIL')

    def test_export_rejects_candidate_change_before_first_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); method = self.make_material(root)
            (root / 'artifacts/candidate/tool.py').write_text(
                'def run(request):\n    return {"changed": True}\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'project_tree_mismatch'):
                project_bundle.export_project_bundle(method, root / 'bundle')

    def test_export_records_explicit_newline_mapping_for_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); method = self.make_material(root)
            candidate = root / 'artifacts/candidate/tool.py'
            candidate.write_bytes(candidate.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
            # The recorded validation must also refer to the changed artifact;
            # this models a real execution record rather than patching a digest.
            final = json.loads((method / 'result.json').read_text())
            (method / 'final-candidate.py').write_bytes(
                (method / 'final-candidate.py').read_bytes().replace(b'\r\n', b'\n'))
            final['final_validation']['project_tree_sha256'] = _digest_tree(root / 'artifacts/candidate')
            (method / 'result.json').write_text(json.dumps(final))
            result = project_bundle.export_project_bundle(method, root / 'bundle')
            binding = json.loads((root / 'bundle/report.json').read_text())['object_binding']
            self.assertTrue(binding['entry_normalized_equal'])
            self.assertEqual(binding['entry_candidate_newline'], 'CRLF')
            self.assertEqual(result['status'], 'EXPORTED')


if __name__ == '__main__':
    unittest.main()
