"""Run only fixed boundary probes and retain their real observations."""
from pathlib import Path
import base64
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from agent_pilot.isolation import BOOTSTRAP, RUNNER, probe_isolation


def nested_probe():
    source = RUNNER.read_bytes()
    packet = {'runner_b64': base64.b64encode(source).decode('ascii'),
              'request': {'operation': 'probe'}}
    # Fixed trusted launcher. Only lo is brought up; no veth or route is created.
    outer = "import subprocess\nsubprocess.run(['/usr/sbin/ip','link','set','lo','up'],check=True)\n" + BOOTSTRAP
    command = ['env', 'HOME=/home/tingfeng/credproof-agent-runtime/service-home',
               'unshare', '--user', '--map-root-user', '--net', '--fork',
               'python3', '-I', '-c', outer]
    if sys.platform != 'linux':
        command = ['wsl.exe', '-d', 'Ubuntu-24.04', '-u', 'tingfeng', '--', *command]
    result = subprocess.run(command, input=json.dumps(packet).encode(),
                            capture_output=True, timeout=30)
    if result.returncode:
        raise RuntimeError('Nested probe supervisor failed: ' + result.stderr.decode(errors='replace'))
    return json.loads(result.stdout)


if __name__ == '__main__':
    destination = Path(__file__).parent / ('observations-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    destination.mkdir()
    normal = probe_isolation()
    (destination / 'probe-normal.json').write_text(json.dumps(normal, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    nested = nested_probe()
    (destination / 'probe-nested.json').write_text(json.dumps(nested, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    result = {'normal_ready': normal.get('ready'), 'nested_ready': nested.get('ready'),
              'normal_checks': len(normal.get('checks', {})), 'nested_checks': len(nested.get('checks', {})),
              'runner_id': hashlib.sha256(RUNNER.read_bytes()).hexdigest(),
              'candidate_executed': False, 'observations': destination.name,
              'nested_parent_home': '/home/tingfeng/credproof-agent-runtime/service-home'}
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if normal.get('ready') and nested.get('ready') else 2)
