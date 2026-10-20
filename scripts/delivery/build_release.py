"""Build the complete judge release: all program sources, tests, examples, the
data the workbench shows, start scripts and documents, plus (on request) the
official Windows embeddable Python so the viewer starts without installation.

    python scripts/delivery/build_release.py --output <new-dir> \
        --document README.md=<path> --document 项目简介.pdf=<path> \
        [--python-zip python-3.12.10-embed-amd64.zip]

The builder copies an explicit allow-list from a clean Git checkout, never a
whole repository; internal review notes, handoff material, raw experiment runs
and one-off research scripts stay out. It refuses to finish when any packaged
text contains a term from --forbid-file (a JSON list kept outside the package).
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import BATCH, PYTHON_SHA, PYTHON_URL, SNAPSHOT  # noqa: E402

# Program, tests and examples: every tracked file under these roots.
CODE_ROOTS = ('credproof/', 'credproof_safety/', 'credproof_access/', 'agent_pilot/', 'tests/',
              'config/', 'deploy/', 'examples/', '.github/workflows/',
              'scripts/bench/', 'scripts/compare/', 'scripts/ci/', 'scripts/runtime/',
              # Evidence the test suite and the comparison page read.
              'docs/compare/onboarding-dotenv/', 'docs/external-scenario/twine/')
# Historical pilot bundles keep the original operator's paths; not needed to run.
EXCLUDED_ROOTS = ('examples/local-agent/',)
# Internal development notes are kept in the repository but not shipped; the
# release holds the program, its tests, examples and the data the workbench reads.
EXCLUDED_FILES = {
    'agent_pilot/holdout-v1/README.md', 'agent_pilot/ui/README.md', 'agent_pilot/protocol-before-safety-fix.json',
    'credproof_safety/tests/data/README.md', 'deploy/docker/README.md',
    'docs/compare/onboarding-dotenv/README.md', 'docs/external-scenario/twine/README.md',
    'docs/external-scenario/twine/freeze-before-run.json',
}
SINGLE_FILES = (
    'README.md', '项目简介.pdf', '评委操作手册.pdf', 'THIRD_PARTY_NOTICES.md', 'pyproject.toml', 'start-credproof.cmd', 'start-credproof.sh', 'start-recheck.cmd', 'start-live.cmd',
    'check-runtime.cmd', '.gitattributes', '.credproof/targets.txt',
    'scripts/delivery/launch.ps1', 'scripts/delivery/launcher/launcher.c', 'scripts/delivery/launcher/launcher.rc',
    'scripts/delivery/launcher/credproof.ico', 'scripts/delivery/launcher/build.sh', 'scripts/delivery/launcher/CredProof.exe', 'scripts/delivery/scan.py', 'scripts/delivery/view_readonly.py',
    'scripts/delivery/check-installed.py', 'scripts/setup-local-agent.cmd', 'scripts/get_gitleaks.py',
    'scripts/demo.py', 'scripts/run-reusable-safety-demo.py', 'scripts/run-external-dotenv-case.py',
    'scripts/run-exported-regression-check.py', 'scripts/prepare-human-review-demo.py',
    # Frozen data shown by the workbench (read-only, no recomputation).
    'docs/bench/bench-results.json', 'docs/compare/comparison.json', 'docs/compare/onboarding-dotenv.json',
    'docs/integration/ci-demo.json',
    'experiments/reusable-tool-safety/20261004-external-dotenv-v5/summary.json',
    'scripts/derive-project-public-bundle.py',
    'scripts/integration/build_ci_demo.py',
    'docs/reusable-tool-safety/acceptance/20261010-format-normalized/public-evidence/normalized-candidate.py',
    'docs/reusable-tool-safety/acceptance/20261007-return-redirect/original-report.json',
    'docs/reusable-tool-safety/acceptance/20261007-return-redirect/context-budget-pilot-v8/public-evidence/initial-report.json',
    'docs/reusable-tool-safety/acceptance/20261009-component-assisted/public-evidence/component-controls-final/unchanged-original-report.json',
    'docs/reusable-tool-safety/acceptance/20261010-format-normalized/public-evidence/original-model-response.json',
)


def tracked():
    out = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT)
    return {p for p in out.decode('utf8').split('\0') if p}


def inventory():
    files = tracked()
    paths = {p for p in files if p.startswith(CODE_ROOTS) and not p.startswith(EXCLUDED_ROOTS)
             and '__pycache__' not in p and p not in EXCLUDED_FILES}
    for name in SINGLE_FILES:
        if name not in files:
            raise ValueError('missing_release_file: ' + name)
        paths.add(name)
    manifest = json.loads((ROOT / SNAPSHOT / 'snapshot-manifest.json').read_text('utf8'))
    paths.add(f'{SNAPSHOT}/snapshot-manifest.json')
    paths.update(f'{SNAPSHOT}/{name}' for name in manifest['files'])
    for case in ('h01', 'h03', 'h07'):
        for method in ('C-agent', 'A-fixed'):
            paths.update(p for p in files if p.startswith(f'{BATCH}/{case}/{method}/')
                         and Path(p).suffix in {'.py', '.json', '.jsonl'})
    missing = [p for p in paths if p not in files]
    if missing:
        raise ValueError('untracked_release_member: ' + ', '.join(sorted(missing)[:5]))
    return sorted(paths)


def forbidden_hits(output, terms, allowed=()):
    """Exact, case-insensitive term hits; digits are bounded so hashes do not match.

    ``allowed`` lists exact third-party strings (for example an upstream
    contributor name) that legitimately contain a term; only those exact
    occurrences are ignored."""
    patterns = [re.compile((r'(?<![0-9A-Fa-f])' + re.escape(t) + r'(?![0-9A-Fa-f])') if t.isdigit()
                           else re.escape(t), re.I) for t in terms]
    hits = []
    for path in sorted(output.rglob('*')):
        if not path.is_file() or path.suffix.lower() in {'.zip', '.exe', '.dll', '.pyd', '.pdf', '.png', '.jpg'}:
            continue
        text = path.read_bytes().decode('utf8', errors='ignore')
        for exact in allowed:
            text = text.replace(exact, ' ' * len(exact))
        for pattern in patterns:
            for match in pattern.finditer(text):
                hits.append({'path': path.relative_to(output).as_posix(), 'term': match.group(0),
                             'line': text.count('\n', 0, match.start()) + 1})
    return hits


def build(output, documents, embedded, forbid, allowed=()):
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT, text=True).strip():
        raise ValueError('commit_changes_before_release_build')
    if output.exists():
        raise ValueError('new_output_required')
    output.mkdir(parents=True)
    members = inventory()
    for rel in members:
        source = ROOT / rel
        if source.is_symlink() or not source.is_file():
            raise ValueError('invalid_release_source: ' + rel)
        target = output / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    for name, source in documents:
        shutil.copyfile(source, output / name)
    # The double-click launcher sits next to start-credproof.cmd; its source is packaged too.
    shutil.copyfile(ROOT / 'scripts/delivery/launcher/CredProof.exe', output / '密证CredProof.exe')
    python = None
    if embedded:
        raw = embedded.read_bytes()
        if hashlib.sha256(raw).hexdigest() != PYTHON_SHA:
            raise ValueError('official_python_zip_hash_mismatch')
        runtime = output / 'runtime/python'
        runtime.mkdir(parents=True)
        with zipfile.ZipFile(embedded) as archive:
            for name in archive.namelist():
                if '/' in name or '\\' in name or name in ('.', '..'):
                    raise ValueError('unexpected_python_zip_layout')
            archive.extractall(runtime)
        (runtime / 'python312._pth').write_text('python312.zip\n.\n..\\..\n', encoding='utf8', newline='\n')
        python = {'version': '3.12.10', 'source': PYTHON_URL, 'download_sha256': PYTHON_SHA}
    hits = forbidden_hits(output, forbid, allowed)
    receipt = {'schema': 'credproof.release/v1', 'team': 'DUIDUI队', 'source_commit': head,
               'members': len(members), 'documents': [n for n, _ in documents], 'embedded_python': python,
               'forbidden_term_hits': len(hits)}
    (output / 'release.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    if hits:
        (output.parent / (output.name + '-forbidden-hits.json')).write_text(
            json.dumps(hits, ensure_ascii=False, indent=1), encoding='utf8')
        raise ValueError(f'forbidden_terms_found: {len(hits)}')
    archive_path = output.parent / (output.name + '.zip')
    if archive_path.exists():
        raise ValueError('new_archive_required')
    with zipfile.ZipFile(archive_path, 'x', zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(output.rglob('*')):
            if file.is_file():
                archive.write(file, (Path(output.name) / file.relative_to(output)).as_posix())
    receipt.update(zip_file=archive_path.name, size=archive_path.stat().st_size,
                   sha256=hashlib.sha256(archive_path.read_bytes()).hexdigest())
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--document', action='append', default=[], help='NAME=PATH copied to the release root')
    parser.add_argument('--python-zip', type=Path)
    parser.add_argument('--forbid-file', type=Path, required=True,
                        help='JSON {terms, allowed_exact} kept outside the package')
    args = parser.parse_args()
    docs = []
    for item in args.document:
        name, _, path = item.partition('=')
        if not name or '/' in name or '\\' in name or not path:
            raise SystemExit('--document expects NAME=PATH with a plain file name')
        docs.append((name, Path(path).resolve(strict=True)))
    spec = json.loads(args.forbid_file.read_text('utf8'))
    terms, allowed = spec.get('terms'), spec.get('allowed_exact', [])
    if not isinstance(terms, list) or not all(isinstance(t, str) and t for t in terms + allowed):
        raise SystemExit('--forbid-file must be {"terms": [...], "allowed_exact": [...]} with non-empty strings')
    build(args.output.resolve(), docs, args.python_zip.resolve(strict=True) if args.python_zip else None, terms, allowed)
