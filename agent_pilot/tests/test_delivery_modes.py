import unittest
from unittest.mock import patch
from agent_pilot.web import Application, Problem


class DeliveryModesTests(unittest.TestCase):
    def test_view_never_inspects_or_starts_runtime(self):
        app=Application(access_mode='view')
        with patch('agent_pilot.web.runtime_observation', side_effect=AssertionError('must not call')):
            self.assertFalse(app.runtime()['ready'])
            with self.assertRaises(Problem): app.start('h01')
            with self.assertRaises(Problem): app.recheck('any')

    def test_recheck_does_not_offer_model_operation(self):
        app=Application(access_mode='recheck')
        with patch('agent_pilot.web.runtime_observation',return_value={'ready':True,'isolation_ready':True,'reasons':[]}):
            self.assertFalse(app.runtime()['ready'])
            self.assertTrue(app.runtime()['isolation_ready'])
            with self.assertRaises(Problem): app.start('h01')


if __name__=='__main__': unittest.main()
