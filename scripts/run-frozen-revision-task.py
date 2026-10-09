"""Register and run exactly one authorised p01 task. Refuse existing output."""
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[1]
dest = Path(sys.argv[1]).resolve()
dest.mkdir(parents=True, exist_ok=False)
paths = ['credproof_safety/agent.py', 'agent_pilot/model_client.py',
         'agent_pilot/tools.py', 'agent_pilot/requirements-lock.txt',
         'examples/material_assistant/credproof.toml', 'examples/material_assistant/tool.py',
         'examples/material_assistant/tests/test_business.py']
freeze = {
    'registered_at': datetime.now(timezone.utc).isoformat(),
    'tested_source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
    'task': 'assistant-original/p01', 'model': 'qwen3-coder:30b',
    'python': platform.python_version(), 'scope': '5090 existing reviewed isolation; no 5060',
    'budgets': {'model_requests': 12, 'model_tools': 12, 'candidates': 3,
                'program_verifications': 3, 'format_corrections': 1,
                'request_seconds': 120, 'task_seconds': 900,
                'context': 16384, 'output_tokens': 1024},
    'files': {p: hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths},
    'command': ['.venv/Scripts/python.exe', '-m', 'credproof_safety', 'repair',
                '--config', 'examples/material_assistant/credproof.toml', '--output',
                dest.relative_to(root).as_posix() + '/result.json'],
    'retry': False,
}
(dest/'freeze.json').write_text(json.dumps(freeze, indent=2)+'\n', encoding='utf8')
with (dest/'stdout.txt').open('wb') as stdout, (dest/'stderr.txt').open('wb') as stderr:
    p = subprocess.run([sys.executable, *freeze['command'][1:]], cwd=root,
                       stdout=stdout, stderr=stderr, timeout=1000)
(dest/'command-receipt.json').write_text(json.dumps({'exit_code': p.returncode,
    'ended_at': datetime.now(timezone.utc).isoformat(), 'model_tasks_registered': 1}, indent=2)+'\n', encoding='utf8')
print('registered_source=' + freeze['tested_source_commit'])
print('exit_code=' + str(p.returncode))
raise SystemExit(p.returncode)
