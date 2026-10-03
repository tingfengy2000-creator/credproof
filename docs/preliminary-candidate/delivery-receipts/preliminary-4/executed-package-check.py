from pathlib import Path
import zipfile,json,subprocess,sys,time,urllib.request,urllib.error,hashlib,os,importlib.util
root=Path('E:/cp-p4-final-995ecefd0b4b');root.mkdir(exist_ok=False)
archive=Path('E:/CredProof-local-runtime/review-packages/preliminary-candidate-4/candidate/credproof-0.2.0-preliminary.4-20261003-995ecefd0b4b.zip')
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='b03fa8d4f341c4cf21f12deac400387cf661e6aa39304dde55f82690608e40b0'
with zipfile.ZipFile(archive) as z:z.extractall(root)
out=Path('E:/CredProof-local-runtime/review-packages/preliminary-candidate-4/validation');out.mkdir(exist_ok=False)
records=[]
def command(name,argv,cwd=root):
 started=time.time();r=subprocess.run(argv,cwd=cwd,capture_output=True,timeout=180)
 (out/(name+'-stdout.txt')).write_bytes(r.stdout);(out/(name+'-stderr.txt')).write_bytes(r.stderr)
 records.append({'name':name,'argv':argv,'cwd':str(cwd),'exit_code':r.returncode,'elapsed_s':time.time()-started})
 (out/'commands.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),'utf-8')
 assert r.returncode==0,name
 return r
command('manifest',[sys.executable,'-B','scripts/verify-review.py','--root',str(root)])
command('new-boundary-tests',[sys.executable,'-B','-m','unittest','agent_pilot.tests.test_delivery_modes','agent_pilot.tests.test_external_twine','-v'])
command('preflight',[sys.executable,'-B','-m','agent_pilot.preflight'])
external=command('external-recheck',[sys.executable,'-B','-m','agent_pilot.external_twine','recheck','.'],root/'docs/external-scenario/twine-material-20261003')
d=json.loads(external.stdout);assert d['old_report_applicable'] and d['historical_material_integrity']=='INTACT' and d['new_check']['verdict']=='PASS'
# Invalid config deliberately proves view mode never requires runtime discovery.
env=dict(os.environ,CREDPROOF_CONFIG=str(out/'intentionally-absent-runtime.json'),PYTHONDONTWRITEBYTECODE='1')
log=(out/'view-server-stdout.txt').open('wb');err=(out/'view-server-stderr.txt').open('wb')
argv=[sys.executable,'-B','-m','agent_pilot.launch','--demo','--mode','view','--port','8787']
proc=subprocess.Popen(argv,cwd=root,env=env,stdout=log,stderr=err)
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}));base='http://127.0.0.1:8787'
def req(path,body=None):
 data=json.dumps(body).encode() if body is not None else None
 q=urllib.request.Request(base+path,data=data,headers={'Content-Type':'application/json'})
 try:
  with opener.open(q,timeout=25) as r:return r.status,r.read()
 except urllib.error.HTTPError as e:return e.code,e.read()
try:
 for _ in range(20):
  try:status,raw=req('/api/agent/bootstrap');break
  except OSError:time.sleep(.25)
 assert status==200
 data=json.loads(raw);assert data['access_mode']=='view' and not data['runtime']['ready'] and len(data['demonstrations'])==3
 (out/'view-bootstrap.json').write_bytes(raw)
 code,_=req('/api/agent/runs',{'case_id':'h01'});assert code==409
 history=data['demonstrations'][2]['run_id'];route='/api/agent/runs/'+history
 code,raw=req(route);assert code==200 and json.loads(raw)['mode']=='REPLAY'
 (out/'h07-view.json').write_bytes(raw)
 code,_=req(route+'/recheck',{});assert code==409
 code,raw=req(route+'/export');assert code==200 and raw[:2]==b'PK'
 (out/'h07-export.zip').write_bytes(raw)
 material=out/'h07-exported';zipfile.ZipFile(out/'h07-export.zip').extractall(material)
 command('exported-h07-recheck',[sys.executable,'-B','-m','agent_pilot.bundle','recheck','--bundle','.','--output',str(out/'h07-fresh-recheck.json')],material)
 fresh=json.loads((out/'h07-fresh-recheck.json').read_text('utf-8'));assert fresh['validation']['verdict']=='PASS'
 (out/'mode-checks.json').write_text(json.dumps({'view_start':'PASS','runtime_configuration_intentionally_missing':True,'model_packages_installed':bool(importlib.util.find_spec('qwen_agent')),'historical_entries':3,'live_request':409,'recheck_request':409,'export_request':200,'direct_export_recheck':'PASS','scope':'same Windows host, new Python venv and archive directory; existing WSL isolation reused'},indent=2),'utf-8')
finally:
 proc.terminate();proc.wait(timeout=10);log.close();err.close()
 records.append({'name':'view-server','argv':argv,'startup':'PASS','stop':'owned child terminated by check harness','exit_code':proc.returncode})
 (out/'commands.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),'utf-8')
print(json.dumps({'status':'PASS','archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'root':str(root),'validation':str(out),'commands':len(records)}))
