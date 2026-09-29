"""Fetch a pinned official Gitleaks executable; never extract arbitrary archive paths."""
import hashlib
import io
import json
from pathlib import Path
import platform
import tarfile
import urllib.request
import zipfile

VERSION = '8.28.0'
ROOT = Path(__file__).resolve().parents[1]


def main():
    system = {'Windows': 'windows', 'Linux': 'linux', 'Darwin': 'darwin'}[platform.system()]
    arch = {'AMD64': 'x64', 'x86_64': 'x64', 'arm64': 'arm64', 'aarch64': 'arm64'}[platform.machine()]
    extension = 'zip' if system == 'windows' else 'tar.gz'
    name = f'gitleaks_{VERSION}_{system}_{arch}.{extension}'
    base = f'https://github.com/gitleaks/gitleaks/releases/download/v{VERSION}/'
    def get(url):
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'CredProof-mechanism-pilot'}), timeout=60) as r:
            return r.read()
    checksums = get(base + f'gitleaks_{VERSION}_checksums.txt').decode()
    expected = next(line.split()[0] for line in checksums.splitlines() if line.split()[-1] == name)
    data = get(base + name)
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        raise RuntimeError('Official archive checksum mismatch')
    executable = 'gitleaks.exe' if system == 'windows' else 'gitleaks'
    if extension == 'zip':
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            binary = archive.read(executable)
            license_text = archive.read('LICENSE')
    else:
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
            binary = archive.extractfile(executable).read()
            license_text = archive.extractfile('LICENSE').read()
    destination = ROOT / '.tools' / f'gitleaks-{VERSION}'
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / executable
    target.write_bytes(binary)
    target.chmod(0o755)
    (destination / 'LICENSE').write_bytes(license_text)
    (destination / 'receipt.json').write_text(json.dumps({
        'version': VERSION, 'source': base + name, 'archive_sha256': actual,
        'executable_sha256': hashlib.sha256(binary).hexdigest(),
        'verification': 'matches checksum published with the official release; not independent attestation'
    }, indent=2) + '\n', encoding='utf-8')
    print(target)


if __name__ == '__main__':
    main()
