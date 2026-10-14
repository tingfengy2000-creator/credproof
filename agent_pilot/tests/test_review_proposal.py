"""Protocol substitutes only; none of these tests infer or execute candidates."""
import ast
import json
from unittest.mock import patch
import pytest
from agent_pilot.tests.test_human_review import review, expected
from credproof_safety.proposal import worker_script, payload_for, LIMITS
from credproof_safety.config import load_config


def candidate(code='def run(request):\n    return dict(request)\n'):
    return {'status':'CANDIDATE','code':code,'reason':'protocol substitute, not model inference',
            'model':{'name':'protocol-substitute','digest':'0'*64},'request_sha256':'1'*64,
            'response_sha256':'2'*64,'strategy':'bounded_patch','model_requests':1,'native_tool_calls':0,'verifications':0}


def test_new_ai_version_remains_unknown_pending_and_parent_unchanged(review):
    w,s=review;parent=(w.folder(s['id'])/'versions/v000/project/tool.py').read_bytes()
    with patch('credproof_safety.proposal.generate_proposal',return_value=candidate()) as generate,patch('credproof_safety.human_review.check_project') as check:
        r=w.propose(s['id'],expected(s))
    v=r['review'];assert v['version']['source']=='AI_CANDIDATE'
    assert v['version']['request_sha256']=='1'*64 and v['version']['response_sha256']=='2'*64
    assert v['technical_verdict']=='UNKNOWN' and v['decision']=='PENDING' and v['application_to_original']=='NOT_APPLIED'
    check.assert_not_called();generate.assert_called_once()
    assert (w.folder(s['id'])/'versions/v000/project/tool.py').read_bytes()==parent
    with pytest.raises(ValueError,match='approval_requires'):w.decide(s['id'],expected(v),'APPROVED','not verified')


@pytest.mark.parametrize('result',[{'status':'NO_CANDIDATE','reason':'MODEL_STOP'}, {'status':'NO_CANDIDATE','reason':'client_wall_timeout'}, candidate('def broken(:')])
def test_no_candidate_or_invalid_output_never_creates_version(review,result):
    w,s=review
    with patch('credproof_safety.proposal.generate_proposal',return_value=result):
        if result.get('code'): 
            with pytest.raises(ValueError):w.propose(s['id'],expected(s))
        else:assert w.propose(s['id'],expected(s))['status']=='NO_CANDIDATE'
    assert len(w.view(s['id'])['versions'])==1


def test_no_change_consumes_receipt_but_creates_no_version(review):
    w,s=review
    with patch('credproof_safety.proposal.generate_proposal',return_value=candidate(s['code'])):
        result=w.propose(s['id'],expected(s))
    assert result['reason']=='NO_CHANGE' and len(result['review']['versions'])==1
    assert len(list(w.folder(s['id']).glob('proposals/*/review-receipt.json')))==1


def test_stale_and_no_current_fail_are_rejected_before_generation(review):
    w,s=review
    with patch('credproof_safety.proposal.generate_proposal') as generate:
        stale=expected(s);stale['object_sha256']='bad'
        with pytest.raises(ValueError,match='stale'):w.propose(s['id'],stale)
        fresh=w.revise(s['id'],expected(s),'def run(request):\n    return dict(request)\n','protocol')
        with pytest.raises(ValueError,match='requires_current_FAIL'):w.propose(s['id'],expected(fresh))
        generate.assert_not_called()


def test_material_change_during_generation_cannot_create_version(review):
    w,s=review
    def changed(*args):
        (w.folder(s['id'])/'versions/v000/project/tests/test_business.py').write_text('changed')
        return candidate()
    with patch('credproof_safety.proposal.generate_proposal',side_effect=changed):
        with pytest.raises(ValueError,match='stale'):w.propose(s['id'],expected(s))
    assert len(w.view(s['id'])['versions'])==1


def test_work_package_and_worker_use_existing_bounded_protocol_without_tools(review):
    w,s=review;cfg=load_config(w.folder(s['id'])/'versions/v000/project/credproof.toml')
    payload=payload_for(cfg,s['report']);wire=json.dumps(payload)
    assert 'tools' not in payload and 'native tool calls only' not in wire
    assert s['code'] in payload['messages'][1]['content']
    assert 'NECESSARY TEST SOURCE' in wire and 'FAILURE FACTS' in wire
    assert payload['options']['num_ctx']==16384 and payload['options']['num_predict']==2048
    script=worker_script();ast.parse(script)
    assert 'max_calls=1' in script and 'client.run(' not in script
    assert LIMITS['verifications']==LIMITS['format_corrections']==0
