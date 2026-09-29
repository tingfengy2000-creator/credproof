"""Preparation helper for the one checksum-pinned official Linux Ollama archive.

Stage 1 on Windows Python 3.14: --decompress ARCHIVE --tar NEW_TAR
Stage 2 in WSL Python 3.12: --extract TAR --destination NEW_DIRECTORY
No installer scripts, global services or account configuration are used.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tarfile

EXPECTED = 'c238986e61d40c0cc5f4a9b9e40b9eea104350b77efa34741fc134e105cb9533'
URL = 'https://github.com/ollama/ollama/releases/download/v0.34.4/ollama-linux-amd64.tar.zst'


def file_sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--decompress', type=Path)
    parser.add_argument('--tar', type=Path)
    parser.add_argument('--extract', type=Path)
    parser.add_argument('--destination', type=Path)
    args = parser.parse_args()
    if args.decompress:
        from compression import zstd
        actual = file_sha(args.decompress)
        if actual != EXPECTED:
            raise SystemExit('Official release archive SHA-256 mismatch')
        if args.tar.exists():
            raise SystemExit('Refuse to overwrite tar')
        with zstd.open(args.decompress, 'rb') as source, args.tar.open('xb') as target:
            shutil.copyfileobj(source, target, length=4 * 1024 * 1024)
        receipt = {'source': URL, 'version': '0.34.4', 'archive_sha256': actual,
                   'tar_sha256': file_sha(args.tar), 'tar_bytes': args.tar.stat().st_size}
        args.tar.with_suffix('.receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(receipt))
    elif args.extract:
        receipt = json.loads(args.extract.with_suffix('.receipt.json').read_text(encoding='utf-8'))
        if receipt['archive_sha256'] != EXPECTED or receipt['tar_sha256'] != file_sha(args.extract):
            raise SystemExit('Uncompressed archive integrity mismatch')
        if args.destination.exists():
            raise SystemExit('Refuse to overwrite installation')
        with tarfile.open(args.extract, 'r:') as archive:
            for member in archive.getmembers():
                path = PurePosixPath(member.name)
                if path.is_absolute() or '..' in path.parts or path.parts[0] not in ('bin', 'lib'):
                    raise SystemExit('Unexpected official archive layout')
                if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
                    raise SystemExit('Unexpected special archive member')
            args.destination.mkdir(parents=True)
            archive.extractall(args.destination, filter='data')
        print(json.dumps({'installed': str(args.destination), 'binary_sha256': file_sha(args.destination / 'bin/ollama'), **receipt}))
    else:
        parser.error('Choose preparation stage')


if __name__ == '__main__':
    main()
