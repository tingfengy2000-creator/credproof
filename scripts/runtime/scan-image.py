"""Bounded docker-export tar inspection; no extraction or link traversal.

Every regular member is hashed in chunks. Recognised binary members bypass
text decoding/regex, not the byte inventory. CLI has a hard child-process
watchdog; scan() additionally checks its cooperative deadline between chunks.
"""
from __future__ import annotations
import argparse
from bisect import bisect_right
from collections import Counter
import hashlib
import importlib.util
import json
import multiprocessing
import os
from pathlib import Path, PurePosixPath
import re
import socket
import tarfile
import tempfile
import time

spec=importlib.util.spec_from_file_location('delivery_scan',Path(__file__).parents[1]/'delivery/scan.py')
patterns_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(patterns_module)
MAX_MEMBER=64*1024**2
MAX_TEXT=8*1024**2
MAX_TOTAL=8*1024**3
MAX_MEMBERS=200000
MAX_FINDINGS=20000
DEFAULT_SECONDS=120
TRIGGERS={'windows_absolute_path':(':',),'home_absolute_path':('/home/',),
          'wsl_drive_path':('/mnt/',),'email':('@',),'private_key':('PRIVATE KEY',),
          'aws_access_key':('AKIA','ASIA'),'github_token':('gh','github_pat_'),'api_key':('sk-',)}


class ScanIncomplete(ValueError):
    def __init__(self, reason, *, member=None, size=None, limit=None):
        super().__init__(reason)
        self.details = {k:v for k,v in {'member':member,'member_bytes':size,'limit_bytes':limit}.items() if v is not None}


def private_list(value):
    if not isinstance(value,list) or any(not isinstance(x,str) or not x for x in value):
        raise ValueError('private-values-file must be a JSON list of non-empty strings')
    return value


def scan(archive,exceptions=(),private_values=(),*,max_seconds=DEFAULT_SECONDS,max_member_bytes=MAX_MEMBER):
    if not 0 < max_seconds <= 600 or not 0 < max_member_bytes <= 256*1024**2:
        raise ValueError('Invalid declared scan boundary')
    private_values=private_list(list(private_values) if isinstance(private_values,tuple) else private_values)
    started=time.monotonic();deadline=started+max_seconds
    def check_time():
        if time.monotonic()>=deadline:raise ScanIncomplete('deadline_exceeded')
    patterns={k:re.compile(v,re.I if k.endswith('path') else 0) for k,v in patterns_module.PATTERNS.items()}
    values={socket.gethostname(),os.environ.get('USERNAME',''),os.environ.get('USER',''),*private_values}
    values={v for v in values if len(v)>=4}
    identity=[re.compile(r'(?<![\w])'+re.escape(v)+r'(?![\w])',re.I) for v in values]
    findings,reviewed,files,links,skipped=[],[],{},[],[]
    distribution=Counter();total=text_count=binary_count=0
    exact={}
    for e in exceptions:
        if not isinstance(e,dict) or set(e)!={'file','file_sha256','kind','match_sha256','reason'} or not all(isinstance(v,str) and v for v in e.values()):
            raise ValueError('Exceptions must bind exact file, bytes, match and reason')
        exact[(e['file'],e['file_sha256'],e['kind'],e['match_sha256'])]=e['reason']
    def inspect(name,data,digest):
        nonlocal text_count
        text_count+=1;text=data.decode('utf8',errors='replace');lines=None
        def matched(kind,m):
            nonlocal lines
            if lines is None:lines=[x.start() for x in re.finditer('\n',text)]
            record={'file':name,'file_sha256':digest,'match_sha256':hashlib.sha256(m.group().encode()).hexdigest(),
                    'kind':kind,'line':bisect_right(lines,m.start())+1}
            # Public system-package diagnostics only, never emit token/key
            # matches. These proposals are NOT automatic exceptions.
            if kind in ('email','windows_absolute_path','home_absolute_path','operator_identity'):
                begin=text.rfind('\n',0,m.start())+1;end=text.find('\n',m.end())
                record['review_context']=text[begin:end if end>=0 else len(text)][:400]
            reason=exact.get((name,digest,kind,hashlib.sha256(m.group().encode()).hexdigest()))
            (reviewed if reason else findings).append({**record,**({'reason':reason} if reason else {})})
            if len(findings)+len(reviewed)>MAX_FINDINGS:raise ScanIncomplete('finding_count_limit')
        for kind,p in patterns.items():
            check_time()
            # Necessary-character prefilter; matching uses the unchanged
            # delivery patterns. In particular avoid quadratic email searches
            # through long base64/text members that contain no @ at all.
            haystack=text.lower() if kind.endswith('path') else text
            if kind in TRIGGERS and not any(x in haystack for x in TRIGGERS[kind]):continue
            for m in p.finditer(text):matched(kind,m);check_time()
        for p in identity:
            check_time()
            for m in p.finditer(text):matched('operator_identity',m);check_time()
    with tarfile.open(archive,'r:*') as tf:
        for count,member in enumerate(tf,1):
            check_time();name=member.name;p=PurePosixPath(name)
            if count>MAX_MEMBERS:raise ScanIncomplete('member_count_limit')
            if p.is_absolute() or '..' in p.parts or '\\' in name:raise ValueError('Unsafe archive member name')
            if member.issym() or member.islnk():
                links.append({'file':name,'target':member.linkname,'followed':False})
                inspect(name,member.linkname.encode(),'');continue
            if member.isdir():continue
            if not member.isfile():skipped.append({'file':name,'type':'special_member_not_read'});continue
            if name in files:raise ValueError('Duplicate archive file')
            if member.size>max_member_bytes:raise ScanIncomplete('member_size_limit',member=name,size=member.size,limit=max_member_bytes)
            if total+member.size>MAX_TOTAL:raise ScanIncomplete('total_size_limit')
            stream=tf.extractfile(member);sample=stream.read(min(4096,member.size));read=len(sample)
            binary=b'\x00' in sample or sample.startswith((b'\x7fELF',b'\x89PNG',b'\xff\xd8',b'PK\x03\x04'))
            if not binary and member.size>MAX_TEXT:raise ScanIncomplete('text_size_limit',member=name,size=member.size,limit=MAX_TEXT)
            h=hashlib.sha256(sample);chunks=[] if binary else [sample]
            while read<member.size:
                check_time();chunk=stream.read(min(1024*1024,member.size-read))
                if not chunk:raise ValueError('Truncated member')
                h.update(chunk);read+=len(chunk)
                if not binary:chunks.append(chunk)
            digest=h.hexdigest();files[name]={'bytes':read,'sha256':digest,'binary_text_scan_skipped':binary}
            total+=read;distribution[p.parts[0] if p.parts else '.']+=1
            pip_source_models='/site-packages/pip/_internal/models/' in name
            if any(x in {'.git','ollama','qwen_agent'} for x in p.parts) or ('models' in p.parts and not pip_source_models) or p.suffix in {'.gguf','.safetensors'} or any(x in name for x in ('docs/handoff/','docs/review/','experiments/')):
                findings.append({'file':name,'kind':'forbidden_image_material'})
            if binary:binary_count+=1
            else:inspect(name,b''.join(chunks),digest)
    check_time()
    if not files or not text_count:raise ValueError('Empty or anomalous scan coverage')
    return {'schema':'credproof.image-scan/v2','status':'COMPLETED','files_scanned':len(files),'bytes_scanned':total,
            'text_files_scanned':text_count,'binary_files_hashed':binary_count,'directory_distribution':dict(distribution),
            'duration_seconds':round(time.monotonic()-started,3),'sensitive_hits':len(findings),'findings':findings,
            'reviewed_exceptions':reviewed,'files':files,'links':links,'special_members':skipped,
            'limits':{'member_bytes':max_member_bytes,'text_bytes':MAX_TEXT,'total_bytes':MAX_TOTAL,'members':MAX_MEMBERS,'seconds':max_seconds},
            'limitations':'Pattern check. Binary bodies hashed but not decoded; links not followed; not universal credential discovery.'}


def worker(archive,exceptions,values,seconds,member_limit,result_file):
    try:
        r=scan(archive,exceptions,values,max_seconds=seconds,max_member_bytes=member_limit)
        code=1 if r['sensitive_hits'] else 0
    except (OSError,ValueError,tarfile.TarError) as exc:
        r={'status':'SCAN_INCOMPLETE','error_type':type(exc).__name__,
           'reason':str(exc) if isinstance(exc,ValueError) else type(exc).__name__};code=4
        if isinstance(exc,ScanIncomplete):r.update(exc.details)
    Path(result_file).write_text(json.dumps({'report':r,'exit_code':code}),encoding='utf8')


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive',type=Path);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--exceptions',type=Path,help='JSON list of exact file/hash/match exceptions')
    p.add_argument('--private-values-file',type=Path,help='UTF-8 JSON list of non-empty strings, e.g. ["host-id", "user-id"]')
    p.add_argument('--max-seconds',type=float,default=DEFAULT_SECONDS,help='Hard watchdog seconds, >0 and <=600; timeout is SCAN_INCOMPLETE')
    p.add_argument('--max-member-bytes',type=int,default=MAX_MEMBER,help='Single regular member limit; over-limit is SCAN_INCOMPLETE')
    a=p.parse_args(argv)
    try:
        if not 0<a.max_seconds<=600:raise ValueError('Invalid max-seconds')
        exceptions=json.loads(a.exceptions.read_text('utf8')) if a.exceptions else []
        if not isinstance(exceptions,list):raise ValueError('exceptions must be a JSON list')
        values=private_list(json.loads(a.private_values_file.read_text('utf8'))) if a.private_values_file else []
        with tempfile.TemporaryDirectory(prefix='credproof-image-scan-') as tmp:
            result_file=str(Path(tmp)/'result.json')
            child=multiprocessing.get_context('spawn').Process(target=worker,args=(str(a.archive),exceptions,values,a.max_seconds,a.max_member_bytes,result_file))
            child.start();child.join(a.max_seconds)
            if child.is_alive():
                child.terminate();child.join(5)
                if child.is_alive():child.kill();child.join(5)
                r={'status':'SCAN_INCOMPLETE','reason':'hard_deadline_exceeded','seconds_limit':a.max_seconds};code=4
            elif Path(result_file).is_file():
                payload=json.loads(Path(result_file).read_text('utf8'));r=payload['report'];code=payload['exit_code']
            else:r={'status':'SCAN_INCOMPLETE','reason':'worker_did_not_complete','worker_exit_code':child.exitcode};code=4
    except (OSError,ValueError) as exc:
        r={'status':'SCAN_INCOMPLETE','error_type':type(exc).__name__,'reason':str(exc) if isinstance(exc,ValueError) else type(exc).__name__};code=4
    a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:r[k] for k in ('status','files_scanned','sensitive_hits','reason') if k in r}))
    return code


if __name__=='__main__':raise SystemExit(main())
