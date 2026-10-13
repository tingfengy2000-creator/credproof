"""Protocol tests, not candidate executions or container acceptance."""
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from credproof_safety import cli
from credproof_safety.runtime_setup import inventory, safe_root, setup
from credproof_safety.doctor import doctor

SPEC=importlib.util.spec_from_file_location('image_scan',Path(__file__).parents[2]/'scripts/runtime/scan-image.py')
SCAN=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(SCAN)


class RuntimeTests(unittest.TestCase):
    def test_existing_mismatch_never_prepares_or_deletes(self):
        with tempfile.TemporaryDirectory() as tmp:
            original=Path(tmp)/'old';original.mkdir();file=original/'keep.txt';file.write_bytes(b'preserve')
            with patch('credproof_safety.runtime_setup.supported'), patch('credproof_safety.runtime_setup.verify_runtime',side_effect=ValueError('changed')):
                with self.assertRaises(ValueError):setup(original)
            self.assertEqual(file.read_bytes(),b'preserve')

    def test_existing_matching_no_receipt_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/'receipt';file.write_bytes(b'original')
            with patch('credproof_safety.runtime_setup.supported'), patch('credproof_safety.runtime_setup.verify_runtime',return_value={}) as verify:
                root,status=setup(tmp)
            verify.assert_called_once();self.assertEqual(status,'REUSED');self.assertEqual(file.read_bytes(),b'original')

    def test_untrusted_cached_package_is_not_extracted(self):
        if __import__('os').name=='nt':self.skipTest('Linux preparation imports resource; checked in WSL')
        with tempfile.TemporaryDirectory() as tmp:
            cache=Path(tmp)/'wrong.deb';cache.write_bytes(b'not an official package')
            with patch('credproof_safety.runtime_setup.supported'), patch('credproof_safety.runtime_setup.subprocess.run') as run:
                with self.assertRaisesRegex(ValueError,'checksum mismatch'):
                    setup(Path(tmp)/'fresh',cache)
            run.assert_not_called()

    def test_inventory_binds_bytes_and_ignores_only_bytecode(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'code.py';p.write_bytes(b'a');first=inventory(tmp)
            p.write_bytes(b'b');self.assertNotEqual(first,inventory(tmp))
            p.write_bytes(b'a');cache=Path(tmp)/'__pycache__';cache.mkdir();(cache/'x.pyc').write_bytes(b'x')
            self.assertEqual(first,inventory(tmp))

    def test_root_and_symlink_rejected(self):
        if __import__('os').name=='nt':self.skipTest('Linux root/symlink check executed in WSL')
        with self.assertRaises(ValueError):safe_root('/')
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'alias';p.symlink_to('/')
            with self.assertRaises(ValueError):safe_root(p)

    def test_doctor_failure_is_structured_nonready(self):
        with patch('credproof_safety.doctor.supported',side_effect=ValueError('unsupported')):
            r=doctor()
        self.assertFalse(r['ready']);self.assertFalse(r['checks']['preconditions'])

    def test_doctor_cli_exit_codes(self):
        for ready,code in [(True,0),(False,4)]:
            with patch('credproof_safety.doctor.doctor',return_value={'ready':ready}),patch('sys.stdout',io.StringIO()):
                self.assertEqual(cli.main(['doctor']),code)


class TarTests(unittest.TestCase):
    def archive(self, root, entries):
        path=Path(root)/'image.tar'
        with tarfile.open(path,'w') as tf:
            for name,data in entries:
                item=tarfile.TarInfo(name);item.size=len(data);tf.addfile(item,io.BytesIO(data))
        return path

    def test_safe_tar_scans_runtime_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=SCAN.scan(self.archive(tmp,[('opt/runtime/rootfs/usr/lib/readme',b'safe'),('opt/app/venv/readme',b'safe')]))
        self.assertEqual(r['files_scanned'],2);self.assertEqual(r['sensitive_hits'],0)

    def test_unsafe_tar_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ['/abs','../escape','ok/../../bad']:
                with self.assertRaises(ValueError):SCAN.scan(self.archive(tmp,[(name,b'x')]))

    def test_empty_tar_is_not_zero_hit_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):SCAN.scan(self.archive(tmp,[]))

    def test_secret_detected_without_printing_match(self):
        value=b'ghp_'+b'A'*36
        with tempfile.TemporaryDirectory() as tmp:r=SCAN.scan(self.archive(tmp,[('app/settings',value)]))
        self.assertGreater(r['sensitive_hits'],0);self.assertNotIn(value.decode(),json.dumps(r))

    def test_exact_exception_does_not_allow_other_file(self):
        import hashlib
        data=b'legal@example.org';digest=hashlib.sha256(data).hexdigest()
        e={'file':'LICENSE','file_sha256':digest,'kind':'email','match_sha256':digest,'reason':'Vendor legal contact'}
        with tempfile.TemporaryDirectory() as tmp:r=SCAN.scan(self.archive(tmp,[('LICENSE',data),('other',data)]),[e])
        self.assertEqual(len(r['reviewed_exceptions']),1);self.assertEqual(r['sensitive_hits'],1)

    def test_link_is_inventoried_not_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive=Path(tmp)/'links.tar'
            with tarfile.open(archive,'w') as tf:
                regular=tarfile.TarInfo('ok');regular.size=4;tf.addfile(regular,io.BytesIO(b'safe'))
                link=tarfile.TarInfo('alias');link.type=tarfile.SYMTYPE;link.linkname='/etc/shadow';tf.addfile(link)
            r=SCAN.scan(archive)
        self.assertEqual(r['files_scanned'],1);self.assertFalse(r['links'][0]['followed'])

    def test_duplicate_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):SCAN.scan(self.archive(tmp,[('same',b'a'),('same',b'b')]))

    def test_seccomp_provenance_and_clone3_fallback(self):
        import hashlib
        root=Path(__file__).parents[2]/'deploy/docker'
        source=(root/'seccomp-default-source.json').read_bytes()
        provenance=json.loads((root/'seccomp-source.json').read_text())
        self.assertEqual(hashlib.sha256(source).hexdigest(),provenance['sha256'])
        profile=json.loads((root/'seccomp-credproof.json').read_text())
        self.assertTrue(any(x['names']==['clone3'] and x.get('errnoRet')==38 for x in profile['syscalls']))
        original=json.loads(source)
        self.assertEqual(profile['syscalls'][:len(original['syscalls'])],original['syscalls'])
