"""Reproduce the host-dependent project-tree digest (read-only; no project code runs).

`credproof_safety.project._digest_tree` hashes an ordered list built from
`sorted(root.rglob("*"))`. Path ordering is case-insensitive on Windows and
case-sensitive on POSIX, so identical bytes give different digests when file
names differ only in letter case at the sort boundary (e.g. README.md vs
credproof.toml). This script recomputes the digest of the disclosed v001
snapshot under both orderings and compares with the stored report.

Usage:  python -I docs/handoff/frontend-5060-intake/tree-order-repro.py [--output FILE]
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform

ROOT = Path(__file__).resolve().parents[3]
VERSION = ROOT / ('docs/reusable-tool-safety/acceptance/20261010-human-review/public-evidence/'
                  'workspace/runs/human-review/939e25f42bb142f39567c5cb644ebc6d/versions/v001')
IGNORED = {'.git', '.venv', '__pycache__', '.credproof'}


def digest(project, key):
    rows = []
    for path in sorted(project.rglob('*'), key=key):
        rel = path.relative_to(project)
        if any(part in IGNORED for part in rel.parts):
            continue
        if path.is_file() and not path.is_symlink():
            rows.append((rel.as_posix(), hashlib.sha256(path.read_bytes()).hexdigest()))
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode()).hexdigest(), [r[0] for r in rows]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    project = VERSION / 'project'
    stored = json.loads((VERSION / 'reports/check-01.json').read_text(encoding='utf8'))['project_tree_sha256']
    native, native_order = digest(project, None)  # exactly what _digest_tree does on this host
    posix, posix_order = digest(project, lambda p: p.relative_to(project).parts)
    windows, windows_order = digest(project, lambda p: [s.lower() for s in p.relative_to(project).parts])
    result = {
        'kind': 'TREE_ORDER_REPRODUCTION', 'host': platform.platform(), 'python': platform.python_version(),
        'stored_report_project_tree_sha256': stored,
        'this_host_native_sorted': {'sha256': native, 'order': native_order, 'matches_report': native == stored},
        'case_sensitive_order': {'sha256': posix, 'order': posix_order, 'matches_report': posix == stored},
        'windows_casefold_order': {'sha256': windows, 'order': windows_order, 'matches_report': windows == stored},
        'executed_project_code': False, 'model_calls': 0,
    }
    text = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        if args.output.exists():
            raise ValueError('new_output_required')
        args.output.write_text(text, encoding='utf8', newline='\n')
    print(text, end='')


if __name__ == '__main__':
    main()
