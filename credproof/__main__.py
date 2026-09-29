"""CLI for a local, synthetic-only acceptance pilot."""
import argparse
import json
from pathlib import Path
import sys
import subprocess
import uuid

from .core import assess, collect, freeze, public_contract, write_json
from .scanner import Gitleaks

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description='CredProof synthetic-only repair acceptance pilot')
    parser.add_argument('--gitleaks', type=Path, default=ROOT / '.tools/gitleaks-8.28.0' / ('gitleaks.exe' if sys.platform == 'win32' else 'gitleaks'))
    parser.add_argument('--config', type=Path, default=ROOT / 'config/synthetic-gitleaks.toml')
    sub = parser.add_subparsers(dest='action', required=True)
    begin = sub.add_parser('freeze', help='Read a synthetic worktree/index and create a new controlled candidate')
    begin.add_argument('--repo', type=Path, required=True)
    begin.add_argument('--bundle', type=Path, required=True)
    begin.add_argument('--source', choices=['index', 'worktree'], default='index')
    begin.add_argument('--scope', nargs='+', default=['config.py', 'notes.txt'])
    begin.add_argument('--target', default='config.py')
    begin.add_argument('--env-name', default='CP_DEMO_TOKEN')
    begin.add_argument('--allow-fixture', action='store_true', help='Authorize only the closed authorization-header-v1 fixture grammar')
    for name in ('check', 'recheck', 'validate-evidence'):
        command = sub.add_parser(name)
        command.add_argument('--bundle', type=Path, required=True)
        if name == 'validate-evidence':
            command.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    try:
        scanner = Gitleaks(args.gitleaks, args.config)
        if args.action == 'freeze':
            contract = freeze(args.repo, args.bundle, scanner, source=args.source, scope=args.scope,
                              target=args.target, env_name=args.env_name, allow_fixture=args.allow_fixture)
            print(json.dumps({'contract_id': contract['contract_id'], 'candidate': str(args.bundle / 'candidate'),
                              'note': 'Synthetic-only candidate created; no acceptance has run'}, ensure_ascii=False))
            return 0
        if args.action == 'validate-evidence':
            evidence = json.loads(args.evidence.read_text(encoding='utf-8'))
        else:
            # Both check and recheck read material and execute the checks; neither reads a saved report verdict.
            evidence = collect(args.bundle, scanner)
        report = assess(args.bundle, evidence, scanner)
        output = args.bundle / 'public' / ('check-' + uuid.uuid4().hex[:12])
        output.mkdir(parents=True, exist_ok=False)
        write_json(output / 'evidence.json', evidence)
        write_json(output / 'report.json', report)
        write_json(output / 'contract-view.json', public_contract(args.bundle))
        (output / 'README.txt').write_text(
            'Sanitized, local evidence record. Not a signature, third-party attestation or security proof.\n'
            'Recheck needs the matching local contract, before material, candidate and private witness.\n'
            'Run: python -m credproof recheck --bundle <local-bundle>\n'
            'The public record alone cannot reproduce unavailable private material.\n', encoding='utf-8')
        print(json.dumps({'verdict': report['verdict'], 'applicability': report['applicability'],
                          'obligations': {k: v['status'] for k, v in report['obligations'].items()},
                          'remaining_risks': report.get('remaining_risks'), 'report': str(output / 'report.json'),
                          'fresh_checks_executed': args.action != 'validate-evidence'}, ensure_ascii=False))
        return {'PASS': 0, 'FAIL': 1, 'UNKNOWN': 2}[report['verdict']]
    except (ValueError, OSError, KeyError, SyntaxError, subprocess.SubprocessError) as error:
        # Do not emit exception text: parser errors can contain source lines and raw values.
        print(json.dumps({'verdict': 'UNKNOWN', 'reason': 'invalid_or_missing_required_material',
                          'error_type': type(error).__name__}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
