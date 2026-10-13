"""Fixed harmless namespace/import probe; never executes project code."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile

from .runtime_setup import safe_root, supported, verify_runtime

PROBE = '''import json,os,sys
sys.path.insert(0, '/tmp/site')
import pytest
from pathlib import Path
checks = {name: not Path(name).exists() for name in ['/home','/workspace','/opt/credproof']}
checks['pytest_import'] = bool(pytest.__version__)
Path('/tmp/scratch').write_text('fixed-probe')
checks['private_scratch'] = Path('/tmp/scratch').read_text() == 'fixed-probe'
checks['proc_mounted'] = Path('/proc/self/status').is_file()
checks['namespaces_distinct'] = all(os.readlink('/proc/self/ns/'+n) != v for n,v in json.loads(sys.argv[1]).items())
checks['capabilities_dropped'] = 'CapEff:\\t0000000000000000' in Path('/proc/self/status').read_text()
checks['root_readonly'] = next(x for x in Path('/proc/mounts').read_text().splitlines() if x.split()[1]=='/').split()[3].split(',')[0]=='ro'
print(json.dumps({'checks':checks,'pytest_version':pytest.__version__}))
'''


def doctor(root=None):
    report = {'schema': 'credproof.doctor/v1', 'ready': False, 'checks': {}, 'hints': []}
    try:
        supported()
        if root is None:
            from agent_pilot.runtime_config import linux_runtime_root
            root = linux_runtime_root()
        root = safe_root(root)
        receipt = verify_runtime(root)
        report['checks']['materials_verified'] = True
        report['runtime_identity'] = {k: receipt[k] for k in ('lock_sha256','manifest_sha256','bwrap_sha256')}
        ids = {n: os.readlink('/proc/self/ns/'+n) for n in ('user','net','pid','mnt')}
        with tempfile.TemporaryDirectory(prefix='credproof-doctor-') as tmp:
            script = Path(tmp) / 'probe.py'
            script.write_text(PROBE, encoding='utf8')
            cmd = [str(root / 'isolation/tools/usr/bin/bwrap'), '--unshare-all', '--die-with-parent',
                   '--new-session', '--cap-drop', 'ALL', '--clearenv', '--setenv', 'PATH', '/usr/bin',
                   '--ro-bind', str(root / 'isolation/rootfs'), '/', '--proc', '/proc', '--dev', '/dev',
                   '--remount-ro', '/dev', '--tmpfs', '/tmp', '--dir', '/tmp/site',
                   '--ro-bind', str(root / 'venv/lib/python3.12/site-packages'), '/tmp/site',
                   '--ro-bind', str(script), '/tmp/probe.py', '--', '/usr/bin/python3', '-I', '-B',
                   '/tmp/probe.py', json.dumps(ids)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30,
                                    env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
        report['probe_exit_code'] = result.returncode
        # Fixed trusted probe output only. Preserve it for namespace failures;
        # no arbitrary project or model output is run by this command.
        report['probe_stdout'] = result.stdout[-16384:]
        report['probe_stderr'] = result.stderr[-16384:]
        if result.returncode:
            report['checks']['namespace_probe'] = False
            report['hints'].append('Namespace/proc probe failed. Check Docker systempaths/seccomp and host AppArmor; see docs/integration/linux.md.')
            report['diagnostic_code'] = 'namespace_probe_failed'
        else:
            observed = json.loads(result.stdout)
            report['checks'].update(observed['checks'])
            report['pytest_version'] = observed['pytest_version']
            report['ready'] = all(v is True for v in report['checks'].values())
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        report['checks']['preconditions'] = False
        report['diagnostic_code'] = type(exc).__name__
        report['hints'].append('Use a verified non-root Ubuntu 24.04 / Python 3.12 runtime; prepare a new versioned root if materials changed.')
    return report
