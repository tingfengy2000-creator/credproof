"""Installed local-only entry for one authorised historical-candidate revision."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import sys

from .agent import request_feedback_revision
from .web_repair import _adapt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--registration', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    if not sys.flags.isolated:
        raise RuntimeError('installed_entry_requires_I')
    import credproof_safety.agent as agent
    import agent_pilot.bounded_patch as bounded
    import agent_pilot.output_format as formatter
    modules = [agent, bounded, formatter]
    if any('site-packages' not in mod.__file__ for mod in modules):
        raise RuntimeError('installed_modules_required')
    origin = {'interpreter': sys.executable, 'cwd': str(Path.cwd()), 'isolated': True,
              'distribution_version': importlib.metadata.version('credproof-safety'),
              'modules': {mod.__name__: mod.__file__ for mod in modules},
              'strategy': 'bounded_patch', 'profile': 'component_assisted',
              'execution_kind': 'new feedback revision linked to historical candidate'}
    (args.output/'origin.json').write_text(json.dumps(origin, indent=2)+'\n', encoding='utf8')
    result = request_feedback_revision(args.config, report_path=args.report,
        registration_path=args.registration, output=args.output/'repair.json')
    registration = json.loads(args.registration.read_text(encoding='utf8'))
    row = _adapt(args.config, args.output, registration['project_id'], 'p01', result)
    row['display_label'] = '基于历史候选的新反馈修订'
    row['parent_task_id'] = registration['parent_task_id']
    row['source_candidate_sha256'] = registration['source_candidate_sha256']
    # Keep provenance on the new record, never edit the parent's UNKNOWN row.
    path = args.output/'comparison/p01/C-agent/result.json'
    path.write_text(json.dumps(row, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(json.dumps({'task_status':result.get('task_status'), 'verdict':result.get('final',{}).get('verdict'),
                      'model_calls':result.get('model',{}).get('model_calls')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
