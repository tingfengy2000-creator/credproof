"""Preparation-only download of one pinned official Ollama model; no inference or fallback."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import shutil
import time
import urllib.request
from runtime_config import linux_runtime_root

BASE = 'https://registry.ollama.ai/v2/library/qwen3-coder'
ROOT = linux_runtime_root()
MODELS = ROOT / 'models'
EXPECTED_MANIFEST = '06c1097efce0431c2045fe7b2e5108366e43bee1b4603a7aded8f21689e90bca'


def download():
    raw = (ROOT / 'model-manifest.download.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != EXPECTED_MANIFEST:
        raise ValueError('Official manifest identity changed; review instead of silently replacing')
    manifest = json.loads(raw)
    records = []
    for blob in [manifest['config'], *manifest['layers']]:
        digest, size = blob['digest'], blob['size']
        destination = MODELS / 'blobs' / digest.replace(':', '-')
        parts = ROOT / 'downloads' / digest.replace(':', '-')
        parts.mkdir(parents=True, exist_ok=True)
        count = 8 if size > 1024 * 1024 else 1
        step = (size + count - 1) // count
        def get_part(i):
            start, end = i * step, min(size, (i + 1) * step) - 1
            expected = end - start + 1
            path = parts / (f'part-{i:02d}' if count > 1 else 'whole-v1')
            if count > 1 and path.exists() and path.stat().st_size == expected:
                return path
            last = None
            for attempt in range(3):
                offset = path.stat().st_size if path.exists() and count > 1 else 0
                if offset > expected:
                    raise ValueError('Oversized partial download')
                headers = {'User-Agent': 'CredProof-local-pilot-prepare'}
                if count > 1:
                    headers['Range'] = f'bytes={start + offset}-{end}'
                request = urllib.request.Request(BASE + '/blobs/' + digest, headers=headers)
                try:
                    with urllib.request.urlopen(request, timeout=60) as response:
                        if count > 1 and response.status != 206:
                            raise ValueError('Server did not honor bounded Range')
                        with path.open('ab' if count > 1 else 'wb') as stream:
                            while data := response.read(1024 * 1024):
                                if stream.tell() + len(data) > (expected if count > 1 else 1024 * 1024):
                                    raise ValueError('Range response too large')
                                stream.write(data)
                    if count > 1 and path.stat().st_size != expected:
                        raise ValueError('Truncated range')
                    print(json.dumps({'blob': digest, 'part': i, 'bytes': expected}), flush=True)
                    return path
                except Exception as exc:
                    last = type(exc).__name__
                    print(json.dumps({'part': i, 'attempt': attempt + 1, 'error_type': last}), flush=True)
                    time.sleep(1)
            raise RuntimeError('Download failed: ' + str(last))
        with concurrent.futures.ThreadPoolExecutor(max_workers=count) as pool:
            paths = list(pool.map(get_part, range(count)))
        temporary = destination.with_suffix('.verified-partial')
        h = hashlib.sha256()
        with temporary.open('wb') as target:
            for path in paths:
                with path.open('rb') as source:
                    while data := source.read(4 * 1024 * 1024):
                        h.update(data)
                        target.write(data)
        if h.hexdigest() != digest.split(':')[1] or (count > 1 and temporary.stat().st_size != size):
            raise ValueError('Official blob hash/size mismatch')
        if destination.exists():
            raise ValueError('Refuse to replace an existing final blob')
        temporary.rename(destination)
        records.append({'digest': digest, 'manifest_size': size, 'actual_size': destination.stat().st_size,
                        'verified': True, 'size_metadata_matches': destination.stat().st_size == size})
    final_manifest = MODELS / 'manifests/registry.ollama.ai/library/qwen3-coder/30b'
    if final_manifest.exists():
        raise ValueError('Refuse to overwrite manifest')
    final_manifest.write_bytes(raw)
    (ROOT / 'download-receipt.json').write_text(json.dumps({'source': BASE, 'manifest_sha256': EXPECTED_MANIFEST, 'blobs': records}, indent=2))
    print('Official model bytes and manifest verified', flush=True)


if __name__ == '__main__':
    download()
