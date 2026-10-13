"""Operator-only model-free installed-wheel check of the 16 existing anchors.

Run with an installed interpreter and -I, outside the source checkout.
Source directories are data; check_project executes their code only in bwrap.
Raw receipts may contain operator paths. Publish only reviewed derived copies.
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--runtime',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--source-commit',required=True,help='Full SHA verified by the source host Git; Windows worktree .git paths are not Linux Git paths')
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    if not re.fullmatch('[0-9a-f]{40}',a.source_commit):raise ValueError('Full source commit required')
    os.environ['CREDPROOF_CONFIG']=str(a.runtime/'runtime.json')
    import credproof_safety.cli as cli
    import credproof_safety.doctor as doctor_module
    import credproof_safety.runtime_setup as setup_module
    import credproof_safety.runner as runner
    import credproof_safety.project as project
    modules={x.__name__:{'path':x.__file__,'sha256':sha(x.__file__)}
             for x in (cli,doctor_module,setup_module,runner,project)}
    if not all('site-packages' in x['path'] for x in modules.values()):
        raise RuntimeError('Installed modules required; source checkout must not shadow wheel')
    for name,identity in modules.items():
        if identity['sha256']!=sha(a.source/Path(*name.split('.')).with_suffix('.py')):
            raise RuntimeError('Installed module differs from declared source tree: '+name)
    save(a.output/'installation.json',{'python':platform.python_version(),
        'executable':sys.executable,'cwd':str(Path.cwd()),'modules':modules,
        'version':importlib.metadata.version('credproof-safety'),
        'source_commit':a.source_commit,
        'model_calls':0})
    before={n:sha(a.runtime/n) for n in ('runtime-receipt.json','rootfs-manifest.json',
        'isolation/preparation.json','isolation/probe-receipt.json')}
    root,status=setup_module.setup(a.runtime)
    after={n:sha(a.runtime/n) for n in before}
    save(a.output/'reuse.json',{'preparation':status,'before':before,'after':after,'unchanged':before==after})
    doctor=doctor_module.doctor(a.runtime);save(a.output/'doctor.json',doctor)
    if not doctor['ready'] or before!=after:
        raise RuntimeError('Readiness/reuse failed; no projects executed')
    mismatch=a.output/'mismatched-runtime';mismatch.mkdir();(mismatch/'preserve.txt').write_bytes(b'preserve')
    try:
        setup_module.setup(mismatch)
    except (ValueError,KeyError,OSError) as exc:
        save(a.output/'mismatch.json',{'rejected':True,'error_type':type(exc).__name__,
            'sentinel_preserved':(mismatch/'preserve.txt').read_bytes()==b'preserve'})
    else:
        raise RuntimeError('Invalid runtime accepted')
    bench=json.loads((a.source/'docs/bench/bench-results.json').read_text('utf8'))
    anchors=[x for x in bench['patches'] if x['origin']['kind'] in ('vulnerable','reference')]
    if len(anchors)!=16:raise RuntimeError('Expected frozen 16-anchor set')
    rows=[]
    for anchor in anchors:
        target=anchor['target'];kind=anchor['origin']['kind'];name=target+'__'+kind
        data=a.source/'examples/bench'/target
        meta=json.loads((data/'meta.json').read_text('utf8'))
        work=a.output/name;work.mkdir();copy=work/'project'
        shutil.copytree(data/'project',copy,ignore=shutil.ignore_patterns('.credproof','__pycache__','*.pyc'))
        if kind=='reference':shutil.copyfile(data/meta['reference_fix'],copy/meta['mutable_file'])
        command=[sys.executable,'-I','-m','credproof_safety','check','--config',str(copy/'credproof.toml'),
                 '--output',str(work/'report.json')]
        started=time.monotonic();r=subprocess.run(command,capture_output=True,text=True,timeout=90)
        (work/'stdout.txt').write_text(r.stdout,encoding='utf8');(work/'stderr.txt').write_text(r.stderr,encoding='utf8')
        report=json.loads((work/'report.json').read_text('utf8')) if (work/'report.json').exists() else {}
        row={'id':name,'source':'frozen_vulnerable' if kind=='vulnerable' else 'human_reference_control',
             'command':command,'exit_code':r.returncode,'duration_seconds':round(time.monotonic()-started,3),
             'expected':anchor['credproof']['verdict'],'actual':report.get('verdict'),
             'source_sha256':sha(copy/meta['mutable_file']),
             'pytest':report.get('execution',{}).get('pytest_observation',{}),
             'scenarios':len(report.get('execution',{}).get('entry_scenarios',[])),
             'failed_checks':[k for k,v in report.get('required_checks',{}).items() if v is False]}
        expected_code={'PASS':0,'FAIL':2,'UNKNOWN':3}[row['expected']]
        row['matches']=row['actual']==row['expected'] and r.returncode==expected_code
        save(work/'command.json',row);rows.append(row)
        print(json.dumps({k:row[k] for k in ('id','actual','exit_code','matches')}),flush=True)
    save(a.output/'summary.json',{'kind':'WSL_INSTALLED_WHEEL_ANCHOR_CHECK','model_calls':0,
        'expected_count':16,'matched':sum(x['matches'] for x in rows),'rows':rows})
    return 0 if all(x['matches'] for x in rows) else 1


if __name__=='__main__':raise SystemExit(main())
