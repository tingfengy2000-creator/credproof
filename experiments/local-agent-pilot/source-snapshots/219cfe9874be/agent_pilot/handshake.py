"""Real two-step runtime-nonce tool handshake, not a replay or a repair benchmark."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets

from .model_client import LocalAgentClient
from .tools import StrictTool, code_path, dispatch, write_json_new


def run(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    audit, state = [], {}
    def issue(args):
        if state:
            return {'status': 'REJECTED', 'reason': 'challenge_already_issued'}
        state.update(nonce=secrets.token_hex(12), value=secrets.randbelow(900) + 100)
        return {'nonce': state['nonce'], 'value': state['value'], 'operation': 'answer = value + 17'}
    def finish(args):
        passed = bool(state) and args['nonce'] == state['nonce'] and args['answer'] == state['value'] + 17
        state['completed'] = passed
        return {'status': 'PASS' if passed else 'FAIL', 'reason': 'actual_dependency_checked'}
    def read(args):
        code_path(args['path'])
        return {'content': '# This handshake has no repair source.'}
    tools = [StrictTool('issue_challenge', 'Create a fresh runtime challenge; call once before completing it.', {}, [], issue, audit),
             StrictTool('complete_challenge', 'Actually validate the nonce and computed answer from issue_challenge.',
                        {'nonce': {'type': 'string'}, 'answer': {'type': 'integer'}}, ['nonce', 'answer'], finish, audit),
             StrictTool('read_code', 'Read only the explicitly allowed tool.py path.', {'path': {'type': 'string'}}, ['path'], read, audit)]
    negative = {
        'unknown_tool': dispatch(tools, 'arbitrary_shell', {}),
        'wrong_type': dispatch(tools, 'complete_challenge', {'nonce': 4, 'answer': 'no'}),
        'extra_argument': dispatch(tools, 'read_code', {'path': 'tool.py', 'shell': 'x'}),
        'outside_path': dispatch(tools, 'read_code', {'path': '../../protocol.json'}),
    }
    assert all(x['status'] == 'REJECTED' for x in negative.values())
    write_json_new(output / 'programmatic-boundary-tests.json', negative)
    audit.clear()  # These four programmatic tests must not count as model tool use.
    client = LocalAgentClient(tools=tools,
        system_message='You are testing a local function-calling interface. Actually use the tools. First call issue_challenge, then read its runtime result and call complete_challenge with its nonce and value + 17. No guess or textual imitation counts. Stop after completion.',
        log_dir=output / 'model', max_model_calls=12, request_timeout_s=120, task_budget_s=900)
    result = client.run([{'role': 'user', 'content': 'Perform the real two-step challenge now.'}])
    result.update(tool_audit=audit, dependency_verified=state.get('completed', False),
                  execution_kind='real-local-model-inference', completed_at_utc=datetime.now(timezone.utc).isoformat(),
                  does_not_establish='Credential repair capability or offline egress isolation')
    write_json_new(output / 'result.json', result)
    print(json.dumps({'dependency_verified': result['dependency_verified'], 'model_calls': result.get('model_calls'),
                      'status': result.get('status'), 'output': str(output)}), flush=True)
    return 0 if result['dependency_verified'] and result.get('model_calls', 0) >= 2 else 1


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    raise SystemExit(run(p.parse_args().output))
