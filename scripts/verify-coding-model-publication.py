"""Anonymous exact-Git evidence retrieval. No model, project execution or credentials."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import subprocess
import urllib.request

parser = argparse.ArgumentParser()
parser.add_argument('--commit', required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--proxy', default='')
args = parser.parse_args()
if not re.fullmatch('[0-9a-f]{40}', args.commit):
    raise ValueError('full fixed commit required')
args.output.mkdir(parents=True, exist_ok=False)
root = Path(__file__).resolve().parents[1]
prefix = 'docs/reusable-tool-safety/acceptance/20261009-coding-model-comparison/public-evidence'
base = 'https://raw.githubusercontent.com/tingfengy2000-creator/credproof/'+args.commit+'/'

def fetch(path, expected=None):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({'https':args.proxy} if args.proxy else {}))
    with opener.open(urllib.request.Request(base+path,headers={'User-Agent':'CredProof-anonymous-byte-review'}), timeout=45) as response:
        body, status = response.read(), response.status
    blob = subprocess.check_output(['git','-c','safe.directory='+str(root),'-C',str(root),'show',args.commit+':'+path])
    digest = hashlib.sha256(body).hexdigest()
    if body != blob or body.startswith(b'version https://git-lfs.github.com/spec/'):
        raise ValueError('Raw content not exact fixed Git bytes: '+path)
    if expected and (digest != expected['sha256'] or len(body) != expected['bytes']):
        raise ValueError('published manifest mismatch: '+path)
    if not body and not (expected and expected['bytes']==0):
        raise ValueError('unexpected empty body: '+path)
    if path.endswith('.json'):
        json.loads(body)
    target=args.output/path
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(body)
    return {'path':path,'url':base+path,'status':status,'bytes':len(body),'sha256':digest,
            'matches_Git_blob':True,'matches_manifest':expected is not None,
            'empty_capture_expected':not bool(body)}

manifest_path=prefix+'/published-manifest.json'
rows=[fetch(manifest_path)]
manifest=json.loads((args.output/manifest_path).read_text('utf8'))
items=[(prefix+'/'+p,d) for p,d in manifest['files'].items()]
extras=['README.md','docs/reusable-tool-safety/README.md','docs/reusable-tool-safety/requirements-acceptance.json',
        'agent_pilot/model_config.py','agent_pilot/bounded_patch.py','agent_pilot/web.py',
        'credproof_safety/agent.py','credproof_safety/web_repair.py','scripts/preflight-coding-model.py',
        'scripts/run-component-page-task.py','agent_pilot/tests/test_model_configuration.py']
items += [(p,None) for p in extras]
with ThreadPoolExecutor(max_workers=4) as pool:
    rows+=list(pool.map(lambda x:fetch(*x),items))
receipt={'kind':'ANONYMOUS_EXACT_FIXED_GIT_EVIDENCE_RETRIEVAL','commit':args.commit,'files':rows,
         'authorization_sent':False,'cookies_sent':False,'TLS_verification_enabled':True,
         'model_calls':0,'candidate_execution':False,'pass':True,
         'expected_empty_files':'only manifest-declared zero-byte captured stderr is allowed'}
(args.output/'retrieval-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n','utf8',newline='\n')
print(json.dumps({'commit':args.commit,'files':len(rows),'pass':True}))
