"""Copy a disclosed history snapshot and installed UI into a NEW data workspace.

No project code, model, check or approval is executed by this preparation step.
The snapshot is history; the browser's recheck executes the actual checker.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import agent_pilot

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--snapshot', type=Path, required=True)
parser.add_argument('--workspace', type=Path, required=True)
args = parser.parse_args()
manifest = json.loads((args.snapshot/'snapshot-manifest.json').read_text(encoding='utf8'))
if args.workspace.exists():
    raise ValueError('new_workspace_required; existing data will not be replaced')
for name, expected in manifest['files'].items():
    rel = PurePosixPath(name)
    source = args.snapshot/name
    if rel.is_absolute() or '..' in rel.parts or source.is_symlink() or not source.is_file():
        raise ValueError('unsafe_or_missing_snapshot_file: '+name)
    if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
        raise ValueError('snapshot_bytes_changed: '+name)
args.workspace.mkdir(parents=True)
for name in manifest['files']:
    target = args.workspace/name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes((args.snapshot/name).read_bytes())
shutil.copytree(Path(agent_pilot.__file__).parent/'ui', args.workspace/'agent_pilot/ui')
print(json.dumps({'kind':'HISTORY_SNAPSHOT_PREPARATION', 'model_calls':0,
    'execution_performed':False, 'files_verified':len(manifest['files']),
    'installed_ui_source':str(Path(agent_pilot.__file__).parent/'ui'),
    'workspace':str(args.workspace), 'note':'History derivative, not new inference or fresh PASS.'}))
