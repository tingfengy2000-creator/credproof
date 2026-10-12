"""Publication scanner regression; synthetic strings, no security execution."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

path=Path(__file__).resolve().parents[2]/'scripts/delivery/scan.py'
spec=importlib.util.spec_from_file_location('delivery_scan',path)
scanner=importlib.util.module_from_spec(spec);spec.loader.exec_module(scanner)


class ScanTests(unittest.TestCase):
    def test_decodes_json_without_treating_python_newlines_as_drive_paths(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'data.json'
            p.write_text(json.dumps({'code':'try:\n    pass\nexcept ValueError as e:\n    raise\n'}),encoding='utf8')
            self.assertEqual(scanner.scan(root)['sensitive_hits'],0)
            p.write_text(json.dumps({'path':'C:\\Users\\PrivateAccount\\data.txt'}),encoding='utf8')
            self.assertGreater(scanner.scan(root)['sensitive_hits'],0)

    def test_scans_zip_members_and_blocks_non_allowlisted_identity(self):
        with tempfile.TemporaryDirectory() as root:
            with zipfile.ZipFile(Path(root)/'data.zip','w') as z:z.writestr('inner.json',json.dumps({'name':'synthetic-private-host'}))
            self.assertGreater(scanner.scan(root,['synthetic-private-host'])['sensitive_hits'],0)

    def test_real_key_pattern_is_not_removed_as_synthetic(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root)/'key.txt').write_text('AKIA'+'A'*16,encoding='utf8')
            self.assertTrue(any(f['kind']=='aws_access_key' for f in scanner.scan(root)['findings']))


if __name__=='__main__':unittest.main()
