"""Transport protocol tests only; no model inference or candidate execution."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parents[2]/'scripts/bench'
spec = importlib.util.spec_from_file_location('bench_transport', HERE/'run_isolated.py')
transport = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)


def bridge(tmp_path):
    rpc, evidence = tmp_path/'rpc', tmp_path/'evidence'
    rpc.mkdir(); evidence.mkdir()
    return transport.Bridge(rpc, evidence, SimpleNamespace(poll=lambda: None))


def body(options=None):
    return json.dumps({'model': transport.MODELS[0], 'messages': [{'role': 'user', 'content': 'harmless transport test'}],
                       'stream': False, 'options': options or dict(transport.common.GEN_OPTIONS, seed=1)}).encode()


def test_exact_frozen_request_and_response_forwarded(tmp_path):
    b = bridge(tmp_path)
    raw = body()
    transport.write(b.rpc/'response-0001.json', {'status': 200, 'body': '{"done":true}', 'seconds': .1})
    assert b.forward('POST', '/api/chat', raw) == (200, b'{"done":true}')
    sent = json.loads((b.rpc/'request-0001.json').read_text())
    assert sent['body'].encode() == raw
    assert b.totals == {'generation': 1, 'judge': 0}


def test_unknown_model_tools_and_route_never_reach_rpc(tmp_path):
    b = bridge(tmp_path)
    data = json.loads(body())
    data['model'] = 'unapproved:latest'
    assert b.forward('POST', '/api/chat', json.dumps(data).encode())[0] == 400
    data = json.loads(body()); data['tools'] = []
    assert b.forward('POST', '/api/chat', json.dumps(data).encode())[0] == 400
    assert b.forward('POST', '/api/pull', b'{}')[0] == 403
    assert list(b.rpc.iterdir()) == []


def test_budget_exhaustion_does_not_forward_or_retry(tmp_path):
    b = bridge(tmp_path)
    b.inferences = b.maximum
    assert b.forward('POST', '/api/chat', body())[0] == 400
    assert list(b.rpc.iterdir()) == []
    assert b.inferences == b.maximum


def test_judge_frozen_options_and_usage_are_preserved(tmp_path):
    b = bridge(tmp_path); b.phase = 'judge'
    response = {'done': True, 'prompt_eval_count': 123, 'eval_count': 12}
    transport.write(b.rpc/'response-0001.json', {'status': 200, 'body': json.dumps(response), 'seconds': .1})
    status, raw = b.forward('POST', '/api/chat', body(dict(transport.common.JUDGE_OPTIONS)))
    assert status == 200 and json.loads(raw) == response
    assert b.totals == {'generation': 0, 'judge': 1}
