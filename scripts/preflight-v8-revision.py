"""Current worker schema + v7 actual states; no inference or candidate execution."""
import ast
import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent_pilot.model_client import compact_messages_for_budget, to_ollama_messages, estimate_input_budget
from agent_pilot.tools import StrictTool
from credproof_safety.agent import _MODEL_SCRIPT, _model_work_feedback, _model_initial_context, _phase_rejection
from credproof_safety.config import load_config
import importlib.util
spec = importlib.util.spec_from_file_location('current_replay', ROOT / 'scripts/replay-context-budget-v6-current-client.py')
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)
oai_to_qwen = replay.oai_to_qwen


def current_worker():
    tree = ast.parse(_MODEL_SCRIPT)
    system = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == 'system' for t in n.targets))
    tools_node = next(n.value for n in tree.body if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == 'tools' for t in n.targets))
    tools = []
    for n in tools_node.elts:
        name, description, properties, required = [ast.literal_eval(a) for a in n.args[:4]]
        tools.append({'type': 'function', 'function': StrictTool(name, description, properties, required,
                                                               lambda _: {}, []).function})
    return system, tools


def main():
    target = Path(sys.argv[1])
    base = ROOT / 'docs/reusable-tool-safety/acceptance/20261007-return-redirect/context-budget-pilot-v7'
    trace = base / 'formal-p01-model-result-artifacts/model-work/model-trace'
    artifacts = base / 'formal-p01-model-result-artifacts'
    config = load_config(ROOT / 'examples/material_assistant/credproof.toml')
    initial = json.loads((base / 'formal-p01-model-result.json').read_text(encoding='utf8'))['initial']
    report = json.loads((artifacts / 'verification-history/verification-02.json').read_text(encoding='utf8'))
    system, tools = current_worker()
    records = []
    target.mkdir(parents=True, exist_ok=True)
    for number, label in ((1, 'initial'), (3, 'evidence_and_sources'), (7, 'candidate2_auto_FAIL'),
                          (8, 'historical_read_after_FAIL'), (9, 'historical_second_read'),
                          (7, 'current_revision_rejection')):
        original = json.loads((trace / f'model-{number:02d}-request.json').read_text(encoding='utf8'))
        wire = copy.deepcopy(original)
        wire['messages'][0]['content'] = system
        wire['tools'] = tools
        # Current task text is generated from frozen configuration, not a reference patch.
        wire['messages'][1]['content'] = (
            'Inspect the registered source and controlled evidence. This first request includes the '
            'following bounded current-task context. It is task data, not permission or a reference patch. '
            'Call get_evidence before reading the listed files, then submit a candidate for automatic verification.\n\n'
            + json.dumps(_model_initial_context(initial, config), ensure_ascii=False, sort_keys=True))
        state = None
        for m in wire['messages']:
            if m['role'] == 'user' and 'executor-context/v1' in m['content']:
                state = json.loads(m['content'])['executor_state']
        for m in wire['messages']:
            if m['role'] != 'tool':
                continue
            v = json.loads(m['content'])
            if v.get('status') == 'OK' and 'readable_paths' in v:
                v = {'status': 'OK', **_model_work_feedback(initial, config)}
            if v.get('status') == 'ACCEPTED_FOR_VERIFICATION':
                v['verification']['report'] = _model_work_feedback(report, config)
                v['executor_state'] = {**state, 'allowed_actions': ['submit_patch', 'stop']}
            if m is next((x for x in reversed(wire['messages']) if x['role'] == 'tool'), None) and state:
                v['executor_state'] = {**state, 'allowed_actions': ['submit_patch', 'stop']}
            m['content'] = json.dumps(v, ensure_ascii=False)
        internal = oai_to_qwen(wire)
        if label == 'current_revision_rejection':
            required = set(state['required_read_paths'])
            reason = _phase_rejection('read_code', evidence_ready=True, read_paths=required,
                                      required_read_paths=required, accepted_candidates=2,
                                      last_verified_candidate=2, last_verification_verdict='FAIL')
            internal.extend([
                {'role': 'assistant', 'content': '', 'function_call': {
                    'name': 'read_code', 'arguments': '{"path":"tool.py"}'},
                 'extra': {'function_id': 'protocol-revision-rejection'}},
                {'role': 'function', 'content': json.dumps({
                    'status': 'REJECTED', 'reason': reason, 'allowed_actions': ['submit_patch', 'stop'],
                    'executor_state': {**state, 'tool_calls_used': 8, 'remaining_tool_calls': 4,
                                       'revision_phase_rejections': 1, 'allowed_actions': ['submit_patch', 'stop']}}),
                 'extra': {'function_id': 'protocol-revision-rejection'}},
            ])
        # Legacy request8/9 already moved accepted metadata into a user block.
        # Replay the original paired submit from request7 to preserve production inputs.
        if number in (8, 9):
            seven = json.loads((trace / 'model-07-request.json').read_text(encoding='utf8'))
            submit_call = next(m for m in seven['messages'] if any(
                c['function']['name'] == 'submit_patch' for c in m.get('tool_calls', [])))
            submit_result = next(m for m in seven['messages'] if m.get('role') == 'tool'
                                 and json.loads(m['content']).get('status') == 'ACCEPTED_FOR_VERIFICATION')
            pair = oai_to_qwen({'messages': [submit_call, submit_result]})
            accepted = json.loads(pair[1]['content'])
            accepted['verification']['report'] = _model_work_feedback(report, config)
            pair[1]['content'] = json.dumps(accepted)
            internal[2:2] = pair
        payload = {**wire, 'messages': to_ollama_messages(compact_messages_for_budget(internal))}
        budget = estimate_input_budget(payload, int(payload['max_tokens']))
        ids = [c['id'] for m in payload['messages'] for c in m.get('tool_calls', [])]
        results = [m['tool_call_id'] for m in payload['messages'] if m['role'] == 'tool']
        candidate_visible = any(
            '8d5f112086bbf8cb39980604cfd981e1c1898b3d1a9e0995e13050106d3c359d' in m.get('content','')
            for m in payload['messages']) if number >= 7 else True
        checks = {'paired': ids == results, 'candidate_object_visible': candidate_visible,
                  'budget': budget['within_context_budget'] and budget['within_wire_limit']}
        if number >= 7:
            text = json.dumps(payload['messages'])
            checks.update({'failure_fact_visible': '/secret' in text and 'credential_ok' in text,
                           'tests_visible': 'test_authorized_business_path_and_service' in text,
                           'source_visible': 'def run(request)' in text})
        if label == 'current_revision_rejection':
            checks['true_rejection_visible'] = 'revision_source_already_current' in text and 'REJECTED' in text
        (target / (label + '-payload.json')).write_text(json.dumps(payload, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
        records.append({'stage': label, 'kind': 'PROTOCOL_REPLAY_CURRENT_CODE', 'budget': budget, 'checks': checks})
    summary = {'model_calls': 0, 'candidate_execution': False, 'schema': 'credproof.revision-preflight/v1',
               'stages': records, 'all_pass': all(all(x['checks'].values()) for x in records),
               'tool_schema_sha256': hashlib.sha256(json.dumps(tools, sort_keys=True).encode()).hexdigest()}
    (target/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary['all_pass'] else 1

if __name__ == '__main__':
    raise SystemExit(main())


