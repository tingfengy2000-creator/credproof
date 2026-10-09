"""Installed-package, no-model recheck of an explicitly supplied review bundle."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import time
import credproof_safety.project_bundle as bundles
import credproof_safety.runner as runner
import credproof_access

ap = argparse.ArgumentParser()
ap.add_argument('--bundle', type=Path, required=True)
ap.add_argument('--output', type=Path, required=True)
ap.add_argument('--receipt', type=Path, required=True)
args = ap.parse_args()
if args.receipt.exists():
    raise ValueError('new receipt required')
began = time.monotonic()
result = bundles.recheck_project_bundle(args.bundle, args.output)
validation = result.get('validation', {})
receipt = {'kind': 'PUBLIC_RETRIEVAL_NO_MODEL_RECHECK',
           'model_calls': 0, 'interpreter': sys.executable,
           'isolated_python': sys.flags.isolated,
           'package_version': importlib.metadata.version('credproof-safety'),
           'module_origins': {m.__name__: {'file': m.__file__, 'sha256':
               hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()}
               for m in (bundles, runner, credproof_access)},
           'candidate_sha256': result.get('candidate_sha256'),
           'prior_report_applicable': result.get('prior_report_applicable'),
           'status': result.get('status'), 'verdict': validation.get('verdict'),
           'elapsed_s': round(time.monotonic() - began, 3),
           'note': 'Wrapper exit 0 means recheck completed, not a safe repair. Read verdict and real pytest observation.'}
args.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
print(json.dumps({'status': receipt['status'], 'verdict': receipt['verdict'],
                  'prior_report_applicable': receipt['prior_report_applicable']}))
raise SystemExit(0 if result.get('status') == 'RECHECKED' and validation.get('verdict') in ('PASS','FAIL') else 2)
