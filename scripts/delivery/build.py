"""Allowlisted judge viewer. Requires an operator-downloaded official Python ZIP.

No download, environment execution, model call or safety check is performed.
The source tree must be a fixed clean commit (untracked local evidence ignored).
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

from scan import scan

ROOT = Path(__file__).resolve().parents[2]
BATCH = 'experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison'
SNAPSHOT = 'docs/reusable-tool-safety/acceptance/20261010-human-review/public-evidence/workspace'
PYTHON_URL = 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip'
PYTHON_SHA = '4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3'


def inventory():
    """Positive list: exact program/data roots and extensions, not a repo copy."""
    paths = set()
    for package in ('agent_pilot','credproof_safety','credproof_access'):
        paths.update(p for p in (ROOT/package).glob('*.py') if not p.name.startswith('test_'))
    for ext in ('html','js','css'):
        paths.update((ROOT/'agent_pilot/ui').glob('*.'+ext))
    for folder in ('fixtures','holdout-v1'):
        paths.add(ROOT/'agent_pilot'/folder/'manifest.json')
        paths.update((ROOT/'agent_pilot'/folder).glob('*/tool.py'))
        if (ROOT/'agent_pilot'/folder/'requirements.md').is_file(): paths.add(ROOT/'agent_pilot'/folder/'requirements.md')
    for example in ('material_assistant','material_assistant_fixed'):
        paths.update(p for p in (ROOT/'examples'/example).rglob('*') if p.is_file() and p.suffix in {'.py','.toml','.md'} and '__pycache__' not in p.parts)
    # The eight benchmark targets are offered as ready-made examples on the "new check" page.
    paths.update(p for p in (ROOT/'examples/bench').rglob('*') if p.is_file() and p.suffix in {'.py','.toml','.json'} and '__pycache__' not in p.parts)
    manifest=json.loads((ROOT/SNAPSHOT/'snapshot-manifest.json').read_text('utf8'))
    paths.add(ROOT/SNAPSHOT/'snapshot-manifest.json')
    paths.update(ROOT/SNAPSHOT/name for name in manifest['files'])
    for case in ('h01','h03','h07'):
        for method in ('C-agent','A-fixed'):
            paths.update(p for p in (ROOT/BATCH/case/method).rglob('*') if p.is_file() and p.suffix in {'.py','.json','.jsonl'} and '__pycache__' not in p.parts)
    paths.update(ROOT/name for name in ('docs/bench/bench-results.json','docs/integration/ci-demo.json','docs/compare/comparison.json','docs/compare/onboarding-dotenv.json','config/runtime.example.json',
                'agent_pilot/data/runtime.example.json','start-credproof.cmd','start-credproof.sh',
                'start-recheck.cmd','start-live.cmd','scripts/delivery/launch.ps1','scripts/delivery/scan.py'))
    # The judge gets usage, not internal review/handoff documents or the build tool.
    paths.add(ROOT/'docs/delivery/VIEWER.md')
    return sorted(paths)


def build(output, embedded):
    source_sha = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if subprocess.check_output(['git','diff','HEAD','--name-only'],cwd=ROOT,text=True).strip():
        raise ValueError('commit_program_changes_before_delivery_build')
    if output.exists(): raise ValueError('new_output_required')
    raw=embedded.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PYTHON_SHA: raise ValueError('official_python_zip_hash_mismatch')
    output.mkdir(parents=True)
    for source in inventory():
        rel=source.relative_to(ROOT)
        if source.is_symlink() or not source.is_file(): raise ValueError('invalid_allowlisted_source')
        target=output/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    runtime=output/'runtime/python';runtime.mkdir(parents=True)
    with zipfile.ZipFile(embedded) as archive:
        for name in archive.namelist():
            if '/' in name or '\\' in name or name in ('.','..'): raise ValueError('unexpected_python_zip_layout')
        archive.extractall(runtime)
    # Windows embeddable getpath needs Windows separators for a two-parent
    # path; '../..' resolved to only one parent in the 3.12.10 real probe.
    (runtime/'python312._pth').write_text('python312.zip\n.\n..\\..\n',encoding='utf8',newline='\n')
    receipt={'schema':'credproof.judge-viewer/v1','source_commit':source_sha,'python':{'version':'3.12.10',
             'source':PYTHON_URL,'download_sha256':PYTHON_SHA,'pth':'python312.zip; .; Windows two-parent relative root; no site'},
             'mode':'view','model_calls':0,'whitelist_files':[p.relative_to(ROOT).as_posix() for p in inventory()]}
    (output/'delivery.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    report=scan(output,['tingfengy2000-creator','tingfeng'])
    report_path=output.parent/(output.name+'-scan.json')
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    if report['sensitive_hits']: raise ValueError('delivery_scan_failed; inspect external scan receipt')
    archive_path=output.parent/(output.name+'.zip')
    if archive_path.exists(): raise ValueError('new_archive_required')
    with zipfile.ZipFile(archive_path,'x',zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(output.rglob('*')):
            if file.is_file():archive.write(file,file.relative_to(output).as_posix())
    receipt.update(zip_file=archive_path.name,size=archive_path.stat().st_size,sha256=hashlib.sha256(archive_path.read_bytes()).hexdigest(),scan_file=report_path.name)
    (output.parent/(output.name+'-receipt.json')).write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:receipt[k] for k in ('source_commit','zip_file','size','sha256')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--python-zip',type=Path,required=True)
    a=p.parse_args();build(a.output.resolve(),a.python_zip.resolve(strict=True))
