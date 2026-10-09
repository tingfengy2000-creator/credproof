"""Configuration/quotas only: no inference or candidate execution."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest
from agent_pilot.model_config import selected_profile, verify_profile, claim_comparison, LIMITS
from credproof_safety.agent import _MODEL_BOUNDARY_BOOTSTRAP, _bounded_model_script


def test_unknown_explicit_model_never_falls_back(monkeypatch):
    monkeypatch.setenv('CREDPROOF_MODEL_PROFILE','latest')
    with pytest.raises(ValueError,match='no_fallback'): selected_profile()


def test_configuration_reaches_client_boundary_and_own_manifest(monkeypatch):
    monkeypatch.setenv('CREDPROOF_MODEL_PROFILE','qwen25')
    profile=selected_profile()
    code='from agent_pilot.bounded_patch import build_payload; from agent_pilot.model_client import MODEL; import json; print(json.dumps([MODEL, build_payload({}, "code", {}, {}, {})]))'
    result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,check=True)
    model,payload=json.loads(result.stdout)
    assert model==payload['model']==profile['name']
    assert 'tools' not in payload and 'template' not in payload
    assert payload['options']=={'num_ctx':16384,'num_predict':2048,'temperature':0,'seed':0}
    assert 'verify_profile(profile, runtime)' in _MODEL_BOUNDARY_BOOTSTRAP
    assert "profile['profile']" in _MODEL_BOUNDARY_BOOTSTRAP
    assert '/api/show' in _bounded_model_script()


def test_manifest_mismatch_blocks_without_substitution(tmp_path,monkeypatch):
    monkeypatch.setenv('CREDPROOF_MODEL_PROFILE','qwen25')
    profile=selected_profile(); manifest=tmp_path/profile['manifest'];manifest.parent.mkdir(parents=True);manifest.write_bytes(b'wrong')
    with pytest.raises(ValueError,match='pinned_model'): verify_profile(profile,tmp_path)


def test_durable_claim_prevents_new_directory_restart(tmp_path,monkeypatch):
    monkeypatch.setenv('CREDPROOF_MODEL_PROFILE','qwen25')
    ledger=tmp_path/'round.json';ledger.write_text(json.dumps({'round':'protocol-only','task':'assistant-original/p01','limits':LIMITS,'model':selected_profile()}))
    monkeypatch.setenv('CREDPROOF_MODEL_COMPARISON_LEDGER',str(ledger))
    assert claim_comparison('preflight').is_file()
    with pytest.raises(FileExistsError):claim_comparison('preflight')
    assert claim_comparison('formal').is_file()
    with pytest.raises(FileExistsError):claim_comparison('formal')


def test_old_instructions_api_and_schema_unchanged():
    import agent_pilot.bounded_patch as bp
    previous=subprocess.check_output(['git','-c','safe.directory='+str(Path(__file__).resolve().parents[2]),'show','7011959e795f3bde442d3f4899ea5097ab42528a:agent_pilot/bounded_patch.py'])
    import ast
    values={}
    for node in ast.parse(previous.decode()).body:
        if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name) and node.targets[0].id in ('SYSTEM','FORMAT'):
            values[node.targets[0].id]=ast.literal_eval(node.value)
    assert bp.SYSTEM==values['SYSTEM'] and bp.FORMAT==values['FORMAT']
