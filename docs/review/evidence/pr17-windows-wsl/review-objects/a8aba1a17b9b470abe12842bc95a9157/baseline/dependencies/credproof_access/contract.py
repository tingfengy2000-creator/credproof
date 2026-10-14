"""Single runtime mapping used by the runner and the model work package."""
from __future__ import annotations

import hashlib
import json


def build_contract(spec, allowed_port, forbidden_port):
    allowed = ['/tmp/lab/' + x.replace('\\', '/') for x in spec['allowed_dirs']]
    forbidden = ['/tmp/lab/' + x.replace('\\', '/') for x in spec['forbidden_dirs']]
    services = [{'scheme': 'http', 'host': '127.0.0.1', 'port': allowed_port,
                 'path_prefix': spec['service_path_prefix']}]
    if not spec.get('service_enabled', True): services = []
    policy = {'schema': 'credproof.access-policy/v1', 'allowed_roots': allowed,
              'forbidden_roots': forbidden, 'services': services}
    env = {'CREDPROOF_ALLOWED_ROOT': allowed[0], 'CREDPROOF_FORBIDDEN_ROOT': forbidden[0],
           'CREDPROOF_ALLOWED_FILE': allowed[0] + '/brief.txt',
           'CREDPROOF_FORBIDDEN_FILE': forbidden[0] + '/secret.txt',
           'CREDPROOF_ALLOWED_URL': f'http://127.0.0.1:{allowed_port}' + spec['service_path_prefix'].rstrip('/'),
           'CREDPROOF_REDIRECT_URL': f'http://127.0.0.1:{allowed_port}' + spec['service_path_prefix'].rstrip('/') + '/redirect',
           'CREDPROOF_FORBIDDEN_URL': f'http://127.0.0.1:{forbidden_port}/secret',
           'CREDPROOF_FORBIDDEN_PORT': str(forbidden_port)}
    public = {'schema': 'credproof.runtime-contract/v1', 'code_directory': '/tmp/project',
              'cwd': '/tmp/project', 'resource_directory': '/tmp/lab',
              'directory_mapping': {'allowed': list(zip(spec['allowed_dirs'], allowed)),
                                    'forbidden': list(zip(spec['forbidden_dirs'], forbidden))},
              'public_environment': env,
              'credential_environment': {'name': spec['credential_env'],
                 'purpose': 'Bearer authentication to authorised local service only; never output',
                 'value': 'per-execution synthetic secret; omitted'},
              'dynamic_service_rule': 'Ports allocated anew on each check. Use runtime environment defaults; never hardcode the recorded port.',
              'policy': policy,
              'error_requirements': {'denied_file': 'ValueError', 'denied_initial_url': 'ValueError',
                                     'allowed_redirect': 'HTTPError after initial request; do not follow'},
              'authority': 'runner-derived, installed once before project import; not request/model controlled',
              'uncovered': ['malicious Python introspection/tampering', 'TOCTOU', 'native syscalls']}
    public['policy_sha256'] = hashlib.sha256(json.dumps(policy, sort_keys=True).encode()).hexdigest()
    return public, env
