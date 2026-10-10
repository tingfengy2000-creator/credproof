"""No inference/candidate execution: reception and one-shot protocol checks."""
import json
from pathlib import Path
from unittest.mock import patch
import pytest

from agent_pilot.bounded_patch import parse_response, BoundedPatchClient
from agent_pilot.output_format import receive_python_source
from credproof_safety.agent import _bounded_model_script

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT/'docs/reusable-tool-safety/acceptance/20261010-format-normalized/public-evidence'


def response(code):
    return {'done': True, 'done_reason': 'stop', 'message': {'role': 'assistant',
            'content': json.dumps({'action': 'PATCH', 'code': code, 'reason': 'protocol input'})}}


def test_actual_historical_response_uses_unified_parser_without_semantic_repair():
    actual = json.loads((OLD/'original-model-response.json').read_text())
    result = parse_response(actual)
    assert result['code'].encode() == (OLD/'normalized-candidate.py').read_bytes()
    assert result['_source_format']['deletions'][0]['text'] == '```python\n'
    assert 'except urllib.error.HTTPError' in result['code']
    assert 'raise ValueError(f' in result['code']  # The real errors are not fixed by format reception.
    assert result['_source_format']['syntax']['executed'] is False


@pytest.mark.parametrize('code', ['```python\nx=1', 'text\n```py\nx=1\n```',
                                  '```py\nx=1\n```\n```py\ny=2\n```', 'def f(:'])
def test_invalid_format_or_syntax_rejected_before_candidate_write(code, tmp_path):
    before = list(tmp_path.iterdir())
    with pytest.raises(ValueError): parse_response(response(code))
    assert list(tmp_path.iterdir()) == before


def test_plain_source_is_unchanged_and_stop_has_no_source():
    source = 'value = "```"\n'
    assert receive_python_source(source)[0] == source
    actual = response(None)
    actual['message']['content'] = json.dumps({'action':'STOP', 'code':None, 'reason':'cannot continue'})
    assert parse_response(actual) == {'action':'STOP', 'code':None, 'reason':'cannot continue'}


def test_one_request_cap_rejects_second_without_http(tmp_path):
    client = BoundedPatchClient(tmp_path/'trace', max_calls=1)
    client.calls = 1
    with patch('urllib.request.build_opener') as network:
        with pytest.raises(RuntimeError, match='budget_exhausted'): client.request({})
        network.assert_not_called()


def test_worker_cap_and_host_reception_are_real_wiring():
    worker = _bounded_model_script()
    compile(worker, '<worker-protocol>', 'exec')
    assert 'max_requests=1 if revision else 4' in worker
    assert 'max_corrections=0 if revision else 1' in worker
    assert 'max_generations=1 if revision else 3' in worker
    host = (ROOT/'credproof_safety/agent.py').read_text()
    assert 'code, format_receipt = receive_python_source(code)' in host
    assert 'max_candidates = max_verifications = 1' in host
