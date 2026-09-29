"""Pinned-engine adapter; no remote credential validity checks."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import tempfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def safe_relative(name):
    p = PurePosixPath(name)
    if (not name or '\\' in name or ':' in name or p.is_absolute()
            or any(ord(c) < 32 or c in '<>"|?*' for c in name)
            or any(x in ('', '.', '..', '.git') or x.endswith((' ', '.')) for x in name.split('/'))):
        raise ValueError('Unsafe relative path')
    reserved = {'CON', 'PRN', 'AUX', 'NUL'} | {f'{prefix}{i}' for prefix in ('COM', 'LPT') for i in range(1, 10)}
    if any(x.split('.')[0].upper() in reserved for x in name.split('/')):
        raise ValueError('Reserved device path')
    return p.as_posix()


class Gitleaks:
    def __init__(self, executable, config):
        self.executable = Path(executable).resolve(strict=True)
        self.config = Path(config).resolve(strict=True)
        proc = subprocess.run([str(self.executable), 'version'], capture_output=True, timeout=10, check=True)
        self.version = proc.stdout.decode().strip()
        if self.version != '8.28.0':
            raise ValueError('Pilot requires the frozen Gitleaks 8.28.0 engine')

    def descriptor(self):
        return {'engine': 'gitleaks', 'version': self.version,
                'binary_sha256': sha(self.executable.read_bytes()),
                'rules_sha256': sha(self.config.read_bytes()),
                'flags': ['dir', '--redact=100', '--ignore-gitleaks-allow', '--exit-code=10', 'isolated-empty-ignore-file']}

    def scan(self, files):
        # Only temporary material copied from the explicit scope is visible to the scanner.
        with tempfile.TemporaryDirectory(prefix='credproof-scan-') as temporary:
            root = Path(temporary).resolve()
            material = root / 'material'
            material.mkdir()
            for name, data in files.items():
                target = material / safe_relative(name)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            config = root / 'rules.toml'
            config.write_bytes(self.config.read_bytes())
            ignore = root / 'empty.ignore'
            ignore.write_text('', encoding='utf-8')
            report = root / 'scanner.json'
            args = [str(self.executable), 'dir', str(material), '--config', str(config),
                    '--report-format', 'json', '--report-path', str(report),
                    '--redact=100', '--ignore-gitleaks-allow', '--exit-code=10',
                    '--no-banner', '--log-level', 'error', '--gitleaks-ignore-path', str(ignore)]
            env = {k: v for k, v in os.environ.items() if not k.upper().startswith('GITLEAKS_')}
            try:
                result = subprocess.run(args, capture_output=True, timeout=20, env=env, cwd=root)
                if result.returncode not in (0, 10):
                    return {'status': 'UNKNOWN', 'reason': 'scanner_process_error', 'exit_code': result.returncode}
                records = json.loads(report.read_text(encoding='utf-8'))
                locations = []
                for record in records:
                    raw = Path(record['File'])
                    if raw.is_absolute():
                        relative = raw.resolve().relative_to(material).as_posix()
                    else:
                        relative = raw.as_posix()
                    if relative not in files:
                        return {'status': 'UNKNOWN', 'reason': 'unexpected_scanner_path'}
                    locations.append({'file': relative, 'line': record['StartLine'], 'rule': record['RuleID']})
                if (result.returncode == 0) != (len(locations) == 0):
                    return {'status': 'UNKNOWN', 'reason': 'inconsistent_scanner_exit'}
                return {'status': 'FAIL' if locations else 'PASS', 'reason': 'findings' if locations else 'zero_findings',
                        'finding_count': len(locations), 'locations': locations, 'objects_scanned': len(files)}
            except (OSError, subprocess.TimeoutExpired, ValueError, KeyError):
                return {'status': 'UNKNOWN', 'reason': 'scanner_unavailable_or_invalid_output'}
