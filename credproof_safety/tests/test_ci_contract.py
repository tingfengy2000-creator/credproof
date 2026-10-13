"""CI protocol tests, not hosted-runner or container acceptance."""
import importlib.util
import io
import json
from pathlib import Path
import re
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).parents[2]
def load(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

CI=load('ci_orchestration',ROOT/'scripts/ci/run.py')
SCAN=load('ci_image_scan',ROOT/'scripts/runtime/scan-image.py')


class CIContractTests(unittest.TestCase):
    def test_exit_record_precedes_final_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);rec=CI.Recorder(out)
            with patch.object(CI.subprocess,'run') as execute:
                execute.return_value=type('Result',(),{'stdout':'FAIL','stderr':'','returncode':2})()
                self.assertEqual(rec.run('check-0',['installed-python','-I','-m','credproof_safety']),2)
            self.assertEqual(json.loads((out/'check-0/command.json').read_text())['exit_code'],2)
            self.assertEqual(CI.gate(out),1)

    def test_target_registry_rejects_escape_duplicate_and_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'.credproof').mkdir();(root/'credproof.toml').write_text('')
            for text in ('../outside.toml','/absolute.toml','credproof.toml\ncredproof.toml',''):
                (root/'.credproof/targets.txt').write_text(text)
                with self.assertRaises((ValueError,FileNotFoundError)):CI.targets(root)
            (root/'.credproof/targets.txt').write_text('# comment\ncredproof.toml\n')
            self.assertEqual(CI.targets(root),['credproof.toml'])

    def test_workflow_order_permissions_and_pins(self):
        value=(ROOT/'.github/workflows/credproof.yml').read_text()
        self.assertIn('on: pull_request\n',value)
        self.assertNotIn('pull_request_target',value)
        self.assertNotIn('workflow_dispatch',value)
        self.assertEqual(value.count('runs-on: ubuntu-24.04'),2)
        for action in re.findall(r'(?:uses:)\s+(\S+)',value):
            self.assertRegex(action,r'^[^@]+@[0-9a-f]{40}$')
        self.assertEqual(value.count('github/codeql-action/upload-sarif@'),1)
        self.assertIn('continue-on-error: true',value)
        self.assertLess(value.index('Upload native evidence'),value.index('Native gate'))
        self.assertLess(value.index('Upload container evidence'),value.index('Container gate'))
        self.assertIn('persist-credentials: false',value)

    def test_scan_incomplete_names_oversized_member(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive=Path(tmp)/'image.tar'
            with tarfile.open(archive,'w') as tf:
                member=tarfile.TarInfo('var/lib/apt/lists/example');member.size=SCAN.MAX_TEXT+1
                tf.addfile(member,io.BytesIO(b'a'*member.size))
            with self.assertRaises(SCAN.ScanIncomplete) as raised:SCAN.scan(archive)
            self.assertEqual(str(raised.exception),'text_size_limit')
            self.assertEqual(raised.exception.details['member'],'var/lib/apt/lists/example')
            self.assertEqual(raised.exception.details['limit_bytes'],SCAN.MAX_TEXT)
            result=Path(tmp)/'worker.json';SCAN.worker(str(archive),[],[],10,SCAN.MAX_MEMBER,str(result))
            self.assertEqual(json.loads(result.read_text())['report']['member'],'var/lib/apt/lists/example')

    def test_completed_scan_has_explicit_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive=Path(tmp)/'image.tar'
            with tarfile.open(archive,'w') as tf:
                member=tarfile.TarInfo('etc/example');member.size=5;tf.addfile(member,io.BytesIO(b'plain'))
            self.assertEqual(SCAN.scan(archive)['status'],'COMPLETED')

    def test_vendor_exception_never_accepts_changed_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive=Path(tmp)/'image.tar'
            def write(data):
                with tarfile.open(archive,'w') as tf:
                    member=tarfile.TarInfo('usr/share/doc/vendor/copyright');member.size=len(data);tf.addfile(member,io.BytesIO(data))
            write(b'Legal contact public@example.com')
            finding=SCAN.scan(archive)['findings'][0]
            exception={k:finding[k] for k in ('file','file_sha256','kind','match_sha256')}
            exception['reason']='Public vendor legal contact, exact bytes only'
            self.assertEqual(SCAN.scan(archive,[exception])['sensitive_hits'],0)
            write(b'Changed bytes public@example.com')
            self.assertGreater(SCAN.scan(archive,[exception])['sensitive_hits'],0)

    def test_pip_python_models_are_not_model_weights(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive=Path(tmp)/'image.tar'
            with tarfile.open(archive,'w') as tf:
                for name in ['opt/app/site-packages/pip/_internal/models/x.py','opt/models/weights.bin']:
                    member=tarfile.TarInfo(name);member.size=5;tf.addfile(member,io.BytesIO(b'plain'))
            findings=SCAN.scan(archive)['findings']
            self.assertEqual([x['file'] for x in findings if x['kind']=='forbidden_image_material'],['opt/models/weights.bin'])


if __name__=='__main__':unittest.main()
