"""Trusted operator configuration; no downloads, services or candidate execution."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

DEFAULTS = {'wsl_distribution': 'Ubuntu-24.04', 'wsl_user': '',
            'runtime_root': '~/credproof-agent-runtime'}
OPTIONAL_KEYS = {'program_python'}


def validate_runtime_root(value):
    if (not isinstance(value, str) or not value or len(value) > 4096
            or any(c in value for c in '\x00\r\n')
            or not (value.startswith('/') or value.startswith('~/'))):
        raise ValueError('runtime_root must be an absolute Linux path or ~/ path')
    return value


def load_config(project_root=None):
    root = Path(project_root) if project_root is not None else Path(__file__).resolve().parents[1]
    explicit = os.environ.get('CREDPROOF_CONFIG')
    path = Path(explicit).expanduser() if explicit else root / 'config/local-runtime.json'
    value = dict(DEFAULTS)
    if explicit or path.exists():
        if not path.is_file() or path.stat().st_size > 16384:
            raise ValueError('Runtime configuration unavailable or oversized')
        override = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(override, dict) or set(override) - (set(DEFAULTS) | OPTIONAL_KEYS):
            raise ValueError('Unsupported runtime configuration keys')
        value.update(override)
    if (not isinstance(value['wsl_distribution'], str)
            or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_. -]{0,127}', value['wsl_distribution'])):
        raise ValueError('Invalid WSL distribution')
    if (not isinstance(value['wsl_user'], str)
            or value['wsl_user'] and not re.fullmatch(r'[a-z_][a-z0-9_-]{0,63}\$?', value['wsl_user'])):
        raise ValueError('Invalid WSL user')
    value['runtime_root'] = validate_runtime_root(os.environ.get('CREDPROOF_RUNTIME_ROOT', value['runtime_root']))
    if 'program_python' in value:
        interpreter = value['program_python']
        if not isinstance(interpreter, str) or not interpreter.strip():
            raise ValueError('program_python must be a non-empty absolute path when configured')
        if not Path(interpreter).expanduser().is_absolute():
            raise ValueError('program_python must be an absolute path')
    return value


def linux_runtime_root(config=None):
    value = config if config is not None else load_config()
    specification = validate_runtime_root(os.environ.get('CREDPROOF_RUNTIME_ROOT', value['runtime_root']))
    if os.name == 'nt':
        raise ValueError('Resolve Linux runtime paths inside the selected WSL distribution')
    path = Path(specification).expanduser()
    if not path.is_absolute():
        raise ValueError('Linux runtime root did not resolve to an absolute path')
    return path.absolute()


def wsl_prefix(config=None):
    value = config if config is not None else load_config()
    result = ['wsl.exe', '-d', value['wsl_distribution']]
    if value['wsl_user']:
        result += ['-u', value['wsl_user']]
    return result


def runtime_paths(config=None):
    """Return all Linux-side reviewed runtime paths from the shared config.

    Callers must pass these paths to WSL rather than embedding the operator's
    home directory in an execution module.  The returned values are Linux
    strings because they are consumed by ``wsl.exe`` and bubblewrap.
    """
    value = config if config is not None else load_config()
    root = validate_runtime_root(value['runtime_root']).rstrip('/')
    return {
        'root': root,
        'isolation': root + '/isolation',
        'rootfs': root + '/isolation/rootfs',
        'bubblewrap': root + '/isolation/tools/usr/bin/bwrap',
        'venv': root + '/venv',
        'python': root + '/venv/bin/python',
        'site_packages': root + '/venv/lib/python3.12/site-packages',
        'ollama': root + '/ollama/bin/ollama',
        'models': root + '/models',
    }


def execution_runtime_paths(config=None):
    """Return runtime paths resolved inside the selected WSL distribution.

    ``runtime_root`` intentionally defaults to ``~/credproof-agent-runtime`` so
    the repository does not contain an operator-specific home directory.  WSL
    does not expand ``~`` for argv passed directly to ``--exec``; resolve it
    once with the selected Linux interpreter before paths reach ``test`` or
    bubblewrap.  No shell is involved and the configured value remains
    validated by :func:`load_config`.
    """
    value = config if config is not None else load_config()
    paths = runtime_paths(value)
    root = paths['root']
    if root.startswith('~/'):
        try:
            result = subprocess.run(
                [*wsl_prefix(value), '--exec', 'python3', '-c',
                 'import os,sys; print(os.path.expanduser(sys.argv[1]))', root],
                capture_output=True, timeout=10, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError('Unable to resolve runtime_root inside WSL') from exc
        raw = result.stdout
        if b'\x00' in raw[:64]:
            text = raw.decode('utf-16le', errors='replace')
        else:
            text = raw.decode('utf-8', errors='replace')
        root = text.strip()
        if result.returncode != 0 or not root.startswith('/') or any(c in root for c in '\x00\r\n'):
            raise ValueError('WSL runtime_root resolution failed')
    return {
        'root': root.rstrip('/'),
        'isolation': root.rstrip('/') + '/isolation',
        'rootfs': root.rstrip('/') + '/isolation/rootfs',
        'bubblewrap': root.rstrip('/') + '/isolation/tools/usr/bin/bwrap',
        'venv': root.rstrip('/') + '/venv',
        'python': root.rstrip('/') + '/venv/bin/python',
        'site_packages': root.rstrip('/') + '/venv/lib/python3.12/site-packages',
        'ollama': root.rstrip('/') + '/ollama/bin/ollama',
        'models': root.rstrip('/') + '/models',
    }


def runtime_temp_root() -> Path:
    """Return the disposable Windows-side run directory.

    ``CREDPROOF_RUNTIME_TEMP`` is the only operator override.  A normal
    system temp directory is the portable default and avoids embedding a
    developer-specific drive path in the safety executor.
    """
    configured = os.environ.get('CREDPROOF_RUNTIME_TEMP')
    path = Path(configured) if configured else Path(tempfile.gettempdir()) / 'credproof-runs'
    if path.is_absolute() and any(c in str(path) for c in '\x00\r\n'):
        raise ValueError('CREDPROOF_RUNTIME_TEMP contains a control character')
    return path
