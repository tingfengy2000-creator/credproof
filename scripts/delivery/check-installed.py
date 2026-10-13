"""Real installed-package HTTP export; no model, WSL or candidate execution."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import threading
from urllib.request import Request, urlopen
import zipfile
from io import BytesIO
import sys
from importlib.metadata import version

from agent_pilot import bundle, presentation, web


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    assert 'site-packages' in str(web.__file__), 'must execute installed wheel with -I'
    app=web.Application(root=a.workspace,access_mode='view')
    presentation.install_demonstrations(app)
    presentation.install_review_demonstration(app)
    with web.Server(('127.0.0.1',0),app) as server:
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(server.server_address[1])
        try:
            bootstrap=json.load(urlopen(base+'/api/agent/bootstrap'))
            review=json.load(urlopen(base+'/api/review/'+bootstrap['reviews'][0]['id']))
            assert (review['technical_verdict'],review['decision'],review['application_to_original'])==('PASS','PENDING','NOT_APPLIED')
            run=next(r for r in app.runs.values() if r.case_id=='h03')
            request=Request(base+'/api/agent/runs/'+run.id+'/export')
            with urlopen(request) as response:
                archive=response.read();status=response.status
            with zipfile.ZipFile(BytesIO(archive)) as z:
                manifest=json.loads(z.read('manifest.json'))
                assert all(hashlib.sha256(z.read(name)).hexdigest()==digest for name,digest in manifest['hashes'].items())
                assert json.loads(z.read('config/runtime.example.json'))['wsl_user']==''
            result={'kind':'CLEAN_WHEEL_REAL_HTTP_NO_EXECUTION','version':version('credproof-safety'),
                'python':sys.version.split()[0],'web_origin':'site-packages/agent_pilot/web.py',
                'bundle_origin':'site-packages/agent_pilot/bundle.py','reviews':len(bootstrap['reviews']),
                'review_state':[review['technical_verdict'],review['decision'],review['application_to_original']],
                'h03_export_http':status,'archive_bytes':len(archive),'archive_sha256':hashlib.sha256(archive).hexdigest(),
                'manifest_files':len(manifest['hashes']),'manifest_all_match':True,
                'resource_present':bundle.runtime_example_path().is_file(),
                'new_model_calls':0,'candidate_execution':0,'wsl_probe':0,'exit_code':0}
            a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
            print(json.dumps(result,ensure_ascii=False))
        finally:
            server.shutdown();thread.join();presentation.close_review_demonstration(app)


if __name__=='__main__':main()
