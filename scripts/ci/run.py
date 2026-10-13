"""Trusted CI orchestration. Projects execute only through the installed checker.

Every command gets an exit receipt before the final gate. Nonzero commands do
not short circuit evidence upload. No tokens, model calls or sysctl changes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import socket
import subprocess
import sys
import tarfile
import time

ANCHORS_COMMIT = 'a5b51e303315dd2dd3f4671d7a771fb9afab0310'
RUNTIME = '/opt/credproof-ci-runtime'
IMAGE_RUNTIME = '/opt/credproof-runtime'
IMAGE_PYTHON = '/opt/credproof/venv/bin/python'


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8')


def targets(source):
    rows=[]
    for line in (source/'.credproof/targets.txt').read_text('utf8').splitlines():
        line=line.strip()
        if not line or line.startswith('#'):continue
        p=PurePosixPath(line)
        if p.is_absolute() or '..' in p.parts or '\\' in line or p.suffix!='.toml':
            raise ValueError('Target must be a repository-relative TOML path')
        resolved=(source/line).resolve(strict=True)
        if not resolved.is_relative_to(source.resolve()):raise ValueError('Target escapes source root')
        if line in rows:raise ValueError('Duplicate target')
        rows.append(line)
    if not 0<len(rows)<=16:raise ValueError('Expected 1..16 explicitly registered targets')
    return rows


class Recorder:
    def __init__(self, out):
        self.out=out;out.mkdir(parents=True,exist_ok=True);self.rows=[]

    def run(self, name, command, expected=(0,), timeout=900, cwd=None):
        started=time.monotonic();folder=self.out/name;folder.mkdir(parents=True,exist_ok=True)
        try:
            r=subprocess.run([str(x) for x in command],capture_output=True,text=True,
                             errors='replace',timeout=timeout,cwd=cwd)
            stdout,stderr,code=r.stdout,r.stderr,r.returncode
        except (OSError,subprocess.TimeoutExpired) as exc:
            stdout='';stderr=type(exc).__name__+': '+str(exc);code=4
        (folder/'stdout.txt').write_text(stdout,encoding='utf8')
        (folder/'stderr.txt').write_text(stderr,encoding='utf8')
        row={'name':name,'command':[str(x) for x in command],'exit_code':code,
             'expected_exit_codes':list(expected),'matches':code in expected,
             'duration_seconds':round(time.monotonic()-started,3)}
        self.rows.append(row);save(folder/'command.json',row);save(self.out/'commands.json',self.rows)
        print(json.dumps({'step':name,'exit_code':code,'matches':row['matches']}),flush=True)
        return code


def identity(source, out, job):
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()
    save(out/'identity.json',{'source_commit':commit,'anchors_commit':ANCHORS_COMMIT,
        'environment':job,'model_calls':0,'python':sys.version,'kernel':os.uname().release,
        'ubuntu':Path('/etc/os-release').read_text(),
        'apparmor_restrict_unprivileged_userns':read('/proc/sys/kernel/apparmor_restrict_unprivileged_userns'),
        'apparmor_enabled':read('/sys/module/apparmor/parameters/enabled'),
        'process_apparmor':read('/proc/self/attr/current'),
        'runner_image':os.environ.get('ImageVersion'),'runner_os':os.environ.get('ImageOS')})
    return commit


def read(path):
    try:return Path(path).read_text().strip()
    except OSError as exc:return type(exc).__name__


def frozen_anchors(source, folder):
    folder.mkdir(parents=True,exist_ok=False)
    archive=subprocess.check_output(['git','archive',ANCHORS_COMMIT,'examples/bench','docs/bench/bench-results.json'],cwd=source)
    import io
    with tarfile.open(fileobj=io.BytesIO(archive)) as tf:
        tf.extractall(folder,filter='data') # Fixed trusted ancestor, never project-provided tar.


def check_args(config, root, folder):
    return ['check','--config',config,'--source-root',root,'--output',folder+'/report.json',
            '--sarif',folder+'/report.sarif','--junit',folder+'/junit.xml','--summary',folder+'/summary.md']


def native(source, out, rec, commit, data):
    app=Path(os.environ['RUNNER_TEMP'])/'credproof-app';python=app/'bin/python'
    rec.run('venv',['/usr/bin/python3','-m','venv',app])
    rec.run('build-dependencies',[python,'-m','pip','install','setuptools','wheel'])
    wheels=out/'wheels';wheels.mkdir()
    rec.run('build-wheel',[python,'-m','pip','wheel','--no-deps','--no-build-isolation','-w',wheels,source])
    wheel=next(wheels.glob('*.whl'))
    save(out/'wheel.json',{'file':wheel.name,'bytes':wheel.stat().st_size,'sha256':hashlib.sha256(wheel.read_bytes()).hexdigest(),'source_commit':commit})
    rec.run('install',[python,'-m','pip','install',str(wheel)+'[test]'])
    # Scoped exception for this trusted bwrap binary only. The private rootfs
    # remains the candidate boundary; no sysctl is changed. Ubuntu documents
    # this unconfined application profile as a userns permission mechanism.
    profile=out/'native-userns.profile'
    profile.write_text('abi <abi/4.0>,\n#include <tunables/global>\nprofile credproof-ci-native '+RUNTIME+'/isolation/tools/usr/bin/bwrap flags=(unconfined) { userns, }\n')
    rec.run('native-apparmor-load',['sudo','apparmor_parser','-r',profile])
    rec.run('runtime-directory',['sudo','install','-d','-o',str(os.getuid()),'-g',str(os.getgid()),RUNTIME])
    rec.run('setup',['/usr/bin/python3',source/'scripts/runtime/setup-linux.py','--runtime-root',RUNTIME])
    os.environ['CREDPROOF_CONFIG']=RUNTIME+'/runtime.json'
    rec.run('doctor',[python,'-I','-m','credproof_safety','doctor'])
    shutil.copyfile(out/'doctor/stdout.txt',out/'doctor.json')
    os.environ['CREDPROOF_REQUIRE_SARIF_SCHEMA']='1'
    rec.run('format-tests',[python,'-m','pytest',str(source/'credproof_safety/tests/test_report_formats.py'),'-q','--junitxml='+str(out/'formats-junit.xml')],cwd=source)
    for i,config in enumerate(targets(source)):
        folder=out/f'target-{i}';folder.mkdir()
        rec.run(f'check-{i}',[python,'-I','-m','credproof_safety',*check_args(str(source/config),str(source),str(folder))])
    rec.run('anchors',[python,'-I',source/'scripts/runtime/verify-anchors.py','--source',source,
        '--source-commit',commit,'--anchors-source',data,'--anchors-commit',ANCHORS_COMMIT,
        '--runtime',RUNTIME,'--output',out/'anchors-results','--environment','native'],timeout=1200,cwd=Path(os.environ['RUNNER_TEMP']))


def container(source, out, rec, commit, data):
    image='credproof:ci';out.chmod(0o777)
    # Ubuntu's unconfined process can still transition to unprivileged_userns
    # on unshare, denying net_admin/setpcap. Grant userns to this exact trusted
    # executable via a host-loaded application exception; never change sysctl.
    profile=out/'container-userns.profile'
    profile.write_text('abi <abi/4.0>,\n#include <tunables/global>\nprofile credproof-ci-container '+IMAGE_RUNTIME+'/isolation/tools/usr/bin/bwrap flags=(unconfined) { userns, }\n')
    rec.run('container-apparmor-load',['sudo','apparmor_parser','-r',profile])
    rec.run('build',['docker','build','--build-arg','SOURCE_COMMIT='+commit,'-f',source/'deploy/docker/Dockerfile','-t',image,source],timeout=1200)
    base=json.loads((source/'deploy/docker/base-image.json').read_text())
    save(out/'base-image.json',base)
    rec.run('docker-version',['docker','version','--format','{{json .}}'])
    rec.run('docker-security',['docker','info','--format','{{json .SecurityOptions}}'])
    common=['docker','run','--rm','--network','none','--read-only','--tmpfs','/tmp:exec',
        '--cap-drop','ALL','--security-opt','no-new-privileges',
        '-v',str(source)+':/workspace:ro','-v',str(out)+':/out',
        '-v',str(data)+':/anchors:ro']
    # Explicit operator-selected R3 option: outer AppArmor unconfined. This is
    # NOT an automatic fallback nor a claim of AppArmor enforcement. Seccomp,
    # zero outer capabilities and the finite inner bwrap rootfs stay enforced.
    hardened=['--security-opt','seccomp='+str(source/'deploy/docker/seccomp-credproof.json'),
              '--security-opt','systempaths=unconfined','--security-opt','apparmor=unconfined']
    save(out/'apparmor-policy.json',{'mode':'explicit_outer_unconfined','host_profile_loaded':False,
        'candidate_profile':'deploy/apparmor/credproof-bwrap','candidate_enforcement_verified':False,
        'reason':'R3 explicit deployment option; private bwrap userns requires AppArmor permission; no sysctl changes'})
    rec.run('container-origin',[*common,*hardened,'--entrypoint',IMAGE_PYTHON,image,'-I','-c',
        "import json,sys,pathlib,credproof_safety.cli as c;print(json.dumps({'python':sys.executable,'cli':c.__file__,'apparmor':pathlib.Path('/proc/self/attr/current').read_text()}))"])
    rec.run('doctor',[*common,*hardened,image,'doctor'])
    shutil.copyfile(out/'doctor/stdout.txt',out/'doctor.json')
    for i,config in enumerate(targets(source)):
        folder=out/f'target-{i}';folder.mkdir();folder.chmod(0o777)
        rec.run(f'check-{i}',[*common,*hardened,image,*check_args('/workspace/'+config,'/workspace','/out/target-'+str(i))])
    rec.run('anchors',[*common,*hardened,'--entrypoint',IMAGE_PYTHON,image,'-I','/workspace/scripts/runtime/verify-anchors.py',
        '--source','/workspace','--source-commit',commit,'--anchors-source','/anchors','--anchors-commit',ANCHORS_COMMIT,
        '--runtime',IMAGE_RUNTIME,'--output','/out/anchors-results','--environment','container'],timeout=1200)
    blocked=out/'default-blocked';blocked.mkdir();blocked.chmod(0o777)
    rec.run('default-doctor',[*common,image,'doctor'],expected=(4,))
    shutil.copyfile(out/'default-doctor/stdout.txt',out/'default-blocked/doctor.json')
    rec.run('default-check',[*common,image,*check_args('/workspace/'+targets(source)[0],'/workspace','/out/default-blocked')],expected=(3,))
    receipt="import pathlib;print(pathlib.Path('/opt/credproof/build-receipt.json').read_text());print(pathlib.Path('/opt/credproof/source-commit.txt').read_text());import hashlib;print(hashlib.sha256(pathlib.Path('/opt/credproof-runtime/rootfs-manifest.json').read_bytes()).hexdigest())"
    rec.run('build-receipt',[*common,*hardened,'--entrypoint',IMAGE_PYTHON,image,'-I','-c',receipt])
    name='credproof-ci-scan-'+str(os.getpid())
    rec.run('image-create',['docker','create','--name',name,image,'--help'])
    archive=Path(os.environ['RUNNER_TEMP'])/'credproof-image.tar'
    rec.run('image-export',['docker','export','-o',archive,name],timeout=180)
    rec.run('image-remove',['docker','rm',name])
    rec.run('image-scan',['/usr/bin/python3',source/'scripts/runtime/scan-image.py',archive,
        '--output',out/'image-scan.json','--max-seconds','600','--exceptions',source/'deploy/docker/scan-exceptions.json'],timeout=620)
    rec.run('output-ownership',['sudo','chown','-R','--no-dereference',str(os.getuid())+':'+str(os.getgid()),out])


def publish(out, source):
    """Exact known host-field replacements; never rewrite source code syntax."""
    substitutions=[(str(source),'<source>'),(os.environ.get('RUNNER_TEMP',''),'<runner-temp>'),
        (str(Path.home()),'<runner-home>'),(socket.gethostname(),'<runner-host>')]
    substitutions=sorted(((a,b) for a,b in substitutions if len(a)>3),key=lambda x:-len(x[0]))
    # Only generated text receipts. Wheels remain byte-identical and their
    # provenance is in wheel.json; project/module files are not rewritten.
    for p in out.rglob('*'):
        if p.suffix not in ('.json','.txt','.xml','.md','.sarif','.profile') or not p.is_file():continue
        value=p.read_text('utf8')
        for old,new in substitutions:value=value.replace(old,new)
        # XML-safe replacement labels, no new angle-bracket markup.
        if p.suffix=='.xml':
            for _,new in substitutions:value=value.replace(new,new[1:-1])
        p.write_text(value,encoding='utf8')
    save(out/'publication.json',{'kind':'STRUCTURED_HOST_PATH_REDACTION','originals':'runner ephemeral commands captured before exact substitutions',
        'fields':['source directory','runner temp','runner home','runner hostname'],'model_calls':0})


def finish(out):
    summaries=[]
    for p in sorted(out.glob('target-*/summary.md')):summaries.append(p.read_text())
    rows=json.loads((out/'commands.json').read_text()) if (out/'commands.json').exists() else []
    lines=['# CredProof CI','',*summaries,'','## Execution receipts','',
        '| Step | Exit | Expected | Match |','|---|---:|---|---|']
    lines += [f"| {r['name']} | {r['exit_code']} | {r['expected_exit_codes']} | {r['matches']} |" for r in rows]
    summary='\n'.join(lines)+'\n';(out/'job-summary.md').write_text(summary,encoding='utf8')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf8') as f:f.write(summary)


def gate(out):
    rows=json.loads((out/'commands.json').read_text()) if (out/'commands.json').exists() else []
    return 0 if rows and all(x['matches'] for x in rows) and any(x['name'].startswith('check-') for x in rows) else 1


def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('native','container','gate'))
    p.add_argument('--out',type=Path,required=True);p.add_argument('--source',type=Path,default=Path.cwd())
    a=p.parse_args();source=a.source.resolve();out=a.out.resolve()
    if a.mode=='gate':return gate(out)
    rec=Recorder(out);commit=identity(source,out,a.mode)
    data=Path(os.environ['RUNNER_TEMP'])/'credproof-frozen-anchors'
    try:
        frozen_anchors(source,data)
        (native if a.mode=='native' else container)(source,out,rec,commit,data)
    except Exception as exc:
        save(out/'orchestration-error.json',{'error_type':type(exc).__name__,'reason':str(exc)})
        rec.rows.append({'name':'orchestration','exit_code':4,'expected_exit_codes':[0],'matches':False})
        save(out/'commands.json',rec.rows)
    finally:
        rec.run('apparmor-denials',['sudo','journalctl','-k','--since','30 minutes ago','--grep','apparmor="DENIED"','--no-pager'],expected=(0,1))
        publish(out,source);finish(out)
    return 0 # Final workflow gate runs only after upload.


if __name__=='__main__':raise SystemExit(main())
