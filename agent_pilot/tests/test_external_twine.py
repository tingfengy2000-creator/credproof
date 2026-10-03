import unittest
from unittest.mock import patch
from agent_pilot import external_twine as ext


class TwineBoundaryTests(unittest.TestCase):
    def test_original_and_public_fix_preserve_business_ast(self):
        self.assertEqual(ext.boundary(ext.original())['status'],'PASS')
        self.assertEqual(ext.boundary(ext.original(True))['status'],'PASS')

    def test_no_constant_return_or_host_execution(self):
        self.assertEqual(ext.boundary(ext.original().replace('return config','return {}'))['status'],'FAIL')
        self.assertEqual(ext.boundary(ext.original(True).replace('f"Malformed configuration in {config_file}.\\n"','str(exc)'))['status'],'FAIL')
        self.assertEqual(ext.boundary('import os\n'+ext.original())['status'],'FAIL')

    def test_isolation_missing_is_unknown_not_host_fallback(self):
        with patch.object(ext,'run_isolated',return_value={'status':'ISOLATION_ERROR'}):
            self.assertEqual(ext.verify(ext.original())['verdict'],'UNKNOWN')


if __name__=='__main__': unittest.main()
