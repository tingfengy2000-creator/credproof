"""Protocol tests only; real isolated component execution is recorded separately."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from credproof_access.contract import build_contract
from credproof_safety.access_dependency import dependency_receipt, API
from credproof_safety import web_repair
from credproof_safety.agent import _bounded_initial_context, _model_work_feedback
from credproof_safety.config import load_config
from agent_pilot.bounded_patch import build_payload, OUTPUT_TOKENS
from agent_pilot.model_client import estimate_input_budget

ROOT = Path(__file__).resolve().parents[2]


def test_runtime_contract_and_environment_share_one_mapping():
    contract, env = build_contract({'allowed_dirs':['docs'], 'forbidden_dirs':['private'],
        'service_path_prefix':'/v1', 'credential_env':'CUSTOM_SECRET'}, 23145, 23146)
    assert contract['public_environment'] == env
    assert env['CREDPROOF_ALLOWED_ROOT'] == '/tmp/lab/docs'
    assert env['CREDPROOF_ALLOWED_URL'] == 'http://127.0.0.1:23145/v1'
    assert contract['policy']['services'][0]['port'] == 23145
    assert contract['credential_environment']['name'] == 'CUSTOM_SECRET'
    assert 'CUSTOM_SECRET' not in env and 'CREDPROOF_ALLOWED_DIRS' not in env


def test_missing_component_blocks_without_unsafe_fallback(tmp_path):
    from credproof_safety.runner import run_sandbox
    with patch('credproof_safety.runner.available', return_value=(True, 'protocol stub')):
        result = run_sandbox(tmp_path, tmp_path, [], 'tool','run',{},'synthetic',
                             access_dependency=tmp_path/'missing')
    assert result == {'status':'BLOCKED', 'reason':'access_dependency_missing'}


def test_component_work_package_contains_actual_contract_and_no_reference():
    report = json.loads((ROOT/'docs/reusable-tool-safety/acceptance/20261009-component-assisted/public-evidence/component-controls-final/unchanged-original-report.json').read_text(encoding='utf8'))
    from credproof_safety.project import _redact_execution
    report = _redact_execution(report, 'unused-no-full-value')
    config = load_config(ROOT/'examples/material_assistant/credproof.toml')
    context = _bounded_initial_context(report, config)
    code = (config.project_root/'tool.py').read_text(encoding='utf8')
    tests = {'tests/test_business.py':(config.project_root/'tests/test_business.py').read_text(encoding='utf8')}
    feedback = _model_work_feedback(report, config)
    payload = build_payload(context,code,tests,feedback,{'remaining_generations':3})
    wire = json.dumps(payload)
    assert code in payload['messages'][1]['content']
    assert context['runtime_contract'] == report['execution']['runtime_contract']
    assert context['access_component']['api'] == API
    assert context['profile']=='component_assisted' and 'tools' not in payload
    assert 'CREDPROOF_ALLOWED_ROOT' in wire and 'material_assistant_fixed' not in wire
    assert 'CP_LAB_' not in wire
    budget = estimate_input_budget(payload, OUTPUT_TOKENS)
    assert budget['within_context_budget'] and budget['within_wire_limit']


def test_web_uses_bounded_component_strategy_and_preserves_block(tmp_path):
    config = ROOT/'examples/material_assistant/credproof.toml'
    with patch.object(web_repair, 'request_repair',return_value={
            'status':'BLOCKED','reason':'protocol_standin','paid_api_used':False}) as repair:
        assert web_repair.main(['--project-id','assistant-original','--case-id','p01',
            '--config',str(config),'--output',str(tmp_path/'out')]) == 0
    assert repair.call_args.kwargs['strategy'] == 'bounded_patch'
    record = json.loads((tmp_path/'out/comparison/p01/C-agent/result.json').read_text(encoding='utf8'))
    assert record['strategy']=='bounded_patch' and record['profile']=='component_assisted'
    assert record['final_validation']['verdict']=='UNKNOWN'
    assert record['execution_kind']=='blocked-before-model-inference'


def test_bundle_binds_and_exports_dependency_without_model_success(tmp_path):
    from credproof_safety.tests.test_project_bundle import ProjectBundleProtocolTests
    from credproof_safety.project_bundle import export_project_bundle, recheck_project_bundle
    method = ProjectBundleProtocolTests().make_material(tmp_path)
    row = json.loads((method/'result.json').read_text())
    row['final_validation']['execution']={'access_component':dependency_receipt(), 'runtime_contract':{'protocol_stub':True}}
    (method/'result.json').write_text(json.dumps(row))
    bundle = tmp_path/'bundle'
    export_project_bundle(method, bundle)
    assert (bundle/'dependencies/credproof_access/__init__.py').is_file()
    with patch('credproof_safety.project_bundle.check_project',return_value={'verdict':'FAIL'}) as checker:
        result = recheck_project_bundle(bundle, tmp_path/'recheck.json')
        assert checker.call_args.kwargs['access_dependency'] == bundle/'dependencies/credproof_access'
    assert result['validation']['verdict']=='FAIL'
    (bundle/'dependencies/credproof_access/__init__.py').write_text('changed')
    with patch('credproof_safety.project_bundle.check_project') as checker:
        result = recheck_project_bundle(bundle,tmp_path/'changed.json')
        checker.assert_not_called()
    assert result['validation']['verdict']=='UNKNOWN'


def test_preflight_program_identity_is_not_read_from_data_workspace():
    from agent_pilot import preflight
    import inspect
    source = inspect.getsource(preflight.observe)
    assert "Path(__file__).resolve().with_name('sandbox_runner.py')" in source
    assert "root / 'agent_pilot/sandbox_runner.py'" not in source
