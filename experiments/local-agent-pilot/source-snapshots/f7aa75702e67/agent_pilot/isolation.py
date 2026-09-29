"""Text-only API to the gated Linux candidate sandbox; no host fallback."""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

RUNNER = Path(__file__).with_name('sandbox_runner.py')
BOOTSTRAP = """import base64,hashlib,json,sys
packet=json.load(sys.stdin)
source=base64.b64decode(packet['runner_b64'])
namespace={'__name__':'credproof_trusted_isolation'}
exec(compile(source,'<trusted-sandbox-runner>','exec'),namespace)
result=namespace['handle'](packet['request'],hashlib.sha256(source).hexdigest())
sys.stdout.write(json.dumps(result,ensure_ascii=False))
"""


def _dispatch(request):
    source = RUNNER.read_bytes()
    identity = hashlib.sha256(source).hexdigest()
    if sys.platform == 'linux':
        from . import sandbox_runner
        return sandbox_runner.handle(request, identity)
    if os.name != 'nt':
        return {'status': 'ISOLATION_ERROR', 'reason': 'supported_linux_or_wsl_required'}
    packet = {'runner_b64': base64.b64encode(source).decode('ascii'), 'request': request}
    try:
        process = subprocess.run(['wsl.exe', '-d', 'Ubuntu-24.04', '-u', 'tingfeng', '--',
            'python3', '-I', '-c', BOOTSTRAP], input=json.dumps(packet).encode('utf-8'),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=120 if request['operation'] == 'prepare' else 35)
        if process.returncode != 0:
            return {'status': 'ISOLATION_ERROR', 'reason': 'wsl_supervisor_failed', 'returncode': process.returncode}
        return json.loads(process.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {'status': 'ISOLATION_ERROR', 'reason': 'linux_supervisor_unavailable'}


def prepare_isolation():
    """Only trusted distro files and the checksum-pinned Ubuntu package are used."""
    return _dispatch({'operation': 'prepare'})


def probe_isolation():
    """Run the fixed self-authored boundary probes; never takes candidate input."""
    return _dispatch({'operation': 'probe'})


def run_isolated(candidate_code: str, harness_code: str, input_data: dict, *, timeout_seconds=10):
    """Return raw private harness output to the judge, never directly to a model."""
    return _dispatch({'operation': 'run', 'candidate_code': candidate_code,
                      'harness_code': harness_code, 'input_data': input_data,
                      'timeout_seconds': timeout_seconds})


if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in ('prepare', 'probe'):
        raise SystemExit('Usage: python -m agent_pilot.isolation prepare|probe')
    result = prepare_isolation() if sys.argv[1] == 'prepare' else probe_isolation()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result.get('ready') is True or sys.argv[1] == 'prepare' and result.get('profile') else 2)
