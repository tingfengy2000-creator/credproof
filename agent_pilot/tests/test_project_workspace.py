from pathlib import Path
import tempfile
import unittest
import zipfile

from agent_pilot.project_workspace import ProjectWorkspace


class ProjectWorkspaceTests(unittest.TestCase):
    def test_registered_project_scope_and_export_are_real(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / 'consumer'
            project.mkdir()
            (project / 'tool.py').write_text('def run(request, auth_service):\n    return {}\n', encoding='utf-8')
            (project / 'tests').mkdir()
            (project / 'tests' / 'test_business.py').write_text('def test_smoke():\n    assert True\n', encoding='utf-8')
            (project / 'credproof.toml').write_text('''schema = "credproof.project-safety/v1"\n[project]\nroot = "."\ntests = ["tests"]\noptional_tests = []\nsource_scope = ["tool.py"]\nmutable_scope = ["tool.py"]\n[files]\nallowed_dirs = ["data"]\nforbidden_dirs = ["secrets"]\n[network]\nallowed_services = []\n[credentials]\nenv = "SYNTHETIC_TOKEN"\n[entry]\nmodule = "tool"\ncallable = "run"\n''', encoding='utf-8')
            workspace = ProjectWorkspace(root, config_path=project / 'credproof.toml')
            selected = workspace.describe('authorized-project')
            self.assertEqual(selected['config']['credential_env'], 'SYNTHETIC_TOKEN')
            self.assertTrue(selected['source_code'])
            archive = workspace.export('authorized-project')
            self.assertTrue(archive.is_file())
            self.assertEqual(archive.read_bytes()[:2], b'PK')
            with zipfile.ZipFile(archive) as bundle:
                self.assertIn('export-instructions.txt', bundle.namelist())


if __name__ == '__main__':
    unittest.main(verbosity=2)
