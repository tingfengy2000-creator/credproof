"""Three-step real demonstration on a newly created, synthetic-only repository.

No existing repository is scanned or modified. Expected answers below are demo
assertions, never inputs to the validator. All displayed verdicts come from it.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from credproof.core import assess, collect, freeze, public_contract, write_json
from credproof.scanner import Gitleaks


def git(repo, *args):
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull, GIT_OPTIONAL_LOCKS='0')
    return subprocess.run(['git', '-c', 'core.autocrlf=false', '-c', 'core.hooksPath=',
                           '-C', str(repo), *args], capture_output=True, check=True,
                          timeout=10, env=env).stdout


def original_state(repo):
    return {layer: {name: hashlib.sha256(
        (repo / name).read_bytes() if layer == 'worktree' else git(repo, 'show', ':' + name)
    ).hexdigest() for name in ('config.py', 'notes.txt')} for layer in ('worktree', 'index')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'runs/demo')
    parser.add_argument('--gitleaks', type=Path, default=ROOT / '.tools/gitleaks-8.28.0' /
                        ('gitleaks.exe' if sys.platform == 'win32' else 'gitleaks'))
    args = parser.parse_args()
    run = args.output.resolve() / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid.uuid4().hex[:8])
    repo, bundle, public = run / 'source', run / 'bundle', run / 'public'
    repo.mkdir(parents=True, exist_ok=False)
    public.mkdir()
    git(repo, 'init', '--quiet')
    marker = 'CP_SYNTH_' + 'A5' * 12
    source = ('import os\nSERVICE_TOKEN = "' + marker + '"\n\n'
              'def authorization_header():\n    return "Bearer " + SERVICE_TOKEN\n')
    (repo / 'config.py').write_text(source, encoding='utf-8', newline='\n')
    (repo / 'notes.txt').write_text('This companion file must stay unchanged.\n', encoding='utf-8')
    git(repo, 'add', '--', 'config.py', 'notes.txt')
    original = original_state(repo)
    scanner = Gitleaks(args.gitleaks, ROOT / 'config/synthetic-gitleaks.toml')
    freeze(repo, bundle, scanner, source='index', allow_fixture=True)
    target = bundle / 'candidate/config.py'
    planned = target.read_bytes()
    write_json(public / 'contract-view.json', public_contract(bundle))
    rows = []

    def show(step, evidence, *, fresh):
        report = assess(bundle, evidence, scanner)
        write_json(public / (step + '-evidence.json'), evidence)
        write_json(public / (step + '-report.json'), report)
        row = {'step': step, 'verdict': report['verdict'], 'applicability': report['applicability'],
               'checks': {k: v['status'] for k, v in report['obligations'].items()},
               'fresh_checks_executed': fresh}
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
        return report

    # Step 1: removes the marker, but silently ignores the required environment value.
    target.write_bytes(planned.replace(b'os.environ["CP_DEMO_TOKEN"]', b'"ordinary-placeholder"'))
    bad = show('01-zero-alert-broken-behavior', collect(bundle, scanner), fresh=True)
    assert bad['obligations']['scan']['status'] == 'PASS'
    assert bad['obligations']['function']['status'] == 'FAIL' and bad['verdict'] == 'FAIL'

    # Step 2: the exact planned edit preserves the controlled behavior and passes.
    target.write_bytes(planned)
    good_evidence = collect(bundle, scanner)
    good = show('02-valid-repair', good_evidence, fresh=True)
    assert good['verdict'] == 'PASS'
    assert good['remaining_risks']['index']['presence'] == 'PRESENT'
    assert good['remaining_risks']['external_revocation'] == 'UNKNOWN'

    # Step 3: outside the authorized edit, despite no effect on the small function.
    with (bundle / 'candidate/notes.txt').open('ab') as stream:
        stream.write(b'Unexpected extra modification after acceptance.\n')
    stale = show('03-old-pass-not-applicable', good_evidence, fresh=False)
    assert stale['verdict'] == 'UNKNOWN' and stale['applicability'] == 'STALE_OR_MISMATCHED'
    fresh = show('04-rechecked-drift', collect(bundle, scanner), fresh=True)
    assert fresh['verdict'] == 'FAIL' and fresh['obligations']['allowed_changes']['status'] == 'FAIL'
    unchanged = original == original_state(repo)
    assert unchanged, 'Controlled source unexpectedly changed'
    result = {'steps': rows, 'original_worktree_and_index_unchanged': unchanged,
              'scope': ['config.py', 'notes.txt'], 'synthetic_only': True,
              'bundle_relative_path': 'bundle',
              'recheck_command': 'python -m credproof recheck --bundle "' + str(bundle) + '"',
              'expected_final_state': 'The candidate intentionally retains the extra modification; a fresh recheck must FAIL.'}
    write_json(public / 'story.json', result)
    print(json.dumps({'story': str(public / 'story.json'), 'bundle': str(bundle),
                      'original_unchanged': unchanged}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
