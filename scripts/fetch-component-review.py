"""Anonymous fixed-commit retrieval of a review bundle; never runs project code."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import urllib.request

ap = argparse.ArgumentParser()
ap.add_argument('--commit', required=True)
ap.add_argument('--prefix', required=True)
ap.add_argument('--output', type=Path, required=True)
ap.add_argument('--proxy', default='')
args = ap.parse_args()
if not re.fullmatch(r'[0-9a-f]{40}', args.commit):
    raise ValueError('full commit required')
prefix = PurePosixPath(args.prefix)
if prefix.is_absolute() or '..' in prefix.parts:
    raise ValueError('repository-relative prefix required')
root = Path(__file__).resolve().parents[1]
args.output.mkdir(parents=True, exist_ok=False)
rows = []
base = 'https://raw.githubusercontent.com/tingfengy2000-creator/credproof/' + args.commit + '/'

def fetch(path):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler(
        {'https': args.proxy} if args.proxy else {}))
    # No cookie jar, Authorization header or authenticated Git credential helper.
    request = urllib.request.Request(base + path, headers={'User-Agent': 'CredProof-anonymous-review'})
    with opener.open(request, timeout=45) as response:
        body = response.read()
        status = response.status
    expected = subprocess.check_output(['git', '-C', str(root), 'show', args.commit + ':' + path])
    if not body or body != expected or body.startswith(b'version https://git-lfs.github.com/spec/'):
        raise ValueError('anonymous body mismatch: ' + path)
    return body, {'path': path, 'url': base + path, 'http_status': status,
                  'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest(),
                  'matches_git_blob': True}

manifest_body, row = fetch(args.prefix + '/manifest.json')
rows.append(row)
manifest = json.loads(manifest_body)
(args.output / 'manifest.json').write_bytes(manifest_body)

def material(item):
    name, digest = item
    rel = PurePosixPath(name)
    if rel.is_absolute() or '..' in rel.parts:
        raise ValueError('unsafe manifest name')
    body, receipt = fetch(args.prefix + '/' + name)
    if hashlib.sha256(body).hexdigest() != digest:
        raise ValueError('published manifest mismatch: ' + name)
    target = args.output / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(body)
    return receipt

with ThreadPoolExecutor(max_workers=4) as pool:
    rows.extend(pool.map(material, manifest['files'].items()))
receipt = {'kind': 'ANONYMOUS_FIXED_GIT_BUNDLE_RETRIEVAL', 'source_commit': args.commit,
           'source_prefix': args.prefix, 'authorization_sent': False, 'cookies_sent': False,
           'tls_verification_enabled': True, 'model_calls': 0, 'execution_performed': False,
           'newline_policy': 'exact Raw response bytes, compared with fixed Git blob and manifest',
           'files': rows, 'pass': True}
(args.output.parent / (args.output.name + '-retrieval.json')).write_text(
    json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
print(json.dumps({'commit': args.commit, 'files': len(rows), 'pass': True}))
