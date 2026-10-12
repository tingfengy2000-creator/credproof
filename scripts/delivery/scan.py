"""Fail closed on identity/credential patterns in a complete delivery tree.

This is a deterministic publication check, not a claim of complete secret
discovery. It scans text and text members of ZIPs, preserves third-party legal
notices, and never prints a matched secret. Use --private-values-file for extra
operator-known host/account values; that file is never copied into a delivery.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import zipfile
from io import BytesIO

PATTERNS = {
    'windows_absolute_path': r'(?<![A-Za-z])[A-Za-z]:[\\/](?![\\/])[^\s"<>]+',
    'home_absolute_path': r'/home/[A-Za-z0-9_.-]+(?:/[^\s"<>]*)?',
    'wsl_drive_path': r'/mnt/[a-z](?:/[^\s"<>]*)?(?![A-Za-z])',
    'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b',
    'private_key': r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    'aws_access_key': r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
    'github_token': r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b',
    'api_key': r'\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b',
}
# A mount namespace constant is not the operator's home. This exact literal
# only occurs in the reviewed model boundary source, never as a host mount.
VIRTUAL_PATHS = {'/home/model'}
# Preserve legal notices distributed verbatim by python.org. Public legal
# contacts in that one vendor license are counted separately, not hidden.
LICENSE_CONTACTS = {'guido@cwi.nl', 'guido@python.org', 'python@stichting.nl',
                    'python-legal@python.org', 'python-dev@python.org',
                    'tim@lassi.ece.uiuc.edu', 'jheffero@archive.uwaterloo.ca',
                    'legal@cnri.reston.va.us', 'sales@cnri.reston.va.us',
                    'jones@unico.cwi.nl', 'peter@math.su.oz.au'}


def scan(root, private_values=()):
    root = Path(root).resolve(strict=True)
    results, reviewed = [], []
    values = {socket.gethostname(), os.environ.get('USERNAME', ''), os.environ.get('USER', ''), *private_values}
    values = {v for v in values if isinstance(v, str) and len(v) >= 4}
    patterns = {k: re.compile(v, re.I if k.endswith('path') else 0) for k, v in PATTERNS.items()}
    files = {}

    def text(name, data):
        # Decode safely for scanning only; no source or evidence is rewritten.
        if b'\x00' in data[:4096]:
            return
        value = data.decode('utf-8', errors='replace')
        for kind, pattern in patterns.items():
            for match in pattern.finditer(value):
                item = {'file': name, 'line': value.count('\n', 0, match.start())+1, 'kind': kind}
                literal = match.group()
                if kind == 'home_absolute_path' and literal in VIRTUAL_PATHS and name == 'credproof_safety/agent.py':
                    reviewed.append({**item, 'classification': 'isolated_virtual_home_literal'})
                elif kind == 'email' and name == 'runtime/python/LICENSE.txt' and literal in LICENSE_CONTACTS:
                    reviewed.append({**item, 'classification': 'vendor_legal_contact'})
                else:
                    results.append(item)
        for v in values:
            # Standalone identity; e.g. "user" in a Python variable is not an account name.
            for match in re.finditer(r'(?<![\w])'+re.escape(v)+r'(?![\w])', value, re.I):
                results.append({'file':name, 'line':value.count('\n',0,match.start())+1, 'kind':'operator_identity'})

    for path in sorted(root.rglob('*')):
        name = path.relative_to(root).as_posix()
        if path.is_symlink() or getattr(path, 'is_junction', lambda:False)():
            results.append({'file':name,'kind':'linked_file'}); continue
        if not path.is_file():
            continue
        data = path.read_bytes()
        files[name] = hashlib.sha256(data).hexdigest()
        if any(part in {'.git','.venv','node_modules','rootfs','__pycache__'} for part in path.relative_to(root).parts) or name.startswith(('docs/handoff/','docs/review/')):
            results.append({'file':name,'kind':'forbidden_delivery_member'})
        text(name, data)
        if zipfile.is_zipfile(BytesIO(data)):
            with zipfile.ZipFile(BytesIO(data)) as archive:
                for member in archive.infolist():
                    if not member.is_dir() and member.file_size < 16*1024*1024:
                        text(name+'!'+member.filename, archive.read(member))
    return {'schema':'credproof.delivery-scan/v1','files_scanned':len(files),
            'sensitive_hits':len(results),'findings':results,'reviewed_non_host_literals':reviewed,
            'file_sha256':files,'limitations':'Pattern check; not a universal secret detector. Binary executable internals are not decoded as source.'}


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--private-values-file',type=Path)
    a=p.parse_args();extra=json.loads(a.private_values_file.read_text('utf8')) if a.private_values_file else []
    report=scan(a.root,extra);a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'files_scanned':report['files_scanned'],'sensitive_hits':report['sensitive_hits']}))
    raise SystemExit(1 if report['sensitive_hits'] else 0)
