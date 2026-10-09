"""Fresh model-controller/Ollama boundary probe, with one bounded inference.

No project or candidate executes here. Output must be a new directory. Requires
the existing trusted WSL runtime; never downloads or falls back to a cloud API.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from credproof_safety.agent import _MODEL_BOUNDARY_BOOTSTRAP, _MODEL_SCRIPT, _runtime_settings, _wsl_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=False)
    stage = output / 'model-stage'; (stage / 'agent_pilot').mkdir(parents=True)
    repo = Path(__file__).resolve().parents[1]
    for name in ('__init__.py', 'tools.py', 'model_client.py', 'model_config.py'):
        (stage / 'agent_pilot' / name).write_bytes((repo / 'agent_pilot' / name).read_bytes())
    from agent_pilot.model_config import selected_profile
    (stage / 'model-profile.json').write_text(json.dumps(selected_profile()), encoding='utf8')
    (stage / 'initial-context.json').write_text('{}', encoding='utf8')
    (stage / 'worker.py').write_text(_MODEL_SCRIPT, encoding='utf-8')
    sentinel = output / 'host-sentinel.txt'
    sentinel.write_text('harmless synthetic isolation sentinel\n', encoding='utf-8')
    wsl, paths = _runtime_settings()
    encoded = base64.b64encode(_MODEL_BOUNDARY_BOOTSTRAP.encode()).decode()
    command = [*wsl, '/usr/bin/env', 'CREDPROOF_BOUNDARY_ONLY=1', paths['python'], '-c',
               'import base64;exec(compile(base64.b64decode(' + repr(encoded) + '),"<model-boundary>","exec"))',
               paths['root'], _wsl_path(stage), _wsl_path(output), _wsl_path(sentinel),
               paths['root'] + '/model-probe-rpc-' + uuid.uuid4().hex]
    result = subprocess.run(command, capture_output=True, timeout=180, check=False)
    (output / 'supervisor-stdout.bin').write_bytes(result.stdout)
    (output / 'supervisor-stderr.bin').write_bytes(result.stderr)
    receipt = {'schema': 'credproof.model-boundary-integration/v1', 'returncode': result.returncode,
               'host_python': sys.version, 'worker_sha256': hashlib.sha256(_MODEL_SCRIPT.encode()).hexdigest(),
               'supervisor_sha256': hashlib.sha256(_MODEL_BOUNDARY_BOOTSTRAP.encode()).hexdigest(),
               'command': ['wsl --exec env CREDPROOF_BOUNDARY_ONLY=1 <trusted-runtime-python>',
                           '<frozen-supervisor>', '<runtime>', '<minimal-stage>', '<output>', '<harmless-sentinel>', '<native-rpc>'],
               'paid_api_used': False}
    if result.returncode == 0:
        work = output / 'model-work'
        probe = json.loads((work / 'boundary-probe.json').read_text())
        service = json.loads((work / 'service-boundary.json').read_text())
        generation = json.loads((work / 'live-generation.json').read_text())
        tree = json.loads((work / 'process-tree-after-inference.json').read_text())
        receipt['checks'] = {
            'controller_only_loopback': probe['interfaces'] == ['lo'],
            'controller_external_denied': len(probe['outside_connect_tests']) == 3 and all(not x['connected'] for x in probe['outside_connect_tests']),
            'host_sentinel_hidden': not probe['host_sentinel_visible'] and not probe['host_link_visible'],
            'reviewed_code_readonly': probe['model_code_writable'] == [],
            'no_unapproved_host_mount': not probe['mountinfo_has_windows_or_host_mount'],
            'service_inherits_namespaces': all(x['controller'] == x['ollama'] for x in service['namespace_ids'].values()),
            'service_host_sentinel_hidden': not service['host_sentinel_via_service_root_visible'],
            'service_external_denied': all(not x['connected'] for x in service['external_probes_after_service_start']),
            'inference_real_completed': generation.get('done') is True and generation.get('eval_count', 0) > 0,
            'inference_children_same_boundary': all(x['mount_namespace'] == probe['mount_namespace'] and x['network_namespace'] == probe['network_namespace'] for x in tree['processes']),
        }
        receipt['ready_for_external_boundary_review'] = all(receipt['checks'].values())
    else:
        receipt['ready_for_external_boundary_review'] = False
    (output / 'integration-receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0 if receipt['ready_for_external_boundary_review'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
