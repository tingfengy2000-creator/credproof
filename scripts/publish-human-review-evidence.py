"""Derive auditable public text; never change private source records or execute code."""
import argparse, hashlib, json, os, re
from pathlib import Path
import xml.etree.ElementTree as ET

ap=argparse.ArgumentParser();ap.add_argument('--installation',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
args=ap.parse_args();repo=Path(__file__).resolve().parents[1];public=args.output
public.mkdir(parents=True,exist_ok=True);sources=[]
prefixes=[(str(args.installation),'<INSTALL>'),(str(repo),'<REPOSITORY>'),('/home/tingfeng','<RUNTIME_HOME>'),(r'C:\Users\Administrator','<HOST_USER>'),(os.environ.get('COMPUTERNAME','UNSET'),'REDACTED_HOST')]
def redact(s):
    for prefix,replacement in prefixes:
        for value in [json.dumps(prefix,ensure_ascii=False)[1:-1],prefix,prefix.replace('\\','/')]:s=s.replace(value,replacement)
    return s
def derive(source,name):
    raw=source.read_bytes()
    if source.suffix in ['.jpg','.png','.whl']:body=raw
    else:
        value=redact(raw.decode('utf-8-sig')).replace('\r\n','\n')
        if source.suffix=='.json':json.loads(value)
        if re.search(r'CP_(?:LAB|EXEC)_[0-9a-fA-F]{6,}',value):raise ValueError('synthetic secret fragment '+name)
        body=value.encode('utf8')
    target=public/name;target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():raise ValueError('refusing existing derivative '+name)
    target.write_bytes(body)
    sources.append({'source':redact(str(source)),'path':name,'raw_sha256':hashlib.sha256(raw).hexdigest(),'raw_bytes':len(raw),'public_sha256':hashlib.sha256(body).hexdigest(),'public_bytes':len(body)})
store=args.installation/'data/runs/human-review'
control=json.loads((args.installation/'http-controls/http-controls.json').read_text(encoding='utf8'));formal=store/control['formal_id'];test=store/control['test_approval_id']
for name in ['meta.json','baseline/candidate.py','baseline/original.py','baseline/report.json','versions/v000/version.json','versions/v001/version.json','versions/v001/format-receipt.json']:
    derive(formal/name,'workflow/'+name)
for p in sorted((formal/'decisions').glob('*.json')):derive(p,'workflow/decisions/'+p.name)
for p in sorted((formal/'versions/v001/reports').glob('*.json')):derive(p,'workflow/reports/'+p.name)
for p in sorted((test/'decisions').glob('*.json')):derive(p,'approval-function-tests/decisions/'+p.name)
for p in sorted((test/'versions/v001/reports').glob('*.json')):derive(p,'approval-function-tests/reports/'+p.name)
derive(args.installation/'http-controls/http-controls.json','approval-function-tests/http-controls.json')
for name in ['dependency-copy.json','server-origin.json','child-origin-final/origin-receipt.json','build-final.txt']:
    derive(args.installation/name,'installation/'+name)
for name in ['protocol-final-pytest.txt','protocol-final-junit.xml']:
    derive(repo/'docs/reusable-tool-safety/acceptance/20261010-human-review/local'/name,'protocol/'+name)
# Keep private bundles unchanged. Public text is a disclosed derivative with a
# fresh byte manifest, then the existing Git-blob derivation is applied.
exports=sorted(formal.glob('exports/*/bundle/report.json'),key=lambda p:p.stat().st_mtime)
bundle=exports[-1].parent
manifest=json.loads((bundle/'manifest.json').read_text(encoding='utf8'))
for name in manifest['files']:derive(bundle/name,'source-bundle/'+name)
source_bundle=public/'source-bundle'
manifest['files']={p.relative_to(source_bundle).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(source_bundle.rglob('*')) if p.is_file()}
manifest['public_text_derivation']='Exact documented private-prefix redaction only; project code/config/tests/component bytes unmodified. Historical report preserved in private original.'
(source_bundle/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
(public/'derivation.json').write_text(json.dumps({'policy':'exact explicit prefix substitution, no broad path regex; no status/code edits','mappings':[(b,'private prefix '+str(i)) for i,(_,b) in enumerate(prefixes)],'sources':sources,'runtime_model_calls':0},ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
print(json.dumps({'files':len(sources),'formal':control['formal_id'],'model_calls':0}))
