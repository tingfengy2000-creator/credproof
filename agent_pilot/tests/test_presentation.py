"""Display consistency using three existing historical cases; no candidate execution."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from agent_pilot import presentation, web


class PresentationHistoryTests(unittest.TestCase):
    def test_real_replays_preserve_failed_stage_and_hide_changed_copy(self):
        repository = Path(__file__).resolve().parents[2]
        cases = [story['case_id'] for story in presentation.STORIES]
        self.assertEqual(cases, ['h01', 'h03', 'h07'])
        originals = {}
        for case in cases:
            for method in ('A-fixed', 'C-agent'):
                source = repository / presentation.BATCH / case / method
                originals[source] = presentation.digest_tree(source)
        with tempfile.TemporaryDirectory(prefix='credproof-presentation-consistency-') as temporary:
            root = Path(temporary)
            fixtures = root / 'agent_pilot/holdout-v1'
            fixtures.mkdir(parents=True)
            (fixtures / 'manifest.json').write_text(json.dumps({'cases': [{'id': case} for case in cases]}))
            for case in cases:
                (fixtures / case).mkdir()
                shutil.copyfile(repository / 'agent_pilot/holdout-v1' / case / 'tool.py', fixtures / case / 'tool.py')
                for method in ('A-fixed', 'C-agent'):
                    source = repository / presentation.BATCH / case / method
                    shutil.copytree(source, root / presentation.BATCH / case / method)
            app = web.Application(root=root)
            presentation.install_demonstrations(app)
            self.assertEqual(len(app.runs), 3)
            self.assertEqual([item['mode'] for item in app.demonstrations], ['REPLAY'] * 3)
            for run in app.runs.values():
                view = app.view(run.id)
                self.assertEqual(view['mode'], 'REPLAY')
                self.assertEqual(view['presentation']['mode'], 'REPLAY')
                self.assertIn('历史记录', view['presentation']['notice'])
                self.assertEqual(view['presentation']['fixed_comparison']['method'], 'A-fixed')
            h03 = next(run for run in app.runs.values() if run.case_id == 'h03')
            story = presentation.story_for(app, h03)
            self.assertEqual([stage['validation']['verdict'] for stage in story['stages']], ['FAIL', 'PASS'])
            self.assertEqual([stage['candidate_id'] for stage in story['stages']], ['candidate-1', 'candidate-2'])
            # Stage identities come from actual historical candidate files, not sample badges.
            for stage in story['stages']:
                code = (h03.method / (stage['candidate_id'] + '.py')).read_text(encoding='utf-8')
                self.assertEqual(stage['sha256'], hashlib.sha256(code.encode()).hexdigest())
            target = h03.method / 'final-candidate.py'
            target.write_bytes(target.read_bytes() + b'\n# disposable presentation-copy drift\n')
            changed = app.view(h03.id)
            self.assertIsNone(changed['presentation'])
            self.assertIsNone(changed['validation'])
            self.assertEqual(changed['mode'], 'REPLAY')
            # Curated source records in the temporary checkout also remain untouched.
            for source, identity in originals.items():
                self.assertEqual(presentation.digest_tree(root / source.relative_to(repository)), identity)
        for source, identity in originals.items():
            self.assertEqual(presentation.digest_tree(source), identity)


if __name__ == '__main__':
    unittest.main(verbosity=2)
