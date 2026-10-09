"""Bounded generation protocol tests, not model/security-case success counts."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from agent_pilot.bounded_patch import build_payload, parse_response, OUTPUT_TOKENS
from agent_pilot.model_client import estimate_input_budget
from credproof_safety.agent import _bounded_model_script, _bounded_initial_context, request_repair
from credproof_safety.config import load_config

ROOT = Path(__file__).resolve().parents[2]
V8 = ROOT / 'docs/reusable-tool-safety/acceptance/20261007-return-redirect/context-budget-pilot-v8/public-evidence'


def envelope(value, **extra):
    return dict(done=True, done_reason='stop', message={'role': 'assistant', 'content': json.dumps(value)}, **extra)


def test_request_uses_real_current_material_and_no_tools():
    config = load_config(ROOT / 'examples/material_assistant/credproof.toml')
    report = json.loads((V8/'initial-report.json').read_text(encoding='utf8'))
    context = _bounded_initial_context(report, config)
    code = (config.project_root/'tool.py').read_text(encoding='utf8')
    tests = {'tests/test_business.py': (config.project_root/'tests/test_business.py').read_text(encoding='utf8')}
    payload = build_payload(context, code, tests, {'verdict': 'FAIL'}, {'remaining_generations': 3})
    assert 'tools' not in payload
    assert 'native tool calls only' not in json.dumps(payload)
    assert 'get_evidence' not in json.dumps(payload)
    assert code in payload['messages'][1]['content']
    assert tests['tests/test_business.py'] in payload['messages'][1]['content']
    assert context['project']['entry_expected_error'] == 'ValueError'
    assert context['project']['scenarios'][1]['expected_error'] == 'HTTPError'
    budget = estimate_input_budget(payload, OUTPUT_TOKENS)
    assert budget['input_token_limit'] == 13824 and budget['within_context_budget']


def test_patch_and_stop_have_distinct_real_branches():
    assert parse_response(envelope({'action':'PATCH','code':'x=1\n','reason':'change'}))['action'] == 'PATCH'
    assert parse_response(envelope({'action':'STOP','code':None,'reason':'cannot preserve required behavior'}))['action'] == 'STOP'
    worker = _bounded_model_script()
    compile(worker, '<bounded-worker>', 'exec')
    assert "if obj['action']=='STOP': terminal='STOPPED_BY_MODEL'; break" in worker
    assert 'native tool calls only' not in worker
    assert "program_call('submit_patch',{'code':obj['code']})" in worker
    assert "terminal='COMPLETED_REPAIRED'" in worker


@pytest.mark.parametrize('value', [
    {'action':'PATCH','code':'x=1','reason':'a','verdict':'PASS'},
    {'action':'PATCH','code':None,'reason':'a'},
    {'action':'STOP','code':'x=1','reason':'a'},
    {'action':'CALL','code':'x=1','reason':'a'},
    {'action':'PATCH','code':12,'reason':'a'},
    {'action':'PATCH','code':'x'*65537,'reason':'a'},
])
def test_invalid_data_is_not_guessed_or_applied(value):
    with pytest.raises(ValueError): parse_response(envelope(value))


def test_truncation_tool_call_and_duplicate_fields_are_rejected():
    obj={'action':'PATCH','code':'x=1','reason':'PASS'}
    response=envelope(obj); response['done_reason']='length'
    with pytest.raises(ValueError): parse_response(response)
    response=envelope(obj); response['message']['tool_calls']=[{'function':{'name':'submit_patch'}}]
    with pytest.raises(ValueError): parse_response(response)
    response=envelope(obj);response['message']['content']='{"action":"PATCH","action":"STOP","code":null,"reason":"x"}'
    with pytest.raises(ValueError):parse_response(response)


def test_unknown_strategy_and_no_violation_never_launch_worker():
    with patch('credproof_safety.agent.check_project') as check:
        with pytest.raises(ValueError):request_repair('none',strategy='unknown')
        check.assert_not_called()
    config=ROOT/'examples/material_assistant/credproof.toml'
    with patch('credproof_safety.agent.check_project',return_value={'verdict':'UNKNOWN'}), \
         patch('credproof_safety.agent._host_repair') as host:
        assert request_repair(config,strategy='bounded_patch')['status']=='BLOCKED'
        host.assert_not_called()


def test_shared_executor_still_enforces_material_auth_and_verdict():
    # Source-level wiring assertion complements saved real controls and the
    # live task. This is NOT a mocked proof of dynamic candidate safety.
    from credproof_safety import agent
    text = Path(agent.__file__).read_text(encoding='utf8')
    assert "current = check_project(candidate_config, project_root=candidate)" in text
    assert "candidate_material_changed_outside_executor" in text
    assert "no_current_confirmed_violation" in text
    assert "candidate_size_or_type" in text
    assert "immutable_candidate_material_changed" in text
    worker=_bounded_model_script()
    assert "if feedback['verdict']=='PASS': terminal='COMPLETED_REPAIRED'" in worker
    assert "obj['reason']" not in worker  # model explanation has no verdict authority
