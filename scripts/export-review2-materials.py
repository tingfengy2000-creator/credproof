"""Create three new self-contained synthetic material sets; never overwrite."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from credproof import core
from credproof.portable import export_package, recheck_package
from credproof.scanner import Gitleaks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--gitleaks', type=Path, default=ROOT / '.tools/gitleaks-8.28.0/gitleaks.exe')
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('Refuse to overwrite an earlier material set')
    scanner = Gitleaks(args.gitleaks, ROOT / 'config/synthetic-gitleaks.toml')
    args.output.mkdir(parents=True)
    rows = []
    with tempfile.TemporaryDirectory(prefix='credproof-material-authoring-') as temporary:
        work = Path(temporary)
        for name in ('accepted', 'rejected', 'stale'):
            repo = work / name / 'repo'
            bundle = work / name / 'copy'
            repo.mkdir(parents=True)
            subprocess.run(['git', '-c', 'core.hooksPath=', 'init', '--quiet', str(repo)], check=True)
            (repo / 'config.py').write_text('import os\nSERVICE_TOKEN = "CP_SYNTH_' + 'A5' * 12 + '"\n\ndef authorization_header():\n    return "Bearer " + SERVICE_TOKEN\n', encoding='utf-8', newline='\n')
            (repo / 'notes.txt').write_text('Synthetic companion file; must remain byte-identical.\n', encoding='utf-8', newline='\n')
            subprocess.run(['git', '-c', 'core.hooksPath=', '-c', 'core.autocrlf=false', '-C', str(repo), 'add', '--', 'config.py', 'notes.txt'], check=True)
            core.freeze(repo, bundle, scanner, allow_fixture=True, edit_policy='python-env-v2')
            target = bundle / 'candidate/config.py'
            if name == 'rejected':
                target.write_bytes(target.read_bytes().replace(b'os.environ["CP_DEMO_TOKEN"]', b'"ordinary-placeholder"'))
            evidence = core.collect(bundle, scanner)
            report = core.assess(bundle, evidence, scanner)
            files, errors = core._tree(bundle / 'candidate')
            assert not errors
            history = [{'label': 'actual-check-before-export', 'evidence': evidence, 'report': report, 'candidate_files': files}]
            if name == 'stale':
                # Actual prior object is preserved above. A permitted edit still
                # changes its identity and requires a new check.
                target.write_bytes(target.read_bytes() + b'\n# Allowed documentation comment after the saved PASS.\n')
            package = export_package(bundle, scanner, args.output / name, history=history, synthetic_confirmed=True)
            fresh = recheck_package(package, args.gitleaks)
            core.write_json(args.output / (name + '-recheck.json'), fresh)
            rows.append({'material': name, 'saved_verdict': report['verdict'],
                         'old_evidence_applicability': fresh['old_evidence_applicability']['status'],
                         'fresh_verdict': fresh['fresh_report']['verdict'],
                         'old_object_verified': fresh['history'][0]['old_object_material_matches_receipt']})
    # Assertions are demo requirements, never inputs to the verifier.
    assert [(r['old_evidence_applicability'], r['fresh_verdict']) for r in rows] == [
        ('APPLICABLE', 'PASS'), ('APPLICABLE', 'FAIL'), ('INAPPLICABLE', 'PASS')]
    core.write_json(args.output / 'generation-results.json', {'generated_at_utc': core.utc_now(), 'cases': rows,
                    'note': 'Three illustrative synthetic sets, not additional evaluation samples.'})
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
