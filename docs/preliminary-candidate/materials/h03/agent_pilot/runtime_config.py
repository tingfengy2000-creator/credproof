"""Trusted operator configuration; no downloads, services or candidate execution."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re

DEFAULTS = {'wsl_distribution': 'Ubuntu-24.04', 'wsl_user': '',
            'runtime_root': '~/credproof-agent-runtime'}


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
        if not isinstance(override, dict) or set(override) - set(DEFAULTS):
            raise ValueError('Unsupported runtime configuration keys')
        value.update(override)
    if (not isinstance(value['wsl_distribution'], str)
            or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_. -]{0,127}', value['wsl_distribution'])):
        raise ValueError('Invalid WSL distribution')
    if (not isinstance(value['wsl_user'], str)
            or value['wsl_user'] and not re.fullmatch(r'[a-z_][a-z0-9_-]{0,63}\$?', value['wsl_user'])):
        raise ValueError('Invalid WSL user')
    value['runtime_root'] = validate_runtime_root(os.environ.get('CREDPROOF_RUNTIME_ROOT', value['runtime_root']))
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
