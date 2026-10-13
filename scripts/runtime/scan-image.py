"""Scan docker-export tar members without extraction or link traversal.

Uses the delivery scanner's sensitive patterns, not its directory blacklist.
Binary bytes are hashed/countable but not claimed as decoded source text.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import socket
import tarfile

spec = importlib.util.spec_from_file_location('delivery_scan', Path(__file__).parents[1] / 'delivery/scan.py')
patterns_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patterns_module)


def scan(archive, exceptions=(), private_values=()):
    patterns = {k: re.compile(v, re.I if k.endswith('path') else 0) for k,v in patterns_module.PATTERNS.items()}
    values = {socket.gethostname(), os.environ.get('USERNAME',''), os.environ.get('USER',''), *private_values}
    values = {v for v in values if len(v) >= 4}
    findings, reviewed, files, links, skipped = [], [], {}, [], []
    distribution = Counter(); total = text_count = 0
    for e in exceptions:
        if set(e) != {'file','file_sha256','kind','match_sha256','reason'} or not e['reason']:
            raise ValueError('Exceptions must bind an exact file, bytes, match and documented reason')
    def inspect(name, data, digest):
        nonlocal text_count
        if b'\x00' in data[:4096]:
            return
        text_count += 1
        text = data.decode('utf8',errors='replace')
        hits = [(kind,m) for kind,p in patterns.items() for m in p.finditer(text)]
        hits += [('operator_identity',m) for value in values
                 for m in re.finditer(r'(?<![\w])'+re.escape(value)+r'(?![\w])',text,re.I)]
        for kind,m in hits:
            record = {'file':name,'kind':kind,'line':text.count('\n',0,m.start())+1}
            exact = next((e for e in exceptions if e['file']==name and e['kind']==kind
                          and e['file_sha256']==digest
                          and e['match_sha256']==hashlib.sha256(m.group().encode()).hexdigest()),None)
            (reviewed if exact else findings).append({**record, **({'reason':exact['reason']} if exact else {})})
    with tarfile.open(archive, 'r:*') as tf:
        for count, member in enumerate(tf):
            name = member.name
            p = PurePosixPath(name)
            if count > 200000 or total > 8*1024**3:
                raise ValueError('Image exceeds declared scan boundary')
            if p.is_absolute() or '..' in p.parts or '\\' in name:
                raise ValueError('Unsafe archive member name')
            if member.issym() or member.islnk():
                links.append({'file':name,'target':member.linkname,'followed':False})
                inspect(name, member.linkname.encode(), '')
                continue
            if member.isdir():
                continue
            if not member.isfile():
                skipped.append({'file':name,'type':'special_member_not_read'})
                continue
            if name in files:
                raise ValueError('Duplicate archive file')
            if member.size > 256*1024**2:
                raise ValueError('Member exceeds supported scan size')
            stream = tf.extractfile(member)
            data = stream.read(member.size+1)
            if len(data) != member.size:
                raise ValueError('Truncated member')
            digest = hashlib.sha256(data).hexdigest()
            files[name] = {'bytes':len(data),'sha256':digest}
            total += len(data); distribution[p.parts[0] if p.parts else '.'] += 1
            if any(x in {'.git','models','ollama','qwen_agent'} for x in p.parts) or any(
                    part in name for part in ('docs/handoff/','docs/review/','experiments/')):
                findings.append({'file':name,'kind':'forbidden_image_material'})
            inspect(name,data,digest)
    if not files or not text_count:
        raise ValueError('Empty or anomalous scan coverage')
    return {'schema':'credproof.image-scan/v1','files_scanned':len(files),'bytes_scanned':total,
            'text_files_scanned':text_count,'directory_distribution':dict(distribution),
            'sensitive_hits':len(findings),'findings':findings,'reviewed_exceptions':reviewed,
            'files':files,'links':links,'special_members':skipped,
            'limitations':'Pattern check. Links not followed; binary internals not decoded; no universal credential-discovery claim.'}


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive',type=Path);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--exceptions',type=Path);p.add_argument('--private-values-file',type=Path)
    a=p.parse_args()
    try:
        r=scan(a.archive,json.loads(a.exceptions.read_text('utf8')) if a.exceptions else [],
               json.loads(a.private_values_file.read_text('utf8')) if a.private_values_file else [])
        code=1 if r['sensitive_hits'] else 0
    except (OSError,ValueError,tarfile.TarError) as e:
        r={'status':'SCAN_INCOMPLETE','error_type':type(e).__name__};code=4
    a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:r[k] for k in ('status','files_scanned','sensitive_hits') if k in r}))
    raise SystemExit(code)
