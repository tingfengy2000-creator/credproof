"""Small policy-bound file/HTTP operations. Not a verdict or a Python sandbox.

The trusted runner installs one immutable policy before importing project code.
No policy is accepted from a business request or from the model.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import MappingProxyType
from urllib.parse import urlsplit, unquote
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

__version__ = '1.0.0'
_policy = None


def _install_policy(value):
    """Runner-only initialization, once. Python introspection is not prevented."""
    global _policy
    if _policy is not None:
        raise RuntimeError('access policy already installed')
    if (not isinstance(value, dict) or value.get('schema') != 'credproof.access-policy/v1'
            or not isinstance(value.get('allowed_roots'), list)
            or not value['allowed_roots'] or not isinstance(value.get('services'), list)):
        raise RuntimeError('invalid or missing trusted access policy')
    roots = tuple(Path(x).resolve(strict=True) for x in value['allowed_roots'])
    forbidden = tuple(Path(x).resolve(strict=True) for x in value['forbidden_roots'])
    services = tuple(MappingProxyType(dict(x)) for x in value['services'])
    if any(x['scheme'] not in ('http', 'https') or type(x['port']) is not int
           or not 1 <= x['port'] <= 65535 or not x['path_prefix'].startswith('/')
           for x in services):
        raise RuntimeError('invalid trusted service policy')
    _policy = MappingProxyType({'roots': roots, 'forbidden': forbidden, 'services': services})


def _current_policy():
    if _policy is None:
        raise RuntimeError('trusted access policy unavailable; no unsafe fallback')
    return _policy


def read_text(path: str, *, encoding: str = 'utf-8') -> str:
    """Resolve relative to execution cwd; reject outside real allowed ancestors.

    ValueError for a denied path; normal I/O errors for a permitted path.
    No protection against malicious in-process tampering or filesystem races.
    """
    policy = _current_policy()
    if not isinstance(path, str):
        raise ValueError('file path must be text')
    resolved = Path(path).resolve()
    if (not any(resolved.is_relative_to(root) for root in policy['roots'])
            or any(resolved.is_relative_to(root) for root in policy['forbidden'])):
        raise ValueError('file outside authorised directories')
    return resolved.read_text(encoding=encoding)


class _RejectRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def get_json(url: str, credential: str, *, timeout: float = 3.0):
    """Authenticated GET to an allowed initial URL; never follow redirects.

    ValueError for denied URL; urllib.error.HTTPError for a redirect/HTTP error.
    A permitted redirect endpoint is really contacted, then its redirect refused.
    """
    policy = _current_policy()
    try:
        parsed = urlsplit(url)
        port = parsed.port or (443 if parsed.scheme == 'https' else 80)
        path = parsed.path or '/'
        decoded = unquote(path)
        valid = (not any(segment in ('.', '..') for segment in decoded.split('/'))
                 and '\\' not in decoded and decoded == path
                 and not parsed.username and not parsed.password and not parsed.fragment
                 and any(parsed.scheme == rule['scheme'] and parsed.hostname == rule['host']
                         and port == rule['port']
                         and (path == rule['path_prefix'].rstrip('/')
                              or path.startswith(rule['path_prefix'].rstrip('/') + '/'))
                         for rule in policy['services']))
    except (TypeError, ValueError):
        valid = False
    if not valid:
        raise ValueError('URL outside authorised services')
    if not isinstance(credential, str) or '\r' in credential or '\n' in credential:
        raise ValueError('invalid authentication value')
    opener = build_opener(ProxyHandler({}), _RejectRedirect())
    request = Request(url, headers={'Authorization': 'Bearer ' + credential})
    with opener.open(request, timeout=timeout) as response:
        return json.load(response)
