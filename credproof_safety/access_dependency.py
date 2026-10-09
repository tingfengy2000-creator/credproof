"""Trusted access dependency identity and a minimal model-facing API contract."""
import hashlib
from pathlib import Path

VERSION = '1.0.0'
API = {
    'import': 'from credproof_access import read_text, get_json',
    'read_text': 'read_text(path: str, *, encoding="utf-8") -> str. Real read; resolved ancestry/symlink check; denied=ValueError.',
    'get_json': 'get_json(url: str, credential: str, *, timeout=3.0) -> JSON data. Real authenticated allowed GET; denied=ValueError; never follow redirects, redirect=urllib.error.HTTPError.',
    'policy': 'Runner installs once before import. Do not configure or invent env names. Pass actual business inputs.',
    'single_operation_examples': ['text = read_text(path)', 'data = get_json(url, credential)'],
    'not_a_solution': 'This API does not validate business requests, remove sensitive logs/return fields, create business results, or decide PASS.'}


def dependency_receipt(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1] / 'credproof_access'
    files = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
             for name in ('__init__.py', 'contract.py')}
    return {'name': 'credproof_access', 'version': VERSION, 'files': files,
            'trust': 'fixed reviewed dependency, not candidate mutable material'}
