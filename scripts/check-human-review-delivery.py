"""Installed HTTP integration controls; no inference, all approvals TEST ONLY.

Run after the browser has created a PASS/PENDING developer revision. Dedicated
clones exercise drift, leaving the formal pending object and old history intact.
"""
import argparse, hashlib, importlib.metadata, json, shutil, sys, uuid
from pathlib import Path
import urllib.request, urllib.error
import credproof_safety.human_review as reviews

ap=argparse.ArgumentParser()
ap.add_argument('--workspace',type=Path,required=True)
ap.add_argument('--output',type=Path,required=True)
ap.add_argument('--url',default='http://127.0.0.1:8795')
args=ap.parse_args()
args.output.mkdir(parents=True,exist_ok=False)
events=[]
def call(path,data=None):
    headers={'Content-Type':'application/json','X-CredProof-Review-Session':session} if data is not None else {}
    req=urllib.request.Request(args.url+path,data=json.dumps(data,ensure_ascii=False).encode() if data is not None else None,headers=headers)
    try:
        with urllib.request.urlopen(req,timeout=90) as r:code,body=r.status,r.read()
    except urllib.error.HTTPError as e:code,body=e.code,e.read()
    value=json.loads(body) if not body.startswith(b'PK') else {'zip_bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
    if path!='/api/agent/bootstrap':events.append({'path':path,'request':data,'http':code,'response':value})
    return code,value
session=''
_,bootstrap=call('/api/agent/bootstrap');session=bootstrap['review_session']
formal=next(reviews.ReviewWorkspace(args.workspace).view(x['id']) for x in bootstrap['reviews'] if reviews.ReviewWorkspace(args.workspace).view(x['id'])['version']['id']=='v001')
assert formal['technical_verdict']=='PASS' and formal['decision']=='PENDING'
def expected(s):return dict(version_id=s['version']['id'],object_sha256=s['object_sha256'],report_sha256=s['report_sha256'],decision_count=len(s['decisions']))
store=args.workspace/'runs/human-review'
def clone(state,label):
    key=uuid.uuid4().hex;folder=store/key;shutil.copytree(store/state['id'],folder)
    meta=json.loads((folder/'meta.json').read_text(encoding='utf8'));meta.update(id=key,label=label)
    (folder/'meta.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return key
key=clone(formal,'审批功能测试 · 非本人审阅')
_,test=call('/api/review/'+key)
stale=expected(test)
code,test=call('/api/review/'+key+'/decide',dict(expected=stale,decision='APPROVED',reason='approval-function-test; no real user signature',test_operation=True));assert code==200
assert test['decision']=='APPROVED' and test['decision_is_test']
code,_=call('/api/review/'+key+'/decide',dict(expected=stale,decision='APPROVED',reason='stale test',test_operation=True));assert code==409
bad=expected(test);bad['version_id']='v999'
code,_=call('/api/review/'+key+'/decide',dict(expected=bad,decision='APPROVED',reason='wrong candidate test',test_operation=True));assert code==409
code,_=call('/api/review/'+key+'/export',dict(expected=expected(test),adopted=True));assert code==200
for mode in ['code','rules','component','missing-test']:
    d=clone(test,'material-drift-function-test-'+mode);folder=store/d
    p=folder/'versions/v001/project'
    if mode=='code':target=p/'tool.py';target.write_bytes(target.read_bytes()+b'\n# drift\n')
    elif mode=='rules':target=p/'credproof.toml';target.write_bytes(target.read_bytes()+b'\n# drift\n')
    elif mode=='component':target=folder/'baseline/dependencies/credproof_access/contract.py';target.write_bytes(target.read_bytes()+b'\n# drift\n')
    else:(p/'tests/test_business.py').rename(p/'tests/removed-business.txt')
    _,changed=call('/api/review/'+d)
    assert changed['technical_verdict']=='UNKNOWN' and changed['decision']!='APPROVED'
    code,_=call('/api/review/'+d+'/decide',dict(expected=expected(changed),decision='APPROVED',reason='drift must block',test_operation=True));assert code==409
    code,_=call('/api/review/'+d+'/export',dict(expected=expected(changed),adopted=True));assert code==409
code,ai=call('/api/review/open',{'run_id':bootstrap['history'][0]['id']});assert code==200 and ai['technical_verdict']=='FAIL'
code,_=call('/api/review/'+ai['id']+'/decide',dict(expected=expected(ai),decision='APPROVED',reason='FAIL cannot approve',test_operation=True));assert code==409
code,_=call('/api/review/'+ai['id']+'/export',dict(expected=expected(ai),adopted=False));assert code==200
# Formal review has no approval, even after every test decision above.
_,current=call('/api/review/'+formal['id']);assert current['decision']=='PENDING'
receipt={'kind':'REAL_INSTALLED_HTTP_REVIEW_CONTROLS','runtime_model_calls':0,'formal_id':formal['id'],'test_approval_id':key,'formal_state':'PASS/PENDING','test_identity':'approval-function-test','python':sys.version,'version':importlib.metadata.version('credproof-safety'),'module':reviews.__file__,'events':events,'pass':True}
(args.output/'http-controls.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({k:receipt[k] for k in ['formal_id','test_approval_id','formal_state','pass']}))
