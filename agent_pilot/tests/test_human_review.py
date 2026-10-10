"""Protocol/state tests. Mock reports are NOT safety or model experiments."""
import json
from pathlib import Path
from unittest.mock import patch
import pytest
from credproof_safety.human_review import ReviewWorkspace
from credproof_safety.project import _digest_tree
from credproof_safety.config import template, load_config
from credproof_safety.access_dependency import dependency_receipt

def expected(s):
    return dict(version_id=s['version']['id'],object_sha256=s['object_sha256'],report_sha256=s['report_sha256'],decision_count=len(s['decisions']))

@pytest.fixture
def review(tmp_path):
    project=tmp_path/'artifact/candidate';project.mkdir(parents=True)
    (project/'tool.py').write_text('def run(request):\n    return request\n',encoding='utf8')
    (project/'tests').mkdir();(project/'tests/test_business.py').write_text('def test_ok():\n    assert True\n',encoding='utf8')
    cfg=template(project).replace('tests/test_tool.py','tests/test_business.py')
    (project/'credproof.toml').write_text(cfg,encoding='utf8')
    tests=load_config(project/'credproof.toml').tests
    for name in tests:
        p=project/name
        if not p.exists():p.parent.mkdir(parents=True,exist_ok=True);p.write_text('def test_ok():\n    assert True\n')
    report={'verdict':'FAIL','project_tree_sha256':_digest_tree(project),'config':load_config(project/'credproof.toml').to_public_dict(),'execution':{'access_component':dependency_receipt(),'runtime_contract':{}},'checks':{'test':False}}
    method=tmp_path/'method';method.mkdir()
    for name in ['original.py','final-candidate.py']:(method/name).write_bytes((project/'tool.py').read_bytes())
    (method/'result.json').write_text(json.dumps({'schema':'credproof.web-live-record/v1','project_id':'protocol','artifact_dir':str(project.parent),'final_validation':report}))
    w=ReviewWorkspace(tmp_path/'data');s=w.open_method(method,'protocol-history')
    return w,s

def test_fail_cannot_be_approved_but_diagnostic_exports(review):
    w,s=review
    assert s['technical_verdict']=='FAIL' and s['decision']=='PENDING'
    with pytest.raises(ValueError,match='approval_requires'):w.decide(s['id'],expected(s),'APPROVED','test',test_operation=True)
    assert w.export(s['id'],expected(s)).is_file()
    with pytest.raises(ValueError,match='adopted_export'):w.export(s['id'],expected(s),adopted=True)

def test_revision_is_new_unverified_object_and_persistent(review):
    w,s=review
    r=w.revise(s['id'],expected(s),'def run(request):\n    return dict(request)\n','developer protocol edit')
    assert r['version']['parent']=='v000' and r['technical_verdict']=='UNKNOWN' and r['decision']=='PENDING'
    assert ReviewWorkspace(w.root.parents[1]).view(s['id'])['version']==r['version']
    with pytest.raises(ValueError,match='stale'):w.decide(s['id'],expected(s),'REJECTED','old')

def test_pass_pending_approval_and_recheck_invalidation(review):
    w,s=review
    def mock_check(cfg,output,**kw):
        value={**s['report'],'verdict':'PASS','checked_at':str(output),'checks':{'test':True}}
        output.write_text(json.dumps(value));return value
    with patch('credproof_safety.human_review.check_project',side_effect=mock_check):
        p=w.check(s['id'],expected(s));assert p['decision']=='PENDING' and p['technical_verdict']=='PASS'
        a=w.decide(s['id'],expected(p),'APPROVED','approval function test',test_operation=True)
        assert a['decision']=='APPROVED' and a['decision_is_test']
        assert w.export(s['id'],expected(a),adopted=True).is_file()
        r=w.check(s['id'],expected(a));assert r['decision']=='PENDING' and len(r['decisions'])==1

@pytest.mark.parametrize('name',['tool.py','credproof.toml','tests/test_business.py'])
def test_drift_invalidates_and_backend_refuses(review,name):
    w,s=review;p=w.folder(s['id'])/'versions/v000/project'/name
    p.write_text(p.read_text()+'\n# changed\n')
    r=w.view(s['id']);assert not r['report_applicable'] and r['technical_verdict']=='UNKNOWN'
    with pytest.raises(ValueError,match='stale'):w.decide(s['id'],expected(r),'APPROVED','cannot approve')

def test_missing_component_and_test_never_green(review):
    w,s=review;(w.folder(s['id'])/'baseline/dependencies/credproof_access/contract.py').unlink()
    r=w.view(s['id']);assert r['technical_verdict']=='UNKNOWN' and r['material_reasons']

def test_invalid_syntax_and_no_change_create_no_new_version(review):
    w,s=review
    for code in ['def broken(:',s['code']]:
        with pytest.raises(ValueError):w.revise(s['id'],expected(s),code,'protocol')
    assert len(w.view(s['id'])['versions'])==1
