"""PR8 disposable review server; installed program, unchanged handler logic, zero inference."""
import hashlib, importlib.metadata, json, os, shutil, sys
from pathlib import Path
import agent_pilot.web as web
import agent_pilot.presentation as presentation
import credproof_safety.human_review as human
import credproof_safety.project as project

HERE = Path(__file__).resolve().parent
SOURCE = Path('<review-source>')
DATA = HERE/'manual-data'
LOG = HERE/'manual-events.jsonl'
if not DATA.exists():
    DATA.mkdir()
    paths = ['agent_pilot/ui','agent_pilot/fixtures','agent_pilot/holdout-v1',presentation.BATCH,
             'examples/material_assistant','examples/material_assistant_fixed']
    for name in paths:
        shutil.copytree(SOURCE/name, DATA/name)
    shutil.copytree(SOURCE/'docs/reusable-tool-safety/acceptance/20261010-human-review/public-evidence/workspace/runs', DATA/'runs')
    # An explicitly selected existing history, never a generated reference answer.
    shutil.copytree(Path('<prior-test-root>/data/runs/history/linked-feedback'),DATA/'runs/history/linked-feedback')

mode = sys.argv[1] if len(sys.argv)>1 else 'recheck'
app=web.Application(root=DATA, histories=[DATA/'runs/history/linked-feedback/p01/C-agent'],
                    access_mode=mode, project_examples=True,
                    bench_results=SOURCE/'docs/bench/bench-results.json')
presentation.install_demonstrations(app)

def note(row):
    with LOG.open('a',encoding='utf8',newline='\n') as f:
        f.write(json.dumps(web.safe_public(row),ensure_ascii=False)+'\n')

class ObservedHandler(web.Handler):
    def do_POST(self):
        self._body=None
        super().do_POST()
    def body(self, limit=4096):
        body=super().body(limit)
        self._body=body
        return body
    def write_headers(self, code, content_type, size, extra=()):
        if self.command == 'POST' or self.path.endswith('/export'):
            note({'at':web.now(),'method':self.command,'path':self.path,'status':code,
                  'session_header_present':bool(self.headers.get('X-CredProof-Review-Session')),
                  'session_header_matches':self.headers.get('X-CredProof-Review-Session')==app.review_session,
                  'body':getattr(self,'_body',None), 'response_content_type':content_type})
        return super().write_headers(code, content_type, size, extra)
    def send_json(self, code, value):
        if self.command=='POST':
            note({'at':web.now(),'path':self.path,'response_status':code,'response':value})
        return super().send_json(code,value)

modules=[web,human,project,presentation]
receipt={'mode':mode,'model_calls':0,'program_source':('installed-wheel' if 'site-packages' in web.__file__ else 'source-launch-equivalent-to-start-recheck'),
         'interpreter':sys.executable,'isolated':sys.flags.isolated,
         'version':importlib.metadata.version('credproof-safety'),
         'modules':{m.__name__:{'file':m.__file__,'sha256':hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()} for m in modules},
         'data_workspace':str(DATA), 'source_head':'79e6b74627b4001ac071bd831d4133c1ccb10c8a'}
(HERE/('manual-origin-'+mode+('-installed' if 'site-packages' in web.__file__ else '-source')+'.json')).write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8')
with web.Server(('127.0.0.1',8768),app) as server:
    server.RequestHandlerClass=ObservedHandler
    print('DISPOSABLE PR8 '+mode+' http://127.0.0.1:8768 ; no model startup',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
